"""Published datasets (decision 0008) and basin outlines (decision 0015).

- Reclamation's naturalized flow at Lees Ferry, water years 1906 onward:
  https://www.usbr.gov/lc/region/g4000/NaturalFlow/provisional.html
- Meko et al. (2007) tree-ring reconstruction of Lees Ferry flow, 762-2005:
  https://www.treeflow.info/content/colorado-r-lees-ferry-az-meko
  Meko, D.M., C.A. Woodhouse, C.H. Baisan, T. Knight, J.J. Lukas, M.K. Hughes,
  and M.W. Salzer. 2007. Medieval drought in the upper Colorado River Basin.
  Geophysical Research Letters 34, L10705.
- USGS Watershed Boundary Dataset HUC2 outlines, simplified to about 2 km.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd

from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import HttpClient, get_json, get_response
from colorado_river_viz.schema import AnnualStatus, annual_frame

NATURAL_FLOW_URL = (
    "https://www.usbr.gov/lc/region/g4000/NaturalFlow/LFnatFlow1906-2024.2024.9.12.xlsx"
)
MEKO_RECON_URL = "https://www.treeflow.info/sites/default/files/coloradoleesmeko_0.txt"
WBD_HUC2_QUERY_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/1/query"
)

NATURAL_FLOW_SERIES_ID = "lees_ferry_natural_flow_wy"
MEKO_RECON_SERIES_ID = "meko_2007_lees_ferry_recon"

_NATURAL_FLOW_SHEET = "Water Year"
_NATURAL_FLOW_TITLE = "WY Lees Ferry Natural Flow"
_FINAL_PERIOD_FOOTER = re.compile(r"^1906-(\d{4}) average$")
_MEKO_HEADER = ["Year", "Recon", "Observed"]
_MEKO_MISSING = -9999


def download_file(client: HttpClient, url: str, dest_dir: Path) -> Path:
    """Save the file at ``url`` into ``dest_dir`` byte-for-byte, and return its path.

    The file keeps its original name. It is written to a temporary name first and
    then moved into place, so an interrupted download never leaves a partial file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / url.rsplit("/", 1)[-1]
    partial = destination.with_name(f"{destination.name}.tmp")
    partial.write_bytes(get_response(client, url).content)
    partial.replace(destination)
    return destination


def parse_natural_flow_xlsx(path: Path) -> pd.DataFrame:
    """Parse the ``Water Year`` sheet of Reclamation's Lees Ferry natural-flow file.

    Rows are ``(year, acre-feet)`` between a three-row header and footer rows
    with period averages. Reclamation's footer averages cover only the years it
    considers final (e.g. "1906-2020 average"), so every year after that is
    marked ``provisional``.
    """
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(workbook[_NATURAL_FLOW_SHEET].iter_rows(values_only=True))
    except KeyError as error:
        raise UnexpectedSourceFormatError(
            f"{path.name}: no {_NATURAL_FLOW_SHEET!r} sheet"
        ) from error
    finally:
        workbook.close()

    if len(rows) < 3 or rows[1][1] != _NATURAL_FLOW_TITLE or rows[2][1] != "(AF)":
        raise UnexpectedSourceFormatError(f"{path.name}: unexpected header rows")

    years_and_values = [
        (row[0], row[1])
        for row in rows[3:]
        if isinstance(row[0], int) and isinstance(row[1], int | float)
    ]
    final_through = _final_through_year(rows, path)
    statuses: list[AnnualStatus] = [
        "final" if year <= final_through else "provisional"
        for year, _ in years_and_values
    ]
    return annual_frame(
        series_id=NATURAL_FLOW_SERIES_ID,
        water_years=[year for year, _ in years_and_values],
        values_af=[float(value) for _, value in years_and_values],
        statuses=statuses,
    )


def _final_through_year(rows: list[tuple[Any, ...]], path: Path) -> int:
    for row in rows:
        match = _FINAL_PERIOD_FOOTER.match(str(row[0]).strip())
        if match:
            return int(match.group(1))
    raise UnexpectedSourceFormatError(f"{path.name}: no '1906-YYYY average' footer")


def parse_meko_recon_txt(path: Path) -> pd.DataFrame:
    """Parse the Meko et al. (2007) reconstruction; ``-9999`` becomes NaN.

    Only the ``Recon`` column is kept. ``Observed`` is an older copy of
    Reclamation's natural flow, which the current published file supersedes.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(
        (i for i, line in enumerate(lines) if line.split()[:1] == ["Year"]), None
    )
    if header_index is None or lines[header_index].split() != _MEKO_HEADER:
        raise UnexpectedSourceFormatError(f"{path.name}: no 'Year Recon Observed' row")

    table = [line.split() for line in lines[header_index + 1 :] if line.strip()]
    if any(len(fields) != len(_MEKO_HEADER) for fields in table):
        raise UnexpectedSourceFormatError(f"{path.name}: ragged data rows")
    recon = np.array([float(fields[1]) for fields in table])
    recon[recon == _MEKO_MISSING] = np.nan
    return annual_frame(
        series_id=MEKO_RECON_SERIES_ID,
        water_years=[int(fields[0]) for fields in table],
        values_af=recon.tolist(),
        statuses=["final"] * len(table),
    )


def fetch_wbd_huc2_geojson(client: HttpClient, huc2: str) -> dict[str, Any]:
    """Fetch one HUC2 region's outline as a simplified GeoJSON FeatureCollection."""
    geojson: dict[str, Any] = get_json(
        client,
        WBD_HUC2_QUERY_URL,
        {
            "where": f"huc2='{huc2}'",
            "outFields": "huc2,name",
            "returnGeometry": "true",
            "maxAllowableOffset": "0.02",
            "outSR": "4326",
            "f": "geojson",
        },
    )
    features = geojson.get("features") or []
    if len(features) != 1 or features[0]["properties"].get("huc2") != huc2:
        raise UnexpectedSourceFormatError(f"WBD HUC2 {huc2}: expected one feature")
    return geojson
