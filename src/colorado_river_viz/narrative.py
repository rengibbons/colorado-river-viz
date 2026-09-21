"""Takeaway sentences for the story notebook, built from table rows (design §8).

Every number in the notebook's narrative comes from one of these functions, so
no number is ever typed by hand.
"""

from __future__ import annotations

import pandas as pd

from colorado_river_viz.metrics.trend import TrendResult


def describe_peak_swe(row: pd.Series[float]) -> str:
    """A water year's peak-SWE headline, e.g. "WY2026 peaked at 9.1 in (61% of
    median) on Mar 15."."""
    peak_date = pd.Timestamp(row["peak_date"])
    return (
        f"WY{int(row['water_year'])} peaked at {row['peak_swe_in']:.1f} in "
        f"({row['peak_pct_of_median']:.0f}% of the 1991-2020 median) "
        f"on {peak_date.strftime('%b %-d')}."
    )


def describe_runoff_year(row: pd.Series[float]) -> str:
    """A water year's runoff-efficiency headline, e.g. "WY2026 produced 1.1 MAF
    of spring runoff from 9.1 in of peak snowpack -- 35% of the normal
    efficiency."."""
    return (
        f"WY{int(row['water_year'])} produced {row['apr_jul_unreg_maf']:.1f} MAF "
        f"of spring runoff from {row['peak_swe_in']:.1f} in of peak snowpack "
        f"-- {row['runoff_efficiency_index']:.0f}% of the normal efficiency."
    )


def describe_trend(trend: TrendResult, subject: str) -> str:
    """A Theil-Sen trend as a sentence, e.g. "Spring runoff efficiency has
    fallen about 13% per decade since WY1980 (Theil-Sen; tau=-0.26,
    p=0.011)."."""
    verb = "fallen" if trend.pct_of_normal_per_decade < 0 else "risen"
    return (
        f"{subject} has {verb} about {abs(trend.pct_of_normal_per_decade):.0f}% "
        f"per decade since WY{trend.first_year} "
        f"(Theil-Sen; tau={trend.kendall_tau:.2f}, p={trend.p_value:.3f})."
    )
