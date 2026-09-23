"""The 'meet the river' map: basin outlines, a river trace, SNOTEL stations,
gauges, and reservoirs (design §7)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import (
    PALETTES,
    RESERVOIR_COLOR,
    RIVER_COLOR,
    Palette,
    Theme,
    hex_to_rgba,
    layout_template,
)
from colorado_river_viz.story_tables import BasinMapLayers

DEFAULT_TITLE = "Meet the river"
MAP_STYLE = "open-street-map"
MAP_HEIGHT_PX = 640
_MAP_MARGIN = {"t": 48, "b": 0, "l": 0, "r": 0}

# The viewport the default zoom is fit to -- matches the story export's own
# figure width cap (``export_web.FIGURE_MAX_WIDTH_PX``) and this module's own
# ``MAP_HEIGHT_PX``, minus the title margin above, which isn't map area.
_VIEWPORT_WIDTH_PX = 670.0 - _MAP_MARGIN["l"] - _MAP_MARGIN["r"]
_VIEWPORT_HEIGHT_PX = MAP_HEIGHT_PX - _MAP_MARGIN["t"] - _MAP_MARGIN["b"]
_VIEWPORT_PADDING = 0.1  # fraction of the viewport left as margin around the bounds

# MapLibre/Mapbox (which Plotly's "map" trace renders through) tiles the world
# at 512px per tile at zoom 0, not the classic 256px Google Maps convention --
# using 256 here under-covers the viewport by one zoom level.
_WORLD_PX = 512.0
_MAX_ZOOM = 12.0

# SNOTEL station marker sizes and halo width (Seaborn-style edge).
_STATION_MARKER_SIZE = 6
_INDEX_MARKER_SIZE = 14
_SITE_MARKER_SIZE = 14
_HALO_WIDTH = 4


def build_basin_map(
    layers: BasinMapLayers, theme: Theme = "light", title: str = DEFAULT_TITLE
) -> go.Figure:
    """The opening map: faint basin outlines, a river trace, SNOTEL stations
    (filled if in the fixed snow index, hollow otherwise), and labeled
    gauge/reservoir markers.

    ``layers`` is ``story_tables.basin_map_layers()``'s output.
    """
    palette = PALETTES[theme]
    fig = go.Figure()

    in_index = layers.stations.loc[layers.stations["in_index"]]
    not_in_index = layers.stations.loc[~layers.stations["in_index"]]
    _add_halo(fig, not_in_index["latitude"], not_in_index["longitude"], palette)
    fig.add_trace(
        go.Scattermap(
            lat=not_in_index["latitude"],
            lon=not_in_index["longitude"],
            mode="markers",
            marker={"size": _STATION_MARKER_SIZE, "color": palette.surface},
            name="SNOTEL station",
            text=not_in_index["name"],
            hovertemplate="%{text}<extra>SNOTEL station</extra>",
        )
    )
    _add_halo(
        fig,
        in_index["latitude"],
        in_index["longitude"],
        palette,
        size=_INDEX_MARKER_SIZE,
    )
    fig.add_trace(
        go.Scattermap(
            lat=in_index["latitude"],
            lon=in_index["longitude"],
            mode="markers",
            marker={"size": _INDEX_MARKER_SIZE, "color": palette.high},
            name="Snow index station",
            text=in_index["name"],
            hovertemplate="%{text}<extra>Snow index station</extra>",
        )
    )

    # Scattermap only honors marker.color for the "circle" symbol (other maki
    # icons, e.g. "square", ignore it and render black) -- gauge and reservoir
    # are distinguished by color instead of shape (decision 0029).
    for kind, label, color in (
        ("gauge", "Stream gauge", palette.low),
        ("reservoir", "Reservoir", RESERVOIR_COLOR[theme]),
    ):
        rows = layers.sites.loc[layers.sites["kind"] == kind]
        _add_halo(
            fig, rows["latitude"], rows["longitude"], palette, size=_SITE_MARKER_SIZE
        )
        fig.add_trace(
            go.Scattermap(
                lat=rows["latitude"],
                lon=rows["longitude"],
                mode="markers+text",
                marker={"size": _SITE_MARKER_SIZE, "symbol": "circle", "color": color},
                text=rows["name"],
                textposition="top right",
                name=label,
                customdata=rows["description"],
                hovertemplate="%{text}<br>%{customdata}<extra></extra>",
            )
        )

    map_layers = [
        {
            "source": layers.basins["14"],
            "type": "fill",
            "color": palette.baseline,
            "opacity": 0.55,
            "below": "traces",
        },
        {
            "source": layers.basins["15"],
            "type": "fill",
            "color": palette.baseline,
            "opacity": 0.35,
            "below": "traces",
        },
        {
            "source": layers.river,
            "type": "line",
            "color": RIVER_COLOR[theme],
            "line": {"width": 2},
            "opacity": 0.85,
            "below": "traces",
        },
    ]
    center, zoom = _fit_view(layers.basins["14"], layers.basins["15"])
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        height=MAP_HEIGHT_PX,
        margin=_MAP_MARGIN,
        map={
            "style": MAP_STYLE,
            "center": center,
            "zoom": zoom,
            "layers": map_layers,
        },
        legend={
            "x": 0.98,
            "y": 0.02,
            "xanchor": "right",
            "yanchor": "bottom",
            "bgcolor": hex_to_rgba(palette.surface, 0.85),
            "bordercolor": palette.gridline,
            "borderwidth": 1,
        },
    )
    return fig


def _add_halo(
    fig: go.Figure,
    lat: pd.Series[float],
    lon: pd.Series[float],
    palette: Palette,
    size: int = _STATION_MARKER_SIZE,
) -> None:
    """Draw a surface-colored ring under a marker group, Seaborn-style edge."""
    fig.add_trace(
        go.Scattermap(
            lat=lat,
            lon=lon,
            mode="markers",
            marker={"size": size + _HALO_WIDTH, "color": palette.surface},
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _coordinates(geometry: dict[str, Any]) -> Iterator[tuple[float, float]]:
    """Yield every ``(lon, lat)`` vertex of a Polygon/MultiPolygon/LineString."""
    coordinates = geometry["coordinates"]
    match geometry["type"]:
        case "Polygon":
            for ring in coordinates:
                yield from ((lon, lat) for lon, lat, *_ in ring)
        case "MultiPolygon":
            for polygon in coordinates:
                for ring in polygon:
                    yield from ((lon, lat) for lon, lat, *_ in ring)
        case "LineString":
            yield from ((lon, lat) for lon, lat, *_ in coordinates)
        case other:
            raise ValueError(f"unsupported geometry type: {other}")


def _bbox(*feature_collections: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return ``(min_lon, min_lat, max_lon, max_lat)`` across GeoJSON collections."""
    lons: list[float] = []
    lats: list[float] = []
    for collection in feature_collections:
        for feature in collection["features"]:
            for lon, lat in _coordinates(feature["geometry"]):
                lons.append(lon)
                lats.append(lat)
    return min(lons), min(lats), max(lons), max(lats)


def _lat_to_mercator_fraction(lat_deg: float) -> float:
    """Web Mercator's y-fraction of a latitude."""
    sin_lat = math.sin(math.radians(lat_deg))
    return math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)


def _zoom_for_span(viewport_px: float, world_px: float, fraction: float) -> float:
    return math.log2(viewport_px / world_px / fraction)


def _fit_view(*feature_collections: dict[str, Any]) -> tuple[dict[str, float], float]:
    """Return a ``(center, zoom)`` that fits the given GeoJSON collections'
    combined bounding box inside the map's viewport, with padding.

    Standard Mercator zoom-to-bounds arithmetic (the same formula behind most
    "fit map to markers" implementations): each axis gets the zoom level that
    would just fit its span, and the tighter of the two wins.
    """
    min_lon, min_lat, max_lon, max_lat = _bbox(*feature_collections)
    center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}

    padded_width = _VIEWPORT_WIDTH_PX * (1 - _VIEWPORT_PADDING)
    padded_height = _VIEWPORT_HEIGHT_PX * (1 - _VIEWPORT_PADDING)

    lat_fraction = _lat_to_mercator_fraction(max_lat) - _lat_to_mercator_fraction(
        min_lat
    )
    lon_span = max_lon - min_lon
    lon_fraction = (lon_span if lon_span > 0 else lon_span + 360) / 360

    lat_zoom = _zoom_for_span(padded_height, _WORLD_PX, abs(lat_fraction))
    lon_zoom = _zoom_for_span(padded_width, _WORLD_PX, lon_fraction)
    zoom = min(lat_zoom, lon_zoom, _MAX_ZOOM)
    return center, zoom
