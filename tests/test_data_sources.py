from datetime import date

from colorado_river_viz.data_sources import DateRange


def test_date_range_stores_start_and_end() -> None:
    date_range = DateRange(start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert date_range.start == date(2026, 1, 1)
    assert date_range.end == date(2026, 1, 31)
