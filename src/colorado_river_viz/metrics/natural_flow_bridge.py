"""Bridge estimate for water years missing from the published natural-flow file.

Fits naturalized Lees Ferry flow (MAF) on Powell unregulated inflow (MAF) over
the published file's final years, then uses that fit to estimate years the
file doesn't yet cover -- currently WY2025-26 (decision 0014).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from colorado_river_viz.constants import AF_PER_MAF
from colorado_river_viz.metrics.flow import water_year_totals
from colorado_river_viz.water_year import water_year

BRIDGE_FIT_START_YEAR = 1964
"""Powell unregulated inflow (RISE 512) begins in WY1964."""

PARTIAL_YEAR_CUTOFF = (7, 31)
"""The current water year is estimated only once its Apr-Jul runoff window
has closed, i.e. after this calendar month/day (design §6.2)."""

CONFIDENCE_Z = 1.96
"""95% interval multiplier on the fit's residual standard deviation."""


@dataclass(frozen=True, slots=True)
class BridgeFit:
    """OLS fit of natural flow (MAF) on Powell unregulated inflow (MAF)."""

    slope: float
    intercept: float
    residual_sd: float
    n: int
    first_year: int
    last_year: int


def fit_bridge(natural: pd.DataFrame, unregulated_daily: pd.DataFrame) -> BridgeFit:
    """Fit natural flow on Powell unregulated inflow over the published file's
    final years, WY1964 onward (decisions 0014, 0022).

    ``natural`` is the cached natural-flow annual frame (``water_year``,
    ``value_af``, ``status``); ``unregulated_daily`` is Powell unregulated
    inflow's cached canonical daily frame (RISE 512).
    """
    final = natural[natural["status"] == "final"]
    totals = water_year_totals(unregulated_daily)
    merged = final.merge(totals[["water_year", "total_maf"]], on="water_year")
    merged = merged[merged["water_year"] >= BRIDGE_FIT_START_YEAR]

    x = merged["total_maf"].to_numpy(dtype=float)
    y = (merged["value_af"].to_numpy(dtype=float)) / AF_PER_MAF
    slope, intercept = np.polyfit(x, y, 1)
    residuals = y - (intercept + slope * x)
    return BridgeFit(
        slope=float(slope),
        intercept=float(intercept),
        residual_sd=float(np.std(residuals, ddof=2)),
        n=len(merged),
        first_year=int(merged["water_year"].min()),
        last_year=int(merged["water_year"].max()),
    )


def apply_bridge(
    natural: pd.DataFrame,
    unregulated_daily: pd.DataFrame,
    fit: BridgeFit,
    today: date,
) -> pd.DataFrame:
    """Estimate the water years present in Powell unregulated inflow but
    missing from the published natural-flow file.

    Published years are never touched. The water year in progress is estimated
    only once its Apr-Jul runoff window has closed (after Jul 31); before that
    it's dropped from the result rather than half-estimated. Every estimated
    row's ``through_date`` is the last date of unregulated inflow used to build
    it, for a "through <date>" label when that's short of Sep 30.

    Columns: ``water_year``, ``natural_flow_maf``, ``estimate_low_maf``,
    ``estimate_high_maf``, ``through_date``.
    """
    totals = water_year_totals(unregulated_daily)
    published_years = set(natural["water_year"])
    missing = totals[~totals["water_year"].isin(published_years)].copy()

    current_wy = water_year(today)
    still_open = (missing["water_year"] == current_wy) & (
        today < date(current_wy, *PARTIAL_YEAR_CUTOFF)
    )
    missing = missing[~still_open]

    estimate = fit.intercept + fit.slope * missing["total_maf"]
    last_date_by_year = (
        unregulated_daily.dropna(subset=["value"])
        .assign(water_year=water_year(unregulated_daily["date"]))
        .groupby("water_year")["date"]
        .max()
    )
    return pd.DataFrame(
        {
            "water_year": missing["water_year"].to_numpy(),
            "natural_flow_maf": estimate.to_numpy(),
            "estimate_low_maf": (estimate - CONFIDENCE_Z * fit.residual_sd).to_numpy(),
            "estimate_high_maf": (estimate + CONFIDENCE_Z * fit.residual_sd).to_numpy(),
            "through_date": missing["water_year"].map(last_date_by_year).to_numpy(),
        }
    )
