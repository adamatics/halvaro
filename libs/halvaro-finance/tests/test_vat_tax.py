"""VAT and tax (plan 5.7): hand computed ledger lines, returns, provisions and invoice formats."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal, fact, registry

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")


def _lines(rows):
    return pd.DataFrame(rows, columns=["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency", "source"])


def _ledger():
    return _lines([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "DKK", "ar"), ("LE-01", "GL-2510", "2025-01", 100.0, "DK25", 400.0, "DKK", "ap"),
                   ("LE-01", "GL-4720", "2025-01", -50.0, "RC-EU", 200.0, "DKK", "ap"), ("LE-01", "GL-2520", "2025-01", 50.0, "RC-EU", 200.0, "DKK", "ap"),
                   ("LE-01", "GL-4710", "2025-03", -25.0, "DK25", 100.0, "DKK", "ar"), ("LE-01", "GL-4730", "2025-01", 0.0, None, None, "DKK", "treasury"),
                   ("LE-02", "GL-4710", "2025-02", -190.0, "DE19", 1000.0, "EUR", "ar")])


def test_vat_return_boxes_bases_and_months_from_the_coded_lines():
    r = fin.vat_return_from_ledger(_ledger(), context=M3)
    v = r.value.set_index(["le_key", "period"])
    assert r.status == "VERIFY" and len(r.facts_used) == 7 and "placeholder" in r.warnings[0], "the box labels are VERIFY facts"
    jan = v.loc[("LE-01", "2025-01")]
    assert (jan.output_vat_domestic, jan.output_vat_acquisition_eu, jan.input_vat_domestic, jan.input_vat_acquisition_eu, jan.total_output_vat, jan.total_input_vat, jan.vat_payable) == (250.0, 50.0, 100.0, 50.0, 300.0, 150.0, 150.0)
    assert (jan.taxable_base_domestic_sales, jan.taxable_base_acquisitions_eu, jan.taxable_base_domestic_purchases, jan.currency) == (1000.0, 200.0, 400.0, "DKK")
    assert v.loc[("LE-01", "2025-02")].vat_payable == 0.0 and v.loc[("LE-01", "2025-03")].vat_payable == 25.0, "a month without lines is listed with zeros"
    assert v.loc[("LE-02", "2025-02")].output_vat_domestic == 190.0 and ("LE-02", "2025-01") not in v.index
    assert [k for k in v.columns if k.startswith(("output_", "input_"))] == ["output_vat_domestic", "output_vat_acquisition_eu", "output_vat_acquisition_non_eu", "input_vat_domestic", "input_vat_acquisition_eu", "input_vat_acquisition_non_eu", "input_vat_import"]
    for bad, msg in ((_ledger().assign(period=_ledger().period.where(_ledger().index != 0, "2025-1")), "period like"), (_ledger().assign(currency=["DKK"] * 6 + ["EUR"]).assign(currency=lambda d: d.currency.where(d.index != 0, "EUR")), "more than one currency")):
        with pytest.raises(FrameError, match=msg):
            fin.vat_return_from_ledger(bad, context=M3)
    with pytest.raises(FrameError, match="boxes names"):
        fin.vat_return_from_ledger(_ledger(), boxes={"x": (("GL-1",), ())}, context=M3)


def test_vat_code_check_rate_account_and_settlement_rules():
    ok = fin.vat_code_check(_ledger(), context=M3)
    assert ok.value.empty and ok.status == "VERIFY"
    bad = _ledger().assign(amount=_ledger().amount.where(_ledger().index != 0, -240.0))
    r = fin.vat_code_check(bad, context=M3).value
    assert set(r.rule) == {"rate_mismatch"}, "240 on a base of 1000 is 24 percent, the coded totals still agree with the postings"
    assert fin.vat_code_check(bad, min_base=2000.0, context=M3).value.empty, "lines under the minimum base are not rated"
    assert "rate_mismatch" not in set(fin.vat_code_check(bad, ratio_tolerance=0.02, context=M3).value.rule)
    wrong = pd.concat([_ledger(), _lines([("LE-01", "GL-1000", "2025-01", 5.0, "DK25", 20.0, "DKK", "ar")])], ignore_index=True)
    assert "code_on_wrong_account" in set(fin.vat_code_check(wrong, context=M3).value.rule)
    uncoded = pd.concat([_ledger(), _lines([("LE-01", "GL-4710", "2025-01", -9.0, None, None, "DKK", "ar")])], ignore_index=True)
    r3 = fin.vat_code_check(uncoded, context=M3).value
    assert r3.rule.tolist() == ["vat_account_differs_from_coded_lines"] and r3.key.tolist() == ["LE-01 2025-01"], "a posting on a VAT account of a document without a code"
    settle = pd.concat([_ledger(), _lines([("LE-01", "GL-4710", "2025-01", 9.0, None, None, "DKK", "treasury")])], ignore_index=True)
    assert fin.vat_code_check(settle, context=M3).value.empty, "the return journals that clear the accounts have no code and are left out by source"
    assert fin.vat_code_check(settle, settlement_sources=("opening",), context=M3).value.rule.tolist() == ["vat_account_differs_from_coded_lines"]
    # the German code is judged against the German rate
    de = _lines([("LE-02", "GL-4710", "2025-02", -250.0, "DE19", 1000.0, "EUR", "ar")])
    assert fin.vat_code_check(de, context=M3).value.rule.tolist() == ["rate_mismatch"] and fact("fin.vat.DE.standard_rate").value == 0.19


def test_vat_filing_calendar_rolls_to_the_next_working_day_of_the_office_region():
    vr = pd.DataFrame({"le_key": ["LE-01", "LE-01", "LE-02", "LE-02"], "period": ["2023-01", "2023-02", "2023-12", "2025-12"],
                       "filing_due_date": [dt.date(2023, 2, 27), dt.date(2023, 3, 27), dt.date(2024, 1, 10), dt.date(2026, 1, 12)]})
    r = fin.vat_filing_calendar(vr, context=M12)
    v = r.value
    assert r.status == "VERIFY" and v.due_date.tolist() == [dt.date(2023, 2, 27), dt.date(2023, 3, 27), dt.date(2024, 1, 10), dt.date(2026, 1, 12)], "25 February 2023 is a Saturday, 10 January 2026 a Saturday"
    assert v.agrees.tolist() == [True, True, True, True]
    assert not fin.vat_filing_calendar(vr.assign(filing_due_date=[dt.date(2023, 2, 25)] + vr.filing_due_date.tolist()[1:]), context=M12).value.agrees.iloc[0]
    with pytest.raises(FrameError, match="no country"):
        fin.vat_filing_calendar(vr.assign(le_key="LE-09"), context=M12)


def test_vat_settlement_signed_payment_next_month_and_payment_day():
    vr = pd.DataFrame({"le_key": ["LE-01", "LE-01", "LE-01"], "period": ["2025-01", "2025-02", "2025-03"], "vat_payable": [150.0, -20.0, 10.0], "settlement_difference": [0.0, 0.0, np.nan]})
    pay = pd.DataFrame({"le_key": ["LE-01", "LE-01", "LE-01"], "payment_date": [dt.date(2025, 2, 25), dt.date(2025, 3, 26), dt.date(2025, 3, 3)], "direction": ["outgoing", "incoming", "outgoing"],
                        "amount": [150.0, 20.0, 5.0], "description": ["VAT payment", "VAT payment", "Supplier payment run"]})
    s = fin.vat_settlement(vr, pay, context=M12)
    v = s.value.set_index("period")
    assert s.status == "VERIFY" and v.loc["2025-01", "paid_signed"] == 150.0 and v.loc["2025-01", "settlement_difference"] == 0.0 and bool(v.loc["2025-01", "agrees"]) and bool(v.loc["2025-01", "day_agrees"])
    assert v.loc["2025-02", "paid_signed"] == -20.0 and v.loc["2025-02", "settlement_difference"] == 0.0 and not bool(v.loc["2025-02", "day_agrees"]), "refund paid on the 26th, the fact says the 25th (a Tuesday)"
    assert pd.isna(v.loc["2025-03", "settlement_difference"]) and pd.isna(v.loc["2025-03", "agrees"]), "no payment in April"
    off = vr.assign(vat_payable=[149.0, -20.0, 10.0])
    assert not bool(fin.vat_settlement(off, pay, context=M12).value.set_index("period").loc["2025-01", "agrees"])
    with pytest.raises(FrameError, match="more than one"):
        fin.vat_settlement(vr, pd.concat([pay, pay.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="direction"):
        fin.vat_settlement(vr, pay.assign(direction="sideways"), context=M12)


def _prov(rows):
    cols = ["le_key", "fiscal_year", "tax_rate", "profit_before_tax", "non_deductible_expenses", "exempt_income", "temporary_difference_movement", "taxable_income_before_losses", "tax_loss_utilised",
            "tax_loss_added", "tax_loss_carried_forward", "taxable_income", "current_tax", "deferred_tax_movement", "total_tax_expense"]
    return pd.DataFrame(rows, columns=cols)


def test_tax_provision_recomputes_losses_carry_forward_and_utilisation():
    rows = [("LE-01", 2024, 0.22, -1000.0, 0.0, 0.0, 100.0, -1100.0, 0.0, 1100.0, 1100.0, 0.0, 0.0, -50.0, -50.0),
            ("LE-01", 2025, 0.22, 2000.0, 100.0, 200.0, -50.0, 1950.0, 1100.0, 0.0, 0.0, 850.0, 187.0, 30.0, 217.0),
            ("LE-02", 2025, 0.30, 100.0, 0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 100.0, 30.0, -5.0, 25.0)]
    r = fin.tax_provision(_prov(rows), context=M12)
    assert r.status == "VERIFY" and r.value.agrees.tolist() == [True, True, True] and r.value.rate_is_the_fact.all()
    v = r.value.set_index(["le_key", "fiscal_year"])
    assert v.loc[("LE-01", 2025), "tax_loss_utilised"] == 1100.0 and v.loc[("LE-01", 2025), "taxable_income"] == 850.0 and v.loc[("LE-01", 2025), "current_tax"] == 187.0
    bad = _prov(rows).assign(current_tax=lambda d: d.current_tax.where(d.index != 1, 190.0), total_tax_expense=lambda d: d.total_tax_expense.where(d.index != 1, 220.0))
    assert fin.tax_provision(bad, context=M12).value.agrees.tolist() == [True, False, True]
    assert not fin.tax_provision(_prov(rows).assign(tax_rate=[0.22, 0.22, 0.25]), context=M12).value.rate_is_the_fact.iloc[2], "0.25 is not the German rate fact"
    capped = _prov([("LE-01", 2024, 0.22, -1000.0, 0.0, 0.0, 0.0, -1000.0, 0.0, 1000.0, 1000.0, 0.0, 0.0, 0.0, 0.0), ("LE-01", 2025, 0.22, 300.0, 0.0, 0.0, 0.0, 300.0, 300.0, 0.0, 700.0, 0.0, 0.0, 0.0, 0.0)])
    assert fin.tax_provision(capped, context=M12).value.agrees.all(), "the cap share is 1.0: a loss is used up to the income, the rest is carried on"
    with pytest.raises(FrameError, match="more than one row"):
        fin.tax_provision(pd.concat([_prov(rows), _prov(rows).iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="null inputs"):
        fin.tax_provision(_prov(rows).assign(profit_before_tax=[np.nan, 1.0, 1.0]), context=M12)


def test_einvoice_share_and_gap():
    ci = pd.DataFrame({"le_key": ["LE-02"] * 6 + ["LE-01"], "cus_key": ["C1", "C1", "C2", "C3", "C3", "C2", "C9"], "counterpart_le_key": [None] * 5 + ["LE-01", None],
                       "invoice_date": ["2026-09-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-11-20", "2026-10-07", "2026-10-08"],
                       "invoice_format": ["pdf", "xrechnung", "pdf", "zugferd", "pdf", "pdf", "pdf"], "inv_key": [f"INV-{i}" for i in range(7)]})
    s = fin.einvoice_format_share(ci, context=M3).set_index("period")
    assert s.loc["2026-10", ["n_invoices", "n_structured", "share"]].tolist() == [3, 2, 0.6667] and s.loc["2026-09", "share"] == 0.0 and s.loc["2026-11", "n_invoices"] == 1, "intercompany and LE-01 invoices are left out"
    assert fin.einvoice_format_share(ci, le_key="LE-01", context=M3).share.tolist() == [0.0]
    with pytest.raises(FrameError, match="invoice_format"):
        fin.einvoice_format_share(ci.assign(invoice_format=ci.invoice_format.where(ci.index != 0, None)), context=M3)
    g = fin.einvoice_gap(ci, dt.date(2026, 11, 30), context=M3)
    v = g.value.set_index("cus_key")
    assert g.status == "VERIFY" and v.loc["C1", "n_pdf"] == 1 and v.loc["C3", ["n_pdf", "last_format"]].tolist() == [1, "pdf"] and v.loc["C2", "n_pdf"] == 1 and "C9" not in v.index
    assert v.days_to_mandatory.unique().tolist() == [32] and fin.einvoice_gap(ci, dt.date(2026, 11, 30), months=1, context=M3).value.cus_key.tolist() == ["C3"]
    with pytest.raises(FrameError, match="months"):
        fin.einvoice_gap(ci, dt.date(2026, 11, 30), months=0, context=M3)


def test_stage_registry_and_facade_for_vat_tax():
    reg = registry.registered()
    ids = {"vat_return_from_ledger", "vat_code_check", "vat_settlement", "vat_filing_calendar", "tax_provision", "einvoice_format_share", "einvoice_gap"}
    for n in ids:
        assert f"halvaro.finance.vat_tax.{n}" in reg and n in fin.__all__
    assert reg["halvaro.finance.vat_tax.vat_return_from_ledger"].sources[0].startswith("finance.") and "frep.vat.boxes.output_domestic.label" in reg["halvaro.finance.vat_tax.vat_return_from_ledger"].facts
    with pytest.raises(StageRefusal):
        fin.tax_provision(pd.DataFrame(), context=M3)


def test_settlement_default_matches_vat_refund_rows_as_incoming():
    vr = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "vat_payable": [-20.0], "settlement_difference": [0.0]})
    pay = pd.DataFrame({"le_key": ["LE-01"], "payment_date": [dt.date(2025, 2, 25)], "direction": ["incoming"], "amount": [20.0], "description": ["VAT refund"]})
    v = fin.vat_settlement(vr, pay, context=M12).value
    assert v.paid_signed.iloc[0] == -20.0 and bool(v.agrees.iloc[0]), "a refund is matched by the default descriptions"
    assert pd.isna(fin.vat_settlement(vr, pay, description="VAT payment", context=M12).value.agrees.iloc[0]), "one description only: the refund is not seen"


def test_non_unique_index_gives_the_same_result_and_unboxed_code_is_flagged():
    a, b = _ledger(), _ledger()
    both = pd.concat([a[a.le_key == "LE-01"], b[b.le_key == "LE-02"].reset_index(drop=True)])
    assert not both.index.is_unique
    r = fin.vat_return_from_ledger(both, context=M3).value
    assert len(r) == 4 and r.set_index(["le_key", "period"]).loc[("LE-02", "2025-02"), "total_output_vat"] == 190.0
    assert fin.vat_code_check(both.assign(source="ar"), context=M3).value.shape[0] >= 0
    odd = pd.concat([_ledger(), _lines([("LE-01", "GL-4710", "2025-01", -100.0, "DK0", 0.0, "DKK", "ar")])], ignore_index=True)
    v = fin.vat_code_check(odd, context=M3).value
    assert "code_in_no_box" in set(v.rule)


def test_tax_provision_refuses_when_the_provision_is_already_in_the_ledger(monkeypatch):
    import halvaro.finance.vat_tax as vt_mod
    real = vt_mod.fact
    def fake(fid, *a, **k):
        f = real(fid, *a, **k)
        return type(f)(**{**f.__dict__, "value": True}) if fid == "fin.corporate_tax.posted_in_ledger" else f
    monkeypatch.setattr(vt_mod, "fact", fake)
    tp = pd.DataFrame({c: [0.0] for c in vt_mod._TAX_COLS}).assign(le_key="LE-01", fiscal_year=2024, tax_rate=0.22)
    with pytest.raises(FrameError, match="twice"):
        fin.tax_provision(tp, context=M12)


def test_vat_code_check_lists_a_capped_number_of_rows_other_country_codes_and_missing_bases():
    many = _lines([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "DKK", "ar")] * 1 + [("LE-01", "GL-4710", "2025-01", -1.0, "DK25", 1000.0, "DKK", "ar")] * 60)
    v = fin.vat_code_check(many, context=M3).value
    assert (v.rule == "rate_mismatch").sum() == 50 and (v.rule == "rate_mismatch_not_listed").sum() == 1 and "10 further" in v[v.rule == "rate_mismatch_not_listed"].detail.iloc[0], "50 listed, then one row that says how many were left out"
    odd = _lines([("LE-01", "GL-4710", "2025-01", -190.0, "DE19", 1000.0, "DKK", "ar"), ("LE-02", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "EUR", "ar"), ("LE-02", "GL-4710", "2025-01", -190.0, "DE19", 1000.0, "EUR", "ar"),
                  ("LE-01", "GL-4710", "2025-01", -250.0, "DK25", np.nan, "DKK", "ar")])
    w = fin.vat_code_check(odd, context=M3).value
    assert (w.rule == "code_of_other_country").sum() == 2 and (w.rule == "missing_vat_base").sum() == 1
    assert fin.vat_code_check(_ledger().assign(source="ar"), context=M3).value.rule.isin(["code_of_other_country", "missing_vat_base"]).sum() == 0


def test_settlement_provision_and_einvoice_guards():
    vr = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "vat_payable": [150.0], "settlement_difference": [0.0]})
    pay = pd.DataFrame({"le_key": ["LE-01"], "payment_date": [dt.date(2025, 2, 25)], "direction": ["outgoing"], "amount": [150.0], "description": ["VAT payment"]})
    assert fin.vat_settlement(vr.assign(period=pd.PeriodIndex(["2025-01"], freq="M")), pay, context=M12).value.agrees.tolist() == [True], "a Period column is read as text"
    with pytest.raises(FrameError, match="no country"):
        fin.vat_settlement(vr.assign(le_key="LE-09"), pay, context=M12)
    with pytest.raises(FrameError, match="payment date"):
        fin.vat_settlement(vr, pay.assign(payment_date=[pd.NaT]), context=M12)
    with pytest.raises(FrameError, match="period"):
        fin.vat_settlement(vr.assign(period="2025-13"), pay, context=M12)
    ci = pd.DataFrame({"le_key": ["LE-02"] * 2, "invoice_date": ["2026-01-05", None], "invoice_format": ["pdf", "pdf"], "counterpart_le_key": [None, None]})
    with pytest.raises(FrameError, match="without a date"):
        fin.einvoice_format_share(ci, context=M12)
    with pytest.raises(FrameError, match="not a single text"):
        fin.einvoice_format_share(ci.iloc[:1], structured="pdf", context=M12)
    tp = pd.DataFrame({c: [0.0] for c in vt_mod_cols()}).assign(le_key=[None], fiscal_year=2024, tax_rate=0.22)
    with pytest.raises(FrameError, match="without le_key"):
        fin.tax_provision(tp, context=M12)


def vt_mod_cols():
    import halvaro.finance.vat_tax as vt_mod
    return vt_mod._TAX_COLS
