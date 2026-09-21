"""Shared chart styling: palette, layout template, and label helpers (design §7).

Palette: gray for ordinary years, one warm hue for "low" highlight years, one
cool hue for "high" highlight years, and WY2026 -- the present year, also a low
year per decision 0012 -- drawn in the same warm hue at extra line width and
flagged for a direct label rather than a legend entry.

The warm/cool pair is the dataviz skill's default categorical slots 2 (orange)
and 1 (blue). The skill's own palette reference documents this adjacent pair as
clearing every contrast and CVD-safety gate in both light and dark mode (worst
adjacent Delta E 9.1 light / 8.4 dark CVD, 19.6 / 19.3 normal-vision -- both
above the skill's 8 / 15 targets), so it is used as-is rather than re-run
through the validator script.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.constants import HIGHLIGHT_YEARS, HighlightYears
from colorado_river_viz.water_year import day_of_water_year, water_year_bounds

Theme = Literal["light", "dark"]

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", sans-serif'

PRESENT_LINE_WIDTH = 3.5
HIGHLIGHT_LINE_WIDTH = 2.0
GRAY_LINE_WIDTH = 0.75


@dataclass(frozen=True, slots=True)
class Palette:
    """Chart chrome and the highlight-year hues, for one theme (design §7)."""

    surface: str
    text_primary: str
    text_secondary: str
    gridline: str
    baseline: str
    band_fill: str
    low: str
    high: str


PALETTES: dict[Theme, Palette] = {
    "light": Palette(
        surface="#fcfcfb",
        text_primary="#0b0b0b",
        text_secondary="#52514e",
        gridline="#e1e0d9",
        baseline="#c3c2b7",
        band_fill="rgba(195,194,183,0.25)",
        low="#eb6834",
        high="#2a78d6",
    ),
    "dark": Palette(
        surface="#1a1a19",
        text_primary="#ffffff",
        text_secondary="#c3c2b7",
        gridline="#2c2c2a",
        baseline="#383835",
        band_fill="rgba(56,56,53,0.35)",
        low="#d95926",
        high="#3987e5",
    ),
}


@dataclass(frozen=True, slots=True)
class YearStyle:
    """How one water year's line should be drawn."""

    color: str
    width: float
    is_present: bool


def style_for_year(
    wy: int,
    theme: Theme = "light",
    highlight_years: HighlightYears = HIGHLIGHT_YEARS,
) -> YearStyle:
    """Return the line style for a water year, following decision 0012.

    Non-highlight years are thin gray. Highlight years are colored by group
    (warm for low, cool for high) at a heavier line width. WY2026, the present
    year, gets the thickest line and ``is_present=True`` so callers add a direct
    label instead of a legend entry.
    """
    palette = PALETTES[theme]
    if wy == highlight_years.present:
        return YearStyle(color=palette.low, width=PRESENT_LINE_WIDTH, is_present=True)
    if wy in highlight_years.low:
        return YearStyle(
            color=palette.low, width=HIGHLIGHT_LINE_WIDTH, is_present=False
        )
    if wy in highlight_years.high:
        return YearStyle(
            color=palette.high, width=HIGHLIGHT_LINE_WIDTH, is_present=False
        )
    return YearStyle(color=palette.baseline, width=GRAY_LINE_WIDTH, is_present=False)


def layout_template(theme: Theme = "light") -> go.layout.Template:
    """A shared Plotly layout template: fonts, surface, gridlines, and axis style."""
    palette = PALETTES[theme]
    axis = {
        "showgrid": True,
        "gridcolor": palette.gridline,
        "gridwidth": 1,
        "linecolor": palette.baseline,
        "tickfont": {"color": palette.text_secondary},
        "title": {"font": {"color": palette.text_secondary}},
        "zeroline": False,
    }
    return go.layout.Template(
        layout=go.Layout(
            font={"family": FONT_FAMILY, "color": palette.text_primary},
            paper_bgcolor=palette.surface,
            plot_bgcolor=palette.surface,
            title={"font": {"size": 18, "color": palette.text_primary}},
            xaxis=axis,
            yaxis=axis,
            legend={"font": {"color": palette.text_secondary}},
        )
    )


def day_of_water_year_ticks() -> tuple[list[int], list[str]]:
    """Month-start tick positions and labels for a day-of-water-year x-axis.

    Oct 1 = day 1. Computed from a non-leap reference year, so the ticks land
    a day early in the second half of a leap water year -- close enough for an
    axis label.
    """
    bounds = water_year_bounds(2025)
    month_starts = pd.date_range(bounds.start, bounds.end, freq="MS")
    days = day_of_water_year(pd.DatetimeIndex(month_starts))
    labels = [pd.Timestamp(d).strftime("%b") for d in month_starts]
    return list(days), labels


def direct_label(
    fig: go.Figure, x: float, y: float, text: str, color: str
) -> go.Figure:
    """Add a direct text label at a line's end, in place of a legend entry."""
    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        xanchor="left",
        font={"color": color, "family": FONT_FAMILY, "size": 12},
        xshift=6,
    )
    return fig
