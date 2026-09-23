from __future__ import annotations

import pandas as pd
import pytest

from colorado_river_viz.charts.map import build_basin_map
from colorado_river_viz.story_tables import BasinMapLayers

_EMPTY_GEOJSON = {"type": "FeatureCollection", "features": []}

_SQUARE_BASIN = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.0, 35.0],
                        [-108.0, 35.0],
                        [-108.0, 40.0],
                        [-112.0, 40.0],
                        [-112.0, 35.0],
                    ]
                ],
            },
        }
    ],
}

_RIVER_TRACE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[-110.0, 37.0], [-109.5, 36.5]],
            },
        }
    ],
}


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
        basins={"14": _SQUARE_BASIN, "15": _EMPTY_GEOJSON},
        river=_RIVER_TRACE,
    )


def test_build_basin_map_has_a_trace_per_station_group_and_site_kind() -> None:
    fig = build_basin_map(_layers(n_index=3, n_other=5))

    # Each of the 4 marker groups (non-index stations, index stations, gauges,
    # reservoirs) draws a halo trace beneath its own colored marker trace.
    assert len(fig.data) == 8


def test_build_basin_map_index_marker_count_matches_in_index_stations() -> None:
    fig = build_basin_map(_layers(n_index=3, n_other=5))

    index_trace = next(t for t in fig.data if t.name == "Snow index station")
    assert len(index_trace.lat) == 3


def test_build_basin_map_marker_traces_have_a_larger_halo_trace_beneath_them() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    index_trace = next(t for t in fig.data if t.name == "Snow index station")
    index_position = list(fig.data).index(index_trace)
    halo_trace = fig.data[index_position - 1]
    assert halo_trace.showlegend is False
    assert halo_trace.marker.size > index_trace.marker.size


def test_build_basin_map_draws_two_basin_fill_layers_and_a_river_line() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert len(fig.layout.map.layers) == 3
    assert [layer.type for layer in fig.layout.map.layers] == ["fill", "fill", "line"]


def test_build_basin_map_layers_sit_below_the_markers() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert all(layer.below == "traces" for layer in fig.layout.map.layers)


def test_build_basin_map_legend_sits_in_the_lower_right_corner() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert fig.layout.legend.xanchor == "right"
    assert fig.layout.legend.yanchor == "bottom"
    assert fig.layout.legend.x > 0.5
    assert fig.layout.legend.y < 0.5


def test_build_basin_map_default_view_fits_the_basin_bounds() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert fig.layout.map.center.lat == pytest.approx(37.5)
    assert fig.layout.map.center.lon == pytest.approx(-110.0)
    assert fig.layout.map.zoom > 0


def test_build_basin_map_gauge_and_reservoir_use_colorable_circle_markers() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    gauge_trace = next(t for t in fig.data if t.name == "Stream gauge")
    reservoir_trace = next(t for t in fig.data if t.name == "Reservoir")
    assert gauge_trace.marker.symbol == "circle"
    assert reservoir_trace.marker.symbol == "circle"
    assert gauge_trace.marker.color != reservoir_trace.marker.color


def test_build_basin_map_smoke_test() -> None:
    fig = build_basin_map(_layers(n_index=1, n_other=1))

    assert fig.layout.title.text
    assert fig.to_json()
