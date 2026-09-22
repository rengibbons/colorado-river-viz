"""The 'meet the river' map: basin outlines, SNOTEL stations, gauges, and
reservoirs (design §7)."""

from __future__ import annotations

import plotly.graph_objects as go

from colorado_river_viz.charts.theme import PALETTES, Theme, layout_template
from colorado_river_viz.story_tables import BasinMapLayers

DEFAULT_TITLE = "Meet the river"
MAP_STYLE = "open-street-map"
DEFAULT_ZOOM = 5.4
DEFAULT_CENTER = {"lat": 37.5, "lon": -111.0}

_SITE_SYMBOLS = {"gauge": "circle", "reservoir": "square"}


def build_basin_map(
    layers: BasinMapLayers, theme: Theme = "light", title: str = DEFAULT_TITLE
) -> go.Figure:
    """The opening map: faint basin outlines, SNOTEL stations (filled if in the
    fixed snow index, hollow otherwise), and labeled gauge/reservoir markers.

    ``layers`` is ``story_tables.basin_map_layers()``'s output.
    """
    palette = PALETTES[theme]
    fig = go.Figure()

    in_index = layers.stations.loc[layers.stations["in_index"]]
    not_in_index = layers.stations.loc[~layers.stations["in_index"]]
    fig.add_trace(
        go.Scattermap(
            lat=not_in_index["latitude"],
            lon=not_in_index["longitude"],
            mode="markers",
            marker={"size": 6, "color": palette.surface, "opacity": 0.9},
            name="SNOTEL station",
            text=not_in_index["name"],
            hovertemplate="%{text}<extra>SNOTEL station</extra>",
        )
    )
    fig.add_trace(
        go.Scattermap(
            lat=in_index["latitude"],
            lon=in_index["longitude"],
            mode="markers",
            marker={"size": 8, "color": palette.high},
            name="Snow index station",
            text=in_index["name"],
            hovertemplate="%{text}<extra>Snow index station</extra>",
        )
    )

    for kind, label in (("gauge", "Stream gauge"), ("reservoir", "Reservoir")):
        rows = layers.sites.loc[layers.sites["kind"] == kind]
        fig.add_trace(
            go.Scattermap(
                lat=rows["latitude"],
                lon=rows["longitude"],
                mode="markers+text",
                marker={
                    "size": 14,
                    "symbol": _SITE_SYMBOLS[kind],
                    "color": palette.low,
                },
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
            "color": palette.band_fill,
            "opacity": 0.5,
        },
        {
            "source": layers.basins["15"],
            "type": "fill",
            "color": palette.gridline,
            "opacity": 0.3,
        },
    ]
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        map={
            "style": MAP_STYLE,
            "center": DEFAULT_CENTER,
            "zoom": DEFAULT_ZOOM,
            "layers": map_layers,
        },
    )
    return fig
