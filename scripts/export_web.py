"""Export the story notebook as a single static HTML fragment for embedding
in another page (e.g. via Jekyll's ``include_relative``) -- not a standalone
document, since it has no ``<html>``/``<head>``/``<body>`` of its own and
relies on the host page for a title and site chrome.

Reads the existing local cache (offline by default; the GitHub Actions
workflow that calls this refreshes it first) and writes one HTML fragment to
``--output-dir`` covering every notebook section -- overview, all six story
chapters, and the KPI snapshot -- in order. Its own styles and the Plotly CDN
``<script>`` tag are scoped so embedding it doesn't leak into the host page.

    uv run python scripts/export_web.py  # offline, ./site_export
    uv run python scripts/export_web.py --output-dir dist --refresh incremental
"""

from __future__ import annotations

import argparse
import html
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import get_args

import plotly.graph_objects as go

from colorado_river_viz.cache import RefreshMode, load_snotel_stations, refresh_story
from colorado_river_viz.charts.ch1_supply import (
    build_paleo_context,
    build_supply_vs_compact,
)
from colorado_river_viz.charts.ch2_snow import build_peak_swe_bar, build_snow_spaghetti
from colorado_river_viz.charts.ch3_runoff import build_efficiency_trend
from colorado_river_viz.charts.ch4_timing import build_timing_trends
from colorado_river_viz.charts.ch5_dams import build_before_after_dam
from colorado_river_viz.charts.ch6_reservoirs import build_reservoir_storage
from colorado_river_viz.charts.kpi_panel import build_kpi_panel
from colorado_river_viz.charts.map import build_basin_map
from colorado_river_viz.metrics.trend import theil_sen_trend
from colorado_river_viz.narrative import (
    describe_dam_effect,
    describe_peak_swe,
    describe_reservoir_drawdown,
    describe_runoff_year,
    describe_supply_vs_compact,
    describe_timing_trend,
    describe_trend,
)
from colorado_river_viz.settings import Settings
from colorado_river_viz.story_tables import (
    annual_supply,
    basin_map_layers,
    kpis,
    lees_ferry_regimes,
    paleo_supply,
    reservoir_storage,
    runoff_vs_snow,
    snow_annual,
    snow_index_daily,
    snow_index_envelope,
    timing_annual,
)

logger = logging.getLogger("export_web")

OUTPUT_FILENAME = "colorado-river-story.html"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"
FRAGMENT_CLASS = "crv-story"

# Caps each chart's on-page width -- tune this if the story column's own
# width changes (e.g. a different theme, or the site's sidebar width).
FIGURE_MAX_WIDTH_PX = 670

FRAGMENT_TEMPLATE = """<script src="{plotly_cdn}"></script>
<style>
  .{fragment_class} h2 {{ font-size: 1.25rem; margin-top: 2.5rem; }}
  .{fragment_class} .figure {{
    margin: 1.5rem auto;
    max-width: {figure_max_width}px;
  }}
</style>
<div class="{fragment_class}">
{body}
</div>
"""


@dataclass(frozen=True, slots=True)
class Section:
    """One section of the exported page: an optional heading, prose
    paragraphs, and figures. ``heading`` is ``None`` for the opening section,
    whose paragraphs sit directly under the page's own ``<h1>``.
    """

    heading: str | None
    paragraphs: list[str]
    figures: list[go.Figure]


def _figure_html(fig: go.Figure) -> str:
    # "responsive" makes Plotly size the chart to its container instead of a
    # fixed 700px-wide default, which is what caused the sideways scroll --
    # the container's own width is capped by FIGURE_MAX_WIDTH_PX above.
    html_str: str = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displaylogo": False, "responsive": True},
    )
    return html_str


def _render_section(section: Section) -> str:
    parts = []
    if section.heading is not None:
        parts.append(f"<h2>{html.escape(section.heading)}</h2>")
    parts.extend(f"<p>{html.escape(paragraph)}</p>" for paragraph in section.paragraphs)
    parts.extend(
        f'<div class="figure">{_figure_html(fig)}</div>' for fig in section.figures
    )
    return "\n".join(parts)


def _render_fragment(sections: list[Section]) -> str:
    body = "\n".join(_render_section(section) for section in sections)
    return FRAGMENT_TEMPLATE.format(
        plotly_cdn=PLOTLY_CDN,
        fragment_class=FRAGMENT_CLASS,
        figure_max_width=FIGURE_MAX_WIDTH_PX,
        body=body,
    )


def build_sections(settings: Settings) -> list[Section]:
    """Build every section of the exported page from the current cache,
    mirroring the chapters of ``colorado_river_story.ipynb``.
    """
    stations = load_snotel_stations(settings.cache_dir)

    map_layers = basin_map_layers(settings.cache_dir, stations)
    overview = Section(
        heading=None,
        paragraphs=[
            "Seven states and Mexico share water that starts as snow in the Rocky "
            "Mountains, travels a thousand miles through two of the country's "
            "largest reservoirs, and has been promised out faster than the river "
            "delivers it.",
            "The Colorado River drains the Upper Basin's high mountain snowpack, "
            "through Cisco and Lees Ferry, into the two great reservoirs -- Lake "
            "Powell and Lake Mead -- that store it for the Lower Basin and Mexico. "
            "The 54 SNOTEL stations that make up this story's snow index (out of "
            "137 in the basin) sit filled in below; the rest are shown hollow for "
            "context.",
        ],
        figures=[build_basin_map(map_layers)],
    )

    supply = annual_supply(settings.cache_dir)
    paleo = paleo_supply(settings.cache_dir)
    ch1 = Section(
        heading="1 · Promised more than it has",
        paragraphs=[
            "In 1922, seven states divided the Colorado River's flow before anyone "
            "had measured it through a full wet-dry cycle. They allocated 16.5 "
            "million acre-feet a year -- 7.5 MAF each to the upper and lower "
            "basins, plus 1.5 MAF promised to Mexico in 1944. The river has rarely "
            "delivered that much.",
            describe_supply_vs_compact(supply),
        ],
        figures=[build_supply_vs_compact(supply), build_paleo_context(paleo, supply)],
    )

    snow_daily = snow_index_daily(settings.cache_dir, stations)
    snow_envelope = snow_index_envelope(snow_daily)
    snow_year = snow_annual(settings.cache_dir, stations, snow_daily)
    latest_snow = snow_year.dropna(subset=["peak_swe_in"]).iloc[-1]
    ch2 = Section(
        heading="2 · It starts as snow",
        paragraphs=[
            "Every drop of Colorado River water begins as snow in the mountains of "
            "Colorado, Wyoming, Utah, and New Mexico. A fixed set of 54 "
            "long-record SNOTEL stations tracks the basin's snow water equivalent "
            "(SWE) -- the depth of water the snowpack would produce if it melted "
            "all at once -- every winter back to the early 1980s.",
            describe_peak_swe(latest_snow),
        ],
        figures=[
            build_snow_spaghetti(snow_daily, snow_envelope),
            build_peak_swe_bar(snow_daily),
        ],
    )

    runoff = runoff_vs_snow(settings.cache_dir, snow_year)
    latest_runoff = runoff.iloc[-1]
    efficiency_trend = theil_sen_trend(
        runoff["water_year"], runoff["runoff_efficiency"]
    )
    ch3 = Section(
        heading="3 · Same snow, less river",
        paragraphs=[
            "A given amount of mountain snowpack no longer turns into the same "
            "amount of spring runoff it once did. Warmer soils and thirstier "
            "vegetation intercept more of the melt before it reaches a gauge, so "
            "the relationship between peak SWE and the Apr-Jul runoff pulse at "
            "Lake Powell has been sliding for decades.",
            describe_runoff_year(latest_runoff),
            describe_trend(efficiency_trend, "Spring runoff efficiency"),
        ],
        figures=[build_efficiency_trend(runoff)],
    )

    timing = timing_annual(settings.cache_dir, snow_year)
    cov_trend = theil_sen_trend(
        timing.dropna(subset=["cisco_center_of_volume_doy"])["water_year"],
        timing.dropna(subset=["cisco_center_of_volume_doy"])[
            "cisco_center_of_volume_doy"
        ],
    )
    ch4 = Section(
        heading="4 · Earlier and faster",
        paragraphs=[
            "Snowmelt no longer waits for summer. Warmer springs pull the peak "
            "snowpack, the melt-out, and the resulting streamflow earlier in the "
            "year than they ran a century ago -- and once the water starts "
            "moving, it moves through faster.",
            describe_timing_trend(cov_trend, "The Cisco half-flow date"),
        ],
        figures=[build_timing_trends(timing)],
    )

    regimes = lees_ferry_regimes(settings.cache_dir)
    ch5 = Section(
        heading="5 · Dams flatten the river",
        paragraphs=[
            "Before Glen Canyon Dam, Lees Ferry's flow followed the snowmelt: a "
            "sharp spring peak, then a long summer and winter recession. The dam "
            "turned that river into a reservoir release, timed to power demand "
            "and downstream deliveries instead of the snowpack. The seasonal "
            "pulse that shaped the canyon for millennia is now a managed, nearly "
            "flat line.",
            describe_dam_effect(regimes.annual_peaks),
        ],
        figures=[build_before_after_dam(regimes)],
    )

    storage = reservoir_storage(settings.cache_dir)
    ch6 = Section(
        heading="6 · The bank account",
        paragraphs=[
            "Lake Powell and Lake Mead exist to smooth the difference between a "
            "variable river and steady promises: they hold water in wet years to "
            "cover dry ones. That buffer has been drawn down for a quarter "
            "century, as demand and a drying climate have outpaced what the "
            "river delivers -- turning a bank account built for occasional "
            "shortfalls into one running low year after year.",
            describe_reservoir_drawdown(storage),
        ],
        figures=[build_reservoir_storage(storage)],
    )

    kpi_table = kpis(snow_year, runoff, storage, supply, as_of=date.today())
    glance = Section(
        heading="2026 at a glance",
        paragraphs=[
            "A snapshot of where the system stands right now, against every "
            "other year on record.",
        ],
        figures=[build_kpi_panel(kpi_table)],
    )

    return [overview, ch1, ch2, ch3, ch4, ch5, ch6, glance]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=Path("site_export"))
    parser.add_argument(
        "--refresh",
        choices=list(get_args(RefreshMode)),
        default="offline",
    )
    args = parser.parse_args()
    refresh_mode: RefreshMode = args.refresh

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    settings = Settings()
    refresh_story(refresh_mode, settings)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sections = build_sections(settings)
    out_path = output_dir / OUTPUT_FILENAME
    out_path.write_text(_render_fragment(sections), encoding="utf-8")
    logger.info("wrote %s (%d sections)", out_path, len(sections))


if __name__ == "__main__":
    main()
