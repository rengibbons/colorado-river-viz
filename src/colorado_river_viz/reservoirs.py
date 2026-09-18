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
    full_pool_elevation_ft: float
    minimum_power_pool_ft: float  # elevation below which turbines can't generate power
    dead_pool_ft: float  # elevation below which water can't be released by gravity


LAKE_POWELL = ReservoirProfile(
    name="Lake Powell",
    dam_name="Glen Canyon Dam",
    elevation_catalog_item_id=508,
    storage_catalog_item_id=509,
    full_pool_capacity_af=24_300_000,
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
    full_pool_elevation_ft=1_219.64,
    minimum_power_pool_ft=950,
    dead_pool_ft=895,
)
