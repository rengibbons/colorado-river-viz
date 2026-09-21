"""Chapter 2 chart: the snow spaghetti (design §7)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import (
    PALETTES,
    Theme,
    day_of_water_year_ticks,
    direct_label,
    layout_template,
    style_for_year,
)

DEFAULT_TITLE = "Every winter starts as snow in the mountains"


def _band_traces(envelope: pd.DataFrame, theme: Theme) -> list[go.Scatter]:
    fill_color = PALETTES[theme].band_fill
    return [
        go.Scatter(
            x=envelope["day_of_water_year"],
            y=envelope["p90_swe_in"],
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
            name="90th percentile",
        ),
        go.Scatter(
            x=envelope["day_of_water_year"],
            y=envelope["p10_swe_in"],
            line={"width": 0},
            fill="tonexty",
            fillcolor=fill_color,
            hoverinfo="skip",
            showlegend=False,
            name="10th-90th percentile (1991-2020)",
        ),
    ]


def _median_trace(envelope: pd.DataFrame, theme: Theme) -> go.Scatter:
    return go.Scatter(
        x=envelope["day_of_water_year"],
        y=envelope["median_swe_in"],
        mode="lines",
        line={"color": PALETTES[theme].text_secondary, "width": 1.5, "dash": "dot"},
        hoverinfo="skip",
        showlegend=False,
        name="1991-2020 median",
    )


def _year_trace(water_year: int, year_rows: pd.DataFrame, theme: Theme) -> go.Scatter:
    style = style_for_year(water_year, theme)
    return go.Scatter(
        x=year_rows["day_of_water_year"],
        y=year_rows["basin_swe_in"],
        mode="lines",
        line={"color": style.color, "width": style.width},
        showlegend=False,
        name=f"WY{water_year}",
        hovertemplate=f"WY{water_year}: %{{y:.1f}} in<extra></extra>",
    )


def build_snow_spaghetti(
    index_daily: pd.DataFrame,
    envelope: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_TITLE,
) -> go.Figure:
    """One line per water year of basin SWE, against the normals band and median.

    ``index_daily`` is ``snow_index_daily()``'s output and ``envelope`` is
    ``snow_index_envelope()``'s (design §6.3), both from ``story_tables``.
    """
    traces = [*_band_traces(envelope, theme), _median_trace(envelope, theme)]
    fig = go.Figure(data=traces)
    for water_year in sorted(index_daily["water_year"].unique()):
        rows = index_daily.loc[index_daily["water_year"] == water_year].dropna(
            subset=["basin_swe_in"]
        )
        if rows.empty:
            continue
        fig.add_trace(_year_trace(int(water_year), rows, theme))
        style = style_for_year(int(water_year), theme)
        if style.is_present:
            last = rows.iloc[-1]
            direct_label(
                fig,
                x=last["day_of_water_year"],
                y=last["basin_swe_in"],
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
        yaxis_title="Basin SWE (in)",
    )
    return fig
