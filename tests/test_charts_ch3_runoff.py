from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from colorado_river_viz.charts.ch3_runoff import (
    build_efficiency_trend,
    build_snow_vs_runoff,
    residual_efficiency_trend,
)
from colorado_river_viz.constants import YearSpan


def _runoff(years: range, slope: float = -0.02, noise: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    peak_swe = np.linspace(10.0, 20.0, len(years))
    efficiency = 1.0 + slope * (np.array(list(years)) - years.start)
    apr_jul = peak_swe * efficiency + rng.normal(0, noise, len(years))
    return pd.DataFrame(
        {
            "water_year": list(years),
            "apr_jul_unreg_maf": apr_jul,
            "peak_swe_in": peak_swe,
            "runoff_efficiency": apr_jul / peak_swe,
            "runoff_efficiency_index": 100 * (apr_jul / peak_swe) / np.mean(efficiency),
        }
    )


def test_snow_vs_runoff_smoke_test() -> None:
    fig = build_snow_vs_runoff(_runoff(range(1990, 2010)))

    assert len(fig.data) >= 2  # scatter + at least one half-split fit line
    assert fig.layout.title.text
    assert fig.to_json()


def test_snow_vs_runoff_labels_highlight_years() -> None:
    fig = build_snow_vs_runoff(_runoff(range(1980, 2027)))

    labels = {a.text for a in fig.layout.annotations}
    assert "WY2026" in labels
    assert "WY1985" in labels


def test_efficiency_trend_annotation_reports_the_slope() -> None:
    runoff = _runoff(range(1991, 2021), slope=-0.03)

    fig = build_efficiency_trend(runoff, normals=YearSpan(1991, 2020))

    assert fig.layout.title.text
    assert fig.to_json()
    annotation_text = fig.layout.annotations[0].text
    assert "%" in annotation_text
    assert "per decade" in annotation_text
    assert "less" in annotation_text  # declining efficiency, per the negative slope


def test_residual_trend_matches_sign_of_a_clear_decline() -> None:
    runoff = _runoff(range(1991, 2021), slope=-0.05)

    trend = residual_efficiency_trend(runoff, normals=YearSpan(1991, 2020))

    assert trend.slope_per_decade < 0
    assert trend.n_years == 30


@pytest.mark.parametrize("slope", [-0.03, 0.0, 0.03])
def test_residual_trend_runs_on_flat_and_rising_efficiency(slope: float) -> None:
    runoff = _runoff(range(1991, 2021), slope=slope, noise=0.01)

    trend = residual_efficiency_trend(runoff, normals=YearSpan(1991, 2020))

    assert trend.n_years == 30
