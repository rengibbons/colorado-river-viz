"""Live checks against the real APIs. Excluded by default; run `pytest -m network`."""

from datetime import date

import pytest

from colorado_river_viz.data_sources import DateRange, fetch_usgs_daily_canonical
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.settings import Settings

pytestmark = pytest.mark.network


def test_usgs_returns_lees_ferry_record_from_its_first_day() -> None:
    frame = fetch_usgs_daily_canonical(
        build_client(DataSource.USGS, Settings()),
        "USGS-09380000__00060",
        "USGS-09380000",
        "00060",
        DateRange(date(1921, 1, 1), date(1922, 9, 30)),
    )
    assert frame["date"].iloc[0].date() == date(1921, 10, 1)
    assert len(frame) == 365
    assert set(frame["approval"]) == {"approved"}
