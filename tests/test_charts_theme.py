from __future__ import annotations

import pytest

from colorado_river_viz.charts.theme import (
    GRAY_LINE_WIDTH,
    HIGHLIGHT_LINE_WIDTH,
    PALETTES,
    PRESENT_LINE_WIDTH,
    Theme,
    direct_label,
    layout_template,
    style_for_year,
)
from colorado_river_viz.constants import HIGHLIGHT_YEARS

THEMES: tuple[Theme, ...] = ("light", "dark")


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("wy", HIGHLIGHT_YEARS.low)
def test_low_years_resolve_to_the_warm_hue(wy: int, theme: Theme) -> None:
    style = style_for_year(wy, theme)

    assert style.color == PALETTES[theme].low
    if wy == HIGHLIGHT_YEARS.present:
        assert style.width == PRESENT_LINE_WIDTH
        assert style.is_present is True
    else:
        assert style.width == HIGHLIGHT_LINE_WIDTH
        assert style.is_present is False


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("wy", HIGHLIGHT_YEARS.high)
def test_high_years_resolve_to_the_cool_hue(wy: int, theme: Theme) -> None:
    style = style_for_year(wy, theme)

    assert style.color == PALETTES[theme].high
    assert style.width == HIGHLIGHT_LINE_WIDTH
    assert style.is_present is False


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("wy", [1990, 2000, 2015, 2022])
def test_non_highlight_years_resolve_to_gray(wy: int, theme: Theme) -> None:
    assert wy not in HIGHLIGHT_YEARS.all

    style = style_for_year(wy, theme)

    assert style.color == PALETTES[theme].baseline
    assert style.width == GRAY_LINE_WIDTH
    assert style.is_present is False


@pytest.mark.parametrize("theme", THEMES)
def test_layout_template_uses_the_theme_surface(theme: Theme) -> None:
    template = layout_template(theme)

    assert template.layout.paper_bgcolor == PALETTES[theme].surface
    assert template.layout.plot_bgcolor == PALETTES[theme].surface


def test_direct_label_adds_an_annotation_in_the_series_color() -> None:
    import plotly.graph_objects as go

    fig = go.Figure()

    direct_label(fig, x=365, y=12.0, text="WY2026", color="#eb6834")

    assert len(fig.layout.annotations) == 1
    annotation = fig.layout.annotations[0]
    assert annotation.text == "WY2026"
    assert annotation.font.color == "#eb6834"
