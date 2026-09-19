"""Robust linear trends: Theil-Sen slope with a Mann-Kendall test (decision 0017)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from colorado_river_viz.constants import NORMALS_PERIOD, YearSpan

YEARS_PER_DECADE = 10


@dataclass(frozen=True, slots=True)
class TrendResult:
    """A Theil-Sen trend of a yearly metric.

    ``slope_per_decade`` is in the metric's own units. ``pct_of_normal_per_decade``
    expresses it relative to the metric's mean over the normals period, the form
    used in plain-language text ("about 6% less per decade").
    """

    slope_per_decade: float
    intercept: float
    pct_of_normal_per_decade: float
    normal_mean: float
    kendall_tau: float
    p_value: float
    n_years: int
    first_year: int
    last_year: int

    def value_at(self, water_year: float) -> float:
        """The fitted trend line's value in a given year."""
        return self.intercept + self.slope_per_decade / YEARS_PER_DECADE * water_year


def theil_sen_trend(
    water_years: pd.Series[int],
    values: pd.Series[float],
    normals: YearSpan = NORMALS_PERIOD,
) -> TrendResult:
    """Fit a Theil-Sen line to ``values`` by water year and test it with Kendall's tau.

    Years with a NaN value are dropped. The Mann-Kendall trend test is Kendall's
    tau between year and value.
    """
    frame = pd.DataFrame(
        {"year": water_years.to_numpy(), "value": values.to_numpy()}
    ).dropna()
    years = frame["year"].to_numpy(dtype=float)
    observed = frame["value"].to_numpy(dtype=float)
    slope, intercept, _, _ = stats.theilslopes(observed, years)
    tau, p_value = stats.kendalltau(years, observed)
    in_normals = (years >= normals.first) & (years <= normals.last)
    normal_mean = float(np.mean(observed[in_normals]))
    slope_per_decade = float(slope) * YEARS_PER_DECADE
    return TrendResult(
        slope_per_decade=slope_per_decade,
        intercept=float(intercept),
        pct_of_normal_per_decade=100 * slope_per_decade / normal_mean,
        normal_mean=normal_mean,
        kendall_tau=float(tau),
        p_value=float(p_value),
        n_years=len(frame),
        first_year=int(years.min()),
        last_year=int(years.max()),
    )
