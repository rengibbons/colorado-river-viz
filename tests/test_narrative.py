from __future__ import annotations

import pandas as pd

from colorado_river_viz.metrics.natural_flow_bridge import BridgeFit
from colorado_river_viz.metrics.trend import TrendResult
from colorado_river_viz.narrative import (
    describe_bridge_fit,
    describe_dam_effect,
    describe_peak_swe,
    describe_reservoir_drawdown,
    describe_runoff_year,
    describe_supply_vs_compact,
    describe_timing_trend,
    describe_trend,
)


def test_describe_supply_vs_compact_reports_the_post_year_mean_and_shortfall() -> None:
    supply = pd.DataFrame(
        {
            "water_year": [1999, 2000, 2001, 2002],
            "natural_flow_maf": [20.0, 12.0, 12.0, 12.0],
        }
    )

    sentence = describe_supply_vs_compact(supply, since_year=2000)

    assert sentence == (
        "Since 2000, the river has averaged 12.0 MAF a year, 27% short of "
        "the 16.5 MAF the 1922 Compact promised."
    )


def test_describe_peak_swe_reports_the_value_pct_and_date() -> None:
    row = pd.Series(
        {
            "water_year": 2026,
            "peak_swe_in": 9.14,
            "peak_pct_of_median": 61.2,
            "peak_date": pd.Timestamp("2026-03-15"),
        }
    )

    sentence = describe_peak_swe(row)

    assert sentence == (
        "In 2026, snowpack peaked at 9.1 in (61% of the 1991-2020 median) on Mar 15."
    )


def test_describe_runoff_year_reports_volume_swe_and_efficiency_index() -> None:
    row = pd.Series(
        {
            "water_year": 2026,
            "apr_jul_unreg_maf": 1.14,
            "peak_swe_in": 9.14,
            "runoff_efficiency_index": 34.8,
        }
    )

    sentence = describe_runoff_year(row)

    assert sentence == (
        "2026 produced 1.1 MAF of spring runoff from 9.1 in of peak snowpack, "
        "only 35% of the normal efficiency."
    )


def _trend(slope_per_decade: float, pct: float) -> TrendResult:
    return TrendResult(
        slope_per_decade=slope_per_decade,
        intercept=0.0,
        pct_of_normal_per_decade=pct,
        normal_mean=1.0,
        kendall_tau=-0.26,
        p_value=0.011,
        n_years=45,
        first_year=1981,
        last_year=2026,
    )


def test_describe_trend_says_fallen_for_a_negative_slope() -> None:
    sentence = describe_trend(_trend(-0.05, -13.2), "Spring runoff efficiency")

    assert sentence == (
        "Spring runoff efficiency has fallen about 13% per decade since 1981 "
        "(Theil-Sen; tau=-0.26, p=0.011)."
    )


def test_describe_trend_says_risen_for_a_positive_slope() -> None:
    sentence = describe_trend(_trend(0.05, 13.2), "Peak SWE")

    assert sentence.startswith("Peak SWE has risen about 13% per decade")


def test_describe_timing_trend_says_earlier_for_a_negative_slope() -> None:
    trend = _trend(-5.2, -13.2)

    sentence = describe_timing_trend(trend, "Peak snowpack")

    assert sentence == (
        "Peak snowpack has shifted 5.2 days earlier per decade since 1981 "
        "(Theil-Sen; tau=-0.26, p=0.011)."
    )


def test_describe_timing_trend_says_later_for_a_positive_slope() -> None:
    sentence = describe_timing_trend(_trend(3.0, 13.2), "Snow melt-out")

    assert sentence.startswith("Snow melt-out has shifted 3.0 days later per decade")


def test_describe_dam_effect_reports_before_after_means_and_pct_lower() -> None:
    annual_peaks = pd.DataFrame(
        {
            "regime": ["before_dam", "before_dam", "after_dam", "after_dam"],
            "peak_cfs": [50_000.0, 54_000.0, 22_000.0, 26_000.0],
        }
    )

    sentence = describe_dam_effect(annual_peaks)

    assert sentence == (
        "Before Glen Canyon Dam, Lees Ferry's annual peak flow averaged "
        "52,000 cfs. Since 1981, it has averaged 24,000 cfs, a 54% decrease."
    )


def test_describe_reservoir_drawdown_reports_fallen_for_a_decline() -> None:
    storage = pd.DataFrame(
        {
            "date": pd.to_datetime(["1999-06-01", "2000-06-01", "2026-06-01"]),
            "reservoir": ["Combined", "Combined", "Combined"],
            "pct_full": [96.0, 95.0, 33.0],
        }
    )

    sentence = describe_reservoir_drawdown(storage, since_year=2000)

    assert sentence == (
        "Combined Powell and Mead storage has fallen from 95% full in 2000 "
        "to 33% full today."
    )


def test_describe_bridge_fit_reports_the_fit_statistics() -> None:
    fit = BridgeFit(
        slope=1.02,
        intercept=0.62,
        residual_sd=0.85,
        n=57,
        first_year=1964,
        last_year=2020,
    )

    sentence = describe_bridge_fit(fit)

    assert sentence == (
        "Fit on 1964-2020 (n=57): natural = 0.62 + 1.02 x Powell unregulated "
        "inflow (MAF); residual SD 0.85 MAF."
    )
