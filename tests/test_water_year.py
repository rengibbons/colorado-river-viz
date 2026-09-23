from datetime import date, datetime

import pandas as pd
import pytest

from colorado_river_viz.data_sources import DateRange
from colorado_river_viz.water_year import (
    complete_water_years,
    day_of_water_year,
    days_in_water_year,
    water_year,
    water_year_bounds,
    water_year_coverage,
)


@pytest.mark.parametrize(
    ("day", "expected_water_year"),
    [
        (date(2025, 9, 30), 2025),
        (date(2025, 10, 1), 2026),
        (date(2025, 12, 31), 2026),
        (date(2026, 1, 1), 2026),
        (date(2026, 9, 30), 2026),
    ],
)
def test_water_year_changes_on_october_first(
    day: date, expected_water_year: int
) -> None:
    assert water_year(day) == expected_water_year


@pytest.mark.parametrize(
    ("day", "expected_day"),
    [
        (date(2025, 10, 1), 1),
        (date(2025, 12, 31), 92),
        (date(2026, 1, 1), 93),
        (date(2026, 3, 1), 152),
        (date(2026, 9, 30), 365),
        (date(2023, 10, 1), 1),  # fall of a leap calendar year
        (date(2024, 2, 29), 152),
        (date(2024, 3, 1), 153),
        (date(2024, 9, 30), 366),
    ],
)
def test_day_of_water_year_counts_from_october_first(
    day: date, expected_day: int
) -> None:
    assert day_of_water_year(day) == expected_day


def test_day_of_water_year_accepts_timestamps() -> None:
    assert day_of_water_year(pd.Timestamp("2024-02-29 07:00")) == 152
    assert day_of_water_year(datetime(2025, 10, 1, 23, 59)) == 1


def test_vectorized_forms_match_scalar_results() -> None:
    days = pd.date_range("2023-09-25", "2024-10-05", freq="D")
    expected_years = [water_year(d.date()) for d in days]
    expected_days = [day_of_water_year(d.date()) for d in days]

    assert list(water_year(days)) == expected_years
    assert list(day_of_water_year(days)) == expected_days

    series = pd.Series(days, index=range(100, 100 + len(days)))
    assert list(water_year(series)) == expected_years
    assert list(day_of_water_year(series)) == expected_days
    assert water_year(series).index.equals(series.index)


def test_water_year_bounds_are_october_first_through_september_thirtieth() -> None:
    assert water_year_bounds(2026) == DateRange(date(2025, 10, 1), date(2026, 9, 30))


@pytest.mark.parametrize(("wy", "expected"), [(2024, 366), (2025, 365), (2000, 366)])
def test_days_in_water_year_includes_leap_day(wy: int, expected: int) -> None:
    assert days_in_water_year(wy) == expected


def test_coverage_is_fraction_of_full_water_year() -> None:
    wy2025 = pd.date_range("2024-10-01", "2025-09-30", freq="D")
    half_of_wy2026 = pd.date_range("2025-10-01", periods=182, freq="D")
    coverage = water_year_coverage(pd.DatetimeIndex(wy2025.append(half_of_wy2026)))
    assert coverage[2025] == 1.0
    assert coverage[2026] == pytest.approx(182 / 365)


def test_coverage_ignores_duplicate_and_intraday_timestamps() -> None:
    days = pd.date_range("2024-10-01", "2025-09-30", freq="D")
    repeated = pd.DatetimeIndex(days.append(days + pd.Timedelta(hours=7)))
    assert water_year_coverage(repeated)[2025] == 1.0


@pytest.mark.parametrize(
    ("missing_days", "is_complete"),
    [(0, True), (7, True), (8, False), (100, False)],
)
def test_complete_water_years_applies_98_percent_threshold(
    missing_days: int, is_complete: bool
) -> None:
    days = pd.date_range("2024-10-01", "2025-09-30", freq="D")
    observed = days[missing_days:]
    assert (2025 in complete_water_years(observed)) is is_complete
