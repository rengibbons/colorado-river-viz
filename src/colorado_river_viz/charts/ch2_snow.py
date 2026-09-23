"""Chapter 2 charts: the snow spaghetti and the peak-SWE bar chart (design §7).

Both highlight the ``N_HIGHLIGHT_YEARS`` driest and wettest water years by peak
basin SWE, computed on the fly from ``index_daily`` (not the fixed decision-0012
highlight-year list, which stays in effect for chapters 3-4 and the KPI panel).
The present water year (``HIGHLIGHT_YEARS.present``) is always forced into the
driest group, in the most-extreme (reddest, boldest) slot, regardless of where
it actually ranks. See decisions 0028, 0029.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import (
    DRY_YEAR_COLORS,
    PALETTES,
    WET_YEAR_COLORS,
    Theme,
    day_of_water_year_ticks,
    layout_template,
)
from colorado_river_viz.constants import HIGHLIGHT_YEARS
from colorado_river_viz.metrics.snow import annual_peaks, top_bottom_peak_years

DEFAULT_TITLE = "Every winter starts as snow in the mountains"
PEAK_BAR_TITLE = "Peak basin snowpack by water year"
N_HIGHLIGHT_YEARS = 3
HIGHLIGHT_LINE_WIDTH = 2.0
PRESENT_YEAR_LINE_WIDTH = HIGHLIGHT_LINE_WIDTH * 2


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


def _highlight_years(
    index_daily: pd.DataFrame,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The driest and wettest water years in ``index_daily``, by peak basin SWE.

    The present water year is always forced into the driest group's first
    (most-extreme) slot, regardless of its computed rank (decision 0029).
    """
    driest, wettest = top_bottom_peak_years(
        annual_peaks(index_daily), n=N_HIGHLIGHT_YEARS
    )
    present = HIGHLIGHT_YEARS.present
    others = tuple(wy for wy in driest if wy != present)[: N_HIGHLIGHT_YEARS - 1]
    wettest = tuple(wy for wy in wettest if wy != present)
    return (present, *others), wettest


def _year_color(
    water_year: int,
    driest: tuple[int, ...],
    wettest: tuple[int, ...],
    theme: Theme,
) -> str:
    if water_year in driest:
        return DRY_YEAR_COLORS[theme][driest.index(water_year)]
    return WET_YEAR_COLORS[theme][wettest.index(water_year)]


def _year_trace(water_year: int, year_rows: pd.DataFrame, color: str) -> go.Scatter:
    width = (
        PRESENT_YEAR_LINE_WIDTH
        if water_year == HIGHLIGHT_YEARS.present
        else HIGHLIGHT_LINE_WIDTH
    )
    return go.Scatter(
        x=year_rows["day_of_water_year"],
        y=year_rows["basin_swe_in"],
        mode="lines",
        line={"color": color, "width": width},
        showlegend=True,
        name=f"WY{water_year}",
        hovertemplate=f"WY{water_year}: %{{y:.1f}} in<extra></extra>",
    )


def build_snow_spaghetti(
    index_daily: pd.DataFrame,
    envelope: pd.DataFrame,
    theme: Theme = "light",
    title: str = DEFAULT_TITLE,
) -> go.Figure:
    """The climatology band/median, plus one line per driest/wettest peak year.

    ``index_daily`` is ``snow_index_daily()``'s output and ``envelope`` is
    ``snow_index_envelope()``'s (design §6.3), both from ``story_tables``. The
    highlighted years are the ``N_HIGHLIGHT_YEARS`` driest and wettest water
    years by peak basin SWE, recomputed from ``index_daily`` on every call.
    """
    traces = [*_band_traces(envelope, theme), _median_trace(envelope, theme)]
    fig = go.Figure(data=traces)

    driest, wettest = _highlight_years(index_daily)
    for water_year in [*driest, *wettest]:
        rows = index_daily.loc[index_daily["water_year"] == water_year].dropna(
            subset=["basin_swe_in"]
        )
        if rows.empty:
            continue
        color = _year_color(water_year, driest, wettest, theme)
        fig.add_trace(_year_trace(water_year, rows, color))

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
        legend={"title": {"text": "Water year"}},
    )
    return fig


def _peak_bar_colors(
    peaks: pd.DataFrame,
    driest: tuple[int, ...],
    wettest: tuple[int, ...],
    theme: Theme,
) -> list[str]:
    baseline = PALETTES[theme].baseline
    colors = []
    for water_year in peaks["water_year"]:
        water_year = int(water_year)
        if water_year in driest:
            colors.append(DRY_YEAR_COLORS[theme][driest.index(water_year)])
        elif water_year in wettest:
            colors.append(WET_YEAR_COLORS[theme][wettest.index(water_year)])
        else:
            colors.append(baseline)
    return colors


def build_peak_swe_bar(
    index_daily: pd.DataFrame,
    theme: Theme = "light",
    title: str = PEAK_BAR_TITLE,
) -> go.Figure:
    """One bar per water year: that year's peak basin SWE.

    ``index_daily`` is ``snow_index_daily()``'s output. Bars for the
    ``N_HIGHLIGHT_YEARS`` driest and wettest years (by this same peak) are
    colored to match ``build_snow_spaghetti``; other years are neutral gray.
    """
    peaks = annual_peaks(index_daily).sort_values("water_year", ignore_index=True)
    driest, wettest = _highlight_years(index_daily)
    colors = _peak_bar_colors(peaks, driest, wettest, theme)

    fig = go.Figure(
        go.Bar(
            x=peaks["water_year"],
            y=peaks["peak_swe_in"],
            marker={"color": colors},
            showlegend=False,
            hovertemplate="WY%{x}: %{y:.1f} in<extra></extra>",
        )
    )
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        xaxis_title="Water year",
        yaxis_title="Peak basin SWE (in)",
    )
    return fig
