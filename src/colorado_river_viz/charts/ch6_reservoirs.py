"""Chapter 6 chart: combined reservoir storage since 1964 (design §7)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import PALETTES, Theme, layout_template
from colorado_river_viz.reservoirs import LAKE_MEAD, LAKE_POWELL

DEFAULT_TITLE = "The basin's bank account has been drawn down since 2000"
POST_2000_SHADE_START = "2000-01-01"


def build_reservoir_storage(
    storage: pd.DataFrame, theme: Theme = "light", title: str = DEFAULT_TITLE
) -> go.Figure:
    """Combined Powell + Mead percent-full since 1964, plus each reservoir's
    own line, with the post-2000 drawdown period shaded (design §7).

    ``storage`` is ``story_tables.reservoir_storage()``'s output.
    ``ft_above_min_power_pool`` is included in hover text for Powell and Mead.
    """
    palette = PALETTES[theme]
    fig = go.Figure()

    combined = storage.loc[storage["reservoir"] == "Combined"].sort_values("date")
    fig.add_trace(
        go.Scatter(
            x=combined["date"],
            y=combined["pct_full"],
            mode="lines",
            fill="tozeroy",
            line={"color": palette.text_secondary, "width": 2},
            fillcolor=palette.band_fill,
            name="Combined",
            hovertemplate="%{x|%b %Y}: %{y:.0f}% full<extra>Combined</extra>",
        )
    )

    for reservoir, color in (
        (LAKE_POWELL.name, palette.high),
        (LAKE_MEAD.name, palette.low),
    ):
        rows = storage.loc[storage["reservoir"] == reservoir].sort_values("date")
        fig.add_trace(
            go.Scatter(
                x=rows["date"],
                y=rows["pct_full"],
                mode="lines",
                line={"color": color, "width": 1.5},
                name=reservoir,
                customdata=rows["ft_above_min_power_pool"],
                hovertemplate=(
                    "%{x|%b %Y}: %{y:.0f}% full, %{customdata:.0f} ft above "
                    f"min. power pool<extra>{reservoir}</extra>"
                ),
            )
        )

    fig.add_vrect(
        x0=pd.Timestamp(POST_2000_SHADE_START),
        x1=storage["date"].max(),
        fillcolor=palette.band_fill,
        opacity=0.5,
        line_width=0,
        annotation_text="Post-2000 drawdown",
        annotation_position="top left",
    )

    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Year",
        yaxis_title="Percent of full-pool capacity",
    )
    return fig
