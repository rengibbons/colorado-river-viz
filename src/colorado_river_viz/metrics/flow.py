"""Streamflow volumes and timing from daily mean flow in cfs.

Inputs are canonical daily frames (``date``, ``value`` in cfs). Every per-year
output carries ``coverage`` and ``is_complete`` so callers can drop partial years
(decision 0019) without this module deciding for them.
"""

from __future__ import annotations

import pandas as pd

from colorado_river_viz.constants import (
    AF_PER_MAF,
    CFS_DAY_TO_AF,
    COMPLETE_WATER_YEAR_MIN_COVERAGE,
)
from colorado_river_viz.water_year import (
    day_of_water_year,
    days_in_water_year,
    water_year,
)

APRIL_1 = (4, 1)
JULY_31 = (7, 31)


def cfs_days_to_af(cfs: pd.Series[float]) -> pd.Series[float]:
    """Convert daily mean flows (cfs) to the acre-feet each day delivered."""
    return cfs * CFS_DAY_TO_AF


def _with_water_year(daily: pd.DataFrame) -> pd.DataFrame:
    return daily.assign(water_year=water_year(daily["date"]))


def water_year_totals(daily: pd.DataFrame) -> pd.DataFrame:
    """Total volume per water year.

    Columns: ``water_year``, ``total_af``, ``total_maf``, ``coverage`` (fraction of
    the year's days with data), ``is_complete``.
    """
    grouped = _with_water_year(daily.dropna(subset=["value"])).groupby("water_year")
    totals = pd.DataFrame(
        {
            "total_af": grouped["value"].sum() * CFS_DAY_TO_AF,
            "days": grouped["value"].size(),
        }
    ).reset_index()
    totals["coverage"] = totals["days"] / totals["water_year"].map(days_in_water_year)
    return _finish(totals.assign(total_maf=totals["total_af"] / AF_PER_MAF))


def seasonal_volume(
    daily: pd.DataFrame,
    start_month_day: tuple[int, int] = APRIL_1,
    end_month_day: tuple[int, int] = JULY_31,
) -> pd.DataFrame:
    """Volume between two calendar days (inclusive) within each water year.

    The season must not cross Oct 1. Defaults to April-July, the snowmelt runoff
    window. Columns: ``water_year``, ``volume_af``, ``volume_maf``, ``coverage``,
    ``is_complete``.
    """
    dated = _with_water_year(daily.dropna(subset=["value"]))
    month_day = dated["date"].dt.month * 100 + dated["date"].dt.day
    start_key = start_month_day[0] * 100 + start_month_day[1]
    end_key = end_month_day[0] * 100 + end_month_day[1]
    in_season = dated[(month_day >= start_key) & (month_day <= end_key)]
    grouped = in_season.groupby("water_year")
    volumes = pd.DataFrame(
        {
            "volume_af": grouped["value"].sum() * CFS_DAY_TO_AF,
            "days": grouped["value"].size(),
        }
    ).reset_index()
    season_lengths = volumes["water_year"].map(
        lambda wy: _season_length(int(wy), start_month_day, end_month_day)
    )
    volumes["coverage"] = volumes["days"] / season_lengths
    return _finish(volumes.assign(volume_maf=volumes["volume_af"] / AF_PER_MAF))


def _season_length(
    wy: int, start_month_day: tuple[int, int], end_month_day: tuple[int, int]
) -> int:
    calendar_year = wy if start_month_day[0] < 10 else wy - 1
    start = pd.Timestamp(calendar_year, *start_month_day)
    end = pd.Timestamp(calendar_year, *end_month_day)
    return (end - start).days + 1


def center_of_volume(daily: pd.DataFrame) -> pd.DataFrame:
    """Day of the water year by which half of the year's flow has passed.

    This is the "center of volume" (or half-flow) date: the first day on which
    cumulative flow reaches 50% of the water-year total. Columns:
    ``water_year``, ``center_of_volume_doy``, ``coverage``, ``is_complete``.
    """
    dated = _with_water_year(daily.dropna(subset=["value"])).sort_values("date")
    dated = dated.assign(doy=day_of_water_year(dated["date"]))
    cumulative_share = dated.groupby("water_year")["value"].transform(
        lambda flow: flow.cumsum() / flow.sum()
    )
    reached_half = dated[cumulative_share >= 0.5]
    centers = (
        reached_half.groupby("water_year")["doy"].first().rename("center_of_volume_doy")
    )
    days = dated.groupby("water_year").size().rename("days")
    result = pd.concat([centers, days], axis=1).reset_index()
    result["coverage"] = result["days"] / result["water_year"].map(days_in_water_year)
    return _finish(result)


def _finish(per_year: pd.DataFrame) -> pd.DataFrame:
    return per_year.drop(columns="days").assign(
        water_year=per_year["water_year"].astype("int64"),
        is_complete=per_year["coverage"] >= COMPLETE_WATER_YEAR_MIN_COVERAGE,
    )
