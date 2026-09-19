"""Physical constants, story-wide configuration, and fixed reference periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CFS_DAY_TO_AF = 1.983471
"""Acre-feet delivered by a flow of 1 cubic foot per second sustained for one day."""

AF_PER_MAF = 1_000_000

COMPACT_APPORTIONMENT_MAF = 16.5
"""Water apportioned by the 1922 Colorado River Compact (7.5 + 7.5 MAF) plus the
1.5 MAF promised to Mexico in the 1944 treaty."""

SNOTEL_INDEX_RECORD_START = date(1980, 10, 1)
"""A SNOTEL station joins the fixed snow index only if its daily SWE record
begins on or before this date (decision 0013)."""

COMPLETE_WATER_YEAR_MIN_COVERAGE = 0.98
"""Fraction of a water year's days that must have data for annual totals and
timing metrics to count that year (decision 0019)."""


@dataclass(frozen=True, slots=True)
class YearSpan:
    """An inclusive range of water years."""

    first: int
    last: int

    def contains(self, water_year: int) -> bool:
        return self.first <= water_year <= self.last


NORMALS_PERIOD = YearSpan(1991, 2020)


@dataclass(frozen=True, slots=True)
class HighlightYears:
    """Water years drawn in color against the gray of all other years (0012)."""

    low: tuple[int, ...]
    high: tuple[int, ...]
    present: int

    @property
    def all(self) -> tuple[int, ...]:
        return tuple(sorted(self.low + self.high))


HIGHLIGHT_YEARS = HighlightYears(
    low=(1981, 2002, 2012, 2018, 2026),
    high=(1985, 2011, 2019, 2023),
    present=2026,
)
