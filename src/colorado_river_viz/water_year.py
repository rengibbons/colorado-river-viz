"""Water-year arithmetic (decision 0002).

A water year runs October 1 through September 30 and is labeled by the calendar
year it ends in: water year 2026 is Oct 1, 2025 - Sep 30, 2026. Day of water year
counts from Oct 1 = day 1, so Sep 30 is day 365 (366 in a water year containing
Feb 29).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import overload

import numpy as np
import pandas as pd

from colorado_river_viz.constants import COMPLETE_WATER_YEAR_MIN_COVERAGE
from colorado_river_viz.data_sources import DateRange

_DAYS_OCT_THROUGH_DEC = 92
_DAY_OF_YEAR_BEFORE_OCT_1 = 273  # in a non-leap calendar year


@overload
def water_year(when: date) -> int: ...
@overload
def water_year(when: pd.DatetimeIndex) -> pd.Index[int]: ...
@overload
def water_year(when: pd.Series[pd.Timestamp]) -> pd.Series[int]: ...
def water_year(
    when: date | pd.DatetimeIndex | pd.Series[pd.Timestamp],
) -> int | pd.Index[int] | pd.Series[int]:
    """Return the water year containing each date."""
    if isinstance(when, date):
        return when.year + int(when.month >= 10)
    if isinstance(when, pd.Series):
        return pd.Series(water_year(pd.DatetimeIndex(when)), index=when.index)
    return pd.Index(when.year + (when.month >= 10).astype(int), dtype="int64")


@overload
def day_of_water_year(when: date) -> int: ...
@overload
def day_of_water_year(when: pd.DatetimeIndex) -> pd.Index[int]: ...
@overload
def day_of_water_year(when: pd.Series[pd.Timestamp]) -> pd.Series[int]: ...
def day_of_water_year(
    when: date | pd.DatetimeIndex | pd.Series[pd.Timestamp],
) -> int | pd.Index[int] | pd.Series[int]:
    """Return the day of the water year for each date, with Oct 1 = day 1."""
    if isinstance(when, date):
        day = when.date() if isinstance(when, datetime) else when
        if day.month >= 10:
            leap_offset = int(calendar.isleap(day.year))
            return day.timetuple().tm_yday - _DAY_OF_YEAR_BEFORE_OCT_1 - leap_offset
        return day.timetuple().tm_yday + _DAYS_OCT_THROUGH_DEC
    if isinstance(when, pd.Series):
        return pd.Series(day_of_water_year(pd.DatetimeIndex(when)), index=when.index)
    fall_days = (
        when.dayofyear - _DAY_OF_YEAR_BEFORE_OCT_1 - when.is_leap_year.astype(int)
    )
    return pd.Index(
        np.where(when.month >= 10, fall_days, when.dayofyear + _DAYS_OCT_THROUGH_DEC),
        dtype="int64",
    )


def water_year_bounds(wy: int) -> DateRange:
    """Return the first and last day (inclusive) of a water year."""
    return DateRange(start=date(wy - 1, 10, 1), end=date(wy, 9, 30))


def days_in_water_year(wy: int) -> int:
    """Return 366 if the water year contains Feb 29, else 365."""
    return 366 if calendar.isleap(wy) else 365


def water_year_coverage(observed_dates: pd.DatetimeIndex) -> pd.Series[float]:
    """Return the fraction of each water year's days that appear in ``observed_dates``.

    Pass the dates that have a real value (drop NaN rows first). A water year in
    progress is measured against its full length, so it reads as incomplete.
    """
    unique_days = observed_dates.normalize().unique()
    counts = pd.Series(1, index=water_year(unique_days)).groupby(level=0).sum()
    full_lengths = pd.Series(
        [days_in_water_year(wy) for wy in counts.index], index=counts.index
    )
    return (counts / full_lengths).rename_axis("water_year").rename("coverage")


def complete_water_years(
    observed_dates: pd.DatetimeIndex,
    min_coverage: float = COMPLETE_WATER_YEAR_MIN_COVERAGE,
) -> list[int]:
    """Return the water years whose coverage meets ``min_coverage``, ascending."""
    coverage = water_year_coverage(observed_dates)
    return sorted(int(wy) for wy in coverage.index[coverage >= min_coverage])
