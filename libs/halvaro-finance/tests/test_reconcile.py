"""Reconciliation and registers (part d): the month end rebuild of the subledgers, fixed asset roll forward, inventory, bank and intercompany checks. Synthetic frames, then the baseline release against the stored tables."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")
D = dt.date


# ---- fixed assets


def _asset(**kw):
    base = {"le_key": "LE-01", "asset_class": "IT", "acquisition_date": D(2023, 2, 10), "cost": 1000.0, "useful_life_months": 3, "disposal_date": None, "depreciation_method": "straight_line_monthly",
            "currency": "DKK"}
    return pd.DataFrame([{**base, **kw}])


def _row(sch, period, col, cls="IT"):
    return float(sch[(sch.period == period) & (sch.asset_class == cls)][col].iloc[0])


def test_straight_line_from_the_month_after_acquisition_rounded_half_even_exact_at_the_end():
    env = fin.fixed_asset_rollforward(_asset(), context=M3)
    s = env.value
    assert env.status == "VERIFY" and len(s) == 47 and list(s.columns)[:3] == ["le_key", "asset_class", "period"]
    assert [_row(s, p, "depreciation") for p in ("2023-02", "2023-03", "2023-04", "2023-05", "2023-06")] == [0.0, 333.33, 333.34, 333.33, 0.0]
    assert _row(s, "2023-02", "additions") == 1000 and _row(s, "2023-03", "additions") == 0 and _row(s, "2023-05", "accumulated_closing") == 1000 and _row(s, "2023-05", "net_book_value") == 0
    assert _row(s, "2023-01", "cost_closing") == 0 and _row(s, "2026-11", "cost_closing") == 1000


def test_half_even_rounding_on_an_exact_half_cent():
    s = fin.fixed_asset_rollforward(_asset(cost=0.01, useful_life_months=2), context=M3).value
    assert [_row(s, p, "accumulated_closing") for p in ("2023-03", "2023-04")] == [0.0, 0.01], "0.5 cent rounds to the even cent (0)"
    s2 = fin.fixed_asset_rollforward(_asset(cost=0.03, useful_life_months=2), context=M3).value
    assert [_row(s2, p, "accumulated_closing") for p in ("2023-03", "2023-04")] == [0.02, 0.03], "1.5 cents rounds to 2"


def test_disposal_month_is_depreciated_then_derecognised_and_pre_window_assets_open_with_accumulated():
    s = fin.fixed_asset_rollforward(_asset(disposal_date=D(2023, 4, 20)), context=M3).value
    assert _row(s, "2023-04", "depreciation") == 333.34 and _row(s, "2023-04", "disposals_cost") == 1000 and _row(s, "2023-04", "disposals_accumulated") == 666.67
    assert _row(s, "2023-04", "cost_closing") == 0 and _row(s, "2023-04", "accumulated_closing") == 0 and _row(s, "2023-05", "depreciation") == 0
    pre = fin.fixed_asset_rollforward(_asset(acquisition_date=D(2022, 6, 15), cost=2400.0, useful_life_months=24), context=M3).value
    assert _row(pre, "2023-01", "cost_opening") == 2400 and _row(pre, "2023-01", "accumulated_opening") == 600.0 and _row(pre, "2023-01", "depreciation") == 100.0 and _row(pre, "2023-01", "additions") == 0
    assert _row(pre, "2024-06", "accumulated_closing") == 2400 and _row(pre, "2024-07", "depreciation") == 0
    late = fin.fixed_asset_rollforward(_asset(disposal_date=D(2027, 1, 5)), context=M3).value
    assert _row(late, "2026-11", "disposals_cost") == 0, "a disposal after the last month is not in the window"


def test_rollforward_groups_by_entity_and_class_and_refuses_other_methods_and_bad_input():
    two = pd.concat([_asset(), _asset(asset_class="VEH", cost=500.0, le_key="LE-02", currency="EUR")], ignore_index=True)
    s = fin.fixed_asset_rollforward(two, context=M3).value
    assert sorted(set(zip(s.le_key, s.asset_class, s.currency))) == [("LE-01", "IT", "DKK"), ("LE-02", "VEH", "EUR")] and len(s) == 94
    with pytest.raises(FrameError, match="use the method 'declining'"):
        fin.fixed_asset_rollforward(_asset(depreciation_method="declining"), context=M3)
    with pytest.raises(FrameError, match="lacks column"):
        fin.fixed_asset_rollforward(_asset().drop(columns="cost"), context=M3)


# ---- inventory, bank, intercompany


def _iv(**kw):
    rate = fact("fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate").value
    base = {"le_key": "LE-01", "site_key": "SITE-01", "item_category": "cable", "period": "2023-01", "gl_key": "GL-2010", "stock_value": 1000.0, "slow_moving_value": 200.0,
            "allowance": round(200 * rate, 2), "net_stock_value": 1000.0 - round(200 * rate, 2)}
    return pd.DataFrame([{**base, **kw}])


def _tb(stock=1000.0, allowance=20.0):
    return pd.DataFrame({"le_key": "LE-01", "period": "2023-01", "gl_key": ["GL-2010", "GL-2015"], "closing_balance": [stock, -allowance]})


def test_inventory_valuation_check_each_rule():
    ok = fin.inventory_valuation_check(_iv(), _tb(), context=M3)
    assert ok.value.empty and ok.status == "VERIFY" and ok.facts_used[0][1] == 0.1
    rules = lambda iv, tb: set(fin.inventory_valuation_check(iv, tb, context=M3).value.rule)
    assert rules(_iv(net_stock_value=981.0), _tb()) == {"net_stock"} and rules(_iv(allowance=30.0, net_stock_value=970.0), _tb(allowance=30.0)) == {"allowance_rate"}
    assert rules(_iv(allowance=210.0, net_stock_value=790.0, slow_moving_value=200.0), _tb(allowance=210.0)) >= {"allowance_over_slow_moving"}
    assert rules(_iv(), _tb(stock=1005.0)) == {"ledger_stock"} and rules(_iv(), _tb(allowance=25.0)) == {"ledger_allowance"}
    assert rules(_iv(), _tb(stock=1000.01)) == set(), "within the tolerance of a cent"
    assert rules(_iv(), _tb(stock=1000.02)) == {"ledger_stock"}


def test_bank_reconciliation_opening_plus_signed_payments():
    bb = pd.DataFrame({"le_key": "LE-01", "bank_account": "B", "balance_date": [D(2023, 1, 1), D(2023, 1, 2), D(2023, 1, 3), D(2023, 1, 4)], "closing_balance": [1000.0, 1200.0, 1150.0, 1150.0], "currency": "DKK"})
    pay = pd.DataFrame({"bank_account": "B", "payment_date": [D(2023, 1, 2), D(2023, 1, 3)], "direction": ["incoming", "outgoing"], "amount": [200.0, 50.0]})
    ba = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["B"], "gl_key": ["GL-2610"]})
    ob = pd.DataFrame({"le_key": "LE-01", "gl_key": ["GL-2610", "GL-2200"], "amount": [1000.0, 5.0]})
    r = fin.bank_reconciliation(bb, pay, ba, ob, context=M3)
    assert r.computed_balance.tolist() == [1000, 1200, 1150, 1150] and r.difference.abs().max() == 0 and r.balance_date.is_monotonic_increasing
    bad = fin.bank_reconciliation(bb.assign(closing_balance=[1000.0, 1200.0, 1149.99, 1150.0]), pay, ba, ob, context=M3)
    assert bad.difference.tolist() == [0, 0, 0.01, 0]
    with pytest.raises(FrameError, match="direction other than"):
        fin.bank_reconciliation(bb, pay.assign(direction="sideways"), ba, ob, context=M3)


def _ic(**kw):
    eur = fact("world.fx_eur_dkk_fixed").value
    cred = round(21000 * eur, 2)
    base = {"ic_type": "it_recharge", "document_date": D(2023, 1, 2), "creditor_amount": cred, "creditor_currency": "DKK", "debtor_amount": 21000.0, "currency": "EUR", "difference_dkk": 0.0, "matched": True}
    return pd.DataFrame([{**base, **kw}])


def _icb(**kw):
    eur = fact("world.fx_eur_dkk_fixed").value
    base = {"period": "2023-01", "creditor_le_key": "LE-01", "debtor_le_key": "LE-02", "balance_type": "trade", "creditor_balance": round(1000 * eur, 2), "debtor_balance": 1000.0,
            "creditor_currency": "DKK", "debtor_currency": "EUR", "difference_dkk": 0.0, "agrees": True}
    return pd.DataFrame([{**base, **kw}])


def test_intercompany_agreement_recomputes_the_difference_and_the_flags():
    assert fin.intercompany_agreement(_ic(), _icb(), context=M3).value.empty
    eur = fact("world.fx_eur_dkk_fixed").value
    off = fin.intercompany_agreement(_ic(creditor_amount=round(21000 * eur, 2) + 5, difference_dkk=0.0), _icb(), context=M3).value
    assert set(off.rule) == {"difference_dkk", "matched_flag", "outside_tolerance"} and set(off.table) == {"finance.intercompany"}
    ok = fin.intercompany_agreement(_ic(creditor_amount=round(21000 * eur, 2) + 0.5, difference_dkk=0.5), _icb(), context=M3).value
    assert ok.empty, "half a krone is inside the tolerance of one"
    tight = fin.intercompany_agreement(_ic(creditor_amount=round(21000 * eur, 2) + 0.5, difference_dkk=0.5), _icb(), tolerance_dkk=0.1, context=M3).value
    assert set(tight.rule) == {"matched_flag", "outside_tolerance"}
    bal = fin.intercompany_agreement(_ic(), _icb(debtor_balance=1010.0, difference_dkk=0.0, agrees=True), context=M3).value
    assert set(bal.table) == {"finance.intercompany_balance"} and set(bal.rule) == {"difference_dkk", "agrees_flag", "outside_tolerance"}


def test_rollforward_drops_assets_gone_before_the_window_and_refuses_impossible_input():
    gone = _asset(asset_class="OLD", acquisition_date=D(2022, 3, 10), useful_life_months=24, disposal_date=D(2022, 12, 20))
    s = fin.fixed_asset_rollforward(pd.concat([_asset(), gone], ignore_index=True), context=M3).value
    assert set(s.asset_class) == {"IT"}, "an asset disposed of before 2023-01 is in no period of the window"
    for bad, msg in ((_asset(disposal_date=D(2023, 1, 5)), "disposed of before they were acquired"), (_asset(useful_life_months=0), "positive number of months"),
                     (_asset(useful_life_months=None), "positive number of months"), (_asset(acquisition_date=None), "no acquisition date")):
        with pytest.raises(FrameError, match=msg):
            fin.fixed_asset_rollforward(bad, context=M3)


def test_inventory_check_sees_months_the_valuation_leaves_out_and_null_amounts():
    tb = pd.concat([_tb(), _tb().assign(period="2023-02")], ignore_index=True)
    r = fin.inventory_valuation_check(_iv(), tb, context=M3).value
    assert set(r.rule) == {"ledger_stock", "ledger_allowance"} and set(r.key) == {"LE-01 2023-02"}, "stock in the ledger and no valuation row is a break"
    nulls = fin.inventory_valuation_check(_iv(allowance=np.nan), _tb(), context=M3).value
    assert "missing_value" in set(nulls.rule), "a null amount does not pass every rule"
    assert fin.inventory_valuation_check(_iv(net_stock_value=np.nan), _tb(), context=M3).value.rule.tolist().count("missing_value") == 1
    with pytest.raises(FrameError, match="more than one row"):
        fin.inventory_valuation_check(_iv(), pd.concat([_tb(), _tb()]), context=M3)


def test_bank_without_accounts_and_intercompany_nulls_and_bad_dates():
    cols = ["le_key", "bank_account", "balance_date", "closing_balance", "currency"]
    empty = fin.bank_reconciliation(pd.DataFrame(columns=cols), pd.DataFrame(columns=["bank_account", "payment_date", "direction", "amount"]), pd.DataFrame(columns=["le_key", "bank_account", "gl_key"]),
                                    pd.DataFrame(columns=["le_key", "gl_key", "amount"]), context=M3)
    assert empty.empty and "difference" in empty.columns
    r = fin.intercompany_agreement(_ic(difference_dkk=np.nan, matched=np.nan), _icb(), context=M3).value
    assert set(r.rule) == {"difference_dkk", "matched_flag"} and r.detail.str.contains("missing").all()
    r = fin.intercompany_agreement(_ic(), _icb(agrees=None, difference_dkk=np.nan), context=M3).value
    assert set(r.table) == {"finance.intercompany_balance"} and set(r.rule) == {"difference_dkk", "agrees_flag"}


# ---- the rebuild on small frames


def _recon_frames(periods=("2023-01", "2023-02", "2023-03"), inv_date=D(2023, 1, 15), schedule_classes=("IT",), ic_ledger=0.0):
    gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100", "GL-1400", "GL-1490", "GL-1500", "GL-1590", "GL-2300"],
                       "control_type": ["ar", "retention", "ap", None, None, None, None, None]})
    ledger = {"GL-1100": 900.0, "GL-1190": 100.0, "GL-2100": 0.0, "GL-1400": 200.0, "GL-1490": -50.0, "GL-1500": 500.0, "GL-1590": 0.0, "GL-2300": ic_ledger}
    tb = pd.DataFrame([{"le_key": "LE-01", "period": p, "gl_key": g, "closing_balance": v} for p in periods for g, v in ledger.items()])
    ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "invoice_type": "invoice", "invoice_date": inv_date, "gross_amount_le": 1000.0, "retention_amount_le": 100.0,
                       "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
    si = pd.DataFrame(columns=["le_key", "invoice_type", "invoice_date", "payable_amount_le"])
    pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
    alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
    ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1400"], "item_ref": ["O1"], "document_date": [D(2022, 12, 1)], "due_date": [None], "amount": [0.0], "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
    fa = pd.DataFrame({"asset_class": ["IT", "VEH"], "gl_cost_key": ["GL-1400", "GL-1500"], "gl_accumulated_key": ["GL-1490", "GL-1590"]})
    sch = pd.DataFrame([{"le_key": "LE-01", "asset_class": c, "period": p, "cost_closing": 200.0, "accumulated_closing": 50.0} for c in schedule_classes for p in periods])
    iv = pd.DataFrame(columns=["le_key", "period", "gl_key", "stock_value", "allowance"])
    ic = pd.DataFrame(columns=["ic_type", "creditor_le_key", "debtor_le_key", "document_date", "settlement_date", "creditor_amount", "debtor_amount"])
    bb = pd.DataFrame(columns=["bank_account", "balance_date", "closing_balance"])
    ba = pd.DataFrame(columns=["le_key", "bank_account", "gl_key"])
    return dict(customer_invoice=ci, supplier_invoice=si, payment=pay, payment_allocation=alloc, opening_balance_item=ob, fixed_asset=fa, fixed_asset_schedule=sch, inventory_valuation=iv,
                intercompany=ic, bank_balance=bb, bank_account=ba, trial_balance=tb, gl_account=gl)


def test_rebuild_on_small_frames_reconciles_and_shows_breaks_a_missing_subledger_would_hide():
    r = fin.rebuild_subledger_reconciliation(**_recon_frames(), context=M3)
    by = r.set_index(["subledger", "detail"])
    assert by.loc[("receivables", "")].reconciled.all() and by.loc[("retention_receivable", "")].reconciled.all(), "900 of receivables and 100 of retention from one invoice of 1000"
    assert by.loc[("fixed_assets_cost", "IT")].reconciled.all() and by.loc[("fixed_assets_accumulated_depreciation", "IT")].reconciled.all()
    broken = r[~r.reconciled]
    assert set(zip(broken.subledger, broken.detail)) == {("fixed_assets_cost", "VEH")}, "the class missing from the schedule still has cost in the ledger"
    assert (broken.difference == -500.0).all() and len(broken) == 3
    ic = fin.rebuild_subledger_reconciliation(**_recon_frames(ic_ledger=1000.0), context=M3)
    x = ic[(ic.subledger == "intercompany_trade") & (ic.detail == "creditor")]
    assert len(x) == 3 and (x.difference == -1000.0).all() and not x.reconciled.any(), "a ledger balance with an empty register is a break, not a skipped row"


def test_rebuild_counts_events_between_periods_in_the_next_period_and_refuses_bad_input():
    r = fin.rebuild_subledger_reconciliation(**_recon_frames(periods=("2023-03", "2023-06"), inv_date=D(2023, 4, 10)), context=M3)
    rec = r[r.subledger == "receivables"].set_index("period")
    assert rec.subledger_balance.to_dict() == {"2023-03": 0.0, "2023-06": 900.0}, "April belongs to the first month end that follows"
    frames = _recon_frames()
    with pytest.raises(FrameError, match="more than one row"):
        fin.rebuild_subledger_reconciliation(**{**frames, "trial_balance": pd.concat([frames["trial_balance"]] * 2)}, context=M3)
    with pytest.raises(FrameError, match="not a date"):
        fin.rebuild_subledger_reconciliation(**{**frames, "customer_invoice": frames["customer_invoice"].assign(invoice_date="not a date")}, context=M3)
    with pytest.raises(FrameError, match="has no rows"):
        fin.rebuild_subledger_reconciliation(**{**frames, "trial_balance": frames["trial_balance"].iloc[0:0]}, context=M3)
