from __future__ import annotations

import pandas as pd

from colorado_river_viz.charts.map import build_basin_map
from colorado_river_viz.story_tables import BasinMapLayers

_EMPTY_GEOJSON = {"type": "FeatureCollection", "features": []}


def _layers(n_index: int, n_other: int) -> BasinMapLayers:
    stations = pd.DataFrame(
        {
            "name": [f"S{i}" for i in range(n_index + n_other)],
            "latitude": [40.0] * (n_index + n_other),
            "longitude": [-108.0] * (n_index + n_other),
            "in_index": [True] * n_index + [False] * n_other,
        }
    )
    sites = pd.DataFrame(
        [
            {
                "name": "Cisco",
                "kind": "gauge",
                "latitude": 38.8,
                "longitude": -109.5,
                "description": "USGS 09180500",
            },
            {
                "name": "Lees Ferry",
                "kind": "gauge",
                "latitude": 36.9,
                "longitude": -111.6,
                "description": "USGS 09380000",
            },
            {
                "name": "Lake Powell",
                "kind": "reservoir",
                "latitude": 36.9,
                "longitude": -111.5,
                "description": "Glen Canyon Dam",
            },
            {
                "name": "Lake Mead",
                "kind": "reservoir",
                "latitude": 36.0,
                "longitude": -114.7,
                "description": "Hoover Dam",
            },
        ]
    )
    return BasinMapLayers(
        stations=stations,
        sites=sites,
        basins={"14": _EMPTY_GEOJSON, "15": _EMPTY_GEOJSON},
    )


def test_build_basin_map_has_a_trace_per_station_group_and_site_kind() -> None:
    fig = build_basin_map(_layers(n_index=3, n_other=5))

    assert len(fig.data) == 4  # non-index stations, index stations, gauges, reservoirs


def test_build_basin_map_index_marker_count_matches_in_index_stations() -> None:
    fig = build_basin_map(_layers(n_index=3, n_other=5))

    index_trace = next(t for t in fig.data if t.name == "Snow index station")
    assert len(index_trace.lat) == 3


def test_build_basin_map_draws_two_basin_fill_layers() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert len(fig.layout.map.layers) == 2


def test_build_basin_map_smoke_test() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert fig.layout.title.text
    assert fig.to_json()
