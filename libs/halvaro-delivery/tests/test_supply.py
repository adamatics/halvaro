"""stock_on, reserved_demand, open_po_lines, exposed_demand, spot_orders: synthetic boundaries, then the baseline against the generator tests (plan oracles O13 to O16, O31)."""
import datetime as dt
import time

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.delivery import supply as _sup
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")
D = dt.date
NOW = D(2026, 11, 30)


def _mv(rows):
    return pd.DataFrame(rows, columns=["site_key", "itm_key", "movement_date", "movement_type", "qty", "prj_key", "reservation_no"])


def _mrow(site, itm, d, qty, typ="receipt", prj=None, res=None):
    return (site, itm, d, typ, qty, prj, res)


def test_stock_is_the_cumulative_signed_movements_and_a_snapshot_wins_on_its_date():
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 1), 10.0), _mrow("S1", "I1", D(2026, 1, 5), -4.0, "issue_project", "P1", 1), _mrow("S1", "I1", D(2026, 1, 10), 3.0), _mrow("S2", "I1", D(2026, 1, 2), 7.0)])
    s = delivery.stock_on(mv, D(2026, 1, 5), context=CTX).set_index(["site_key", "itm_key"])
    assert s.on_hand.to_dict() == {("S1", "I1"): 6.0, ("S2", "I1"): 7.0} and (s.source == "movements").all() and s.reserved.isna().all(), "movements on the date count"
    assert delivery.stock_on(mv, D(2026, 1, 4), context=CTX).set_index(["site_key", "itm_key"]).on_hand[("S1", "I1")] == 10.0
    snap = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "as_of_date": [D(2026, 1, 5)], "on_hand": [99.0], "reserved": [2.0], "available": [97.0]})
    t = delivery.stock_on(mv, D(2026, 1, 5), stock_level=snap, context=CTX).set_index(["site_key", "itm_key"])
    assert t.loc[("S1", "I1"), ["on_hand", "reserved", "source"]].tolist() == [99.0, 2.0, "snapshot"] and t.loc[("S2", "I1"), "source"] == "movements"
    res = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "qty_open": [8.0]})
    r = delivery.stock_on(mv, D(2026, 1, 5), reservation_open=res, context=CTX).set_index(["site_key", "itm_key"])
    assert r.loc[("S1", "I1"), ["reserved", "available"]].tolist() == [8.0, -2.0], "available can be negative"
    assert r.loc[("S2", "I1"), "reserved"] == 0.0
    with pytest.raises(FrameError, match="qty must be numeric"):
        delivery.stock_on(mv.assign(qty="1"), D(2026, 1, 5), context=CTX)
    with pytest.raises(FrameError, match="more than one snapshot"):
        delivery.stock_on(mv, D(2026, 1, 5), stock_level=pd.concat([snap, snap]), context=CTX)


def _res(rows):
    return pd.DataFrame(rows, columns=["prj_key", "itm_key", "reservation_no", "site_key", "qty", "created_date", "needed_by_date", "po_key", "po_line_no"])


def test_reservations_open_on_a_date_issues_up_to_the_date_and_free_ones():
    r = _res([("P1", "I1", 1, "S1", 10.0, D(2026, 1, 1), D(2026, 3, 1), None, None), ("P1", "I2", 1, "S1", 5.0, D(2026, 2, 1), D(2026, 3, 1), "PO-1", 1), ("P2", "I1", 1, "S1", 4.0, D(2026, 1, 1), D(2026, 3, 1), None, None)])
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 10), -6.0, "issue_project", "P1", 1), _mrow("S1", "I1", D(2026, 1, 20), -4.0, "issue_project", "P1", 1), _mrow("S1", "I1", D(2026, 1, 12), -4.0, "issue_ticket", None, None),
              _mrow("S1", "I1", D(2026, 1, 3), 50.0)])
    o = lambda d: delivery.reserved_demand(r, mv, d, context=CTX).set_index(["prj_key", "itm_key"])
    assert o(D(2026, 1, 9)).qty_open.to_dict() == {("P1", "I1"): 10.0, ("P2", "I1"): 4.0}
    assert o(D(2026, 1, 10)).qty_open.to_dict() == {("P1", "I1"): 4.0, ("P2", "I1"): 4.0}, "an issue on the date counts"
    assert ("P1", "I1") not in o(D(2026, 1, 20)).index, "fully issued on the date: no longer open"
    assert o(D(2026, 1, 31)).index.tolist() == [("P2", "I1")] and o(D(2026, 2, 1)).index.tolist() == [("P1", "I2"), ("P2", "I1")], "created on the date counts; before it the reservation does not exist"
    assert o(D(2026, 2, 1)).loc[("P1", "I2"), "po_key"] == "PO-1" and pd.isna(o(D(2026, 2, 1)).loc[("P2", "I1"), "po_key"])
    assert delivery.reserved_demand(r, mv, D(2025, 12, 31), context=CTX).empty
    with pytest.raises(FrameError, match="more than one row"):
        delivery.reserved_demand(pd.concat([r, r.iloc[:1]]), mv, D(2026, 2, 1), context=CTX)


def _pl(rows):
    f = pd.DataFrame(rows, columns=["po_key", "line_no", "itm_key", "qty", "promised_date"])
    return f.assign(requested_date=f["promised_date"] - pd.DateOffset(days=20)) if len(f) else f.assign(requested_date=pd.Series(dtype="datetime64[ns]"))


def _po(rows):
    return pd.DataFrame(rows, columns=["po_key", "sup_key", "prj_key", "order_date", "status"])


def _gr(rows):
    return pd.DataFrame(rows, columns=["po_key", "line_no", "receipt_date", "qty_accepted"])


def test_open_lines_remaining_slip_and_cancelled_orders():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 3, 1)), ("PO-1", 2, "I2", 5.0, D(2026, 3, 1)), ("PO-2", 1, "I1", 3.0, D(2026, 6, 1)), ("PO-3", 1, "I1", 3.0, D(2026, 6, 1))])
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open"), ("PO-2", "S1", "P1", D(2026, 5, 1), "open"), ("PO-3", "S1", "P1", D(2026, 1, 1), "cancelled")])
    gr = _gr([("PO-1", 1, D(2026, 2, 1), 4.0), ("PO-1", 1, D(2026, 4, 1), 6.0), ("PO-1", 2, D(2026, 3, 1), 5.0)])
    o = lambda d: delivery.open_po_lines(pl, po, gr, d, context=CTX).set_index(["po_key", "line_no"])
    a = o(D(2026, 3, 10))
    assert a.remaining.to_dict() == {("PO-1", 1): 6.0} and a.days_overdue.to_dict() == {("PO-1", 1): 9} and a.slip_days.to_dict() == {("PO-1", 1): 20}, "line 2 was received in full on 2026-03-01; PO-3 is cancelled; PO-2 not placed yet"
    assert o(D(2026, 4, 1)).empty or ("PO-1", 1) not in o(D(2026, 4, 1)).index, "received in full on the date: not open"
    assert o(D(2026, 3, 31)).remaining[("PO-1", 1)] == 6.0 and o(D(2026, 5, 1)).index.tolist() == [("PO-2", 1)] and o(D(2026, 5, 1)).days_overdue[("PO-2", 1)] == 0, "order placed on the date counts; promise not past: not overdue"
    assert o(D(2026, 6, 1)).days_overdue[("PO-2", 1)] == 0 and o(D(2026, 6, 2)).days_overdue[("PO-2", 1)] == 1, "overdue only after the promised date"
    assert o(D(2026, 3, 10)).columns.tolist()[:5] == ["prj_key", "itm_key", "sup_key", "order_date", "qty"]
    with pytest.raises(FrameError, match="more than one row"):
        delivery.open_po_lines(pd.concat([pl, pl.iloc[:1]]), po, gr, D(2026, 3, 10), context=CTX)
    with pytest.raises(FrameError, match="qty_accepted must be numeric"):
        delivery.open_po_lines(pl, po, gr.assign(qty_accepted="1"), D(2026, 3, 10), context=CTX)


def test_exposed_demand_active_projects_free_reservations_items_of_the_supplier_and_the_effective_date():
    ol = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3", "PO-4"], "line_no": 1, "prj_key": ["P1", "P1", "P2", "P3"], "itm_key": "I1", "sup_key": ["S1", "S1", "S1", "S2"],
                       "order_date": [D(2026, 3, 31), D(2026, 4, 1), D(2026, 5, 1), D(2026, 5, 1)], "remaining": [2.0, 3.0, 4.0, 5.0]})
    rs = pd.DataFrame({"prj_key": ["P4", "P4", "P1", "P5"], "itm_key": ["I1", "I9", "I1", "I1"], "qty_open": [7.0, 8.0, 1.0, 9.0], "po_key": [None, None, "PO-9", None]})
    pls = pd.DataFrame({"sup_key": ["S1", "S1", "S2"], "itm_key": ["I1", "I2", "I9"]})
    pj = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5"], "price_type": ["fixed_price", "indexed", "fixed_price", "indexed", "fixed_price"]})
    e = delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=["P1", "P2", "P4"], context=CTX)
    assert e.lines.after_effective_date.tolist() == [False, True, True] and e.lines.prj_key.tolist() == ["P1", "P1", "P2"], "an order placed on 2026-03-31 is before the step"
    assert e.reservations.itm_key.tolist() == ["I1"] and e.reservations.prj_key.tolist() == ["P4"], "free reservations of the supplier's items only: not an order bound one, not an item of another supplier, not an inactive project"
    p = e.projects.set_index("prj_key")
    assert p.index.tolist() == ["P1", "P2", "P4"] and p.price_type.to_dict() == {"P1": "fixed_price", "P2": "indexed", "P4": "indexed"} and p.remaining_lines.to_dict() == {"P1": 5.0, "P2": 4.0, "P4": 0.0}
    assert p.remaining_reserved.to_dict() == {"P1": 0.0, "P2": 0.0, "P4": 7.0} and p.n_lines.to_dict()["P1"] == 2
    assert delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active="P1", context=CTX).projects.prj_key.tolist() == ["P1"], "one key given as text is one project"


def test_spot_orders_premium_needs_a_rate_and_freight_is_expedite_service():
    pl = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-2"], "line_no": [1, 2, 1], "itm_key": ["I1", "I9", "I1"], "unit_price": [1500.0, 80.0, 99.0], "currency": ["EUR", "EUR", "EUR"],
                       "price_source": ["spot", "list", "list"], "expedite": [False, True, False]})
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "order_type": ["spot", "project"], "sup_key": ["S9", "S1"], "prj_key": ["P1", "P1"], "order_date": [D(2026, 9, 1), D(2026, 9, 1)]})
    price = pd.DataFrame({"sup_key": ["S2", "S2", "S2"], "itm_key": ["I1", "I1", "I1"], "valid_from": [D(2026, 1, 1), D(2026, 9, 1), D(2026, 8, 1)], "valid_to": [D(2026, 8, 31), None, D(2026, 12, 31)],
                          "unit_price": [10000.0, 11000.0, 5.0], "currency": ["SEK", "SEK", "SEK"], "change_reason": ["initial", "indexation", "spot_quote"]})
    s = delivery.spot_orders(pl, po, price, context=CTX)
    assert s.po_key.tolist() == ["PO-1", "PO-1"] and s.freight.isna().all() and s.premium.isna().all(), "without item types an expedite line is not known to be freight"
    item = pd.Series({"I1": "goods", "I9": "service"})
    r = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates={"EUR": 7.5, "SEK": 0.7}, item_type=item, context=CTX).set_index("line_no")
    assert r.premium[1] == pytest.approx(1500 * 7.5 / (11000 * 0.7) - 1) and pd.isna(r.premium[2]), "the framework price on the order date (the spot quote row is not a list price); freight has no premium"
    with pytest.raises(FrameError, match="both framework_sup_key and rates"):
        delivery.spot_orders(pl, po, price, framework_sup_key="S2", context=CTX)
    with pytest.raises(FrameError, match="no rate for currency SEK"):
        delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates={"EUR": 7.5}, context=CTX)


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["stock_on", "reserved_demand", "open_po_lines", "exposed_demand", "spot_orders"]
    for n in names:
        m = reg[f"halvaro.delivery.supply.{n}"]
        assert m.parameters[-1] == "context" and m.sources          # the oracle pointers of exposed_demand and spot_orders are kept in a file of the closed repository
    assert registry.check() == [] and {f"halvaro.delivery.supply.{n}" for n in names} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    with pytest.raises(StageRefusal, match="procurement"):
        delivery.open_po_lines(_pl([]), _po([]), _gr([]), D(2026, 1, 1), context=Context(stage="month3", role="r"))


# the baseline


@pytest.mark.release
def test_reservations_open_at_now_equal_qty_open_and_stock_equals_every_snapshot(load):
    r, mv, sl = load("inventory", "reservation"), load("inventory", "stock_movement"), load("inventory", "stock_level")
    rd = delivery.reserved_demand(r, mv, NOW, context=CTX)
    want = r[r.qty_open > 1e-9]
    assert set(zip(rd.prj_key, rd.itm_key, rd.reservation_no)) == set(zip(want.prj_key, want.itm_key, want.reservation_no)) and abs(rd.qty_open.sum() - want.qty_open.sum()) < 1e-6, "O14"
    dates = sorted(sl.as_of_date.unique())
    for d in (dates[0], dates[len(dates) // 2], dates[-1]):
        snap = sl[sl.as_of_date == d].set_index(["site_key", "itm_key"])
        mine = delivery.stock_on(mv, d, context=CTX).set_index(["site_key", "itm_key"])
        both = snap.join(mine, rsuffix="_m", how="inner")
        assert len(both) == len(snap) and ((both.on_hand - both.on_hand_m).abs() < 1e-6).all(), d
        assert (delivery.stock_on(mv, d, stock_level=sl, context=CTX).source == "snapshot").sum() == len(snap)
    weekly = sl[sl.itm_key.isin(["ITM-000001", "ITM-000002"]) & (sl.site_key == "SITE-04")]
    assert weekly.as_of_date.nunique() > 150, "A and B at SITE-04 have weekly snapshots"


# review fixes: slip, freight, latest price, validation and the boundaries mutations must break

def test_slip_is_promised_minus_requested_and_residue_below_the_epsilon_is_not_open():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 6, 1))]).assign(requested_date=pd.Timestamp(2026, 4, 1))
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open")])
    r = delivery.open_po_lines(pl, po, _gr([]), D(2026, 3, 1), context=CTX).iloc[0]
    assert r.slip_days == 61 and r.days_overdue == 0, "the supplier moved the date by 61 days; nothing is overdue yet"
    gr = _gr([("PO-1", 1, D(2026, 2, 1), 0.1)] * 100)
    assert delivery.open_po_lines(pl, po, gr, D(2026, 3, 1), context=CTX).empty, "100 receipts of 0.1 for 10 units leave float dust, not an open line"
    with pytest.raises(FrameError, match="without promised_date or requested_date"):
        delivery.open_po_lines(pl.assign(requested_date=pd.NaT), po, _gr([]), D(2026, 3, 1), context=CTX)
    with pytest.raises(FrameError, match="is a number"):
        delivery.open_po_lines(pl, po, _gr([]), 20260301, context=CTX)


def test_reservation_only_pairs_stay_in_the_stock_issues_must_be_negative_and_nulls_are_refused():
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 1), 10.0)])
    res = pd.DataFrame({"site_key": ["S9"], "itm_key": ["I9"], "qty_open": [5.0]})
    s = delivery.stock_on(mv, D(2026, 1, 5), reservation_open=res, context=CTX).set_index(["site_key", "itm_key"])
    assert s.loc[("S9", "I9"), ["on_hand", "reserved", "available"]].tolist() == [0.0, 5.0, -5.0], "reserved with no stock at all: the pair stays visible, available is negative"
    with pytest.raises(FrameError, match="without movement_date"):
        delivery.stock_on(mv.assign(movement_date=[None]), D(2026, 1, 5), context=CTX)
    snap = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "as_of_date": [D(2026, 1, 5)], "on_hand": [None], "reserved": [0.0], "available": [0.0]})
    with pytest.raises(FrameError, match="null on_hand"):
        delivery.stock_on(mv, D(2026, 1, 5), stock_level=snap, context=CTX)
    r = _res([("P1", "I1", 1, "S1", 10.0, D(2026, 1, 1), D(2026, 3, 1), None, None)])
    bad = _mv([_mrow("S1", "I1", D(2026, 1, 10), 3.0, "issue_project", "P1", 1)])
    with pytest.raises(FrameError, match="positive quantity"):
        delivery.reserved_demand(r, bad, D(2026, 2, 1), context=CTX)
    other = _mv([_mrow("S1", "I1", D(2026, 1, 10), -3.0, "issue_ticket", "P1", 1), _mrow("S1", "I1", D(2026, 1, 11), 3.0, "return", "P1", 1), _mrow("S1", "I1", D(2026, 1, 12), -2.0, "issue_project", "P1", None)])
    assert delivery.reserved_demand(r, other, D(2026, 2, 1), context=CTX).qty_open.tolist() == [10.0], "only issue_project movements with a reservation number are issues"
    dust = _mv([_mrow("S1", "I1", D(2026, 1, 1 + i), -1.0, "issue_project", "P1", 1) for i in range(10)])
    assert delivery.reserved_demand(r.assign(qty=10.0000000001), dust, D(2026, 2, 1), context=CTX).empty, "an open quantity under the epsilon is closed"


def test_exposed_demand_refuses_unknown_projects_duplicates_and_bad_active():
    ol = pd.DataFrame({"po_key": ["PO-1"], "line_no": 1, "prj_key": ["P1"], "itm_key": "I1", "sup_key": "S1", "order_date": [D(2026, 5, 1)], "remaining": [2.0]})
    rs = pd.DataFrame({"prj_key": [], "itm_key": [], "qty_open": [], "po_key": []})
    pls = pd.DataFrame({"sup_key": ["S1"], "itm_key": ["I1"]})
    pj = pd.DataFrame({"prj_key": ["P1"], "price_type": ["fixed_price"]})
    ok = delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=["P1"], context=CTX)
    assert ok.projects.n_lines.dtype == "int64" and ok.projects.n_reservations.tolist() == [0]
    with pytest.raises(FrameError, match="not in the project frame.*P1"):
        delivery.exposed_demand(ol, rs, pls, pj.iloc[:0], "S1", "2026-04-01", active=["P1"], context=CTX)
    with pytest.raises(FrameError, match="more than one row for an order line"):
        delivery.exposed_demand(pd.concat([ol, ol]), rs, pls, pj, "S1", "2026-04-01", active=["P1"], context=CTX)
    with pytest.raises(FrameError, match="project key or a list"):
        delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=pj, context=CTX)
    with pytest.raises(FrameError, match="project key or a list"):
        delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=None, context=CTX)
    with pytest.raises(FrameError, match="without order_date"):
        delivery.exposed_demand(ol.assign(order_date=None), rs, pls, pj, "S1", "2026-04-01", active=["P1"], context=CTX)


def test_spot_premium_uses_the_latest_valid_row_leaves_out_the_framework_supplier_and_checks_rates():
    pl = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "line_no": 1, "itm_key": ["I1", "I1", "I7"], "unit_price": [1500.0, 1500.0, 50.0], "currency": "EUR", "price_source": "spot", "expedite": False})
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "order_type": "spot", "sup_key": ["S9", "S2", "S9"], "prj_key": "P1", "order_date": [D(2026, 9, 1)] * 3})
    price = pd.DataFrame({"sup_key": "S2", "itm_key": "I1", "valid_from": [D(2026, 1, 1), D(2026, 9, 1)], "valid_to": [D(2026, 9, 1), None], "unit_price": [10000.0, 11000.0], "currency": "SEK",
                          "change_reason": ["initial", "indexation"]})
    r = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates={"EUR": 7.5, "SEK": 0.7}, context=CTX)
    assert r.po_key.tolist() == ["PO-1"], "the framework supplier's own order and an item off its list are left out"
    assert r.premium.iloc[0] == pytest.approx(1500 * 7.5 / (11000 * 0.7) - 1), "valid_to equal to the next valid_from: the latest row counts"
    for rates, match in (({"EUR": 0.0, "SEK": 0.7}, "positive"), ({"EUR": float("nan"), "SEK": 0.7}, "positive"), ({"EUR": -1.0, "SEK": 0.7}, "positive"), ({}, "no rate for currency")):
        with pytest.raises(FrameError, match=match):
            delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates=rates, context=CTX)
    with pytest.raises(FrameError, match="True or False"):
        delivery.spot_orders(pl.assign(expedite="False"), po, price, context=CTX)
    with pytest.raises(FrameError, match="unique index"):
        delivery.spot_orders(pl, po, price, item_type=pd.Series(["goods", "goods"], index=["I1", "I1"]), context=CTX)
    freight = pl.assign(expedite=[True, False, False], itm_key=["I9", "I1", "I7"])
    s = delivery.spot_orders(freight, po, price, item_type=pd.Series({"I9": "service", "I1": "goods", "I7": "goods"}), context=CTX)
    assert s.freight.tolist() == [True, False, False], "freight needs expedite and a service item"
    assert delivery.spot_orders(freight.assign(expedite=True), po, price, item_type=pd.Series({"I9": "service", "I1": "goods", "I7": "goods"}), context=CTX).freight.tolist() == [True, False, False]


# second review: promise as of the date, freight tie, combined frame, nulls, price ties, speed, epsilon, sources

def _spot_reference(po_line, purchase_order, price_list, framework_sup_key, item_type, rates):
    """The iterrows implementation before the vectorised one (premium and row selection only; the freight tie came later), kept as the reference."""
    o = purchase_order[purchase_order["order_type"] == "spot"][["po_key", "sup_key", "prj_key", "order_date"]].assign(order_date=lambda x: _sup._date(x, "order_date", "procurement.purchase_order"))
    out = po_line[["po_key", "line_no", "itm_key", "unit_price", "currency", "price_source", "expedite"]].merge(o, on="po_key", how="inner")
    out["expedite"] = out["expedite"].astype(bool)
    if item_type is not None:
        out["freight"] = (out["expedite"] & (out["itm_key"].map(item_type) == "service")).astype("boolean")
    else:
        out["freight"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    out["premium"] = np.nan
    pl = price_list[(price_list["sup_key"] == framework_sup_key) & (price_list["change_reason"] != "spot_quote")].assign(
        valid_from=lambda x: _sup._date(x, "valid_from", "procurement.price_list"), valid_to=lambda x: _sup._date(x, "valid_to", "procurement.price_list"))
    listed = set(pl["itm_key"])
    out = out[(out["sup_key"] != framework_sup_key) & out["itm_key"].isin(listed | set(item_type[item_type == "service"].index if item_type is not None else []))].reset_index(drop=True)
    for i, r in out[~out["freight"].fillna(False).astype(bool)].iterrows():
        hit = pl[(pl["itm_key"] == r["itm_key"]) & (pl["valid_from"] <= r["order_date"]) & (pl["valid_to"].isna() | (pl["valid_to"] >= r["order_date"]))].sort_values("valid_from")
        if len(hit):
            row = hit.iloc[-1]
            out.loc[i, "premium"] = r["unit_price"] * rates[r["currency"]] / (row["unit_price"] * rates[row["currency"]]) - 1.0
    return out[["po_key", "line_no", "prj_key", "itm_key", "sup_key", "order_date", "unit_price", "currency", "price_source", "expedite", "freight", "premium"]].sort_values(["po_key", "line_no"]).reset_index(drop=True)


def _random_spot(n, seed, items=8):
    rng = np.random.default_rng(seed)
    itm = [f"I{i}" for i in range(items)]
    pl = []
    for k, it in enumerate(itm):
        start = pd.Timestamp(2023, 1, 1)
        for j in range(int(rng.integers(2, 6))):
            length = int(rng.integers(60, 400))
            end = start + pd.Timedelta(days=length)
            pl.append(("S2", it, start.date(), None if j == 4 else end.date(), float(rng.integers(100, 900)), str(rng.choice(["SEK", "EUR"])), "initial" if j == 0 else "indexation"))
            start = end + pd.Timedelta(days=int(rng.integers(0, 40)))       # gaps and exact hand-overs (valid_to equal to the next valid_from minus zero) both occur
        pl.append(("S2", it, pd.Timestamp(2024, 3, 1).date(), pd.Timestamp(2026, 12, 31).date(), 1.0, "SEK", "spot_quote"))
    pl = pd.DataFrame(pl, columns=["sup_key", "itm_key", "valid_from", "valid_to", "unit_price", "currency", "change_reason"]).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    pk = [f"PO-{i:05d}" for i in range(n)]
    od = pd.Timestamp(2023, 1, 1) + pd.to_timedelta(rng.integers(0, 1300, n), unit="D")
    po = pd.DataFrame({"po_key": pk, "order_type": rng.choice(["spot", "spot", "project"], n), "sup_key": rng.choice(["S2", "S5", "S6", "S7"], n), "prj_key": rng.choice(["P1", "P2", "P3"], n),
                       "order_date": [d.date() for d in od]})
    ln = pd.DataFrame({"po_key": pk, "line_no": 1, "itm_key": rng.choice(itm + ["I77", "SV"], n), "unit_price": rng.integers(100, 2000, n).astype(float), "currency": rng.choice(["SEK", "EUR", "DKK"], n),
                       "price_source": "spot", "expedite": rng.choice([True, False], n)})
    return ln, po, pl, pd.Series({**{i: "goods" for i in itm}, "I77": "goods", "SV": "service"})


RATES = {"EUR": 7.5, "SEK": 0.7, "DKK": 1.0}


def test_open_lines_promise_is_the_one_valid_on_the_date_and_flags_a_promise_that_is_not_final():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 7, 14)), ("PO-1", 2, "I1", 10.0, D(2026, 7, 14))]).assign(requested_date=pd.Timestamp(2026, 6, 20), promise_revised_on=[D(2026, 7, 1), None])
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open")])
    o = lambda d, p=pl: delivery.open_po_lines(p, po, _gr([]), d, context=CTX).set_index(["po_key", "line_no"])
    a = o(D(2026, 6, 30))
    assert a.loc[("PO-1", 1), ["slip_days", "days_overdue", "promise_is_final"]].tolist() == [0, 10, False], "before the revision the original date 2026-06-20 stood: overdue by 10, not slipped"
    assert a.loc[("PO-1", 1), "promised_date"] == pd.Timestamp(2026, 6, 20) and pd.isna(a.loc[("PO-1", 1), "promise_revised_on"])
    assert a.loc[("PO-1", 2), ["slip_days", "days_overdue", "promise_is_final"]].tolist() == [24, 0, True], "a line without a revision keeps its stored promise"
    b = o(D(2026, 7, 1))
    assert b.loc[("PO-1", 1), ["slip_days", "days_overdue", "promise_is_final"]].tolist() == [24, 0, True] and b.loc[("PO-1", 1), "promise_revised_on"] == pd.Timestamp(2026, 7, 1), "on the revision day the revision stands"
    c = o(D(2026, 7, 20))
    assert c.loc[("PO-1", 1), ["slip_days", "days_overdue", "promise_is_final"]].tolist() == [24, 6, True]
    nocol = o(D(2026, 6, 30), pl.drop(columns="promise_revised_on"))
    assert nocol.promise_is_final.all() and nocol.slip_days.tolist() == [24, 24] and nocol.promise_revised_on.isna().all(), "without the column no revision is known: the stored promise is used"


def test_open_lines_line_no_widths_may_differ_but_text_against_integer_is_refused():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 3, 1))])
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open")])
    gr = _gr([("PO-1", 1, D(2026, 2, 1), 4.0)])
    for a, b in (("int32", "int64"), ("Int64", "int64"), ("int64", "Int32"), ("int64", "int8")):
        r = delivery.open_po_lines(pl.assign(line_no=pl.line_no.astype(a)), po, gr.assign(line_no=gr.line_no.astype(b)), D(2026, 3, 10), context=CTX)
        assert r.remaining.tolist() == [6.0], (a, b)
    with pytest.raises(FrameError, match="differs in type"):
        delivery.open_po_lines(pl, po, gr.assign(line_no="1"), D(2026, 3, 10), context=CTX)
    with pytest.raises(FrameError, match="differs in type"):
        delivery.open_po_lines(pl.assign(line_no="1"), po, gr, D(2026, 3, 10), context=CTX)
    with pytest.raises(FrameError, match="differs in type"):
        delivery.open_po_lines(pl, po, gr.assign(line_no=1.0), D(2026, 3, 10), context=CTX)


def _framework_spot_case():
    rows = [("PO-1", "S9", "P1", D(2026, 9, 1), "I1", False), ("PO-2", "S8", "P1", D(2026, 9, 1), "I9", True),      # goods and express freight of one project and day
            ("PO-3", "S8", "P2", D(2026, 9, 1), "I9", True),                                                       # express service, no goods order of the project
            ("PO-4", "S8", "P1", D(2026, 9, 2), "I9", True),                                                       # same project, other day
            ("PO-5", "S2", "P5", D(2026, 9, 1), "I1", False), ("PO-6", "S8", "P5", D(2026, 9, 1), "I9", True),     # the goods order is the framework supplier's own: not a switch order
            ("PO-7", "S9", "P6", D(2026, 9, 1), "I7", False), ("PO-8", "S8", "P6", D(2026, 9, 1), "I9", True),     # goods of an item outside the framework list
            ("PO-9", "S9", "P7", D(2026, 9, 1), "I1", False), ("PO-10", "S8", "P7", D(2026, 9, 1), "I9", False),   # a service line that is not express
            ("PO-11", "S9", "P8", D(2026, 9, 1), "I1", True), ("PO-12", "S8", "P8", D(2026, 9, 1), "I1", True)]    # express goods lines are goods
    po = pd.DataFrame({"po_key": [r[0] for r in rows], "order_type": "spot", "sup_key": [r[1] for r in rows], "prj_key": [r[2] for r in rows], "order_date": [r[3] for r in rows]})
    pl = pd.DataFrame({"po_key": po.po_key, "line_no": 1, "itm_key": [r[4] for r in rows], "unit_price": 1500.0, "currency": "EUR", "price_source": "spot", "expedite": [r[5] for r in rows]})
    price = pd.DataFrame({"sup_key": "S2", "itm_key": ["I1"], "valid_from": [D(2026, 1, 1)], "valid_to": [None], "unit_price": [10000.0], "currency": "SEK", "change_reason": "initial"})
    return pl, po, price, pd.Series({"I1": "goods", "I7": "goods", "I9": "service"})


def test_framework_freight_is_an_express_service_line_next_to_a_goods_spot_order_of_the_same_project_and_day():
    pl, po, price, item = _framework_spot_case()
    s = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates=RATES, item_type=item, context=CTX).set_index("po_key")
    assert set(s.index) == {"PO-1", "PO-2", "PO-3", "PO-4", "PO-6", "PO-8", "PO-9", "PO-10", "PO-11", "PO-12"}, "the framework supplier's own order and the list-less goods item are out"
    assert s.freight.astype(bool).to_dict() == {"PO-1": False, "PO-2": True, "PO-3": False, "PO-4": False, "PO-6": False, "PO-8": False, "PO-9": False, "PO-10": False, "PO-11": False, "PO-12": False}
    assert s.freight_unmatched.to_dict() == {"PO-1": False, "PO-2": False, "PO-3": True, "PO-4": True, "PO-6": True, "PO-8": True, "PO-9": False, "PO-10": False, "PO-11": False, "PO-12": False}, "an express service line with no goods order next to it is unmatched"
    assert s.loc["PO-2", "premium"] != s.loc["PO-2", "premium"] and s.loc["PO-1", "premium"] == pytest.approx(1500 * 7.5 / (10000 * 0.7) - 1) and s.loc["PO-11", "premium"] == pytest.approx(1500 * 7.5 / (10000 * 0.7) - 1)
    plain = delivery.spot_orders(pl, po, price, item_type=item, context=CTX)
    assert plain.freight_unmatched.eq(False).all() and plain.set_index("po_key").freight.astype(bool)[["PO-2", "PO-3", "PO-4"]].all(), "without a framework supplier freight is expedite and service, as before"
    assert delivery.spot_orders(pl, po, price, context=CTX).freight_unmatched.eq(False).all()
    nofr = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates=RATES, context=CTX)
    assert nofr.freight.isna().all() and nofr.freight_unmatched.eq(False).all(), "without item types nothing is known about freight"


def test_an_unmatched_express_service_line_of_a_listed_item_has_no_premium():
    pl, po, price, item = _framework_spot_case()
    price = pd.concat([price, price.assign(itm_key="I9", unit_price=7000.0)], ignore_index=True)       # the service item is on the framework list too
    s = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates=RATES, item_type=item, context=CTX).set_index("po_key")
    assert s.loc["PO-3", "freight_unmatched"] and not s.loc["PO-3", "freight"] and np.isnan(s.loc["PO-3", "premium"]), "express service, no goods order: unmatched and no premium"
    assert np.isnan(s.loc["PO-2", "premium"]), "a matched one has none either"
    assert s.loc["PO-10", "premium"] == pytest.approx(1500 * 7.5 / (7000 * 0.7) - 1), "a service line that is not express keeps its premium"
    assert s.loc["PO-1", "premium"] == pytest.approx(1500 * 7.5 / (10000 * 0.7) - 1)


def test_exposed_demand_combined_is_the_single_frame_of_lines_and_reservations():
    ol = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "line_no": [1, 3], "prj_key": ["P1", "P2"], "itm_key": "I1", "sup_key": "S1", "order_date": [D(2026, 3, 31), D(2026, 5, 1)], "remaining": [2.0, 3.0]})
    rs = pd.DataFrame({"prj_key": ["P2", "P1"], "itm_key": ["I1", "I1"], "reservation_no": [7, 4], "qty_open": [7.0, 1.5], "po_key": [None, None]})
    pls = pd.DataFrame({"sup_key": ["S1"], "itm_key": ["I1"]})
    pj = pd.DataFrame({"prj_key": ["P1", "P2"], "price_type": ["fixed_price", "indexed"]})
    e = delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=["P1", "P2"], context=CTX)
    c = e.combined
    assert c.columns.tolist() == ["prj_key", "itm_key", "source", "reference", "remaining", "sup_key", "after_effective_date"]
    assert c.source.tolist() == ["po_line", "po_line", "reservation", "reservation"] and c.prj_key.tolist() == ["P1", "P2", "P1", "P2"]
    assert c.reference.tolist() == ["PO-1/1", "PO-2/3", "P1/I1/4", "P2/I1/7"] and c.remaining.tolist() == [2.0, 3.0, 1.5, 7.0] and c.sup_key.eq("S1").all()
    assert c.after_effective_date.iloc[:2].tolist() == [False, True] and c.after_effective_date.iloc[2:].isna().all(), "reservations have no order date"
    assert c.remaining.sum() == e.projects.remaining_lines.sum() + e.projects.remaining_reserved.sum() and set(c.prj_key) == set(e.projects.prj_key), "same project set and quantities as the project frame"
    assert e.lines.shape[1] == 8 and e.reservations.shape[1] == 5 and e.projects.columns.tolist()[:2] == ["prj_key", "n_lines"], "the three frames are as before"
    only = delivery.exposed_demand(ol, rs.iloc[:0], pls, pj, "S1", "2026-04-01", active=["P1"], context=CTX).combined
    assert only.source.tolist() == ["po_line"] and only.reference.tolist() == ["PO-1/1"]
    none = delivery.exposed_demand(ol.iloc[:0], rs.iloc[:0], pls, pj, "S1", "2026-04-01", active=["P1"], context=CTX).combined
    assert none.empty and none.columns.tolist() == c.columns.tolist()
    with pytest.raises(FrameError, match="reservation_no"):
        delivery.exposed_demand(ol, rs.drop(columns="reservation_no"), pls, pj, "S1", "2026-04-01", active=["P1", "P2"], context=CTX).combined


def test_exposed_demand_unknown_projects_are_refused_only_when_they_take_part_in_the_result():
    ol = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "line_no": 1, "prj_key": ["P1", "P2"], "itm_key": "I1", "sup_key": ["S1", "S2"], "order_date": [D(2026, 5, 1)] * 2, "remaining": [2.0, 3.0]})
    rs = pd.DataFrame({"prj_key": ["P3", "P4"], "itm_key": ["I1", "I9"], "qty_open": [1.0, 2.0], "po_key": [None, None]})
    pls = pd.DataFrame({"sup_key": ["S1", "S2"], "itm_key": ["I1", "I9"]})
    pj = pd.DataFrame({"prj_key": ["P1"], "price_type": ["fixed_price"]})
    ok = delivery.exposed_demand(ol, rs.iloc[1:], pls, pj, "S1", "2026-04-01", active=["P1", "P2", "P4", "P9"], context=CTX)
    assert ok.projects.prj_key.tolist() == ["P1"], "P2 is the line of another supplier, P4 holds an item of another supplier, P9 has nothing: none of them is in the result"
    with pytest.raises(FrameError, match="not in the project frame.*P3"):
        delivery.exposed_demand(ol, rs, pls, pj, "S1", "2026-04-01", active=["P1", "P3"], context=CTX)
    with pytest.raises(FrameError, match="not in the project frame.*P2"):
        delivery.exposed_demand(ol, rs.iloc[1:], pls, pj, "S2", "2026-04-01", active=["P2"], context=CTX)


def test_spot_premium_equals_the_reference_implementation_on_random_frames_and_is_fast():
    for seed in (1, 2, 3):
        ln, po, pl, item = _random_spot(500, seed)
        for it in (None, item):
            want = _spot_reference(ln, po, pl, "S2", it, RATES)
            got = delivery.spot_orders(ln, po, pl, framework_sup_key="S2", rates=RATES, item_type=it, context=CTX)
            assert len(got) > 100 and got.premium.notna().sum() > 50, "the random frame has hits, misses and gaps"
            cols = [c for c in want.columns if c not in ("freight", "premium")]
            pd.testing.assert_frame_equal(got[cols], want[cols])
            pd.testing.assert_series_equal(got["premium"], want["premium"], check_exact=True)
    ln, po, pl, item = _random_spot(5000, 7)
    po = po.assign(order_type="spot", sup_key=np.random.default_rng(7).choice(["S5", "S6", "S7"], len(po)))
    ln = ln.assign(itm_key=ln["itm_key"].where(~ln["itm_key"].isin(["I77", "SV"]), "I0"))
    t0 = time.perf_counter()
    big = delivery.spot_orders(ln, po, pl, framework_sup_key="S2", rates=RATES, item_type=item, context=CTX)
    took = time.perf_counter() - t0
    assert len(big) == 5000 and big.premium.notna().sum() > 1000 and took < 2.0, took


def test_spot_premium_picks_the_latest_valid_row_whatever_the_row_order_and_has_inclusive_dates():
    pl = pd.DataFrame({"po_key": ["PO-1"], "line_no": 1, "itm_key": "I1", "unit_price": 1500.0, "currency": "EUR", "price_source": "spot", "expedite": False})
    po = pd.DataFrame({"po_key": ["PO-1"], "order_type": "spot", "sup_key": "S9", "prj_key": "P1", "order_date": [D(2026, 9, 1)]})

    def prem(rows, price=None):
        price = pd.DataFrame(rows, columns=["valid_from", "valid_to", "unit_price", "change_reason"]).assign(sup_key="S2", itm_key="I1", currency="SEK") if price is None else price
        r = delivery.spot_orders(pl, po, price, framework_sup_key="S2", rates=RATES, context=CTX)
        return r.premium.iloc[0] if len(r) else np.nan      # an item with no list row at all is left out

    def want(p):
        return 1500 * 7.5 / (p * 0.7) - 1
    new, old = (D(2026, 8, 1), None, 11000.0, "indexation"), (D(2026, 1, 1), None, 10000.0, "initial")
    assert prem([new, old]) == pytest.approx(want(11000.0)) and prem([old, new]) == pytest.approx(want(11000.0)), "both valid: the later valid_from wins in either row order"
    assert prem([(D(2026, 1, 1), D(2026, 9, 1), 10000.0, "initial")]) == pytest.approx(want(10000.0)), "valid_to is inclusive"
    assert prem([(D(2026, 9, 1), None, 10000.0, "initial")]) == pytest.approx(want(10000.0)), "valid_from is inclusive"
    assert np.isnan(prem([(D(2026, 1, 1), D(2026, 8, 31), 10000.0, "initial")])) and np.isnan(prem([(D(2026, 9, 2), None, 10000.0, "initial")])), "outside the dates: no premium"
    spot = (D(2026, 8, 15), None, 5.0, "spot_quote")
    assert prem([spot, old]) == pytest.approx(want(10000.0)) and prem([old, spot]) == pytest.approx(want(10000.0)), "a spot quote row is never a list price, even when it is the latest valid row"
    assert np.isnan(prem([spot])), "a spot quote alone gives no list price"
    for rows in ([old, (D(2026, 1, 1), D(2026, 12, 31), 12000.0, "indexation")], [(D(2026, 1, 1), None, 12000.0, "indexation"), old]):
        with pytest.raises(FrameError, match="more than one framework row.*I1.*2026-01-01"):
            prem(rows)
    assert prem([old, (D(2026, 1, 1), None, 1.0, "spot_quote")]) == pytest.approx(want(10000.0)), "a tie with a spot quote is no tie"
    other = pd.DataFrame({"sup_key": ["S2", "S3", "S3"], "itm_key": "I1", "valid_from": [D(2026, 1, 1)] * 3, "valid_to": None, "unit_price": [10000.0, 5.0, 6.0], "currency": "SEK", "change_reason": "initial"})
    assert prem(None, other) == pytest.approx(want(10000.0)), "rows of another supplier are not framework rows and do not tie"


def test_spot_orders_validates_nulls_in_keys_prices_and_dates():
    pl, po, price, item = _framework_spot_case()
    kw = dict(framework_sup_key="S2", rates=RATES, item_type=item, context=CTX)
    bad_pl = lambda c, v: pl.assign(**{c: pl[c].astype(object).where(pl.index != 0, v)})
    for col, match in (("line_no", "line_no has null"), ("po_key", "po_key has null"), ("itm_key", "itm_key has null")):
        with pytest.raises(FrameError, match=match):
            delivery.spot_orders(bad_pl(col, None), po, price, **kw)
    for v in (np.nan, "1500"):
        with pytest.raises(FrameError, match="unit_price must be numeric"):
            delivery.spot_orders(bad_pl("unit_price", v), po, price, **kw)
    with pytest.raises(FrameError, match="order_date has null"):
        delivery.spot_orders(pl, po.assign(order_date=[None] + po.order_date.tolist()[1:]), price, **kw)
    with pytest.raises(FrameError, match="po_key has null"):
        delivery.spot_orders(pl, po.assign(po_key=[None] + po.po_key.tolist()[1:]), price, **kw)
    with pytest.raises(FrameError, match="valid_from has null"):
        delivery.spot_orders(pl, po, price.assign(valid_from=None), **kw)
    with pytest.raises(FrameError, match="itm_key has null"):
        delivery.spot_orders(pl, po, price.assign(itm_key=None), **kw)
    with pytest.raises(FrameError, match="unit_price must be numeric"):
        delivery.spot_orders(pl, po, price.assign(unit_price=np.nan), **kw)
    with pytest.raises(FrameError, match="unit_price must be numeric"):
        delivery.spot_orders(pl, po, price.assign(unit_price="10000"), **kw)


def test_quantity_columns_must_be_numeric_without_nulls_and_keys_set():
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 1), 10.0), _mrow("S1", "I1", D(2026, 1, 5), -4.0, "issue_project", "P1", 1)])
    r = _res([("P1", "I1", 1, "S1", 10.0, D(2026, 1, 1), D(2026, 3, 1), None, None)])
    d = D(2026, 2, 1)
    for v in (np.nan, "4"):
        with pytest.raises(FrameError, match="qty must be numeric"):
            delivery.reserved_demand(r, mv.assign(qty=[10.0, v]), d, context=CTX)
        with pytest.raises(FrameError, match="qty must be numeric"):
            delivery.reserved_demand(r.assign(qty=v), mv, d, context=CTX)
    for col in ("prj_key", "itm_key", "movement_date"):
        with pytest.raises(FrameError, match=f"{col} has null"):
            delivery.reserved_demand(r, mv.assign(**{col: [mv[col][0], None]}), d, context=CTX)
    other_project_row = mv.assign(prj_key=[None, None])
    with pytest.raises(FrameError, match="prj_key has null"):
        delivery.reserved_demand(r, other_project_row, d, context=CTX)
    for col in ("prj_key", "itm_key", "reservation_no", "site_key", "created_date"):
        with pytest.raises(FrameError, match=f"{col} has null"):
            delivery.reserved_demand(r.assign(**{col: pd.Series([None], dtype=object)}), mv, d, context=CTX)
    assert delivery.reserved_demand(r, mv.assign(prj_key=[None, "P1"], itm_key=["I1", "I1"]), d, context=CTX).qty_open.tolist() == [6.0], "a receipt may have no project"
    res = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "qty_open": [1.0]})
    for col in ("site_key", "itm_key"):
        with pytest.raises(FrameError, match=f"{col} has null"):
            delivery.stock_on(mv, d, reservation_open=res.assign(**{col: [None]}), context=CTX)
        with pytest.raises(FrameError, match=f"{col} has null"):
            delivery.stock_on(mv.assign(**{col: [None, "x"]}), d, context=CTX)
    for v in (np.nan, "1"):
        with pytest.raises(FrameError, match="qty_open must be numeric"):
            delivery.stock_on(mv, d, reservation_open=res.assign(qty_open=v), context=CTX)
    snap = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "as_of_date": [D(2026, 2, 1)], "on_hand": [5.0], "reserved": [0.0], "available": [5.0]})
    for c in ("on_hand", "reserved"):
        with pytest.raises(FrameError, match=f"stock_level.{c} must be numeric"):
            delivery.stock_on(mv, d, stock_level=snap.assign(**{c: "5"}), context=CTX)
    for c in ("site_key", "itm_key", "as_of_date"):
        with pytest.raises(FrameError, match=f"{c} has null"):
            delivery.stock_on(mv, d, stock_level=snap.assign(**{c: [None]}), context=CTX)


def test_open_lines_and_exposed_demand_refuse_null_keys_and_non_numeric_quantities():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 3, 1))])
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open")])
    gr = _gr([("PO-1", 1, D(2026, 2, 1), 4.0)])
    d = D(2026, 3, 10)
    for col in ("po_key", "line_no"):
        with pytest.raises(FrameError, match=f"po_line.{col} has null"):
            delivery.open_po_lines(pl.assign(**{col: pd.Series([None], dtype=object)}), po, gr, d, context=CTX)
        with pytest.raises(FrameError, match=f"goods_receipt.{col} has null"):
            delivery.open_po_lines(pl, po, gr.assign(**{col: pd.Series([None], dtype=object)}), d, context=CTX)
    with pytest.raises(FrameError, match="purchase_order.po_key has null"):
        delivery.open_po_lines(pl, po.assign(po_key=pd.Series([None], dtype=object)), gr, d, context=CTX)
    with pytest.raises(FrameError, match="purchase_order.order_date has null"):
        delivery.open_po_lines(pl, po.assign(order_date=pd.Series([None], dtype=object)), gr, d, context=CTX)
    with pytest.raises(FrameError, match="goods_receipt.receipt_date has null"):
        delivery.open_po_lines(pl, po, gr.assign(receipt_date=pd.Series([None], dtype=object)), d, context=CTX)
    for v in (np.nan, "4"):
        with pytest.raises(FrameError, match="qty must be numeric"):
            delivery.open_po_lines(pl.assign(qty=v), po, gr, d, context=CTX)
        with pytest.raises(FrameError, match="qty_accepted must be numeric"):
            delivery.open_po_lines(pl, po, gr.assign(qty_accepted=v), d, context=CTX)
    ol = pd.DataFrame({"po_key": ["PO-1"], "line_no": 1, "prj_key": ["P1"], "itm_key": "I1", "sup_key": "S1", "order_date": [D(2026, 5, 1)], "remaining": [2.0]})
    rs = pd.DataFrame({"prj_key": ["P1"], "itm_key": ["I1"], "qty_open": [1.0], "po_key": [None]})
    pls = pd.DataFrame({"sup_key": ["S1"], "itm_key": ["I1"]})
    pj = pd.DataFrame({"prj_key": ["P1"], "price_type": ["fixed_price"]})
    kw = dict(active=["P1"], context=CTX)
    nul = pd.Series([None], dtype=object)
    for col in ("po_key", "line_no", "itm_key", "sup_key"):
        with pytest.raises(FrameError, match=f"open_po_lines output.{col} has null"):
            delivery.exposed_demand(ol.assign(**{col: nul}), rs, pls, pj, "S1", "2026-04-01", **kw)
    for col in ("prj_key", "itm_key"):
        with pytest.raises(FrameError, match=f"reserved_demand output.{col} has null"):
            delivery.exposed_demand(ol, rs.assign(**{col: nul}), pls, pj, "S1", "2026-04-01", **kw)
    for col in ("sup_key", "itm_key"):
        with pytest.raises(FrameError, match=f"price_list.{col} has null"):
            delivery.exposed_demand(ol, rs, pls.assign(**{col: nul}), pj, "S1", "2026-04-01", **kw)
    with pytest.raises(FrameError, match="projects.project.prj_key has null"):
        delivery.exposed_demand(ol, rs, pls, pj.assign(prj_key=nul), "S1", "2026-04-01", **kw)
    for v in (np.nan, "2"):
        with pytest.raises(FrameError, match="remaining must be numeric"):
            delivery.exposed_demand(ol.assign(remaining=v), rs, pls, pj, "S1", "2026-04-01", **kw)
        with pytest.raises(FrameError, match="qty_open must be numeric"):
            delivery.exposed_demand(ol, rs.assign(qty_open=v), pls, pj, "S1", "2026-04-01", **kw)
    assert delivery.exposed_demand(ol.assign(prj_key=None), rs, pls, pj, "S1", "2026-04-01", **kw).lines.empty, "a line without a project is not on an active project (and not an error)"


def test_the_epsilon_closes_float_dust_and_nothing_larger():
    pl = _pl([("PO-1", 1, "I1", 10.0, D(2026, 6, 1)), ("PO-1", 2, "I1", 10.0, D(2026, 6, 1)), ("PO-1", 3, "I1", 10.0, D(2026, 6, 1))])
    po = _po([("PO-1", "S1", "P1", D(2026, 1, 1), "open")])
    gr = _gr([("PO-1", 1, D(2026, 2, 1), 10.0 - 5e-10), ("PO-1", 2, D(2026, 2, 1), 10.0 - 2e-9), ("PO-1", 3, D(2026, 2, 1), 10.0 - 5e-4)])
    r = delivery.open_po_lines(pl, po, gr, D(2026, 3, 1), context=CTX).set_index("line_no")
    assert r.index.tolist() == [2, 3], "5e-10 left is dust (closed); 2e-9 and 0.0005 left are open"
    res = _res([("P1", f"I{i}", 1, "S1", 10.0, D(2026, 1, 1), D(2026, 3, 1), None, None) for i in (1, 2, 3)])
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 5), -(10.0 - 5e-10), "issue_project", "P1", 1), _mrow("S1", "I2", D(2026, 1, 5), -(10.0 - 2e-9), "issue_project", "P1", 1),
              _mrow("S1", "I3", D(2026, 1, 5), -(10.0 - 5e-4), "issue_project", "P1", 1)])
    assert delivery.reserved_demand(res, mv, D(2026, 2, 1), context=CTX).itm_key.tolist() == ["I2", "I3"]


def test_stock_reserved_comes_from_the_reservations_not_the_snapshot_and_dates_are_calendar_days():
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 1), 10.0), _mrow("S1", "I2", D(2026, 1, 1), 3.0)])
    snap = pd.DataFrame({"site_key": ["S1", "S1"], "itm_key": ["I1", "I2"], "as_of_date": [D(2026, 1, 5)] * 2, "on_hand": [99.0, 50.0], "reserved": [2.0, 4.0], "available": [97.0, 46.0]})
    res = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "qty_open": [8.0]})
    t = delivery.stock_on(mv, D(2026, 1, 5), stock_level=snap, reservation_open=res, context=CTX).set_index("itm_key")
    assert t.loc["I1", ["on_hand", "reserved", "available", "source"]].tolist() == [99.0, 8.0, 91.0, "snapshot"], "on hand from the snapshot, reserved from the reservations (8, not the snapshot's 2)"
    assert t.loc["I2", ["on_hand", "reserved", "available"]].tolist() == [50.0, 0.0, 50.0], "no open reservation: reserved 0, not the snapshot's 4"
    only = delivery.stock_on(mv, D(2026, 1, 5), stock_level=snap, context=CTX).set_index("itm_key")
    assert only.reserved.to_dict() == {"I1": 2.0, "I2": 4.0}, "without reservations the snapshot value stays"
    # times of day: every date is a calendar day
    ts = lambda *a: pd.Timestamp(*a)
    mt = _mv([_mrow("S1", "I1", ts(2026, 1, 5, 15, 30), 4.0), _mrow("S1", "I1", ts(2026, 1, 6, 0, 0, 1), 100.0)])
    assert delivery.stock_on(mt, D(2026, 1, 5), context=CTX).on_hand.tolist() == [4.0], "a movement in the afternoon of the date counts"
    assert delivery.stock_on(mt, ts(2026, 1, 5, 6, 0), context=CTX).on_hand.tolist() == [4.0], "an as_of with a time of day is the calendar day"
    sn = snap.assign(as_of_date=[ts(2026, 1, 5, 6, 0)] * 2)
    assert (delivery.stock_on(mt, D(2026, 1, 5), stock_level=sn, context=CTX).source == "snapshot").all(), "a snapshot stamped with a time matches its day"
    r = _res([("P1", "I1", 1, "S1", 10.0, ts(2026, 1, 1, 10, 0), ts(2026, 3, 1, 8, 0), None, None)])
    iss = _mv([_mrow("S1", "I1", ts(2026, 1, 10, 9, 0), -4.0, "issue_project", "P1", 1)])
    got = delivery.reserved_demand(r, iss, D(2026, 1, 10), context=CTX)
    assert got.qty_open.tolist() == [6.0] and got.needed_by_date.iloc[0] == ts(2026, 3, 1), "created and issued during the date both count; dates come back as days"
    assert delivery.reserved_demand(r, iss, D(2026, 1, 1), context=CTX).qty_open.tolist() == [10.0]
    pl = _pl([("PO-1", 1, "I1", 10.0, ts(2026, 3, 1, 12, 0))]).assign(requested_date=ts(2026, 2, 1, 12, 0))
    po = _po([("PO-1", "S1", "P1", ts(2026, 1, 1, 16, 0), "open")])
    gr = _gr([("PO-1", 1, ts(2026, 2, 20, 18, 0), 4.0)])
    a = delivery.open_po_lines(pl, po, gr, D(2026, 2, 20), context=CTX).iloc[0]
    assert a.remaining == 6.0 and a.order_date == ts(2026, 1, 1) and a.slip_days == 28, "an order placed in the afternoon of a day and a receipt in the evening count on that day"
    b = delivery.open_po_lines(pl, po, gr, ts(2026, 3, 2, 3, 0), context=CTX).iloc[0]
    assert b.days_overdue == 1 and b.promised_date == ts(2026, 3, 1)
    assert not delivery.open_po_lines(pl, po, gr, D(2026, 1, 1), context=CTX).empty, "placed on the date at 16:00: open"


def test_the_sources_list_the_columns_the_functions_read():
    reg = registry.registered()
    want = {"reserved_demand": {"inventory.stock_movement.prj_key", "inventory.stock_movement.itm_key", "inventory.reservation.po_line_no", "inventory.reservation.created_date"},
            "open_po_lines": {"procurement.po_line.promise_revised_on", "procurement.purchase_order.status"},
            "exposed_demand": {"procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.purchase_order.sup_key", "procurement.purchase_order.order_date", "procurement.goods_receipt.qty_accepted",
                               "inventory.reservation.prj_key", "inventory.reservation.itm_key", "inventory.reservation.reservation_no", "inventory.reservation.qty", "inventory.reservation.po_key",
                               "procurement.price_list.sup_key", "projects.project.price_type"},
            "spot_orders": {"procurement.purchase_order.po_key", "procurement.price_list.sup_key", "procurement.price_list.itm_key", "procurement.price_list.valid_from", "procurement.price_list.valid_to",
                            "procurement.price_list.currency", "procurement.price_list.change_reason", "procurement.price_list.unit_price"}}
    for name, cols in want.items():
        assert cols <= set(reg[f"halvaro.delivery.supply.{name}"].sources), (name, sorted(cols - set(reg[f"halvaro.delivery.supply.{name}"].sources)))
    stages = {"exposed_demand": {"inventory", "procurement", "projects"}, "spot_orders": {"procurement"}, "reserved_demand": {"inventory"}, "open_po_lines": {"procurement"}}
    for name, names in stages.items():
        assert {s.split(".")[0] for s in reg[f"halvaro.delivery.supply.{name}"].sources} == names, f"{name}: the stage of the function must not change"


# the baseline, second review

@pytest.mark.release
def test_open_lines_promise_on_past_dates_follows_the_revision_day(load):
    po, pl, gr = (load("procurement", t) for t in ("purchase_order", "po_line", "goods_receipt"))
    rev = pl.set_index(["po_key", "line_no"])["promise_revised_on"].pipe(pd.to_datetime)
    final = pl.set_index(["po_key", "line_no"])["promised_date"].pipe(pd.to_datetime)
    for day in (D(2025, 6, 30), D(2026, 3, 31), D(2026, 9, 30), NOW):
        ol = delivery.open_po_lines(pl, po, gr, day, context=CTX)
        k = pd.MultiIndex.from_frame(ol[["po_key", "line_no"]])
        later = (rev.reindex(k).gt(pd.Timestamp(day))).to_numpy()
        assert (ol.promise_is_final.to_numpy() == ~later).all() and (ol.loc[later, "promised_date"] == ol.loc[later, "requested_date"]).all() and (ol.loc[later, "slip_days"] == 0).all()
        assert (ol.loc[~later, "promised_date"].to_numpy() == final.reindex(k[~later]).to_numpy()).all()
        assert (ol.days_overdue == np.maximum(0, (pd.Timestamp(day) - ol.promised_date).dt.days)).all()
        if day == NOW:
            assert ol.promise_is_final.all(), "at now no revision is in the future (decision 13)"
    a = delivery.open_po_lines(pl, po, gr, D(2025, 6, 30), context=CTX).set_index(["po_key", "line_no"]).loc[("PO-037545", 1)]
    assert (a.slip_days, a.days_overdue, a.promise_is_final) == (0, 10, False)
    assert delivery.open_po_lines(pl, po, gr, D(2025, 7, 1), context=CTX).set_index(["po_key", "line_no"]).loc[("PO-037545", 1), "slip_days"] == 24


@pytest.mark.release
def test_spot_orders_on_the_baseline_match_the_reference_and_every_freight_line_is_matched(load):
    po, pl, plist = (load("procurement", t) for t in ("purchase_order", "po_line", "price_list"))
    itype = load("inventory", "item").set_index("itm_key")["item_type"]
    rates = {"EUR": 7.46, "DKK": 1.0, "SEK": 0.67}
    got = delivery.spot_orders(pl, po, plist, framework_sup_key="SUP-000002", rates=rates, item_type=itype, context=CTX)
    want = _spot_reference(pl, po, plist, "SUP-000002", itype, rates)
    cols = [c for c in want.columns if c != "premium"]
    pd.testing.assert_frame_equal(got[cols], want[cols])
    pd.testing.assert_series_equal(got["premium"], want["premium"], check_exact=True)
    assert got.freight.astype(bool).sum() >= 4 and not got.freight_unmatched.any(), "the generator's express freight sits next to its goods orders"


def test_a_service_line_of_the_framework_list_is_not_the_goods_order_a_freight_line_needs():
    pl, po, price, item = _framework_spot_case()
    price = pd.concat([price, price.assign(itm_key="I9")], ignore_index=True)      # the service item is on the framework list too
    extra_po = pd.DataFrame({"po_key": ["PO-20", "PO-21"], "order_type": "spot", "sup_key": ["S9", "S8"], "prj_key": "P9", "order_date": [D(2026, 9, 1)] * 2})
    extra = pd.DataFrame({"po_key": ["PO-20", "PO-21"], "line_no": 1, "itm_key": "I9", "unit_price": 100.0, "currency": "EUR", "price_source": "spot", "expedite": [False, True]})
    s = delivery.spot_orders(pd.concat([pl, extra]), pd.concat([po, extra_po]), price, framework_sup_key="S2", rates=RATES, item_type=item, context=CTX).set_index("po_key")
    assert not s.loc["PO-21", "freight"] and s.loc["PO-21", "freight_unmatched"], "next to a service line of the same day there is still no goods order"
    assert s.loc["PO-2", "freight"], "the real goods order of P1 still matches"


def test_a_snapshot_is_found_with_an_as_of_that_carries_a_time_of_day_and_combined_is_sorted():
    mv = _mv([_mrow("S1", "I1", D(2026, 1, 1), 10.0)])
    snap = pd.DataFrame({"site_key": ["S1"], "itm_key": ["I1"], "as_of_date": [D(2026, 1, 5)], "on_hand": [99.0], "reserved": [0.0], "available": [99.0]})
    s = delivery.stock_on(mv, pd.Timestamp(2026, 1, 5, 6, 30), stock_level=snap, context=CTX)
    assert s.source.tolist() == ["snapshot"] and s.on_hand.tolist() == [99.0] and s.as_of.tolist() == [pd.Timestamp(2026, 1, 5)]
    lines = pd.DataFrame({"po_key": ["PO-2", "PO-1"], "line_no": [1, 1], "prj_key": ["P2", "P1"], "itm_key": "I1", "sup_key": "S1", "remaining": [1.0, 2.0], "after_effective_date": [True, False]})
    res = pd.DataFrame({"prj_key": ["P2", "P1"], "itm_key": ["I1", "I1"], "reservation_no": [1, 1], "qty_open": [4.0, 3.0], "po_key": [None, None]})
    c = delivery.ExposedDemand(lines, res, pd.DataFrame({"prj_key": ["P1", "P2"]}), "S1").combined
    assert c.reference.tolist() == ["PO-1/1", "PO-2/1", "P1/I1/1", "P2/I1/1"]
