from __future__ import annotations

import pandas as pd
import pytest

from colorado_river_viz.charts.ch2_snow import build_peak_swe_bar, build_snow_spaghetti
from colorado_river_viz.charts.theme import DRY_YEAR_COLORS

BAND_AND_MEDIAN_TRACES = 3


def _index_daily(peaks: dict[int, float]) -> pd.DataFrame:
    rows = [
        {
            "water_year": wy,
            "day_of_water_year": doy,
            "date": pd.Timestamp(wy - 1, 10, 1) + pd.Timedelta(days=doy - 1),
            "basin_swe_in": peak * doy / 5,
        }
        for wy, peak in peaks.items()
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


_SEVEN_YEARS = {
    1985: 30.0,
    2002: 8.0,
    2011: 25.0,
    2018: 6.0,
    2019: 28.0,
    2023: 22.0,
    2026: 4.0,
}


def test_trace_count_is_six_highlight_years_plus_band_and_median() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    assert len(fig.data) == 6 + BAND_AND_MEDIAN_TRACES


def test_highlighted_years_are_the_three_driest_and_three_wettest_by_peak() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    highlighted = {trace.name for trace in fig.data if trace.name.startswith("WY")}
    assert highlighted == {"WY2026", "WY2018", "WY2002", "WY1985", "WY2019", "WY2011"}


def test_every_highlighted_year_trace_is_in_the_legend() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    year_traces = [trace for trace in fig.data if trace.name.startswith("WY")]
    assert all(trace.showlegend is True for trace in year_traces)


def test_driest_and_wettest_years_get_distinct_colors() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    year_traces = [trace for trace in fig.data if trace.name.startswith("WY")]
    colors = {trace.name: trace.line.color for trace in year_traces}
    assert len(set(colors.values())) == len(colors)


def test_figure_serializes_to_json() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    assert fig.to_json()


def test_title_is_set_and_defaults_to_the_takeaway_sentence() -> None:
    fig = build_snow_spaghetti(_index_daily(_SEVEN_YEARS), _envelope())

    assert fig.layout.title.text

    fig_custom = build_snow_spaghetti(
        _index_daily(_SEVEN_YEARS), _envelope(), title="Custom takeaway"
    )
    assert fig_custom.layout.title.text == "Custom takeaway"


def test_peak_bar_has_one_bar_per_water_year() -> None:
    fig = build_peak_swe_bar(_index_daily(_SEVEN_YEARS))

    assert len(fig.data) == 1
    assert len(fig.data[0].x) == len(_SEVEN_YEARS)


def test_peak_bar_serializes_to_json() -> None:
    fig = build_peak_swe_bar(_index_daily(_SEVEN_YEARS))

    assert fig.to_json()


_PRESENT_YEAR_IS_ACTUALLY_WETTEST = {
    1985: 30.0,
    2002: 8.0,
    2011: 25.0,
    2018: 6.0,
    2019: 28.0,
    2023: 22.0,
    2026: 99.0,  # would rank wettest, not driest, by peak alone
}


def test_present_year_is_forced_into_the_driest_group_regardless_of_rank() -> None:
    fig = build_snow_spaghetti(
        _index_daily(_PRESENT_YEAR_IS_ACTUALLY_WETTEST), _envelope()
    )

    highlighted = {trace.name for trace in fig.data if trace.name.startswith("WY")}
    assert "WY2026" in highlighted
    assert "WY2023" not in highlighted  # the driest group's weakest slot, bumped out
    assert "WY2019" in highlighted  # unaffected wettest years are untouched


def test_present_year_line_is_twice_as_wide_and_the_driest_red() -> None:
    fig = build_snow_spaghetti(
        _index_daily(_PRESENT_YEAR_IS_ACTUALLY_WETTEST), _envelope()
    )

    present = next(trace for trace in fig.data if trace.name == "WY2026")
    other_driest = next(trace for trace in fig.data if trace.name == "WY2018")
    assert present.line.width == pytest.approx(other_driest.line.width * 2)
    assert present.line.color == DRY_YEAR_COLORS["light"][0]
