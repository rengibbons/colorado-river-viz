import numpy as np
import pandas as pd
import pytest

from colorado_river_viz.errors import UnexpectedSourceFormatError
from colorado_river_viz.schema import (
    CANONICAL_COLUMNS,
    canonical_frame,
    empty_canonical_frame,
)


def test_truncates_timestamps_to_dates_and_sorts() -> None:
    frame = canonical_frame(
        series_id="s",
        dates=pd.DatetimeIndex(["2026-01-02 07:00", "2026-01-01 07:00"]),
        values=pd.Series([2.0, 1.0]),
        unit="ft",
        approval="unknown",
    )
    assert frame["date"].tolist() == [
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-02"),
    ]
    assert frame["value"].tolist() == [1.0, 2.0]


def test_drops_rows_without_a_value() -> None:
    frame = canonical_frame(
        series_id="s",
        dates=pd.date_range("2026-01-01", periods=3),
        values=pd.Series([1.0, np.nan, 3.0]),
        unit="cfs",
        approval="unknown",
    )
    assert len(frame) == 2


def test_rejects_duplicate_dates() -> None:
    with pytest.raises(UnexpectedSourceFormatError):
        canonical_frame(
            series_id="s",
            dates=pd.DatetimeIndex(["2026-01-01 00:00", "2026-01-01 07:00"]),
            values=pd.Series([1.0, 2.0]),
            unit="cfs",
            approval="unknown",
        )


def test_rejects_unknown_approval_values() -> None:
    with pytest.raises(UnexpectedSourceFormatError):
        canonical_frame(
            series_id="s",
            dates=pd.date_range("2026-01-01", periods=1),
            values=pd.Series([1.0]),
            unit="cfs",
            approval=pd.Series(["maybe"]),
        )


def test_empty_frame_has_the_canonical_columns() -> None:
    assert tuple(empty_canonical_frame().columns) == CANONICAL_COLUMNS
