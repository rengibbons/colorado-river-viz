"""Chapter tables for the story notebook, built from the cache (design §6).

Each function loads what it needs from ``cache_dir`` (or takes an
already-loaded table from another function in this module) and returns a
notebook-ready ``DataFrame``. Naming follows design §6.5's rule: there are
three different "medians" in this file, so each is named for what it is a
median *of* -- ``pct_of_median`` (NRCS station medians), the ``median_swe_in``
envelope (our own index's 1991-2020 daily median), and ``peak_pct_of_median``
(the median of 1991-2020 peaks).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from colorado_river_viz.cache import (
    load_annual,
    load_daily,
    load_snotel_daily,
    load_snotel_medians,
)
from colorado_river_viz.catalog import (
    MEKO_RECON,
    NATURAL_FLOW,
    POWELL_UNREGULATED_INFLOW,
    snotel_index_series,
)
from colorado_river_viz.constants import AF_PER_MAF, NORMALS_PERIOD, YearSpan
from colorado_river_viz.metrics.flow import seasonal_volume
from colorado_river_viz.metrics.natural_flow_bridge import apply_bridge, fit_bridge
from colorado_river_viz.metrics.snow import (
    annual_peaks,
    april_first,
    basin_index_daily,
    basin_timing,
    fill_short_gaps,
    station_timing,
    to_wide,
)

PALEO_ROLLING_WINDOW_YEARS = 20


def _index_wide_swe(cache_dir: Path, stations: pd.DataFrame) -> pd.DataFrame:
    specs = snotel_index_series(stations)
    swe = load_snotel_daily(cache_dir, specs)
    return fill_short_gaps(to_wide(swe))


def snow_index_daily(cache_dir: Path, stations: pd.DataFrame) -> pd.DataFrame:
    """Daily basin snow index from the fixed SNOTEL stations (design §6.3)."""
    wide = _index_wide_swe(cache_dir, stations)
    medians = load_snotel_medians(cache_dir)
    return basin_index_daily(wide, medians)


def snow_index_envelope(
    index_daily: pd.DataFrame, normals: YearSpan = NORMALS_PERIOD
) -> pd.DataFrame:
    """Per-day 1991-2020 median and 10th/90th percentiles of ``basin_swe_in``.

    Feeds the median line and band on the chapter 2 spaghetti chart.
    """
    in_normals = index_daily[
        index_daily["water_year"].between(normals.first, normals.last)
    ].dropna(subset=["basin_swe_in"])
    grouped = in_normals.groupby("day_of_water_year")["basin_swe_in"]
    return pd.DataFrame(
        {
            "median_swe_in": grouped.median(),
            "p10_swe_in": grouped.quantile(0.10),
            "p90_swe_in": grouped.quantile(0.90),
        }
    ).reset_index()


def _date_of_day_of_water_year(water_year: int, day: float) -> pd.Timestamp:
    if pd.isna(day):
        return pd.NaT
    return pd.Timestamp(water_year - 1, 10, 1) + pd.Timedelta(days=round(day) - 1)


def snow_annual(
    cache_dir: Path,
    stations: pd.DataFrame,
    index_daily: pd.DataFrame,
    normals: YearSpan = NORMALS_PERIOD,
) -> pd.DataFrame:
    """One row per water year: peak, April 1, and station timing (design §6.4)."""
    wide = _index_wide_swe(cache_dir, stations)
    timings = basin_timing(station_timing(wide), index_size=wide.shape[1])

    peaks = annual_peaks(index_daily)
    normal_peaks = peaks.loc[
        peaks["water_year"].between(normals.first, normals.last), "peak_swe_in"
    ]
    peak_median = normal_peaks.median()

    merged = (
        peaks.merge(april_first(index_daily), on="water_year", how="outer")
        .merge(timings, on="water_year", how="outer")
        .sort_values("water_year", ignore_index=True)
    )
    merged["peak_pct_of_median"] = 100 * merged["peak_swe_in"] / peak_median
    merged["station_peak_date_median"] = merged.apply(
        lambda row: _date_of_day_of_water_year(
            int(row["water_year"]), row["station_peak_doy_median"]
        ),
        axis=1,
    )
    merged["station_meltout_date_median"] = merged.apply(
        lambda row: _date_of_day_of_water_year(
            int(row["water_year"]), row["station_meltout_doy_median"]
        ),
        axis=1,
    )
    return merged[
        [
            "water_year",
            "peak_swe_in",
            "peak_date",
            "apr1_swe_in",
            "apr1_pct_of_median",
            "peak_pct_of_median",
            "station_peak_date_median",
            "station_meltout_date_median",
        ]
    ]


def runoff_vs_snow(
    cache_dir: Path,
    snow_annual_table: pd.DataFrame,
    normals: YearSpan = NORMALS_PERIOD,
) -> pd.DataFrame:
    """Peak SWE vs. spring runoff volume and its trend, per water year (design §6.5)."""
    inflow = load_daily(cache_dir, POWELL_UNREGULATED_INFLOW)
    apr_jul = seasonal_volume(inflow)
    apr_jul = apr_jul.loc[apr_jul["is_complete"], ["water_year", "volume_maf"]]

    merged = apr_jul.merge(
        snow_annual_table[["water_year", "peak_swe_in"]], on="water_year", how="inner"
    ).dropna(subset=["peak_swe_in"])
    merged = merged.rename(columns={"volume_maf": "apr_jul_unreg_maf"})
    merged["runoff_efficiency"] = merged["apr_jul_unreg_maf"] / merged["peak_swe_in"]

    normal_mean = merged.loc[
        merged["water_year"].between(normals.first, normals.last), "runoff_efficiency"
    ].mean()
    merged["runoff_efficiency_index"] = 100 * merged["runoff_efficiency"] / normal_mean
    return merged.reset_index(drop=True)


_STATUS_TO_KIND = {"final": "published_final", "provisional": "published_provisional"}


def annual_supply(cache_dir: Path, today: date | None = None) -> pd.DataFrame:
    """Natural flow by water year: published where available, bridge-estimated
    otherwise (design §6.2, decision 0014).

    Columns: ``water_year``, ``natural_flow_maf``, ``kind`` (``"published_final"``,
    ``"published_provisional"``, or ``"estimated"``), ``estimate_low_maf``,
    ``estimate_high_maf`` (estimated rows only), ``through_date`` (estimated rows
    only, for a "through <date>" label when short of Sep 30).
    """
    natural = load_annual(cache_dir, NATURAL_FLOW)
    unregulated_daily = load_daily(cache_dir, POWELL_UNREGULATED_INFLOW)
    fit = fit_bridge(natural, unregulated_daily)
    estimated = apply_bridge(
        natural, unregulated_daily, fit, today if today is not None else date.today()
    )
    estimated["kind"] = "estimated"

    published = pd.DataFrame(
        {
            "water_year": natural["water_year"],
            "natural_flow_maf": natural["value_af"] / AF_PER_MAF,
            "kind": natural["status"].map(_STATUS_TO_KIND),
            "estimate_low_maf": pd.NA,
            "estimate_high_maf": pd.NA,
            "through_date": pd.NaT,
        }
    )
    columns = [
        "water_year",
        "natural_flow_maf",
        "kind",
        "estimate_low_maf",
        "estimate_high_maf",
        "through_date",
    ]
    return pd.concat([published, estimated[columns]], ignore_index=True).sort_values(
        "water_year", ignore_index=True
    )


def paleo_supply(cache_dir: Path) -> pd.DataFrame:
    """Meko et al. (2007) tree-ring reconstruction and its 20-year rolling mean
    (design §6.2), water year 762-2005."""
    meko = load_annual(cache_dir, MEKO_RECON)
    recon_maf = meko["value_af"] / AF_PER_MAF
    return pd.DataFrame(
        {
            "water_year": meko["water_year"],
            "recon_maf": recon_maf,
            "recon_20yr_mean_maf": recon_maf.rolling(
                PALEO_ROLLING_WINDOW_YEARS, min_periods=PALEO_ROLLING_WINDOW_YEARS
            ).mean(),
        }
    )
