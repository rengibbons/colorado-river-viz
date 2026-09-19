"""Runtime configuration, read from ``CRV_*`` environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from colorado_river_viz.constants import REPO_ROOT


class Settings(BaseSettings):
    """Pipeline settings.

    ``cache_dir`` defaults to ``<repo>/data/cache`` rather than a path relative to
    the working directory, so notebooks (which run from ``notebooks/``) and
    scripts share one cache.
    """

    model_config = SettingsConfigDict(env_prefix="CRV_", frozen=True)

    cache_dir: Path = REPO_ROOT / "data" / "cache"
    usgs_api_key: SecretStr | None = None
    request_timeout_seconds: float = 60.0
    max_retries: int = 5
