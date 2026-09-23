"""The local data cache: one file per series plus a manifest (design §3, §5).

Layout under ``cache_dir``::

    manifest.json
    raw/{usgs,rise,snotel}/<series_id>.parquet
    published/<series_id>.parquet   published/downloads/<original files>
    reference/snotel_stations_huc14.parquet   reference/snotel_daily_median.parquet
    reference/wbd_huc2_14.geojson   reference/wbd_huc2_15.geojson

Every file is written to ``<name>.tmp`` and then renamed into place, and the
manifest is rewritten after each series completes, so an interrupted refresh
keeps everything it finished (decision 0010).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import batched
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, TypeAdapter

from colorado_river_viz.catalog import (
    FULL_HISTORY_START,
    SNOTEL_MEDIANS_SERIES_ID,
    SNOTEL_STATIONS_SERIES_ID,
    BasinOutline,
    PublishedFile,
    PublishedFormat,
    RefreshPolicy,
    RiseDailySeries,
    SeriesSpec,
    SnotelDailySeries,
    UsgsDailySeries,
    story_series,
)
from colorado_river_viz.data_sources import (
    DateRange,
    fetch_rise_daily_canonical,
    fetch_usgs_daily_canonical,
)
from colorado_river_viz.errors import CacheMissError, UnexpectedSourceFormatError
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.published import (
    download_file,
    fetch_wbd_huc2_geojson,
    parse_meko_recon_txt,
    parse_natural_flow_xlsx,
)
from colorado_river_viz.schema import empty_canonical_frame
from colorado_river_viz.settings import Settings
from colorado_river_viz.snotel import (
    SNOTEL_BATCH_SIZE,
    SnotelBatch,
    fetch_huc14_snotel_stations,
    fetch_snotel_daily_canonical,
)

logger = logging.getLogger(__name__)

RefreshMode = Literal["offline", "incremental", "full"]

INCREMENTAL_LOOKBACK = timedelta(days=60)
RECENTLY_FETCHED = timedelta(hours=12)
MANIFEST_NAME = "manifest.json"


class ManifestEntry(BaseModel):
    """What the cache knows about one series (the ``manifest.json`` schema)."""

    model_config = ConfigDict(frozen=True)

    series_id: str
    source: DataSource
    params: dict[str, str | int]
    unit: str | None
    first_date: date | None
    last_date: date | None
    row_count: int
    earliest_provisional_date: date | None
    fetched_at: datetime
    refresh_policy: RefreshPolicy


Manifest = dict[str, ManifestEntry]
_MANIFEST_ADAPTER = TypeAdapter(Manifest)


# --- Fetch plans -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Skip:
    reason: str


@dataclass(frozen=True, slots=True)
class FullFetch:
    pass


@dataclass(frozen=True, slots=True)
class WindowFetch:
    start: date


FetchPlan = Skip | FullFetch | WindowFetch


def plan_daily_refresh(
    series_id: str,
    entry: ManifestEntry | None,
    mode: RefreshMode,
    now: datetime,
) -> FetchPlan:
    """Decide what a daily series needs (design §5).

    ``incremental`` refetches from 60 days before the last cached date, or from
    the earliest provisional row if that is earlier, so revised values replace
    old ones. A series fetched in the last 12 hours is skipped.
    """
    match mode:
        case "offline":
            if entry is None:
                raise _cache_miss(series_id)
            return Skip("offline")
        case "full":
            return FullFetch()
        case "incremental":
            if entry is None or entry.last_date is None:
                return FullFetch()
            age = now - entry.fetched_at
            if age < RECENTLY_FETCHED:
                return Skip(f"fetched {age.total_seconds() / 3600:.1f} h ago")
            start = entry.last_date - INCREMENTAL_LOOKBACK
            if entry.earliest_provisional_date is not None:
                start = min(start, entry.earliest_provisional_date)
            return WindowFetch(start)


def plan_reference_refresh(
    series_id: str, entry: ManifestEntry | None, mode: RefreshMode
) -> FetchPlan:
    """Published files and reference tables: fetched once, replaced only on ``full``."""
    match mode:
        case "offline":
            if entry is None:
                raise _cache_miss(series_id)
            return Skip("offline")
        case "full":
            return FullFetch()
        case "incremental":
            return FullFetch() if entry is None else Skip("fetched once; use full")


def _cache_miss(series_id: str) -> CacheMissError:
    return CacheMissError(
        f"{series_id} is not in the cache. Run with REFRESH='incremental' "
        "(or scripts/build_cache.py) to fetch it."
    )


# --- Fetchers ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fetchers:
    """The network calls the cache makes, injectable so tests can stub them."""

    usgs: Callable[[UsgsDailySeries, DateRange], pd.DataFrame]
    rise: Callable[[RiseDailySeries, DateRange], pd.DataFrame]
    snotel: Callable[[Sequence[str], DateRange], SnotelBatch]
    snotel_stations: Callable[[], pd.DataFrame]
    published: Callable[[PublishedFile, Path], pd.DataFrame]
    outline: Callable[[BasinOutline], dict[str, Any]]


def live_fetchers(settings: Settings) -> Fetchers:
    """Fetchers that call the real APIs."""
    usgs = build_client(DataSource.USGS, settings)
    rise = build_client(DataSource.RISE, settings)
    snotel = build_client(DataSource.SNOTEL, settings)
    published = build_client(DataSource.PUBLISHED, settings)

    def fetch_published(spec: PublishedFile, downloads_dir: Path) -> pd.DataFrame:
        path = download_file(published, spec.url, downloads_dir)
        match spec.file_format:
            case PublishedFormat.NATURAL_FLOW_XLSX:
                return parse_natural_flow_xlsx(path)
            case PublishedFormat.MEKO_RECON_TXT:
                return parse_meko_recon_txt(path)

    return Fetchers(
        usgs=lambda spec, window: fetch_usgs_daily_canonical(
            usgs,
            spec.series_id,
            spec.monitoring_location_id,
            spec.parameter_code,
            window,
        ),
        rise=lambda spec, window: fetch_rise_daily_canonical(
            rise, spec.series_id, spec.item_id, spec.unit, window
        ),
        snotel=lambda triplets, window: fetch_snotel_daily_canonical(
            snotel, triplets, window
        ),
        snotel_stations=lambda: fetch_huc14_snotel_stations(snotel),
        published=fetch_published,
        outline=lambda spec: fetch_wbd_huc2_geojson(published, spec.huc2),
    )


# --- Paths and atomic I/O ------------------------------------------------------


def series_path(cache_dir: Path, spec: SeriesSpec) -> Path:
    """Return where a series' file lives in the cache."""
    match spec:
        case UsgsDailySeries() | RiseDailySeries() | SnotelDailySeries():
            return cache_dir / "raw" / spec.source / f"{spec.series_id}.parquet"
        case PublishedFile():
            return cache_dir / "published" / f"{spec.series_id}.parquet"
        case BasinOutline():
            return cache_dir / "reference" / f"{spec.series_id}.geojson"


def _reference_path(cache_dir: Path, series_id: str) -> Path:
    return cache_dir / "reference" / f"{series_id}.parquet"


def _write_atomic(path: Path, write: Callable[[Path], None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.tmp")
    try:
        write(partial)
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    """Write ``frame`` to parquet via a temp file, storing any ``date`` as date32."""
    if "date" in frame.columns:
        frame = frame.assign(date=frame["date"].dt.date)
    _write_atomic(path, lambda partial: frame.to_parquet(partial, index=False))


def _write_json_atomic(payload: Any, path: Path) -> None:
    def write(partial: Path) -> None:
        partial.write_text(json.dumps(payload))

    _write_atomic(path, write)


def read_manifest(cache_dir: Path) -> Manifest:
    """Return the manifest, or an empty one if the cache hasn't been built."""
    path = cache_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return _MANIFEST_ADAPTER.validate_json(path.read_bytes())


def write_manifest(cache_dir: Path, manifest: Manifest) -> None:
    """Atomically replace the manifest."""

    def write(partial: Path) -> None:
        ordered = dict(sorted(manifest.items()))
        partial.write_bytes(_MANIFEST_ADAPTER.dump_json(ordered, indent=2))

    _write_atomic(cache_dir / MANIFEST_NAME, write)


def _read_daily_file(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    return frame.assign(date=pd.to_datetime(frame["date"]).dt.as_unit("ns"))


# --- Loading -------------------------------------------------------------------


def _require(path: Path, series_id: str) -> Path:
    if not path.exists():
        raise _cache_miss(series_id)
    return path


def load_daily(
    cache_dir: Path, spec: UsgsDailySeries | RiseDailySeries | SnotelDailySeries
) -> pd.DataFrame:
    """Load one cached daily series in the canonical schema."""
    return _read_daily_file(_require(series_path(cache_dir, spec), spec.series_id))


def load_snotel_daily(
    cache_dir: Path, specs: Sequence[SnotelDailySeries]
) -> pd.DataFrame:
    """Load and stack several SNOTEL stations' daily SWE."""
    frames = [load_daily(cache_dir, spec) for spec in specs]
    return pd.concat(frames, ignore_index=True).astype({"series_id": "category"})


def load_annual(cache_dir: Path, spec: PublishedFile) -> pd.DataFrame:
    """Load a cached annual published series."""
    return pd.read_parquet(_require(series_path(cache_dir, spec), spec.series_id))


def load_outline(cache_dir: Path, spec: BasinOutline) -> dict[str, Any]:
    """Load a cached basin outline as a GeoJSON dict."""
    path = _require(series_path(cache_dir, spec), spec.series_id)
    outline: dict[str, Any] = json.loads(path.read_text())
    return outline


def load_snotel_stations(cache_dir: Path) -> pd.DataFrame:
    """Load the cached SNOTEL station reference table."""
    path = _reference_path(cache_dir, SNOTEL_STATIONS_SERIES_ID)
    return pd.read_parquet(_require(path, SNOTEL_STATIONS_SERIES_ID))


def load_snotel_medians(cache_dir: Path) -> pd.DataFrame:
    """Load the cached per-station 1991-2020 daily SWE medians."""
    path = _reference_path(cache_dir, SNOTEL_MEDIANS_SERIES_ID)
    return pd.read_parquet(_require(path, SNOTEL_MEDIANS_SERIES_ID))


# --- Merging -------------------------------------------------------------------


def upsert_on_date(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    """Merge newly fetched rows into a cached series; fetched rows win on ``date``."""
    merged = pd.concat([existing, fetched], ignore_index=True)
    return (
        merged.drop_duplicates("date", keep="last")
        .sort_values("date", ignore_index=True)
        .astype({"series_id": "category"})
    )


def _upsert_medians(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    keys = ["station_triplet", "month", "day"]
    merged = pd.concat([existing, fetched], ignore_index=True)
    return merged.drop_duplicates(keys, keep="last").sort_values(
        keys, ignore_index=True
    )


def _daily_entry(
    spec: UsgsDailySeries | RiseDailySeries | SnotelDailySeries,
    frame: pd.DataFrame,
    now: datetime,
) -> ManifestEntry:
    provisional = frame.loc[frame["approval"] == "provisional", "date"]
    return ManifestEntry(
        series_id=spec.series_id,
        source=spec.source,
        params=_params(spec),
        unit=spec.unit,
        first_date=frame["date"].min().date() if len(frame) else None,
        last_date=frame["date"].max().date() if len(frame) else None,
        row_count=len(frame),
        earliest_provisional_date=provisional.min().date()
        if len(provisional)
        else None,
        fetched_at=now,
        refresh_policy=spec.refresh_policy,
    )


def _reference_entry(
    series_id: str,
    params: dict[str, str | int],
    row_count: int,
    now: datetime,
    source: DataSource,
) -> ManifestEntry:
    return ManifestEntry(
        series_id=series_id,
        source=source,
        params=params,
        unit=None,
        first_date=None,
        last_date=None,
        row_count=row_count,
        earliest_provisional_date=None,
        fetched_at=now,
        refresh_policy="on_full_refresh",
    )


def _params(spec: SeriesSpec) -> dict[str, str | int]:
    match spec:
        case UsgsDailySeries():
            return {
                "monitoring_location_id": spec.monitoring_location_id,
                "parameter_code": spec.parameter_code,
            }
        case RiseDailySeries():
            return {"item_id": spec.item_id}
        case SnotelDailySeries():
            return {"station_triplet": spec.station_triplet}
        case PublishedFile():
            return {"url": spec.url}
        case BasinOutline():
            return {"huc2": spec.huc2}


# --- Refreshing ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefreshContext:
    """Where the cache lives, how to fetch, and the moment the refresh runs."""

    cache_dir: Path
    fetchers: Fetchers
    now: datetime

    @property
    def today(self) -> date:
        return self.now.date()

    def window(self, plan: FullFetch | WindowFetch) -> DateRange:
        start = FULL_HISTORY_START if isinstance(plan, FullFetch) else plan.start
        return DateRange(start=start, end=self.today)


def refresh_story(
    mode: RefreshMode,
    settings: Settings,
    *,
    fetchers: Fetchers | None = None,
    now: datetime | None = None,
) -> tuple[SeriesSpec, ...]:
    """Bring every story series up to date for ``mode`` and return the series list.

    The SNOTEL station table is refreshed first, since the fixed index station set
    (and so the list of SNOTEL series) is read from it.
    """
    context = RefreshContext(
        cache_dir=settings.cache_dir,
        fetchers=fetchers if fetchers is not None else live_fetchers(settings),
        now=now if now is not None else datetime.now(UTC),
    )
    _refresh_snotel_stations(context, mode)
    specs = story_series(load_snotel_stations(context.cache_dir))
    refresh_all(specs, mode, context)
    return specs


def refresh_all(
    specs: Sequence[SeriesSpec], mode: RefreshMode, context: RefreshContext
) -> None:
    """Refresh each series in turn, saving each one before starting the next."""
    snotel_specs: list[SnotelDailySeries] = []
    for spec in specs:
        match spec:
            case UsgsDailySeries() | RiseDailySeries():
                _refresh_daily(context, spec, mode)
            case SnotelDailySeries():
                snotel_specs.append(spec)
            case PublishedFile():
                _refresh_published(context, spec, mode)
            case BasinOutline():
                _refresh_outline(context, spec, mode)
    _refresh_snotel(context, snotel_specs, mode)


def _refresh_daily(
    context: RefreshContext,
    spec: UsgsDailySeries | RiseDailySeries,
    mode: RefreshMode,
) -> None:
    manifest = read_manifest(context.cache_dir)
    plan = plan_daily_refresh(
        spec.series_id, manifest.get(spec.series_id), mode, context.now
    )
    if isinstance(plan, Skip):
        logger.debug("%s: skipped (%s)", spec.series_id, plan.reason)
        return
    started = time.monotonic()
    window = context.window(plan)
    match spec:
        case UsgsDailySeries():
            fetched = context.fetchers.usgs(spec, window)
        case RiseDailySeries():
            fetched = context.fetchers.rise(spec, window)
    merged = _save_daily(context, spec, plan, fetched)
    logger.info(
        "%s: %s, %s rows fetched, %s total, %.0f s",
        spec.series_id,
        _describe(plan),
        f"{len(fetched):,}",
        f"{len(merged):,}",
        time.monotonic() - started,
    )


def _save_daily(
    context: RefreshContext,
    spec: UsgsDailySeries | RiseDailySeries | SnotelDailySeries,
    plan: FullFetch | WindowFetch,
    fetched: pd.DataFrame,
) -> pd.DataFrame:
    path = series_path(context.cache_dir, spec)
    if isinstance(plan, WindowFetch):
        merged = upsert_on_date(_read_daily_file(path), fetched)
    else:
        merged = fetched
    if merged.empty:
        raise UnexpectedSourceFormatError(f"{spec.series_id}: source returned no data")
    write_parquet_atomic(merged, path)
    manifest = read_manifest(context.cache_dir)
    write_manifest(
        context.cache_dir,
        {**manifest, spec.series_id: _daily_entry(spec, merged, context.now)},
    )
    return merged


def _refresh_snotel(
    context: RefreshContext, specs: Sequence[SnotelDailySeries], mode: RefreshMode
) -> None:
    manifest = read_manifest(context.cache_dir)
    plans = [
        (
            spec,
            plan_daily_refresh(
                spec.series_id, manifest.get(spec.series_id), mode, context.now
            ),
        )
        for spec in specs
    ]
    if mode == "offline":
        if specs:
            _require(
                _reference_path(context.cache_dir, SNOTEL_MEDIANS_SERIES_ID),
                SNOTEL_MEDIANS_SERIES_ID,
            )
        return
    to_fetch = [(spec, plan) for spec, plan in plans if not isinstance(plan, Skip)]
    for batch in batched(to_fetch, SNOTEL_BATCH_SIZE):
        started = time.monotonic()
        window = _batch_window(context, [plan for _, plan in batch])
        result = context.fetchers.snotel(
            [spec.station_triplet for spec, _ in batch], window
        )
        by_series = {
            str(series_id): rows
            for series_id, rows in result.daily_swe.groupby("series_id", observed=True)
        }
        for spec, plan in batch:
            fetched = by_series.get(spec.series_id, empty_canonical_frame())
            _save_daily(context, spec, plan, fetched)
        _save_medians(context, result.medians)
        logger.info(
            "SNOTEL: %d stations from %s, %s rows, %.0f s",
            len(batch),
            window.start.isoformat(),
            f"{len(result.daily_swe):,}",
            time.monotonic() - started,
        )


def _batch_window(
    context: RefreshContext, plans: Sequence[FullFetch | WindowFetch]
) -> DateRange:
    if any(isinstance(plan, FullFetch) for plan in plans):
        return context.window(FullFetch())
    return DateRange(
        start=min(plan.start for plan in plans if isinstance(plan, WindowFetch)),
        end=context.today,
    )


def _save_medians(context: RefreshContext, fetched: pd.DataFrame) -> None:
    path = _reference_path(context.cache_dir, SNOTEL_MEDIANS_SERIES_ID)
    existing = pd.read_parquet(path) if path.exists() else fetched.iloc[0:0]
    medians = _upsert_medians(existing, fetched)
    write_parquet_atomic(medians, path)
    manifest = read_manifest(context.cache_dir)
    entry = _reference_entry(
        SNOTEL_MEDIANS_SERIES_ID,
        {"centralTendencyType": "MEDIAN"},
        len(medians),
        context.now,
        DataSource.SNOTEL,
    )
    write_manifest(context.cache_dir, {**manifest, SNOTEL_MEDIANS_SERIES_ID: entry})


def _refresh_snotel_stations(context: RefreshContext, mode: RefreshMode) -> None:
    manifest = read_manifest(context.cache_dir)
    plan = plan_reference_refresh(
        SNOTEL_STATIONS_SERIES_ID, manifest.get(SNOTEL_STATIONS_SERIES_ID), mode
    )
    if isinstance(plan, Skip):
        return
    stations = context.fetchers.snotel_stations()
    write_parquet_atomic(
        stations, _reference_path(context.cache_dir, SNOTEL_STATIONS_SERIES_ID)
    )
    entry = _reference_entry(
        SNOTEL_STATIONS_SERIES_ID,
        {"hucs": "14*", "stationTriplets": "*:*:SNTL"},
        len(stations),
        context.now,
        DataSource.SNOTEL,
    )
    write_manifest(context.cache_dir, {**manifest, SNOTEL_STATIONS_SERIES_ID: entry})
    logger.info(
        "%s: %d stations, %d in the index",
        SNOTEL_STATIONS_SERIES_ID,
        len(stations),
        int(stations["in_index"].sum()),
    )


def _refresh_published(
    context: RefreshContext, spec: PublishedFile, mode: RefreshMode
) -> None:
    manifest = read_manifest(context.cache_dir)
    plan = plan_reference_refresh(spec.series_id, manifest.get(spec.series_id), mode)
    if isinstance(plan, Skip):
        return
    downloads = context.cache_dir / "published" / "downloads"
    annual = context.fetchers.published(spec, downloads)
    write_parquet_atomic(annual, series_path(context.cache_dir, spec))
    entry = _reference_entry(
        spec.series_id, _params(spec), len(annual), context.now, spec.source
    )
    write_manifest(context.cache_dir, {**manifest, spec.series_id: entry})
    logger.info("%s: %d years", spec.series_id, len(annual))


def _refresh_outline(
    context: RefreshContext, spec: BasinOutline, mode: RefreshMode
) -> None:
    manifest = read_manifest(context.cache_dir)
    plan = plan_reference_refresh(spec.series_id, manifest.get(spec.series_id), mode)
    if isinstance(plan, Skip):
        return
    _write_json_atomic(
        context.fetchers.outline(spec), series_path(context.cache_dir, spec)
    )
    entry = _reference_entry(spec.series_id, _params(spec), 1, context.now, spec.source)
    write_manifest(context.cache_dir, {**manifest, spec.series_id: entry})
    logger.info("%s: saved outline", spec.series_id)


def _describe(plan: FullFetch | WindowFetch) -> str:
    match plan:
        case FullFetch():
            return "full history"
        case WindowFetch():
            return f"from {plan.start.isoformat()}"
