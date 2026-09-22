"""Chapter 3 chart: the runoff efficiency trend (design §7)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from colorado_river_viz.charts.theme import PALETTES, Theme, layout_template
from colorado_river_viz.constants import NORMALS_PERIOD, YearSpan
from colorado_river_viz.metrics.trend import TrendResult, theil_sen_trend

DEFAULT_TREND_TITLE = "Runoff efficiency has fallen over the record"


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
