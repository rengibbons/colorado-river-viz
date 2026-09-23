from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.kpi_panel import build_kpi_panel


def _kpi_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "kpi_id": "peak_swe_pct_median",
                "label": "Peak snowpack",
                "value": 57.0,
                "unit": "%",
                "display": "57% of median",
                "rank": 3,
                "n_years": 46,
                "rank_phrase": "3rd lowest of 46",
                "as_of": pd.Timestamp("2026-06-01"),
                "is_partial": True,
            },
            {
                "kpi_id": "combined_storage_pct_full",
                "label": "Combined storage",
                "value": 24.0,
                "unit": "%",
                "display": "24% full",
                "rank": 2,
                "n_years": 62,
                "rank_phrase": "2nd lowest of 62",
                "as_of": pd.Timestamp("2026-06-01"),
                "is_partial": False,
            },
        ]
    )


def test_build_kpi_panel_has_one_tile_per_row() -> None:
    fig = build_kpi_panel(_kpi_table())

    assert len(fig.data) == 2


def test_build_kpi_panel_includes_an_as_of_footnote() -> None:
    fig = build_kpi_panel(_kpi_table())

    assert any("As of" in a.text for a in fig.layout.annotations)


def test_build_kpi_panel_omits_partial_flag_and_joins_rank_with_a_colon() -> None:
    fig = build_kpi_panel(_kpi_table())

    assert all("(partial)" not in trace.title.text for trace in fig.data)
    assert ": 3rd lowest of 46" in fig.data[0].title.text


def test_build_kpi_panel_smoke_test() -> None:
    fig = build_kpi_panel(_kpi_table())

    assert fig.layout.title.text
    assert fig.to_json()
