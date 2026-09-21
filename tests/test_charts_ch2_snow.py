from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.ch2_snow import build_snow_spaghetti

BAND_AND_MEDIAN_TRACES = 3


def _index_daily(years: list[int]) -> pd.DataFrame:
    rows = [
        {
            "water_year": wy,
            "day_of_water_year": doy,
            "basin_swe_in": float(doy),
        }
        for wy in years
        for doy in range(1, 6)
    ]
    return pd.DataFrame(rows)


def _envelope() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day_of_water_year": range(1, 6),
            "median_swe_in": [1.0, 2.0, 3.0, 4.0, 5.0],
            "p10_swe_in": [0.5, 1.5, 2.5, 3.5, 4.5],
            "p90_swe_in": [1.5, 2.5, 3.5, 4.5, 5.5],
        }
    )


def test_trace_count_is_years_plus_band_and_median() -> None:
    years = [1990, 2018, 2026]
    fig = build_snow_spaghetti(_index_daily(years), _envelope())

    assert len(fig.data) == len(years) + BAND_AND_MEDIAN_TRACES


def test_figure_serializes_to_json() -> None:
    fig = build_snow_spaghetti(_index_daily([1990, 2026]), _envelope())

    assert fig.to_json()


def test_title_is_set_and_defaults_to_the_takeaway_sentence() -> None:
    fig = build_snow_spaghetti(_index_daily([1990]), _envelope())

    assert fig.layout.title.text

    fig_custom = build_snow_spaghetti(
        _index_daily([1990]), _envelope(), title="Custom takeaway"
    )
    assert fig_custom.layout.title.text == "Custom takeaway"


def test_present_year_gets_a_direct_label_not_a_legend_entry() -> None:
    fig = build_snow_spaghetti(_index_daily([2026]), _envelope())

    assert all(trace.showlegend is not True for trace in fig.data)
    assert len(fig.layout.annotations) == 1
    assert fig.layout.annotations[0].text == "WY2026"
