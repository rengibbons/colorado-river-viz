"""Reservoir storage and elevation metrics (design §6.8).

RISE storage is dead-pool referenced (02-research §6), so ``pct_full`` is RISE
storage divided by ``full_pool_capacity_af`` directly, with no rebasing.
Comparisons against minimum power pool are made by elevation, not by
``minimum_power_pool_storage_af`` -- Lake Powell's RISE storage runs 2-8% above
the 2017 area-capacity table at the same elevation, so a storage-based
comparison would be biased.
"""

from __future__ import annotations

import pandas as pd

from colorado_river_viz.reservoirs import ReservoirProfile

COMBINED_CAPACITY_AF_COLUMN = "combined_full_pool_capacity_af"


def pct_full(
    storage_af: pd.Series[float], reservoir: ReservoirProfile
) -> pd.Series[float]:
    """Storage as a percentage of ``full_pool_capacity_af``."""
    return 100 * storage_af / reservoir.full_pool_capacity_af


def ft_above_min_power_pool(
    elevation_ft: pd.Series[float], reservoir: ReservoirProfile
) -> pd.Series[float]:
    """Elevation above (or, negative, below) minimum power pool."""
    return elevation_ft - reservoir.minimum_power_pool_ft


def single_reservoir_storage(
    elevation: pd.DataFrame, storage: pd.DataFrame, reservoir: ReservoirProfile
) -> pd.DataFrame:
    """Merge one reservoir's daily elevation and storage into the design §6.8 shape.

    Columns: ``date``, ``reservoir``, ``storage_af``, ``pct_full``,
    ``elevation_ft``, ``ft_above_min_power_pool``.
    """
    merged = (
        elevation[["date", "value"]]
        .rename(columns={"value": "elevation_ft"})
        .merge(
            storage[["date", "value"]].rename(columns={"value": "storage_af"}),
            on="date",
            how="inner",
        )
    )
    return pd.DataFrame(
        {
            "date": merged["date"],
            "reservoir": reservoir.name,
            "storage_af": merged["storage_af"],
            "pct_full": pct_full(merged["storage_af"], reservoir),
            "elevation_ft": merged["elevation_ft"],
            "ft_above_min_power_pool": ft_above_min_power_pool(
                merged["elevation_ft"], reservoir
            ),
        }
    )


def combined_storage(
    powell: pd.DataFrame,
    mead: pd.DataFrame,
    powell_profile: ReservoirProfile,
    mead_profile: ReservoirProfile,
) -> pd.DataFrame:
    """Combined Powell + Mead storage, on days both reservoirs report.

    Columns: ``date``, ``reservoir`` (``"Combined"``), ``storage_af``,
    ``pct_full``. Powell storage begins in 1964, so this starts there.
    """
    merged = powell[["date", "storage_af"]].merge(
        mead[["date", "storage_af"]], on="date", suffixes=("_powell", "_mead")
    )
    combined_capacity = (
        powell_profile.full_pool_capacity_af + mead_profile.full_pool_capacity_af
    )
    storage_af = merged["storage_af_powell"] + merged["storage_af_mead"]
    return pd.DataFrame(
        {
            "date": merged["date"],
            "reservoir": "Combined",
            "storage_af": storage_af,
            "pct_full": 100 * storage_af / combined_capacity,
        }
    )
