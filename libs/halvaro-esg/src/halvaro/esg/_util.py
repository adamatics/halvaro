"""Shared helpers of halvaro.esg: frame checks, calendar days and the provenance result."""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, make_envelope


@dataclasses.dataclass(frozen=True)
class Provenance(Envelope):
    """Envelope of a result that uses emission factors: the factor sets used and the VERIFY notes behind them."""

    factor_sets: tuple[str, ...] = ()
    verify_facts: tuple[str, ...] = ()


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}; load the source columns without renaming them")


def _day(value: Any, what: str) -> pd.Timestamp:
    """A calendar day from a date, a Timestamp, ISO text or a period 'YYYY-MM' (its first day); numbers and time zones raise FrameError."""
    if isinstance(value, (bool, int, float, np.number)):
        raise FrameError(f"{what} {value!r} is a number, not a date")
    try:
        d = pd.Timestamp(value + "-01") if isinstance(value, str) and len(value) == 7 else pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what} {value!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise FrameError(f"{what} {value!r} is not a date without a time zone")
    return d.normalize()


def _days(frame: pd.DataFrame, columns: Sequence[str], what: str) -> pd.DataFrame:
    """The columns as naive calendar days (null stays NaT); unreadable values or numbers raise FrameError."""
    out = frame.copy()
    for c in columns:
        if pd.api.types.is_numeric_dtype(out[c]) and not pd.api.types.is_datetime64_any_dtype(out[c]) and out[c].notna().any():
            raise FrameError(f"{what}.{c} holds numbers, not dates")
        try:
            x = pd.to_datetime(out[c], format="mixed") if (out[c].dtype == object or pd.api.types.is_string_dtype(out[c])) else pd.to_datetime(out[c])
            x.dt  # an object result (mixed time zone offsets) has no .dt
        except (ValueError, TypeError, OverflowError, AttributeError) as e:
            raise FrameError(f"{what}.{c} holds a value that is not a date: {e}") from None
        if getattr(x.dt, "tz", None) is not None:
            raise FrameError(f"{what}.{c} has a time zone; dates here are calendar days")
        out[c] = x.dt.normalize().astype("datetime64[ns]")
    return out


def _provenance(value: Any, function: str, rows: pd.DataFrame, *, sources: Sequence[str] = (), as_of: dt.date | None = None, warnings: Sequence[str] = ()) -> Provenance:
    """A Provenance for the factor rows used: synthetic is true unless a row says otherwise, status VERIFY+synthetic when the rows are synthetic and carry a VERIFY note."""
    synthetic = bool(rows["synthetic"].eq(True).all()) if len(rows) and "synthetic" in rows else True
    notes = rows["verify_note"] if len(rows) and "verify_note" in rows else pd.Series(dtype=object)
    verify = tuple(sorted({str(n) for n in notes.dropna() if "VERIFY" in str(n)}))
    noted_all = bool(len(notes) and notes.map(lambda n: isinstance(n, str) and "VERIFY" in n).all())
    status = ("VERIFY+synthetic" if noted_all else "synthetic") if synthetic else "VERIFY"           # a factor result is never 'ok': a row that is not synthetic still needs its verification
    sets = tuple(sorted({str(s) for s in rows["factor_set"].dropna()})) if len(rows) and "factor_set" in rows else ()
    env = make_envelope(value, function, sources=sources, as_of=as_of, warnings=warnings, cls=Provenance, factor_sets=sets, verify_facts=verify)
    return cast(Provenance, dataclasses.replace(env, status=status, synthetic=synthetic))


_LINE_COLS = ["le_key", "period", "scope", "category", "line_no", "kgco2e", "quantity", "efac_key", "method", "ghg_category", "restated_from_period", "supersedes_line_no", "is_superseded"]


_BASIS_COLS = ["le_key", "period", "scope", "category", "line_no", "is_superseded", "restated_from_period"]
_LINK_COLS = [*_BASIS_COLS, "supersedes_line_no"]


def _num(series: pd.Series) -> pd.Series:
    """A key column as float64 with NaN for null (Int64, int64 and float64 keys then merge on every pandas 2.x)."""
    return pd.Series(pd.to_numeric(series, errors="coerce").to_numpy(dtype=float, na_value=np.nan), index=series.index)


def _lines(L: pd.DataFrame, extra: Sequence[str] = (), base: Sequence[str] = _LINE_COLS) -> pd.DataFrame:
    """The emission lines checked for the columns the restatement logic needs; is_superseded must be a boolean without nulls and the line key unique."""
    _need(L, [*base, *extra], "energy-esg.emission_line")
    if L["is_superseded"].isna().any():
        raise FrameError("energy-esg.emission_line.is_superseded has nulls")
    if L.duplicated(["le_key", "period", "scope", "category", "line_no"]).any():
        raise FrameError("energy-esg.emission_line has more than one row for the same le_key, period, scope, category and line_no")
    return L


def _period_text(value: Any, what: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-" or not (value[:4].isascii() and value[:4].isdigit()) or not (value[5:].isascii() and value[5:].isdigit()) or not 1 <= int(value[5:]) <= 12:
        raise FrameError(f"{what} must be a period text like 2025-12, not {value!r}")
    return value


def _basis(L: pd.DataFrame, basis: str) -> pd.DataFrame:
    """The lines of a basis: current (superseded originals left out) or first_booked (restated lines left out)."""
    L = _lines(L, base=_BASIS_COLS)
    if basis == "current":
        return L[~L["is_superseded"].astype(bool)]
    if basis == "first_booked":
        return L[L["restated_from_period"].isna()]
    raise FrameError(f"basis must be 'current' or 'first_booked', not {basis!r}")
