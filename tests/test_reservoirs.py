import pytest

from colorado_river_viz.reservoirs import LAKE_MEAD, LAKE_POWELL, ReservoirProfile


@pytest.mark.parametrize("reservoir", [LAKE_POWELL, LAKE_MEAD])
def test_elevation_thresholds_are_ordered(reservoir: ReservoirProfile) -> None:
    assert (
        reservoir.dead_pool_ft
        < reservoir.minimum_power_pool_ft
        < reservoir.full_pool_elevation_ft
    )


@pytest.mark.parametrize("reservoir", [LAKE_POWELL, LAKE_MEAD])
def test_elevation_and_storage_catalog_items_are_distinct(
    reservoir: ReservoirProfile,
) -> None:
    assert reservoir.elevation_catalog_item_id != reservoir.storage_catalog_item_id
