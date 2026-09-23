from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from colorado_river_viz import data_sources
from colorado_river_viz.data_sources import (
    DateRange,
    fetch_usgs_daily_canonical,
    fetch_usgs_daily_values,
)
from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.settings import Settings
from tests.conftest import ScriptedResponse, ScriptedServer

WY2026_FIRST_WEEK = DateRange(date(2025, 10, 1), date(2025, 10, 7))


def _feature(
    day: str,
    value: str | None,
    approval: str = "Approved",
    unit: str = "ft^3/s",
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "time": day,
            "value": value,
            "approval_status": approval,
            "unit_of_measure": unit,
        },
        "geometry": None,
    }


def _page(features: list[dict[str, Any]], next_href: str | None) -> dict[str, Any]:
    links = [{"rel": "self", "href": "ignored"}]
    if next_href is not None:
        links.append({"rel": "next", "href": next_href})
    return {"type": "FeatureCollection", "features": features, "links": links}


@pytest.fixture
def two_page_server(scripted_server: ScriptedServer) -> ScriptedServer:
    base = scripted_server.base_url
    scripted_server.script = [
        ScriptedResponse(
            body=_page(
                [
                    _feature("2025-10-03", "300"),
                    _feature("2025-10-01", "100"),
                    _feature("2025-10-02", "200"),
                ],
                next_href=f"{base}/items?offset=3&cursor=abc",
            )
        ),
        ScriptedResponse(
            body=_page(
                [
                    _feature("2025-10-05", "500", approval="Provisional"),
                    _feature("2025-10-04", None, approval="Provisional"),
                ],
                next_href=None,
            )
        ),
    ]
    return scripted_server


@pytest.fixture
def usgs_url_on_server(
    two_page_server: ScriptedServer, monkeypatch: pytest.MonkeyPatch
) -> ScriptedServer:
    monkeypatch.setattr(
        data_sources, "USGS_DAILY_VALUES_URL", f"{two_page_server.base_url}/items"
    )
    monkeypatch.setenv("CRV_RETRY_BACKOFF_FACTOR", "0")
    return two_page_server


def test_follows_next_links_until_none_remain(
    usgs_url_on_server: ScriptedServer,
) -> None:
    fetch_usgs_daily_values("USGS-09380000", "00060", WY2026_FIRST_WEEK)

    paths = [request.path for request in usgs_url_on_server.received]
    assert len(paths) == 2
    assert paths[1] == "/items?offset=3&cursor=abc"


def test_first_request_asks_for_sorted_daily_means(
    usgs_url_on_server: ScriptedServer,
) -> None:
    fetch_usgs_daily_values("USGS-09380000", "00060", WY2026_FIRST_WEEK)

    query = parse_qs(urlparse(usgs_url_on_server.received[0].path).query)
    assert query["sortby"] == ["time"]
    assert query["statistic_id"] == ["00003"]
    assert query["skipGeometry"] == ["true"]
    assert query["datetime"] == ["2025-10-01/2025-10-07"]


def test_legacy_fetch_keeps_its_return_shape_and_sorts(
    usgs_url_on_server: ScriptedServer,
) -> None:
    frame = fetch_usgs_daily_values("USGS-09380000", "00060", WY2026_FIRST_WEEK)

    assert frame.index.name == "time"
    assert pd.api.types.is_datetime64_any_dtype(frame.index)
    assert list(frame.columns) == ["value", "unit_of_measure"]
    assert frame.index.is_monotonic_increasing
    assert frame["value"].iloc[:3].tolist() == [100.0, 200.0, 300.0]


def test_canonical_fetch_maps_units_approval_and_drops_missing_values(
    two_page_server: ScriptedServer, fast_settings: Settings
) -> None:
    client = build_client(DataSource.USGS, fast_settings)
    url = f"{two_page_server.base_url}/items"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(data_sources, "USGS_DAILY_VALUES_URL", url)
        frame = fetch_usgs_daily_canonical(
            client, "USGS-09380000__00060", "USGS-09380000", "00060", WY2026_FIRST_WEEK
        )

    assert list(frame.columns) == ["series_id", "date", "value", "unit", "approval"]
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-10-01",
        "2025-10-02",
        "2025-10-03",
        "2025-10-05",
    ]
    assert frame["approval"].tolist() == [
        "approved",
        "approved",
        "approved",
        "provisional",
    ]
    assert set(frame["unit"]) == {"cfs"}
    assert set(frame["series_id"]) == {"USGS-09380000__00060"}


def test_canonical_fetch_returns_empty_frame_when_no_rows(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_server.script = [ScriptedResponse(body=_page([], next_href=None))]
    monkeypatch.setattr(
        data_sources, "USGS_DAILY_VALUES_URL", f"{scripted_server.base_url}/items"
    )
    frame = fetch_usgs_daily_canonical(
        build_client(DataSource.USGS, fast_settings),
        "USGS-09380000__00060",
        "USGS-09380000",
        "00060",
        WY2026_FIRST_WEEK,
    )
    assert frame.empty
    assert list(frame.columns) == ["series_id", "date", "value", "unit", "approval"]


def test_canonical_fetch_rejects_unexpected_units(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_server.script = [
        ScriptedResponse(
            body=_page([_feature("2025-10-01", "3", unit="m^3/s")], next_href=None)
        )
    ]
    monkeypatch.setattr(
        data_sources, "USGS_DAILY_VALUES_URL", f"{scripted_server.base_url}/items"
    )
    with pytest.raises(UnexpectedSourceFormatError):
        fetch_usgs_daily_canonical(
            build_client(DataSource.USGS, fast_settings),
            "USGS-09380000__00060",
            "USGS-09380000",
            "00060",
            WY2026_FIRST_WEEK,
        )
