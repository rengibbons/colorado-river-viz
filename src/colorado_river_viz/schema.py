"""The canonical long-format schema shared by every cached daily series (design §4).

In memory, ``date`` is a midnight ``datetime64[ns]`` column so pandas date logic
works directly; the cache stores it as parquet ``date32``.
"""

from __future__ import annotations

from typing import Literal, get_args

import pandas as pd

from colorado_river_viz.errors import UnexpectedSourceFormatError

Unit = Literal["cfs", "af", "ft", "in"]
Approval = Literal["approved", "provisional", "unknown"]

CANONICAL_COLUMNS = ("series_id", "date", "value", "unit", "approval")


def canonical_frame(
    series_id: str,
    dates: pd.Series[pd.Timestamp] | pd.DatetimeIndex,
    values: pd.Series[float],
    unit: Unit,
    approval: pd.Series[str] | Approval,
) -> pd.DataFrame:
    """Assemble a canonical daily frame, sorted by date, with NaN values dropped.

    ``dates`` may carry times of day; they are truncated to the calendar date.
    Raises ``UnexpectedSourceFormatError`` if a date appears twice.
    """
    frame = pd.DataFrame(
        {
            "series_id": series_id,
            "date": pd.DatetimeIndex(dates).normalize().as_unit("ns"),
            "value": pd.to_numeric(values.to_numpy(), errors="raise").astype(float),
            "unit": unit,
            "approval": approval
            if isinstance(approval, str)
            else approval.to_numpy(dtype=str),
        }
    )
    frame = frame.dropna(subset=["value"]).sort_values("date", ignore_index=True)
    if frame["date"].duplicated().any():
        raise UnexpectedSourceFormatError(f"{series_id}: duplicate dates in source")
    unknown_approvals = set(frame["approval"]) - set(get_args(Approval))
    if unknown_approvals:
        raise UnexpectedSourceFormatError(
            f"{series_id}: unexpected approval values {sorted(unknown_approvals)}"
        )
    return frame.astype(
        {"series_id": "category", "unit": "string", "approval": "string"}
    )


def empty_canonical_frame() -> pd.DataFrame:
    """Return a canonical frame with no rows but the right columns and dtypes."""
    return pd.DataFrame(
        {
            "series_id": pd.Series(dtype="category"),
            "date": pd.Series(dtype="datetime64[ns]"),
            "value": pd.Series(dtype=float),
            "unit": pd.Series(dtype="string"),
            "approval": pd.Series(dtype="string"),
        }
    )
