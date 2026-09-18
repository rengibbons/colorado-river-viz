"""Schematic reservoir geometry derived from official elevation-area-capacity tables.

These are illustrative, not surveyed shapes: both reservoirs are modeled as a
single circular cross-section whose radius at each elevation is set so its area
matches the real surface area at that elevation. This reproduces the true
"how much bigger does the reservoir get as it fills" story (from Reclamation's
own area-capacity tables) without requiring the actual bathymetric terrain
data, which is only available as multi-gigabyte GIS rasters.

The per-foot elevation, surface area (acres), and capacity (acre-feet) tables
in data/reservoir_area_capacity/ were extracted from:

- Lake Powell (elevation 3,130-3,709 ft, NGVD29): "Lake Powell, Colorado River
  Storage Project, Glen Canyon Unit, 2017 Area Capacity Tables" (Reclamation,
  2022), Area Table and Capacity Table at 1-Foot Increments.
  https://www.usbr.gov/uc/water/Lake_Powell_Area_Capacity_Table_Report_FINAL.pdf
- Lake Mead (elevation 895-1,228 ft): "2009 Lake Mead Area and Capacity
  Tables" (Reclamation), Table of Surface Area at 0.1-Foot Increments and
  Table of Available Capacity at 0.01-Foot Increments. The source capacity
  table is referenced to dead pool (895 ft) as zero; 2,547,000 acre-feet of
  dead storage (stated directly in the report) was added back to every row so
  capacity_af here is the actual reservoir volume, matching Lake Powell's
  table.
  https://www.usbr.gov/lc/region/g4000/LM_AreaCapacityTables2009.pdf

Lake Mead's table doesn't extend below 895 ft (dead pool), so the modeled
cross-section is truncated there rather than showing a fabricated deeper
floor.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from colorado_river_viz.reservoirs import ReservoirProfile

ACRES_TO_SQUARE_FEET = 43_560
FEET_TO_MILES = 1 / 5_280

REPO_ROOT = Path(__file__).resolve().parents[2]
AREA_CAPACITY_DATA_DIR = REPO_ROOT / "data" / "reservoir_area_capacity"

_AREA_CAPACITY_TABLE_FILENAMES = {
    "Lake Powell": "lake_powell_area_capacity_1ft.csv",
    "Lake Mead": "lake_mead_area_capacity_1ft.csv",
}


def load_area_capacity_table(reservoir: ReservoirProfile) -> pd.DataFrame:
    """Load the per-foot elevation/surface-area/capacity table for a reservoir.

    Returns a DataFrame sorted by elevation_ft with columns surface_area_acres
    and capacity_af.
    """
    filename = _AREA_CAPACITY_TABLE_FILENAMES[reservoir.name]
    table = pd.read_csv(AREA_CAPACITY_DATA_DIR / filename)
    return table.sort_values("elevation_ft").reset_index(drop=True)


def surface_area_at_elevation(table: pd.DataFrame, elevation_ft: float) -> float:
    """Interpolate surface area (acres) at a given elevation from the table."""
    return float(
        np.interp(elevation_ft, table["elevation_ft"], table["surface_area_acres"])
    )


def equivalent_radius_miles(surface_area_acres: float) -> float:
    """Radius (miles) of a circle with the given surface area (acres)."""
    area_sq_ft = surface_area_acres * ACRES_TO_SQUARE_FEET
    return float(np.sqrt(area_sq_ft / np.pi)) * FEET_TO_MILES


def schematic_perimeter_miles(
    table: pd.DataFrame, elevation_ft: float, n_points: int = 200
) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) coordinates in miles for a circular shoreline matching the real
    surface area at the given elevation, centered on the origin."""
    area_acres = surface_area_at_elevation(table, elevation_ft)
    radius_miles = equivalent_radius_miles(area_acres)
    angles = np.linspace(0, 2 * np.pi, n_points)
    return radius_miles * np.cos(angles), radius_miles * np.sin(angles)


def schematic_floor_profile_miles(
    table: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Half-width (miles) of the equivalent circular cross-section at each
    tabulated elevation (feet), for drawing a valley-shaped floor profile."""
    radii_miles = np.array(
        [equivalent_radius_miles(area) for area in table["surface_area_acres"]]
    )
    return radii_miles, table["elevation_ft"].to_numpy()
