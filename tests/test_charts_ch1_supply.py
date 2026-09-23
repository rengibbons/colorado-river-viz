from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.ch1_supply import (
    build_paleo_context,
    build_supply_vs_compact,
)


def _supply() -> pd.DataFrame:
    published_years = list(range(1906, 2025))
    published = pd.DataFrame(
        {
            "water_year": published_years,
            "natural_flow_maf": [14.0] * len(published_years),
            "kind": "published_final",
            "estimate_low_maf": pd.NA,
            "estimate_high_maf": pd.NA,
            "through_date": pd.NaT,
        }
    )
    estimated = pd.DataFrame(
        {
            "water_year": [2025, 2026],
            "natural_flow_maf": [9.0, 8.0],
            "kind": "estimated",
            "estimate_low_maf": [7.5, 6.5],
            "estimate_high_maf": [10.5, 9.5],
            "through_date": [pd.Timestamp("2025-09-30"), pd.Timestamp("2026-09-17")],
        }
    )
    return pd.concat([published, estimated], ignore_index=True)


def _paleo() -> pd.DataFrame:
    years = list(range(762, 2006))
    return pd.DataFrame(
        {
            "water_year": years,
            "recon_maf": [14.0] * len(years),
            "recon_20yr_mean_maf": [14.0] * len(years),
        }
    )


def test_supply_bars_mark_estimated_years_distinctly() -> None:
    fig = build_supply_vs_compact(_supply())

    bar = fig.data[0]
    assert list(bar.marker.pattern.shape) == [""] * 119 + ["/", "/"]
    assert list(bar.marker.line.width) == [0] * 119 + [1.5, 1.5]
    assert bar.error_y.array[-1] > 0
    assert bar.error_y.array[0] == 0


def test_supply_chart_smoke_test() -> None:
    fig = build_supply_vs_compact(_supply())

    assert fig.layout.title.text
    assert fig.to_json()
    assert len(fig.layout.shapes) >= 1  # the Compact-era shaded region


def test_paleo_context_splices_the_gauge_tail_onto_the_reconstruction() -> None:
    fig = build_paleo_context(_paleo(), _supply())

    line = fig.data[0]
    assert line.x[0] == 762
    assert line.x[-1] == 2026
    assert fig.layout.title.text
    assert fig.to_json()
