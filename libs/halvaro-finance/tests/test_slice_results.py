"""Typed results of the standard slice: the models match what the functions return, carry a description and a unit, and change nothing about the return values (issue #201, lane V, V3)."""
import dataclasses
import datetime as dt

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact
from halvaro.finance.results import RESULT_MODELS, UNITS, ColumnSpec
from halvaro.finance.vat_tax import _TAX_COLS
from test_reconcile import _recon_frames

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")


def _cash():
    return pd.DataFrame([{"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": w, "closing_cash": c, "closing_cash_p10": c - 30.0, "closing_cash_p90": c + 30.0, "minimum_cash_floor": 100.0,
                          "rcf_limit": 500.0, "rcf_drawn": 100.0, "rcf_available": 400.0, "headroom_to_floor": c - 100.0, "headroom_to_floor_p10": c - 130.0,
                          "floor_breach_risk": c - 30.0 < 100.0, "actual_closing_cash_ex_rcf": c + 10.0} for w, c in ((1, 700.0), (2, 110.0))])


def _lines():
    return pd.DataFrame([("LE-01", "GL-4710", "2025-01", -240.0, "DK25", 1000.0, "DKK", "ar"), ("LE-01", "GL-2510", "2025-01", 100.0, "DK25", 400.0, "DKK", "ap")],
                        columns=["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency", "source"])


def _frames():
    ret = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "vat_payable": [150.0], "settlement_difference": [0.0], "filing_due_date": [None]})
    pay = pd.DataFrame({"le_key": ["LE-01"], "payment_date": ["2025-02-25"], "direction": ["outgoing"], "amount": [150.0], "description": ["VAT payment"]})
    row = dict.fromkeys(_TAX_COLS, 0.0)
    row.update(le_key="LE-01", fiscal_year=2025, tax_rate=fact("frep.corporate_tax.DK.rate").value, profit_before_tax=1000.0)
    inv = pd.DataFrame({"le_key": "LE-02", "cus_key": ["CUS-1", "CUS-2"], "invoice_date": ["2025-03-03", "2025-03-04"], "invoice_format": ["pdf", "xrechnung"], "counterpart_le_key": [None, None]})
    fa = pd.DataFrame([{"le_key": "LE-01", "asset_class": "IT", "acquisition_date": dt.date(2023, 2, 10), "cost": 900.0, "useful_life_months": 3, "disposal_date": None,
                        "depreciation_method": "straight_line_monthly", "currency": "DKK"}])
    bb = pd.DataFrame({"le_key": "LE-01", "bank_account": "BA-1", "balance_date": ["2025-01-02"], "closing_balance": [1100.0], "currency": "DKK"})
    bpay = pd.DataFrame({"bank_account": ["BA-1"], "payment_date": ["2025-01-02"], "direction": ["incoming"], "amount": [100.0]})
    ba = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["BA-1"], "gl_key": ["GL-1200"]})
    ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1200"], "amount": [1000.0]})
    gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
    alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
    lpay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
    lob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0], "currency": ["DKK"],
                        "cus_key": [None], "sup_key": [None]})
    ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"], "gross_amount_le": 1000.0,
                       "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
    si = pd.DataFrame({"sinv_key": ["S1"], "le_key": "LE-01", "sup_key": "SUP-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"], "payable_amount_le": 500.0})
    items = fin.open_items_ar(ci, alloc, lpay, lob, gl, dt.date(2026, 6, 30), context=M3)
    cust = pd.DataFrame({"cus_key": ["CUS-1"], "credit_limit": [500.0], "currency": ["DKK"]})
    return {"liquidity_headroom": fin.liquidity_headroom(_cash(), context=M3), "forecast_accuracy": fin.forecast_accuracy(_cash(), context=M3),
            "vat_return_from_ledger": fin.vat_return_from_ledger(_lines(), context=M3).value, "vat_code_check": fin.vat_code_check(_lines(), context=M3).value,
            "vat_settlement": fin.vat_settlement(ret, pay, context=M12).value, "vat_filing_calendar": fin.vat_filing_calendar(ret, context=M12).value,
            "tax_provision": fin.tax_provision(pd.DataFrame([row]), context=M12).value, "einvoice_format_share": fin.einvoice_format_share(inv, context=M3),
            "einvoice_gap": fin.einvoice_gap(inv, dt.date(2025, 3, 31), context=M3).value, "fixed_asset_rollforward": fin.fixed_asset_rollforward(fa, context=M3).value,
            "bank_reconciliation": fin.bank_reconciliation(bb, bpay, ba, ob, context=M3),
            "open_items_ar": items, "open_items_ap": fin.open_items_ap(si, alloc, lpay, lob, gl, dt.date(2026, 6, 30), context=M3), "retention_receivable": fin.retention_receivable(items, context=M3),
            "ageing": fin.ageing(items, dt.date(2026, 6, 30), context=M3), "bad_debt_candidates": fin.bad_debt_candidates(items, dt.date(2026, 6, 30), context=M3).value,
            "customer_exposure": fin.customer_exposure(items[items["source"] == "invoice"], cust, context=M12), "rebuild_subledger_reconciliation": fin.rebuild_subledger_reconciliation(**_recon_frames(), context=M3)}


def test_every_model_field_has_a_description_and_a_unit_from_the_vocabulary():
    assert len(RESULT_MODELS) == 21
    for name, model in RESULT_MODELS.items():
        specs = model.columns()
        assert specs and all(isinstance(c, ColumnSpec) for c in specs), name
        for c in specs:
            assert c.description.strip() and c.description.strip().endswith("."), f"{name}.{c.name}: description"
            assert c.unit in UNITS, f"{name}.{c.name}: unit {c.unit!r}"
        assert len({c.name for c in specs}) == len(specs)


def test_the_columns_of_each_frame_are_the_fields_of_its_model_in_order():
    for name, frame in _frames().items():
        assert list(frame.columns) == [c.name for c in RESULT_MODELS[name].columns()], name


def test_the_violation_model_fits_the_frame_of_the_four_check_functions():
    assert [c.name for c in fin.ViolationRow.columns()] == ["table", "key", "rule", "detail"]
    rows = fin.ViolationRow.from_frame(_frames()["vat_code_check"])
    assert [r.rule for r in rows] == ["rate_mismatch"] and rows[0].table == "finance.journal_line"


def test_from_frame_gives_one_frozen_model_per_row_and_turns_missing_values_into_none():
    f = _frames()
    head = fin.HeadroomRow.from_frame(f["liquidity_headroom"])
    assert len(head) == 1 and head[0].weeks == 2 and head[0].first_breach_week == 2 and head[0].agrees is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        head[0].weeks = 3                                                          # type: ignore[misc]
    vr = fin.VatReturnRow.from_frame(f["vat_return_from_ledger"])[0]
    assert vr.vat_payable == 140.0 and vr.currency == "DKK"
    assert fin.FilingDateRow.from_frame(f["vat_filing_calendar"])[0].stored_due_date is None
    assert fin.SubledgerReconciliationRow.from_frame(f["rebuild_subledger_reconciliation"])


def test_from_frame_names_the_missing_column():
    with pytest.raises(FrameError, match="lacks column"):
        fin.VatReturnRow.from_frame(_frames()["vat_return_from_ledger"].drop(columns="vat_payable"))


def test_the_functions_still_return_what_they_returned_before():
    f = _frames()
    assert all(isinstance(v, pd.DataFrame) for v in f.values())
    assert type(fin.vat_return_from_ledger(_lines(), context=M3)).__name__ == "Envelope"
