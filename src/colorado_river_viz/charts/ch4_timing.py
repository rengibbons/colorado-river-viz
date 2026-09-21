"""Chapter 4 charts: timing trends and the Cisco hydrograph (design §7)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from colorado_river_viz.charts.theme import (
    PALETTES,
    Theme,
    day_of_water_year_ticks,
    direct_label,
    layout_template,
    style_for_year,
)
from colorado_river_viz.metrics.trend import theil_sen_trend

DEFAULT_TIMING_TITLE = "The river runs earlier and faster than it used to"
DEFAULT_HYDROGRAPH_TITLE = "Cisco's hydrograph has changed shape"

_TIMING_PANELS = (
    ("snow_peak_doy", "Peak snowpack"),
    ("snow_meltout_doy", "Snow melt-out"),
    ("cisco_center_of_volume_doy", "Half the year's flow has passed"),
)


def build_timing_trends(
    timing: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_TIMING_TITLE,
) -> go.Figure:
    """Three small multiples of timing metrics vs. water year, each with its
    Theil-Sen trend line and an "N days earlier/later per decade" label.

    ``timing`` is ``story_tables.timing_annual()``'s output. Y-axes show date
    labels rather than day-of-water-year numbers (design §7).
    """
    palette = PALETTES[theme]
    fig = make_subplots(
        rows=1, cols=3, subplot_titles=[label for _, label in _TIMING_PANELS]
    )
    tick_positions, tick_labels = day_of_water_year_ticks()

    for col, (column, _) in enumerate(_TIMING_PANELS, start=1):
        subset = timing.dropna(subset=[column])
        fig.add_trace(
            go.Scatter(
                x=subset["water_year"],
                y=subset[column],
                mode="markers",
                marker={"color": palette.baseline, "size": 6},
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=col,
        )
        trend = theil_sen_trend(subset["water_year"], subset[column])
        x_domain = [subset["water_year"].min(), subset["water_year"].max()]
        fig.add_trace(
            go.Scatter(
                x=x_domain,
                y=[trend.value_at(x) for x in x_domain],
                mode="lines",
                line={"color": palette.high, "width": 2},
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=col,
        )
        direction = "earlier" if trend.slope_per_decade < 0 else "later"
        axis_suffix = "" if col == 1 else str(col)
        fig.add_annotation(
            text=f"{abs(trend.slope_per_decade):.1f} days {direction} per decade",
            xref=f"x{axis_suffix} domain",
            yref=f"y{axis_suffix} domain",
            x=0.02,
            y=0.02,
            showarrow=False,
            font={"size": 11, "color": palette.text_primary},
        )
        fig.update_yaxes(
            tickmode="array",
            tickvals=tick_positions,
            ticktext=tick_labels,
            row=1,
            col=col,
        )

    fig.update_layout(template=layout_template(theme), title=title)
    return fig


def build_cisco_spaghetti(
    hydrograph: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_HYDROGRAPH_TITLE,
) -> go.Figure:
    """One line per water year of Cisco daily flow, against the pre-1963 median
    and 10th/90th percentile envelope -- the same treatment as the chapter 2
    snow spaghetti (design §7).

    ``hydrograph`` is ``story_tables.cisco_hydrograph()``'s output. The USGS
    Cisco record has no data for WY1918-1922, so the baseline envelope draws
    on 44 complete years (1914-1962), not 49 (T20 carry-over note).
    """
    palette = PALETTES[theme]
    envelope = hydrograph.drop_duplicates("day_of_water_year").sort_values(
        "day_of_water_year"
    )
    band_upper = go.Scatter(
        x=envelope["day_of_water_year"],
        y=envelope["p90_cfs"],
        line={"width": 0},
        hoverinfo="skip",
        showlegend=False,
        name="90th percentile (1914-1962)",
    )
    band_lower = go.Scatter(
        x=envelope["day_of_water_year"],
        y=envelope["p10_cfs"],
        line={"width": 0},
        fill="tonexty",
        fillcolor=palette.band_fill,
        hoverinfo="skip",
        showlegend=False,
        name="10th-90th percentile (1914-1962)",
    )
    median_trace = go.Scatter(
        x=envelope["day_of_water_year"],
        y=envelope["median_cfs"],
        mode="lines",
        line={"color": palette.text_secondary, "width": 1.5, "dash": "dot"},
        hoverinfo="skip",
        showlegend=False,
        name="1914-1962 median",
    )
    fig = go.Figure(data=[band_upper, band_lower, median_trace])

    for water_year in sorted(hydrograph["water_year"].unique()):
        rows = hydrograph.loc[hydrograph["water_year"] == water_year].dropna(
            subset=["cfs"]
        )
        if rows.empty:
            continue
        style = style_for_year(int(water_year), theme)
        fig.add_trace(
            go.Scatter(
                x=rows["day_of_water_year"],
                y=rows["cfs"],
                mode="lines",
                line={"color": style.color, "width": style.width},
                showlegend=False,
                name=f"WY{int(water_year)}",
                hovertemplate=f"WY{int(water_year)}: %{{y:,.0f}} cfs<extra></extra>",
            )
        )
        if style.is_present:
            last = rows.iloc[-1]
            direct_label(
                fig,
                x=last["day_of_water_year"],
                y=last["cfs"],
                text=f"WY{int(water_year)}",
                color=style.color,
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
        yaxis_title="Cisco daily flow (cfs)",
    )
    return fig
