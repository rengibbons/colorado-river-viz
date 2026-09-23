"""Chapter 5 chart: Lees Ferry flow before and after Glen Canyon Dam (design §7)."""

from __future__ import annotations

import plotly.graph_objects as go

from colorado_river_viz.charts.theme import (
    PALETTES,
    Theme,
    day_of_water_year_ticks,
    direct_label,
    layout_template,
)
from colorado_river_viz.story_tables import LeesFerryRegimes

DEFAULT_TITLE = "Glen Canyon Dam flattened Lees Ferry's hydrograph"

_REGIME_LABELS = {
    "before_dam": "Before dam (WY1922-1962)",
    "after_dam": "After dam (WY1981-)",
}


def build_before_after_dam(
    regimes: LeesFerryRegimes, theme: Theme = "light", title: str = DEFAULT_TITLE
) -> go.Figure:
    """Median and 10th/90th percentile Lees Ferry flow by day of water year,
    one line per regime, each with a direct label (design §7).

    ``regimes`` is ``story_tables.lees_ferry_regimes()``'s output. The natural,
    pre-dam regime is drawn in the "high" hue (a snowmelt-driven spring peak)
    and the managed, post-dam regime in the "low" hue (a flattened, load-driven
    line), reusing the theme's two highlight colors rather than adding a third.
    """
    palette = PALETTES[theme]
    regime_colors = {"before_dam": palette.high, "after_dam": palette.low}
    fig = go.Figure()

    for regime in ("before_dam", "after_dam"):
        rows = regimes.envelope.loc[regimes.envelope["regime"] == regime].sort_values(
            "day_of_water_year"
        )
        color = regime_colors[regime]
        label = _REGIME_LABELS[regime]
        fig.add_trace(
            go.Scatter(
                x=rows["day_of_water_year"],
                y=rows["p90_cfs"],
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
                name=f"{label} 90th percentile",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=rows["day_of_water_year"],
                y=rows["p10_cfs"],
                line={"width": 0},
                fill="tonexty",
                fillcolor=palette.band_fill,
                hoverinfo="skip",
                showlegend=False,
                name=f"{label} 10th-90th percentile",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=rows["day_of_water_year"],
                y=rows["median_cfs"],
                mode="lines",
                line={"color": color, "width": 2.5},
                showlegend=False,
                name=f"{label} median",
                hovertemplate=f"{label}: %{{y:,.0f}} cfs<extra></extra>",
            )
        )
        last = rows.iloc[-1]
        direct_label(
            fig,
            x=last["day_of_water_year"],
            y=last["median_cfs"],
            text=label,
            color=color,
        )

    tick_positions, tick_labels = day_of_water_year_ticks()
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis={
            "tickmode": "array",
            "tickvals": tick_positions,
            "ticktext": tick_labels,
        },
        yaxis_title="Lees Ferry daily flow (cfs)",
    )
    return fig
