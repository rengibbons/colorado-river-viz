"""REST clients for public Colorado River Basin data sources.

- USGS Water Data OGC API (streamflow): https://api.waterdata.usgs.gov/ogcapi/v1/
- Bureau of Reclamation RISE API (reservoir elevations): https://data.usbr.gov/rise-api
- USDA NRCS AWDB REST API (SNOTEL snowpack): https://wcc.sc.egov.usda.gov/awdbRestApi/swagger-ui/index.html
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import requests

from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import (
    DataSource,
    HttpClient,
    build_client,
    get_json,
)
from colorado_river_viz.schema import (
    Approval,
    Unit,
    canonical_frame,
    empty_canonical_frame,
)
from colorado_river_viz.settings import Settings

USGS_DAILY_VALUES_URL = (
    "https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items"
)
USGS_PAGE_LIMIT = 50_000
USGS_DAILY_MEAN_STATISTIC_ID = "00003"
_USGS_UNITS: dict[str, Unit] = {"ft^3/s": "cfs"}
_USGS_APPROVALS: dict[str, Approval] = {
    "Approved": "approved",
    "Provisional": "provisional",
}
RISE_RESULT_URL = "https://data.usbr.gov/rise/api/result"
AWDB_DATA_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"

REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class DateRange:
    """An inclusive start/end date range for a data query."""

    start: date
    end: date


def _default_client(source: DataSource) -> HttpClient:
    return build_client(source, Settings())


def _iter_usgs_daily_pages(
    client: HttpClient,
    monitoring_location_id: str,
    parameter_code: str,
    date_range: DateRange,
) -> Iterator[list[dict[str, Any]]]:
    """Yield each page of daily-mean records, oldest first, following ``next`` links.

    Without ``sortby`` the API returns rows in arbitrary order, so a single capped
    page is a scattered sample rather than a contiguous window.
    """
    url: str | None = USGS_DAILY_VALUES_URL
    params: dict[str, str | int] | None = {
        "monitoring_location_id": monitoring_location_id,
        "parameter_code": parameter_code,
        "statistic_id": USGS_DAILY_MEAN_STATISTIC_ID,
        "datetime": f"{date_range.start.isoformat()}/{date_range.end.isoformat()}",
        "sortby": "time",
        "skipGeometry": "true",
        "properties": "time,value,approval_status,unit_of_measure",
        "limit": USGS_PAGE_LIMIT,
        "f": "json",
    }
    while url is not None:
        payload = get_json(client, url, params)
        yield [feature["properties"] for feature in payload["features"]]
        url = _next_link(payload)
        params = None  # the next link already carries every query parameter


def _next_link(payload: dict[str, Any]) -> str | None:
    for link in payload.get("links", []):
        if link.get("rel") == "next":
            href: str = link["href"]
            return href
    return None


def _usgs_records(
    client: HttpClient,
    monitoring_location_id: str,
    parameter_code: str,
    date_range: DateRange,
) -> pd.DataFrame:
    records = [
        record
        for page in _iter_usgs_daily_pages(
            client, monitoring_location_id, parameter_code, date_range
        )
        for record in page
    ]
    columns = ["time", "value", "approval_status", "unit_of_measure"]
    return pd.DataFrame.from_records(records, columns=columns)


def fetch_usgs_daily_values(
    monitoring_location_id: str, parameter_code: str, date_range: DateRange
) -> pd.DataFrame:
    """Fetch a daily-mean time series for one USGS monitoring location and parameter.

    Returns every day in ``date_range``, indexed by ``time`` and sorted, with
    columns ``value`` and ``unit_of_measure``.

    Source: https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily
    Example: monitoring_location_id="USGS-09380000" (Lees Ferry, AZ),
    parameter_code="00060" (discharge, cfs)
    """
    frame = _usgs_records(
        _default_client(DataSource.USGS),
        monitoring_location_id,
        parameter_code,
        date_range,
    )
    frame["time"] = pd.to_datetime(frame["time"])
    frame["value"] = pd.to_numeric(frame["value"])
    return frame.sort_values("time").set_index("time")[["value", "unit_of_measure"]]


def fetch_usgs_daily_canonical(
    client: HttpClient,
    series_id: str,
    monitoring_location_id: str,
    parameter_code: str,
    date_range: DateRange,
) -> pd.DataFrame:
    """Fetch a USGS daily-mean series in the canonical cache schema (design §4)."""
    frame = _usgs_records(client, monitoring_location_id, parameter_code, date_range)
    if frame.empty:
        return empty_canonical_frame()
    units = set(frame["unit_of_measure"])
    if len(units) != 1 or next(iter(units)) not in _USGS_UNITS:
        raise UnexpectedSourceFormatError(f"{series_id}: unexpected units {units}")
    return canonical_frame(
        series_id=series_id,
        dates=pd.to_datetime(frame["time"]),
        values=pd.to_numeric(frame["value"]),
        unit=_USGS_UNITS[next(iter(units))],
        approval=frame["approval_status"]
        .map(_USGS_APPROVALS)
        .fillna("unknown")
        .astype(str),
    )


def fetch_rise_time_series(catalog_item_id: int, date_range: DateRange) -> pd.DataFrame:
    """Fetch a daily time series from Reclamation's RISE API for one catalog item.

    Source: https://data.usbr.gov/rise-api
    Example catalog items: 508 (Lake Powell elevation, ft),
    6123 (Lake Mead elevation, ft)
    """
    params: dict[str, str | int] = {
        "itemId": catalog_item_id,
        "dateTime[after]": date_range.start.isoformat(),
        "dateTime[before]": date_range.end.isoformat(),
        "itemsPerPage": 10000,
    }
    response = requests.get(
        RISE_RESULT_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    records = [row["attributes"] for row in response.json()["data"]]
    frame = pd.DataFrame.from_records(records)
    frame["dateTime"] = pd.to_datetime(frame["dateTime"])
    frame["result"] = pd.to_numeric(frame["result"])
    return frame.sort_values("dateTime").set_index("dateTime")[["result"]]


def fetch_snotel_daily_values(
    station_triplet: str, element_code: str, date_range: DateRange
) -> pd.DataFrame:
    """Fetch a daily SNOTEL/AWDB element time series for one station.

    Source: https://wcc.sc.egov.usda.gov/awdbRestApi/swagger-ui/index.html
    Example: station_triplet="713:CO:SNTL" (Red Mountain Pass, CO),
    element_code="WTEQ" (snow water equivalent, in)
    """
    params = {
        "stationTriplets": station_triplet,
        "elements": element_code,
        "duration": "DAILY",
        "beginDate": date_range.start.isoformat(),
        "endDate": date_range.end.isoformat(),
    }
    response = requests.get(
        AWDB_DATA_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    values = response.json()[0]["data"][0]["values"]
    frame = pd.DataFrame.from_records(values)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["value"] = pd.to_numeric(frame["value"])
    return frame.sort_values("date").set_index("date")[["value"]]
