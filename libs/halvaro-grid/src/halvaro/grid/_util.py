"""Shared helpers of halvaro.grid: frame checks and timestamps."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError

FLAGS = ("ok", "estimated", "suspect", "missing")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}; load the source columns without renaming them")


def _utc(values: Any, what: str) -> pd.Series[Any]:
    """Timestamps as naive datetime64[ns] (the sources are UTC without zone). A text that pandas reads as one format is read as before; a text in several ISO forms (with and without seconds, with a T) that failed on its second form is
    read value by value as ISO 8601 (day first or month first spellings are never guessed per value); a time zone, a mix of zones, numbers or unreadable text raise FrameError."""
    s = pd.Series(values)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_datetime64_any_dtype(s) and s.notna().any():
        raise FrameError(f"{what} holds numbers, not timestamps")
    try:
        try:
            x = pd.to_datetime(s)
        except ValueError:
            if not (s.dtype == object or pd.api.types.is_string_dtype(s)):
                raise
            x = pd.to_datetime(s, format="ISO8601")
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what} holds a value that is not a timestamp: {e}") from None
    if getattr(x.dt, "tz", None) is not None:
        raise FrameError(f"{what} has a time zone; telemetry timestamps are UTC without zone")
    return x.astype("datetime64[ns]")


def _positive_interval(sensor: pd.DataFrame, what: str = "telemetry.sensor") -> None:
    iv = pd.to_numeric(sensor["interval_s"], errors="coerce")
    if not (iv > 0).all() or not np.isfinite(iv).all():
        raise FrameError(f"{what}.interval_s must be a positive number for every sensor")


def _checked_measurement(measurement: pd.DataFrame) -> pd.DataFrame:
    """The measurement frame with ts as datetime and a quality_flag from the four known flags; sorted by sensor and time. A duplicated slot or an unknown flag raises."""
    _need(measurement, ["sns_key", "ts", "value", "quality_flag"], "telemetry.measurement")
    out = measurement.assign(ts=_utc(measurement["ts"], "telemetry.measurement.ts").to_numpy())
    if out["ts"].isna().any() or out["sns_key"].isna().any():
        raise FrameError("telemetry.measurement has rows without a sns_key or a ts")
    bad = sorted(set(out["quality_flag"].dropna().unique()) - set(FLAGS))
    if bad or out["quality_flag"].isna().any():
        raise FrameError(f"telemetry.measurement.quality_flag holds {bad or ['null']}; the flags are {', '.join(FLAGS)}")
    if out.duplicated(["sns_key", "ts"]).any():
        raise FrameError("telemetry.measurement has more than one row for the same sensor and timestamp")
    return out.sort_values(["sns_key", "ts"], kind="stable").reset_index(drop=True)
