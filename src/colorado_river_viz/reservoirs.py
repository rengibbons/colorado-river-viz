"""Reference data for Colorado River reservoirs: RISE catalog items and critical
elevations, sourced from the Bureau of Reclamation.

Full-pool capacity figures are Reclamation's operational values (used for public
"percent full" reporting), not the higher figures from recent topobathymetric
resurveys that account for sediment already in the reservoirs.

Sources (all Bureau of Reclamation, usbr.gov):

- Minimum power pool and dead pool elevations: "Technical Appendix 15 - Dams and
  Electrical Power Resources," Post-2026 Colorado River Reservoir Operations DEIS
  (January 2026), p. 15-4 and p. 15-9 to 15-11.
  https://www.usbr.gov/ColoradoRiverBasin/post2026/draft-eis/docs/vol-3/P26-DEIS-TA-15.pdf
  - Glen Canyon Dam: "Water cannot be released from the penstocks below a Lake
    Powell elevation of 3,490 feet (which is known as the minimum power pool...)."
    The river outlet works - the last gravity-release point once the powerplant is
    unusable - sit at a centerline elevation of 3,374 feet. Reclamation does not use
    the term "dead pool" for Lake Powell in this document; secondary sources
    commonly round this figure to 3,370 feet.
  - Hoover Dam: "Effective power generation currently requires a minimum water
    elevation of 950 feet in Lake Mead... Below 895 feet, water reaches dead pool."
- Lake Powell active capacity (24,300,000 acre-feet) and full-pool elevation
  (3,700 feet, "top of active conservation... the normal operating level"):
  "Attachment B - Dams and Reservoirs Along the Lower Colorado River," and
  Technical Appendix 15 (above), p. 15-4, respectively.
  https://www.usbr.gov/lc/region/g4000/surplus1/pdf/Attachments/Attachment_B.pdf
  Capacity is commonly cited elsewhere as 24,322,000 acre-feet; this is the
  figure directly sourced from a Reclamation document.
- Lake Mead active capacity (26,120,000 acre-feet) and full-pool elevation
  ("top of joint use," rounded to 1,219.64 feet - the elevation at which
  capacity equals 26,120,000 acre-feet): "Lake Mead Reservoir Capacity
  Allocations" (2022).
  https://www.usbr.gov/lc/region/g4000/LakeMeadReservoirCapacityAllocations_2022.pdf
- Storage at minimum power pool, in acre-feet (`minimum_power_pool_storage_af`):
  read from each dam's official area-capacity table, then rebased so dead pool
  reads as zero acre-feet - the same convention the "percent full" figures above
  use (confirmed against live RISE data: at Lake Mead elevation 1,038.44 ft on
  2026-09-17, storage rebased this way gives ~6,841,000 acre-feet against a
  reported 6,870,680 acre-feet / 26.3% full - i.e. dead pool is the zero point
  reservoirs are reported "percent full" against, not the physical lakebed).
  - Lake Powell: capacity at 3,490 ft (5,454,712 af) minus capacity at 3,374 ft
    (1,788,412 af) = 3,666,300 af. "Lake Powell, Colorado River Storage Project,
    Glen Canyon Unit, 2017 Area Capacity Tables" (Reclamation, 2022), Capacity
    Table at 1-Foot Increments.
    https://www.usbr.gov/uc/water/Lake_Powell_Area_Capacity_Table_Report_FINAL.pdf
  - Lake Mead: available capacity at 950 ft, already referenced to dead pool
    (895 ft) as zero, is 2,006,000 af directly. "2009 Lake Mead Area and
    Capacity Tables" (Reclamation), Table of Available Capacity in 1,000
    Acre-Feet.
    https://www.usbr.gov/lc/region/g4000/LM_AreaCapacityTables2009.pdf
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReservoirProfile:
    """RISE catalog items and critical elevations for one reservoir."""

    name: str
    dam_name: str
    elevation_catalog_item_id: int
    storage_catalog_item_id: int
    full_pool_capacity_af: float
    minimum_power_pool_storage_af: float
    full_pool_elevation_ft: float
    minimum_power_pool_ft: float  # elevation below which turbines can't generate power
    dead_pool_ft: float  # elevation below which water can't be released by gravity


LAKE_POWELL = ReservoirProfile(
    name="Lake Powell",
    dam_name="Glen Canyon Dam",
    elevation_catalog_item_id=508,
    storage_catalog_item_id=509,
    full_pool_capacity_af=24_300_000,
    minimum_power_pool_storage_af=3_666_300,
    full_pool_elevation_ft=3_700,
    minimum_power_pool_ft=3_490,
    dead_pool_ft=3_374,
)

LAKE_MEAD = ReservoirProfile(
    name="Lake Mead",
    dam_name="Hoover Dam",
    elevation_catalog_item_id=6123,
    storage_catalog_item_id=6124,
    full_pool_capacity_af=26_120_000,
    minimum_power_pool_storage_af=2_006_000,
    full_pool_elevation_ft=1_219.64,
    minimum_power_pool_ft=950,
    dead_pool_ft=895,
)
