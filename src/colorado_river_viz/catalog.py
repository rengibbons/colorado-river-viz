"""Every series the story uses, as a sum type of frozen specs (design §2, §3).

Each spec has a stable ``series_id``: its cache file name and manifest key.
SNOTEL series can't be listed up front, because the fixed index station set is
read from the cached station table (decision 0013), so ``story_series`` builds the
full list from that table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

import pandas as pd

from colorado_river_viz.http_session import DataSource
from colorado_river_viz.published import (
    MEKO_RECON_SERIES_ID,
    MEKO_RECON_URL,
    NATURAL_FLOW_SERIES_ID,
    NATURAL_FLOW_URL,
    RIVER_TRACE_SERIES_ID,
)
from colorado_river_viz.reservoirs import LAKE_MEAD, LAKE_POWELL
from colorado_river_viz.schema import Unit
from colorado_river_viz.snotel import index_station_triplets, snotel_series_id

RefreshPolicy = Literal["incremental", "on_full_refresh"]
"""``incremental`` series are topped up on every refresh; the rest are fetched
once and only replaced by an explicit ``full`` refresh (decision 0008)."""

FULL_HISTORY_START = date(1900, 1, 1)
"""Earlier than every series' first record, so a full fetch gets everything."""

SNOTEL_STATIONS_SERIES_ID = "snotel_stations_huc14"
SNOTEL_MEDIANS_SERIES_ID = "snotel_daily_median"


@dataclass(frozen=True, slots=True)
class UsgsDailySeries:
    series_id: str
    monitoring_location_id: str
    parameter_code: str
    unit: Unit
    source: DataSource = DataSource.USGS
    refresh_policy: RefreshPolicy = "incremental"


@dataclass(frozen=True, slots=True)
class RiseDailySeries:
    series_id: str
    item_id: int
    unit: Unit
    source: DataSource = DataSource.RISE
    refresh_policy: RefreshPolicy = "incremental"


@dataclass(frozen=True, slots=True)
class SnotelDailySeries:
    series_id: str
    station_triplet: str
    unit: Unit = "in"
    source: DataSource = DataSource.SNOTEL
    refresh_policy: RefreshPolicy = "incremental"


class PublishedFormat(StrEnum):
    NATURAL_FLOW_XLSX = "natural_flow_xlsx"
    MEKO_RECON_TXT = "meko_recon_txt"


@dataclass(frozen=True, slots=True)
class PublishedFile:
    series_id: str
    url: str
    file_format: PublishedFormat
    source: DataSource = DataSource.PUBLISHED
    refresh_policy: RefreshPolicy = "on_full_refresh"


@dataclass(frozen=True, slots=True)
class BasinOutline:
    series_id: str
    huc2: str
    source: DataSource = DataSource.PUBLISHED
    refresh_policy: RefreshPolicy = "on_full_refresh"


@dataclass(frozen=True, slots=True)
class RiverTrace:
    series_id: str
    source: DataSource = DataSource.PUBLISHED
    refresh_policy: RefreshPolicy = "on_full_refresh"


SeriesSpec = (
    UsgsDailySeries
    | RiseDailySeries
    | SnotelDailySeries
    | PublishedFile
    | BasinOutline
    | RiverTrace
)
DailySeriesSpec = UsgsDailySeries | RiseDailySeries | SnotelDailySeries


def usgs_series_id(monitoring_location_id: str, parameter_code: str) -> str:
    return f"{monitoring_location_id}__{parameter_code}"


def rise_series_id(item_id: int) -> str:
    return f"rise-{item_id:04d}"


def _usgs_discharge(monitoring_location_id: str) -> UsgsDailySeries:
    return UsgsDailySeries(
        series_id=usgs_series_id(monitoring_location_id, "00060"),
        monitoring_location_id=monitoring_location_id,
        parameter_code="00060",
        unit="cfs",
    )


def _rise(item_id: int, unit: Unit) -> RiseDailySeries:
    return RiseDailySeries(
        series_id=rise_series_id(item_id), item_id=item_id, unit=unit
    )


CISCO = _usgs_discharge("USGS-09180500")
LEES_FERRY = _usgs_discharge("USGS-09380000")
POWELL_ELEVATION = _rise(LAKE_POWELL.elevation_catalog_item_id, "ft")
POWELL_STORAGE = _rise(LAKE_POWELL.storage_catalog_item_id, "af")
POWELL_UNREGULATED_INFLOW = _rise(512, "cfs")
MEAD_ELEVATION = _rise(LAKE_MEAD.elevation_catalog_item_id, "ft")
MEAD_STORAGE = _rise(LAKE_MEAD.storage_catalog_item_id, "af")
NATURAL_FLOW = PublishedFile(
    series_id=NATURAL_FLOW_SERIES_ID,
    url=NATURAL_FLOW_URL,
    file_format=PublishedFormat.NATURAL_FLOW_XLSX,
)
MEKO_RECON = PublishedFile(
    series_id=MEKO_RECON_SERIES_ID,
    url=MEKO_RECON_URL,
    file_format=PublishedFormat.MEKO_RECON_TXT,
)
UPPER_BASIN_OUTLINE = BasinOutline(series_id="wbd_huc2_14", huc2="14")
LOWER_BASIN_OUTLINE = BasinOutline(series_id="wbd_huc2_15", huc2="15")
RIVER_TRACE = RiverTrace(series_id=RIVER_TRACE_SERIES_ID)

FIXED_SERIES: tuple[SeriesSpec, ...] = (
    CISCO,
    LEES_FERRY,
    POWELL_ELEVATION,
    POWELL_STORAGE,
    POWELL_UNREGULATED_INFLOW,
    MEAD_ELEVATION,
    MEAD_STORAGE,
    NATURAL_FLOW,
    MEKO_RECON,
    UPPER_BASIN_OUTLINE,
    LOWER_BASIN_OUTLINE,
    RIVER_TRACE,
)
"""Every story series except the SNOTEL index stations."""


def snotel_index_series(stations: pd.DataFrame) -> tuple[SnotelDailySeries, ...]:
    """Return one daily-SWE spec per fixed index station in the station table."""
    return tuple(
        SnotelDailySeries(series_id=snotel_series_id(triplet), station_triplet=triplet)
        for triplet in index_station_triplets(stations)
    )


def story_series(stations: pd.DataFrame) -> tuple[SeriesSpec, ...]:
    """Return every series the story notebook loads (the design's ``STORY_SERIES``)."""
    return FIXED_SERIES + snotel_index_series(stations)
