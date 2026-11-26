"""Exposure part 1: three-way match, price variance report, finance exposure, spend, approval limits. Synthetic cases."""

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")


def _lines(rows):
    """rows: (quantity, unit_price, po_unit_price, qty_accepted, invoice_type, stored_status, stored_variance)."""
    n = len(rows)
    sl = pd.DataFrame({"sinv_key": [f"SINV-{i:06d}" for i in range(n)], "line_no": 1, "po_key": [f"PO-{i:06d}" if r[2] is not None else None for i, r in enumerate(rows)],
                       "po_line_no": pd.array([1 if r[2] is not None else -1 for r in rows], dtype="Int64"), "receipt_no": pd.array([1 if r[2] is not None else None for r in rows], dtype="Int64"),
                       "quantity": [r[0] for r in rows], "unit_price": [r[1] for r in rows], "po_unit_price": [r[2] if r[2] is not None else np.nan for r in rows], "invoice_type": [r[4] for r in rows],
                       "match_status": [r[5] for r in rows], "price_variance": [r[6] for r in rows]})
    gr = pd.DataFrame({"po_key": [f"PO-{i:06d}" for i, r in enumerate(rows) if r[2] is not None], "line_no": 1, "receipt_no": 1, "qty_accepted": [r[3] for r in rows if r[2] is not None]})
    return sl, gr


CASES = [(10.0, 100.0, 100.0, 10.0, "invoice", "matched", 0.0),                 # matched
         (10.0, 101.5, 100.0, 10.0, "invoice", "price_variance", 15.0),         # price only
         (12.0, 100.0, 100.0, 10.0, "invoice", "quantity_variance", 0.0),       # quantity only
         (12.0, 101.0, 100.0, 10.0, "invoice", "quantity_variance", 12.0),      # both: quantity wins, the price variance is still computed
         (3.0, 100.0, 100.0, 10.0, "credit_note", "credit_for_rejected_goods", 0.0),
         (1.0, 50.0, None, None, "invoice", "non_po", 0.0)]


def test_status_follows_quantity_first_then_price_then_matched():
    sl, gr = _lines(CASES)
    t = fin.three_way_match(sl, gr, context=M12)
    assert t.status.tolist() == ["matched", "price_variance", "quantity_variance", "quantity_variance", "credit_for_rejected_goods", "non_po"]
    assert t.price_variance.tolist() == [0.0, 15.0, 0.0, 12.0, 0.0, 0.0] and t.agrees.all() and t.price_diff_percent.iloc[1] == 1.5 and np.isnan(t.price_diff_percent.iloc[5])
    assert list(t.columns) == ["sinv_key", "line_no", "po_key", "status", "price_variance", "price_diff_percent", "stored_status", "stored_price_variance", "agrees"]


def test_the_tolerance_is_a_parameter_and_the_stored_values_are_compared():
    sl, gr = _lines(CASES)
    assert fin.three_way_match(sl, gr, price_tolerance_percent=2.0, context=M12).status.iloc[1] == "matched", "1.5 percent inside a 2 percent tolerance"
    assert fin.three_way_match(sl, gr, price_tolerance_percent=1.5, context=M12).status.iloc[1] == "matched", "the tolerance itself is inside"
    assert fin.three_way_match(sl, gr, price_tolerance_percent=1.4, context=M12).status.iloc[1] == "price_variance"
    bad = sl.assign(match_status=["matched", "matched", "matched", "price_variance", "credit_for_rejected_goods", "non_po"], price_variance=[0.0, 15.0, 0.0, 12.01, 0.0, 0.0])
    t = fin.three_way_match(bad, gr, context=M12)
    assert t.agrees.tolist() == [True, False, False, False, True, True]
    for tol in (-1, None, True, "2"):
        with pytest.raises(FrameError, match="price_tolerance_percent"):
            fin.three_way_match(sl, gr, price_tolerance_percent=tol, context=M12)


def test_three_way_match_tolerance_boundary_is_not_decided_by_float_noise():
    rows = [(10, price, po, 10, "invoice", "matched", 0.0) for po, price in ((0.50, 0.51), (1.00, 1.02), (1.50, 1.53), (0.50, 0.511))]
    sl, gr = _lines(rows)
    t = fin.three_way_match(sl, gr, price_tolerance_percent=2.0, context=M12)
    assert t.status.tolist() == ["matched", "matched", "matched", "price_variance"], "2 percent exactly is inside the tolerance whatever the float noise; 2.2 percent is not"


def test_three_way_match_refuses_missing_receipts_and_duplicate_receipts():
    sl, gr = _lines(CASES)
    with pytest.raises(FrameError, match="no goods receipt.*SINV-000000"):
        fin.three_way_match(sl, gr.iloc[1:], context=M12)
    with pytest.raises(FrameError, match="duplicate"):
        fin.three_way_match(sl, pd.concat([gr, gr.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="lacks column.*qty_accepted"):
        fin.three_way_match(sl, gr.drop(columns="qty_accepted"), context=M12)
    assert fin.three_way_match(sl.iloc[:0], gr.iloc[:0], context=M12).empty
    shuffled = sl.sample(frac=1, random_state=3)
    assert fin.three_way_match(shuffled, gr, context=M12).status.tolist() == fin.three_way_match(sl, gr, context=M12).status.iloc[shuffled.index].tolist()


def test_review_cases_credit_precedence_signs_zero_prices_nulls_and_duplicates():
    one = lambda row: fin.three_way_match(*_lines([row]), context=M12).iloc[0]
    c = one((15.0, 120.0, 100.0, 10.0, "credit_note", "credit_for_rejected_goods", 0.0))
    assert c.status == "credit_for_rejected_goods" and c.price_variance == 0.0, "a credit note with excess quantity and a price difference stays a credit and carries no variance"
    sl, gr = _lines([(10.0, 120.0, 100.0, 10.0, "credit_note", "credit_for_rejected_goods", 0.0)])
    assert fin.three_way_match(sl, gr.iloc[:0], context=M12).status.tolist() == ["credit_for_rejected_goods"], "a credit note needs no receipt"
    neg = one((10.0, 90.0, 100.0, 10.0, "invoice", "price_variance", -100.0))
    assert neg.status == "price_variance" and neg.price_variance == -100.0 and neg.price_diff_percent == -10.0
    zero = one((10.0, 5.0, 0.0, 10.0, "invoice", "price_variance", 50.0))
    assert zero.status == "price_variance" and zero.price_variance == 50.0 and np.isnan(zero.price_diff_percent), "a PO price of 0 has no percentage: any difference is off, at any tolerance"
    assert fin.three_way_match(*_lines([(10.0, 5.0, 0.0, 10.0, "invoice", "price_variance", 50.0)]), price_tolerance_percent=50.0, context=M12).status.tolist() == ["price_variance"]
    bad = one((10.0, 100.01, 100.0, 10.0, "invoice", "price_variance", 0.1))
    assert bad.status == "price_variance" and bad.agrees, "0.1 stored against 0.10 recomputed"
    off_by = one((10.0, 100.01, 100.0, 10.0, "invoice", "price_variance", 0.11))
    assert off_by.status == "price_variance" and not off_by.agrees, "a variance 0.01 away, with the same status, disagrees"
    frac = one((3.0, 100.333, 100.0, 3.0, "invoice", "price_variance", 1.0))
    assert frac.price_variance == 1.0, "rounded to the cent"
    for kw in ({"quantity": np.nan}, {"unit_price": np.nan}):
        sl, gr = _lines([(10.0, 100.0, 100.0, 10.0, "invoice", "matched", 0.0)])
        with pytest.raises(FrameError, match="null"):
            fin.three_way_match(sl.assign(**kw), gr, context=M12)
    sl, gr = _lines(CASES)
    with pytest.raises(FrameError, match="more than one row"):
        fin.three_way_match(pd.concat([sl, sl.iloc[:1]]), gr, context=M12)
    for bad_tol in (np.nan, np.inf, -1.0, True, "2"):
        with pytest.raises(FrameError, match="price_tolerance_percent"):
            fin.three_way_match(sl, gr, price_tolerance_percent=bad_tol, context=M12)


def _report_frames():
    sl = pd.DataFrame({"sinv_key": ["S1", "S2", "S3", "S4", "S5"], "itm_key": ["I1", "I1", "I2", "I1", "I1"], "unit_price": [101.0, 99.0, 118.0, 100.0, 50.0], "po_unit_price": [100.0, 100.0, 100.0, 100.0, np.nan],
                       "price_variance": [10.0, -10.0, 180.0, 0.0, 0.0], "currency": "DKK", "invoice_type": ["invoice", "invoice", "invoice", "credit_note", "invoice"]})
    si = pd.DataFrame({"sinv_key": ["S1", "S2", "S3", "S4", "S5"], "sup_key": ["SUP-1", "SUP-1", "SUP-2", "SUP-1", "SUP-1"]})
    return sl, si


def test_price_variance_report_by_supplier_and_item_and_the_step():
    sl, si = _report_frames()
    r = fin.price_variance_report(sl, si, context=M3)
    assert r[["sup_key", "itm_key", "n_lines"]].values.tolist() == [["SUP-1", "I1", 2], ["SUP-2", "I2", 1]], "credit notes and non-PO lines are left out"
    a = r.iloc[0]
    assert a.price_variance == 0.0 and a.mean_diff_percent == 0.0 and round(a.sd_diff_percent, 6) == round(float(np.std([1.0, -1.0], ddof=1)), 6) and a.max_abs_diff_percent == 1.0
    steps = pd.DataFrame({"sup_key": ["SUP-1", "SUP-2"], "itm_key": ["I1", "I2"], "step_percent": [18.0, 18.0]})
    s = fin.price_variance_report(sl, si, price_steps=steps, context=M3)
    assert s.step_in_variance.tolist() == [False, True] and s.step_percent.tolist() == [18.0, 18.0], "18 percent in the invoice price would be a variance; noise is not"
    with pytest.raises(FrameError, match="not in finance.supplier_invoice"):
        fin.price_variance_report(sl, si.iloc[1:], context=M3)
    with pytest.raises(FrameError, match="duplicate sinv_key"):
        fin.price_variance_report(sl, pd.concat([si, si.iloc[:1]]), context=M3)


def test_review_cases_report_steps_nulls_and_spend_dates():
    sl, si = _report_frames()
    steps = lambda *rows: pd.DataFrame(rows, columns=["sup_key", "itm_key", "step_percent"])
    r = fin.price_variance_report(sl, si, price_steps=steps(("SUP-1", "I1", 18.0), ("SUP-2", "I2", 36.0), ("SUP-9", "I9", -18.0)), context=M12).set_index(["sup_key", "itm_key"])
    assert r.loc[("SUP-2", "I2"), "mean_diff_percent"] == 18.0 and bool(r.loc[("SUP-2", "I2"), "step_in_variance"]) and not bool(r.loc[("SUP-1", "I1"), "step_in_variance"])
    for step, mean_hits in ((36.0, True), (36.01, False)):
        assert bool(fin.price_variance_report(sl, si, price_steps=steps(("SUP-2", "I2", step)), context=M12).set_index("sup_key").loc["SUP-2", "step_in_variance"]) is mean_hits, "half the step is reached, not exceeded"
    neg = fin.price_variance_report(sl, si, price_steps=steps(("SUP-1", "I1", -18.0)), context=M12).set_index("sup_key")
    assert not bool(neg.loc["SUP-1", "step_in_variance"]), "a negative step is compared by its size"
    with pytest.raises(FrameError, match="more than one row"):
        fin.price_variance_report(sl, si, price_steps=steps(("SUP-1", "I1", 1.0), ("SUP-1", "I1", 2.0)), context=M12)
    with pytest.raises(FrameError, match="PO price of 0"):
        fin.price_variance_report(sl.assign(po_unit_price=[0.0] + [100.0] * 4), si, context=M12)
    with pytest.raises(FrameError, match="itm_key and a currency"):
        fin.price_variance_report(sl.assign(itm_key=[None] + ["I1"] * 4), si, context=M12)
    inv = pd.DataFrame({"sinv_key": ["A", "B"], "sup_key": "SUP-1", "invoice_type": "invoice", "invoice_date": ["2025-01-05", "2025-01-06"], "net_amount_dkk": [10.0, 20.0]})
    sup = pd.DataFrame({"sup_key": ["SUP-1"], "category": "cable"})
    assert fin.supplier_spend(inv, sup, "2025-01-05", "2025-01-06", context=M12).spend_dkk.tolist() == [30.0]
    for args in ((2023, "2025-01-06"), (None, "2025-01-06"), ("2025-01-05", pd.Timestamp("2025-01-06", tz="UTC"))):
        with pytest.raises(Exception, match="date|time zone|number"):
            fin.supplier_spend(inv, sup, *args, context=M12)
    with pytest.raises(FrameError, match="duplicate sinv_key"):
        fin.supplier_spend(pd.concat([inv, inv.iloc[:1]]), sup, "2025-01-01", "2025-12-31", context=M12)


def test_finance_exposure_lists_only_projects_with_an_exposure_in_dkk():
    eur = fact("world.fx_eur_dkk_fixed").value
    pf = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P1"], "period": ["2026-11", "2026-11", "2026-11", "2026-10"], "currency": ["EUR", "DKK", "DKK", "EUR"],
                       "price_exposure": [1000.0, 500.0, 0.0, 400.0], "price_recoverable": [0.0, 250.0, 0.0, 0.0]})
    e = fin.finance_exposure(pf, "2026-11", context=M3)
    assert e.prj_key.tolist() == ["P1", "P2"] and e.price_exposure_dkk.tolist() == [round(1000 * eur, 2), 500.0] and e.price_recoverable_dkk.tolist() == [0.0, 250.0]
    assert fin.finance_exposure(pf, "2026-10", context=M3).price_exposure.tolist() == [400.0] and fin.finance_exposure(pf, "2026-01", context=M3).empty
    with pytest.raises(FrameError, match="more than one row"):
        fin.finance_exposure(pd.concat([pf, pf.iloc[:1]]), "2026-11", context=M3)


def test_supplier_spend_window_credit_notes_and_missing_suppliers():
    si = pd.DataFrame({"sup_key": ["SUP-1", "SUP-1", "SUP-2", "SUP-1"], "invoice_type": ["invoice", "credit_note", "invoice", "invoice"], "invoice_date": pd.to_datetime(["2023-01-01", "2023-01-31", "2023-02-01", "2023-02-02"]),
                       "net_amount_dkk": [100.0, 30.0, 70.0, 5.0]})
    sup = pd.DataFrame({"sup_key": ["SUP-1", "SUP-2"], "category": ["cable", "switchgear"]})
    s = fin.supplier_spend(si, sup, "2023-01-01", "2023-01-31", context=M12)
    assert s.values.tolist() == [["SUP-1", "cable", 2, 70.0]], "both boundary days count, the credit note is negative"
    assert fin.supplier_spend(si, sup, "2023-01-01", "2023-12-31", context=M12).spend_dkk.sum() == 145.0
    with pytest.raises(FrameError, match="after end"):
        fin.supplier_spend(si, sup, "2023-02-01", "2023-01-01", context=M12)
    with pytest.raises(FrameError, match="not in procurement.supplier.*SUP-1"):
        fin.supplier_spend(si, sup.iloc[1:], "2023-01-01", "2023-12-31", context=M12)


def test_approval_limit_breaches_by_grade_and_currency():
    eur = fact("world.fx_eur_dkk_fixed").value
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3", "PO-4", "PO-5"], "buyer_emp_key": "EMP-1", "order_date": "2025-01-01", "currency": ["DKK", "DKK", "EUR", "DKK", "DKK"],
                       "total_value": [50000.0, 50000.01, 40000.0, 250000.0, 1000000.01]})
    g = pd.DataFrame({"po_key": po.po_key, "grade_level": [3, 3, 3, 5, 6]})
    r = fin.approval_limit_breaches(po, g, context=M12)
    assert r.breach.tolist() == [False, True, True, False, True] and r.limit_dkk.tolist() == [50000.0, 50000.0, 50000.0, 250000.0, 1000000.0]
    assert r.total_value_dkk.tolist()[2] == round(40000 * eur, 2)
    sek = fact("world.fx_sek_dkk_fixed").value
    rs = fin.approval_limit_breaches(po.iloc[:1].assign(po_key="PO-S", currency="SEK", total_value=10000.0), g.iloc[:1].assign(po_key="PO-S"), context=M12)
    assert rs.total_value_dkk.tolist() == [round(10000 * sek, 2)], "SEK converts at the fixed booking rate, not at a group payment rate"
    assert fin.approval_limit_breaches(po, g.assign(grade_level=1), limits=((1, 10.0), (None, 1e9)), context=M12).breach.all()
    for bad in ([], [(3, 1.0)], [(5, 1.0), (3, 2.0), (None, 3.0)], [(None, 1.0), (None, 2.0)]):
        with pytest.raises(FrameError, match="limits is a list"):
            fin.approval_limit_breaches(po, g, limits=bad, context=M12)
    with pytest.raises(FrameError, match="no buyer grade.*PO-1"):
        fin.approval_limit_breaches(po, g.iloc[1:], context=M12)
    with pytest.raises(FrameError, match="unique"):
        fin.approval_limit_breaches(po, pd.concat([g, g.iloc[:1]]), context=M12)
