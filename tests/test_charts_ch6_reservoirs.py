from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.ch6_reservoirs import build_reservoir_storage


def _storage() -> pd.DataFrame:
    dates = pd.date_range("1964-01-01", periods=5, freq="YS")
    rows = []
    for reservoir, base in (
        ("Lake Powell", 80.0),
        ("Lake Mead", 70.0),
        ("Combined", 75.0),
    ):
        for i, d in enumerate(dates):
            rows.append(
                {
                    "date": d,
                    "reservoir": reservoir,
                    "storage_af": 1.0,
                    "pct_full": base - i,
                    "elevation_ft": 3500.0,
                    "ft_above_min_power_pool": 10.0 + i,
                }
            )
    return pd.DataFrame(rows)


def test_build_reservoir_storage_has_one_trace_per_reservoir() -> None:
    fig = build_reservoir_storage(_storage())

    assert len(fig.data) == 3
    names = {trace.name for trace in fig.data}
    assert names == {"Combined", "Lake Powell", "Lake Mead"}


def test_build_reservoir_storage_shades_the_post_2000_period() -> None:
    fig = build_reservoir_storage(_storage())

    vrects = [shape for shape in fig.layout.shapes if shape.type == "rect"]
    assert len(vrects) == 1


def test_build_reservoir_storage_draws_a_min_power_pool_line_per_reservoir() -> None:
    fig = build_reservoir_storage(_storage())

    hlines = [shape for shape in fig.layout.shapes if shape.type == "line"]
    assert len(hlines) == 2


def test_build_reservoir_storage_smoke_test() -> None:
    fig = build_reservoir_storage(_storage())

    assert fig.layout.title.text
    assert fig.to_json()
