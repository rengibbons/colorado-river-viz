"""SNOTEL stations in the Upper Colorado (HUC 14), the fixed snow-index station
set (decision 0013), and batched daily SWE fetches from the NRCS AWDB API.

AWDB ignores the ``networkCds`` filter on ``/stations`` and returns manual snow
courses too, so SNOTEL is selected with the ``*:*:SNTL`` triplet pattern
(decision 0021).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import batched
from typing import Any

import pandas as pd

from colorado_river_viz.constants import SNOTEL_INDEX_RECORD_START
from colorado_river_viz.data_sources import AWDB_DATA_URL, DateRange
from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import HttpClient, get_json
from colorado_river_viz.schema import canonical_frame, empty_canonical_frame

AWDB_STATIONS_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/stations"
SNOTEL_BATCH_SIZE = 10
SWE_ELEMENT = "WTEQ"

STATION_COLUMNS = (
    "station_triplet",
    "name",
    "latitude",
    "longitude",
    "elevation_ft",
    "huc",
    "huc4",
    "daily_swe_begin_date",
    "in_index",
)
MEDIAN_COLUMNS = ("station_triplet", "month", "day", "median_swe_in")


@dataclass(frozen=True, slots=True)
class SnotelBatch:
    """Daily SWE for a set of stations, plus each station's 1991-2020 daily median."""

    daily_swe: pd.DataFrame
    medians: pd.DataFrame


def snotel_series_id(station_triplet: str) -> str:
    """Return the cache series id for a station's daily SWE (``335_CO_SNTL__WTEQ``)."""
    return f"{station_triplet.replace(':', '_')}__{SWE_ELEMENT}"


def fetch_huc14_snotel_stations(
    client: HttpClient, cutoff: date = SNOTEL_INDEX_RECORD_START
) -> pd.DataFrame:
    """Fetch every active SNOTEL station in HUC 14 as the station reference table."""
    payload = get_json(
        client,
        AWDB_STATIONS_URL,
        {
            "stationTriplets": "*:*:SNTL",
            "hucs": "14*",
            "elements": SWE_ELEMENT,
            "returnStationElements": "true",
            "activeOnly": "true",
        },
    )
    return parse_stations(payload, cutoff)


def parse_stations(payload: list[dict[str, Any]], cutoff: date) -> pd.DataFrame:
    """Parse an AWDB ``/stations`` response into the station reference table."""
    rows = [
        {
            "station_triplet": station["stationTriplet"],
            "name": station["name"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "elevation_ft": station["elevation"],
            "huc": station["huc"],
            "huc4": station["huc"][:4],
            "daily_swe_begin_date": _daily_swe_begin(station),
        }
        for station in payload
        if station["networkCode"] == "SNTL"
    ]
    stations = pd.DataFrame(rows, columns=list(STATION_COLUMNS[:-1]))
    stations["daily_swe_begin_date"] = pd.to_datetime(stations["daily_swe_begin_date"])
    stations["in_index"] = select_index_stations(stations, cutoff)
    return stations.sort_values("station_triplet", ignore_index=True)


def _daily_swe_begin(station: dict[str, Any]) -> str | None:
    begins = [
        element["beginDate"][:10]
        for element in station.get("stationElements") or []
        if element["elementCode"] == SWE_ELEMENT and element["durationName"] == "DAILY"
    ]
    return min(begins) if begins else None


def select_index_stations(stations: pd.DataFrame, cutoff: date) -> pd.Series[bool]:
    """Flag the stations whose daily SWE record begins on or before ``cutoff`` (0013).

    Stations with no daily SWE record at all are never in the index.
    """
    begins = stations["daily_swe_begin_date"]
    return (begins.notna() & (begins <= pd.Timestamp(cutoff))).astype(bool)


def index_station_triplets(stations: pd.DataFrame) -> list[str]:
    """Return the fixed index station set from a station reference table, sorted."""
    return sorted(stations.loc[stations["in_index"], "station_triplet"])


def fetch_snotel_daily_canonical(
    client: HttpClient,
    station_triplets: Sequence[str],
    date_range: DateRange,
    batch_size: int = SNOTEL_BATCH_SIZE,
) -> SnotelBatch:
    """Fetch daily SWE and daily medians for many stations, ``batch_size`` per request.

    Values are in the canonical schema with one series id per station.
    """
    payloads = [
        station
        for batch in batched(station_triplets, batch_size)
        for station in _fetch_batch(client, batch, date_range)
    ]
    return parse_snotel_data(payloads)


def _fetch_batch(
    client: HttpClient, station_triplets: tuple[str, ...], date_range: DateRange
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = get_json(
        client,
        AWDB_DATA_URL,
        {
            "stationTriplets": ",".join(station_triplets),
            "elements": SWE_ELEMENT,
            "duration": "DAILY",
            "beginDate": date_range.start.isoformat(),
            "endDate": date_range.end.isoformat(),
            "centralTendencyType": "MEDIAN",
        },
    )
    return payload


def parse_snotel_data(payload: list[dict[str, Any]]) -> SnotelBatch:
    """Split an AWDB ``/data`` response into per-station values and medians."""
    value_frames: list[pd.DataFrame] = []
    median_frames: list[pd.DataFrame] = []
    for station in payload:
        triplet: str = station["stationTriplet"]
        for element in station.get("data") or []:
            unit = element["stationElement"]["storedUnitCode"]
            if unit != "in":
                raise UnexpectedSourceFormatError(f"{triplet}: SWE unit {unit!r}")
            rows = pd.DataFrame.from_records(
                element["values"], columns=["date", "value", "median"]
            )
            if rows.empty:
                continue
            dates = pd.to_datetime(rows["date"])
            value_frames.append(
                canonical_frame(
                    series_id=snotel_series_id(triplet),
                    dates=dates,
                    values=pd.to_numeric(rows["value"]),
                    unit="in",
                    approval="unknown",
                )
            )
            median_frames.append(
                pd.DataFrame(
                    {
                        "station_triplet": triplet,
                        "month": dates.dt.month,
                        "day": dates.dt.day,
                        "median_swe_in": pd.to_numeric(rows["median"]),
                    }
                )
            )
    daily_swe = (
        pd.concat(value_frames, ignore_index=True).astype({"series_id": "category"})
        if value_frames
        else empty_canonical_frame()
    )
    return SnotelBatch(daily_swe=daily_swe, medians=daily_median_table(median_frames))


def daily_median_table(median_frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """Collapse per-date medians to one row per station and calendar day.

    A station with no Feb 29 median uses its Feb 28 median (design §6.3).
    """
    if not median_frames:
        return pd.DataFrame(columns=list(MEDIAN_COLUMNS))
    medians = (
        pd.concat(median_frames, ignore_index=True)
        .dropna(subset=["median_swe_in"])
        .drop_duplicates(["station_triplet", "month", "day"], keep="last")
    )
    has_feb29 = set(
        medians.loc[(medians["month"] == 2) & (medians["day"] == 29), "station_triplet"]
    )
    feb28 = medians[(medians["month"] == 2) & (medians["day"] == 28)]
    feb29_fill = feb28[~feb28["station_triplet"].isin(has_feb29)].assign(day=29)
    return (
        pd.concat([medians, feb29_fill], ignore_index=True)
        .sort_values(["station_triplet", "month", "day"], ignore_index=True)
        .astype({"month": "int8", "day": "int8"})
    )
