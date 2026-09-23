"""Chapter 1 charts: supply vs. the Compact allocation, and paleo context.

Design §7.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import PALETTES, Theme, layout_template
from colorado_river_viz.constants import COMPACT_APPORTIONMENT_MAF

DEFAULT_SUPPLY_TITLE = "The river has been promised more than it delivers"
DEFAULT_PALEO_TITLE = "Twelve centuries of Colorado River flow"

COMPACT_ERA_START = 1906
COMPACT_ERA_END = 1922
ROLLING_WINDOW_YEARS = 20
MEGADROUGHT_START = 1130
MEGADROUGHT_END = 1160
PALEO_MODERN_ERA_START = 2000


def build_supply_vs_compact(
    supply: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_SUPPLY_TITLE,
) -> go.Figure:
    """Annual natural flow, published and bridge-estimated, against the 16.5
    MAF Compact allocation and its 20-year rolling mean.

    ``supply`` is ``story_tables.annual_supply()``'s output. Estimated bars are
    hatched and outlined, with an asymmetric error whisker from
    ``estimate_low_maf``/``estimate_high_maf`` (design §7).
    """
    palette = PALETTES[theme]
    is_estimated = (supply["kind"] == "estimated").to_numpy()

    bars = go.Bar(
        x=supply["water_year"],
        y=supply["natural_flow_maf"],
        marker={
            "color": palette.high,
            "line": {
                "color": palette.text_primary,
                "width": [1.5 if e else 0 for e in is_estimated],
            },
            "pattern": {"shape": ["/" if e else "" for e in is_estimated]},
        },
        error_y={
            "type": "data",
            "symmetric": False,
            "array": (supply["estimate_high_maf"] - supply["natural_flow_maf"])
            .where(is_estimated, 0)
            .to_numpy(dtype=float),
            "arrayminus": (supply["natural_flow_maf"] - supply["estimate_low_maf"])
            .where(is_estimated, 0)
            .to_numpy(dtype=float),
            "color": palette.text_secondary,
        },
        name="Natural flow",
        showlegend=False,
        hovertemplate="WY%{x}: %{y:.1f} MAF<extra></extra>",
    )
    rolling = (
        supply["natural_flow_maf"]
        .rolling(ROLLING_WINDOW_YEARS, min_periods=ROLLING_WINDOW_YEARS)
        .mean()
    )
    rolling_trace = go.Scatter(
        x=supply["water_year"],
        y=rolling,
        mode="lines",
        line={"color": palette.text_primary, "width": 2},
        name="20-year rolling mean",
        showlegend=False,
        hoverinfo="skip",
    )
    fig = go.Figure(data=[bars, rolling_trace])
    fig.add_hline(
        y=COMPACT_APPORTIONMENT_MAF,
        line={"color": palette.low, "dash": "dash", "width": 1.5},
        annotation_text=f"{COMPACT_APPORTIONMENT_MAF} MAF Compact allocation",
        annotation_position="top left",
    )
    fig.add_vrect(
        x0=COMPACT_ERA_START - 0.5,
        x1=COMPACT_ERA_END + 0.5,
        fillcolor=palette.gridline,
        opacity=0.5,
        line_width=0,
        annotation_text="Compact era",
        annotation_position="top",
    )
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Water year",
        yaxis_title="Natural flow (MAF)",
    )
    return fig


def _spliced_flow(paleo: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """The reconstruction's tail spliced onto the gauge era (design §7, 1b)."""
    splice_year = int(paleo["water_year"].max())
    gauge_tail = supply.loc[
        supply["water_year"] > splice_year, ["water_year", "natural_flow_maf"]
    ].rename(columns={"natural_flow_maf": "flow_maf"})
    recon_head = paleo[["water_year", "recon_maf"]].rename(
        columns={"recon_maf": "flow_maf"}
    )
    combined = pd.concat([recon_head, gauge_tail], ignore_index=True).sort_values(
        "water_year", ignore_index=True
    )
    combined["rolling_20yr_mean_maf"] = (
        combined["flow_maf"]
        .rolling(ROLLING_WINDOW_YEARS, min_periods=ROLLING_WINDOW_YEARS)
        .mean()
    )
    return combined


def build_paleo_context(
    paleo: pd.DataFrame,
    supply: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_PALEO_TITLE,
) -> go.Figure:
    """The 20-year rolling mean of reconstructed and gauged flow, 762-2026.

    ``paleo`` is ``story_tables.paleo_supply()``'s output (762-2005); its tail
    is spliced onto ``supply`` (``story_tables.annual_supply()``'s output) so
    the line runs to the present.
    """
    palette = PALETTES[theme]
    spliced = _spliced_flow(paleo, supply)
    line = go.Scatter(
        x=spliced["water_year"],
        y=spliced["rolling_20yr_mean_maf"],
        mode="lines",
        line={"color": palette.high, "width": 1.5},
        showlegend=False,
        name="20-year rolling mean",
        hovertemplate="%{x}: %{y:.1f} MAF<extra></extra>",
    )
    fig = go.Figure(data=[line])
    fig.add_vrect(
        x0=MEGADROUGHT_START,
        x1=MEGADROUGHT_END,
        fillcolor=palette.low,
        opacity=0.15,
        line_width=0,
        annotation_text="1100s megadrought",
        annotation_position="top",
    )
    fig.add_vrect(
        x0=PALEO_MODERN_ERA_START,
        x1=spliced["water_year"].max(),
        fillcolor=palette.gridline,
        opacity=0.4,
        line_width=0,
        annotation_text="Since 2000",
        annotation_position="bottom",
    )
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Year",
        yaxis_title="20-year rolling mean flow (MAF)",
    )
    return fig
