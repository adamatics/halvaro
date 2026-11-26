"""Shared helpers of halvaro.finance: frame checks, cents, calendar days and the control accounts."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, PeriodError


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}; load the source columns without renaming them")


def _numeric(frame: pd.DataFrame, columns: Sequence[str], what: str, *, allow_null: Sequence[str] = ()) -> None:
    """The columns hold numbers (text that reads as a number, as astype(float) takes it, passes); another value raises FrameError naming the column and the value. A null passes only in a column of allow_null, else it is reported as a null."""
    for c in columns:
        s = frame[c]
        if c in allow_null:
            s = s[s.notna()]
        try:
            s.astype(float)
        except (ValueError, TypeError):
            bad = next((v for v in s if not pd.isna(v) and not _is_number(v)), None)      # a null is not the culprit when a text is in the column too
            if bad is None:
                raise FrameError(f"{what}.{c} has a null; it must hold numbers") from None
            raise FrameError(f"{what}.{c} must hold numbers, not {bad!r}") from None


def _is_number(v: Any) -> bool:
    if v is None or v is pd.NA:
        return False
    try:
        float(v)
    except (ValueError, TypeError):
        return False
    return True


def _cents(x: pd.Series) -> np.ndarray:
    """Integer cents of an amount column; a null amount raises."""
    v = x.to_numpy(dtype=float)
    if np.isnan(v).any():
        raise FrameError(f"{int(np.isnan(v).sum())} amounts are null; the ledger has no null amounts")
    return np.rint(v * 100).astype(np.int64)


def _round_half_away(v: np.ndarray) -> np.ndarray:
    return np.sign(v) * np.floor(np.abs(v) + 0.5)


def _day(as_of: Any, name: str = "as_of") -> pd.Timestamp:
    """A calendar day: dates, Timestamps and ISO text; a number, an unreadable text or a time zone raises PeriodError naming the argument (name, default as_of)."""
    if isinstance(as_of, (bool, int, float, np.number)):
        raise PeriodError(f"{name} {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise PeriodError(f"{name} {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise PeriodError(f"{name} {as_of!r} is not a date without a time zone")
    return d.normalize()


def _days(frame: pd.DataFrame, columns: Sequence[str], what: str) -> pd.DataFrame:
    """The columns as naive calendar days (missing stays NaT); an unreadable value or a time zone raises FrameError."""
    out = frame.copy()
    for c in columns:
        if pd.api.types.is_numeric_dtype(out[c]) and not pd.api.types.is_datetime64_any_dtype(out[c]) and out[c].notna().any():
            raise FrameError(f"{what}.{c} holds numbers, not dates")
        try:
            x = pd.to_datetime(out[c], format="mixed") if (out[c].dtype == object or pd.api.types.is_string_dtype(out[c])) else pd.to_datetime(out[c])
        except (ValueError, TypeError, OverflowError) as e:
            raise FrameError(f"{what}.{c} holds a value that is not a date: {e}") from None
        if getattr(x.dt, "tz", None) is not None:
            raise FrameError(f"{what}.{c} has a time zone; dates here are calendar days")
        out[c] = x.dt.normalize().astype("datetime64[ns]")
    return out


def _control(gl_account: pd.DataFrame, control_type: str) -> list[Any]:
    """Accounts of a control type (finance.gl_account.control_type); none found raises."""
    _need(gl_account, ["gl_key", "control_type"], "finance.gl_account")
    keys = sorted(gl_account.loc[gl_account["control_type"] == control_type, "gl_key"])
    if not keys:
        raise FrameError(f"finance.gl_account has no account with control_type {control_type!r}")
    return keys


def _entity_currency(opening_balance_item: pd.DataFrame) -> pd.Series:
    """Entity currency per le_key, taken from the opening items (the ledger is in the entity currency)."""
    _need(opening_balance_item, ["le_key", "currency"], "finance.opening_balance_item")
    cur = opening_balance_item.groupby("le_key")["currency"].first()
    if cur.empty:
        raise FrameError("finance.opening_balance_item is empty: the entity currencies are taken from it")
    return cur


def _opening(opening_balance_item: pd.DataFrame, gl_keys: Sequence[str]) -> pd.DataFrame:
    """The opening items of the given accounts with their dates as days; every item needs an item_ref."""
    _need(opening_balance_item, ["le_key", "gl_key", "item_ref", "document_date", "due_date", "amount", "currency", "cus_key", "sup_key"], "finance.opening_balance_item")
    ob = _days(opening_balance_item[opening_balance_item["gl_key"].isin(gl_keys)], ["document_date", "due_date"], "finance.opening_balance_item")
    if ob["item_ref"].isna().any():
        raise FrameError("opening items of a control account need an item_ref")
    return ob
