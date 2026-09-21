from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from colorado_river_viz.constants import AF_PER_MAF
from colorado_river_viz.metrics.flow import water_year_totals
from colorado_river_viz.metrics.natural_flow_bridge import (
    CONFIDENCE_Z,
    apply_bridge,
    fit_bridge,
)
from colorado_river_viz.schema import annual_frame
from colorado_river_viz.water_year import water_year_bounds

TRUE_SLOPE = 1.05
TRUE_INTERCEPT = 0.4


def _constant_flow_daily(cfs_by_wy: dict[int, float]) -> pd.DataFrame:
    frames = []
    for wy, cfs in cfs_by_wy.items():
        bounds = water_year_bounds(wy)
        dates = pd.date_range(bounds.start, bounds.end, freq="D")
        frames.append(pd.DataFrame({"date": dates, "value": cfs}))
    return pd.concat(frames, ignore_index=True)


def _partial_flow_daily(wy: int, cfs: float, through_day: int) -> pd.DataFrame:
    bounds = water_year_bounds(wy)
    dates = pd.date_range(bounds.start, periods=through_day, freq="D")
    return pd.DataFrame({"date": dates, "value": cfs})


def _natural_from_totals(
    totals: pd.DataFrame, years: range, noise: np.ndarray | float = 0.0
) -> pd.DataFrame:
    subset = totals[totals["water_year"].isin(years)]
    values_af = (TRUE_INTERCEPT + TRUE_SLOPE * subset["total_maf"] + noise) * AF_PER_MAF
    return annual_frame(
        series_id="lees_ferry_natural_flow_wy",
        water_years=subset["water_year"].tolist(),
        values_af=values_af.tolist(),
        statuses=["final"] * len(subset),
    )


@pytest.fixture
def unregulated_daily() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    cfs_by_wy = {wy: 4000 + 200 * rng.normal() for wy in range(1960, 2025)}
    return _constant_flow_daily(cfs_by_wy)


def test_fit_recovers_known_coefficients_with_no_noise(
    unregulated_daily: pd.DataFrame,
) -> None:
    totals = water_year_totals(unregulated_daily)
    natural = _natural_from_totals(totals, range(1964, 2021))

    fit = fit_bridge(natural, unregulated_daily)

    assert fit.slope == pytest.approx(TRUE_SLOPE, abs=1e-6)
    assert fit.intercept == pytest.approx(TRUE_INTERCEPT, abs=1e-6)
    assert fit.residual_sd == pytest.approx(0.0, abs=1e-6)
    assert fit.n == 57
    assert (fit.first_year, fit.last_year) == (1964, 2020)


def test_fit_ignores_provisional_and_pre_1964_years(
    unregulated_daily: pd.DataFrame,
) -> None:
    totals = water_year_totals(unregulated_daily)
    final = _natural_from_totals(totals, range(1964, 2021))
    provisional = annual_frame(
        "lees_ferry_natural_flow_wy", [2021], [999_000_000.0], ["provisional"]
    )
    pre_1964 = _natural_from_totals(totals, range(1960, 1964))
    natural = pd.concat([pre_1964, final, provisional], ignore_index=True)

    fit = fit_bridge(natural, unregulated_daily)

    assert fit.n == 57
    assert fit.first_year == 1964


def test_published_years_are_never_touched(unregulated_daily: pd.DataFrame) -> None:
    totals = water_year_totals(unregulated_daily)
    final = _natural_from_totals(totals, range(1964, 2021))
    # A provisional row whose value disagrees with what the bridge would predict.
    provisional = annual_frame(
        "lees_ferry_natural_flow_wy", [2021], [1.0], ["provisional"]
    )
    natural = pd.concat([final, provisional], ignore_index=True)
    fit = fit_bridge(natural, unregulated_daily)

    estimated = apply_bridge(natural, unregulated_daily, fit, today=date(2022, 12, 1))

    assert 2021 not in estimated["water_year"].to_numpy()
    for wy in final["water_year"]:
        assert wy not in estimated["water_year"].to_numpy()


def test_estimate_bounds_are_the_fit_plus_or_minus_z_times_residual_sd(
    unregulated_daily: pd.DataFrame,
) -> None:
    totals = water_year_totals(unregulated_daily)
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 0.3, 57)
    natural = _natural_from_totals(totals, range(1964, 2021), noise=noise)
    fit = fit_bridge(natural, unregulated_daily)
    assert fit.residual_sd > 0

    estimated = apply_bridge(natural, unregulated_daily, fit, today=date(2022, 12, 1))

    spread = estimated["estimate_high_maf"] - estimated["estimate_low_maf"]
    expected_spread = [2 * CONFIDENCE_Z * fit.residual_sd] * len(spread)
    assert spread.tolist() == pytest.approx(expected_spread)
    midpoint = (estimated["estimate_high_maf"] + estimated["estimate_low_maf"]) / 2
    assert midpoint.tolist() == pytest.approx(estimated["natural_flow_maf"].tolist())


def test_the_in_progress_year_is_dropped_before_jul_31() -> None:
    fit_years_daily = _constant_flow_daily({wy: 4000.0 for wy in range(1964, 2021)})
    totals = water_year_totals(fit_years_daily)
    natural = _natural_from_totals(totals, range(1964, 2021))
    fit = fit_bridge(natural, fit_years_daily)
    current_year_partial = _partial_flow_daily(2022, cfs=4000, through_day=200)
    full = pd.concat([fit_years_daily, current_year_partial], ignore_index=True)

    before = apply_bridge(natural, full, fit, today=date(2022, 6, 1))
    after = apply_bridge(natural, full, fit, today=date(2022, 8, 1))

    assert 2022 not in before["water_year"].to_numpy()
    assert 2022 in after["water_year"].to_numpy()
    row = after[after["water_year"] == 2022].iloc[0]
    assert row["through_date"] == current_year_partial["date"].max()
