"""Subledgers part c: open items, retention, ageing, bad debt candidates and customer exposure. Synthetic frames with hand computed values, then the baseline release against the stored reconciliation rows."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, PeriodError, StageRefusal, fact

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")
D = dt.date


def _gl():
    return pd.DataFrame({"gl_key": ["GL-1000", "GL-2200", "GL-2210", "GL-4300"], "control_type": [None, "ar", "retention", "ap"]})


def _pay(rows):
    """rows: (payment_no, payment_date)."""
    return pd.DataFrame({"le_key": "LE-01", "bank_account": "B", "payment_no": [r[0] for r in rows], "payment_date": [r[1] for r in rows]})


def _alloc(rows):
    """rows: (payment_no, kind, document_type, key, amount)."""
    return pd.DataFrame({"le_key": "LE-01", "bank_account": "B", "payment_no": [r[0] for r in rows], "alloc_no": 1, "allocation_kind": [r[1] for r in rows], "document_type": [r[2] for r in rows],
                         "inv_key": [r[3] if r[1] in ("inv", "inv_ret") else None for r in rows], "sinv_key": [r[3] if r[1] == "sinv" else None for r in rows],
                         "opening_item_ref": [r[3] if r[1].startswith("open") else None for r in rows], "booked_amount": [float(r[4]) for r in rows]})


def _ob(rows):
    """rows: (gl_key, item_ref, amount, due_date)."""
    return pd.DataFrame({"le_key": "LE-01", "gl_key": [r[0] for r in rows], "item_ref": [r[1] for r in rows], "document_date": D(2022, 12, 1), "due_date": [r[3] for r in rows],
                         "amount": [float(r[2]) for r in rows], "currency": "DKK", "cus_key": "CUS-9", "sup_key": "SUP-9"})


def _ci():
    cols = ["inv_key", "le_key", "cus_key", "invoice_type", "invoice_date", "due_date", "gross_amount_le", "retention_amount_le", "retention_release_date", "written_off_date", "counterpart_le_key"]
    rows = [("INV-000001", "LE-01", "CUS-1", "invoice", D(2023, 1, 10), D(2023, 2, 9), 1000, 100, D(2023, 6, 30), None, None),
            ("INV-000002", "LE-01", "CUS-1", "credit_note", D(2023, 1, 15), D(2023, 2, 14), 200, 0, None, None, None),
            ("INV-000003", "LE-01", None, "invoice", D(2023, 1, 16), D(2023, 2, 15), 999, 0, None, None, "LE-02"),
            ("INV-000004", "LE-01", "CUS-2", "invoice", D(2023, 2, 1), D(2023, 3, 3), 500, 0, None, D(2023, 3, 15), None),
            ("INV-000005", "LE-01", "CUS-2", "invoice", D(2023, 1, 20), D(2023, 2, 19), 800, 80, D(2023, 4, 1), None, None)]
    return pd.DataFrame(rows, columns=cols)


def _ar_inputs():
    pay = _pay([(1, D(2023, 2, 20)), (2, D(2023, 3, 10)), (3, D(2023, 4, 5)), (4, D(2023, 2, 25))])
    al = _alloc([(1, "inv", "invoice", "INV-000001", 400), (2, "inv", "invoice", "INV-000005", 720), (3, "inv_ret", "invoice", "INV-000005", 80), (4, "open_ar", "invoice", "OB/AR/00001", 300)])
    ob = _ob([("GL-2200", "OB/AR/00001", 300, D(2023, 1, 12)), ("GL-2210", "OB/RET/00001", 50, D(2023, 6, 1))])
    return _ci(), al, pay, ob, _gl()


def _ar(as_of):
    ci, al, pay, ob, gl = _ar_inputs()
    return fin.open_items_ar(ci, al, pay, ob, gl, as_of, context=M3).set_index("item_key")


def test_open_items_ar_by_payment_date_with_credit_notes_write_off_retention_and_opening_items():
    x = _ar(D(2023, 3, 31))
    assert list(x.columns) == ["source", "le_key", "cus_key", "inv_key", "document_date", "due_date", "currency", "invoice_amount", "paid", "written_off", "open_amount", "retention_held", "release_date"]
    assert x.loc["INV-000001", ["invoice_amount", "paid", "open_amount", "retention_held"]].tolist() == [1000, 400, 600, 100]
    assert x.loc["INV-000002", ["invoice_amount", "open_amount"]].tolist() == [-200, -200], "a credit note is negative"
    assert "INV-000003" not in x.index, "intercompany invoices are not receivables"
    assert x.loc["INV-000004", ["written_off", "open_amount"]].tolist() == [500, 0]
    assert x.loc["INV-000005", ["paid", "open_amount", "retention_held"]].tolist() == [720, 80, 80], "the retention payment of 5 April is after the date"
    assert x.loc["OB/AR/00001", ["source", "open_amount"]].tolist() == ["opening", 0] and x.loc["OB/RET/00001", ["open_amount", "retention_held"]].tolist() == [50, 50]
    assert (x.open_amount.sum(), x.retention_held.sum()) == (530, 230) and set(x.currency) == {"DKK"}


def test_open_items_ar_day_boundaries():
    assert "INV-000001" not in _ar(D(2023, 1, 9)).index and "INV-000001" in _ar(D(2023, 1, 10)).index, "an invoice dated on the date is open on it"
    assert _ar(D(2023, 2, 20)).loc["INV-000001", "paid"] == 400 and _ar(D(2023, 2, 19)).loc["INV-000001", "paid"] == 0, "a payment on the date counts"
    assert _ar(D(2023, 3, 15)).loc["INV-000004", "open_amount"] == 0 and _ar(D(2023, 3, 14)).loc["INV-000004", "open_amount"] == 500, "write off on the date counts"
    late = _ar(D(2023, 4, 5)).loc["INV-000005"]
    assert (late.open_amount, late.retention_held) == (0, 0), "paid in full and released on the release date"
    assert _ar(D(2023, 3, 31)).loc["INV-000005", "retention_held"] == 80 and _ar(D(2023, 4, 1)).loc["INV-000005", "retention_held"] == 0, "released on the release date of a collected retention"
    assert _ar(D(2023, 5, 31)).loc["INV-000001", "retention_held"] == 100, "a retention never collected stays held, whatever its release date"
    assert _ar(D(2023, 5, 31)).loc["OB/RET/00001", "retention_held"] == 50 and _ar(D(2023, 6, 1)).loc["OB/RET/00001", "retention_held"] == 0
    only_opening = _ar(D(2022, 12, 31))
    assert only_opening.index.tolist() == ["OB/AR/00001", "OB/RET/00001"] and only_opening.open_amount.tolist() == [300, 50]


def test_open_items_ar_refuses_bad_input():
    ci, al, pay, ob, gl = _ar_inputs()
    with pytest.raises(FrameError, match="no account with control_type 'retention'"):
        fin.open_items_ar(ci, al, pay, ob, gl.assign(control_type=["x", "ar", "x", "ap"]), D(2023, 3, 31), context=M3)
    with pytest.raises(FrameError, match="name a payment that is not in finance.payment"):
        fin.open_items_ar(ci, al, pay.iloc[1:], ob, gl, D(2023, 3, 31), context=M3)
    with pytest.raises(PeriodError):
        fin.open_items_ar(ci, al, pay, ob, gl, "junk", context=M3)
    with pytest.raises(FrameError, match="lacks column.*written_off_date"):
        fin.open_items_ar(ci.drop(columns="written_off_date"), al, pay, ob, gl, D(2023, 3, 31), context=M3)
    assert ci.invoice_date.tolist()[0] == D(2023, 1, 10), "the input is not changed"


def _ap_inputs():
    si = pd.DataFrame({"sinv_key": ["SINV-000001", "SINV-000002"], "le_key": "LE-01", "sup_key": ["SUP-1", "SUP-2"], "invoice_type": ["invoice", "credit_note"], "invoice_date": [D(2023, 1, 5), D(2023, 1, 10)],
                       "due_date": [D(2023, 2, 4), D(2023, 2, 9)], "payable_amount_le": [1000.0, 100.0]})
    pay = _pay([(5, D(2023, 2, 10)), (6, D(2023, 3, 1))])
    al = _alloc([(5, "sinv", "invoice", "SINV-000001", 600), (6, "open_ap", "invoice", "OB/AP/00001", 150)])
    ob = _ob([("GL-4300", "OB/AP/00001", -400, D(2023, 1, 20))])
    return si, al, pay, ob, _gl()


def test_open_items_ap_owed_positive_credit_notes_negative_opening_items_and_payment_dates():
    si, al, pay, ob, gl = _ap_inputs()
    f = lambda d: fin.open_items_ap(si, al, pay, ob, gl, d, context=M3).set_index("item_key")
    x = f(D(2023, 2, 28))
    assert x.loc["SINV-000001", ["payable_amount_le", "paid", "open_amount"]].tolist() == [1000, 600, 400] and x.loc["SINV-000002", "open_amount"] == -100 and x.loc["OB/AP/00001", "open_amount"] == 400
    assert f(D(2023, 3, 1)).loc["OB/AP/00001", "open_amount"] == 250 and f(D(2023, 2, 28)).open_amount.sum() == 700
    assert f(D(2023, 2, 9)).loc["SINV-000001", "open_amount"] == 1000 and f(D(2023, 2, 10)).loc["SINV-000001", "open_amount"] == 400, "paid on the date counts"
    assert f(D(2023, 1, 4)).index.tolist() == ["OB/AP/00001"]


def test_retention_receivable_lists_held_items_and_the_entity_total():
    ci, al, pay, ob, gl = _ar_inputs()
    r = fin.retention_receivable(fin.open_items_ar(ci, al, pay, ob, gl, D(2023, 3, 31), context=M3), context=M3)
    held = r[r.source != "total"]
    assert held.item_key.tolist() == ["INV-000001", "INV-000005", "OB/RET/00001"] and held.retention_held.tolist() == [100, 80, 50]
    assert pd.to_datetime(held.release_date).tolist() == [pd.Timestamp(2023, 6, 30), pd.Timestamp(2023, 4, 1), pd.Timestamp(2023, 6, 1)], "invoice release dates, the due date for an opening item"
    tot = r[r.source == "total"]
    assert tot.retention_held.tolist() == [230] and tot.le_key.tolist() == ["LE-01"]


def _items(rows):
    return pd.DataFrame({"item_key": [f"I{i}" for i in range(len(rows))], "le_key": "LE-01", "cus_key": [r[0] for r in rows], "due_date": [r[1] for r in rows], "open_amount": [float(r[2]) for r in rows]})


def test_ageing_buckets_boundaries_and_totals():
    d = D(2023, 6, 30)
    x = _items([("C1", D(2023, 7, 1), 10), ("C1", D(2023, 6, 30), 20), ("C1", D(2023, 5, 31), 30), ("C1", D(2023, 5, 30), 40), ("C1", D(2023, 4, 30), 50),
                ("C1", D(2023, 4, 1), 60), ("C1", D(2023, 3, 31), 70), ("C1", None, 5), ("C2", D(2022, 1, 1), 100), ("C2", D(2023, 6, 1), 0)])
    a = fin.ageing(x, d, context=M3)
    got = a[a.cus_key == "C1"].set_index("bucket").amount.to_dict()
    assert got == {"not_due": 30.0, "1-30": 30.0, "31-60": 40.0, "61-90": 110.0, "over_90": 70.0, "no_due_date": 5.0}, "0 days late is not due, 30 is the first bucket's last day, 90 the third's"
    assert a.amount.sum() == x.open_amount.sum() and a[a.cus_key == "C2"].bucket.tolist() == ["over_90"] and a[a.cus_key == "C2"].n_items.tolist() == [1], "zero items are left out"
    assert a.bucket.tolist()[:3] == ["not_due", "1-30", "31-60"], "buckets keep their order"
    b = fin.ageing(x, d, buckets=(0, 10, 100), context=M3)
    assert set(b.bucket) == {"not_due", "11-100", "over_100", "no_due_date"} and b.amount.sum() == x.open_amount.sum()
    for bad in ((30, 60), (0, 60, 30), (0, 0, 30), (-1, 5)):
        with pytest.raises(FrameError, match="increasing days past due"):
            fin.ageing(x, d, buckets=bad, context=M3)
    ap = x.rename(columns={"cus_key": "sup_key"})
    assert fin.ageing(ap, d, party="sup_key", context=M3).amount.sum() == x.open_amount.sum()
    assert fin.ageing(x.iloc[:0], d, context=M3).empty
    with pytest.raises(FrameError, match="increasing days past due"):
        fin.ageing(x, d, buckets=(), context=M3)
    nokey = x.assign(cus_key=[None] + list(x.cus_key[1:]))
    assert round(fin.ageing(nokey, d, context=M3).amount.sum(), 2) == round(x.open_amount.sum(), 2), "items without a party still add up to the total"


def test_bad_debt_candidates_use_the_fact_and_carry_its_status():
    days = fact("fin.payment.bad_debt_write_off_after_days_overdue").value
    d = D(2024, 12, 31)
    due = lambda n: pd.Timestamp(d) - pd.Timedelta(days=int(n))
    x = _items([("C1", due(days), 10), ("C1", due(days + 1), 20), ("C2", due(days + 400), -5), ("C2", due(days + 400), 7), ("C3", due(5), 99)])
    env = fin.bad_debt_candidates(x, d, context=M3)
    assert env.value.item_key.tolist() == ["I3", "I1", "I0"] and env.value.open_amount.tolist() == [7.0, 20.0, 10.0], "overdue for the fact's days or more, owed to us, longest first"
    assert env.value.days_past_due.tolist() == [days + 400, days + 1, days] and env.status == "VERIFY" and env.facts_used[0][1] == days
    on_the_day = fin.bad_debt_candidates(_items([("C1", due(days), 10), ("C1", due(days - 1), 10)]), d, context=M3).value
    assert on_the_day.days_past_due.tolist() == [days], "the day the generator writes off is a candidate, the day before is not"


def test_customer_exposure_converts_to_dkk_and_needs_month12():
    eur = fact("world.fx_eur_dkk_fixed").value
    items = pd.DataFrame({"le_key": ["LE-01", "LE-02", "LE-02", "LE-01"], "cus_key": ["C1", "C2", "C2", None], "open_amount": [500.0, 100.0, 50.0, 7.0], "currency": ["DKK", "EUR", "EUR", "DKK"]})
    cust = pd.DataFrame({"cus_key": ["C1", "C2", "C3"], "credit_limit": [400.0, 1000.0, 5.0], "currency": ["DKK", "EUR", "DKK"]})
    x = fin.customer_exposure(items, cust, context=M12).set_index("cus_key")
    assert x.loc["C1", ["open_dkk", "limit_dkk", "over_limit"]].tolist() == [500.0, 400.0, True]
    assert x.loc["C2", "open_dkk"] == round(150 * eur, 2) and x.loc["C2", "limit_dkk"] == round(1000 * eur, 2) and not x.loc["C2", "over_limit"] and x.loc["C3", "open_dkk"] == 0
    assert abs(x.loc["C2", "utilisation"] - 150 / 1000) < 1e-9
    nolimit = fin.customer_exposure(items, cust.assign(credit_limit=[400.0, np.nan, 5.0]), context=M12).set_index("cus_key")
    assert pd.isna(nolimit.loc["C2", "limit_dkk"]) and not nolimit.loc["C2", "over_limit"] and nolimit.loc["C1", "over_limit"]
    with pytest.raises(StageRefusal, match="crm"):
        fin.customer_exposure(items, cust, context=M3)
    with pytest.raises(FrameError, match="not in crm.customer.*C9"):
        fin.customer_exposure(items.assign(cus_key=["C9", "C2", "C2", None]), cust, context=M12)
    with pytest.raises(FrameError, match="duplicate cus_key"):
        fin.customer_exposure(items, pd.concat([cust, cust]), context=M12)
