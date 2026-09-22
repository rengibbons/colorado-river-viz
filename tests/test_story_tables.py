from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from colorado_river_viz.cache import write_parquet_atomic
from colorado_river_viz.catalog import (
    CISCO,
    LEES_FERRY,
    MEKO_RECON,
    NATURAL_FLOW,
    POWELL_UNREGULATED_INFLOW,
    SNOTEL_MEDIANS_SERIES_ID,
    snotel_index_series,
)
from colorado_river_viz.constants import AF_PER_MAF, YearSpan
from colorado_river_viz.metrics.flow import water_year_totals
from colorado_river_viz.schema import annual_frame, canonical_frame
from colorado_river_viz.story_tables import (
    MAP_SITES,
    annual_supply,
    basin_map_layers,
    cisco_hydrograph,
    lees_ferry_regimes,
    paleo_supply,
    runoff_vs_snow,
    snow_annual,
    snow_index_daily,
    snow_index_envelope,
    timing_annual,
)
from colorado_river_viz.water_year import water_year_bounds

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


def _constant_flow_daily(cfs_by_wy: dict[int, float]) -> pd.DataFrame:
    frames = []
    for wy, cfs in cfs_by_wy.items():
        bounds = water_year_bounds(wy)
        dates = pd.date_range(bounds.start, bounds.end, freq="D")
        frames.append(pd.DataFrame({"date": dates, "value": cfs}))
    return pd.concat(frames, ignore_index=True)


def test_annual_supply_estimates_missing_years_and_keeps_published_ones(
    cache_dir: Path,
) -> None:
    unregulated = _constant_flow_daily({wy: 4000.0 for wy in range(1964, 2023)})
    write_parquet_atomic(
        canonical_frame(
            POWELL_UNREGULATED_INFLOW.series_id,
            pd.DatetimeIndex(unregulated["date"]),
            unregulated["value"],
            "cfs",
            "unknown",
        ),
        cache_dir / "raw" / "rise" / f"{POWELL_UNREGULATED_INFLOW.series_id}.parquet",
    )
    totals = water_year_totals(unregulated)
    published_years = totals[totals["water_year"] <= 2020]
    natural = annual_frame(
        NATURAL_FLOW.series_id,
        published_years["water_year"].tolist(),
        (published_years["total_maf"] * AF_PER_MAF).tolist(),
        ["final"] * len(published_years),
    )
    write_parquet_atomic(
        natural, cache_dir / "published" / f"{NATURAL_FLOW.series_id}.parquet"
    )

    supply = annual_supply(cache_dir, today=date(2023, 1, 1))

    assert list(supply.columns) == [
        "water_year",
        "natural_flow_maf",
        "kind",
        "estimate_low_maf",
        "estimate_high_maf",
        "through_date",
    ]
    published_rows = supply[supply["water_year"] <= 2020]
    assert (published_rows["kind"] == "published_final").all()
    assert published_rows["estimate_low_maf"].isna().all()

    for wy in (2021, 2022):
        row = supply[supply["water_year"] == wy].iloc[0]
        assert row["kind"] == "estimated"
        assert row["estimate_low_maf"] < row["natural_flow_maf"]
        assert row["natural_flow_maf"] < row["estimate_high_maf"]


def test_paleo_supply_has_a_twenty_year_rolling_mean(cache_dir: Path) -> None:
    years = list(range(762, 802))
    values = [float(i) for i in range(len(years))]
    meko = annual_frame(
        MEKO_RECON.series_id,
        years,
        [v * AF_PER_MAF for v in values],
        ["final"] * len(years),
    )
    write_parquet_atomic(
        meko, cache_dir / "published" / f"{MEKO_RECON.series_id}.parquet"
    )

    paleo = paleo_supply(cache_dir)

    assert list(paleo.columns) == ["water_year", "recon_maf", "recon_20yr_mean_maf"]
    assert paleo["recon_20yr_mean_maf"].isna().sum() == 19
    assert paleo["recon_20yr_mean_maf"].iloc[19] == pytest.approx(sum(values[:20]) / 20)


def _rising_flow_daily(wy: int, through_day: int | None = None) -> pd.DataFrame:
    """A hydrograph that rises then falls, so its center of volume is well inside
    the year rather than landing on an edge."""
    bounds = water_year_bounds(wy)
    dates = pd.date_range(bounds.start, bounds.end, freq="D")
    if through_day is not None:
        dates = dates[:through_day]
    doy = pd.Series(range(1, len(dates) + 1), index=dates)
    values = 1000 + 4000 * doy / len(dates)
    return pd.DataFrame({"date": dates, "value": values})


def _write_cisco_cache(cache_dir: Path, years: range, incomplete: set[int]) -> None:
    frames = [
        _rising_flow_daily(wy, through_day=50 if wy in incomplete else None)
        for wy in years
    ]
    daily = pd.concat(frames, ignore_index=True)
    frame = canonical_frame(
        CISCO.series_id,
        pd.DatetimeIndex(daily["date"]),
        daily["value"],
        "cfs",
        "unknown",
    )
    write_parquet_atomic(
        frame, cache_dir / "raw" / "usgs" / f"{CISCO.series_id}.parquet"
    )


def test_timing_annual_gives_expected_days_and_excludes_incomplete_cisco_years(
    cache_dir: Path,
) -> None:
    _write_cisco_cache(cache_dir, range(2020, 2023), incomplete={2022})
    snow_annual_table = pd.DataFrame(
        {
            "water_year": [2020, 2021, 2022],
            "station_peak_date_median": [
                pd.Timestamp("2020-03-15"),
                pd.Timestamp("2021-03-20"),
                pd.NaT,
            ],
            "station_meltout_date_median": [
                pd.Timestamp("2020-06-01"),
                pd.Timestamp("2021-06-05"),
                pd.NaT,
            ],
        }
    )

    timing = timing_annual(cache_dir, snow_annual_table)

    assert list(timing.columns) == [
        "water_year",
        "snow_peak_doy",
        "snow_meltout_doy",
        "cisco_center_of_volume_doy",
    ]
    row_2020 = timing[timing["water_year"] == 2020].iloc[0]
    # Oct 1 -> Mar 15 / Jun 1; WY2020 is a leap water year, hence the +1.
    assert row_2020["snow_peak_doy"] == pytest.approx(167.0)
    assert row_2020["snow_meltout_doy"] == pytest.approx(245.0)
    assert not pd.isna(row_2020["cisco_center_of_volume_doy"])

    row_2022 = timing[timing["water_year"] == 2022].iloc[0]
    assert pd.isna(row_2022["snow_peak_doy"])
    assert pd.isna(row_2022["cisco_center_of_volume_doy"])  # incomplete year excluded


def test_cisco_hydrograph_has_an_envelope_from_the_baseline_years(
    cache_dir: Path,
) -> None:
    _write_cisco_cache(cache_dir, range(1914, 1965), incomplete=set())

    hydro = cisco_hydrograph(cache_dir)

    assert list(hydro.columns) == [
        "date",
        "water_year",
        "day_of_water_year",
        "cfs",
        "median_cfs",
        "p10_cfs",
        "p90_cfs",
    ]
    assert hydro["median_cfs"].notna().all()
    post_baseline = hydro[hydro["water_year"] == 1964]
    assert post_baseline["median_cfs"].notna().all()


def _write_lees_ferry_cache(cache_dir: Path, years: range) -> None:
    frames = [_rising_flow_daily(wy) for wy in years]
    daily = pd.concat(frames, ignore_index=True)
    frame = canonical_frame(
        LEES_FERRY.series_id,
        pd.DatetimeIndex(daily["date"]),
        daily["value"],
        "cfs",
        "unknown",
    )
    write_parquet_atomic(
        frame, cache_dir / "raw" / "usgs" / f"{LEES_FERRY.series_id}.parquet"
    )


@pytest.mark.parametrize(
    ("water_year", "expected_regime"),
    [(1962, "before_dam"), (1963, None), (1980, None), (1981, "after_dam")],
)
def test_lees_ferry_regimes_labels_years_at_the_dam_boundaries(
    cache_dir: Path, water_year: int, expected_regime: str | None
) -> None:
    _write_lees_ferry_cache(cache_dir, range(1922, 1985))

    regimes = lees_ferry_regimes(cache_dir)

    peak_years = (
        set(
            regimes.annual_peaks.loc[
                regimes.annual_peaks["regime"] == expected_regime, "water_year"
            ]
        )
        if expected_regime is not None
        else set()
    )
    if expected_regime is None:
        assert water_year not in set(regimes.annual_peaks["water_year"])
    else:
        assert water_year in peak_years


def test_lees_ferry_regimes_envelope_has_a_full_day_of_water_year_range(
    cache_dir: Path,
) -> None:
    _write_lees_ferry_cache(cache_dir, range(1922, 1963))

    regimes = lees_ferry_regimes(cache_dir)

    before = regimes.envelope[regimes.envelope["regime"] == "before_dam"]
    assert set(before["regime"]) == {"before_dam"}
    assert before["day_of_water_year"].min() == 1
    assert (before["p10_cfs"] <= before["median_cfs"]).all()
    assert (before["median_cfs"] <= before["p90_cfs"]).all()


def test_basin_map_layers_has_one_site_row_per_map_site_and_both_outlines(
    cache_dir: Path,
) -> None:
    upper = {"type": "FeatureCollection", "features": [{"huc2": "14"}]}
    lower = {"type": "FeatureCollection", "features": [{"huc2": "15"}]}
    reference_dir = cache_dir / "reference"
    reference_dir.mkdir(parents=True)
    (reference_dir / "wbd_huc2_14.geojson").write_text(json.dumps(upper))
    (reference_dir / "wbd_huc2_15.geojson").write_text(json.dumps(lower))
    stations = _stations(["1:CO:SNTL"])

    layers = basin_map_layers(cache_dir, stations)

    assert len(layers.sites) == len(MAP_SITES)
    assert set(layers.sites["kind"]) == {"gauge", "reservoir"}
    assert layers.basins["14"] == upper
    assert layers.basins["15"] == lower
    assert layers.stations is stations
