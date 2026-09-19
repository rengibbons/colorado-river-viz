import numpy as np
import pandas as pd
import pytest

from colorado_river_viz.metrics.snow import (
    annual_peaks,
    april_first,
    basin_index_daily,
    basin_timing,
    fill_short_gaps,
    station_timing,
    station_triplet_of,
    to_wide,
)
from colorado_river_viz.schema import canonical_frame
from colorado_river_viz.snotel import snotel_series_id

WY2025 = pd.date_range("2024-10-01", "2025-09-30", freq="D")


def _wide(
    columns: dict[str, list[float] | np.ndarray], dates: pd.DatetimeIndex
) -> pd.DataFrame:
    return pd.DataFrame(columns, index=dates).rename_axis(
        index="date", columns="station"
    )


def _flat_medians(stations: list[str], median: float) -> pd.DataFrame:
    days = pd.date_range("2024-01-01", "2024-12-31", freq="D")  # includes Feb 29
    return pd.DataFrame(
        [
            {
                "station_triplet": station,
                "month": day.month,
                "day": day.day,
                "median_swe_in": median,
            }
            for station in stations
            for day in days
        ]
    )


def _snowpack(peak_doy: int, peak_swe: float, meltout_doy: int | None) -> np.ndarray:
    """Linear build-up from Oct 1 to the peak, then linear melt to zero."""
    doy = np.arange(1, len(WY2025) + 1, dtype=float)
    build = peak_swe * doy / peak_doy
    if meltout_doy is None:
        melt = np.full_like(doy, peak_swe / 2)
    else:
        melt = np.clip(
            peak_swe * (meltout_doy - doy) / (meltout_doy - peak_doy), 0, None
        )
    return np.where(doy <= peak_doy, build, melt)


def test_series_id_maps_back_to_the_station_triplet() -> None:
    assert station_triplet_of(snotel_series_id("335:CO:SNTL")) == "335:CO:SNTL"


def test_to_wide_pivots_stations_and_exposes_missing_days() -> None:
    dates = pd.DatetimeIndex(["2025-01-01", "2025-01-03"])
    swe = canonical_frame(
        snotel_series_id("1:CO:SNTL"), dates, pd.Series([1.0, 3.0]), "in", "unknown"
    )

    wide = to_wide(swe)

    assert list(wide.columns) == ["1:CO:SNTL"]
    assert len(wide) == 3
    assert pd.isna(wide.iloc[1, 0])


def test_fills_gaps_of_seven_days_but_not_eight_or_edges() -> None:
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    values = np.arange(30, dtype=float)
    seven_gap = values.copy()
    seven_gap[5:12] = np.nan
    eight_gap = values.copy()
    eight_gap[5:13] = np.nan
    leading_gap = values.copy()
    leading_gap[:3] = np.nan

    filled = fill_short_gaps(
        _wide({"seven": seven_gap, "eight": eight_gap, "leading": leading_gap}, dates)
    )

    assert filled["seven"].tolist() == pytest.approx(values.tolist())
    assert filled["eight"].isna().sum() == 8
    assert filled["leading"].isna().sum() == 3


def test_basin_index_for_three_stations_with_a_known_answer() -> None:
    dates = pd.date_range("2025-04-01", periods=2, freq="D")
    wide = _wide({"a": [10.0, 12.0], "b": [20.0, 18.0], "c": [30.0, 30.0]}, dates)
    medians = pd.concat(
        [
            _flat_medians(["a"], 10.0),
            _flat_medians(["b"], 20.0),
            _flat_medians(["c"], 50.0),
        ]
    )

    index = basin_index_daily(wide, medians).set_index("date")

    assert index["basin_swe_in"].tolist() == pytest.approx([20.0, 20.0])
    assert index["pct_of_median"].tolist() == pytest.approx([75.0, 75.0])
    assert index.loc["2025-04-01", "water_year"] == 2025
    assert index.loc["2025-04-01", "day_of_water_year"] == 183


@pytest.mark.parametrize(
    ("missing_stations", "is_reported"),
    [(0, True), (1, True), (2, False)],
)
def test_ninety_percent_of_stations_must_report(
    missing_stations: int, is_reported: bool
) -> None:
    stations = [f"s{i}" for i in range(10)]
    values: dict[str, list[float] | np.ndarray] = {s: [10.0] for s in stations}
    for station in stations[:missing_stations]:
        values[station] = [np.nan]
    wide = _wide(values, pd.DatetimeIndex(["2025-03-01"]))

    index = basin_index_daily(wide, _flat_medians(stations, 20.0))

    row = index.iloc[0]
    assert row["stations_reporting"] == 10 - missing_stations
    assert (not np.isnan(row["basin_swe_in"])) is is_reported
    if is_reported:
        assert row["pct_of_median"] == pytest.approx(50.0)


def test_pct_of_median_is_nan_when_every_median_is_zero() -> None:
    wide = _wide({"a": [0.0]}, pd.DatetimeIndex(["2025-08-15"]))

    index = basin_index_daily(wide, _flat_medians(["a"], 0.0))

    assert index["basin_swe_in"].iloc[0] == 0.0
    assert np.isnan(index["pct_of_median"].iloc[0])


def test_annual_peak_and_april_first_values() -> None:
    wide = _wide({"a": _snowpack(peak_doy=190, peak_swe=19.0, meltout_doy=260)}, WY2025)
    index = basin_index_daily(wide, _flat_medians(["a"], 19.0))

    peak = annual_peaks(index).iloc[0]
    april = april_first(index).iloc[0]

    assert peak["water_year"] == 2025
    assert peak["peak_swe_in"] == pytest.approx(19.0)
    assert peak["peak_date"] == WY2025[189]
    assert april["apr1_swe_in"] == pytest.approx(19.0 * 183 / 190)
    assert april["apr1_pct_of_median"] == pytest.approx(100 * 183 / 190)


def test_station_peak_and_meltout_days() -> None:
    wide = _wide(
        {
            "early": _snowpack(peak_doy=170, peak_swe=15.0, meltout_doy=240),
            "late": _snowpack(peak_doy=200, peak_swe=30.0, meltout_doy=280),
            "never_melts": _snowpack(peak_doy=200, peak_swe=30.0, meltout_doy=None),
        },
        WY2025,
    )

    timing = station_timing(wide).set_index("station")

    assert timing.loc["early", "peak_doy"] == 170
    assert timing.loc["early", "meltout_doy"] == 240
    assert timing.loc["late", "meltout_doy"] == 280
    assert pd.isna(timing.loc["never_melts", "meltout_doy"])


def test_station_years_missing_much_of_the_season_are_dropped() -> None:
    patchy = _snowpack(peak_doy=170, peak_swe=15.0, meltout_doy=240)
    patchy[30:60] = np.nan

    timing = station_timing(_wide({"patchy": patchy}, WY2025))

    assert timing.empty


def test_basin_timing_takes_the_median_when_enough_stations_report() -> None:
    timings = pd.DataFrame(
        {
            "station": ["a", "b", "c", "a", "b"],
            "water_year": [2024, 2024, 2024, 2025, 2025],
            "peak_doy": [170.0, 180.0, 200.0, 175.0, 185.0],
            "meltout_doy": [240.0, 250.0, np.nan, 245.0, 255.0],
        }
    )

    basin = basin_timing(timings, index_size=3, min_reporting_fraction=0.9).set_index(
        "water_year"
    )

    assert basin.loc[2024, "station_peak_doy_median"] == 180.0
    assert pd.isna(basin.loc[2024, "station_meltout_doy_median"])
    assert pd.isna(basin.loc[2025, "station_peak_doy_median"])
