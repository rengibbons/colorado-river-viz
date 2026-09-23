from datetime import date

import pandas as pd

from colorado_river_viz.catalog import (
    FIXED_SERIES,
    SnotelDailySeries,
    story_series,
)
from colorado_river_viz.snotel import select_index_stations


def _stations() -> pd.DataFrame:
    stations = pd.DataFrame(
        {
            "station_triplet": ["335:CO:SNTL", "713:CO:SNTL", "1344:CO:SNTL"],
            "daily_swe_begin_date": pd.to_datetime(
                ["1978-10-01", "1979-10-01", "2025-09-25"]
            ),
        }
    )
    return stations.assign(in_index=select_index_stations(stations, date(1980, 10, 1)))


def test_fixed_series_ids_are_stable() -> None:
    assert [spec.series_id for spec in FIXED_SERIES] == [
        "USGS-09180500__00060",
        "USGS-09380000__00060",
        "rise-0508",
        "rise-0509",
        "rise-0512",
        "rise-6123",
        "rise-6124",
        "lees_ferry_natural_flow_wy",
        "meko_2007_lees_ferry_recon",
        "wbd_huc2_14",
        "wbd_huc2_15",
        "colorado_river_mainstem",
    ]


def test_story_series_adds_one_spec_per_index_station() -> None:
    specs = story_series(_stations())

    snotel = [spec for spec in specs if isinstance(spec, SnotelDailySeries)]
    assert [spec.series_id for spec in snotel] == [
        "335_CO_SNTL__WTEQ",
        "713_CO_SNTL__WTEQ",
    ]


def test_series_ids_are_unique() -> None:
    ids = [spec.series_id for spec in story_series(_stations())]
    assert len(ids) == len(set(ids))
