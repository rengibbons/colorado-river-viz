"""Basin snowpack metrics from the fixed SNOTEL index stations (decisions 0013, 0017).

Station data comes in as the canonical long frame (one ``series_id`` per station)
and is worked on as a wide date x station table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from colorado_river_viz.constants import COMPLETE_WATER_YEAR_MIN_COVERAGE
from colorado_river_viz.water_year import day_of_water_year, water_year

MAX_INTERPOLATED_GAP_DAYS = 7
MIN_REPORTING_FRACTION = 0.9
TIMING_SEASON_END = (7, 31)
"""Station timing needs data from Oct 1 through Jul 31 (decision 0024)."""


def station_triplet_of(series_id: str) -> str:
    """Invert ``snotel_series_id``: ``335_CO_SNTL__WTEQ`` -> ``335:CO:SNTL``."""
    return series_id.rsplit("__", 1)[0].replace("_", ":")


def to_wide(swe: pd.DataFrame) -> pd.DataFrame:
    """Pivot canonical station SWE to a daily date x station-triplet table.

    The index covers every day from the first to the last observation, so
    missing days appear as NaN.
    """
    wide = swe.assign(
        station=swe["series_id"].astype(str).map(station_triplet_of)
    ).pivot_table(index="date", columns="station", values="value", aggfunc="first")
    full_range = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    return wide.reindex(full_range).rename_axis(index="date", columns="station")


def fill_short_gaps(
    wide: pd.DataFrame, max_gap_days: int = MAX_INTERPOLATED_GAP_DAYS
) -> pd.DataFrame:
    """Linearly interpolate interior gaps of ``max_gap_days`` or fewer, per station.

    Longer gaps, and gaps before a station's first or after its last value, stay
    NaN.
    """
    return wide.apply(lambda column: _fill_column(column, max_gap_days))


def _fill_column(column: pd.Series[float], max_gap_days: int) -> pd.Series[float]:
    missing = column.isna()
    run_ids = (missing != missing.shift()).cumsum()
    run_lengths = missing.groupby(run_ids).transform("size")
    interpolated = column.interpolate(method="linear", limit_area="inside")
    fillable = missing & (run_lengths <= max_gap_days) & interpolated.notna()
    return column.where(~fillable, interpolated)


def medians_by_date(medians: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Expand the per-station calendar-day medians onto ``dates`` (date x station)."""
    by_month_day = medians.pivot_table(
        index=["month", "day"], columns="station_triplet", values="median_swe_in"
    )
    keys = pd.MultiIndex.from_arrays([dates.month, dates.day], names=["month", "day"])
    return (
        by_month_day.reindex(keys)
        .set_axis(dates, axis=0)
        .rename_axis(index="date", columns="station")
    )


def basin_index_daily(
    wide_swe: pd.DataFrame,
    medians: pd.DataFrame,
    min_reporting_fraction: float = MIN_REPORTING_FRACTION,
) -> pd.DataFrame:
    """Daily basin snow index from gap-filled station SWE (design §6.3).

    - ``basin_swe_in``: mean SWE across reporting stations.
    - ``pct_of_median``: 100 x (sum of station SWE) / (sum of their 1991-2020
      medians), over stations reporting both: the NRCS basin-index method.
    - Days with fewer than ``min_reporting_fraction`` of the stations reporting
      get NaN for both.

    ``wide_swe`` must have one column per index station, so its width is the size
    of the index.
    """
    index_size = wide_swe.shape[1]
    reporting = wide_swe.notna().sum(axis=1)
    enough = reporting >= min_reporting_fraction * index_size

    median_table = medians_by_date(medians, pd.DatetimeIndex(wide_swe.index))[
        wide_swe.columns
    ]
    both = wide_swe.notna() & median_table.notna()
    swe_sum = wide_swe.where(both).sum(axis=1)
    median_sum = median_table.where(both).sum(axis=1)

    dates = pd.DatetimeIndex(wide_swe.index)
    return pd.DataFrame(
        {
            "date": dates,
            "water_year": water_year(dates),
            "day_of_water_year": day_of_water_year(dates),
            "basin_swe_in": wide_swe.mean(axis=1).where(enough).to_numpy(),
            "pct_of_median": (100 * swe_sum / median_sum.replace(0, np.nan))
            .where(enough)
            .to_numpy(),
            "stations_reporting": reporting.to_numpy(),
        }
    )


def annual_peaks(index_daily: pd.DataFrame) -> pd.DataFrame:
    """Peak basin SWE per water year: ``water_year``, ``peak_swe_in``, ``peak_date``."""
    valid = index_daily.dropna(subset=["basin_swe_in"])
    peak_rows = valid.loc[valid.groupby("water_year")["basin_swe_in"].idxmax()]
    return (
        peak_rows[["water_year", "basin_swe_in", "date"]]
        .rename(columns={"basin_swe_in": "peak_swe_in", "date": "peak_date"})
        .reset_index(drop=True)
    )


def april_first(index_daily: pd.DataFrame) -> pd.DataFrame:
    """April 1 basin values: ``water_year``, ``apr1_swe_in``, ``apr1_pct_of_median``."""
    dates = index_daily["date"]
    rows = index_daily[(dates.dt.month == 4) & (dates.dt.day == 1)]
    april: pd.DataFrame = (
        rows[["water_year", "basin_swe_in", "pct_of_median"]]
        .rename(
            columns={
                "basin_swe_in": "apr1_swe_in",
                "pct_of_median": "apr1_pct_of_median",
            }
        )
        .reset_index(drop=True)
    )
    return april


def station_timing(wide_swe: pd.DataFrame) -> pd.DataFrame:
    """Per station and water year: the day of peak SWE and the melt-out day.

    Melt-out is the first day after the peak with SWE of zero; NaN if SWE never
    reaches zero in the data. A station-year counts only if it covers at least 98%
    of Oct 1 - Jul 31 (decision 0024). Columns: ``station``, ``water_year``,
    ``peak_doy``, ``meltout_doy``.
    """
    long = wide_swe.reset_index().melt(
        id_vars="date", var_name="station", value_name="swe"
    )
    long = long.assign(
        water_year=water_year(long["date"]),
        doy=day_of_water_year(long["date"]),
    )
    rows = [
        _station_year_timing(group)
        for _, group in long.groupby(["station", "water_year"])
    ]
    return pd.DataFrame(
        rows, columns=["station", "water_year", "peak_doy", "meltout_doy"]
    ).dropna(subset=["peak_doy"])


def _season_days(wy: int) -> int:
    end = pd.Timestamp(wy, *TIMING_SEASON_END)
    return (end - pd.Timestamp(wy - 1, 10, 1)).days + 1


def _station_year_timing(group: pd.DataFrame) -> tuple[str, int, float, float]:
    station = str(group["station"].iloc[0])
    wy = int(group["water_year"].iloc[0])
    season_end_doy = _season_days(wy)
    in_season = group[group["doy"] <= season_end_doy]
    coverage = in_season["swe"].notna().sum() / season_end_doy
    if coverage < COMPLETE_WATER_YEAR_MIN_COVERAGE:
        return (station, wy, np.nan, np.nan)
    ordered = group.dropna(subset=["swe"]).sort_values("doy")
    peak_position = ordered["swe"].to_numpy().argmax()
    peak_doy = float(ordered["doy"].iloc[peak_position])
    after_peak = ordered.iloc[peak_position + 1 :]
    melted = after_peak[after_peak["swe"] <= 0]
    meltout_doy = float(melted["doy"].iloc[0]) if len(melted) else np.nan
    return (station, wy, peak_doy, meltout_doy)


def basin_timing(
    station_timings: pd.DataFrame,
    index_size: int,
    min_reporting_fraction: float = MIN_REPORTING_FRACTION,
) -> pd.DataFrame:
    """Median peak and melt-out day across stations, per water year.

    A water year's median is NaN unless at least ``min_reporting_fraction`` of the
    index stations have a value for it. Columns: ``water_year``,
    ``station_peak_doy_median``, ``station_meltout_doy_median``.
    """
    needed = min_reporting_fraction * index_size
    grouped = station_timings.groupby("water_year")
    peak = grouped["peak_doy"].median().where(grouped["peak_doy"].count().ge(needed))
    meltout = (
        grouped["meltout_doy"].median().where(grouped["meltout_doy"].count().ge(needed))
    )
    return pd.DataFrame(
        {
            "station_peak_doy_median": peak,
            "station_meltout_doy_median": meltout,
        }
    ).reset_index()
