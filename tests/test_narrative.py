from __future__ import annotations

import pandas as pd

from colorado_river_viz.metrics.trend import TrendResult
from colorado_river_viz.narrative import (
    describe_peak_swe,
    describe_runoff_year,
    describe_supply_vs_compact,
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
        "Since WY2000, the river has averaged 12.0 MAF a year -- 27% short of "
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
        "WY2026 peaked at 9.1 in (61% of the 1991-2020 median) on Mar 15."
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
        "WY2026 produced 1.1 MAF of spring runoff from 9.1 in of peak snowpack "
        "-- 35% of the normal efficiency."
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
        "Spring runoff efficiency has fallen about 13% per decade since WY1981 "
        "(Theil-Sen; tau=-0.26, p=0.011)."
    )


def test_describe_trend_says_risen_for_a_positive_slope() -> None:
    sentence = describe_trend(_trend(0.05, 13.2), "Peak SWE")

    assert sentence.startswith("Peak SWE has risen about 13% per decade")
