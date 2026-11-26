"""Procurement exposure and control, the part that needs only finance and procurement tables: three-way match, price variance report, the finance definition of the price exposure, supplier spend and
approval limit breaches. The open quantity definition of the price exposure needs the halvaro-delivery frames and is not here.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, convert

from ._guard import staged
from ._util import _cents, _day, _days, _need

_STATUSES = ("matched", "price_variance", "quantity_variance")
_LIMITS = ((3, 50_000.0), (5, 250_000.0), (None, 1_000_000.0))     # PROPOSED: policy.approval.limits_per_role (needed): grade level up to, limit in DKK; above the last limit the CFO or CEO decides
_PO_KEY = ["po_key", "po_line_no", "receipt_no"]


@staged(sources=("finance.supplier_invoice_line.sinv_key", "finance.supplier_invoice_line.line_no", "finance.supplier_invoice_line.po_key", "finance.supplier_invoice_line.po_line_no",
                 "finance.supplier_invoice_line.receipt_no", "finance.supplier_invoice_line.quantity", "finance.supplier_invoice_line.unit_price", "finance.supplier_invoice_line.po_unit_price",
                 "finance.supplier_invoice_line.invoice_type", "finance.supplier_invoice_line.match_status", "finance.supplier_invoice_line.price_variance",
                 "procurement.goods_receipt.po_key", "procurement.goods_receipt.line_no", "procurement.goods_receipt.receipt_no", "procurement.goods_receipt.qty_accepted"),
        oracle="py:tests/tieout_c.py::t19_price_variance")
def three_way_match(supplier_invoice_line: pd.DataFrame, goods_receipt: pd.DataFrame, *, price_tolerance_percent: float = 0.0) -> pd.DataFrame:
    """Use this when you check each supplier invoice line against the purchase order price and the quantity accepted on the receipt.

    Rule (quantity first): a credit note is credit_for_rejected_goods; a line without a PO price is non_po; an invoiced quantity above the accepted quantity is quantity_variance; a price difference beyond the tolerance is price_variance; otherwise matched. price_variance is (invoice price less PO price) times quantity, to the cent. The stored status and variance are shown beside the recomputed ones.

    Args:
        supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, line_no, po_key, po_line_no, receipt_no, quantity, unit_price, po_unit_price, invoice_type, match_status and price_variance.
        goods_receipt: Frame procurement.goods_receipt with po_key, line_no, receipt_no and qty_accepted.
        price_tolerance_percent: Largest accepted price difference in percent, zero or more. Default 0 (PROPOSED; the plan recommends a policy value).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with sinv_key, line_no, po_key, status, price_variance, price_diff_percent, stored_status, stored_price_variance and agrees.

    Raises:
        FrameError: a column is missing, the tolerance is not a finite number of zero or more, a line or a receipt key is repeated, a PO line has a null price or quantity, or a PO line has no goods receipt.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import three_way_match
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"sinv_key": ["S1", "S2"], "line_no": [1, 1], "po_key": ["PO-1"] * 2, "po_line_no": [1, 2], "receipt_no": [1, 1], "quantity": [10, 10],
        ...                       "unit_price": [11.0, 10.0], "po_unit_price": [10.0, 10.0], "invoice_type": ["invoice"] * 2, "match_status": ["matched"] * 2, "price_variance": [10.0, 0.0]})
        >>> receipt = pd.DataFrame({"po_key": ["PO-1"] * 2, "line_no": [1, 2], "receipt_no": [1, 1], "qty_accepted": [10, 8]})
        >>> three_way_match(lines, receipt, context=ctx)[["sinv_key", "status", "price_variance"]].values.tolist()
        [['S1', 'price_variance', 10.0], ['S2', 'quantity_variance', 0.0]]
    """
    _need(supplier_invoice_line, ["sinv_key", "line_no", "po_key", "po_line_no", "receipt_no", "quantity", "unit_price", "po_unit_price", "invoice_type", "match_status", "price_variance"],
          "finance.supplier_invoice_line")
    _need(goods_receipt, ["po_key", "line_no", "receipt_no", "qty_accepted"], "procurement.goods_receipt")
    if not isinstance(price_tolerance_percent, (int, float, np.number)) or isinstance(price_tolerance_percent, bool) or not np.isfinite(price_tolerance_percent) or price_tolerance_percent < 0:
        raise FrameError(f"price_tolerance_percent must be a finite number, zero or more, not {price_tolerance_percent!r}")
    if supplier_invoice_line.duplicated(["sinv_key", "line_no"]).any():
        raise FrameError("finance.supplier_invoice_line has more than one row for the same sinv_key and line_no")
    if goods_receipt.duplicated(["po_key", "line_no", "receipt_no"]).any():
        raise FrameError("procurement.goods_receipt has duplicate (po_key, line_no, receipt_no) rows")
    sl = supplier_invoice_line.reset_index(drop=True)
    gr = goods_receipt[["po_key", "line_no", "receipt_no", "qty_accepted"]].rename(columns={"line_no": "po_line_no"}).astype({"po_line_no": "Int64"})
    m = sl.assign(po_line_no=sl["po_line_no"].astype("Int64")).merge(gr, on=_PO_KEY, how="left", validate="many_to_one")
    credit = (m["invoice_type"] == "credit_note").to_numpy()
    has_po = m["po_unit_price"].notna().to_numpy()
    for col in ("quantity", "unit_price"):
        if (has_po & m[col].isna().to_numpy()).any():
            raise FrameError(f"{int((has_po & m[col].isna().to_numpy()).sum())} PO invoice lines have a null {col}; a line cannot be matched without it")
    missing = has_po & ~credit & m["qty_accepted"].isna().to_numpy()
    if missing.any():
        raise FrameError(f"{int(missing.sum())} PO invoice lines have no goods receipt in procurement.goods_receipt (for example {m.loc[missing, 'sinv_key'].iloc[0]} line {m.loc[missing, 'line_no'].iloc[0]})")
    diff = (m["unit_price"] - m["po_unit_price"]).to_numpy(dtype=float)
    diff_pct = np.where(has_po & (m["po_unit_price"].to_numpy(dtype=float) != 0), diff / np.where(m["po_unit_price"].to_numpy(dtype=float) == 0, 1, m["po_unit_price"].to_numpy(dtype=float)) * 100, np.nan)
    over = has_po & (m["quantity"].to_numpy(dtype=float) > m["qty_accepted"].to_numpy(dtype=float) + 1e-9)
    off = has_po & (np.abs(diff) > 1e-9) & ~(np.abs(diff_pct) <= price_tolerance_percent + 1e-9)            # a PO price of 0 has no percentage: any difference is off
    status = np.where(credit, "credit_for_rejected_goods", np.where(~has_po, "non_po", np.where(over, "quantity_variance", np.where(off, "price_variance", "matched"))))
    variance = np.where(has_po & ~credit, np.round(np.nan_to_num(diff) * m["quantity"].to_numpy(dtype=float), 2), 0.0)
    out = pd.DataFrame({"sinv_key": m["sinv_key"], "line_no": m["line_no"], "po_key": m["po_key"], "status": status, "price_variance": variance, "price_diff_percent": diff_pct,
                        "stored_status": m["match_status"], "stored_price_variance": m["price_variance"]})
    out["agrees"] = (out["status"] == out["stored_status"]) & ((out["price_variance"] - out["stored_price_variance"]).abs() <= 0.005)
    return out


@staged(sources=("finance.supplier_invoice_line.sinv_key", "finance.supplier_invoice_line.itm_key", "finance.supplier_invoice_line.quantity", "finance.supplier_invoice_line.unit_price",
                 "finance.supplier_invoice_line.po_unit_price", "finance.supplier_invoice_line.price_variance", "finance.supplier_invoice_line.currency", "finance.supplier_invoice_line.invoice_type",
                 "finance.supplier_invoice.sinv_key", "finance.supplier_invoice.sup_key"), oracle="py:tests/test_exposure.py::test_price_variance_report_by_supplier_and_item_and_the_step")
def price_variance_report(supplier_invoice_line: pd.DataFrame, supplier_invoice: pd.DataFrame, *, price_steps: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need how far the invoiced prices of each supplier and item sit from the purchase order price.

    Rule: credit notes and lines without a PO price are left out. The difference of a line is (invoice price less PO price) over the PO price, in percent. Per supplier, item and currency the report gives the number of lines, the summed price variance (contract currency, to the cent) and the mean, standard deviation and largest absolute difference in percent. With a price_steps frame the step is added and step_in_variance says whether the mean difference reaches half of the step (the step sits in the PO price, so it is not in the invoice variance).

    Args:
        supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, itm_key, unit_price, po_unit_price, price_variance, currency and invoice_type.
        supplier_invoice: Frame finance.supplier_invoice with sinv_key and sup_key, one row per invoice.
        price_steps: The result of price_steps, or a frame with sup_key, itm_key and step_percent, one row per supplier and item. Optional.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with sup_key, itm_key, currency, n_lines, price_variance, mean_diff_percent, sd_diff_percent and max_abs_diff_percent (and step_percent and step_in_variance with price_steps), sorted by supplier, item and currency.

    Raises:
        FrameError: a column is missing, supplier_invoice repeats an invoice key, an invoice line belongs to an invoice that is not in supplier_invoice, a PO price is 0, a line with a PO price has no item or currency, or price_steps repeats a supplier and item.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import price_variance_report
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"sinv_key": ["INV-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "po_unit_price": [10.0], "price_variance": [10.0], "currency": ["EUR"], "invoice_type": ["invoice"]})
        >>> invoices = pd.DataFrame({"sinv_key": ["INV-1"], "sup_key": ["SUP-1"]})
        >>> price_variance_report(lines, invoices, context=ctx)[["sup_key", "itm_key", "n_lines", "price_variance", "mean_diff_percent"]].values.tolist()
        [['SUP-1', 'ITM-1', 1, 10.0, 10.0]]
    """
    _need(supplier_invoice_line, ["sinv_key", "itm_key", "unit_price", "po_unit_price", "price_variance", "currency", "invoice_type"], "finance.supplier_invoice_line")
    _need(supplier_invoice, ["sinv_key", "sup_key"], "finance.supplier_invoice")
    if supplier_invoice["sinv_key"].duplicated().any():
        raise FrameError("finance.supplier_invoice has duplicate sinv_key values")
    x = supplier_invoice_line[supplier_invoice_line["po_unit_price"].notna() & (supplier_invoice_line["invoice_type"] != "credit_note")]
    x = x.merge(supplier_invoice[["sinv_key", "sup_key"]], on="sinv_key", how="left", validate="many_to_one")
    if x["sup_key"].isna().any():
        raise FrameError(f"{int(x['sup_key'].isna().sum())} invoice lines belong to an invoice that is not in finance.supplier_invoice")
    if (x["po_unit_price"] == 0).any():
        raise FrameError(f"{int((x['po_unit_price'] == 0).sum())} invoice lines have a PO price of 0; the relative difference is undefined")
    if x[["itm_key", "currency"]].isna().any().any():
        raise FrameError("invoice lines with a PO price need an itm_key and a currency")
    x = x.assign(pct=(x["unit_price"] - x["po_unit_price"]) / x["po_unit_price"] * 100)
    g = x.groupby(["sup_key", "itm_key", "currency"], as_index=False).agg(n_lines=("pct", "size"), price_variance=("price_variance", "sum"), mean_diff_percent=("pct", "mean"),
                                                                         sd_diff_percent=("pct", "std"), max_abs_diff_percent=("pct", lambda s: s.abs().max()))
    g["price_variance"] = g["price_variance"].round(2)
    if price_steps is not None:
        _need(price_steps, ["sup_key", "itm_key", "step_percent"], "price_steps")
        if price_steps.duplicated(["sup_key", "itm_key"]).any():
            raise FrameError("price_steps has more than one row for a sup_key and itm_key")
        g = g.merge(price_steps[["sup_key", "itm_key", "step_percent"]], on=["sup_key", "itm_key"], how="left", validate="many_to_one")
        g["step_in_variance"] = g["step_percent"].notna() & (g["mean_diff_percent"].abs() >= g["step_percent"].abs() / 2)
    return g.sort_values(["sup_key", "itm_key", "currency"]).reset_index(drop=True)


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.currency", "finance.project_financials.price_exposure",
                 "finance.project_financials.price_recoverable"))
def finance_exposure(project_financials: pd.DataFrame, period: str) -> pd.DataFrame:
    """Use this when you need the price exposure of the projects at a period as the finance data defines it: the cumulative exposure and the part that can be recovered.

    Rule: the rows of the period with a price exposure or a recoverable amount different from zero are taken from finance.project_financials and converted to DKK at the booking rates. The open quantity definition of the exposure is a different figure.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period, currency, price_exposure and price_recoverable, one row per project and period.
        period: The period, text like 2026-03.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, period, currency, price_exposure, price_recoverable, price_exposure_dkk and price_recoverable_dkk; empty when no project has a non-zero row in the period.

    Raises:
        FrameError: a column is missing or a project has more than one row in the period.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import finance_exposure
        >>> ctx = Context(stage="month12", role="analyst")
        >>> projects = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["EUR"], "price_exposure": [100.0], "price_recoverable": [40.0]})
        >>> finance_exposure(projects, "2026-03", context=ctx)[["prj_key", "price_exposure", "price_recoverable"]].values.tolist()
        [['PRJ-1', 100.0, 40.0]]
        >>> finance_exposure(projects, "2026-04", context=ctx).empty
        True
    """
    _need(project_financials, ["prj_key", "period", "currency", "price_exposure", "price_recoverable"], "finance.project_financials")
    x = project_financials[(project_financials["period"] == period) & ((project_financials["price_exposure"] != 0) | (project_financials["price_recoverable"] != 0))]
    if x["prj_key"].duplicated().any():
        raise FrameError(f"finance.project_financials has more than one row for a project in {period}")
    out = x[["prj_key", "period", "currency", "price_exposure", "price_recoverable"]].copy()
    for col in ("price_exposure", "price_recoverable"):
        dkk = np.zeros(len(out), dtype=np.int64)
        for cur in out["currency"].unique():
            m = (out["currency"] == cur).to_numpy()
            dkk[m] = convert(pd.Series(_cents(out.loc[m, col])), str(cur), "DKK", basis="booking").to_numpy()
        out[f"{col}_dkk"] = dkk / 100.0
    return out.sort_values("prj_key").reset_index(drop=True)


@staged(sources=("finance.supplier_invoice.sup_key", "finance.supplier_invoice.invoice_type", "finance.supplier_invoice.invoice_date", "finance.supplier_invoice.net_amount_dkk",
                 "procurement.supplier.sup_key", "procurement.supplier.category"), oracle="py:tests/test_exposure.py::test_supplier_spend_window_credit_notes_and_missing_suppliers")
def supplier_spend(supplier_invoice: pd.DataFrame, supplier: pd.DataFrame, start: dt.date | str, end: dt.date | str) -> pd.DataFrame:
    """Use this when you need what was spent per supplier and category in DKK over a range of invoice dates.

    Rule: invoices dated from start to end, both days included; credit notes count negative.

    Args:
        supplier_invoice: Frame finance.supplier_invoice with sup_key, invoice_type, invoice_date and net_amount_dkk.
        supplier: Frame procurement.supplier with sup_key and category, one row per supplier.
        start: First day.
        end: Last day.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with sup_key, category, n_invoices and spend_dkk, sorted by supplier.

    Raises:
        FrameError: a column is missing, a supplier or an invoice key is duplicated, start is after end, or an invoice is from a supplier that is not in the supplier frame.
        PeriodError: start or end is a number, not a date, an unreadable text or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import supplier_spend
        >>> ctx = Context(stage="month12", role="analyst")
        >>> import datetime as dt
        >>> invoices = pd.DataFrame({"sup_key": ["SUP-1"] * 2, "invoice_type": ["invoice", "credit_note"], "invoice_date": ["2026-01-05", "2026-01-20"], "net_amount_dkk": [100.0, 30.0]})
        >>> suppliers = pd.DataFrame({"sup_key": ["SUP-1"], "category": ["steel"]})
        >>> supplier_spend(invoices, suppliers, dt.date(2026, 1, 1), dt.date(2026, 1, 31), context=ctx).values.tolist()
        [['SUP-1', 'steel', 2, 70.0]]
    """
    _need(supplier_invoice, ["sup_key", "invoice_type", "invoice_date", "net_amount_dkk"], "finance.supplier_invoice")
    _need(supplier, ["sup_key", "category"], "procurement.supplier")
    if supplier["sup_key"].duplicated().any():
        raise FrameError("procurement.supplier has duplicate sup_key values")
    s, e = _day(start, "start"), _day(end, "end")
    if "sinv_key" in supplier_invoice.columns and supplier_invoice["sinv_key"].duplicated().any():
        raise FrameError("finance.supplier_invoice has duplicate sinv_key values")
    if s > e:
        raise FrameError(f"start {s.date()} is after end {e.date()}")
    si = _days(supplier_invoice, ["invoice_date"], "finance.supplier_invoice")
    si = si[(si["invoice_date"] >= s) & (si["invoice_date"] <= e)]
    missing = set(si["sup_key"]) - set(supplier["sup_key"])
    if missing:
        raise FrameError(f"{len(missing)} suppliers with invoices are not in procurement.supplier (for example {sorted(missing)[0]})")
    cents = _cents(si["net_amount_dkk"]) * np.where(si["invoice_type"] == "credit_note", -1, 1)
    g = pd.DataFrame({"sup_key": si["sup_key"].to_numpy(), "c": cents}).groupby("sup_key").agg(n_invoices=("c", "size"), c=("c", "sum")).reset_index()
    g["spend_dkk"] = g["c"] / 100.0
    return g.merge(supplier[["sup_key", "category"]], on="sup_key", how="left")[["sup_key", "category", "n_invoices", "spend_dkk"]].sort_values("sup_key").reset_index(drop=True)


@staged(sources=("procurement.purchase_order.po_key", "procurement.purchase_order.total_value", "procurement.purchase_order.currency", "procurement.purchase_order.buyer_emp_key",
                 "procurement.purchase_order.order_date"), oracle="py:tests/test_exposure.py::test_approval_limit_breaches_by_grade_and_currency")
def approval_limit_breaches(purchase_order: pd.DataFrame, buyer_grade: pd.DataFrame, *, limits: Sequence[tuple[Any, Any]] = _LIMITS) -> pd.DataFrame:
    """Use this when you check that the buyers of purchase orders had the authority for the value, by the grade of the buyer on the order date.

    Rule: the limit depends on the grade level (PROPOSED: up to level 3 DKK 50,000, up to level 5 DKK 250,000, above DKK 1,000,000; the policy value is needed). An order above the limit of its buyer is a breach. The data has no approver, so only the buyer's authority is tested.

    Args:
        purchase_order: Frame procurement.purchase_order with po_key, total_value, currency, buyer_emp_key and order_date.
        buyer_grade: Frame with po_key and grade_level (the level of the buyer at the order date, from halvaro-hr).
        limits: A list of (grade level up to, limit in DKK) with increasing levels and None for the last step. Default PROPOSED as above.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with po_key, buyer_emp_key, order_date, grade_level, total_value_dkk, limit_dkk and breach.

    Raises:
        FrameError: a column is missing, po_key is not unique, limits is not a list of increasing steps ending in None, or an order has no buyer grade.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import approval_limit_breaches
        >>> ctx = Context(stage="month12", role="analyst")
        >>> orders = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "total_value": [60000.0, 1000.0], "currency": ["DKK"] * 2, "buyer_emp_key": ["EMP-000001"] * 2, "order_date": ["2026-01-05"] * 2})
        >>> grades = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "grade_level": [3, 3]})
        >>> approval_limit_breaches(orders, grades, context=ctx)[["po_key", "breach"]].values.tolist()
        [['PO-1', True], ['PO-2', False]]
    """
    _need(purchase_order, ["po_key", "total_value", "currency", "buyer_emp_key", "order_date"], "procurement.purchase_order")
    _need(buyer_grade, ["po_key", "grade_level"], "buyer_grade")
    if buyer_grade["po_key"].duplicated().any() or purchase_order["po_key"].duplicated().any():
        raise FrameError("po_key must be unique in the purchase orders and in buyer_grade")
    steps = list(limits)
    if not steps or steps[-1][0] is not None or any(a[0] is None for a in steps[:-1]) or [a[0] for a in steps[:-1]] != sorted(a[0] for a in steps[:-1]):
        raise FrameError("limits is a list of (grade level up to, limit) with increasing levels and None for the last step")
    po = purchase_order[["po_key", "buyer_emp_key", "order_date", "total_value", "currency"]].merge(buyer_grade[["po_key", "grade_level"]], on="po_key", how="left", validate="one_to_one")
    if po["grade_level"].isna().any():
        raise FrameError(f"{int(po['grade_level'].isna().sum())} purchase orders have no buyer grade (for example {po.loc[po['grade_level'].isna(), 'po_key'].iloc[0]})")
    dkk = np.zeros(len(po), dtype=np.int64)
    for cur in po["currency"].unique():
        m = (po["currency"] == cur).to_numpy()
        dkk[m] = convert(pd.Series(_cents(po.loc[m, "total_value"])), str(cur), "DKK", basis="booking").to_numpy()
    lvl = po["grade_level"].to_numpy(dtype=float)
    limit = np.full(len(po), steps[-1][1], dtype=float)
    for upto, lim in reversed(steps[:-1]):
        limit = np.where(lvl <= upto, lim, limit)
    out = po.assign(total_value_dkk=dkk / 100.0, limit_dkk=limit)
    out["breach"] = out["total_value_dkk"] > out["limit_dkk"]
    return out[["po_key", "buyer_emp_key", "order_date", "grade_level", "total_value_dkk", "limit_dkk", "breach"]].sort_values("po_key").reset_index(drop=True)
