from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from colorado_river_viz.cache import write_parquet_atomic
from colorado_river_viz.catalog import (
    POWELL_UNREGULATED_INFLOW,
    SNOTEL_MEDIANS_SERIES_ID,
    snotel_index_series,
)
from colorado_river_viz.constants import YearSpan
from colorado_river_viz.schema import canonical_frame
from colorado_river_viz.story_tables import (
    runoff_vs_snow,
    snow_annual,
    snow_index_daily,
    snow_index_envelope,
)

WATER_YEARS = (2024, 2025)


def _stations(triplets: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"station_triplet": triplets, "in_index": True})


def _build_and_melt(
    peak_doy: int, peak_swe: float, meltout_doy: int
) -> pd.Series[float]:
    dates = pd.date_range("2023-10-01", "2025-09-30", freq="D")
    doy_within_year = pd.Series(
        ((dates - pd.Timestamp("2023-10-01")).days % 365) + 1, index=dates
    )
    build = peak_swe * doy_within_year / peak_doy
    melt = (peak_swe * (meltout_doy - doy_within_year) / (meltout_doy - peak_doy)).clip(
        lower=0
    )
    return build.where(doy_within_year <= peak_doy, melt)


def _write_station_cache(
    cache_dir: Path, stations: pd.DataFrame, station_values: dict[str, pd.Series[float]]
) -> None:
    specs = snotel_index_series(stations)
    for spec in specs:
        values = station_values[spec.station_triplet]
        frame = canonical_frame(
            spec.series_id, pd.DatetimeIndex(values.index), values, "in", "unknown"
        )
        path = cache_dir / "raw" / "snotel" / f"{spec.series_id}.parquet"
        write_parquet_atomic(frame, path)

    days = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    medians = pd.DataFrame(
        [
            {
                "station_triplet": triplet,
                "month": day.month,
                "day": day.day,
                "median_swe_in": 10.0,
            }
            for triplet in stations["station_triplet"]
            for day in days
        ]
    )
    write_parquet_atomic(
        medians, cache_dir / "reference" / f"{SNOTEL_MEDIANS_SERIES_ID}.parquet"
    )


def _write_inflow_cache(cache_dir: Path, cfs_by_water_year: dict[int, float]) -> None:
    dates = pd.date_range("2023-10-01", "2025-09-30", freq="D")
    wy = pd.Index(dates.year + (dates.month >= 10).astype(int))
    values = pd.Series([cfs_by_water_year[y] for y in wy], index=dates)
    frame = canonical_frame(
        POWELL_UNREGULATED_INFLOW.series_id, dates, values, "cfs", "unknown"
    )
    write_parquet_atomic(
        frame,
        cache_dir / "raw" / "rise" / f"{POWELL_UNREGULATED_INFLOW.series_id}.parquet",
    )


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def stations() -> pd.DataFrame:
    return _stations(["1:CO:SNTL", "2:CO:SNTL"])


def test_snow_index_daily_has_the_design_columns_and_dtypes(
    cache_dir: Path, stations: pd.DataFrame
) -> None:
    _write_station_cache(
        cache_dir,
        stations,
        {
            "1:CO:SNTL": _build_and_melt(190, 15.0, 260),
            "2:CO:SNTL": _build_and_melt(190, 15.0, 260),
        },
    )

    daily = snow_index_daily(cache_dir, stations)

    assert list(daily.columns) == [
        "date",
        "water_year",
        "day_of_water_year",
        "basin_swe_in",
        "pct_of_median",
        "stations_reporting",
    ]
    assert daily["water_year"].dtype == "int64"
    assert daily["basin_swe_in"].dtype == "float64"
    assert daily.to_json(orient="records")


def test_snow_index_envelope_gives_median_and_band_for_one_normal_year(
    cache_dir: Path, stations: pd.DataFrame
) -> None:
    _write_station_cache(
        cache_dir,
        stations,
        {
            "1:CO:SNTL": _build_and_melt(190, 10.0, 260),
            "2:CO:SNTL": _build_and_melt(190, 10.0, 260),
        },
    )
    daily = snow_index_daily(cache_dir, stations)
    daily.loc[daily["water_year"] == 2024, "water_year"] = 1991

    envelope = snow_index_envelope(daily, normals=YearSpan(1991, 1991))

    assert list(envelope.columns) == [
        "day_of_water_year",
        "median_swe_in",
        "p10_swe_in",
        "p90_swe_in",
    ]
    assert envelope["median_swe_in"].max() == pytest.approx(10.0, abs=0.1)


def test_snow_annual_has_the_design_columns(
    cache_dir: Path, stations: pd.DataFrame
) -> None:
    _write_station_cache(
        cache_dir,
        stations,
        {
            "1:CO:SNTL": _build_and_melt(190, 15.0, 260),
            "2:CO:SNTL": _build_and_melt(190, 15.0, 260),
        },
    )
    daily = snow_index_daily(cache_dir, stations)

    annual = snow_annual(cache_dir, stations, daily)

    assert list(annual.columns) == [
        "water_year",
        "peak_swe_in",
        "peak_date",
        "apr1_swe_in",
        "apr1_pct_of_median",
        "peak_pct_of_median",
        "station_peak_date_median",
        "station_meltout_date_median",
    ]
    row = annual[annual["water_year"] == 2024].iloc[0]
    assert row["peak_swe_in"] == pytest.approx(15.0)
    assert row["station_peak_date_median"] == pd.Timestamp("2023-10-01") + pd.Timedelta(
        days=189
    )


def test_runoff_vs_snow_computes_efficiency_against_the_normal_mean(
    cache_dir: Path, stations: pd.DataFrame
) -> None:
    _write_station_cache(
        cache_dir,
        stations,
        {
            "1:CO:SNTL": _build_and_melt(190, 15.0, 260),
            "2:CO:SNTL": _build_and_melt(190, 15.0, 260),
        },
    )
    _write_inflow_cache(cache_dir, {2024: 1000.0, 2025: 1000.0})
    daily = snow_index_daily(cache_dir, stations)
    annual = snow_annual(cache_dir, stations, daily)

    runoff = runoff_vs_snow(cache_dir, annual, normals=YearSpan(2024, 2025))

    assert list(runoff.columns) == [
        "water_year",
        "apr_jul_unreg_maf",
        "peak_swe_in",
        "runoff_efficiency",
        "runoff_efficiency_index",
    ]
    assert runoff["runoff_efficiency_index"].tolist() == pytest.approx([100.0, 100.0])
    assert runoff.to_json(orient="records")
