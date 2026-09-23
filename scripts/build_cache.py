"""Build or refresh the local data cache used by the story notebook.

    uv run python scripts/build_cache.py                 # incremental (default)
    uv run python scripts/build_cache.py --mode full     # refetch everything

A first run fetches every series' full history (several minutes). It can be
interrupted and rerun: series that finished are kept and not fetched again.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import get_args

from colorado_river_viz.cache import RefreshMode, read_manifest, refresh_story
from colorado_river_viz.settings import Settings

logger = logging.getLogger("build_cache")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mode",
        choices=[mode for mode in get_args(RefreshMode) if mode != "offline"],
        default="incremental",
    )
    args = parser.parse_args()
    mode: RefreshMode = args.mode

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    settings = Settings()
    started = time.monotonic()
    specs = refresh_story(mode, settings)
    manifest = read_manifest(settings.cache_dir)
    total_rows = sum(manifest[spec.series_id].row_count for spec in specs)
    logger.info(
        "%s refresh done: %d series, %s rows, %.0f s, cache at %s",
        mode,
        len(specs),
        f"{total_rows:,}",
        time.monotonic() - started,
        settings.cache_dir,
    )


if __name__ == "__main__":
    main()
