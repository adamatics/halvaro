"""Supply: stock on a date, reservations still open, order lines still open, the demand exposed to one supplier's price step and the spot orders around a supplier failure (plan 5.5).

Quantities stay in item units. Prices and values stay in the currency of the row: nothing here adds across currencies; the premium of a spot order is computed only when a rate frame is passed.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._types import DateLike
from .params import param

_KB = ("DA.REF.215", "DA.REF.218")
_EPS = 1e-9
_OPEN_STATUS = ("open", "partially_received")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    if frame.columns.duplicated().any():
        raise FrameError(f"{what} has duplicate column names")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys and frame.duplicated(list(keys)).any():
        d = frame[frame.duplicated(list(keys), keep=False)].iloc[0]
        raise FrameError(f"{what} has more than one row for {', '.join(str(d[k]) for k in keys)}; one row per key is required")


def _date(frame: pd.DataFrame, column: str, what: str) -> pd.Series:
    try:
        out = pd.to_datetime(frame[column])
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    return out.dt.normalize()


def _day(as_of: Any) -> pd.Timestamp:
    if isinstance(as_of, (bool, int, float, np.number)):
        raise FrameError(f"as_of {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise FrameError(f"as_of {as_of!r} is not a date without a time zone")
    return d.normalize()


def _keys(value: Any, name: str) -> set[Any]:
    if value is None or isinstance(value, (pd.DataFrame, dict)):
        raise FrameError(f"{name} is a project key or a list of keys")
    return {value} if isinstance(value, str) else set(value)


def _keyed(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    """A key column that drives the arithmetic has no nulls: a null key would silently drop a row from a group or match another one."""
    for c in columns:
        if len(frame) and frame[c].isna().any():
            raise FrameError(f"{what}.{c} has null values; it is a key and must be set on every row")


def _kind(series: pd.Series) -> str:
    t = series.dtype
    if pd.api.types.is_bool_dtype(t):
        return "boolean"
    if pd.api.types.is_integer_dtype(t):
        return "integer"
    if pd.api.types.is_float_dtype(t):
        return "float"
    return "text" if t == object or pd.api.types.is_string_dtype(t) else str(t)


def _numeric(frame: pd.DataFrame, column: str, what: str) -> None:
    if len(frame) and (not pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]) or frame[column].isna().any()):
        raise FrameError(f"{what}.{column} must be numeric without nulls")


@staged(sources=("inventory.stock_movement.site_key", "inventory.stock_movement.itm_key", "inventory.stock_movement.movement_date", "inventory.stock_movement.qty",
                 "inventory.stock_level.site_key", "inventory.stock_level.itm_key", "inventory.stock_level.as_of_date", "inventory.stock_level.on_hand", "inventory.stock_level.reserved",
                 "inventory.stock_level.available"), kb=_KB, oracle="py:tests/test_inventory.py::test_stock_never_negative_and_matches_levels")
def stock_on(stock_movement: pd.DataFrame, as_of: DateLike, *, stock_level: pd.DataFrame | None = None, reservation_open: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need on hand, reserved and available stock per site and item on a date.

    On hand is the cumulative signed movement quantity up to and including the date (the generator rebuilds on_hand the same way). When `stock_level` has a snapshot row for the date it is used (source snapshot), otherwise the movements are (source movements). `reservation_open` (output of reserved_demand: site_key, itm_key, qty_open) gives reserved, also on a snapshot row (the snapshot's own reserved column is then not used, and a pair without a reservation is reserved 0); without it reserved is the snapshot value or null. A reservation on a site and item with no stock is kept, with zero on hand. available is on_hand minus reserved and can be negative.

    Args:
        stock_movement: The inventory.stock_movement frame; it needs site_key, itm_key, movement_date and qty (signed, numeric without nulls).
        as_of: The day of the stock (a date, a Timestamp or a text); a time of day is dropped.
        stock_level: Optional inventory.stock_level frame (site_key, itm_key, as_of_date, on_hand, reserved, available); a row for the date replaces the movement sum of its pair.
        reservation_open: Optional output of reserved_demand (site_key, itm_key, qty_open); it gives the reserved quantity per site and item.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns site_key, itm_key, as_of, on_hand, reserved, available, source ('snapshot' or 'movements'), sorted by site_key and itm_key.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; qty, on_hand or qty_open is not numeric or has nulls; a site or item key is null; a movement has no movement_date or a date that is not a date or has a time zone; as_of is a number, has a time zone or is not a date; the snapshot of the date has a null on_hand or reserved or more than one row for a site and item.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import stock_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> mv = pd.DataFrame({"site_key": ["SIT-900001"] * 3, "itm_key": ["ITM-900001"] * 3,
        ...                    "movement_date": ["2025-01-05", "2025-02-01", "2025-03-01"], "qty": [10.0, -4.0, 5.0]})
        >>> r = stock_on(mv, "2025-02-15", context=ctx)
        >>> r["on_hand"].tolist(), r["source"].tolist()
        ([6.0], ['movements'])
        >>> res = pd.DataFrame({"site_key": ["SIT-900001"], "itm_key": ["ITM-900001"], "qty_open": [2.0]})
        >>> stock_on(mv, "2025-02-15", reservation_open=res, context=ctx)["available"].tolist()
        [4.0]"""
    _need(stock_movement, ["site_key", "itm_key", "movement_date", "qty"], "inventory.stock_movement")
    _numeric(stock_movement, "qty", "inventory.stock_movement")
    _keyed(stock_movement, ["site_key", "itm_key"], "inventory.stock_movement")
    d = _day(as_of)
    m = stock_movement.assign(_d=_date(stock_movement, "movement_date", "inventory.stock_movement"))
    if m["_d"].isna().any():
        raise FrameError("inventory.stock_movement has rows without movement_date")
    cum = cast(pd.DataFrame, m[m["_d"] <= d].groupby(["site_key", "itm_key"], as_index=False)["qty"].sum()).rename(columns={"qty": "on_hand"})
    cum["source"] = "movements"
    cum["reserved"] = np.nan
    if stock_level is not None:
        _need(stock_level, ["site_key", "itm_key", "as_of_date", "on_hand", "reserved", "available"], "inventory.stock_level")
        _keyed(stock_level, ["site_key", "itm_key", "as_of_date"], "inventory.stock_level")
        snap = stock_level.assign(_d=_date(stock_level, "as_of_date", "inventory.stock_level"))
        snap = snap[snap["_d"] == d][["site_key", "itm_key", "on_hand", "reserved"]]
        if snap[["on_hand", "reserved"]].isna().any().any():
            raise FrameError("the stock snapshot of the date has a null on_hand or reserved")
        _numeric(snap, "on_hand", "inventory.stock_level")
        _numeric(snap, "reserved", "inventory.stock_level")
        if snap.duplicated(["site_key", "itm_key"]).any():
            raise FrameError("inventory.stock_level has more than one snapshot row for a site and item on the date")
        if len(snap):
            snap = snap.assign(source="snapshot")
            cum = pd.concat([snap, cum[~cum.set_index(["site_key", "itm_key"]).index.isin(snap.set_index(["site_key", "itm_key"]).index)]], ignore_index=True)
    if reservation_open is not None:
        _need(reservation_open, ["site_key", "itm_key", "qty_open"], "reserved_demand output")
        _keyed(reservation_open, ["site_key", "itm_key"], "reserved_demand output")
        _numeric(reservation_open, "qty_open", "reserved_demand output")
        res = cast(pd.DataFrame, reservation_open.groupby(["site_key", "itm_key"], as_index=False)["qty_open"].sum()).rename(columns={"qty_open": "res"})
        cum = cum.merge(res, on=["site_key", "itm_key"], how="outer")      # a reservation on a site and item with no stock is kept: zero on hand, reserved above zero
        cum["on_hand"] = cum["on_hand"].fillna(0.0)
        cum["source"] = cum["source"].fillna("movements")
        cum["reserved"] = cum["res"].fillna(0.0)
        cum = cum.drop(columns="res")
    cum["available"] = cum["on_hand"] - cum["reserved"]
    cum["as_of"] = d
    return cum[["site_key", "itm_key", "as_of", "on_hand", "reserved", "available", "source"]].sort_values(["site_key", "itm_key"]).reset_index(drop=True)


@staged(sources=("inventory.reservation.prj_key", "inventory.reservation.itm_key", "inventory.reservation.reservation_no", "inventory.reservation.site_key", "inventory.reservation.qty",
                 "inventory.reservation.created_date", "inventory.reservation.needed_by_date", "inventory.reservation.po_key", "inventory.stock_movement.reservation_no",
                 "inventory.stock_movement.movement_type", "inventory.stock_movement.movement_date", "inventory.stock_movement.qty", "inventory.stock_movement.prj_key",
                 "inventory.stock_movement.itm_key", "inventory.reservation.po_line_no"), kb=_KB, oracle="py:tests/test_inventory.py::test_reservations_do_not_exceed_demand")
def reserved_demand(reservation: pd.DataFrame, stock_movement: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the reservations created by a date that still have quantity open, with what was issued against them.

    A reservation counts when it was created on or before the date. Its open quantity is qty minus the issues to the project up to and including the date (movements of type issue_project with the reservation number; issues are negative stock movements, the issued quantity is their absolute sum). Only reservations with open quantity above zero are returned.

    Args:
        reservation: The inventory.reservation frame, one row per prj_key, itm_key and reservation_no; it needs prj_key, itm_key, reservation_no, site_key, qty (numeric), created_date, needed_by_date, po_key and po_line_no.
        stock_movement: The inventory.stock_movement frame; it needs movement_type, movement_date, qty (numeric), prj_key, reservation_no and itm_key.
        as_of: The day to measure on (a date, a Timestamp or a text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns prj_key, itm_key, reservation_no, site_key, qty, issued, qty_open, needed_by_date, po_key (null for a free reservation, one that waits for no order), po_line_no, sorted by prj_key, itm_key, reservation_no.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the reservation frame repeats a prj_key, itm_key and reservation_no; qty is not numeric or has nulls; a key or created_date of a reservation is null; an issue_project movement with a reservation number has a null key or movement_date; such a movement has a positive quantity; a date is not a date or has a time zone; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import reserved_demand
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rsv = pd.DataFrame({"prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"], "reservation_no": [1], "site_key": ["SIT-900001"], "qty": [10.0],
        ...                     "created_date": ["2025-01-10"], "needed_by_date": ["2025-03-01"], "po_key": [None], "po_line_no": [None]})
        >>> mv = pd.DataFrame({"movement_type": ["issue_project"], "movement_date": ["2025-02-01"], "qty": [-4.0], "prj_key": ["PRJ-900001"],
        ...                    "reservation_no": [1], "itm_key": ["ITM-900001"]})
        >>> r = reserved_demand(rsv, mv, "2025-02-15", context=ctx)
        >>> r[["issued", "qty_open"]].to_dict("records")
        [{'issued': 4.0, 'qty_open': 6.0}]"""
    _need(reservation, ["prj_key", "itm_key", "reservation_no", "site_key", "qty", "created_date", "needed_by_date", "po_key", "po_line_no"], "inventory.reservation", keys=("prj_key", "itm_key", "reservation_no"))
    _need(stock_movement, ["movement_type", "movement_date", "qty", "prj_key", "reservation_no", "itm_key"], "inventory.stock_movement")
    _numeric(reservation, "qty", "inventory.reservation")
    _numeric(stock_movement, "qty", "inventory.stock_movement")
    _keyed(reservation, ["prj_key", "itm_key", "reservation_no", "site_key", "created_date"], "inventory.reservation")
    d = _day(as_of)
    r = reservation.assign(_c=_date(reservation, "created_date", "inventory.reservation"), needed_by_date=_date(reservation, "needed_by_date", "inventory.reservation"))
    r = r[r["_c"] <= d]
    mv = stock_movement.assign(_d=_date(stock_movement, "movement_date", "inventory.stock_movement"))
    cand = mv[(mv["movement_type"] == "issue_project") & mv["reservation_no"].notna()]
    _keyed(cand, ["prj_key", "itm_key", "movement_date"], "inventory.stock_movement (issue_project with a reservation_no)")
    iss = cand[cand["_d"] <= d]
    if (iss["qty"] > 0).any():
        raise FrameError("an issue_project movement has a positive quantity; issues are negative stock movements")
    issued = cast(pd.DataFrame, iss.assign(q=-iss["qty"]).groupby(["prj_key", "itm_key", "reservation_no"], as_index=False)["q"].sum()).rename(columns={"q": "issued"})
    out = r.merge(issued, on=["prj_key", "itm_key", "reservation_no"], how="left")
    out["issued"] = out["issued"].fillna(0.0)
    out["qty_open"] = out["qty"] - out["issued"]
    out = out[out["qty_open"] > _EPS]
    return out[["prj_key", "itm_key", "reservation_no", "site_key", "qty", "issued", "qty_open", "needed_by_date", "po_key", "po_line_no"]].sort_values(["prj_key", "itm_key", "reservation_no"]).reset_index(drop=True)


@staged(sources=("procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.itm_key", "procurement.po_line.qty", "procurement.po_line.promised_date", "procurement.po_line.requested_date",
                 "procurement.po_line.promise_revised_on", "procurement.purchase_order.po_key", "procurement.purchase_order.sup_key", "procurement.purchase_order.prj_key", "procurement.purchase_order.order_date",
                 "procurement.purchase_order.status", "procurement.goods_receipt.po_key", "procurement.goods_receipt.line_no", "procurement.goods_receipt.receipt_date",
                 "procurement.goods_receipt.qty_accepted"), kb=_KB, oracle="py:tests/test_procurement.py::test_receipts_and_statuses")
def open_po_lines(po_line: pd.DataFrame, purchase_order: pd.DataFrame, goods_receipt: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the order lines still open on a date, with the quantity remaining, the slip of the promise and the days overdue.

    A line is open when its order is not cancelled (no cancel date exists, so a cancelled order is left out for every date; policy.delivery.cancel_date_proxy, proposed), was placed on or before the date, and the quantity accepted in receipts up to and including the date is below the ordered quantity. remaining = qty minus accepted. slip_days = promised_date minus requested_date, the days the supplier moved the date. days_overdue = days from promised_date to the date when the promise is already past, else 0.
    The promise is the one valid on the date. `po_line.promised_date` is the final promise and `promise_revised_on` the day the supplier gave it (one revision per line; `requested_date` is the original due date and the promise before the revision, generator orders.py). When the date is before the revision the original date (`requested_date`) is the promise: slip_days is then 0, days_overdue counts from it, `promised_date` shows it and `promise_is_final` is False; from the revision day on `promised_date` is the stored one and `promise_is_final` is True. A line without a revision keeps its stored promised_date (promise_is_final True). Without a `promise_revised_on` column in `po_line` no revision is known: the stored promised_date is used for every date and promise_is_final is True, which can show a later promise than the one that stood on a past date. `promise_revised_on` in the result is the revision day when it is on or before the date, else null.

    Args:
        po_line: The procurement.po_line frame, one row per po_key and line_no; it needs po_key, line_no, itm_key, qty (numeric), promised_date and requested_date, and optionally promise_revised_on.
        purchase_order: The procurement.purchase_order frame, one row per po_key; it needs po_key, sup_key, prj_key, order_date and status.
        goods_receipt: The procurement.goods_receipt frame; it needs po_key, line_no, receipt_date and qty_accepted (numeric); line_no has the type of po_line.line_no.
        as_of: The day to measure on (a date, a Timestamp or a text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame keyed by po_key and line_no with the columns po_key, line_no, prj_key, itm_key, sup_key, order_date, qty, accepted, remaining, requested_date, promised_date, promise_revised_on, promise_is_final, slip_days, days_overdue, sorted by po_key and line_no.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line repeats a po_key and line_no or purchase_order repeats a po_key; qty or qty_accepted is not numeric or has nulls; a key, order_date or receipt_date is null; a line has no promised_date or requested_date; a date is not a date or has a time zone; line_no differs in type between po_line and goods_receipt; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import open_po_lines
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pl = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "itm_key": ["ITM-900001", "ITM-900002"], "qty": [10.0, 5.0],
        ...                    "promised_date": ["2025-03-01", "2025-03-01"], "requested_date": ["2025-02-01", "2025-02-01"]})
        >>> po = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"], "prj_key": ["PRJ-900001"], "order_date": ["2025-01-10"], "status": ["open"]})
        >>> gr = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [2], "receipt_date": ["2025-02-20"], "qty_accepted": [5.0]})
        >>> r = open_po_lines(pl, po, gr, "2025-03-05", context=ctx)
        >>> r[["line_no", "remaining", "slip_days", "days_overdue"]].to_dict("records")
        [{'line_no': 1, 'remaining': 10.0, 'slip_days': 28, 'days_overdue': 4}]"""
    _need(po_line, ["po_key", "line_no", "itm_key", "qty", "promised_date", "requested_date"], "procurement.po_line", keys=("po_key", "line_no"))
    _need(purchase_order, ["po_key", "sup_key", "prj_key", "order_date", "status"], "procurement.purchase_order", keys=("po_key",))
    _need(goods_receipt, ["po_key", "line_no", "receipt_date", "qty_accepted"], "procurement.goods_receipt")
    _numeric(po_line, "qty", "procurement.po_line")
    _numeric(goods_receipt, "qty_accepted", "procurement.goods_receipt")
    _keyed(po_line, ["po_key", "line_no"], "procurement.po_line")
    _keyed(purchase_order, ["po_key", "order_date"], "procurement.purchase_order")
    _keyed(goods_receipt, ["po_key", "line_no", "receipt_date"], "procurement.goods_receipt")
    d = _day(as_of)
    revised = "promise_revised_on" in po_line.columns
    o = purchase_order[purchase_order["status"] != "cancelled"][["po_key", "sup_key", "prj_key", "order_date"]].assign(order_date=lambda x: _date(x, "order_date", "procurement.purchase_order"))
    o = o[o["order_date"] <= d]
    lines = po_line[["po_key", "line_no", "itm_key", "qty", "promised_date", "requested_date"] + (["promise_revised_on"] if revised else [])].merge(o, on="po_key", how="inner")
    lines = lines.assign(promised_date=_date(lines, "promised_date", "procurement.po_line"), requested_date=_date(lines, "requested_date", "procurement.po_line"))
    if lines[["promised_date", "requested_date"]].isna().any().any():
        raise FrameError("procurement.po_line has lines without promised_date or requested_date")
    if len(goods_receipt) and _kind(goods_receipt["line_no"]) != _kind(po_line["line_no"]):
        raise FrameError("line_no differs in type between procurement.po_line and procurement.goods_receipt")
    if revised:
        rev = _date(lines, "promise_revised_on", "procurement.po_line")
        pending = rev.notna() & (rev > d)
        lines["promised_date"] = lines["promised_date"].where(~pending, lines["requested_date"])
        lines["promise_revised_on"] = rev.where(~pending)
        lines["promise_is_final"] = ~pending
    else:
        lines["promise_revised_on"] = pd.Series(pd.NaT, index=lines.index, dtype="datetime64[ns]")
        lines["promise_is_final"] = True
    gr = goods_receipt.assign(_d=_date(goods_receipt, "receipt_date", "procurement.goods_receipt"))
    got = cast(pd.DataFrame, gr[gr["_d"] <= d].groupby(["po_key", "line_no"], as_index=False)["qty_accepted"].sum()).rename(columns={"qty_accepted": "accepted"})
    out = lines.merge(got, on=["po_key", "line_no"], how="left")
    out["accepted"] = out["accepted"].fillna(0.0)
    out["remaining"] = out["qty"] - out["accepted"]
    out = out[out["remaining"] > _EPS].copy()
    out["days_overdue"] = np.maximum(0, (d - out["promised_date"]).dt.days).astype("int64")
    out["slip_days"] = (out["promised_date"] - out["requested_date"]).dt.days.astype("int64")
    return out[["po_key", "line_no", "prj_key", "itm_key", "sup_key", "order_date", "qty", "accepted", "remaining", "requested_date", "promised_date", "promise_revised_on", "promise_is_final", "slip_days",
                "days_overdue"]].sort_values(["po_key", "line_no"]).reset_index(drop=True)


class ExposedDemand(NamedTuple):
    """Result of exposed_demand: the open order lines and the free reservations of one supplier's items on active projects, and the project set they define.
    `sup_key` is the supplier the frames were built for. `combined` is the single frame of plan section 6."""

    lines: pd.DataFrame
    reservations: pd.DataFrame
    projects: pd.DataFrame
    sup_key: str | None = None

    @property
    def combined(self) -> pd.DataFrame:
        """One frame of lines and reservations (plan section 6, read by finance open_exposure and exposure_bridge): prj_key, itm_key, source ('po_line' or 'reservation'), reference (po_key/line_no for a line,
        prj_key/itm_key/reservation_no for a reservation), remaining (remaining or qty_open, item units), sup_key (the supplier asked for) and after_effective_date (a line: placed on or after the effective date;
        a reservation: null, no order is placed yet). The project set is `projects`. Sorted by source, prj_key, itm_key, reference. A reservation frame without reservation_no cannot give a reference and is refused."""
        li, rs = self.lines, self.reservations
        if len(rs) and "reservation_no" not in rs.columns:
            raise FrameError("the reservations lack reservation_no; pass the output of reserved_demand to get a reference per reservation")
        a = pd.DataFrame({"prj_key": li["prj_key"], "itm_key": li["itm_key"], "source": "po_line", "reference": li["po_key"].astype(str) + "/" + li["line_no"].astype(str),
                          "remaining": li["remaining"], "sup_key": li["sup_key"], "after_effective_date": li["after_effective_date"].astype("boolean")})
        ref = rs["prj_key"].astype(str) + "/" + rs["itm_key"].astype(str) + "/" + (rs["reservation_no"].astype(str) if len(rs) else rs["prj_key"].astype(str))
        b = pd.DataFrame({"prj_key": rs["prj_key"], "itm_key": rs["itm_key"], "source": "reservation", "reference": ref, "remaining": rs["qty_open"], "sup_key": self.sup_key,
                          "after_effective_date": pd.array([pd.NA] * len(rs), dtype="boolean")})
        out = pd.concat([x for x in (a, b) if len(x)] or [a], ignore_index=True)
        out["after_effective_date"] = out["after_effective_date"].astype("boolean")
        return out.sort_values(["source", "prj_key", "itm_key", "reference"]).reset_index(drop=True)


@staged(sources=("procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.itm_key", "procurement.po_line.qty", "procurement.purchase_order.sup_key", "procurement.purchase_order.prj_key",
                 "procurement.purchase_order.order_date", "procurement.goods_receipt.qty_accepted", "procurement.price_list.sup_key", "procurement.price_list.itm_key", "projects.project.prj_key",
                 "projects.project.price_type", "inventory.reservation.prj_key", "inventory.reservation.itm_key", "inventory.reservation.reservation_no", "inventory.reservation.qty",
                 "inventory.reservation.po_key"), kb=_KB)
def exposed_demand(open_lines: pd.DataFrame, reservations_open: pd.DataFrame, price_list: pd.DataFrame, project: pd.DataFrame, sup_key: str, effective_from: DateLike, *, active: Sequence[str]) -> ExposedDemand:
    """Use this when you need the quantity exposed to one supplier's price step: its open order lines and the free reservations on active projects, and the projects they define.

    The lines are the open order lines of the supplier (open_po_lines output) on the active projects, with remaining quantity and after_effective_date (placed on or after `effective_from`, the lines the price step reaches). The reservations are the free ones (po_key null, quantity open) on active projects for items in the supplier's price list. `active` is the list of active project keys the app passes (from active_on). projects: every project with either, with price_type, n_lines, n_reservations and the remaining quantities. Every project in `projects` must be in the project frame; an active project that has no demand of the supplier need not be. The supplier and the date are the caller's. Quantities only: money is multiplied by finance. The remaining quantities add up quantities of items with different units (metres, sets, units), as the generator's own exposure test does; they are not unit safe. `.combined` gives lines and reservations as the single frame of plan section 6.

    Args:
        open_lines: Output of open_po_lines; it needs po_key, line_no, prj_key, itm_key, sup_key, order_date and remaining (numeric), one row per po_key and line_no.
        reservations_open: Output of reserved_demand; it needs prj_key, itm_key, qty_open (numeric) and po_key.
        price_list: The procurement.price_list frame; it needs sup_key and itm_key and gives the items of the supplier.
        project: The projects.project frame, one row per prj_key; it needs prj_key and price_type.
        sup_key: The supplier the price step belongs to.
        effective_from: The day the price step starts (a date, a Timestamp or a text).
        active: The active project keys, a list or a single key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An ExposedDemand tuple: `lines` (the supplier's open lines on active projects with after_effective_date, sorted by prj_key, po_key, line_no), `reservations` (the free reservations, sorted by prj_key, itm_key), `projects` (prj_key, n_lines, remaining_lines, n_reservations, remaining_reserved, price_type, sorted by prj_key) and `sup_key`; its `.combined` property is the single frame.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the project frame repeats a prj_key; remaining or qty_open is not numeric or has nulls; a key column is null; the open lines repeat an order line or have a row without order_date; active is a frame, a mapping or None; effective_from or an order_date is not a date; a project with demand is not in the project frame.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import exposed_demand
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"],
        ...                       "sup_key": ["SUP-900001"], "order_date": ["2025-03-01"], "remaining": [8.0]})
        >>> res = pd.DataFrame({"prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"], "qty_open": [3.0], "po_key": [None]})
        >>> pl = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"]})
        >>> pj = pd.DataFrame({"prj_key": ["PRJ-900001"], "price_type": ["fixed"]})
        >>> r = exposed_demand(lines, res, pl, pj, "SUP-900001", "2025-02-01", active=["PRJ-900001"], context=ctx)
        >>> r.lines["after_effective_date"].tolist()
        [True]
        >>> r.projects[["prj_key", "remaining_lines", "remaining_reserved"]].to_dict("records")
        [{'prj_key': 'PRJ-900001', 'remaining_lines': 8.0, 'remaining_reserved': 3.0}]"""
    _need(open_lines, ["po_key", "line_no", "prj_key", "itm_key", "sup_key", "order_date", "remaining"], "open_po_lines output")
    _need(reservations_open, ["prj_key", "itm_key", "qty_open", "po_key"], "reserved_demand output")
    _need(price_list, ["sup_key", "itm_key"], "procurement.price_list")
    _need(project, ["prj_key", "price_type"], "projects.project", keys=("prj_key",))
    _numeric(open_lines, "remaining", "open_po_lines output")
    _numeric(reservations_open, "qty_open", "reserved_demand output")
    _keyed(open_lines, ["po_key", "line_no", "itm_key", "sup_key"], "open_po_lines output")
    _keyed(reservations_open, ["prj_key", "itm_key"], "reserved_demand output")
    _keyed(price_list, ["sup_key", "itm_key"], "procurement.price_list")
    _keyed(project, ["prj_key"], "projects.project")
    act = _keys(active, "active")
    eff = _day(effective_from)
    if open_lines.duplicated(["po_key", "line_no"]).any():
        raise FrameError("the open lines have more than one row for an order line")
    if open_lines["order_date"].isna().any():
        raise FrameError("the open lines have rows without order_date")
    items = set(price_list.loc[price_list["sup_key"] == sup_key, "itm_key"])
    lines = open_lines[(open_lines["sup_key"] == sup_key) & open_lines["prj_key"].isin(act)].copy()
    lines["after_effective_date"] = _date(lines, "order_date", "open_po_lines output") >= eff
    res = reservations_open[reservations_open["po_key"].isna() & reservations_open["prj_key"].isin(act) & reservations_open["itm_key"].isin(items)].copy()
    unknown = sorted((set(lines["prj_key"]) | set(res["prj_key"])) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} active projects with demand are not in the project frame (for example {unknown[0]})")
    a = lines.groupby("prj_key").agg(n_lines=("po_key", "size"), remaining_lines=("remaining", "sum"))
    b = res.groupby("prj_key").agg(n_reservations=("itm_key", "size"), remaining_reserved=("qty_open", "sum"))
    pj = a.join(b, how="outer").fillna(0.0).reset_index()
    for c in ("n_lines", "n_reservations"):
        pj[c] = pj[c].astype("int64")
    pj = pj.merge(project[["prj_key", "price_type"]], on="prj_key", how="left")
    return ExposedDemand(lines.sort_values(["prj_key", "po_key", "line_no"]).reset_index(drop=True), res.sort_values(["prj_key", "itm_key"]).reset_index(drop=True), pj.sort_values("prj_key").reset_index(drop=True), sup_key)


@staged(sources=("procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.itm_key", "procurement.po_line.unit_price", "procurement.po_line.currency",
                 "procurement.po_line.price_source", "procurement.po_line.expedite", "procurement.purchase_order.po_key", "procurement.purchase_order.order_type", "procurement.purchase_order.sup_key",
                 "procurement.purchase_order.prj_key", "procurement.purchase_order.order_date", "procurement.price_list.sup_key", "procurement.price_list.itm_key", "procurement.price_list.valid_from",
                 "procurement.price_list.valid_to", "procurement.price_list.unit_price", "procurement.price_list.currency", "procurement.price_list.change_reason"), kb=_KB)
def spot_orders(po_line: pd.DataFrame, purchase_order: pd.DataFrame, price_list: pd.DataFrame, *, framework_sup_key: str | None = None, item_type: pd.Series | None = None,
                rates: Mapping[str, float] | None = None) -> pd.DataFrame:
    """Use this when you need the lines of spot orders with their price, whether an expedite line is freight and the premium over the framework list price.

    The lines are those of orders of order_type spot. freight is true for an expedite line of a service item (`item_type`: a Series itm_key to item_type, unique index) and is null without it (an expedite line alone does not say what it is). With `framework_sup_key` the lines of that supplier itself and of items outside its price list are left out (spot orders are for its items from other suppliers), and freight is tied to the goods: an expedite service line is freight only when a spot order of the same project and order date has a goods line (an item of the framework supplier's list, not a service, from another supplier); otherwise freight is False and `freight_unmatched` is True (an express service line with no goods order next to it); an express service line, matched or not, has no premium. freight_unmatched is False on every other row and without a framework supplier. With `framework_sup_key` and `rates` the framework list price of the failing supplier for the same item on the order date (the latest valid row that is not a spot quote; two such rows with the same valid_from are refused) is joined and premium = price in DKK over list price in DKK minus one; otherwise premium is null (prices of different currencies are never compared without a rate).

    Args:
        po_line: The procurement.po_line frame, one row per po_key and line_no; it needs po_key, line_no, itm_key, unit_price (numeric), currency, price_source and expedite (True or False on every row).
        purchase_order: The procurement.purchase_order frame, one row per po_key; it needs po_key, order_type, sup_key, prj_key and order_date.
        price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency and change_reason, and is read only for a premium.
        framework_sup_key: The framework supplier whose list is the reference; give it together with `rates` for a premium.
        item_type: A Series from itm_key to item_type with a unique index; items of type service make expedite lines freight.
        rates: A mapping from currency to DKK per unit, positive numbers, from core; give it together with `framework_sup_key`.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns po_key, line_no, prj_key, itm_key, sup_key, order_date, unit_price, currency, price_source, expedite, freight (nullable boolean), freight_unmatched, premium (a ratio, null when not computed), sorted by po_key and line_no.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line repeats a po_key and line_no or purchase_order repeats a po_key; a key, order_date or (for a premium) valid_from is null; unit_price is not numeric or has nulls; expedite is not True or False on every row; item_type is not a Series with a unique index; only one of framework_sup_key and rates is given; the framework list has two rows for an item with the same valid_from; a rate is not a positive number or a currency has no rate; a date is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import spot_orders
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pl = pd.DataFrame({"po_key": ["PO-900001", "PO-900002"], "line_no": [1, 1], "itm_key": ["ITM-900001", "ITM-900002"], "unit_price": [120.0, 50.0],
        ...                    "currency": ["DKK", "DKK"], "price_source": ["spot", "framework"], "expedite": [False, False]})
        >>> po = pd.DataFrame({"po_key": ["PO-900001", "PO-900002"], "order_type": ["spot", "standard"], "sup_key": ["SUP-900002", "SUP-900001"],
        ...                    "prj_key": ["PRJ-900001", "PRJ-900001"], "order_date": ["2025-03-01", "2025-03-01"]})
        >>> fw = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"], "valid_from": ["2025-01-01"], "valid_to": [None],
        ...                    "unit_price": [100.0], "currency": ["DKK"], "change_reason": ["annual"]})
        >>> r = spot_orders(pl, po, fw, framework_sup_key="SUP-900001", rates={"DKK": 1.0}, context=ctx)
        >>> r[["po_key", "premium"]].round(2).to_dict("records")
        [{'po_key': 'PO-900001', 'premium': 0.2}]"""
    _need(po_line, ["po_key", "line_no", "itm_key", "unit_price", "currency", "price_source", "expedite"], "procurement.po_line", keys=("po_key", "line_no"))
    _need(purchase_order, ["po_key", "order_type", "sup_key", "prj_key", "order_date"], "procurement.purchase_order", keys=("po_key",))
    _keyed(po_line, ["po_key", "line_no", "itm_key"], "procurement.po_line")
    _keyed(purchase_order, ["po_key"], "procurement.purchase_order")
    o = purchase_order[purchase_order["order_type"] == "spot"][["po_key", "sup_key", "prj_key", "order_date"]]
    _keyed(o, ["order_date"], "procurement.purchase_order")
    o = o.assign(order_date=lambda x: _date(x, "order_date", "procurement.purchase_order"))
    _numeric(po_line, "unit_price", "procurement.po_line")
    if not po_line["expedite"].isin([True, False]).all() or po_line["expedite"].map(lambda v: isinstance(v, str)).any():
        raise FrameError("procurement.po_line.expedite must be True or False on every row")
    out = po_line[["po_key", "line_no", "itm_key", "unit_price", "currency", "price_source", "expedite"]].merge(o, on="po_key", how="inner")
    out["expedite"] = out["expedite"].astype(bool)
    if item_type is not None:
        if not isinstance(item_type, pd.Series) or item_type.index.duplicated().any():
            raise FrameError("item_type is a Series itm_key to item_type with a unique index")
        out["freight"] = (out["expedite"] & (out["itm_key"].map(item_type) == "service")).astype("boolean")
    else:
        out["freight"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    out["freight_unmatched"] = False
    out["premium"] = np.nan
    if framework_sup_key is not None or rates is not None:
        if framework_sup_key is None or rates is None:
            raise FrameError("a premium needs both framework_sup_key and rates")
        _need(price_list, ["sup_key", "itm_key", "valid_from", "valid_to", "unit_price", "currency", "change_reason"], "procurement.price_list")
        pl = price_list[(price_list["sup_key"] == framework_sup_key) & (price_list["change_reason"] != "spot_quote")]
        _keyed(pl, ["itm_key", "valid_from"], "procurement.price_list")
        _numeric(pl, "unit_price", "procurement.price_list")
        pl = pl.assign(valid_from=lambda x: _date(x, "valid_from", "procurement.price_list"), valid_to=lambda x: _date(x, "valid_to", "procurement.price_list"))
        tie = pl[pl.duplicated(["itm_key", "valid_from"], keep=False)]
        if len(tie):
            raise FrameError(f"procurement.price_list has more than one framework row for {framework_sup_key}, {tie.iloc[0]['itm_key']} valid from {tie.iloc[0]['valid_from']:%Y-%m-%d}; the price on a date is not defined")
        bad = [c for c, v in rates.items() if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not np.isfinite(v) or v <= 0]
        if bad:
            raise FrameError(f"the rate of {', '.join(map(str, bad))} must be a positive number")
        listed = set(pl["itm_key"])
        service = set(item_type[item_type == "service"].index) if item_type is not None else set()
        out = out[(out["sup_key"] != framework_sup_key) & out["itm_key"].isin(listed | service)].reset_index(drop=True)
        cand = np.zeros(len(out), dtype=bool)
        if item_type is not None:
            is_service = (out["itm_key"].map(item_type) == "service").to_numpy()
            goods = out.loc[out["itm_key"].isin(listed).to_numpy() & ~is_service, ["prj_key", "order_date"]].dropna().drop_duplicates().assign(_goods=True)
            near = out[["prj_key", "order_date"]].merge(goods, on=["prj_key", "order_date"], how="left")["_goods"].eq(True).to_numpy()
            cand = out["expedite"].to_numpy() & is_service
            out["freight"] = pd.Series(cand & near, index=out.index).astype("boolean")
            out["freight_unmatched"] = cand & ~near
        rest = out[~out["freight"].fillna(False).astype(bool) & ~cand]       # an express service line is no goods order, matched to goods or not: it has no premium against a goods list price
        hit = rest[["itm_key", "order_date", "unit_price", "currency"]].rename(columns={"unit_price": "price", "currency": "cur"}).reset_index().merge(
            pl[["itm_key", "valid_from", "valid_to", "unit_price", "currency"]].rename(columns={"unit_price": "list_price", "currency": "list_cur"}), on="itm_key")
        hit = hit[(hit["valid_from"] <= hit["order_date"]) & (hit["valid_to"].isna() | (hit["valid_to"] >= hit["order_date"]))]
        hit = hit.sort_values(["index", "valid_from"], kind="stable").drop_duplicates("index", keep="last")      # the latest valid row (rule card 5.10); a row that starts on the previous valid_to is the latest
        missing = hit[~hit["cur"].isin(list(rates)) | ~hit["list_cur"].isin(list(rates))]
        if len(missing):
            r = missing.iloc[0]
            raise FrameError(f"no rate for currency {next(c for c in (r['cur'], r['list_cur']) if c not in rates)}")
        out.loc[hit["index"].to_numpy(), "premium"] = (hit["price"] * hit["cur"].map(rates) / (hit["list_price"] * hit["list_cur"].map(rates)) - 1.0).to_numpy()
    return out[["po_key", "line_no", "prj_key", "itm_key", "sup_key", "order_date", "unit_price", "currency", "price_source", "expedite", "freight", "freight_unmatched", "premium"]].sort_values(["po_key", "line_no"]).reset_index(drop=True)


_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}([T ].*)?")


def _iso_day(as_of: Any) -> pd.Timestamp:
    """as_of of the supply strain functions: a date object, a timestamp or an ISO text YYYY-MM-DD. A text such as 01-08-2026 is refused: it would be read month first."""
    if isinstance(as_of, str) and _ISO_DAY.fullmatch(as_of.strip()) is None:
        raise FrameError(f"as_of {as_of!r} is not an ISO date YYYY-MM-DD; a day-first text is not read")
    return _day(as_of.strip() if isinstance(as_of, str) else as_of)


_STOCK_DATE_COLUMNS = ("as_of", "as_of_date")


def _stock_day(stock: pd.DataFrame, d: pd.Timestamp | None) -> pd.Timestamp | None:
    """A stock_on frame carries its date in `as_of` (the raw inventory.stock_level table in `as_of_date`); a frame of another date than the question, or of several dates, is refused, not read as the stock
    of the date. A frame holds one row per (site_key, itm_key): a frame of snapshots or movements would be summed over every date. With d None the date of the frame is returned (None when it has no date column)."""
    found = None
    for col in _STOCK_DATE_COLUMNS:
        if col not in stock.columns:
            continue
        if stock[col].isna().any():
            raise FrameError(f"stock_on output.{col} has nulls")
        days = _date(stock, col, "stock_on output").unique()
        shown = ", ".join(sorted(str(pd.Timestamp(x).date()) for x in days))
        if d is None and len(days) > 1:
            raise FrameError(f"the stock frame holds more than one date ({shown}); pass one stock_on frame")
        if d is not None and (len(days) > 1 or (len(days) == 1 and pd.Timestamp(days[0]) != d)):
            raise FrameError(f"the stock frame is for {shown}, not for {d.date()}; build it with stock_on for the same date")
        if found is None and len(days) == 1:
            found = pd.Timestamp(days[0])
    if {"site_key", "itm_key"} <= set(stock.columns) and stock.duplicated(["site_key", "itm_key"]).any():
        k = stock[stock.duplicated(["site_key", "itm_key"], keep=False)].iloc[0]
        raise FrameError(f"the stock frame has more than one row for {k['site_key']} {k['itm_key']}; pass one stock_on frame (one row per site and item), not snapshots or movements that would be summed over every date")
    return found


def _one_key(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise FrameError(f"{name} is one key given as text, not {value!r}")


class BlockedProjects(NamedTuple):
    """Result of blocked_projects: one row per project and item with the unmet quantity, and the projects."""

    items: pd.DataFrame
    projects: pd.DataFrame


@staged(sources=("inventory.reservation.prj_key", "inventory.reservation.itm_key", "inventory.reservation.site_key", "inventory.reservation.qty_open", "inventory.reservation.needed_by_date"),
        kb=_KB)
def blocked_projects(reservations_open: pd.DataFrame, stock: pd.DataFrame, as_of: DateLike, *, items: Sequence[str], active: Sequence[str], site: str | None = None,
                     horizon_days: int | None = None) -> BlockedProjects:
    """Use this when you need the active projects whose open reservations of given items cannot be met because the stock at the site is zero or less on a date.

    A project is listed when it has an open reservation (qty_open above zero, reserved_demand output) of the given items, needed within `horizon_days` of the date (days already past count), where the stock of the item at the site is zero or less on the date (stock_on output). The horizon defaults to the parameter blocked_need_horizon_days of inventory.yaml (45, verified). With `site` only reservations at that site count; without it each reservation is judged at its own site. PROPOSED: policy.delivery.blocked_project_definition (needed): the generator truth selects by item and need date only, the test adds the site and the zero stock. A pair with no row in the stock frame counts as zero stock. A stock frame with an `as_of` column (stock_on output) must be for `as_of`.

    Args:
        reservations_open: Output of reserved_demand; it needs prj_key, itm_key, site_key, qty_open (numeric) and needed_by_date, none of them null.
        stock: Output of stock_on; it needs site_key, itm_key and on_hand (numeric), one row per site and item, and when it has an as_of (or as_of_date) column that is one date equal to `as_of`.
        as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
        items: The item keys to look at, a list or a single key.
        active: The active project keys, a list or a single key.
        site: Optional site key; only reservations at that site count.
        horizon_days: Optional whole number of days from zero to 36500 that a need may lie ahead; defaults to the parameter above.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A BlockedProjects tuple. `items` has one row per project and item with prj_key, itm_key, site_key, unmet_qty, n_reservations, earliest_needed_by, days_past_need (date minus earliest need, negative while the need is ahead) and on_hand, sorted by prj_key and itm_key. `projects` has prj_key, unmet_qty and n_items.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; as_of is not an ISO date, is a number or has a time zone; the stock frame is for another date than as_of, holds more than one date, has more than one row for a site and item or has nulls in site_key or itm_key; horizon_days is not a whole number from zero to 36500; qty_open or on_hand is not numeric or has nulls; a reservation has a null project, item, site or need date; items or active is a frame, a mapping or None.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import blocked_projects
        >>> ctx = Context(stage="month12", role="analyst")
        >>> res = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "itm_key": ["ITM-900001", "ITM-900001"], "site_key": ["SIT-900001", "SIT-900001"],
        ...                     "qty_open": [4.0, 2.0], "needed_by_date": ["2025-03-10", "2025-09-01"]})
        >>> stock = pd.DataFrame({"site_key": ["SIT-900001"], "itm_key": ["ITM-900001"], "on_hand": [0.0]})
        >>> r = blocked_projects(res, stock, "2025-03-01", items=["ITM-900001"], active=["PRJ-900001", "PRJ-900002"], horizon_days=45, context=ctx)
        >>> r.items[["prj_key", "unmet_qty", "days_past_need"]].to_dict("records")
        [{'prj_key': 'PRJ-900001', 'unmet_qty': 4.0, 'days_past_need': -9}]
        >>> r.projects["n_items"].tolist()
        [1]"""
    _need(reservations_open, ["prj_key", "itm_key", "site_key", "qty_open", "needed_by_date"], "reserved_demand output")
    _need(stock, ["site_key", "itm_key", "on_hand"], "stock_on output")
    d = _iso_day(as_of)
    _stock_day(stock, d)
    h = int(param("inventory.yaml#critical_supply.blocked_need_horizon_days").value) if horizon_days is None else horizon_days
    if isinstance(h, bool) or not isinstance(h, (int, np.integer)) or not 0 <= h <= 36500:
        raise FrameError(f"horizon_days must be a whole number of days from zero to 36500, not {h!r}")
    _numeric(reservations_open, "qty_open", "reserved_demand output")
    _numeric(stock, "on_hand", "stock_on output")
    for c in ("prj_key", "itm_key", "site_key", "needed_by_date"):
        if reservations_open[c].isna().any():
            raise FrameError(f"reserved_demand output.{c} has nulls; a reservation needs its project, item, site and need date")
    if stock[["site_key", "itm_key"]].isna().any().any():
        raise FrameError("stock_on output has nulls in site_key or itm_key")
    act, its = _keys(active, "active"), _keys(items, "items")
    r = reservations_open[reservations_open["prj_key"].isin(act) & reservations_open["itm_key"].isin(its) & (reservations_open["qty_open"] > _EPS)].copy()
    if site is not None:
        r = r[r["site_key"] == site]
    r["needed_by_date"] = _date(r, "needed_by_date", "reserved_demand output")
    r = r[r["needed_by_date"] <= d + pd.DateOffset(days=h)]
    g = r.groupby(["prj_key", "itm_key", "site_key"], as_index=False).agg(unmet_qty=("qty_open", "sum"), n_reservations=("qty_open", "size"), earliest_needed_by=("needed_by_date", "min"))
    on = stock.groupby(["site_key", "itm_key"], as_index=False)["on_hand"].sum()
    g = g.merge(on, on=["site_key", "itm_key"], how="left")
    g["on_hand"] = g["on_hand"].fillna(0.0)
    g = g[g["on_hand"] <= _EPS].copy()
    g["days_past_need"] = (d - g["earliest_needed_by"]).dt.days
    g = g.sort_values(["prj_key", "itm_key"]).reset_index(drop=True)
    pj = g.groupby("prj_key", as_index=False).agg(unmet_qty=("unmet_qty", "sum"), n_items=("itm_key", "nunique"))
    return BlockedProjects(g, pj)


@staged(sources=("inventory.lead_time.sup_key", "inventory.lead_time.itm_key", "inventory.lead_time.valid_from", "inventory.lead_time.valid_to", "inventory.lead_time.lead_time_weeks"), kb=_KB)
def lead_time_on(lead_time: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the lead time in weeks per supplier and item on a date, with the change from the previous lead time.

    The lead time is the row valid on the date (valid_from on or before, valid_to null or on or after), with the previous row's value and the change.

    Args:
        lead_time: The inventory.lead_time frame; it needs sup_key, itm_key, valid_from, valid_to (null for the open row) and lead_time_weeks (numeric without nulls).
        as_of: The day to read the lead times on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns sup_key, itm_key, lead_time_weeks, valid_from, previous_weeks, change_weeks, change_percent (null without a previous row above zero), one row per supplier and item valid on the date, in the order of sup_key, itm_key.

    Raises:
        FrameError: lead_time is not a DataFrame, has duplicate column names or lacks a needed column; lead_time_weeks is not numeric or has nulls; a row has no valid_from, or ends before it starts, or holds a date that is not a date or has a time zone; two rows are valid on the date for one supplier and item; as_of is not an ISO date, is a number or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import lead_time_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lt = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
        ...                    "valid_from": ["2025-01-01", "2025-06-01"], "valid_to": ["2025-05-31", None], "lead_time_weeks": [10.0, 15.0]})
        >>> r = lead_time_on(lt, "2025-07-01", context=ctx)
        >>> r[["lead_time_weeks", "previous_weeks", "change_weeks", "change_percent"]].to_dict("records")
        [{'lead_time_weeks': 15.0, 'previous_weeks': 10.0, 'change_weeks': 5.0, 'change_percent': 50.0}]"""
    _need(lead_time, ["sup_key", "itm_key", "valid_from", "valid_to", "lead_time_weeks"], "inventory.lead_time")
    _numeric(lead_time, "lead_time_weeks", "inventory.lead_time")
    d = _iso_day(as_of)
    lt = lead_time.assign(valid_from=_date(lead_time, "valid_from", "inventory.lead_time"), valid_to=_date(lead_time, "valid_to", "inventory.lead_time"))
    if lt["valid_from"].isna().any() or (lt["valid_to"] < lt["valid_from"]).any():
        raise FrameError("inventory.lead_time has a row without valid_from or a row that ends before it starts")
    lt = lt.sort_values(["sup_key", "itm_key", "valid_from"], kind="stable")
    lt["previous_weeks"] = lt.groupby(["sup_key", "itm_key"])["lead_time_weeks"].shift(1)
    cur = lt[(lt["valid_from"] <= d) & (lt["valid_to"].isna() | (lt["valid_to"] >= d))]
    if cur.duplicated(["sup_key", "itm_key"]).any():
        k = cur[cur.duplicated(["sup_key", "itm_key"], keep=False)].iloc[0]
        raise FrameError(f"two lead time rows are valid on the date for {k['sup_key']} {k['itm_key']}")
    cur = cur.assign(change_weeks=cur["lead_time_weeks"] - cur["previous_weeks"], change_percent=(cur["lead_time_weeks"] - cur["previous_weeks"]) / cur["previous_weeks"].where(cur["previous_weeks"] > 0) * 100.0)
    return cur[["sup_key", "itm_key", "lead_time_weeks", "valid_from", "previous_weeks", "change_weeks", "change_percent"]].reset_index(drop=True)


@staged(sources=("inventory.lead_time.lead_time_weeks",), kb=_KB)
def lead_time_alerts(lead_on: pd.DataFrame, *, min_rise_weeks: float = 8.0, min_rise_percent: float = 25.0) -> pd.DataFrame:
    """Use this when you need the supplier and item pairs whose lead time rose sharply against the previous valid row.

    The pairs of a lead_time_on frame whose lead time rose by at least min_rise_weeks AND at least min_rise_percent against the previous valid row (PROPOSED policy.delivery.lead_time_alert, needed: 8 weeks and 25 percent; the threshold must exceed the normal drift of a lead time in either direction). Rows without a previous value are never alerts.

    Args:
        lead_on: Output of lead_time_on; it needs sup_key, itm_key, lead_time_weeks, previous_weeks, change_weeks and change_percent.
        min_rise_weeks: The smallest rise in weeks that counts, a number of zero or more (default 8.0, PROPOSED).
        min_rise_percent: The smallest rise in percent that counts, a number of zero or more (default 25.0, PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns of the input and nothing more, only the rows that meet both thresholds, sorted by change_weeks (high first), then sup_key and itm_key.

    Raises:
        FrameError: lead_on is not a DataFrame, has duplicate column names or lacks a needed column; min_rise_weeks or min_rise_percent is not a number of zero or more.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import lead_time_alerts
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lt = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900002"], "itm_key": ["ITM-900001", "ITM-900002", "ITM-900001"],
        ...                    "lead_time_weeks": [24.0, 14.0, 6.0], "previous_weeks": [12.0, 12.0, None],
        ...                    "change_weeks": [12.0, 2.0, None], "change_percent": [100.0, 16.7, None]})
        >>> lead_time_alerts(lt, context=ctx)[["sup_key", "itm_key", "change_weeks"]].to_dict("records")
        [{'sup_key': 'SUP-900001', 'itm_key': 'ITM-900001', 'change_weeks': 12.0}]"""
    _need(lead_on, ["sup_key", "itm_key", "lead_time_weeks", "previous_weeks", "change_weeks", "change_percent"], "lead_time_on output")
    for name, v in (("min_rise_weeks", min_rise_weeks), ("min_rise_percent", min_rise_percent)):
        if isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not v >= 0:
            raise FrameError(f"{name} must be a number, zero or more, not {v!r}")
    hit = lead_on[(lead_on["change_weeks"] >= min_rise_weeks - _EPS) & (lead_on["change_percent"] >= min_rise_percent - _EPS)]
    return hit.sort_values(["change_weeks", "sup_key", "itm_key"], ascending=[False, True, True]).reset_index(drop=True)


@staged(sources=("procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.qty", "procurement.po_line.requested_date", "procurement.purchase_order.sup_key",
                 "procurement.purchase_order.status", "procurement.goods_receipt.receipt_no", "procurement.goods_receipt.receipt_date", "procurement.goods_receipt.qty_accepted"), kb=_KB,
        oracle="py:tests/test_procurement.py::test_supplier_performance")
def supplier_performance_recompute(po_line: pd.DataFrame, purchase_order: pd.DataFrame, goods_receipt: pd.DataFrame, as_of: DateLike, *, grace_days: int = 2) -> pd.DataFrame:
    """Use this when you need the lines due and on time per supplier and month rebuilt from the order lines and goods receipts up to a date.

    Lines due and on time per supplier and month of requested_date (the original due date), like procurement.supplier_performance. A line is due when requested_date is on or before the date, on time when the cumulative accepted quantity reached the ordered quantity (receipts up to the date) on or before requested_date plus grace_days (PROPOSED policy.delivery.supplier_on_time_rule, 2 days). Cancelled orders are left out. goods_receipt is one row per (po_key, line_no, receipt_no); a repeated key, or without a receipt_no an identical row, is refused.

    Args:
        po_line: The procurement.po_line frame; it needs po_key, line_no, qty (numeric without nulls) and requested_date, one row per po_key and line_no.
        purchase_order: The procurement.purchase_order frame; it needs po_key, sup_key (no nulls) and status, one row per po_key.
        goods_receipt: The procurement.goods_receipt frame; it needs po_key, line_no, receipt_date and qty_accepted (numeric, not negative, no nulls), and receipt_no when several receipts may look alike.
        as_of: The day to count up to, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
        grace_days: Whole days after requested_date that still count as on time, zero or more (default 2, PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns sup_key, period (YYYY-MM of requested_date), po_count, lines_due, lines_on_time and on_time_percent (rounded to 1 decimal), sorted by sup_key and period.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line or purchase_order has more than one row for a key; goods_receipt repeats a key or, without receipt_no, has identical rows; grace_days is not a whole number of zero or more; qty or qty_accepted is not numeric or has nulls; qty_accepted is negative; as_of is not an ISO date, is a number or has a time zone; an order has no sup_key; line_no has different types in po_line and goods_receipt; requested_date or receipt_date has nulls, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import supplier_performance_recompute
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "qty": [5.0, 3.0], "requested_date": ["2031-03-10", "2031-03-20"]})
        >>> orders = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"], "status": ["received"]})
        >>> gr = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "receipt_no": [1, 1],
        ...                    "receipt_date": ["2031-03-11", "2031-03-25"], "qty_accepted": [5.0, 3.0]})
        >>> r = supplier_performance_recompute(lines, orders, gr, "2031-04-01", context=ctx)
        >>> r[["sup_key", "period", "lines_due", "lines_on_time", "on_time_percent"]].to_dict("records")
        [{'sup_key': 'SUP-900001', 'period': '2031-03', 'lines_due': 2, 'lines_on_time': 1, 'on_time_percent': 50.0}]"""
    _need(po_line, ["po_key", "line_no", "qty", "requested_date"], "procurement.po_line", keys=("po_key", "line_no"))
    _need(purchase_order, ["po_key", "sup_key", "status"], "procurement.purchase_order", keys=("po_key",))
    _need(goods_receipt, ["po_key", "line_no", "receipt_date", "qty_accepted"], "procurement.goods_receipt", keys=("po_key", "line_no", "receipt_no") if "receipt_no" in goods_receipt.columns else ())
    if "receipt_no" not in goods_receipt.columns and goods_receipt.duplicated().any():
        raise FrameError("procurement.goods_receipt has identical rows and no receipt_no to tell them apart; a repeated row would count its quantity twice")
    if isinstance(grace_days, bool) or not isinstance(grace_days, (int, np.integer)) or grace_days < 0:
        raise FrameError(f"grace_days must be a whole number of days, zero or more, not {grace_days!r}")
    _numeric(po_line, "qty", "procurement.po_line")
    _numeric(goods_receipt, "qty_accepted", "procurement.goods_receipt")
    d = _iso_day(as_of)
    if purchase_order["sup_key"].isna().any():
        raise FrameError("procurement.purchase_order has an order without sup_key")
    if (goods_receipt["qty_accepted"] < 0).any():
        raise FrameError("procurement.goods_receipt.qty_accepted has a negative quantity; returns are not netted here")
    if len(goods_receipt) and _kind(po_line["line_no"]) != _kind(goods_receipt["line_no"]):
        raise FrameError("procurement.po_line.line_no and goods_receipt.line_no have different types")
    lines = po_line[["po_key", "line_no", "qty", "requested_date"]].merge(purchase_order[purchase_order["status"] != "cancelled"][["po_key", "sup_key"]], on="po_key", how="inner")
    lines["due"] = _date(lines, "requested_date", "procurement.po_line")
    if lines["due"].isna().any():
        raise FrameError("procurement.po_line.requested_date has nulls")
    lines = lines[lines["due"] <= d]
    gr = goods_receipt.assign(_d=_date(goods_receipt, "receipt_date", "procurement.goods_receipt"))
    if gr["_d"].isna().any():
        raise FrameError("procurement.goods_receipt.receipt_date has nulls")
    gr = gr[gr["_d"] <= d].sort_values(["po_key", "line_no", "_d"], kind="stable")
    gr["cum"] = gr.groupby(["po_key", "line_no"])["qty_accepted"].cumsum()
    m = gr.merge(lines[["po_key", "line_no", "qty"]], on=["po_key", "line_no"], how="inner")
    done = cast(pd.DataFrame, m[m["cum"] >= m["qty"] - _EPS].groupby(["po_key", "line_no"], as_index=False)["_d"].min()).rename(columns={"_d": "done"})
    lines = lines.merge(done, on=["po_key", "line_no"], how="left")
    lines["on_time"] = lines["done"].notna() & (lines["done"] <= lines["due"] + pd.DateOffset(days=int(grace_days)))
    lines["period"] = lines["due"].dt.strftime("%Y-%m")
    out = lines.groupby(["sup_key", "period"], as_index=False).agg(po_count=("po_key", "nunique"), lines_due=("line_no", "size"), lines_on_time=("on_time", "sum"))
    out["lines_on_time"] = out["lines_on_time"].astype("int64")
    out["on_time_percent"] = (100.0 * out["lines_on_time"] / out["lines_due"]).round(1)
    return out.sort_values(["sup_key", "period"]).reset_index(drop=True)


@staged(sources=("procurement.supplier_performance.sup_key", "procurement.supplier_performance.period", "procurement.supplier_performance.lines_due", "procurement.supplier_performance.lines_on_time"),
        kb=_KB)
def supplier_performance_window(performance: pd.DataFrame, first_period: str, last_period: str, *, sup_key: str | None = None) -> pd.DataFrame:
    """Use this when you need the on time share of suppliers over a window of months, weighted by lines.

    On time share over a window of months (inclusive, text YYYY-MM) by summed lines, never by averaging the monthly percentages. The input is supplier_performance_recompute or the stored table. Suppliers without lines in the window are absent. A null period is refused.

    Args:
        performance: Output of supplier_performance_recompute or the procurement.supplier_performance table; it needs sup_key, period (YYYY-MM, no nulls), lines_due and lines_on_time (numeric without nulls, lines_on_time not above lines_due), one row per supplier and period.
        first_period: First month of the window as text YYYY-MM.
        last_period: Last month of the window as text YYYY-MM, not before first_period.
        sup_key: Optional supplier key as text; limits the result to that supplier.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns sup_key, lines_due, lines_on_time, on_time_percent (null when the supplier has no lines due) and n_months, one row per supplier, sorted by sup_key.

    Raises:
        FrameError: performance is not a DataFrame, has duplicate column names or lacks a needed column; sup_key is not one key as text; a period is null; first_period or last_period is not a month as text YYYY-MM; lines_due or lines_on_time is not numeric or has nulls; a supplier key is null or a supplier has more than one row for a month; a row has more lines on time than lines due or negative lines; the window ends before it starts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import supplier_performance_window
        >>> ctx = Context(stage="month12", role="analyst")
        >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900001"], "period": ["2031-01", "2031-02", "2031-03"],
        ...                      "lines_due": [10, 30, 5], "lines_on_time": [10, 15, 0]})
        >>> r = supplier_performance_window(perf, "2031-01", "2031-02", context=ctx)
        >>> r.to_dict("records")
        [{'sup_key': 'SUP-900001', 'lines_due': 40, 'lines_on_time': 25, 'on_time_percent': 62.5, 'n_months': 2}]"""
    _need(performance, ["sup_key", "period", "lines_due", "lines_on_time"], "supplier performance")
    if sup_key is not None:
        _one_key(sup_key, "sup_key")
    if performance["period"].isna().any():
        raise FrameError("supplier performance has a row without period")
    for name, v in (("first_period", first_period), ("last_period", last_period)):
        if not isinstance(v, str) or re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v) is None:
            raise FrameError(f"{name} is a month as text YYYY-MM, not {v!r}")
    _numeric(performance, "lines_due", "supplier performance")
    _numeric(performance, "lines_on_time", "supplier performance")
    if performance["sup_key"].isna().any() or performance.duplicated(["sup_key", "period"]).any():
        raise FrameError("supplier performance has a null sup_key or more than one row for a supplier and month")
    if (performance["lines_on_time"] > performance["lines_due"]).any() or (performance["lines_due"] < 0).any():
        raise FrameError("supplier performance has more lines on time than lines due, or negative lines")
    if last_period < first_period:
        raise FrameError("the window ends before it starts")
    w = performance[(performance["period"] >= first_period) & (performance["period"] <= last_period)]
    if sup_key is not None:
        w = w[w["sup_key"] == sup_key]
    out = w.groupby("sup_key", as_index=False).agg(lines_due=("lines_due", "sum"), lines_on_time=("lines_on_time", "sum"), n_months=("period", "nunique"))
    out["on_time_percent"] = np.where(out["lines_due"] > 0, 100.0 * out["lines_on_time"] / out["lines_due"].where(out["lines_due"] > 0), np.nan)
    return out[["sup_key", "lines_due", "lines_on_time", "on_time_percent", "n_months"]].sort_values("sup_key").reset_index(drop=True)


@staged(sources=("inventory.stock_level.on_hand", "gis.grid_element.element_type", "gis.grid_element.status", "gis.grid_element.zone_key", "gis.grid_element.commissioned_date"), kb=_KB)
def elements_per_spare_unit(stock: pd.DataFrame, grid_element: pd.DataFrame, *, items: Sequence[str], site: str, element_types: Sequence[str] = ("transformer_station", "substation"),
                            status: str = "in_service", zone_keys: Sequence[str] | None = None, as_of: DateLike | None = None) -> pd.DataFrame:
    """Use this when you need how many installed grid elements share one spare switchgear unit in stock.

    Installed grid elements that house the switchgear divided by the spare units of the items at the site (stock_on output, each balance counted from zero up, so a negative balance does not cancel a positive one). A higher elements_per_spare_unit is thinner cover; it is null when no spare unit is left. Element types and status are the parameter thin_cover of inventory.yaml (passed in, the grid frame is not read for config). Every zone counts unless `zone_keys` is passed: one row per zone key passed, or one row for all zones. The date is `as_of`, or the one `as_of` of the stock frame when it has one (a frame of several dates, or of another date than `as_of`, is refused); with a date, only elements with commissioned_date on or before it are installed (a null commissioned_date counts as not yet commissioned; `as_of` given and no commissioned_date column is refused). Without a date at all every element of the grid frame counts, as at the date of that frame.

    Args:
        stock: Output of stock_on; it needs site_key, itm_key and on_hand (numeric without nulls), one row per site and item.
        grid_element: The gis.grid_element frame; it needs element_type, status and zone_key, and commissioned_date when a date is used.
        items: The item keys of the switchgear, a list or a single key.
        site: The site key as text whose stock is counted.
        element_types: The element types that house the switchgear (default transformer_station and substation).
        status: The status an element must have to count (default in_service).
        zone_keys: Optional zone keys as text; one row per zone. Without it one row covers all zones.
        as_of: Optional day to count elements on, a date, a Timestamp or an ISO text YYYY-MM-DD.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns zone_key (null for all zones), installed_elements, spare_units and elements_per_spare_unit (rounded to one decimal), one row per zone key passed or a single row.

    Raises:
        FrameError: stock or grid_element is not a DataFrame, has duplicate column names or lacks a needed column; the stock frame is for another date than as_of, holds more than one date or has more than one row for a site and item; as_of is not an ISO date, is a number or has a time zone; site or status is not text; on_hand is not numeric or has nulls; as_of is given and grid_element lacks commissioned_date or holds a value there that is not a date; items, element_types or zone_keys is a frame, a mapping or None; a zone key is not text.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import elements_per_spare_unit
        >>> ctx = Context(stage="month12", role="analyst")
        >>> stock = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900001"], "itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [2.0, -1.0]})
        >>> grid = pd.DataFrame({"element_type": ["substation", "substation", "substation", "cable"], "status": ["in_service"] * 4,
        ...                      "zone_key": ["ZONE-0001", "ZONE-0001", "ZONE-0002", "ZONE-0001"]})
        >>> r = elements_per_spare_unit(stock, grid, items=["ITM-900001", "ITM-900002"], site="SIT-900001", zone_keys=["ZONE-0001"], context=ctx)
        >>> r.to_dict("records")
        [{'zone_key': 'ZONE-0001', 'installed_elements': 2, 'spare_units': 2.0, 'elements_per_spare_unit': 1.0}]"""
    _need(stock, ["site_key", "itm_key", "on_hand"], "stock_on output")
    _need(grid_element, ["element_type", "status", "zone_key"], "gis.grid_element")
    its, types = _keys(items, "items"), _keys(element_types, "element_types")
    d = None if as_of is None else _iso_day(as_of)
    found = _stock_day(stock, d)
    if d is None:
        d = found
    if not isinstance(site, str) or not isinstance(status, str):
        raise FrameError("site and status are single keys given as text")
    _numeric(stock, "on_hand", "stock_on output")
    spare = float(stock[(stock["site_key"] == site) & stock["itm_key"].isin(its)]["on_hand"].clip(lower=0.0).sum())
    el = grid_element[grid_element["element_type"].isin(types) & (grid_element["status"] == status)]
    if d is not None and "commissioned_date" in grid_element.columns:
        el = el[_date(el, "commissioned_date", "gis.grid_element") <= d]
    elif as_of is not None:
        raise FrameError("gis.grid_element lacks commissioned_date; load the source columns without renaming them")
    def row(zone: str | None, n: int) -> dict[str, Any]:
        return {"zone_key": zone, "installed_elements": int(n), "spare_units": spare, "elements_per_spare_unit": round(n / spare, 1) if spare > _EPS else np.nan}
    if zone_keys is None:
        return pd.DataFrame([row(None, len(el))])
    zk = _keys(zone_keys, "zone_keys")
    if any(not isinstance(z, str) for z in zk):
        raise FrameError("zone_keys are text keys without nulls")
    return pd.DataFrame([row(z, int((el["zone_key"] == z).sum())) for z in sorted(zk)], columns=["zone_key", "installed_elements", "spare_units", "elements_per_spare_unit"])


@staged(sources=("inventory.stock_level.on_hand", "procurement.po_line.promised_date", "procurement.po_line.requested_date", "inventory.lead_time.lead_time_weeks", "procurement.supplier_performance.on_time_percent"), kb=_KB)
def at_risk_items(items: Sequence[str], stock: pd.DataFrame, open_lines: pd.DataFrame, alerts: pd.DataFrame, window_performance: pd.DataFrame, *, site: str, sup_key: str, as_of: DateLike,
                  min_on_time_percent: float = 75.0, min_lines: int | None = None) -> pd.DataFrame:
    """Use this when you need to flag which items of one supplier are at risk from stock, slipping order lines, lead time alerts or poor on time delivery.

    Per item of a supplier: stock_zero (on hand at the site zero or less), n_slipping_lines (open lines of the supplier promised later than requested or already past their promise, from an open_po_lines frame built for the same date as `as_of`), lead_time_alert (the item is in the alerts), on_time_percent (supplier_performance_window row of the supplier) and low_on_time (below min_on_time_percent, PROPOSED 75). lines_due is the supplier's line count of the window (null when the window frame has no lines_due column): OP.STD.002 flags a supplier with few lines only with the count shown, so read low_on_time with it; min_lines (None) adds thin_window, true when lines_due is below it or unknown (the supplier has no row in the window frame, no line in the window being the thinnest window, or the frame has no lines_due column), and does not change low_on_time or at_risk. no_stock_row is true for an item with no row in the stock frame at the site: it counts as zero stock (stock_zero true, as in blocked_projects), so a mistyped or unstocked item shows up as at risk with this flag set. The stock frame, when it has an `as_of` column (stock_on output), must be for `as_of`; open_lines carries no date, build it with open_po_lines for the same date. at_risk is true when any of the four holds.

    Args:
        items: The item keys of the supplier to judge, a list or a single key.
        stock: Output of stock_on; it needs site_key, itm_key and on_hand, one row per site and item, and when it has an as_of column that is one date equal to `as_of`.
        open_lines: Output of open_po_lines for the same date; it needs sup_key, itm_key, slip_days and days_overdue.
        alerts: Output of lead_time_alerts; it needs sup_key and itm_key.
        window_performance: Output of supplier_performance_window; it needs sup_key and on_time_percent, and lines_due for the line count, at most one row for the supplier.
        site: The site key whose stock is judged.
        sup_key: The supplier key as text.
        as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
        min_on_time_percent: Below this on time percent the supplier counts as low (default 75.0, PROPOSED).
        min_lines: Optional whole number of zero or more; a window with fewer lines than this, or an unknown line count, sets thin_window.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per item and the columns itm_key, stock_zero, n_slipping_lines, lead_time_alert, on_time_percent, lines_due, low_on_time, thin_window, no_stock_row and at_risk, sorted by itm_key.

    Raises:
        FrameError: as_of is not an ISO date, is a number or has a time zone; sup_key is not one key as text; a frame is not a DataFrame, has duplicate column names or lacks a needed column; the stock frame is for another date than as_of, holds more than one date or has more than one row for a site and item; min_lines is not a whole number of zero or more or None; items is a frame, a mapping or None; window_performance has more than one row for the supplier or a non-numeric on_time_percent.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import at_risk_items
        >>> ctx = Context(stage="month12", role="analyst")
        >>> stock = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900001"], "itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [0.0, 5.0]})
        >>> lines = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900002"], "slip_days": [0], "days_overdue": [0]})
        >>> alerts = pd.DataFrame({"sup_key": [], "itm_key": []})
        >>> perf = pd.DataFrame({"sup_key": ["SUP-900001"], "lines_due": [40], "on_time_percent": [90.0]})
        >>> r = at_risk_items(["ITM-900001", "ITM-900002"], stock, lines, alerts, perf, site="SIT-900001", sup_key="SUP-900001", as_of="2031-04-01", context=ctx)
        >>> r[["itm_key", "stock_zero", "at_risk"]].to_dict("records")
        [{'itm_key': 'ITM-900001', 'stock_zero': True, 'at_risk': True}, {'itm_key': 'ITM-900002', 'stock_zero': False, 'at_risk': False}]"""
    d = _iso_day(as_of)
    _one_key(sup_key, "sup_key")
    _need(stock, ["site_key", "itm_key", "on_hand"], "stock_on output")
    _stock_day(stock, d)
    if min_lines is not None and (isinstance(min_lines, bool) or not isinstance(min_lines, (int, np.integer)) or min_lines < 0):
        raise FrameError(f"min_lines is a whole number, zero or more, or None, not {min_lines!r}")
    _need(open_lines, ["sup_key", "itm_key", "slip_days", "days_overdue"], "open_po_lines output")
    _need(alerts, ["sup_key", "itm_key"], "lead_time_alerts output")
    _need(window_performance, ["sup_key", "on_time_percent"], "supplier_performance_window output")
    its = sorted(_keys(items, "items"))
    perf = window_performance[window_performance["sup_key"] == sup_key]["on_time_percent"]
    if len(perf) > 1:
        raise FrameError(f"supplier_performance_window output has more than one row for {sup_key}")
    pct = float(pd.to_numeric(perf, errors="raise").iloc[0]) if len(perf) else np.nan
    n_lines = float(window_performance[window_performance["sup_key"] == sup_key]["lines_due"].iloc[0]) if len(perf) and "lines_due" in window_performance.columns else np.nan
    rows = []
    for itm in its:
        here = stock[(stock["site_key"] == site) & (stock["itm_key"] == itm)]
        oh = float(here["on_hand"].sum())
        slip = int(((open_lines["sup_key"] == sup_key) & (open_lines["itm_key"] == itm) & ((open_lines["slip_days"] > 0) | (open_lines["days_overdue"] > 0))).sum())
        alert = bool(((alerts["sup_key"] == sup_key) & (alerts["itm_key"] == itm)).any())
        low = bool(pct < min_on_time_percent) if not np.isnan(pct) else False
        rows.append({"itm_key": itm, "stock_zero": oh <= _EPS, "n_slipping_lines": slip, "lead_time_alert": alert, "on_time_percent": pct, "lines_due": n_lines, "low_on_time": low,
                     "thin_window": bool(min_lines is not None and (np.isnan(n_lines) or n_lines < min_lines)), "no_stock_row": bool(here.empty), "at_risk": bool(oh <= _EPS or slip > 0 or alert or low)})
    return pd.DataFrame(rows, columns=["itm_key", "stock_zero", "n_slipping_lines", "lead_time_alert", "on_time_percent", "lines_due", "low_on_time", "thin_window", "no_stock_row", "at_risk"])


@staged(sources=("inventory.stock_movement.site_key", "inventory.stock_movement.itm_key", "inventory.stock_movement.movement_date", "inventory.stock_movement.movement_type", "inventory.stock_movement.qty",
                 "inventory.lead_time.sup_key", "inventory.lead_time.itm_key", "inventory.lead_time.valid_from", "inventory.lead_time.valid_to", "inventory.lead_time.lead_time_weeks",
                 "inventory.item.itm_key", "inventory.item.stocked", "inventory.item.preferred_sup_key"), kb=_KB, oracle="py:tests/test_network_contingency_stock_views.py::test_minimum_stock_rule_window_and_stocked_items")
def minimum_stock(stock_movement: pd.DataFrame, lead_time: pd.DataFrame, item: pd.DataFrame, as_of: DateLike, *, window_weeks: float = 52.0, usage_types: Sequence[str] = ("issue_project", "issue_ticket"),
                  min_floor: float = 1.0) -> pd.DataFrame:
    """Use this when you need a suggested minimum and order up to level of stock per stocked site and item from recent usage and lead time.

    Minimum, order up to level and cover weeks per stocked (site, item) pair from the usage in the last `window_weeks` weeks before the date (PROPOSED 52, the issues of `usage_types`) and the lead time of the item's preferred supplier on the date. PROPOSED rule (policy.delivery.minimum_stock_rule is needed; LOW confidence): rate = units issued per week over the window, or over the weeks since the first movement when the data starts inside it (`history_weeks`); min = max(`min_floor`, ceil(rate x (lead time weeks + cover_weeks_min)), ceil(event_cover x average issue quantity)); order up to = max(min + 1, ceil(min + rate x cover_weeks_order), min + ceil(event_cover x average issue quantity)); the cover parameters are the generator values procurement.yaml#stock (cover_weeks_min 2, cover_weeks_order 6, event_cover 1.5, synthetic). Pack sizes and fixed levels set in the generator config are not applied. Pairs without usage in the window and items that are not stocked are not listed. The result is a suggestion: compare it with `stock_level.min_level` in the measured notes, it is not that table.

    Args:
        stock_movement: The inventory.stock_movement frame; it needs site_key, itm_key, movement_date, movement_type and qty (no nulls; issues are negative).
        lead_time: The inventory.lead_time frame; it needs sup_key, itm_key, valid_from, valid_to and lead_time_weeks, as lead_time_on reads it.
        item: The inventory.item frame; it needs itm_key (one row per item), stocked and preferred_sup_key, and critical when the flag should be carried.
        as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
        window_weeks: Length of the usage window in weeks, a number above zero (default 52.0, PROPOSED).
        usage_types: The movement types that count as usage, a tuple of text (default issue_project and issue_ticket).
        min_floor: The lowest minimum quantity (default 1.0).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns site_key, itm_key, sup_key, lead_time_weeks, rate_per_week, avg_issue_qty, n_issues, history_weeks, min_qty, order_up_to_qty, cover_weeks (min over rate; null without usage) and critical (only when the item frame has the flag), sorted by site_key and itm_key.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; inventory.item has more than one row for an item; usage_types is a text instead of a tuple; window_weeks is not a positive number; as_of is not an ISO date, is a number or has a time zone; qty has nulls; the movements of an item that inventory.item does not hold; a usage movement has a positive quantity; a listed item has no lead time row on the date for its preferred supplier; inventory.item.critical has nulls; lead_time has a value that lead_time_on refuses.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import minimum_stock
        >>> ctx = Context(stage="month12", role="analyst")
        >>> mv = pd.DataFrame({"site_key": ["SIT-900001"] * 3, "itm_key": ["ITM-900001"] * 3, "movement_type": ["issue_project"] * 3,
        ...                    "movement_date": ["2031-05-01", "2031-05-08", "2031-05-15"], "qty": [-2.0, -2.0, -2.0]})
        >>> lt = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"], "valid_from": ["2031-01-01"], "valid_to": [None], "lead_time_weeks": [4.0]})
        >>> item = pd.DataFrame({"itm_key": ["ITM-900001"], "stocked": [True], "preferred_sup_key": ["SUP-900001"]})
        >>> r = minimum_stock(mv, lt, item, "2031-05-21", context=ctx)
        >>> r[["itm_key", "n_issues", "min_qty", "order_up_to_qty"]].to_dict("records")
        [{'itm_key': 'ITM-900001', 'n_issues': 3, 'min_qty': 12.0, 'order_up_to_qty': 24.0}]"""
    _need(stock_movement, ["site_key", "itm_key", "movement_date", "movement_type", "qty"], "inventory.stock_movement")
    _need(lead_time, ["sup_key", "itm_key", "valid_from", "valid_to", "lead_time_weeks"], "inventory.lead_time")
    _need(item, ["itm_key", "stocked", "preferred_sup_key"], "inventory.item")
    if item["itm_key"].duplicated().any():
        raise FrameError("inventory.item has more than one row for an item")
    if isinstance(usage_types, (str, bytes)):
        raise FrameError("usage_types must be a tuple of movement types")
    if isinstance(window_weeks, bool) or not isinstance(window_weeks, (int, float)) or not window_weeks > 0:
        raise FrameError("window_weeks must be a positive number")
    d = _iso_day(as_of)
    cmin, cord, ev = float(param("procurement.yaml#stock.cover_weeks_min").value), float(param("procurement.yaml#stock.cover_weeks_order").value), float(param("procurement.yaml#stock.event_cover").value)
    if stock_movement["qty"].isna().any():
        raise FrameError("inventory.stock_movement.qty has nulls")
    alldays = pd.to_datetime(stock_movement["movement_date"]).dt.normalize()
    first_pair = stock_movement.assign(_d=alldays)[alldays <= d].groupby(["site_key", "itm_key"])["_d"].min()                 # per pair: the first movement of any type
    mv = stock_movement[stock_movement["movement_type"].isin(list(usage_types))]
    day = pd.to_datetime(mv["movement_date"]).dt.normalize()
    mv = mv[(day <= d) & (day > d - pd.Timedelta(days=int(round(window_weeks * 7))))]
    missing_items = sorted(set(mv["itm_key"]) - set(item["itm_key"]))
    if missing_items:
        raise FrameError(f"stock movements of items that inventory.item does not hold, for example {missing_items[0]}")
    if (mv["qty"] > 0).any():
        raise FrameError("a usage movement has a positive quantity; issues are negative")
    g = mv.assign(_q=-mv["qty"]).groupby(["site_key", "itm_key"], as_index=False).agg(total=("_q", "sum"), n_issues=("_q", "size"))
    g = g[g["total"] > 0]
    stocked = item[item["stocked"].astype(bool)].set_index("itm_key")["preferred_sup_key"]
    g = g[g["itm_key"].isin(set(stocked.index))].copy()
    g["sup_key"] = g["itm_key"].map(stocked)
    lt = cast(Any, lead_time_on).__wrapped__(lead_time, d)
    ltm = lt.set_index(["sup_key", "itm_key"])["lead_time_weeks"]
    miss = [(a, b) for a, b in zip(g["sup_key"], g["itm_key"]) if (a, b) not in ltm.index]
    if miss:
        raise FrameError(f"no lead time on the date for supplier {miss[0][0]}, item {miss[0][1]}")
    g["lead_time_weeks"] = [float(ltm.loc[(a, b)]) for a, b in zip(g["sup_key"], g["itm_key"])]
    fp = pd.Series([first_pair.get((a, b), pd.NaT) for a, b in zip(g["site_key"], g["itm_key"])], index=g.index)
    eff = np.minimum(float(window_weeks), np.maximum(((d - fp).dt.days + 1) / 7.0, 1.0))          # a pair that starts inside the window: the rate is over the weeks it exists
    eff = eff.fillna(float(window_weeks))
    g["rate_per_week"] = g["total"] / eff
    g["history_weeks"] = eff.round(2)
    g["avg_issue_qty"] = g["total"] / g["n_issues"]
    qev = np.ceil(ev * g["avg_issue_qty"] - 1e-9)
    mn = cast(Any, np.maximum).reduce([np.full(len(g), float(min_floor)), np.ceil(g["rate_per_week"] * (g["lead_time_weeks"] + cmin) - 1e-9).to_numpy(), qev.to_numpy()])
    mx = cast(Any, np.maximum).reduce([mn + 1.0, np.ceil(mn + g["rate_per_week"].to_numpy() * cord - 1e-9), mn + qev.to_numpy()])
    g["min_qty"], g["order_up_to_qty"] = mn, mx
    g["cover_weeks"] = (g["min_qty"] / g["rate_per_week"].where(g["rate_per_week"] > 0)).round(2)
    if "critical" in item.columns:
        crit = g["itm_key"].map(item.set_index("itm_key")["critical"])
        if crit.isna().any():
            raise FrameError("inventory.item.critical has nulls")
        g["critical"] = crit.astype(bool)
    return g[["site_key", "itm_key", "sup_key", "lead_time_weeks", "rate_per_week", "avg_issue_qty", "n_issues", "history_weeks", "min_qty", "order_up_to_qty", "cover_weeks"] + (["critical"] if "critical" in g.columns else [])].round(
        {"rate_per_week": 4, "avg_issue_qty": 3}).sort_values(["site_key", "itm_key"]).reset_index(drop=True)


class SupplyAnswer(NamedTuple):
    """The supply side of the supply strain question for a list of items and zones: stock, open order lines, blocked projects, lead times with alerts, supplier performance, spot orders, the thin cover rows and the customers
    of the zones. Every frame is limited to the items (or zones) passed in; no stock, order or price is computed here."""
    stock: pd.DataFrame
    open_lines: pd.DataFrame
    blocked_projects: pd.DataFrame
    lead_times: pd.DataFrame
    alerts: pd.DataFrame
    performance: pd.DataFrame
    spot_orders: pd.DataFrame
    thin_cover: pd.DataFrame
    customers: pd.DataFrame
    items: tuple[Any, ...]
    zones: tuple[Any, ...]


@staged(sources=("inventory.stock_level.on_hand", "procurement.po_line.itm_key", "inventory.lead_time.lead_time_weeks", "procurement.supplier_performance.sup_key", "gis.supply_zone.zone_key", "gis.supply_zone.cus_key",
                 "crm.customer.cus_key", "crm.customer.name"), kb=_KB)
def supply_strain_answer(items: Sequence[str], zones: Sequence[str], *, stock: pd.DataFrame, open_lines: pd.DataFrame, blocked: BlockedProjects, lead_on: pd.DataFrame, alerts: pd.DataFrame,
                     performance: pd.DataFrame, spot: pd.DataFrame, thin_cover: pd.DataFrame, supply_zone: pd.DataFrame, customer: pd.DataFrame) -> SupplyAnswer:
    """Use this when you need the supply side of the supply strain question assembled for the items and zones that the grid side of the answer in halvaro-grid hands over.

    Composes the outputs of this module for the item list and the zone list (keys only). Each frame is cut to the items: stock_on (itm_key), open_po_lines (itm_key), blocked_projects (its `items` frame), lead_time_on and its alerts, spot_orders, the thin cover frame (as passed, one row per zone key or all), and the supplier_performance_window rows of the suppliers of those items (the suppliers in the lead time frame). The customers are those of the zones (gis.supply_zone.cus_key) with their names. An item or a zone that is not in any frame is not an error (an empty cut is honest). Nothing is computed here: no stock, order or price is calculated, the frames are only cut and joined.

    Args:
        items: The item keys as a list of text, from the grid side of the answer (halvaro-grid).
        zones: The zone keys as a list of text, from the grid side of the answer (halvaro-grid); each must be in gis.supply_zone.
        stock: Output of stock_on; it needs itm_key.
        open_lines: Output of open_po_lines; it needs itm_key.
        blocked: Output of blocked_projects; its `items` frame needs itm_key.
        lead_on: Output of lead_time_on; it needs itm_key, and sup_key to pick the suppliers.
        alerts: Output of lead_time_alerts; it needs itm_key.
        performance: Output of supplier_performance_window or the stored table; it needs sup_key.
        spot: Output of spot_orders; it needs itm_key.
        thin_cover: Output of elements_per_spare_unit, passed through; when it has zone_key, rows of other zones are dropped and the row for all zones (null zone_key) is kept.
        supply_zone: The gis.supply_zone frame; it needs zone_key and cus_key.
        customer: The crm.customer frame; it needs cus_key (one row per customer) and name.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A SupplyAnswer tuple with the frames stock, open_lines, blocked_projects, lead_times, alerts, performance, spot_orders, thin_cover and customers (zone_key, cus_key, name, sorted by zone_key), and the sorted tuples items and zones.

    Raises:
        FrameError: items or zones is a frame, a mapping or None, or holds a key that is not text; a frame is not a DataFrame, has duplicate column names or lacks a needed column; a zone is not in gis.supply_zone; crm.customer has more than one row for a customer.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import supply_strain_answer
        >>> from halvaro.delivery.supply import BlockedProjects
        >>> ctx = Context(stage="month12", role="analyst")
        >>> by_item = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [0.0, 5.0]})
        >>> lead = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900002"], "itm_key": ["ITM-900001", "ITM-900002"]})
        >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900002"], "on_time_percent": [60.0, 95.0]})
        >>> zone = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0002"], "cus_key": ["CUS-900001", "CUS-900002"]})
        >>> cus = pd.DataFrame({"cus_key": ["CUS-900001", "CUS-900002"], "name": ["Customer A", "Customer B"]})
        >>> empty = by_item.iloc[:0]
        >>> a = supply_strain_answer(["ITM-900001"], ["ZONE-0001"], stock=by_item, open_lines=empty, blocked=BlockedProjects(empty, empty), lead_on=lead, alerts=empty,
        ...                      performance=perf, spot=empty, thin_cover=pd.DataFrame({"zone_key": [None]}), supply_zone=zone, customer=cus, context=ctx)
        >>> a.stock["itm_key"].tolist(), a.performance["sup_key"].tolist(), a.customers["name"].tolist()
        (['ITM-900001'], ['SUP-900001'], ['Customer A'])"""
    it, zn = _keys(items, "items"), _keys(zones, "zones")
    if not all(isinstance(k, str) for k in it | zn):
        raise FrameError("items and zones are lists of text keys")
    for nm, fr, col in (("stock", stock, "itm_key"), ("open_lines", open_lines, "itm_key"), ("lead_on", lead_on, "itm_key"), ("alerts", alerts, "itm_key"), ("spot", spot, "itm_key")):
        _need(fr, [col], nm)
    _need(blocked.items, ["itm_key"], "blocked.items")
    _need(performance, ["sup_key"], "performance")
    _need(supply_zone, ["zone_key", "cus_key"], "gis.supply_zone")
    _need(customer, ["cus_key", "name"], "crm.customer")
    bad = sorted(zn - set(supply_zone["zone_key"]))
    if bad:
        raise FrameError(f"zone {bad[0]} is not in gis.supply_zone")
    cut = lambda f: f[f["itm_key"].isin(it)].reset_index(drop=True)                                       # noqa: E731
    lead = cut(lead_on)
    perf = performance[performance["sup_key"].isin(set(lead["sup_key"]))].reset_index(drop=True) if "sup_key" in lead.columns else performance.iloc[:0]
    if customer["cus_key"].duplicated().any():
        raise FrameError("crm.customer has more than one row for a customer")
    z = supply_zone[supply_zone["zone_key"].isin(zn)][["zone_key", "cus_key"]].merge(customer[["cus_key", "name"]], on="cus_key", how="left").sort_values("zone_key").reset_index(drop=True)
    tc = thin_cover if "zone_key" not in thin_cover.columns else thin_cover[thin_cover["zone_key"].isna() | thin_cover["zone_key"].isin(zn)].reset_index(drop=True)
    return SupplyAnswer(cut(stock), cut(open_lines), cut(blocked.items), lead, cut(alerts), perf, cut(spot), tc, z, tuple(sorted(it)), tuple(sorted(zn)))
