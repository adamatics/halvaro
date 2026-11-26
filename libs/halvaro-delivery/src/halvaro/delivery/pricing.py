"""Pricing: the price per supplier and item on a date and the gaps of the price list (plan 5.6).

Effective dating follows DA.REF.007: valid_from and valid_to are inclusive, a null valid_to is open. Prices stay in the currency of the row.
"""
from __future__ import annotations

from typing import Any, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, check_contiguity, rows_on

from ._guard import staged
from ._types import DateLike

_KB = ("DA.REF.007",)
_COLS = ["sup_key", "itm_key", "valid_from", "valid_to", "unit_price", "currency", "con_key", "change_reason"]
_SRC = tuple(f"procurement.price_list.{c}" for c in _COLS)
_ORACLE = "py:tests/test_procurement.py::test_price_list_no_overlap_and_indexation"


def _check(price_list: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(price_list, pd.DataFrame):
        raise FrameError(f"procurement.price_list must be a DataFrame, not {type(price_list).__name__}")
    missing = [c for c in _COLS if c not in price_list.columns]
    if missing:
        raise FrameError(f"procurement.price_list frame lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if price_list.columns.duplicated().any():
        raise FrameError("procurement.price_list has duplicate column names")
    if price_list[["sup_key", "itm_key", "valid_from"]].isna().any().any():
        raise FrameError("procurement.price_list has rows without sup_key, itm_key or valid_from")
    if len(price_list) and not pd.api.types.is_numeric_dtype(price_list["unit_price"]):
        raise FrameError("procurement.price_list.unit_price must be numeric")
    out = price_list.copy()
    for c in ("valid_from", "valid_to"):
        try:
            out[c] = pd.to_datetime(out[c]).dt.normalize()
        except (ValueError, TypeError, OverflowError) as e:
            raise FrameError(f"procurement.price_list.{c} holds a value that is not a date: {e}") from None
    return out


def _window_day(w: Any) -> pd.Timestamp:
    if isinstance(w, (bool, int, float, np.number)):
        raise FrameError(f"window {w!r} is a number, not a date")
    try:
        d = pd.Timestamp(w)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"window {w!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise FrameError(f"window {w!r} is not a date without a time zone")
    return d.normalize()


@staged(sources=_SRC, kb=_KB)
def price_list_on(price_list: pd.DataFrame, as_of: DateLike, *, sup_key: str | None = None, itm_key: str | None = None) -> pd.DataFrame:
    """Use this when you need the price per supplier and item that is valid on a date, optionally for one supplier and one item.

    A price row is valid when valid_from is on or before the date and valid_to is null or on or after it (DA.REF.007, inclusive). Prices stay in the currency of the row. Two valid rows for one supplier and item on the date raise AmbiguousKey (the generator test forbids it). A valid row without a unit_price raises FrameError (no price is never passed on as a missing number).

    Args:
        price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        sup_key: Optional keyword, one supplier key as text; only its prices are returned.
        itm_key: Optional keyword, one item key as text; only its prices are returned.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason, sorted by sup_key and itm_key, index reset.

    Raises:
        FrameError: price_list is not a DataFrame, lacks a needed column, has duplicate column names, has a row without sup_key, itm_key or valid_from, has a unit_price that is not numeric, or holds a valid_from or valid_to that is not a date; sup_key or itm_key is not text; as_of is a number, has a time zone or is not a date; a valid row has no unit_price.
        AmbiguousKey: two rows of one supplier and item are valid on the date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import price_list_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pl = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
        ...                    "valid_from": ["2025-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None],
        ...                    "unit_price": [10.0, 12.5], "currency": ["EUR", "EUR"], "con_key": [None, None], "change_reason": [None, "indexation"]})
        >>> price_list_on(pl, "2026-03-01", context=ctx)["unit_price"].tolist()
        [12.5]
        >>> price_list_on(pl, "2025-03-01", sup_key="SUP-900001", itm_key="ITM-900001", context=ctx)["unit_price"].tolist()
        [10.0]"""
    p = _check(price_list)
    for name, v in (("sup_key", sup_key), ("itm_key", itm_key)):
        if v is not None and not isinstance(v, str):
            raise FrameError(f"{name} is one key as text, not {type(v).__name__}")
    if sup_key is not None:
        p = p[p["sup_key"] == sup_key]
    if itm_key is not None:
        p = p[p["itm_key"] == itm_key]
    if isinstance(as_of, (bool, int, float, np.number)):
        raise FrameError(f"as_of {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError) as e:
        raise FrameError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise FrameError(f"as_of {as_of!r} is not a date without a time zone")
    out = rows_on(p, d.normalize(), key=["sup_key", "itm_key"])
    if out["unit_price"].isna().any():
        bad = out[out["unit_price"].isna()].iloc[0]
        raise FrameError(f"procurement.price_list has no unit_price for {bad['sup_key']}, {bad['itm_key']} (valid from {bad['valid_from'].date()}) on {d.date()}")
    return out[_COLS].sort_values(["sup_key", "itm_key"]).reset_index(drop=True)


class PriceGaps(NamedTuple):
    """Result of price_gaps: the contiguity violations, the days without a valid price per supplier and item and the pairs whose currency changes between two rows."""

    violations: pd.DataFrame
    gaps: pd.DataFrame
    currency_changes: pd.DataFrame


@staged(sources=_SRC, kb=_KB, oracle=_ORACLE)
def price_gaps(price_list: pd.DataFrame, *, window: tuple[DateLike, DateLike] | None = None) -> PriceGaps:
    """Use this when you need to check the effective dating of the price list: the violations, the periods without a valid price per supplier and item, and the currency changes.

    The result has three parts. Violations of effective dating per supplier and item (reversed, two open rows, an open row followed by another, overlap, gap; core check_contiguity, convention day_after). The periods without a valid price: sup_key, itm_key, gap_start, gap_end, days (a row starts after the latest end of the rows before it plus one day; nested or overlapping rows do not create a false gap). And currency_changes (a pair whose currency differs between consecutive rows; a price step across currencies is not comparable). The release test only forbids duplicates of the start date (3.4), so gaps can exist.

    Two modes, and they do not give the same answer about the same pair:
    - Without `window` only the holes between two rows of a pair are reported (internal gaps). The days before a pair's first row and the days after its last row are never reported, so a pair whose
      last row is closed (valid_to set) and ended long ago has no gap, although price_list_on of a later date returns no row for it. Use `window`, or compare with price_list_on, to find those pairs.
    - With `window` (first, last day, inclusive) the result is limited to the days inside the window, and the window's days before a pair's first row (gap_start = the window's first day) and after
      the pair's last closed row (gap_end = the window's last day) are counted too; a pair with an open last row has no trailing gap. A pair that was introduced after the window starts therefore
      reports the whole stretch before its first row, for example 30 days for a pair whose first row starts 30 days after the first day of the window: that is "not priced yet", not a hole in a price list. With a window the same pairs as without it are reported, plus those leading and trailing days; how many there are is computed from the data.

    `violations` comes from core check_contiguity, which costs most of the run time; the gaps and the currency changes are computed column wise and do not call it.

    Args:
        price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason.
        window: Optional keyword (first day, last day), both inclusive, as two dates; None (the default) reports only the internal gaps.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A PriceGaps named tuple. `violations` is the core check_contiguity frame (table, key, rule, detail). `gaps` has sup_key, itm_key, gap_start, gap_end and days, sorted by sup_key, itm_key and gap_start. `currency_changes` has sup_key, itm_key, valid_from, currency_before and currency_after.

    Raises:
        FrameError: price_list is not a DataFrame, lacks a needed column, has duplicate column names, has a row without sup_key, itm_key or valid_from, has a unit_price that is not numeric, or holds a valid_from or valid_to that is not a date; window is not two dates, holds a number, a time zone or a null, or ends before it starts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import price_gaps
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pl = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
        ...                    "valid_from": ["2025-01-01", "2025-02-01"], "valid_to": ["2025-01-10", None],
        ...                    "unit_price": [10.0, 11.0], "currency": ["EUR", "DKK"], "con_key": [None, None], "change_reason": [None, None]})
        >>> res = price_gaps(pl, context=ctx)
        >>> res.gaps["days"].tolist()
        [21]
        >>> res.currency_changes[["currency_before", "currency_after"]].values.tolist()
        [['EUR', 'DKK']]
        >>> price_gaps(pl, window=("2024-12-22", "2025-03-01"), context=ctx).gaps["days"].tolist()
        [10, 21]"""
    p = _check(price_list)
    first: pd.Timestamp | None = None
    last: pd.Timestamp | None = None
    if window is not None:
        try:
            first, last = (_window_day(w) for w in window)
        except (ValueError, TypeError, IndexError, AttributeError) as e:
            raise FrameError(f"window is (first day, last day) as two dates: {e}") from None
        if pd.isna(first) or pd.isna(last):
            raise FrameError("window is (first day, last day) as two dates")
        if last < first:
            raise FrameError("window ends before it starts")
    # core check_contiguity is called for `violations` (its rule and detail strings are the public result); the gaps and currency changes below do not use it.
    viol = check_contiguity(p, ["sup_key", "itm_key"], table="procurement.price_list")
    s = p.sort_values(["sup_key", "itm_key", "valid_from"], kind="stable").reset_index(drop=True)
    one = np.timedelta64(1, "D")
    open_end = np.datetime64("2262-01-01", "ns")
    gid = s.groupby(["sup_key", "itm_key"], sort=False).ngroup().to_numpy()
    vfrom = s["valid_from"].to_numpy("datetime64[ns]")
    vto = s["valid_to"].to_numpy("datetime64[ns]")
    ends = np.where(np.isnat(vto), open_end, vto)
    # end of the rows before each row of its pair: running maximum of the ends, shifted by one inside the pair
    run = pd.Series(ends.astype("int64")).groupby(gid).cummax().to_numpy().astype("datetime64[ns]")
    prev = np.empty_like(run)
    prev[1:] = run[:-1]
    start = np.ones(len(s), dtype=bool)
    start[1:] = gid[1:] != gid[:-1]
    inner = ~start & (prev < open_end)
    inner[inner] = vfrom[inner] > prev[inner] + one
    sup, itm = s["sup_key"].to_numpy(object), s["itm_key"].to_numpy(object)
    parts = [(sup[inner], itm[inner], prev[inner] + one, vfrom[inner] - one)]
    if first is not None:
        head = np.flatnonzero(start)                                  # the first row of a pair is its earliest valid_from
        lead = head[vfrom[head] > first.to_datetime64()]
        parts.append((sup[lead], itm[lead], np.full(len(lead), first.to_datetime64(), "datetime64[ns]"), vfrom[lead] - one))
        tail_row = np.append(head[1:], len(s)) - 1                    # the last row of each pair
        closed = pd.Series(np.isnat(vto)).groupby(gid).sum().to_numpy() == 0
        pair_end = pd.Series(ends.astype("int64")).groupby(gid).max().to_numpy().astype("datetime64[ns]")
        last_day = cast(pd.Timestamp, last)
        tail = closed & (pair_end < last_day.to_datetime64())
        parts.append((sup[tail_row[tail]], itm[tail_row[tail]], pair_end[tail] + one, np.full(int(tail.sum()), last_day.to_datetime64(), "datetime64[ns]")))
    gaps = pd.DataFrame({"sup_key": np.concatenate([x[0] for x in parts]), "itm_key": np.concatenate([x[1] for x in parts]),
                         "gap_start": np.concatenate([x[2] for x in parts]), "gap_end": np.concatenate([x[3] for x in parts])})
    if first is not None:
        gaps["gap_start"], gaps["gap_end"] = cast(Any, gaps["gap_start"]).clip(lower=first), cast(Any, gaps["gap_end"]).clip(upper=last)
        gaps = gaps[gaps["gap_end"] >= gaps["gap_start"]]
    if gaps.empty:
        gaps = pd.DataFrame([], columns=["sup_key", "itm_key", "gap_start", "gap_end", "days"])
    else:
        gaps["days"] = (gaps["gap_end"] - gaps["gap_start"]).dt.days.astype("int64") + 1
        gaps = gaps.drop_duplicates().sort_values(["sup_key", "itm_key", "gap_start"]).reset_index(drop=True)
    cur = s["currency"].to_numpy(object)
    step = np.zeros(len(s), dtype=bool)
    step[1:] = (gid[1:] == gid[:-1]) & (cur[1:] != cur[:-1])          # elementwise Python comparison, as for two currencies read one after the other
    cols = ["sup_key", "itm_key", "valid_from", "currency_before", "currency_after"]
    if step.any():
        later = np.flatnonzero(step)
        changes = pd.DataFrame({"sup_key": sup[later], "itm_key": itm[later], "valid_from": vfrom[later], "currency_before": cur[later - 1], "currency_after": cur[later]})
    else:
        changes = pd.DataFrame([], columns=cols)
    return PriceGaps(viol, gaps, changes)
