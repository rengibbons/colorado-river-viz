from pathlib import Path

import pytest

from colorado_river_viz.constants import REPO_ROOT
from colorado_river_viz.settings import Settings


def test_defaults_put_cache_under_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CRV_CACHE_DIR", "CRV_USGS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.cache_dir == REPO_ROOT / "data" / "cache"
    assert settings.usgs_api_key is None


def test_reads_crv_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CRV_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("CRV_USGS_API_KEY", "abc123")
    monkeypatch.setenv("CRV_REQUEST_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("CRV_MAX_RETRIES", "2")

    settings = Settings()

    assert settings.cache_dir == tmp_path
    assert settings.usgs_api_key is not None
    assert settings.usgs_api_key.get_secret_value() == "abc123"
    assert settings.request_timeout_seconds == 12.5
    assert settings.max_retries == 2
