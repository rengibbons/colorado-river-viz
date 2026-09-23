"""The "2026 at a glance" KPI panel: Plotly Indicator tiles (design §7)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from colorado_river_viz.charts.theme import PALETTES, Theme, layout_template

DEFAULT_TITLE = "2026 at a glance"
PANEL_COLUMNS = 2
PANEL_ROW_HEIGHT_PX = 200


def build_kpi_panel(
    kpi_table: pd.DataFrame, theme: Theme = "light", title: str = DEFAULT_TITLE
) -> go.Figure:
    """One ``Indicator`` tile per row of ``story_tables.kpis()``'s output,
    each showing its ``display`` string and ``rank_phrase`` (design §7).
    """
    palette = PALETTES[theme]
    n = len(kpi_table)
    rows = -(-n // PANEL_COLUMNS)  # ceiling division
    fig = go.Figure()

    for i, (_, kpi) in enumerate(kpi_table.iterrows()):
        row, col = divmod(i, PANEL_COLUMNS)
        domain_x = [col / PANEL_COLUMNS, (col + 0.95) / PANEL_COLUMNS]
        domain_y = [1 - (row + 0.9) / rows, 1 - row / rows]
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=float(kpi["value"]),
                number={"suffix": f" {kpi['unit']}", "font": {"size": 40}},
                title={
                    "font": {"size": 20},
                    "text": (
                        f"{kpi['label']}<br>"
                        f"<span style='font-size:0.8em;color:{palette.text_secondary}'>"
                        f"{kpi['display']}: {kpi['rank_phrase']}</span>"
                    ),
                },
                domain={"x": domain_x, "y": domain_y},
            )
        )

    as_of = pd.Timestamp(kpi_table["as_of"].iloc[0]).strftime("%b %-d, %Y")
    fig.update_layout(
        template=layout_template(theme),
        title=title,
        height=rows * PANEL_ROW_HEIGHT_PX + 120,
        annotations=[
            {
                "text": f"As of {as_of}",
                "xref": "paper",
                "yref": "paper",
                "x": 0,
                "y": -0.05,
                "showarrow": False,
                "font": {"size": 11, "color": palette.text_secondary},
            }
        ],
    )
    return fig
