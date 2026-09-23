from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from colorado_river_viz import snotel
from colorado_river_viz.constants import SNOTEL_INDEX_RECORD_START
from colorado_river_viz.data_sources import DateRange
from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.settings import Settings
from colorado_river_viz.snotel import (
    daily_median_table,
    fetch_snotel_daily_canonical,
    index_station_triplets,
    parse_snotel_data,
    parse_stations,
    snotel_series_id,
)
from tests.conftest import ScriptedResponse, ScriptedServer


def _station(
    triplet: str, daily_begin: str | None, network: str = "SNTL"
) -> dict[str, Any]:
    elements = [
        {"elementCode": "WTEQ", "durationName": "MONTHLY", "beginDate": "1850-01-01"}
    ]
    if daily_begin is not None:
        elements.append(
            {
                "elementCode": "WTEQ",
                "durationName": "DAILY",
                "beginDate": f"{daily_begin} 00:00",
            }
        )
    return {
        "stationTriplet": triplet,
        "networkCode": network,
        "name": triplet.split(":")[0],
        "huc": "140100010101",
        "elevation": 10_000.0,
        "latitude": 39.5,
        "longitude": -106.0,
        "stationElements": elements,
    }


STATIONS_PAYLOAD = [
    _station("335:CO:SNTL", "1978-10-01"),
    _station("713:CO:SNTL", "1980-10-01"),  # exactly on the cutoff
    _station("1344:CO:SNTL", "2025-09-25"),
    _station("999:UT:SNTL", None),
    _station("05K12:CO:SNOW", None, network="SNOW"),
]


def test_parse_stations_flags_long_record_stations_for_the_index() -> None:
    stations = parse_stations(STATIONS_PAYLOAD, SNOTEL_INDEX_RECORD_START)

    flags = dict(zip(stations["station_triplet"], stations["in_index"], strict=True))
    assert flags == {
        "1344:CO:SNTL": False,
        "335:CO:SNTL": True,
        "713:CO:SNTL": True,
        "999:UT:SNTL": False,
    }
    assert index_station_triplets(stations) == ["335:CO:SNTL", "713:CO:SNTL"]


def test_parse_stations_drops_snow_courses_and_fills_reference_columns() -> None:
    stations = parse_stations(STATIONS_PAYLOAD, SNOTEL_INDEX_RECORD_START)

    assert "05K12:CO:SNOW" not in set(stations["station_triplet"])
    assert tuple(stations.columns) == snotel.STATION_COLUMNS
    assert set(stations["huc4"]) == {"1401"}


def _data_station(
    triplet: str, values: list[tuple[str, float | None, float]], unit: str = "in"
) -> dict[str, Any]:
    return {
        "stationTriplet": triplet,
        "data": [
            {
                "stationElement": {"elementCode": "WTEQ", "storedUnitCode": unit},
                "values": [
                    {"date": day, "median": median}
                    | ({} if value is None else {"value": value})
                    for day, value, median in values
                ],
            }
        ],
    }


def test_batched_fetch_splits_stations_across_requests_and_series(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snotel, "AWDB_DATA_URL", f"{scripted_server.base_url}/data")
    scripted_server.script = [
        ScriptedResponse(
            body=[
                _data_station("1:CO:SNTL", [("2026-01-01", 5.0, 6.0)]),
                _data_station("2:CO:SNTL", [("2026-01-01", 7.0, 8.0)]),
            ]
        ),
        ScriptedResponse(body=[_data_station("3:UT:SNTL", [("2026-01-01", 9.0, 9.5)])]),
    ]

    batch = fetch_snotel_daily_canonical(
        build_client(DataSource.SNOTEL, fast_settings),
        ["1:CO:SNTL", "2:CO:SNTL", "3:UT:SNTL"],
        DateRange(date(2026, 1, 1), date(2026, 1, 1)),
        batch_size=2,
    )

    requested = [
        parse_qs(urlparse(request.path).query)["stationTriplets"]
        for request in scripted_server.received
    ]
    assert requested == [["1:CO:SNTL,2:CO:SNTL"], ["3:UT:SNTL"]]
    by_series = batch.daily_swe.set_index("series_id")["value"].to_dict()
    assert by_series == {
        "1_CO_SNTL__WTEQ": 5.0,
        "2_CO_SNTL__WTEQ": 7.0,
        "3_UT_SNTL__WTEQ": 9.0,
    }
    assert batch.medians["median_swe_in"].tolist() == [6.0, 8.0, 9.5]


def test_missing_values_are_dropped_but_their_medians_kept() -> None:
    batch = parse_snotel_data(
        [
            _data_station(
                "1:CO:SNTL",
                [("2026-01-01", 5.0, 6.0), ("2026-01-02", None, 6.1)],
            )
        ]
    )
    assert len(batch.daily_swe) == 1
    assert batch.medians["median_swe_in"].tolist() == [6.0, 6.1]


def test_rejects_swe_in_unexpected_units() -> None:
    with pytest.raises(UnexpectedSourceFormatError):
        parse_snotel_data(
            [_data_station("1:CO:SNTL", [("2026-01-01", 5.0, 6.0)], unit="mm")]
        )


def test_feb29_median_falls_back_to_feb28_only_when_missing() -> None:
    frames = [
        pd.DataFrame(
            {
                "station_triplet": ["no_leap", "no_leap", "leap", "leap", "leap"],
                "month": [2, 3, 2, 2, 3],
                "day": [28, 1, 28, 29, 1],
                "median_swe_in": [10.0, 10.5, 20.0, 20.2, 20.4],
            }
        )
    ]
    medians = daily_median_table(frames).set_index(["station_triplet", "month", "day"])[
        "median_swe_in"
    ]

    assert medians[("no_leap", 2, 29)] == 10.0
    assert medians[("leap", 2, 29)] == 20.2
    assert len(medians) == 6


def test_series_id_replaces_colons() -> None:
    assert snotel_series_id("335:CO:SNTL") == "335_CO_SNTL__WTEQ"
