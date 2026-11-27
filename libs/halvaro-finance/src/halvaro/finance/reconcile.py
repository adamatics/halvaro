"""Month end rebuild of the subledgers against the control accounts, and the registers next to the ledger (fixed assets, inventory, bank, intercompany).

The function ids are those of the plan (halvaro.finance.subledgers.*). Amounts are integer cents of the entity currency in the computation.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, convert, fact, make_envelope, violations

from ._guard import staged
from ._util import _cents, _control, _days, _entity_currency, _need, _opening

_ALLOWANCE_RATE = "fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate"
_METHODS = ("fin.fixed_assets.DK.method", "fin.fixed_assets.DE.method")
_FX_FACTS = ("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed")
_DEPRECIATION_START = "fin.finance_planning_and_registers.fixed_asset_register.depreciation_start"
_TOLERANCE_CENT = 0.005
_ALLOC = ["le_key", "bank_account", "payment_no"]
_PLAN_MODULE = "halvaro.finance.subledgers"


# ---- month end rebuild of the subledgers against the control accounts

_IC_ACCOUNTS = {"intercompany_trade": (("management_fee", "it_recharge"), "GL-2300", "GL-4800"), "intercompany_interest": (("loan_interest",), "GL-2320", "GL-4820"),
                "intercompany_dividend": (("dividend",), "GL-2310", "GL-4810"), "intercompany_loan": (("loan_principal",), "GL-1510", "GL-4120")}      # PROPOSED: the plan names no account map


def _events(le: Any, dates: Any, cents: Any) -> pd.DataFrame:
    """Dated amounts in cents; a missing date stays missing (ignored later), an unreadable one raises FrameError."""
    p = _days(pd.DataFrame({"d": pd.Series(dates).to_numpy()}), ["d"], "event dates")["d"].dt.strftime("%Y-%m")
    return pd.DataFrame({"le": np.asarray(le, dtype=object), "p": p.to_numpy(dtype=object), "c": np.asarray(cents, dtype=np.int64)})


def _unique(frame: pd.DataFrame, keys: Sequence[str], what: str) -> None:
    if frame.duplicated(list(keys)).any():
        raise FrameError(f"{what} has more than one row for the same {', '.join(keys)}")


def _opening_events(le: Any, cents: Any) -> pd.DataFrame:
    return pd.DataFrame({"le": np.asarray(le, dtype=object), "p": "", "c": np.asarray(cents, dtype=np.int64)})


def _balances(events: Sequence[pd.DataFrame], periods: Sequence[str], les: Sequence[str]) -> dict[Any, Any]:
    """Month end balances in cents per entity: the events before the first period are the opening balance, an event in a month that is not a period counts from the next period at or after it,
    events without a date or after the last period are ignored."""
    ev = pd.concat(events, ignore_index=True) if events else pd.DataFrame({"le": [], "p": [], "c": []})
    ev = ev[ev["p"].notna()]
    first, pr = periods[0], np.asarray(periods, dtype=object)
    out = {}
    for le in les:
        e = ev[ev["le"] == le]
        base = int(e.loc[e["p"] < first, "c"].sum())
        inside = e[e["p"] >= first]
        idx = np.searchsorted(pr, inside["p"].to_numpy(dtype=object), side="left")
        keep = idx < len(pr)
        within = np.zeros(len(pr), dtype=np.int64)
        np.add.at(within, idx[keep], inside["c"].to_numpy(dtype=np.int64)[keep])
        out[le] = base + within.cumsum()
    return out


def _allocations(payment_allocation: pd.DataFrame, payment: pd.DataFrame) -> pd.DataFrame:
    """Payment allocations with the date of their payment and a signed amount in cents (a credit note allocation is negative); an allocation whose payment is missing raises."""
    _need(payment_allocation, [*_ALLOC, "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"], "finance.payment_allocation")
    _need(payment, [*_ALLOC, "payment_date"], "finance.payment")
    a = payment_allocation.merge(_days(payment[[*_ALLOC, "payment_date"]], ["payment_date"], "finance.payment"), on=_ALLOC, how="left", validate="many_to_one")
    if a["payment_date"].isna().any():
        raise FrameError(f"{int(a['payment_date'].isna().sum())} allocations name a payment that is not in finance.payment")
    a["c"] = _cents(a["booked_amount"]) * np.where(a["document_type"] == "credit_note", -1, 1)
    return a


@staged(id=f"{_PLAN_MODULE}.rebuild_subledger_reconciliation", sources=("finance.customer_invoice.inv_key", "finance.customer_invoice.le_key", "finance.customer_invoice.invoice_type", "finance.customer_invoice.invoice_date", "finance.customer_invoice.gross_amount_le", "finance.customer_invoice.retention_amount_le", "finance.customer_invoice.retention_release_date", "finance.customer_invoice.written_off_date", "finance.customer_invoice.counterpart_le_key", "finance.supplier_invoice.le_key", "finance.supplier_invoice.invoice_type", "finance.supplier_invoice.invoice_date", "finance.supplier_invoice.payable_amount_le", "finance.payment.le_key", "finance.payment.bank_account", "finance.payment.payment_no", "finance.payment.payment_date", "finance.payment_allocation.le_key", "finance.payment_allocation.bank_account", "finance.payment_allocation.payment_no", "finance.payment_allocation.allocation_kind", "finance.payment_allocation.document_type", "finance.payment_allocation.booked_amount", "finance.payment_allocation.inv_key", "finance.payment_allocation.sinv_key", "finance.payment_allocation.opening_item_ref", "finance.opening_balance_item.le_key", "finance.opening_balance_item.gl_key", "finance.opening_balance_item.item_ref", "finance.opening_balance_item.document_date", "finance.opening_balance_item.due_date", "finance.opening_balance_item.amount", "finance.opening_balance_item.currency", "finance.opening_balance_item.cus_key", "finance.opening_balance_item.sup_key", "finance.fixed_asset.asset_class", "finance.fixed_asset.gl_cost_key", "finance.fixed_asset.gl_accumulated_key", "finance.fixed_asset_schedule.le_key", "finance.fixed_asset_schedule.asset_class", "finance.fixed_asset_schedule.period", "finance.fixed_asset_schedule.cost_closing", "finance.fixed_asset_schedule.accumulated_closing", "finance.inventory_valuation.le_key", "finance.inventory_valuation.period", "finance.inventory_valuation.gl_key", "finance.inventory_valuation.stock_value", "finance.inventory_valuation.allowance", "finance.intercompany.ic_type", "finance.intercompany.creditor_le_key", "finance.intercompany.debtor_le_key", "finance.intercompany.document_date", "finance.intercompany.settlement_date", "finance.intercompany.creditor_amount", "finance.intercompany.debtor_amount", "finance.bank_balance.bank_account", "finance.bank_balance.balance_date", "finance.bank_balance.closing_balance", "finance.bank_account.le_key", "finance.bank_account.bank_account", "finance.bank_account.gl_key", "finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.closing_balance", "finance.gl_account.gl_key", "finance.gl_account.control_type"),
        oracle="py:tests/test_finance.py::test_subledgers_reconcile_to_control_accounts_every_month_end")
def rebuild_subledger_reconciliation(customer_invoice: pd.DataFrame, supplier_invoice: pd.DataFrame, payment: pd.DataFrame, payment_allocation: pd.DataFrame, opening_balance_item: pd.DataFrame,
                                     fixed_asset: pd.DataFrame, fixed_asset_schedule: pd.DataFrame, inventory_valuation: pd.DataFrame, intercompany: pd.DataFrame, bank_balance: pd.DataFrame,
                                     bank_account: pd.DataFrame, trial_balance: pd.DataFrame, gl_account: pd.DataFrame, *, allowance_gl: str = "GL-2015",
                                     intercompany_accounts: Mapping[Any, Any] = _IC_ACCOUNTS) -> pd.DataFrame:
    """Use this when you need every subledger compared with its control account in the ledger at each month end.

    Rule: for each entity and month end the balance of a subledger is rebuilt from the published tables and compared with the closing balance of its control account in the trial balance:
    receivables and retention receivable (customer invoices and credit notes, payments allocated, write offs, opening items), payables, fixed assets cost and accumulated depreciation per
    asset class, inventory and its allowance, intercompany trade, and every bank account (last daily balance of the month). reconciled = the difference is zero to the cent. An event in a
    month that is not a period counts from the next period; events before the first period are the opening balance and events after the last period are ignored. The ledger account of the
    allowance and the intercompany accounts are PROPOSED keywords.

    Args:
        customer_invoice: Frame finance.customer_invoice (invoices and credit notes, retention, write off date, counterpart entity).
        supplier_invoice: Frame finance.supplier_invoice with le_key, invoice_type, invoice_date and payable_amount_le.
        payment: Frame finance.payment with the allocation key columns and payment_date.
        payment_allocation: Frame finance.payment_allocation, the allocation of payments to documents.
        opening_balance_item: Frame finance.opening_balance_item, open items at the start of the window.
        fixed_asset: Frame finance.fixed_asset with asset_class and its cost and accumulated depreciation accounts.
        fixed_asset_schedule: Frame finance.fixed_asset_schedule with cost_closing and accumulated_closing per entity, asset class and period.
        inventory_valuation: Frame finance.inventory_valuation with stock_value and allowance per entity, period and account.
        intercompany: Frame finance.intercompany with creditor and debtor entity, amounts and dates.
        bank_balance: Frame finance.bank_balance, one row per bank account and date.
        bank_account: Frame finance.bank_account with le_key, bank_account and gl_key, one row per account.
        trial_balance: Frame finance.trial_balance with closing_balance per entity, account and period, one row each.
        gl_account: Frame finance.gl_account with control_type per account.
        allowance_gl: Ledger account of the inventory allowance (default GL-2015, PROPOSED).
        intercompany_accounts: Map of the intercompany control accounts (default the proposed map).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with le_key, period, subledger, detail, gl_key, subledger_balance, ledger_balance, difference (currency units), currency and reconciled (yes or no), in the shape of
        finance.subledger_reconciliation.
        Typed form: SubledgerReconciliationRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a frame lacks a required column, the trial balance, the asset schedule, the bank accounts or the bank balances have duplicate keys, a date cannot be read, or the trial
            balance has no rows.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import rebuild_subledger_reconciliation
        >>> ctx = Context(stage="month3", role="analyst")
        >>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
        >>> tb = pd.DataFrame({"le_key": "LE-01", "period": ["2023-01"] * 3, "gl_key": ["GL-1100", "GL-1190", "GL-2100"], "closing_balance": [900.0, 100.0, 0.0]})
        >>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "invoice_type": "invoice", "invoice_date": ["2023-01-15"], "gross_amount_le": 1000.0, "retention_amount_le": 100.0,
        ...                    "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
        >>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2022-12-01"], "due_date": [None], "amount": [0.0],
        ...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
        >>> empty = lambda *cols: pd.DataFrame(columns=list(cols))
        >>> r = rebuild_subledger_reconciliation(
        ...     ci, empty("le_key", "invoice_type", "invoice_date", "payable_amount_le"), empty("le_key", "bank_account", "payment_no", "payment_date"), alloc, ob,
        ...     empty("asset_class", "gl_cost_key", "gl_accumulated_key"), empty("le_key", "asset_class", "period", "cost_closing", "accumulated_closing"),
        ...     empty("le_key", "period", "gl_key", "stock_value", "allowance"),
        ...     empty("ic_type", "creditor_le_key", "debtor_le_key", "document_date", "settlement_date", "creditor_amount", "debtor_amount"),
        ...     empty("bank_account", "balance_date", "closing_balance"), empty("le_key", "bank_account", "gl_key"), tb, gl, context=ctx)
        >>> rec = r[r["subledger"] == "receivables"]
        >>> rec[["subledger_balance", "ledger_balance", "reconciled"]].iloc[0].tolist() == [900.0, 900.0, True]
        True
    """
    for f, cols, what in ((customer_invoice, ["inv_key", "le_key", "invoice_type", "invoice_date", "gross_amount_le", "retention_amount_le", "retention_release_date", "written_off_date",
                                              "counterpart_le_key"], "finance.customer_invoice"),
                          (supplier_invoice, ["le_key", "invoice_type", "invoice_date", "payable_amount_le"], "finance.supplier_invoice"),
                          (fixed_asset, ["asset_class", "gl_cost_key", "gl_accumulated_key"], "finance.fixed_asset"),
                          (fixed_asset_schedule, ["le_key", "asset_class", "period", "cost_closing", "accumulated_closing"], "finance.fixed_asset_schedule"),
                          (inventory_valuation, ["le_key", "period", "gl_key", "stock_value", "allowance"], "finance.inventory_valuation"),
                          (intercompany, ["ic_type", "creditor_le_key", "debtor_le_key", "document_date", "settlement_date", "creditor_amount", "debtor_amount"], "finance.intercompany"),
                          (bank_balance, ["bank_account", "balance_date", "closing_balance"], "finance.bank_balance"), (bank_account, ["le_key", "bank_account", "gl_key"], "finance.bank_account"),
                          (trial_balance, ["le_key", "period", "gl_key", "closing_balance"], "finance.trial_balance")):
        _need(f, cols, what)
    _unique(trial_balance, ["le_key", "gl_key", "period"], "finance.trial_balance")
    _unique(fixed_asset_schedule, ["le_key", "asset_class", "period"], "finance.fixed_asset_schedule")
    _unique(bank_account, ["bank_account"], "finance.bank_account")
    _unique(bank_balance, ["bank_account", "balance_date"], "finance.bank_balance")
    periods = sorted(trial_balance["period"].unique())
    if not periods:
        raise FrameError("finance.trial_balance has no rows")
    les = sorted(trial_balance["le_key"].unique())
    ar, ret, ap = _control(gl_account, "ar"), _control(gl_account, "retention"), _control(gl_account, "ap")
    cur = _entity_currency(opening_balance_item)
    ob = _opening(opening_balance_item, [*ar, *ret, *ap])
    ob_c = _cents(ob["amount"])
    a = _allocations(payment_allocation, payment)
    ci = _days(customer_invoice[customer_invoice["counterpart_le_key"].isna()], ["invoice_date", "retention_release_date", "written_off_date"], "finance.customer_invoice")
    sg = np.where(ci["invoice_type"] == "credit_note", -1, 1)
    # receivables including retention, then the retention part
    incl = [_events(ci["le_key"], ci["invoice_date"], _cents(ci["gross_amount_le"]) * sg),
            _opening_events(ob.loc[ob["gl_key"].isin([*ar, *ret]), "le_key"], ob_c[ob["gl_key"].isin([*ar, *ret]).to_numpy()])]
    s = a[a["allocation_kind"].isin(["inv", "inv_ret", "open_ar", "open_ret"])]
    incl.append(_events(s["le_key"], s["payment_date"], -s["c"]))
    wo = ci[ci["written_off_date"].notna()]
    incl.append(_events(wo["le_key"], wo["written_off_date"], -_cents(wo["gross_amount_le"])))
    held = ci[ci["retention_amount_le"] > 0]
    sgh = np.where(held["invoice_type"] == "credit_note", -1, 1)
    collected = set(a.loc[a["allocation_kind"] == "inv_ret", "inv_key"])
    rel = held[held["inv_key"].isin(collected)]
    sgr = np.where(rel["invoice_type"] == "credit_note", -1, 1)
    rt = ob[ob["gl_key"].isin(ret)]
    rt_c = _cents(rt["amount"])
    retention = [_events(held["le_key"], held["invoice_date"], _cents(held["retention_amount_le"]) * sgh), _events(rel["le_key"], rel["retention_release_date"], -_cents(rel["retention_amount_le"]) * sgr),
                 _opening_events(rt["le_key"], rt_c), _events(rt.loc[rt["due_date"].notna(), "le_key"], rt.loc[rt["due_date"].notna(), "due_date"], -rt_c[rt["due_date"].notna().to_numpy()])]
    receivables = incl + [e.assign(c=-e["c"]) for e in retention]
    si = _days(supplier_invoice, ["invoice_date"], "finance.supplier_invoice")
    sgs = np.where(si["invoice_type"] == "credit_note", -1, 1)
    apo = ob[ob["gl_key"].isin(ap)]
    sp = a[a["allocation_kind"].isin(["sinv", "open_ap"])]
    payables = [_events(si["le_key"], si["invoice_date"], -_cents(si["payable_amount_le"]) * sgs), _opening_events(apo["le_key"], _cents(apo["amount"])), _events(sp["le_key"], sp["payment_date"], sp["c"])]
    subs = {("receivables", ""): (ar, _balances(receivables, periods, les)), ("retention_receivable", ""): (ret, _balances(retention, periods, les)), ("trade_payables", ""): (ap, _balances(payables, periods, les))}
    # fixed assets by class from the schedule
    accounts = fixed_asset.drop_duplicates("asset_class").set_index("asset_class")
    fs = fixed_asset_schedule
    missing = sorted(set(fs["asset_class"]) - set(accounts.index))
    if missing:
        raise FrameError(f"asset class {missing[0]} of the schedule is not in finance.fixed_asset")
    for cls in sorted(set(fs["asset_class"]) | set(accounts.index)):
        for kind, col, gl, sgn in (("fixed_assets_cost", "cost_closing", accounts.loc[cls, "gl_cost_key"], 1), ("fixed_assets_accumulated_depreciation", "accumulated_closing", accounts.loc[cls, "gl_accumulated_key"], -1)):
            x = fs[fs["asset_class"] == cls]
            subs[(kind, cls)] = ([gl], {le: x[x["le_key"] == le].set_index("period")[col].reindex(periods, fill_value=0).pipe(lambda v: _cents(v) * sgn) for le in les})
    # inventory
    iv = inventory_valuation
    stock_gl = sorted(iv["gl_key"].unique())
    for kind, col, gl, sgn in (("inventory_stock", "stock_value", stock_gl, 1), ("inventory_allowance", "allowance", [allowance_gl], -1)):
        subs[(kind, "")] = (gl, {le: iv[iv["le_key"] == le].groupby("period")[col].sum().reindex(periods, fill_value=0.0).pipe(lambda v: _cents(v) * sgn) for le in les})
    # intercompany from the document register
    for kind, (types, gl_c, gl_d) in intercompany_accounts.items():
        x = intercompany[intercompany["ic_type"].isin(types)]
        for side, le_col, gl, col, sgn in (("creditor", "creditor_le_key", gl_c, "creditor_amount", 1), ("debtor", "debtor_le_key", gl_d, "debtor_amount", -1)):
            c = _cents(x[col]) * sgn
            subs[(kind, side)] = ([gl], _balances([_events(x[le_col], x["document_date"], c), _events(x[le_col], x["settlement_date"], -c)], periods, les))
    # bank from the last daily balance of each month
    bb = _days(bank_balance, ["balance_date"], "finance.bank_balance")
    bb["p"] = bb["balance_date"].dt.strftime("%Y-%m")
    last = bb[bb["p"].isin(periods)].sort_values("balance_date").groupby(["bank_account", "p"]).tail(1)
    for r in bank_account.to_dict("records"):
        x = last[last["bank_account"] == r['bank_account']].set_index("p")["closing_balance"]
        subs[("bank", r['bank_account'])] = ([r['gl_key']], {le: (_cents(x.reindex(periods, fill_value=0.0)) if le == r['le_key'] else np.zeros(len(periods), dtype=np.int64)) for le in les})
    tb = trial_balance.assign(c=_cents(trial_balance["closing_balance"]))
    ledger = {gl: {le: g.set_index("period")["c"].reindex(periods, fill_value=0).to_numpy() for le, g in x.groupby("le_key")} for gl, x in tb.groupby("gl_key")}
    owner = bank_account.set_index("bank_account")["le_key"].to_dict()
    rows = []
    for (kind, detail), (gls, sub) in subs.items():
        for le in les:
            led = sum((ledger.get(g, {}).get(le, np.zeros(len(periods), dtype=np.int64)) for g in gls), np.zeros(len(periods), dtype=np.int64))
            s = sub[le]
            if not s.any() and not led.any():
                continue
            if kind == "bank" and le != owner[detail]:
                continue                                            # an account is reconciled in the entity that owns it; the ledger of another entity on the same account is its own
            rows.append(pd.DataFrame({"le_key": le, "period": periods, "subledger": kind, "detail": detail, "gl_key": ",".join(gls), "subledger_balance": s / 100.0, "ledger_balance": led / 100.0,
                                      "difference": (s - led) / 100.0, "currency": cur.get(le), "reconciled": s == led}))
    return pd.concat(rows, ignore_index=True).sort_values(["le_key", "subledger", "detail", "period"]).reset_index(drop=True)


# ---- registers next to the ledger

def _cum_dep(cost: np.ndarray, months: np.ndarray, life: np.ndarray) -> np.ndarray:
    """Accumulated straight line depreciation in cents after `months` depreciated months, rounded half to even, exact at the end of the life."""
    m = np.clip(months, 0, life)
    q, r = np.divmod(cost * m, life)
    return np.asarray(q + ((2 * r > life) | ((2 * r == life) & (q % 2 == 1))))


def _month_index(dates: pd.Series) -> np.ndarray:
    return np.asarray((dates.dt.year * 12 + dates.dt.month - 1).to_numpy(dtype=np.int64))


@staged(id=f"{_PLAN_MODULE}.fixed_asset_rollforward", sources=("finance.fixed_asset.le_key", "finance.fixed_asset.asset_class", "finance.fixed_asset.acquisition_date", "finance.fixed_asset.cost", "finance.fixed_asset.useful_life_months",
                 "finance.fixed_asset.disposal_date", "finance.fixed_asset.depreciation_method", "finance.fixed_asset.currency"),
        facts=(*_METHODS, _DEPRECIATION_START, "world.window_start", "world.now"), oracle="py:tests/test_finance.py::test_fixed_asset_register_and_schedule")
def fixed_asset_rollforward(fixed_asset: pd.DataFrame) -> Envelope:
    """Use this when you need the monthly cost and accumulated depreciation of the fixed asset register, per entity and asset class.

    Rule: straight line depreciation of cost over useful_life_months, from the month after acquisition, accumulated amounts rounded half to even to the cent and exact at the end of the life. A
    disposal month is depreciated and then derecognised. An asset acquired before the window opens opens with its accumulated depreciation. The window is the fact world.window_start to world.now.
    A depreciation method other than the fact fin.fixed_assets.<country>.method (straight_line_monthly) is refused.

    Args:
        fixed_asset: Frame finance.fixed_asset with le_key, asset_class, acquisition_date, cost, useful_life_months, disposal_date, depreciation_method and currency.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame in the shape of finance.fixed_asset_schedule: le_key, asset_class, period (text like 2025-02), cost_opening, additions, disposals_cost,
        cost_closing, accumulated_opening, depreciation, disposals_accumulated, accumulated_closing and net_book_value (all in the entity currency), and currency.
        Typed form: AssetScheduleRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, an asset has no acquisition date or no positive number of months, an asset is disposed of before it was acquired, or the method is not the fact's method.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import fixed_asset_rollforward
        >>> ctx = Context(stage="month3", role="analyst")
        >>> fa = pd.DataFrame([{"le_key": "LE-01", "asset_class": "IT", "acquisition_date": dt.date(2023, 2, 10), "cost": 900.0, "useful_life_months": 3, "disposal_date": None,
        ...                     "depreciation_method": "straight_line_monthly", "currency": "DKK"}])
        >>> s = fixed_asset_rollforward(fa, context=ctx).value.set_index("period")
        >>> s.loc[["2023-02", "2023-03", "2023-05"], "accumulated_closing"].tolist()
        [0.0, 300.0, 900.0]
    """
    _need(fixed_asset, ["le_key", "asset_class", "acquisition_date", "cost", "useful_life_months", "disposal_date", "depreciation_method", "currency"], "finance.fixed_asset")
    facts = [fact(i) for i in (*_METHODS, _DEPRECIATION_START, "world.window_start", "world.now")]
    if str(facts[2].value) != "month_after_acquisition":
        raise FrameError(f"the fact {_DEPRECIATION_START} says {facts[2].value!r}; only month_after_acquisition is rebuilt")
    methods = {str(f.value) for f in facts[:2]}
    if len(methods) != 1:
        raise FrameError(f"the facts give different depreciation methods: {sorted(methods)}")
    method = methods.pop()
    bad = fixed_asset.loc[fixed_asset["depreciation_method"] != method, "depreciation_method"]
    if len(bad):
        raise FrameError(f"{len(bad)} assets use the method {bad.iloc[0]!r}; only {method!r} (fact {_METHODS[0]}) is rebuilt")
    w0, now = pd.Timestamp(facts[3].value), pd.Timestamp(facts[4].value)
    fa = _days(fixed_asset, ["acquisition_date", "disposal_date"], "finance.fixed_asset")
    if fa["acquisition_date"].isna().any():
        raise FrameError(f"{int(fa['acquisition_date'].isna().sum())} assets have no acquisition date")
    life_in = pd.to_numeric(fa["useful_life_months"], errors="coerce")
    if (life_in.isna() | (life_in <= 0)).any():
        raise FrameError("useful_life_months must be a positive number of months for every asset")
    if (fa["disposal_date"] < fa["acquisition_date"]).any():
        raise FrameError(f"{int((fa['disposal_date'] < fa['acquisition_date']).sum())} assets are disposed of before they were acquired")
    fa = fa[~(fa["disposal_date"] < w0)].reset_index(drop=True)                    # gone before the window: neither cost nor depreciation in any period of it
    first, last = w0.year * 12 + w0.month - 1, now.year * 12 + now.month - 1
    M = last - first + 1
    cost, life = _cents(fa["cost"]), fa["useful_life_months"].to_numpy(dtype=np.int64)
    pm = _month_index(fa["acquisition_date"])
    rm = np.where(fa["disposal_date"].notna().to_numpy() & (fa["disposal_date"] <= now).to_numpy(), _month_index(fa["disposal_date"].fillna(w0)), -1)
    pre = (fa["acquisition_date"] < w0).to_numpy()
    acc0 = np.where(pre, _cum_dep(cost, (first - 1) - pm, life), 0)
    t_idx = np.arange(M)
    mm = (first + t_idx)[None, :] - pm[:, None]
    lastm = np.where(rm >= 0, rm - pm, 10 ** 6)[:, None]
    cum_now = _cum_dep(cost[:, None], np.minimum(mm, lastm), life[:, None])
    cum_prev = np.empty_like(cum_now)
    cum_prev[:, 1:], cum_prev[:, 0] = cum_now[:, :-1], np.where(pre, acc0, 0)
    dep = cum_now - cum_prev
    tp = np.where(pre, -1, np.clip(pm - first, -1, M))
    tr = np.where(rm >= 0, np.clip(rm - first, -1, M), 10 ** 6)
    acc_ret = _cum_dep(cost, rm - pm, life)
    periods = pd.period_range(w0, now, freq="M").strftime("%Y-%m")
    rows = []
    for le in sorted(fa["le_key"].unique()):
        for cls in sorted(fa.loc[fa["le_key"] == le, "asset_class"].unique()):
            m = ((fa["le_key"] == le) & (fa["asset_class"] == cls)).to_numpy()
            c_open, a_open = int(cost[m & pre].sum()), int(acc0[m].sum())
            ccy = fa.loc[m, "currency"].iloc[0]
            for t in range(M):
                add, dis_m = int(cost[m & (tp == t)].sum()), m & (tr == t)
                dis, dis_ad, d_ = int(cost[dis_m].sum()), int(acc_ret[dis_m].sum()), int(dep[m, t].sum())
                c_close, a_close = c_open + add - dis, a_open + d_ - dis_ad
                rows.append((le, cls, periods[t], c_open, add, dis, c_close, a_open, d_, dis_ad, a_close, c_close - a_close, ccy))
                c_open, a_open = c_close, a_close
    out = pd.DataFrame(rows, columns=["le_key", "asset_class", "period", "cost_opening", "additions", "disposals_cost", "cost_closing", "accumulated_opening", "depreciation", "disposals_accumulated",
                                      "accumulated_closing", "net_book_value", "currency"])
    for c in out.columns[3:12]:
        out[c] = out[c] / 100.0
    return make_envelope(out, "halvaro.finance.subledgers.fixed_asset_rollforward", facts=facts, sources=("finance.fixed_asset",))


@staged(id=f"{_PLAN_MODULE}.inventory_valuation_check", sources=("finance.inventory_valuation.le_key", "finance.inventory_valuation.site_key", "finance.inventory_valuation.item_category", "finance.inventory_valuation.period", "finance.inventory_valuation.gl_key", "finance.inventory_valuation.stock_value", "finance.inventory_valuation.slow_moving_value", "finance.inventory_valuation.allowance", "finance.inventory_valuation.net_stock_value", "finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.closing_balance"),
        facts=(_ALLOWANCE_RATE,), oracle="py:tests/test_finance_planning.py::test_inventory_valuation_ties_to_the_ledger")
def inventory_valuation_check(inventory_valuation: pd.DataFrame, trial_balance: pd.DataFrame, *, allowance_gl: str = "GL-2015", tolerance: float = 0.011) -> Envelope:
    """Use this when you need to check the inventory valuation for missing amounts, the allowance rule and agreement with the ledger.

    Rule: net_stock: net_stock_value = stock_value less allowance. allowance_rate: allowance = the fact fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate (status VERIFY)
    times slow_moving_value. allowance_over_slow_moving: the allowance is not above the slow moving value. missing_value: an amount is missing. ledger_stock and ledger_allowance: per entity and
    period the valuation equals the ledger accounts of stock and of the allowance (allowance_gl) within the tolerance, and a period with stock in the ledger and no valuation row is a break.

    Args:
        inventory_valuation: Frame finance.inventory_valuation with le_key, site_key, item_category, period, gl_key, stock_value, slow_moving_value, allowance and net_stock_value.
        trial_balance: Frame finance.trial_balance with le_key, period, gl_key and closing_balance, one row per entity, period and account.
        allowance_gl: Ledger account of the allowance (default GL-2015, PROPOSED).
        tolerance: Largest accepted difference in currency units (default 0.011).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame of violations (table, key, rule, detail), empty when the valuation is clean. The envelope carries the VERIFY status of the allowance rate.
        Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, the tolerance is negative or not a number, or the trial balance has more than one row for an entity, period and account.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context, fact
        >>> from halvaro.finance import inventory_valuation_check
        >>> ctx = Context(stage="month3", role="analyst")
        >>> rate = fact("fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate").value
        >>> allowance = round(200.0 * rate, 2)
        >>> iv = pd.DataFrame([{"le_key": "LE-01", "site_key": "SITE-01", "item_category": "cable", "period": "2023-01", "gl_key": "GL-2010", "stock_value": 1000.0,
        ...                     "slow_moving_value": 200.0, "allowance": allowance, "net_stock_value": 1000.0 - allowance}])
        >>> tb = pd.DataFrame({"le_key": "LE-01", "period": "2023-01", "gl_key": ["GL-2010", "GL-2015"], "closing_balance": [1000.0, -allowance]})
        >>> inventory_valuation_check(iv, tb, context=ctx).value.empty
        True
    """
    _need(inventory_valuation, ["le_key", "site_key", "item_category", "period", "gl_key", "stock_value", "slow_moving_value", "allowance", "net_stock_value"], "finance.inventory_valuation")
    _need(trial_balance, ["le_key", "period", "gl_key", "closing_balance"], "finance.trial_balance")
    f = fact(_ALLOWANCE_RATE)
    iv, rows = inventory_valuation, []
    key = iv["le_key"] + " " + iv["site_key"] + " " + iv["item_category"] + " " + iv["period"]
    net_off = (iv["net_stock_value"] - (iv["stock_value"] - iv["allowance"])).abs() > tolerance
    rate_off = (iv["allowance"] - iv["slow_moving_value"] * float(f.value)).abs() > tolerance
    over = iv["allowance"] > iv["slow_moving_value"] + tolerance
    for rule, m, detail in (("net_stock", net_off, "net stock value differs from stock less allowance"), ("allowance_rate", rate_off, f"allowance differs from {f.value} times the slow moving value"),
                            ("allowance_over_slow_moving", over, "allowance above the slow moving value")):
        rows += [("finance.inventory_valuation", k, rule, detail) for k in key[m]]
    for col in ("stock_value", "slow_moving_value", "allowance", "net_stock_value"):
        rows += [("finance.inventory_valuation", k, "missing_value", f"{col} is missing") for k in key[iv[col].isna()]]
    _unique(trial_balance, ["le_key", "gl_key", "period"], "finance.trial_balance")
    tb = trial_balance.set_index(["le_key", "gl_key", "period"])["closing_balance"]
    for rule, col, gls, sgn in (("ledger_stock", "stock_value", sorted(iv["gl_key"].unique()), 1), ("ledger_allowance", "allowance", [allowance_gl], -1)):
        s = iv.groupby(["le_key", "period"])[col].sum()
        ledger = trial_balance[trial_balance["gl_key"].isin(gls) & trial_balance["closing_balance"].abs().gt(tolerance)].groupby(["le_key", "period"]).size().index
        for (le, p) in s.index.union(ledger):                                  # a month with stock in the ledger but no valuation is a break too
            v = float(s.get((le, p), 0.0))
            led = sum(float(tb.get((le, g, p), 0.0)) for g in gls) * sgn
            if abs(v - led) > tolerance:
                rows.append(("finance.inventory_valuation", f"{le} {p}", rule, f"valuation {v:.2f}, ledger {led:.2f}"))
    return make_envelope(violations.frame(rows), "halvaro.finance.subledgers.inventory_valuation_check", facts=(f,), sources=("finance.inventory_valuation", "finance.trial_balance"))


@staged(id=f"{_PLAN_MODULE}.bank_reconciliation", sources=("finance.bank_balance.bank_account", "finance.bank_balance.balance_date", "finance.bank_balance.closing_balance", "finance.payment.bank_account", "finance.payment.payment_date",
                 "finance.payment.direction", "finance.payment.amount", "finance.bank_account.gl_key", "finance.opening_balance_item.amount"),
        oracle="py:tests/test_finance.py::test_bank_balance_equals_cash_accounts_and_payments")
def bank_reconciliation(bank_balance: pd.DataFrame, payment: pd.DataFrame, bank_account: pd.DataFrame, opening_balance_item: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the ledger balance of every bank account rebuilt from the opening balance and the payments, compared with the stored daily balance.

    Rule: computed_balance on a date = the opening balance of the ledger account of the bank account + the signed payments of the account up to and including that date (incoming positive,
    outgoing negative). difference = computed less the stored closing balance, to the cent. Dates without a payment carry the balance of the date before.

    Args:
        bank_balance: Frame finance.bank_balance with le_key, bank_account, balance_date, closing_balance and currency, one row per account and date.
        payment: Frame finance.payment with bank_account, payment_date, direction (incoming or outgoing) and amount.
        bank_account: Frame finance.bank_account with le_key, bank_account and gl_key, one row per account.
        opening_balance_item: Frame finance.opening_balance_item with le_key, gl_key and amount (the opening balance of the ledger accounts).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with le_key, bank_account, balance_date, computed_balance, closing_balance, difference (currency units to the cent) and currency; empty when there are no bank accounts.
        Typed form: BankReconRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a column is missing, a payment direction is neither incoming nor outgoing, or a date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import bank_reconciliation
        >>> ctx = Context(stage="month3", role="analyst")
        >>> bb = pd.DataFrame({"le_key": "LE-01", "bank_account": "BA-1", "balance_date": ["2025-01-02", "2025-01-03"], "closing_balance": [1100.0, 1000.0], "currency": "DKK"})
        >>> pay = pd.DataFrame({"bank_account": ["BA-1", "BA-1"], "payment_date": ["2025-01-02", "2025-01-03"], "direction": ["incoming", "outgoing"], "amount": [100.0, 100.0]})
        >>> ba = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["BA-1"], "gl_key": ["GL-1200"]})
        >>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1200"], "amount": [1000.0]})
        >>> bank_reconciliation(bb, pay, ba, ob, context=ctx)[["computed_balance", "difference"]].values.tolist()
        [[1100.0, 0.0], [1000.0, 0.0]]
    """
    _need(bank_balance, ["le_key", "bank_account", "balance_date", "closing_balance", "currency"], "finance.bank_balance")
    _need(payment, ["bank_account", "payment_date", "direction", "amount"], "finance.payment")
    _need(bank_account, ["le_key", "bank_account", "gl_key"], "finance.bank_account")
    _need(opening_balance_item, ["le_key", "gl_key", "amount"], "finance.opening_balance_item")
    bb = _days(bank_balance, ["balance_date"], "finance.bank_balance")
    pay = _days(payment[["bank_account", "payment_date", "direction", "amount"]], ["payment_date"], "finance.payment")
    if not set(pay["direction"]) <= {"incoming", "outgoing"}:
        raise FrameError(f"payment direction other than incoming or outgoing: {sorted(set(pay['direction']) - {'incoming', 'outgoing'})}")
    pay["c"] = _cents(pay["amount"]) * np.where(pay["direction"] == "incoming", 1, -1)
    opening = opening_balance_item.assign(c=_cents(opening_balance_item["amount"])).groupby(["le_key", "gl_key"])["c"].sum()
    out = []
    for r in bank_account.to_dict("records"):
        x = bb[bb["bank_account"] == r['bank_account']].sort_values("balance_date")
        day = pay[pay["bank_account"] == r['bank_account']].groupby("payment_date")["c"].sum().sort_index().cumsum()
        moved = day.reindex(day.index.union(x["balance_date"])).ffill().fillna(0).reindex(x["balance_date"]).to_numpy(dtype=np.int64)
        computed = int(opening.get((r['le_key'], r['gl_key']), 0)) + moved
        out.append(pd.DataFrame({"le_key": r['le_key'], "bank_account": r['bank_account'], "balance_date": x["balance_date"].to_numpy(), "computed_balance": computed / 100.0,
                                 "closing_balance": x["closing_balance"].to_numpy(), "difference": (computed - _cents(x["closing_balance"])) / 100.0, "currency": x["currency"].to_numpy()}))
    if not out:
        return pd.DataFrame(columns=["le_key", "bank_account", "balance_date", "computed_balance", "closing_balance", "difference", "currency"])
    return pd.concat(out, ignore_index=True)


@staged(id=f"{_PLAN_MODULE}.intercompany_agreement", sources=("finance.intercompany.ic_type", "finance.intercompany.document_date", "finance.intercompany.creditor_amount", "finance.intercompany.creditor_currency", "finance.intercompany.debtor_amount", "finance.intercompany.currency", "finance.intercompany.difference_dkk", "finance.intercompany.matched", "finance.intercompany_balance.period", "finance.intercompany_balance.balance_type", "finance.intercompany_balance.creditor_le_key", "finance.intercompany_balance.debtor_le_key", "finance.intercompany_balance.creditor_balance", "finance.intercompany_balance.creditor_currency", "finance.intercompany_balance.debtor_balance", "finance.intercompany_balance.debtor_currency", "finance.intercompany_balance.difference_dkk", "finance.intercompany_balance.agrees"),
        facts=_FX_FACTS, oracle="py:halvaro_gen/world/finance/checks.py::intercompany_agrees")
def intercompany_agreement(intercompany: pd.DataFrame, intercompany_balance: pd.DataFrame, *, tolerance_dkk: float = 1.0) -> Envelope:
    """Use this when you need to check that the two sides of the intercompany records agree.

    Rule: both sides of a record are converted to DKK at the fixed booking rates (facts world.fx_eur_dkk_fixed and world.fx_sek_dkk_fixed) and must agree within tolerance_dkk; the stored
    difference_dkk must equal the recomputed one and the stored flags matched (documents) and agrees (balances) must say the same as the recomputation. The tolerance is a PROPOSED keyword.

    Args:
        intercompany: Frame finance.intercompany with ic_type, document_date, creditor_amount, creditor_currency, debtor_amount, currency, difference_dkk and matched.
        intercompany_balance: Frame finance.intercompany_balance with period, creditor and debtor entity, balance_type, both balances and currencies, difference_dkk and agrees.
        tolerance_dkk: Largest accepted difference between the two sides, in DKK (default 1.0, PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame of violations (table, key, rule, detail), empty when both sides agree. The envelope carries the VERIFY status of the exchange rate facts.
        Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, the tolerance is negative or not a number, or a date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import intercompany_agreement
        >>> ctx = Context(stage="month3", role="analyst")
        >>> ic = pd.DataFrame({"ic_type": ["recharge"], "document_date": ["2025-01-31"], "creditor_amount": [100.0], "creditor_currency": ["DKK"], "debtor_amount": [100.0],
        ...                    "currency": ["DKK"], "difference_dkk": [0.0], "matched": [True]})
        >>> icb = pd.DataFrame({"period": ["2025-01"], "creditor_le_key": ["LE-01"], "debtor_le_key": ["LE-02"], "balance_type": ["trade"], "creditor_balance": [100.0],
        ...                     "creditor_currency": ["DKK"], "debtor_balance": [100.0], "debtor_currency": ["DKK"], "difference_dkk": [0.0], "agrees": [True]})
        >>> intercompany_agreement(ic, icb, context=ctx).value.empty
        True
    """
    _need(intercompany, ["ic_type", "document_date", "creditor_amount", "creditor_currency", "debtor_amount", "currency", "difference_dkk", "matched"], "finance.intercompany")
    _need(intercompany_balance, ["period", "creditor_le_key", "debtor_le_key", "balance_type", "creditor_balance", "creditor_currency", "debtor_balance", "debtor_currency", "difference_dkk", "agrees"],
          "finance.intercompany_balance")
    if isinstance(tolerance_dkk, bool) or not isinstance(tolerance_dkk, (int, float, np.number)) or not np.isfinite(tolerance_dkk) or tolerance_dkk < 0:
        raise FrameError("tolerance_dkk must be zero or more")

    def dkk(amount: pd.Series, currency: pd.Series) -> np.ndarray:
        out = np.zeros(len(amount), dtype=np.int64)
        for cur in currency.unique():
            m = (currency == cur).to_numpy()
            out[m] = convert(pd.Series(_cents(amount[m])), str(cur), "DKK", basis="booking").to_numpy()
        return out

    rows = []
    for table, df, cred, cur_c, debt, cur_d, flag, key in (
            ("finance.intercompany", intercompany, "creditor_amount", "creditor_currency", "debtor_amount", "currency", "matched", intercompany["ic_type"] + " " + intercompany["document_date"].astype(str)),
            ("finance.intercompany_balance", intercompany_balance, "creditor_balance", "creditor_currency", "debtor_balance", "debtor_currency", "agrees",
             intercompany_balance["period"] + " " + intercompany_balance["balance_type"])):
        diff = (dkk(df[cred], df[cur_c]) - dkk(df[debt], df[cur_d])) / 100.0
        within = np.abs(diff) <= tolerance_dkk
        for k, d_stored, d_calc, ok_calc, ok_stored in zip(key + " #" + pd.Series(range(len(df))).astype(str), df["difference_dkk"], diff, within, df[flag]):
            if pd.isna(d_stored):
                rows.append((table, k, "difference_dkk", f"stored difference is missing, recomputed {d_calc:.2f}"))
            elif abs(d_stored - d_calc) > _TOLERANCE_CENT:
                rows.append((table, k, "difference_dkk", f"stored {d_stored:.2f}, recomputed {d_calc:.2f}"))
            if pd.isna(ok_stored):
                rows.append((table, k, f"{flag}_flag", f"flag is missing, recomputed {bool(ok_calc)} at tolerance {tolerance_dkk}"))
            elif bool(ok_calc) != bool(ok_stored):
                rows.append((table, k, f"{flag}_flag", f"flag {bool(ok_stored)}, recomputed {bool(ok_calc)} at tolerance {tolerance_dkk}"))
            if not ok_calc:
                rows.append((table, k, "outside_tolerance", f"difference {d_calc:.2f} DKK"))
    return make_envelope(violations.frame(rows), "halvaro.finance.subledgers.intercompany_agreement", sources=("finance.intercompany", "finance.intercompany_balance"))
