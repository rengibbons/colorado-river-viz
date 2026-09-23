import math
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from colorado_river_viz import published
from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.http_session import DataSource, build_client
from colorado_river_viz.published import (
    download_file,
    fetch_wbd_huc2_geojson,
    parse_meko_recon_txt,
    parse_natural_flow_xlsx,
)
from colorado_river_viz.settings import Settings
from tests.conftest import ScriptedResponse, ScriptedServer

FIXTURES = Path(__file__).parent / "fixtures"


def _write_natural_flow_workbook(
    path: Path,
    title: str = "WY Lees Ferry Natural Flow",
    footer: str = "1906-2020 average",
) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Water Year"
    sheet.append(["Last Updated 9/12/2024"])
    sheet.append([None, title])
    sheet.append([None, "(AF)"])
    for year, value in [(1906, 18_214_678), (2020, 9_887_593), (2021, 7_152_000)]:
        sheet.append([year, value])
    sheet.append([])
    sheet.append([footer, 14_737_285.43])
    sheet.append([])
    sheet.append(["1991-2020 average", 13_494_713.9])
    workbook.create_sheet("Calendar Year")
    workbook.save(path)
    return path


def test_natural_flow_skips_header_and_footer_rows(tmp_path: Path) -> None:
    flow = parse_natural_flow_xlsx(_write_natural_flow_workbook(tmp_path / "nf.xlsx"))

    assert flow["water_year"].tolist() == [1906, 2020, 2021]
    assert flow["value_af"].tolist() == [18_214_678.0, 9_887_593.0, 7_152_000.0]


def test_natural_flow_years_after_the_final_period_are_provisional(
    tmp_path: Path,
) -> None:
    flow = parse_natural_flow_xlsx(_write_natural_flow_workbook(tmp_path / "nf.xlsx"))

    assert flow["status"].tolist() == ["final", "final", "provisional"]


@pytest.mark.parametrize(
    "workbook_kwargs",
    [{"title": "Lees Ferry Flow (renamed)"}, {"footer": "long-term average"}],
)
def test_natural_flow_rejects_a_changed_layout(
    tmp_path: Path, workbook_kwargs: dict[str, str]
) -> None:
    path = _write_natural_flow_workbook(tmp_path / "nf.xlsx", **workbook_kwargs)
    with pytest.raises(UnexpectedSourceFormatError):
        parse_natural_flow_xlsx(path)


def test_meko_reads_recon_column_and_maps_missing_to_nan() -> None:
    recon = parse_meko_recon_txt(FIXTURES / "meko_recon_excerpt.txt")

    by_year = dict(zip(recon["water_year"], recon["value_af"], strict=True))
    assert by_year[762] == 16_355_515.0
    assert by_year[2002] == 4_464_679.0
    assert math.isnan(by_year[767])
    assert recon["water_year"].is_monotonic_increasing
    assert set(recon["status"]) == {"final"}


def test_meko_rejects_a_changed_header(tmp_path: Path) -> None:
    text = (FIXTURES / "meko_recon_excerpt.txt").read_text()
    changed = tmp_path / "meko.txt"
    changed.write_text(text.replace("Year\t   Recon  Observed", "Year Flow Observed"))
    with pytest.raises(UnexpectedSourceFormatError):
        parse_meko_recon_txt(changed)


def _outline(huc2: str) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"huc2": huc2, "name": "Upper Colorado Region"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-110, 40], [-106, 40], [-106, 37], [-110, 40]]],
                },
            }
        ],
    }


def test_wbd_outline_is_returned_as_geojson(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(published, "WBD_HUC2_QUERY_URL", scripted_server.base_url)
    scripted_server.script = [ScriptedResponse(body=_outline("14"))]

    geojson = fetch_wbd_huc2_geojson(
        build_client(DataSource.PUBLISHED, fast_settings), "14"
    )

    assert geojson["features"][0]["properties"]["huc2"] == "14"


def test_wbd_rejects_a_response_for_the_wrong_region(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(published, "WBD_HUC2_QUERY_URL", scripted_server.base_url)
    scripted_server.script = [ScriptedResponse(body=_outline("15"))]

    with pytest.raises(UnexpectedSourceFormatError):
        fetch_wbd_huc2_geojson(build_client(DataSource.PUBLISHED, fast_settings), "14")


def test_download_saves_the_file_verbatim_under_its_own_name(
    scripted_server: ScriptedServer, fast_settings: Settings, tmp_path: Path
) -> None:
    scripted_server.script = [ScriptedResponse(body={"a": 1})]
    url = f"{scripted_server.base_url}/files/LFnatFlow1906-2024.2024.9.12.xlsx"

    saved = download_file(
        build_client(DataSource.PUBLISHED, fast_settings), url, tmp_path / "downloads"
    )

    assert saved.name == "LFnatFlow1906-2024.2024.9.12.xlsx"
    assert saved.read_bytes() == b'{"a": 1}'
    assert list(saved.parent.iterdir()) == [saved]
