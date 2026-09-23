from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from colorado_river_viz import data_sources
from colorado_river_viz.data_sources import (
    DateRange,
    fetch_rise_daily_canonical,
    fetch_rise_time_series,
)
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.settings import Settings
from tests.conftest import ScriptedResponse, ScriptedServer

FIVE_DAYS = DateRange(date(2026, 1, 1), date(2026, 1, 5))
PAGE_SIZE = 2


def _page(stamps_and_values: list[tuple[str, float]], total: int) -> dict[str, Any]:
    return {
        "meta": {"totalItems": total, "itemsPerPage": PAGE_SIZE},
        "data": [
            {"attributes": {"dateTime": stamp, "result": value, "itemId": 512}}
            for stamp, value in stamps_and_values
        ],
    }


PAGES = [
    _page([("2026-01-01T07:00:00+00:00", 1.0), ("2026-01-02T07:00:00+00:00", 2.0)], 5),
    _page([("2026-01-03T07:00:00+00:00", 3.0), ("2026-01-04T07:00:00+00:00", 4.0)], 5),
    _page([("2026-01-05T07:00:00+00:00", 5.0)], 5),
]


@pytest.fixture
def rise_on_server(
    scripted_server: ScriptedServer, monkeypatch: pytest.MonkeyPatch
) -> ScriptedServer:
    monkeypatch.setattr(
        data_sources, "RISE_RESULT_URL", f"{scripted_server.base_url}/result"
    )
    monkeypatch.setattr(data_sources, "RISE_PAGE_SIZE", PAGE_SIZE)
    monkeypatch.setenv("CRV_RETRY_BACKOFF_FACTOR", "0")
    scripted_server.script = [ScriptedResponse(body=page) for page in PAGES]
    return scripted_server


def _query(server: ScriptedServer, request_index: int) -> dict[str, list[str]]:
    return parse_qs(urlparse(server.received[request_index].path).query)


def test_walks_every_page(rise_on_server: ScriptedServer) -> None:
    frame = fetch_rise_time_series(512, FIVE_DAYS)

    assert frame["result"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [_query(rise_on_server, i)["page"] for i in range(3)] == [
        ["1"],
        ["2"],
        ["3"],
    ]


def test_requests_ascending_order_and_an_inclusive_end_date(
    rise_on_server: ScriptedServer,
) -> None:
    fetch_rise_time_series(512, FIVE_DAYS)

    query = _query(rise_on_server, 0)
    assert query["order[dateTime]"] == ["ASC"]
    assert query["dateTime[after]"] == ["2026-01-01"]
    assert query["dateTime[before]"] == ["2026-01-06"]


def test_recovers_when_one_page_times_out_once(
    rise_on_server: ScriptedServer,
) -> None:
    settings = Settings(
        request_timeout_seconds=0.3, max_retries=2, retry_backoff_factor=0.0
    )
    rise_on_server.script = [
        ScriptedResponse(body=PAGES[0]),
        ScriptedResponse(body=PAGES[1], delay_seconds=1.0),
        ScriptedResponse(body=PAGES[1]),
        ScriptedResponse(body=PAGES[2]),
    ]
    client = build_client(DataSource.RISE, settings)

    frame = fetch_rise_daily_canonical(client, "rise-0512", 512, "cfs", FIVE_DAYS)

    assert frame["value"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [_query(rise_on_server, i)["page"] for i in range(4)] == [
        ["1"],
        ["2"],
        ["2"],
        ["3"],
    ]


def test_legacy_fetch_keeps_its_return_shape(rise_on_server: ScriptedServer) -> None:
    frame = fetch_rise_time_series(512, FIVE_DAYS)

    assert frame.index.name == "dateTime"
    assert str(frame.index.dtype).startswith("datetime64")
    assert pd.DatetimeIndex(frame.index).tz is not None
    assert list(frame.columns) == ["result"]
    assert frame.index.is_monotonic_increasing


@pytest.mark.parametrize(
    ("stamp", "local_date"),
    [
        ("2026-01-01T07:00:00+00:00", "2026-01-01"),  # midnight in Arizona
        ("2026-07-01T07:00:00+00:00", "2026-07-01"),  # no daylight saving shift
        ("2026-01-02T06:59:00+00:00", "2026-01-01"),  # still the previous local day
    ],
)
def test_canonical_dates_are_arizona_local_dates(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    stamp: str,
    local_date: str,
) -> None:
    monkeypatch.setattr(
        data_sources, "RISE_RESULT_URL", f"{scripted_server.base_url}/result"
    )
    scripted_server.script = [ScriptedResponse(body=_page([(stamp, 9.0)], 1))]

    frame = fetch_rise_daily_canonical(
        build_client(DataSource.RISE, fast_settings), "rise-0512", 512, "cfs", FIVE_DAYS
    )

    assert frame["date"].tolist() == [pd.Timestamp(local_date)]
    assert frame["approval"].tolist() == ["unknown"]
    assert frame["unit"].tolist() == ["cfs"]
