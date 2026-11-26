"""Subledgers: open items of receivables and payables on a date, retention, ageing, bad debt candidates and customer exposure.

Open items use the payment dates up to `as_of`, never `paid_amount` or `status` (values at the release date). Amounts are in the entity currency, credit notes negative.
"""
from __future__ import annotations

import datetime as dt
from typing import Sequence

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, convert, fact, make_envelope

from ._guard import staged
from ._util import _cents, _control, _day, _days, _entity_currency, _need, _opening

_BAD_DEBT = "fin.payment.bad_debt_write_off_after_days_overdue"
_FX_FACTS = ("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed")
_BUCKETS = (0, 30, 60, 90)              # PROPOSED: policy.ageing.buckets (needed): days past due, not due, 1 to 30, 31 to 60, 61 to 90, over 90
_ALLOC = ["le_key", "bank_account", "payment_no"]


def _paid(payment_allocation: pd.DataFrame, payment: pd.DataFrame, kinds: Sequence[str], d: pd.Timestamp) -> pd.DataFrame:
    """Allocations of the given kinds with a payment on or before the date, signed like the document (a credit note allocation is negative)."""
    _need(payment_allocation, [*_ALLOC, "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"], "finance.payment_allocation")
    _need(payment, [*_ALLOC, "payment_date"], "finance.payment")
    pay = _days(payment[[*_ALLOC, "payment_date"]], ["payment_date"], "finance.payment")
    a = payment_allocation[payment_allocation["allocation_kind"].isin(kinds)].merge(pay, on=_ALLOC, how="left", validate="many_to_one")
    if a["payment_date"].isna().any():
        raise FrameError(f"{int(a['payment_date'].isna().sum())} allocations name a payment that is not in finance.payment")
    a = a[a["payment_date"] <= d].copy()
    a["c"] = _cents(a["booked_amount"]) * np.where(a["document_type"] == "credit_note", -1, 1)
    return a




@staged(sources=("finance.customer_invoice.inv_key", "finance.customer_invoice.le_key", "finance.customer_invoice.cus_key", "finance.customer_invoice.invoice_type", "finance.customer_invoice.invoice_date", "finance.customer_invoice.due_date", "finance.customer_invoice.gross_amount_le", "finance.customer_invoice.retention_amount_le", "finance.customer_invoice.retention_release_date", "finance.customer_invoice.written_off_date", "finance.customer_invoice.counterpart_le_key", "finance.payment_allocation.le_key", "finance.payment_allocation.bank_account", "finance.payment_allocation.payment_no", "finance.payment_allocation.allocation_kind", "finance.payment_allocation.document_type", "finance.payment_allocation.booked_amount", "finance.payment_allocation.inv_key", "finance.payment_allocation.opening_item_ref", "finance.payment.le_key", "finance.payment.bank_account", "finance.payment.payment_no", "finance.payment.payment_date", "finance.opening_balance_item.le_key", "finance.opening_balance_item.gl_key", "finance.opening_balance_item.item_ref", "finance.opening_balance_item.document_date", "finance.opening_balance_item.due_date", "finance.opening_balance_item.amount", "finance.opening_balance_item.currency", "finance.opening_balance_item.cus_key", "finance.gl_account.gl_key", "finance.gl_account.control_type"),
        oracle="py:tests/test_finance.py::test_subledgers_reconcile_to_control_accounts_every_month_end")
def open_items_ar(customer_invoice: pd.DataFrame, payment_allocation: pd.DataFrame, payment: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the open receivables of every domestic invoice and opening item on a date.

    Rule: open_amount = invoice amount including retention - payments allocated up to and including the date - amount written off up to the date; credit notes are negative. retention_held is the
    retention billed and not yet released on the date; the receivable account holds open_amount less retention_held and the retention account holds the rest. Only payments with a date up to
    the date count, never the stored paid_amount or status (values at the release date). Intercompany invoices are not receivables and are left out.

    Args:
        customer_invoice: Frame finance.customer_invoice with inv_key, le_key, cus_key, invoice_type, invoice_date, due_date, gross_amount_le, retention_amount_le, retention_release_date,
            written_off_date and counterpart_le_key.
        payment_allocation: Frame finance.payment_allocation, the allocation of payments to documents.
        payment: Frame finance.payment with the allocation key columns and payment_date.
        opening_balance_item: Frame finance.opening_balance_item, open items at the start of the window; it also gives the currency of each entity.
        gl_account: Frame finance.gl_account with control_type per account (ar, retention).
        as_of: The date the open items are taken on (a date).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with item_key, source (invoice or opening), le_key, cus_key, inv_key, document_date, due_date, currency, invoice_amount, paid, written_off, open_amount, retention_held (all in the
        entity currency) and release_date, one row per invoice and opening item.
        Typed form: OpenItemArRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a frame lacks a required column, a date cannot be read, an allocation names a payment that is not in the payment frame, or the opening items are empty (the entity currencies are taken from them).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import open_items_ar
        >>> r = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
        >>> r[r["source"] == "invoice"][["open_amount", "retention_held"]].values.tolist()
        [[1000.0, 100.0]]
    """
    d = _day(as_of)
    _need(customer_invoice, ["inv_key", "le_key", "cus_key", "invoice_type", "invoice_date", "due_date", "gross_amount_le", "retention_amount_le", "retention_release_date", "written_off_date",
                             "counterpart_le_key"], "finance.customer_invoice")
    ar, ret = _control(gl_account, "ar"), _control(gl_account, "retention")
    ci = _days(customer_invoice[customer_invoice["counterpart_le_key"].isna()], ["invoice_date", "due_date", "retention_release_date", "written_off_date"], "finance.customer_invoice")
    ci = ci[ci["invoice_date"] <= d]
    cur = _entity_currency(opening_balance_item)
    sg = np.where(ci["invoice_type"] == "credit_note", -1, 1)
    gross, held = _cents(ci["gross_amount_le"]) * sg, _cents(ci["retention_amount_le"]) * sg
    alloc_all = _paid(payment_allocation, payment, ["inv", "inv_ret", "open_ar", "open_ret"], d)
    paid = alloc_all[alloc_all["allocation_kind"].isin(["inv", "inv_ret"])].groupby("inv_key")["c"].sum()
    collected = set(payment_allocation.loc[payment_allocation["allocation_kind"] == "inv_ret", "inv_key"])         # retention collected at some date: it is released on the release date
    released = ci["inv_key"].isin(collected).to_numpy() & (ci["retention_release_date"] <= d).to_numpy()
    wo = np.where((ci["written_off_date"] <= d).to_numpy(), _cents(ci["gross_amount_le"]), 0)
    inv = pd.DataFrame({"item_key": ci["inv_key"].to_numpy(), "source": "invoice", "le_key": ci["le_key"].to_numpy(), "cus_key": ci["cus_key"].to_numpy(), "inv_key": ci["inv_key"].to_numpy(),
                        "document_date": ci["invoice_date"].to_numpy(), "due_date": ci["due_date"].to_numpy(), "invoice_c": gross, "paid_c": ci["inv_key"].map(paid).fillna(0).astype(np.int64).to_numpy(),
                        "written_off_c": wo, "held_c": np.where(released, 0, held), "release_date": ci["retention_release_date"].to_numpy()})
    ob = _opening(opening_balance_item, [*ar, *ret])
    opaid = alloc_all[alloc_all["allocation_kind"].isin(["open_ar", "open_ret"])].groupby("opening_item_ref")["c"].sum()
    is_ret = ob["gl_key"].isin(ret).to_numpy()
    c0 = _cents(ob["amount"])
    still_held = is_ret & (ob["due_date"].isna() | (ob["due_date"] > d)).to_numpy()
    opn = pd.DataFrame({"item_key": ob["item_ref"].to_numpy(), "source": "opening", "le_key": ob["le_key"].to_numpy(), "cus_key": ob["cus_key"].to_numpy(), "inv_key": None,
                        "document_date": ob["document_date"].to_numpy(), "due_date": ob["due_date"].to_numpy(), "invoice_c": c0, "paid_c": ob["item_ref"].map(opaid).fillna(0).astype(np.int64).to_numpy(),
                        "written_off_c": 0, "held_c": np.where(still_held, c0, 0), "release_date": ob["due_date"].to_numpy()})
    out = pd.concat([inv, opn], ignore_index=True)
    out["currency"] = out["le_key"].map(cur)
    out["open_c"] = out["invoice_c"] - out["paid_c"] - out["written_off_c"]
    for col, new in (("invoice_c", "invoice_amount"), ("paid_c", "paid"), ("written_off_c", "written_off"), ("open_c", "open_amount"), ("held_c", "retention_held")):
        out[new] = out[col] / 100
    cols = ["item_key", "source", "le_key", "cus_key", "inv_key", "document_date", "due_date", "currency", "invoice_amount", "paid", "written_off", "open_amount", "retention_held", "release_date"]
    return out[cols].sort_values(["le_key", "source", "item_key"]).reset_index(drop=True)


@staged(sources=("finance.supplier_invoice.sinv_key", "finance.supplier_invoice.le_key", "finance.supplier_invoice.sup_key", "finance.supplier_invoice.invoice_type", "finance.supplier_invoice.invoice_date", "finance.supplier_invoice.due_date", "finance.supplier_invoice.payable_amount_le", "finance.payment_allocation.le_key", "finance.payment_allocation.bank_account", "finance.payment_allocation.payment_no", "finance.payment_allocation.allocation_kind", "finance.payment_allocation.document_type", "finance.payment_allocation.booked_amount", "finance.payment_allocation.sinv_key", "finance.payment_allocation.opening_item_ref", "finance.payment.le_key", "finance.payment.bank_account", "finance.payment.payment_no", "finance.payment.payment_date", "finance.opening_balance_item.le_key", "finance.opening_balance_item.gl_key", "finance.opening_balance_item.item_ref", "finance.opening_balance_item.document_date", "finance.opening_balance_item.due_date", "finance.opening_balance_item.amount", "finance.opening_balance_item.currency", "finance.opening_balance_item.sup_key", "finance.gl_account.gl_key", "finance.gl_account.control_type"),
        oracle="py:tests/test_finance.py::test_subledgers_reconcile_to_control_accounts_every_month_end")
def open_items_ap(supplier_invoice: pd.DataFrame, payment_allocation: pd.DataFrame, payment: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the open payables of every supplier invoice and opening item on a date.

    Rule: open_amount = payable amount - payments allocated up to and including the date; amounts owed are positive and credit notes negative. Payments after the date do not count, and the stored
    paid_amount and status (values at the release date) are not read.

    Args:
        supplier_invoice: Frame finance.supplier_invoice with sinv_key, le_key, sup_key, invoice_type, invoice_date, due_date and payable_amount_le.
        payment_allocation: Frame finance.payment_allocation, the allocation of payments to documents.
        payment: Frame finance.payment with the allocation key columns and payment_date.
        opening_balance_item: Frame finance.opening_balance_item, open items at the start of the window; it also gives the currency of each entity.
        gl_account: Frame finance.gl_account with control_type per account (ap).
        as_of: The date the open items are taken on (a date).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with item_key, source (invoice or opening), le_key, sup_key, sinv_key, document_date, due_date, currency, payable_amount_le, paid and open_amount (all in the entity currency),
        one row per invoice and opening item.
        Typed form: OpenItemApRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a frame lacks a required column, a date cannot be read, an allocation names a payment that is not in the payment frame, or the opening items are empty (the entity currencies are taken from them).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import open_items_ap
        >>> si = pd.DataFrame({"sinv_key": ["S1"], "le_key": "LE-01", "sup_key": "SUP-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "payable_amount_le": 500.0})
        >>> r = open_items_ap(si, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
        >>> r[r["source"] == "invoice"]["open_amount"].tolist()
        [500.0]
    """
    d = _day(as_of)
    _need(supplier_invoice, ["sinv_key", "le_key", "sup_key", "invoice_type", "invoice_date", "due_date", "payable_amount_le"], "finance.supplier_invoice")
    ap = _control(gl_account, "ap")
    si = _days(supplier_invoice, ["invoice_date", "due_date"], "finance.supplier_invoice")
    si = si[si["invoice_date"] <= d]
    cur = _entity_currency(opening_balance_item)
    alloc = _paid(payment_allocation, payment, ["sinv", "open_ap"], d)
    paid = alloc[alloc["allocation_kind"] == "sinv"].groupby("sinv_key")["c"].sum()
    opaid = alloc[alloc["allocation_kind"] == "open_ap"].groupby("opening_item_ref")["c"].sum()
    sg = np.where(si["invoice_type"] == "credit_note", -1, 1)
    inv = pd.DataFrame({"item_key": si["sinv_key"].to_numpy(), "source": "invoice", "le_key": si["le_key"].to_numpy(), "sup_key": si["sup_key"].to_numpy(), "sinv_key": si["sinv_key"].to_numpy(),
                        "document_date": si["invoice_date"].to_numpy(), "due_date": si["due_date"].to_numpy(), "invoice_c": _cents(si["payable_amount_le"]) * sg,
                        "paid_c": si["sinv_key"].map(paid).fillna(0).astype(np.int64).to_numpy()})
    ob = _opening(opening_balance_item, ap)
    opn = pd.DataFrame({"item_key": ob["item_ref"].to_numpy(), "source": "opening", "le_key": ob["le_key"].to_numpy(), "sup_key": ob["sup_key"].to_numpy(), "sinv_key": None,
                        "document_date": ob["document_date"].to_numpy(), "due_date": ob["due_date"].to_numpy(), "invoice_c": -_cents(ob["amount"]),
                        "paid_c": ob["item_ref"].map(opaid).fillna(0).astype(np.int64).to_numpy()})
    out = pd.concat([inv, opn], ignore_index=True)
    out["currency"] = out["le_key"].map(cur)
    out["open_c"] = out["invoice_c"] - out["paid_c"]
    for col, new in (("invoice_c", "payable_amount_le"), ("paid_c", "paid"), ("open_c", "open_amount")):
        out[new] = out[col] / 100
    cols = ["item_key", "source", "le_key", "sup_key", "sinv_key", "document_date", "due_date", "currency", "payable_amount_le", "paid", "open_amount"]
    return out[cols].sort_values(["le_key", "source", "item_key"]).reset_index(drop=True)


@staged(sources=("finance.customer_invoice.inv_key", "finance.customer_invoice.le_key", "finance.customer_invoice.cus_key", "finance.customer_invoice.retention_amount_le", "finance.customer_invoice.retention_release_date", "finance.opening_balance_item.due_date"),
        oracle="py:tests/test_finance.py::test_subledgers_reconcile_to_control_accounts_every_month_end")
def retention_receivable(open_items: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the retention held on receivables per item and in total per entity.

    Rule: the items are the rows of the open items of receivables whose retention_held is not zero; the total row of an entity and currency is the sum of retention_held over all its open items.
    The retention account of the ledger holds exactly the total. The release date is the release date of the invoice, or the due date of an opening item.

    Args:
        open_items: The frame returned by open_items_ar.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with item_key (empty on a total row), source (invoice, opening or total), le_key, cus_key, document_date, release_date, currency and retention_held (entity currency), items first and
        the total row of each entity last.
        Typed form: RetentionRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: the frame lacks a required column.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import open_items_ar, retention_receivable
        >>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
        >>> retention_receivable(items, context=ctx)[["source", "retention_held"]].values.tolist()
        [['invoice', 100.0], ['total', 100.0]]
    """
    _need(open_items, ["item_key", "le_key", "cus_key", "document_date", "release_date", "retention_held", "currency", "source"], "open_items_ar output")
    held = open_items[open_items["retention_held"] != 0]
    items = held[["item_key", "source", "le_key", "cus_key", "document_date", "release_date", "currency", "retention_held"]].reset_index(drop=True)
    tot = open_items.groupby(["le_key", "currency"], as_index=False)["retention_held"].sum().assign(item_key=None, source="total")
    out = pd.concat([items, tot], ignore_index=True)
    return out.sort_values(["le_key", "source", "item_key"], na_position="last").reset_index(drop=True)


def _receivable(open_items: pd.DataFrame) -> pd.Series:
    """The open amount net of the retention held (the receivable account), or the open amount when the frame has no retention column (payables)."""
    return open_items["open_amount"] - open_items["retention_held"] if "retention_held" in open_items.columns else open_items["open_amount"]


def _bucket_labels(bounds: Sequence[int]) -> list[str]:
    b = list(bounds)
    if not b or sorted(b) != b or len(set(b)) != len(b) or b[0] != 0 or any(x < 0 for x in b):
        raise FrameError("buckets are increasing days past due starting at 0, for example (0, 30, 60, 90)")
    return ["not_due", *[f"{lo + 1}-{hi}" for lo, hi in zip(b, b[1:])], f"over_{b[-1]}"]


@staged(sources=("finance.customer_invoice.due_date", "finance.customer_invoice.le_key", "finance.customer_invoice.cus_key", "finance.supplier_invoice.due_date", "finance.supplier_invoice.sup_key"), oracle="py:tests/test_finance.py::test_subledgers_reconcile_to_control_accounts_every_month_end")
def ageing(open_items: pd.DataFrame, as_of: dt.date, *, party: str = "cus_key", buckets: Sequence[int] = _BUCKETS) -> pd.DataFrame:
    """Use this when you need open items grouped by party and by days past due on a date.

    Rule: the amount of an item is open_amount less retention_held (retention is not aged: it falls due on its release date). days past due = as_of less due_date. The default buckets are not due (0
    days or less), 1 to 30, 31 to 60, 61 to 90 and over 90 days; items without a due date are their own bucket no_due_date, and the buckets add up to the total of the open items. Items with
    amount zero are left out. The bucket bounds are PROPOSED (the policy value is needed).

    Args:
        open_items: The frame returned by open_items_ar (party cus_key) or open_items_ap (party sup_key).
        as_of: The date the days past due are counted to (a date).
        party: Column of the party to group by: cus_key (default) or sup_key.
        buckets: Upper bounds in days of the buckets after the not due bucket (default 0, 30, 60, 90).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with le_key, the party column (cus_key or sup_key), bucket (text such as 31-60), n_items (count) and amount (entity currency), ordered by entity, party and bucket.
        Typed form: AgeingRow.from_frame(the frame) for customers and AgeingApRow.from_frame(the frame) for suppliers, one frozen model per row.

    Raises:
        FrameError: the frame lacks a required column or a due date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import ageing, open_items_ar
        >>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
        >>> ageing(items, dt.date(2025, 3, 31), context=ctx)[["cus_key", "bucket", "n_items", "amount"]].values.tolist()
        [['CUS-1', '31-60', 1, 900.0]]
    """
    _need(open_items, ["le_key", party, "due_date", "open_amount", "item_key"], "open items")
    d = _day(as_of)
    labels = _bucket_labels(buckets)
    x = _days(open_items[["le_key", party, "due_date", "item_key"]], ["due_date"], "open items").assign(open_amount=_receivable(open_items).round(2))
    x = x[x["open_amount"] != 0]
    late = (d - x["due_date"]).dt.days
    idx = np.searchsorted(np.asarray(list(buckets)), late.to_numpy(dtype=float, na_value=-1), side="left")        # 0 or less: not due
    bucket = np.where(x["due_date"].isna(), "no_due_date", np.array(labels, dtype=object)[np.clip(np.where(late.to_numpy(dtype=float, na_value=-1) <= 0, 0, idx), 0, len(labels) - 1)])
    x = x.assign(bucket=bucket)
    out = x.groupby(["le_key", party, "bucket"], as_index=False, dropna=False).agg(n_items=("item_key", "size"), amount=("open_amount", "sum"))
    out["amount"] = out["amount"].round(2)
    order = {b: i for i, b in enumerate([*labels, "no_due_date"])}
    return out.sort_values(["le_key", party, "bucket"], key=lambda s: s.map(order) if s.name == "bucket" else s).reset_index(drop=True)


@staged(sources=("finance.customer_invoice.due_date", "finance.customer_invoice.le_key"), facts=(_BAD_DEBT,), oracle="py:tests/test_finance.py::test_customer_invoices_and_payments_are_consistent")
def bad_debt_candidates(open_items: pd.DataFrame, as_of: dt.date) -> Envelope:
    """Use this when you need the receivables that are overdue by at least the write-off days of the fact.

    Rule: a receivable is a candidate when days past due = as_of less due_date is at least the fact fin.payment.bad_debt_write_off_after_days_overdue (status VERIFY) and the receivable net of
    retention (open_amount less retention_held) is above zero; retention is not collectable before its release date. The rows are ordered by entity, then longest overdue first.

    Args:
        open_items: The frame returned by open_items_ar.
        as_of: The date the days past due are counted to (a date).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is the frame of the overdue open items: item_key, source, le_key, cus_key, inv_key, document_date, due_date, currency, invoice_amount, paid, written_off, open_amount,
        retention_held, release_date as in open_items_ar, and two columns added, receivable_net (entity currency) and days_past_due (days). The envelope carries the VERIFY status of the fact.
        Typed form: BadDebtRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: the frame lacks a required column or a due date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import bad_debt_candidates, open_items_ar
        >>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2026, 6, 30), context=ctx)
        >>> r = bad_debt_candidates(items, dt.date(2026, 6, 30), context=ctx).value
        >>> r[["item_key", "receivable_net", "days_past_due"]].values.tolist() == [["I1", 900.0, (dt.date(2026, 6, 30) - dt.date(2025, 2, 10)).days]]
        True
    """
    _need(open_items, ["item_key", "le_key", "due_date", "open_amount"], "open items")
    d, f = _day(as_of), fact(_BAD_DEBT)
    x = _days(open_items, ["due_date"], "open items").assign(receivable_net=_receivable(open_items).round(2))
    late = (d - x["due_date"]).dt.days
    out = x.assign(days_past_due=late)[late >= int(f.value)]
    out = out[out["receivable_net"] > 0]
    return make_envelope(out.sort_values(["le_key", "days_past_due", "item_key"], ascending=[True, False, True]).reset_index(drop=True), "halvaro.finance.subledgers.bad_debt_candidates", facts=(f,),
                         sources=("finance.customer_invoice",))


@staged(sources=("finance.customer_invoice.cus_key", "finance.customer_invoice.le_key", "crm.customer.cus_key", "crm.customer.credit_limit", "crm.customer.currency"), facts=_FX_FACTS, oracle="py:repo_tests/test_oracle_subledgers_release.py::test_oracle_customer_exposure_baseline_invoices_per_customer_with_exact_decimals")
def customer_exposure(open_items: pd.DataFrame, customer: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the open receivables of each customer in DKK against the credit limit of the customer.

    Rule: open_dkk = the open amounts of the customer converted to DKK at the fixed booking rates (facts world.fx_eur_dkk_fixed and world.fx_sek_dkk_fixed); limit_dkk = the credit limit converted the
    same way; utilisation = open_dkk / limit_dkk; over_limit = open_dkk is above limit_dkk. A customer without a credit limit has no limit_dkk and is never over the limit; a customer without open
    items is listed with zero. Needs the crm source (stage month12).

    Args:
        open_items: The frame returned by open_items_ar, with cus_key, open_amount and currency.
        customer: Frame crm.customer with cus_key, credit_limit and currency, one row per customer.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with cus_key, credit_limit and limit_currency (the limit as stored), limit_dkk, open_dkk (DKK), utilisation (a share, empty without a limit) and over_limit (yes or no), one row per
        customer.
        Typed form: CustomerExposureRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a frame lacks a required column, crm.customer has a duplicate cus_key, or a customer with open items is not in crm.customer.
        StageRefusal: a source of the function is above the stage of the context (crm is stage month12).

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
        ...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> from halvaro.finance import customer_exposure, open_items_ar
        >>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
        >>> cust = pd.DataFrame({"cus_key": ["CUS-1"], "credit_limit": [500.0], "currency": ["DKK"]})
        >>> r = customer_exposure(items[items["source"] == "invoice"], cust, context=ctx)
        >>> r[["open_dkk", "limit_dkk", "over_limit"]].values.tolist() == [[1000.0, 500.0, True]]
        True
    """
    _need(open_items, ["le_key", "cus_key", "open_amount", "currency"], "open_items_ar output")
    _need(customer, ["cus_key", "credit_limit", "currency"], "crm.customer")
    if customer["cus_key"].duplicated().any():
        raise FrameError("crm.customer has duplicate cus_key values")
    x = open_items[open_items["cus_key"].notna()]
    missing = set(x["cus_key"]) - set(customer["cus_key"])
    if missing:
        raise FrameError(f"{len(missing)} customers with open items are not in crm.customer (for example {sorted(missing)[0]})")
    dkk = pd.Series(0, index=x.index, dtype=np.int64)
    for cur in x["currency"].unique():
        m = (x["currency"] == cur).to_numpy()
        dkk[m] = convert(pd.Series(_cents(x.loc[m, "open_amount"]), index=x.index[m]), str(cur), "DKK", basis="booking")
    open_dkk = (dkk / 100).groupby(x["cus_key"]).sum().round(2)
    c = customer.set_index("cus_key")
    lim = pd.Series(0, index=c.index, dtype=np.int64)
    for cur in c["currency"].unique():
        m = (c["currency"] == cur).to_numpy()
        lim[m] = convert(pd.Series(_cents(c.loc[m, "credit_limit"].fillna(0.0)), index=c.index[m]), str(cur), "DKK", basis="booking")
    out = pd.DataFrame({"cus_key": c.index, "credit_limit": c["credit_limit"].to_numpy(), "limit_currency": c["currency"].to_numpy(), "limit_dkk": (lim / 100).where(c["credit_limit"].notna()).to_numpy()})
    out["open_dkk"] = out["cus_key"].map(open_dkk).fillna(0.0)
    out["utilisation"] = np.where(out["limit_dkk"] > 0, out["open_dkk"] / out["limit_dkk"], np.nan)
    out["over_limit"] = (out["open_dkk"] > out["limit_dkk"]).fillna(False)                 # no limit set: not over it
    return out.sort_values("cus_key").reset_index(drop=True)
