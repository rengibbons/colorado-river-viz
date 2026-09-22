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

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from colorado_river_viz.cache import (
    load_annual,
    load_daily,
    load_outline,
    load_snotel_daily,
    load_snotel_medians,
)
from colorado_river_viz.catalog import (
    CISCO,
    LEES_FERRY,
    LOWER_BASIN_OUTLINE,
    MEAD_ELEVATION,
    MEAD_STORAGE,
    MEKO_RECON,
    NATURAL_FLOW,
    POWELL_ELEVATION,
    POWELL_STORAGE,
    POWELL_UNREGULATED_INFLOW,
    UPPER_BASIN_OUTLINE,
    snotel_index_series,
)
from colorado_river_viz.constants import AF_PER_MAF, NORMALS_PERIOD, YearSpan
from colorado_river_viz.metrics.flow import center_of_volume, seasonal_volume
from colorado_river_viz.metrics.natural_flow_bridge import apply_bridge, fit_bridge
from colorado_river_viz.metrics.reservoir import (
    combined_storage,
    single_reservoir_storage,
)
from colorado_river_viz.metrics.snow import (
    annual_peaks,
    april_first,
    basin_index_daily,
    basin_timing,
    fill_short_gaps,
    station_timing,
    to_wide,
)
from colorado_river_viz.reservoirs import LAKE_MEAD, LAKE_POWELL
from colorado_river_viz.water_year import (
    day_of_water_year,
    water_year,
    water_year_bounds,
)

PALEO_ROLLING_WINDOW_YEARS = 20
CISCO_ENVELOPE_YEARS = YearSpan(1914, 1962)
"""Before most upstream storage (design §6.6)."""

BEFORE_DAM_YEARS = YearSpan(1922, 1962)
AFTER_DAM_START_YEAR = 1981
"""Glen Canyon Dam closed in 1963; Lake Powell first filled in 1980, so the
1963-1980 filling years are excluded from both regimes (design §6.7)."""


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


def _day_of_water_year_of_date(value: pd.Timestamp) -> float:
    if pd.isna(value):
        return np.nan
    return float(day_of_water_year(value.date()))


def timing_annual(cache_dir: Path, snow_annual_table: pd.DataFrame) -> pd.DataFrame:
    """One row per water year: snow peak/melt-out day and Cisco's
    center-of-volume day, all as day of water year (design §6.6).

    ``snow_annual_table`` is ``snow_annual()``'s output. Cisco's
    center-of-volume day only counts complete water years.
    """
    cisco_daily = load_daily(cache_dir, CISCO)
    cisco_cov = center_of_volume(cisco_daily)
    cisco_cov = cisco_cov.loc[
        cisco_cov["is_complete"], ["water_year", "center_of_volume_doy"]
    ].rename(columns={"center_of_volume_doy": "cisco_center_of_volume_doy"})

    snow_timing = pd.DataFrame(
        {
            "water_year": snow_annual_table["water_year"],
            "snow_peak_doy": snow_annual_table["station_peak_date_median"].map(
                _day_of_water_year_of_date
            ),
            "snow_meltout_doy": snow_annual_table["station_meltout_date_median"].map(
                _day_of_water_year_of_date
            ),
        }
    )
    return snow_timing.merge(cisco_cov, on="water_year", how="outer").sort_values(
        "water_year", ignore_index=True
    )


def cisco_hydrograph(
    cache_dir: Path, envelope_years: YearSpan = CISCO_ENVELOPE_YEARS
) -> pd.DataFrame:
    """Cisco daily cfs in the same water_year/day_of_water_year layout as
    ``snow_index_daily()``, plus the ``envelope_years`` per-day median and
    10th/90th percentile envelope (design §6.6).
    """
    daily = load_daily(cache_dir, CISCO)
    dates = pd.DatetimeIndex(daily["date"])
    daily = daily.assign(
        water_year=water_year(dates),
        day_of_water_year=day_of_water_year(dates),
    )

    in_envelope = daily["water_year"].between(envelope_years.first, envelope_years.last)
    baseline = daily[in_envelope]
    grouped = baseline.groupby("day_of_water_year")["value"]
    envelope = pd.DataFrame(
        {
            "median_cfs": grouped.median(),
            "p10_cfs": grouped.quantile(0.10),
            "p90_cfs": grouped.quantile(0.90),
        }
    ).reset_index()

    return daily.merge(envelope, on="day_of_water_year", how="left").rename(
        columns={"value": "cfs"}
    )[
        [
            "date",
            "water_year",
            "day_of_water_year",
            "cfs",
            "median_cfs",
            "p10_cfs",
            "p90_cfs",
        ]
    ]


def _regime_label(
    wy: int, before_dam_years: YearSpan, after_dam_start_year: int
) -> str | None:
    if before_dam_years.contains(wy):
        return "before_dam"
    if wy >= after_dam_start_year:
        return "after_dam"
    return None


@dataclass(frozen=True, slots=True)
class LeesFerryRegimes:
    """Lees Ferry flow before and after Glen Canyon Dam (design §6.7)."""

    envelope: pd.DataFrame
    """One row per ``regime``/``day_of_water_year``: median and 10th/90th
    percentile ``cfs``."""

    annual_peaks: pd.DataFrame
    """One row per ``regime``/``water_year``: that year's ``peak_cfs``."""


def lees_ferry_regimes(
    cache_dir: Path,
    before_dam_years: YearSpan = BEFORE_DAM_YEARS,
    after_dam_start_year: int = AFTER_DAM_START_YEAR,
) -> LeesFerryRegimes:
    """Lees Ferry daily flow before and after Glen Canyon Dam (design §6.7).

    ``before_dam`` is water years 1922-1962; ``after_dam`` is 1981 onward, once
    Lake Powell first filled, so the 1963-1980 filling years don't blur the
    comparison. Years in neither span (and thus with no ``regime``) are
    dropped.
    """
    daily = load_daily(cache_dir, LEES_FERRY)
    dates = pd.DatetimeIndex(daily["date"])
    wy = water_year(dates)
    daily = daily.assign(
        water_year=wy,
        day_of_water_year=day_of_water_year(dates),
        regime=pd.array(
            [_regime_label(y, before_dam_years, after_dam_start_year) for y in wy],
            dtype="string",
        ),
    )
    in_regime = daily.dropna(subset=["regime"])

    grouped = in_regime.groupby(["regime", "day_of_water_year"], observed=True)["value"]
    envelope = pd.DataFrame(
        {
            "median_cfs": grouped.median(),
            "p10_cfs": grouped.quantile(0.10),
            "p90_cfs": grouped.quantile(0.90),
        }
    ).reset_index()

    annual_peaks = (
        in_regime.groupby(["regime", "water_year"], observed=True)["value"]
        .max()
        .rename("peak_cfs")
        .reset_index()
        .sort_values(["regime", "water_year"], ignore_index=True)
    )

    return LeesFerryRegimes(envelope=envelope, annual_peaks=annual_peaks)


def reservoir_storage(cache_dir: Path) -> pd.DataFrame:
    """Daily storage and elevation for Lake Powell, Lake Mead, and their
    combined total (design §6.8).

    Combined storage only covers days both reservoirs report, starting in
    1964 when Powell storage begins. ``ft_above_min_power_pool`` is NaN for
    the ``"Combined"`` rows, since it isn't meaningful summed across dams.
    """
    powell = single_reservoir_storage(
        load_daily(cache_dir, POWELL_ELEVATION),
        load_daily(cache_dir, POWELL_STORAGE),
        LAKE_POWELL,
    )
    mead = single_reservoir_storage(
        load_daily(cache_dir, MEAD_ELEVATION),
        load_daily(cache_dir, MEAD_STORAGE),
        LAKE_MEAD,
    )
    combined = combined_storage(powell, mead, LAKE_POWELL, LAKE_MEAD)
    return pd.concat([powell, mead, combined], ignore_index=True).sort_values(
        ["reservoir", "date"], ignore_index=True
    )


SiteKind = Literal["gauge", "reservoir"]


@dataclass(frozen=True, slots=True)
class MapSite:
    """One labeled point on the basin map (decision 0026)."""

    name: str
    kind: SiteKind
    latitude: float
    longitude: float
    description: str


MAP_SITES: tuple[MapSite, ...] = (
    MapSite(
        name="Cisco",
        kind="gauge",
        latitude=38.8117,
        longitude=-109.5346,
        description="USGS 09180500, Colorado River near Cisco, UT",
    ),
    MapSite(
        name="Lees Ferry",
        kind="gauge",
        latitude=36.8636,
        longitude=-111.5878,
        description="USGS 09380000, Colorado River at Lees Ferry, AZ",
    ),
    MapSite(
        name="Lake Powell",
        kind="reservoir",
        latitude=36.9366,
        longitude=-111.4830,
        description="Glen Canyon Dam",
    ),
    MapSite(
        name="Lake Mead",
        kind="reservoir",
        latitude=36.0161,
        longitude=-114.7377,
        description="Hoover Dam",
    ),
)


@dataclass(frozen=True, slots=True)
class BasinMapLayers:
    """Everything the "meet the river" map draws (design §6.1)."""

    stations: pd.DataFrame
    """The cached ``snotel_stations_huc14`` reference table."""

    sites: pd.DataFrame
    """One row per ``MAP_SITES`` entry: ``name``, ``kind``, ``latitude``,
    ``longitude``, ``description``."""

    basins: dict[str, dict[str, Any]]
    """Upper (``"14"``) and Lower (``"15"``) basin outlines, as GeoJSON dicts."""


def basin_map_layers(cache_dir: Path, stations: pd.DataFrame) -> BasinMapLayers:
    """Load the map's stations, labeled sites, and basin outlines (design §6.1)."""
    sites = pd.DataFrame(
        [
            {
                "name": site.name,
                "kind": site.kind,
                "latitude": site.latitude,
                "longitude": site.longitude,
                "description": site.description,
            }
            for site in MAP_SITES
        ]
    )
    basins = {
        "14": load_outline(cache_dir, UPPER_BASIN_OUTLINE),
        "15": load_outline(cache_dir, LOWER_BASIN_OUTLINE),
    }
    return BasinMapLayers(stations=stations, sites=sites, basins=basins)


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _rank_lowest(values: pd.Series[float], key: int) -> tuple[int, int]:
    """Rank ``key``'s value among ``values`` ascending (1 = lowest; decision 0027)."""
    valid = values.dropna()
    ranks = valid.rank(method="min")
    return int(ranks.loc[key]), len(valid)


def _annual_snapshot(daily: pd.DataFrame, value_col: str) -> pd.Series[float]:
    """One row per water year: its last available value on or before ``as_of``."""
    wy = water_year(pd.DatetimeIndex(daily["date"]))
    return (
        daily.assign(water_year=wy)
        .sort_values("date")
        .groupby("water_year")[value_col]
        .last()
    )


def _kpi_row(
    kpi_id: str,
    label: str,
    value: float,
    unit: str,
    display: str,
    rank: int,
    n_years: int,
    as_of: date,
    is_partial: bool,
) -> dict[str, object]:
    return {
        "kpi_id": kpi_id,
        "label": label,
        "value": value,
        "unit": unit,
        "display": display,
        "rank": rank,
        "n_years": n_years,
        "rank_phrase": f"{_ordinal(rank)} lowest of {n_years}",
        "as_of": as_of,
        "is_partial": is_partial,
    }


def kpis(
    snow_annual_table: pd.DataFrame,
    runoff_table: pd.DataFrame,
    reservoir_storage_table: pd.DataFrame,
    supply_table: pd.DataFrame,
    as_of: date,
    normals: YearSpan = NORMALS_PERIOD,
) -> pd.DataFrame:
    """The "2026 at a glance" tiles (design §6.9, decision 0027).

    Every tile ranks ascending (1 = lowest on record). Continuous daily
    metrics (Powell's ft above minimum power pool, combined percent full) are
    reduced to one value per water year -- that year's most recent reading on
    or before ``as_of`` -- so the in-progress year ranks on equal footing with
    complete ones.
    """
    wy = water_year(as_of)
    wy_is_partial = as_of < water_year_bounds(wy).end

    peak_pct = snow_annual_table.set_index("water_year")["peak_pct_of_median"]
    peak_rank, peak_n = _rank_lowest(peak_pct, wy)

    normal_apr_jul = runoff_table.loc[
        runoff_table["water_year"].between(normals.first, normals.last),
        "apr_jul_unreg_maf",
    ].mean()
    apr_jul_pct_normal = (
        100 * runoff_table.set_index("water_year")["apr_jul_unreg_maf"] / normal_apr_jul
    )
    inflow_rank, inflow_n = _rank_lowest(apr_jul_pct_normal, wy)

    efficiency_index = runoff_table.set_index("water_year")["runoff_efficiency_index"]
    efficiency_rank, efficiency_n = _rank_lowest(efficiency_index, wy)

    powell = reservoir_storage_table.loc[
        reservoir_storage_table["reservoir"] == LAKE_POWELL.name
    ]
    powell_annual = _annual_snapshot(powell, "ft_above_min_power_pool")
    powell_rank, powell_n = _rank_lowest(powell_annual, wy)
    powell_latest = powell.sort_values("date")["ft_above_min_power_pool"].iloc[-1]

    combined = reservoir_storage_table.loc[
        reservoir_storage_table["reservoir"] == "Combined"
    ]
    combined_annual = _annual_snapshot(combined, "pct_full")
    combined_rank, combined_n = _rank_lowest(combined_annual, wy)
    combined_latest = combined.sort_values("date")["pct_full"].iloc[-1]

    supply_by_year = supply_table.set_index("water_year")
    flow_values = supply_by_year["natural_flow_maf"]
    flow_rank, flow_n = _rank_lowest(flow_values, wy)
    flow_maf = float(flow_values.loc[wy])
    flow_is_estimated = bool(supply_by_year["kind"].loc[wy] == "estimated")

    return pd.DataFrame(
        [
            _kpi_row(
                "peak_swe_pct_median",
                "Peak snowpack",
                peak_pct.loc[wy],
                "%",
                f"{peak_pct.loc[wy]:.0f}% of median",
                peak_rank,
                peak_n,
                as_of,
                wy_is_partial,
            ),
            _kpi_row(
                "apr_jul_inflow_pct_normal",
                "Spring runoff",
                apr_jul_pct_normal.loc[wy],
                "%",
                f"{apr_jul_pct_normal.loc[wy]:.0f}% of the 1991-2020 average",
                inflow_rank,
                inflow_n,
                as_of,
                wy_is_partial,
            ),
            _kpi_row(
                "runoff_efficiency_index",
                "Runoff efficiency",
                efficiency_index.loc[wy],
                "index",
                f"{efficiency_index.loc[wy]:.0f} (100 = normal)",
                efficiency_rank,
                efficiency_n,
                as_of,
                wy_is_partial,
            ),
            _kpi_row(
                "powell_ft_above_min_power_pool",
                "Lake Powell",
                powell_latest,
                "ft",
                f"{powell_latest:.0f} ft above minimum power pool",
                powell_rank,
                powell_n,
                as_of,
                wy_is_partial,
            ),
            _kpi_row(
                "combined_storage_pct_full",
                "Combined storage",
                combined_latest,
                "%",
                f"{combined_latest:.0f}% full",
                combined_rank,
                combined_n,
                as_of,
                wy_is_partial,
            ),
            _kpi_row(
                "annual_natural_flow_maf",
                "Natural flow this water year",
                flow_maf,
                "MAF",
                f"{flow_maf:.1f} MAF" + (" (estimated)" if flow_is_estimated else ""),
                flow_rank,
                flow_n,
                as_of,
                flow_is_estimated,
            ),
        ]
    )
