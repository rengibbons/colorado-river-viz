from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from colorado_river_viz import cache
from colorado_river_viz.cache import (
    Fetchers,
    FullFetch,
    ManifestEntry,
    Skip,
    WindowFetch,
    load_annual,
    load_daily,
    load_outline,
    load_river_trace,
    load_snotel_daily,
    load_snotel_medians,
    plan_daily_refresh,
    read_manifest,
    refresh_story,
    upsert_on_date,
    write_parquet_atomic,
)
from colorado_river_viz.catalog import (
    CISCO,
    FULL_HISTORY_START,
    LEES_FERRY,
    MEKO_RECON,
    NATURAL_FLOW,
    POWELL_UNREGULATED_INFLOW,
    RIVER_TRACE,
    UPPER_BASIN_OUTLINE,
    BasinOutline,
    PublishedFile,
    RiseDailySeries,
    SnotelDailySeries,
    UsgsDailySeries,
)
from colorado_river_viz.data_sources import DateRange
from colorado_river_viz.errors import CacheMissError
from colorado_river_viz.schema import annual_frame, canonical_frame
from colorado_river_viz.settings import Settings
from colorado_river_viz.snotel import (
    SnotelBatch,
    daily_median_table,
    select_index_stations,
    snotel_series_id,
)

FIRST_RUN = datetime(2026, 9, 1, 12, tzinfo=UTC)
LATER_RUN = FIRST_RUN + timedelta(days=17)
INDEX_TRIPLETS = ["1:CO:SNTL", "2:CO:SNTL"]


def _daily(
    series_id: str, start: str, end: str, value: float = 1.0, approval: str = "approved"
) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    return canonical_frame(
        series_id=series_id,
        dates=dates,
        values=pd.Series([value] * len(dates)),
        unit="cfs",
        approval=pd.Series([approval] * len(dates)),
    )


def _in_window(frame: pd.DataFrame, window: DateRange) -> pd.DataFrame:
    mask = frame["date"].between(pd.Timestamp(window.start), pd.Timestamp(window.end))
    return frame[mask].reset_index(drop=True)


@dataclass
class FakeSources:
    """Serves a 'true' record per series, filtered to each requested window."""

    daily: dict[str, pd.DataFrame]
    calls: list[tuple[str, DateRange]] = field(default_factory=list)
    fail_on: set[str] = field(default_factory=set)

    def _serve(self, series_id: str, window: DateRange) -> pd.DataFrame:
        self.calls.append((series_id, window))
        if series_id in self.fail_on:
            raise RuntimeError(f"simulated crash fetching {series_id}")
        return _in_window(self.daily[series_id], window)

    def usgs(self, spec: UsgsDailySeries, window: DateRange) -> pd.DataFrame:
        return self._serve(spec.series_id, window)

    def rise(self, spec: RiseDailySeries, window: DateRange) -> pd.DataFrame:
        return self._serve(spec.series_id, window)

    def snotel(self, triplets: Sequence[str], window: DateRange) -> SnotelBatch:
        frames = [self._serve(snotel_series_id(t), window) for t in triplets]
        medians = daily_median_table(
            [
                pd.DataFrame(
                    {
                        "station_triplet": [t],
                        "month": [1],
                        "day": [1],
                        "median_swe_in": [5.0],
                    }
                )
                for t in triplets
            ]
        )
        return SnotelBatch(
            daily_swe=pd.concat(frames, ignore_index=True), medians=medians
        )

    def stations(self) -> pd.DataFrame:
        self.calls.append(("stations", DateRange(date.min, date.min)))
        table = pd.DataFrame(
            {
                "station_triplet": [*INDEX_TRIPLETS, "3:UT:SNTL"],
                "daily_swe_begin_date": pd.to_datetime(
                    ["1978-10-01", "1979-10-01", "2010-10-01"]
                ),
            }
        )
        return table.assign(in_index=select_index_stations(table, date(1980, 10, 1)))

    def published(self, spec: PublishedFile, downloads: Path) -> pd.DataFrame:
        self.calls.append((spec.series_id, DateRange(date.min, date.min)))
        downloads.mkdir(parents=True, exist_ok=True)
        (downloads / f"{spec.series_id}.original").write_text("verbatim")
        return annual_frame(spec.series_id, [2020, 2021], [1.0, 2.0], ["final"] * 2)

    def outline(self, spec: BasinOutline) -> dict[str, Any]:
        self.calls.append((spec.series_id, DateRange(date.min, date.min)))
        return {"type": "FeatureCollection", "features": [{"huc2": spec.huc2}]}

    def river_trace(self) -> dict[str, Any]:
        self.calls.append((RIVER_TRACE.series_id, DateRange(date.min, date.min)))
        return {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "LineString"}}],
        }

    def fetchers(self) -> Fetchers:
        return Fetchers(
            usgs=self.usgs,
            rise=self.rise,
            snotel=self.snotel,
            snotel_stations=self.stations,
            published=self.published,
            outline=self.outline,
            river_trace=self.river_trace,
        )

    def windows_for(self, series_id: str) -> list[DateRange]:
        return [window for sid, window in self.calls if sid == series_id]


def _truth() -> dict[str, pd.DataFrame]:
    ids = [
        "USGS-09180500__00060",
        "USGS-09380000__00060",
        "rise-0508",
        "rise-0509",
        "rise-0512",
        "rise-6123",
        "rise-6124",
        *[snotel_series_id(t) for t in INDEX_TRIPLETS],
    ]
    return {
        series_id: _daily(series_id, "2026-01-01", "2026-08-31") for series_id in ids
    }


@pytest.fixture
def sources() -> FakeSources:
    return FakeSources(daily=_truth())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(cache_dir=tmp_path / "cache")


def _refresh(
    sources: FakeSources, settings: Settings, mode: cache.RefreshMode, now: datetime
) -> None:
    refresh_story(mode, settings, fetchers=sources.fetchers(), now=now)


def test_offline_on_an_empty_cache_raises_cache_miss(
    sources: FakeSources, settings: Settings
) -> None:
    with pytest.raises(CacheMissError, match="REFRESH='incremental'"):
        _refresh(sources, settings, "offline", FIRST_RUN)
    assert sources.calls == []


def test_first_incremental_run_fetches_full_history_and_offline_reads_it(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)

    assert sources.windows_for(CISCO.series_id) == [
        DateRange(FULL_HISTORY_START, FIRST_RUN.date())
    ]
    cisco = load_daily(settings.cache_dir, CISCO)
    assert len(cisco) == len(sources.daily[CISCO.series_id])
    assert pd.api.types.is_datetime64_dtype(cisco["date"])

    sources.calls.clear()
    _refresh(sources, settings, "offline", LATER_RUN)
    assert sources.calls == []


def test_incremental_refetches_only_the_lookback_window(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)
    sources.calls.clear()

    _refresh(sources, settings, "incremental", LATER_RUN)

    assert sources.windows_for(LEES_FERRY.series_id) == [
        DateRange(date(2026, 8, 31) - timedelta(days=60), LATER_RUN.date())
    ]
    assert sources.windows_for(snotel_series_id("1:CO:SNTL")) == [
        DateRange(date(2026, 7, 2), LATER_RUN.date())
    ]
    assert sources.windows_for(NATURAL_FLOW.series_id) == []
    assert sources.windows_for("stations") == []


def test_incremental_skips_series_fetched_within_12_hours(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)
    sources.calls.clear()

    _refresh(sources, settings, "incremental", FIRST_RUN + timedelta(hours=11))

    assert sources.calls == []


def test_revised_values_replace_cached_ones_and_new_days_are_added(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)
    sources.daily[CISCO.series_id] = pd.concat(
        [
            _daily(CISCO.series_id, "2026-01-01", "2026-08-19", value=1.0),
            _daily(CISCO.series_id, "2026-08-20", "2026-09-15", value=2.0),
        ],
        ignore_index=True,
    )

    _refresh(sources, settings, "incremental", LATER_RUN)

    cisco = load_daily(settings.cache_dir, CISCO).set_index("date")["value"]
    assert cisco[pd.Timestamp("2026-08-19")] == 1.0
    assert cisco[pd.Timestamp("2026-08-20")] == 2.0
    assert cisco.index.max() == pd.Timestamp("2026-09-15")
    assert cisco.index.is_unique
    manifest = read_manifest(settings.cache_dir)
    assert manifest[CISCO.series_id].last_date == date(2026, 9, 15)


def test_usgs_lookback_reaches_back_to_the_earliest_provisional_row(
    sources: FakeSources, settings: Settings
) -> None:
    sources.daily[LEES_FERRY.series_id] = pd.concat(
        [
            _daily(LEES_FERRY.series_id, "2026-01-01", "2026-03-31"),
            _daily(
                LEES_FERRY.series_id,
                "2026-04-01",
                "2026-08-31",
                approval="provisional",
            ),
        ],
        ignore_index=True,
    )
    _refresh(sources, settings, "incremental", FIRST_RUN)
    assert read_manifest(settings.cache_dir)[
        LEES_FERRY.series_id
    ].earliest_provisional_date == date(2026, 4, 1)
    sources.calls.clear()

    _refresh(sources, settings, "incremental", LATER_RUN)

    assert sources.windows_for(LEES_FERRY.series_id)[0].start == date(2026, 4, 1)


def test_full_refetches_published_files_and_station_table(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)
    sources.calls.clear()

    _refresh(sources, settings, "full", FIRST_RUN + timedelta(hours=1))

    assert sources.windows_for(NATURAL_FLOW.series_id) != []
    assert sources.windows_for("stations") != []
    assert sources.windows_for(CISCO.series_id)[0].start == FULL_HISTORY_START


def test_a_crash_keeps_every_series_finished_before_it(
    sources: FakeSources, settings: Settings
) -> None:
    sources.fail_on = {POWELL_UNREGULATED_INFLOW.series_id}

    with pytest.raises(RuntimeError, match="simulated crash"):
        _refresh(sources, settings, "incremental", FIRST_RUN)

    manifest = read_manifest(settings.cache_dir)
    assert CISCO.series_id in manifest
    assert "rise-0509" in manifest
    assert POWELL_UNREGULATED_INFLOW.series_id not in manifest
    assert len(load_daily(settings.cache_dir, CISCO)) > 0

    sources.fail_on = set()
    sources.calls.clear()
    _refresh(sources, settings, "incremental", FIRST_RUN + timedelta(minutes=5))
    assert sources.windows_for(CISCO.series_id) == []
    assert sources.windows_for(POWELL_UNREGULATED_INFLOW.series_id) != []


def test_snotel_stations_are_cached_per_station_with_medians(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)

    specs = [
        SnotelDailySeries(series_id=snotel_series_id(t), station_triplet=t)
        for t in INDEX_TRIPLETS
    ]
    swe = load_snotel_daily(settings.cache_dir, specs)
    assert set(swe["series_id"]) == {snotel_series_id(t) for t in INDEX_TRIPLETS}
    assert set(load_snotel_medians(settings.cache_dir)["station_triplet"]) == set(
        INDEX_TRIPLETS
    )
    assert snotel_series_id("3:UT:SNTL") not in read_manifest(settings.cache_dir)


def test_published_files_and_outlines_round_trip(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)

    assert load_annual(settings.cache_dir, MEKO_RECON)["value_af"].tolist() == [
        1.0,
        2.0,
    ]
    assert load_outline(settings.cache_dir, UPPER_BASIN_OUTLINE)["features"] == [
        {"huc2": "14"}
    ]
    assert len(load_river_trace(settings.cache_dir, RIVER_TRACE)["features"]) == 1
    downloads = settings.cache_dir / "published" / "downloads"
    assert (downloads / f"{NATURAL_FLOW.series_id}.original").read_text() == "verbatim"


def test_manifest_is_readable_json_with_the_design_fields(
    sources: FakeSources, settings: Settings
) -> None:
    _refresh(sources, settings, "incremental", FIRST_RUN)

    raw = json.loads((settings.cache_dir / "manifest.json").read_text())
    assert raw["rise-0512"] | {"fetched_at": None} == {
        "series_id": "rise-0512",
        "source": "rise",
        "params": {"item_id": 512},
        "unit": "cfs",
        "first_date": "2026-01-01",
        "last_date": "2026-08-31",
        "row_count": 243,
        "earliest_provisional_date": None,
        "fetched_at": None,
        "refresh_policy": "incremental",
    }


def test_failed_write_leaves_no_temp_file_and_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def write_half_then_fail(self: pd.DataFrame, path: Path, **_: Any) -> None:
        Path(path).write_bytes(b"PAR1 half a file")
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", write_half_then_fail)
    target = tmp_path / "raw" / "usgs" / "x.parquet"

    with pytest.raises(OSError, match="disk full"):
        write_parquet_atomic(_daily("x", "2026-01-01", "2026-01-02"), target)

    assert list(target.parent.iterdir()) == []


def test_upsert_prefers_fetched_rows_on_the_same_date() -> None:
    existing = _daily("s", "2026-01-01", "2026-01-03", value=1.0)
    fetched = _daily("s", "2026-01-03", "2026-01-04", value=9.0)

    merged = upsert_on_date(existing, fetched)

    assert merged["value"].tolist() == [1.0, 1.0, 9.0, 9.0]


def _entry(**overrides: Any) -> ManifestEntry:
    values: dict[str, Any] = {
        "series_id": "s",
        "source": "usgs",
        "params": {},
        "unit": "cfs",
        "first_date": date(2000, 1, 1),
        "last_date": date(2026, 8, 31),
        "row_count": 1,
        "earliest_provisional_date": None,
        "fetched_at": FIRST_RUN,
        "refresh_policy": "incremental",
    }
    return ManifestEntry.model_validate(values | overrides)


@pytest.mark.parametrize(
    ("entry", "mode", "now", "expected"),
    [
        (None, "incremental", LATER_RUN, FullFetch()),
        (_entry(), "full", LATER_RUN, FullFetch()),
        (_entry(), "offline", LATER_RUN, Skip("offline")),
        (_entry(), "incremental", LATER_RUN, WindowFetch(date(2026, 7, 2))),
        (
            _entry(earliest_provisional_date=date(2026, 3, 1)),
            "incremental",
            LATER_RUN,
            WindowFetch(date(2026, 3, 1)),
        ),
        (
            _entry(earliest_provisional_date=date(2026, 8, 30)),
            "incremental",
            LATER_RUN,
            WindowFetch(date(2026, 7, 2)),
        ),
    ],
)
def test_plan_daily_refresh(
    entry: ManifestEntry | None,
    mode: cache.RefreshMode,
    now: datetime,
    expected: cache.FetchPlan,
) -> None:
    assert plan_daily_refresh("s", entry, mode, now) == expected


def test_plan_offline_without_an_entry_names_the_missing_series() -> None:
    with pytest.raises(CacheMissError, match="rise-0512"):
        plan_daily_refresh("rise-0512", None, "offline", LATER_RUN)
