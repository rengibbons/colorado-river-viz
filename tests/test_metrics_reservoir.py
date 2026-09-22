from __future__ import annotations

import pandas as pd
import pytest

from colorado_river_viz.metrics.reservoir import (
    combined_storage,
    ft_above_min_power_pool,
    pct_full,
    single_reservoir_storage,
)
from colorado_river_viz.reservoirs import LAKE_MEAD, LAKE_POWELL


def test_pct_full_is_storage_over_full_pool_capacity() -> None:
    result = pct_full(pd.Series([LAKE_POWELL.full_pool_capacity_af / 2]), LAKE_POWELL)

    assert result.iloc[0] == pytest.approx(50.0)


@pytest.mark.parametrize(
    ("elevation_ft", "expected"), [(3490, 0.0), (3500, 10.0), (3480, -10.0)]
)
def test_ft_above_min_power_pool_is_relative_to_the_threshold(
    elevation_ft: float, expected: float
) -> None:
    result = ft_above_min_power_pool(pd.Series([elevation_ft]), LAKE_POWELL)

    assert result.iloc[0] == pytest.approx(expected)


def test_single_reservoir_storage_merges_elevation_and_storage_on_date() -> None:
    dates = pd.date_range("2020-01-01", periods=3)
    elevation = pd.DataFrame({"date": dates, "value": [3500.0, 3501.0, 3502.0]})
    storage = pd.DataFrame({"date": dates, "value": [10_000_000.0] * 3})

    result = single_reservoir_storage(elevation, storage, LAKE_POWELL)

    assert list(result.columns) == [
        "date",
        "reservoir",
        "storage_af",
        "pct_full",
        "elevation_ft",
        "ft_above_min_power_pool",
    ]
    assert (result["reservoir"] == "Lake Powell").all()
    assert result["ft_above_min_power_pool"].tolist() == pytest.approx(
        [10.0, 11.0, 12.0]
    )


def test_combined_storage_only_covers_days_both_reservoirs_report() -> None:
    powell = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "storage_af": [10_000_000.0, 11_000_000.0],
        }
    )
    mead = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-01"]), "storage_af": [8_000_000.0]}
    )

    result = combined_storage(powell, mead, LAKE_POWELL, LAKE_MEAD)

    assert len(result) == 1
    assert result.iloc[0]["storage_af"] == pytest.approx(18_000_000.0)
    expected_capacity = (
        LAKE_POWELL.full_pool_capacity_af + LAKE_MEAD.full_pool_capacity_af
    )
    assert result.iloc[0]["pct_full"] == pytest.approx(
        100 * 18_000_000.0 / expected_capacity
    )
