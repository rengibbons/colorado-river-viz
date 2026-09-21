"""Chapter 3 charts: snow vs. runoff, and the efficiency trend (design §7)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from colorado_river_viz.charts.theme import (
    PALETTES,
    Theme,
    direct_label,
    layout_template,
    style_for_year,
)
from colorado_river_viz.constants import (
    HIGHLIGHT_YEARS,
    NORMALS_PERIOD,
    HighlightYears,
    YearSpan,
)
from colorado_river_viz.metrics.trend import TrendResult, theil_sen_trend

DEFAULT_SCATTER_TITLE = "The same snowpack now yields less spring runoff"
DEFAULT_TREND_TITLE = "Runoff efficiency has fallen over the record"


def _half_split_fit_traces(runoff: pd.DataFrame) -> list[go.Scatter]:
    """A Theil-Sen fit line for each half of the record, split by year."""
    years = sorted(int(wy) for wy in runoff["water_year"].unique())
    midpoint = len(years) // 2
    halves = {"first half": years[:midpoint], "second half": years[midpoint:]}
    x_domain = np.array(
        [runoff["peak_swe_in"].min(), runoff["peak_swe_in"].max()], dtype=float
    )

    traces = []
    for label, half_years in halves.items():
        subset = runoff[runoff["water_year"].isin(half_years)]
        if len(subset) < 2:
            continue
        slope, intercept, _, _ = stats.theilslopes(
            subset["apr_jul_unreg_maf"], subset["peak_swe_in"]
        )
        traces.append(
            go.Scatter(
                x=x_domain,
                y=intercept + slope * x_domain,
                mode="lines",
                line={"dash": "dash"},
                name=f"{label} fit ({half_years[0]}-{half_years[-1]})",
            )
        )
    return traces


def build_snow_vs_runoff(
    runoff: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_SCATTER_TITLE,
    highlight_years: HighlightYears = HIGHLIGHT_YEARS,
) -> go.Figure:
    """Peak SWE vs. Apr-Jul runoff, colored by year, with per-half fitted lines.

    ``runoff`` is ``story_tables.runoff_vs_snow()``'s output.
    """
    scatter = go.Scatter(
        x=runoff["peak_swe_in"],
        y=runoff["apr_jul_unreg_maf"],
        mode="markers",
        marker={
            "color": runoff["water_year"],
            "colorscale": "Blues",
            "colorbar": {"title": "Water year"},
            "size": 9,
        },
        text=[f"WY{int(wy)}" for wy in runoff["water_year"]],
        hovertemplate="%{text}: %{x:.1f} in peak SWE, %{y:.2f} MAF<extra></extra>",
        name="Water years",
        showlegend=False,
    )
    fig = go.Figure(data=[scatter, *_half_split_fit_traces(runoff)])

    for _, row in runoff.iterrows():
        wy = int(row["water_year"])
        if wy in highlight_years.all:
            style = style_for_year(wy, theme)
            direct_label(
                fig,
                x=row["peak_swe_in"],
                y=row["apr_jul_unreg_maf"],
                text=f"WY{wy}",
                color=style.color,
            )

    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Peak basin SWE (in)",
        yaxis_title="Apr-Jul unregulated inflow (MAF)",
    )
    return fig


def residual_efficiency_trend(
    runoff: pd.DataFrame, normals: YearSpan = NORMALS_PERIOD
) -> TrendResult:
    """Robustness check for the efficiency trend (T16 carry-over note).

    ``runoff_efficiency`` (Apr-Jul MAF / peak SWE) is inflated in dry years
    because base flow doesn't shrink with snow, so a run of dry years can
    create a "decline" by itself. This is the trend in the *residuals* of a
    runoff-vs-peak-SWE regression instead -- a check that isn't vulnerable to
    that inflation. Compare its sign and significance against
    ``theil_sen_trend(runoff["water_year"], runoff["runoff_efficiency"])``
    before the chapter 3 narrative claims "same snow, less river"; if they
    disagree, say so in the "How we know" note rather than picking one.
    """
    slope, intercept, _, _ = stats.theilslopes(
        runoff["apr_jul_unreg_maf"], runoff["peak_swe_in"]
    )
    residuals = runoff["apr_jul_unreg_maf"] - (
        intercept + slope * runoff["peak_swe_in"]
    )
    return theil_sen_trend(runoff["water_year"], residuals, normals)


def build_efficiency_trend(
    runoff: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_TREND_TITLE,
    normals: YearSpan = NORMALS_PERIOD,
) -> go.Figure:
    """Runoff efficiency per year, with its Theil-Sen trend line (design §7)."""
    palette = PALETTES[theme]
    trend = theil_sen_trend(runoff["water_year"], runoff["runoff_efficiency"], normals)

    dots = go.Scatter(
        x=runoff["water_year"],
        y=runoff["runoff_efficiency"],
        mode="markers",
        marker={"color": palette.baseline, "size": 7},
        name="Runoff efficiency",
        hovertemplate="WY%{x}: %{y:.3f} MAF/in<extra></extra>",
        showlegend=False,
    )
    x_domain = np.array(
        [runoff["water_year"].min(), runoff["water_year"].max()], dtype=float
    )
    line = go.Scatter(
        x=x_domain,
        y=[trend.value_at(x) for x in x_domain],
        mode="lines",
        line={"color": palette.high, "width": 2},
        name="Theil-Sen trend",
        showlegend=False,
    )
    fig = go.Figure(data=[dots, line])

    direction = "less" if trend.pct_of_normal_per_decade < 0 else "more"
    fig.add_annotation(
        x=0.02,
        y=0.98,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        text=(
            f"≈{abs(trend.pct_of_normal_per_decade):.0f}% {direction} "
            "runoff per inch of snow per decade"
        ),
        font={"color": palette.text_primary},
    )
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Water year",
        yaxis_title="Runoff efficiency (MAF per in of peak SWE)",
    )
    return fig
