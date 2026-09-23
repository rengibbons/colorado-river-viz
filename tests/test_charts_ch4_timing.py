from __future__ import annotations

import numpy as np
import pandas as pd

from colorado_river_viz.charts.ch4_timing import build_timing_trends


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
