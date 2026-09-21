from __future__ import annotations

import numpy as np
import pandas as pd

from colorado_river_viz.charts.ch4_timing import (
    build_cisco_spaghetti,
    build_timing_trends,
)


def _timing(years: range) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = len(years)
    return pd.DataFrame(
        {
            "water_year": list(years),
            "snow_peak_doy": 190 - 0.3 * np.arange(n) + rng.normal(0, 1, n),
            "snow_meltout_doy": 240 - 0.4 * np.arange(n) + rng.normal(0, 1, n),
            "cisco_center_of_volume_doy": (
                220 - 0.2 * np.arange(n) + rng.normal(0, 1, n)
            ),
        }
    )


def _hydrograph(years: list[int]) -> pd.DataFrame:
    rows = [
        {
            "water_year": wy,
            "day_of_water_year": doy,
            "cfs": 1000.0 + doy,
            "median_cfs": 1000.0 + doy,
            "p10_cfs": 800.0 + doy,
            "p90_cfs": 1200.0 + doy,
        }
        for wy in years
        for doy in range(1, 6)
    ]
    return pd.DataFrame(rows)


def test_timing_trends_has_three_panels_with_dots_line_and_label() -> None:
    fig = build_timing_trends(_timing(range(1980, 2027)))

    assert len(fig.data) == 6  # 3 panels x (dots + trend line)
    assert len(fig.layout.annotations) == 6  # 3 subplot titles + 3 trend labels
    trend_labels = [a.text for a in fig.layout.annotations if "per decade" in a.text]
    assert len(trend_labels) == 3
    assert all("earlier" in t or "later" in t for t in trend_labels)


def test_timing_trends_y_axes_use_date_ticks_not_day_numbers() -> None:
    fig = build_timing_trends(_timing(range(1980, 2027)))

    assert fig.layout.yaxis.tickmode == "array"
    assert "Mar" in fig.layout.yaxis.ticktext


def test_timing_trends_smoke_test() -> None:
    fig = build_timing_trends(_timing(range(1980, 2027)))

    assert fig.layout.title.text
    assert fig.to_json()


def test_cisco_spaghetti_trace_count_is_years_plus_band_and_median() -> None:
    years = [1990, 2018, 2026]
    fig = build_cisco_spaghetti(_hydrograph(years))

    assert len(fig.data) == len(years) + 3  # band (2) + median (1)


def test_cisco_spaghetti_present_year_gets_a_direct_label() -> None:
    fig = build_cisco_spaghetti(_hydrograph([2026]))

    assert len(fig.layout.annotations) == 1
    assert fig.layout.annotations[0].text == "WY2026"


def test_cisco_spaghetti_smoke_test() -> None:
    fig = build_cisco_spaghetti(_hydrograph([1990, 2026]))

    assert fig.layout.title.text
    assert fig.to_json()
