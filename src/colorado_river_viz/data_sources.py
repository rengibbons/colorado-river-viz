"""REST clients for public Colorado River Basin data sources.

- USGS Water Data OGC API (streamflow): https://api.waterdata.usgs.gov/ogcapi/v0/
- Bureau of Reclamation RISE API (reservoir elevations): https://data.usbr.gov/rise-api
- USDA NRCS AWDB REST API (SNOTEL snowpack): https://wcc.sc.egov.usda.gov/awdbRestApi/swagger-ui/index.html
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests

USGS_DAILY_VALUES_URL = (
    "https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items"
)
RISE_RESULT_URL = "https://data.usbr.gov/rise/api/result"
AWDB_DATA_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"

REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class DateRange:
    """An inclusive start/end date range for a data query."""

    start: date
    end: date


def fetch_usgs_daily_values(
    monitoring_location_id: str, parameter_code: str, date_range: DateRange
) -> pd.DataFrame:
    """Fetch a daily-value time series for one USGS monitoring location and parameter.

    Source: https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily
    Example: monitoring_location_id="USGS-09380000" (Lees Ferry, AZ),
    parameter_code="00060" (discharge, cfs)
    """
    params: dict[str, str | int] = {
        "monitoring_location_id": monitoring_location_id,
        "parameter_code": parameter_code,
        "datetime": f"{date_range.start.isoformat()}/{date_range.end.isoformat()}",
        "f": "json",
        "limit": 10000,
    }
    response = requests.get(
        USGS_DAILY_VALUES_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    records = [feature["properties"] for feature in response.json()["features"]]
    frame = pd.DataFrame.from_records(records)
    frame["time"] = pd.to_datetime(frame["time"])
    frame["value"] = pd.to_numeric(frame["value"])
    return frame.sort_values("time").set_index("time")[["value", "unit_of_measure"]]


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
