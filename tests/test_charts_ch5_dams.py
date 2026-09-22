from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.ch5_dams import build_before_after_dam
from colorado_river_viz.story_tables import LeesFerryRegimes


def _regimes() -> LeesFerryRegimes:
    days = list(range(1, 6))
    envelope = pd.DataFrame(
        [
            {
                "regime": regime,
                "day_of_water_year": day,
                "median_cfs": 1000.0 + day,
                "p10_cfs": 800.0 + day,
                "p90_cfs": 1200.0 + day,
            }
            for regime in ("before_dam", "after_dam")
            for day in days
        ]
    )
    annual_peaks = pd.DataFrame(
        [
            {"regime": "before_dam", "water_year": 1940, "peak_cfs": 20_000.0},
            {"regime": "after_dam", "water_year": 1990, "peak_cfs": 15_000.0},
        ]
    )
    return LeesFerryRegimes(envelope=envelope, annual_peaks=annual_peaks)


def test_before_after_dam_draws_one_band_and_median_line_per_regime() -> None:
    fig = build_before_after_dam(_regimes())

    assert len(fig.data) == 6  # 2 regimes x (band upper + band lower + median)


def test_before_after_dam_labels_each_regime_directly() -> None:
    fig = build_before_after_dam(_regimes())

    labels = {a.text for a in fig.layout.annotations}
    assert labels == {"Before dam (WY1922-1962)", "After dam (WY1981-)"}


def test_before_after_dam_smoke_test() -> None:
    fig = build_before_after_dam(_regimes())

    assert fig.layout.title.text
    assert fig.to_json()
