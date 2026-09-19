import numpy as np
import pandas as pd
import pytest

from colorado_river_viz.constants import CFS_DAY_TO_AF, YearSpan
from colorado_river_viz.metrics.flow import (
    center_of_volume,
    cfs_days_to_af,
    seasonal_volume,
    water_year_totals,
)
from colorado_river_viz.metrics.trend import theil_sen_trend


def _daily(start: str, end: str, cfs: float | np.ndarray) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    values = np.broadcast_to(cfs, len(dates)).astype(float)
    return pd.DataFrame({"date": dates, "value": values})


# --- trend -----------------------------------------------------------------------


@pytest.mark.parametrize("slope_per_year", [-0.5, 0.0, 1.25])
def test_theil_sen_recovers_a_known_slope_from_noisy_data(
    slope_per_year: float,
) -> None:
    rng = np.random.default_rng(42)
    years = pd.Series(np.arange(1960, 2026))
    values = pd.Series(100 + slope_per_year * (years - 1960) + rng.normal(0, 2, 66))

    trend = theil_sen_trend(years, values)

    assert trend.slope_per_decade == pytest.approx(slope_per_year * 10, abs=0.6)
    assert trend.n_years == 66
    assert (trend.first_year, trend.last_year) == (1960, 2025)


def test_trend_reports_slope_as_percent_of_the_normals_mean() -> None:
    years = pd.Series(np.arange(1981, 2026))
    values = pd.Series(50.0 - 0.5 * (years - 2005))  # mean over 1991-2020 is 50

    trend = theil_sen_trend(years, values, normals=YearSpan(1991, 2020))

    assert trend.normal_mean == pytest.approx(49.75)
    assert trend.pct_of_normal_per_decade == pytest.approx(-5 / 49.75 * 100)
    assert trend.kendall_tau == pytest.approx(-1.0)
    assert trend.p_value < 1e-6
    assert trend.value_at(2005) == pytest.approx(50.0)


def test_trend_ignores_years_without_a_value() -> None:
    years = pd.Series([2000, 2001, 2002, 2003, 2004])
    values = pd.Series([1.0, np.nan, 3.0, 4.0, 5.0])

    trend = theil_sen_trend(years, values, normals=YearSpan(2000, 2004))

    assert trend.n_years == 4
    assert trend.slope_per_decade == pytest.approx(10.0)


# --- flow ------------------------------------------------------------------------


def test_cfs_days_convert_to_acre_feet() -> None:
    assert cfs_days_to_af(pd.Series([1.0, 1000.0])).tolist() == pytest.approx(
        [CFS_DAY_TO_AF, 1000 * CFS_DAY_TO_AF]
    )


def test_constant_flow_gives_the_exact_april_july_volume() -> None:
    daily = _daily("2024-10-01", "2025-09-30", 1000.0)

    volume = seasonal_volume(daily).set_index("water_year").loc[2025]

    assert volume["volume_af"] == pytest.approx(1000 * CFS_DAY_TO_AF * 122)
    assert volume["volume_maf"] == pytest.approx(1000 * CFS_DAY_TO_AF * 122 / 1e6)
    assert bool(volume["is_complete"])


def test_april_july_volume_is_incomplete_when_the_season_is_cut_short() -> None:
    daily = _daily("2025-04-01", "2025-06-30", 1000.0)

    volume = seasonal_volume(daily).set_index("water_year").loc[2025]

    assert volume["coverage"] == pytest.approx(91 / 122)
    assert not bool(volume["is_complete"])


def test_water_year_totals_flag_incomplete_years() -> None:
    daily = pd.concat(
        [
            _daily("2023-10-01", "2024-09-30", 10.0),  # leap water year, complete
            _daily("2024-10-01", "2025-03-31", 10.0),  # half a year
        ]
    )

    totals = water_year_totals(daily).set_index("water_year")

    assert totals.loc[2024, "total_af"] == pytest.approx(10 * CFS_DAY_TO_AF * 366)
    assert bool(totals.loc[2024, "is_complete"])
    assert not bool(totals.loc[2025, "is_complete"])


def test_symmetric_hydrograph_centers_on_its_midpoint() -> None:
    days = np.arange(1, 366)
    symmetric_pulse = 100 + 5000 * np.exp(-(((days - 183) / 30) ** 2))
    daily = _daily("2024-10-01", "2025-09-30", symmetric_pulse)

    center = center_of_volume(daily).set_index("water_year").loc[2025]

    assert center["center_of_volume_doy"] == 183
    assert bool(center["is_complete"])


def test_earlier_melt_moves_the_center_of_volume_earlier() -> None:
    days = np.arange(1, 366)
    late = 100 + 5000 * np.exp(-(((days - 250) / 20) ** 2))
    early = 100 + 5000 * np.exp(-(((days - 230) / 20) ** 2))
    daily = pd.concat(
        [
            _daily("2023-10-01", "2024-09-29", late),
            _daily("2024-10-01", "2025-09-30", early),
        ]
    )

    centers = center_of_volume(daily).set_index("water_year")["center_of_volume_doy"]

    assert centers[2025] < centers[2024]
