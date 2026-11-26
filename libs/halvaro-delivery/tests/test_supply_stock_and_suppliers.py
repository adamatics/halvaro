"""blocked_projects, lead_time_on, lead_time_alerts, supplier_performance_recompute, supplier_performance_window, elements_per_spare_unit, at_risk_items: boundaries on synthetic frames."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, registry

CTX = Context(stage="month12", role="r")
D = dt.date
NOW = D(2026, 11, 30)
STOCK_AND_SUPPLIER_FUNCTIONS = ["blocked_projects", "lead_time_on", "lead_time_alerts", "supplier_performance_recompute", "supplier_performance_window", "elements_per_spare_unit", "at_risk_items"]


def _rs(rows):
    return pd.DataFrame(rows, columns=["prj_key", "itm_key", "site_key", "qty_open", "needed_by_date"])


def _st(rows):
    return pd.DataFrame(rows, columns=["site_key", "itm_key", "on_hand"])


def test_blocked_needs_an_active_project_the_item_the_horizon_and_zero_stock():
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 10, 13)), ("P1", "I1", "S1", 2.0, D(2026, 10, 1)), ("P1", "I2", "S1", 3.0, D(2026, 10, 14)), ("P2", "I1", "S1", 9.0, D(2026, 10, 13)),
              ("P3", "I1", "S1", 5.0, D(2026, 10, 13)), ("P4", "I1", "S1", 5.0, D(2026, 12, 16)), ("P5", "I1", "S1", 5.0, D(2026, 12, 15)), ("P6", "I1", "S1", 0.0, D(2026, 10, 13)),
              ("P7", "I3", "S1", 6.0, D(2026, 10, 13)), ("P8", "I1", "S2", 6.0, D(2026, 10, 13))])
    st = _st([("S1", "I1", 0.0), ("S1", "I2", 0.0), ("S1", "I3", 0.0), ("S2", "I1", 5.0)])
    b = delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1", "I2"], active=["P1", "P3", "P4", "P5", "P6", "P7", "P8"], horizon_days=45, context=CTX)
    it = b.items.set_index(["prj_key", "itm_key"])
    assert it.unmet_qty.to_dict() == {("P1", "I1"): 6.0, ("P1", "I2"): 3.0, ("P3", "I1"): 5.0, ("P5", "I1"): 5.0}, "P2 inactive, P4 one day past the horizon, P5 on it, P6 nothing open, P7 other item, P8 stock at its site"
    assert it.loc[("P1", "I1"), ["n_reservations", "days_past_need"]].tolist() == [2, 30] and it.loc[("P1", "I1"), "earliest_needed_by"] == pd.Timestamp(2026, 10, 1)
    assert it.loc[("P5", "I1"), "days_past_need"] == -45, "negative while the need is ahead"
    p = b.projects.set_index("prj_key")
    assert p.unmet_qty.to_dict() == {"P1": 9.0, "P3": 5.0, "P5": 5.0} and p.n_items.to_dict() == {"P1": 2, "P3": 1, "P5": 1}


def test_blocked_stock_above_zero_is_not_blocked_a_missing_row_is_and_the_site_limits():
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 10, 13)), ("P1", "I1", "S2", 4.0, D(2026, 10, 13))])
    st = _st([("S1", "I1", 1.0)])
    f = lambda **k: delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1"], horizon_days=0, context=CTX, **k).items
    assert f().site_key.tolist() == ["S2"], "one spare unit at S1 means not blocked; no stock row at S2 counts as zero"
    assert f(site="S1").empty and f(site="S2").site_key.tolist() == ["S2"]
    assert delivery.blocked_projects(rs, _st([("S1", "I1", -3.0), ("S2", "I1", 0.0)]), D(2026, 10, 31), items="I1", active="P1", horizon_days=0, context=CTX).items.unmet_qty.tolist() == [4.0, 4.0], "negative stock is blocked"
    late = delivery.blocked_projects(rs, st, D(2026, 10, 12), items=["I1"], active=["P1"], horizon_days=0, context=CTX).items
    assert late.empty, "need on the 13th is after the 12th plus zero days"
    assert not delivery.blocked_projects(rs, st, D(2026, 10, 13), items=["I1"], active=["P1"], horizon_days=0, context=CTX).items.empty, "the horizon is inclusive"


def test_blocked_default_horizon_is_the_parameter_and_bad_arguments_are_refused():
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 12, 15)), ("P2", "I1", "S1", 4.0, D(2026, 12, 16))])
    st = _st([("S1", "I1", 0.0)])
    b = delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1", "P2"], context=CTX)
    assert b.projects.prj_key.tolist() == ["P1"], "45 days from 2026-10-31 is 2026-12-15, inclusive"
    for bad in (-1, 1.5, True, "45"):
        with pytest.raises(FrameError, match="horizon_days"):
            delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1"], horizon_days=bad, context=CTX)
    with pytest.raises(FrameError, match="reserved_demand output"):
        delivery.blocked_projects(rs.drop(columns="qty_open"), st, D(2026, 10, 31), items=["I1"], active=["P1"], context=CTX)
    assert delivery.blocked_projects(rs.iloc[:0], st, D(2026, 10, 31), items=["I1"], active=["P1"], context=CTX).projects.empty


def _lt(rows):
    return pd.DataFrame(rows, columns=["sup_key", "itm_key", "valid_from", "valid_to", "lead_time_weeks"])


def test_lead_time_on_picks_the_valid_row_with_the_change_against_the_previous_one():
    lt = _lt([("S1", "I1", D(2022, 1, 1), D(2026, 7, 31), 16.0), ("S1", "I1", D(2026, 8, 1), None, 30.0), ("S1", "I2", D(2022, 1, 1), None, 10.0)])
    o = lambda d: delivery.lead_time_on(lt, d, context=CTX).set_index(["sup_key", "itm_key"])
    a = o(D(2026, 7, 31))
    assert a.lead_time_weeks.to_dict() == {("S1", "I1"): 16.0, ("S1", "I2"): 10.0} and a.previous_weeks.isna().all() and a.change_weeks.isna().all(), "valid_to is inclusive"
    b = o(D(2026, 8, 1))
    assert b.lead_time_weeks[("S1", "I1")] == 30.0 and b.previous_weeks[("S1", "I1")] == 16.0 and b.change_weeks[("S1", "I1")] == 14.0 and b.change_percent[("S1", "I1")] == pytest.approx(87.5), "valid_from is inclusive"
    assert pd.isna(b.change_weeks[("S1", "I2")])
    assert delivery.lead_time_on(lt, D(2021, 12, 31), context=CTX).empty
    with pytest.raises(FrameError, match="two lead time rows"):
        delivery.lead_time_on(pd.concat([lt, _lt([("S1", "I2", D(2025, 1, 1), None, 12.0)])]), D(2026, 1, 1), context=CTX)
    with pytest.raises(FrameError, match="lead_time_weeks must be numeric"):
        delivery.lead_time_on(lt.assign(lead_time_weeks="16"), D(2026, 1, 1), context=CTX)


def test_alerts_need_both_the_weeks_and_the_percent_and_a_previous_row():
    lt = _lt([("S1", "A", D(2022, 1, 1), D(2026, 7, 31), 16.0), ("S1", "A", D(2026, 8, 1), None, 24.0),
              ("S1", "B", D(2022, 1, 1), D(2026, 7, 31), 40.0), ("S1", "B", D(2026, 8, 1), None, 48.0),
              ("S1", "C", D(2022, 1, 1), D(2026, 7, 31), 10.0), ("S1", "C", D(2026, 8, 1), None, 17.0),
              ("S1", "D", D(2022, 1, 1), D(2026, 7, 31), 20.0), ("S1", "D", D(2026, 8, 1), None, 50.0),
              ("S1", "E", D(2022, 1, 1), None, 99.0)])
    on = delivery.lead_time_on(lt, D(2026, 8, 1), context=CTX)
    al = delivery.lead_time_alerts(on, context=CTX)
    assert al.itm_key.tolist() == ["D", "A"], "A: +8 weeks and +50 percent (on both boundaries, in); B: +8 weeks but +20 percent; C: +70 percent but +7 weeks; E has no previous row; sorted by the rise"
    assert delivery.lead_time_alerts(on, min_rise_weeks=7.0, context=CTX).itm_key.tolist() == ["D", "A", "C"]
    assert delivery.lead_time_alerts(on, min_rise_percent=20.0, context=CTX).itm_key.tolist() == ["D", "A", "B"]
    for k in ({"min_rise_weeks": -1}, {"min_rise_percent": True}, {"min_rise_weeks": "8"}):
        with pytest.raises(FrameError, match="must be a number"):
            delivery.lead_time_alerts(on, context=CTX, **k)
    with pytest.raises(FrameError, match="lead_time_on output"):
        delivery.lead_time_alerts(on.drop(columns="change_percent"), context=CTX)


def _perf_inputs():
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3", "PO-4"], "sup_key": ["S1", "S1", "S2", "S1"], "status": ["closed", "open", "open", "cancelled"]})
    pl = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-2", "PO-3", "PO-4"], "line_no": [1, 2, 1, 1, 1], "qty": [10.0, 5.0, 4.0, 2.0, 9.0],
                       "requested_date": [D(2026, 3, 10), D(2026, 3, 10), D(2026, 4, 1), D(2026, 3, 31), D(2026, 3, 10)]})
    gr = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-1", "PO-2", "PO-3", "PO-4"], "line_no": [1, 1, 2, 1, 1, 1], "receipt_date": [D(2026, 3, 5), D(2026, 3, 12), D(2026, 3, 13), D(2026, 4, 3), D(2026, 4, 2), D(2026, 3, 1)],
                       "qty_accepted": [6.0, 4.0, 5.0, 4.0, 2.0, 9.0]})
    return pl, po, gr


def test_recompute_counts_a_line_on_time_when_the_cumulative_accepted_quantity_is_reached_within_the_grace():
    pl, po, gr = _perf_inputs()
    r = delivery.supplier_performance_recompute(pl, po, gr, D(2026, 4, 30), context=CTX).set_index(["sup_key", "period"])
    assert r.loc[("S1", "2026-03"), ["po_count", "lines_due", "lines_on_time", "on_time_percent"]].tolist() == [1, 2, 1, 50.0], "line 1 completes on the 12th (due 10th plus 2 days: in), line 2 on the 13th (out); cancelled order left out"
    assert r.loc[("S1", "2026-04"), ["lines_due", "lines_on_time"]].tolist() == [1, 1], "received on the 3rd, due the 1st: exactly the grace"
    assert r.loc[("S2", "2026-03"), ["lines_due", "lines_on_time", "on_time_percent"]].tolist() == [1, 1, 100.0], "due 31 March, received 2 April: within the grace, counted in the month of the due date"
    assert delivery.supplier_performance_recompute(pl, po, gr, D(2026, 4, 30), grace_days=1, context=CTX).set_index(["sup_key", "period"]).loc[("S1", "2026-04"), "lines_on_time"] == 0
    assert delivery.supplier_performance_recompute(pl, po, gr, D(2026, 4, 30), grace_days=3, context=CTX).set_index(["sup_key", "period"]).loc[("S1", "2026-03"), "lines_on_time"] == 2


def test_recompute_as_of_date_leaves_out_later_dues_and_later_receipts():
    pl, po, gr = _perf_inputs()
    r = delivery.supplier_performance_recompute(pl, po, gr, D(2026, 3, 31), context=CTX).set_index(["sup_key", "period"])
    assert ("S1", "2026-04") not in r.index and r.loc[("S2", "2026-03"), "lines_due"] == 1, "due on the date counts, a line due later does not"
    assert r.loc[("S2", "2026-03"), "lines_on_time"] == 0, "the receipt of the 2nd is after the date: not yet received"
    early = delivery.supplier_performance_recompute(pl, po, gr, D(2026, 3, 11), context=CTX).set_index(["sup_key", "period"])
    assert early.loc[("S1", "2026-03"), "lines_on_time"] == 0, "the completing receipt of line 1 is on the 12th, after the date"


def test_recompute_refuses_bad_input_and_a_partial_receipt_is_never_on_time():
    pl, po, gr = _perf_inputs()
    short = gr.assign(qty_accepted=gr.qty_accepted.where(gr.po_key != "PO-2", 3.0))
    r = delivery.supplier_performance_recompute(pl, po, short, D(2026, 4, 30), context=CTX).set_index(["sup_key", "period"])
    assert r.loc[("S1", "2026-04"), "lines_on_time"] == 0
    for g in (-1, 1.5, True):
        with pytest.raises(FrameError, match="grace_days"):
            delivery.supplier_performance_recompute(pl, po, gr, D(2026, 4, 30), grace_days=g, context=CTX)
    with pytest.raises(FrameError, match="qty_accepted must be numeric"):
        delivery.supplier_performance_recompute(pl, po, gr.assign(qty_accepted="1"), D(2026, 4, 30), context=CTX)
    assert delivery.supplier_performance_recompute(pl, po, gr, D(2020, 1, 1), context=CTX).empty


def test_window_sums_the_lines_it_never_averages_the_monthly_percentages():
    perf = pd.DataFrame({"sup_key": ["S1", "S1", "S1", "S2"], "period": ["2026-01", "2026-02", "2026-03", "2026-02"], "lines_due": [100, 2, 10, 0], "lines_on_time": [90, 0, 5, 0]})
    w = delivery.supplier_performance_window(perf, "2026-01", "2026-02", context=CTX).set_index("sup_key")
    assert w.loc["S1", ["lines_due", "lines_on_time", "n_months"]].tolist() == [102, 90, 2] and w.loc["S1", "on_time_percent"] == pytest.approx(100 * 90 / 102), "not the mean of 90 and 0"
    assert np.isnan(w.loc["S2", "on_time_percent"]), "no lines due: no share"
    assert delivery.supplier_performance_window(perf, "2026-03", "2026-03", sup_key="S1", context=CTX).on_time_percent.tolist() == [50.0], "a one month window is inclusive on both ends"
    assert delivery.supplier_performance_window(perf, "2027-01", "2027-02", context=CTX).empty
    for a, b, m in (("2026-1", "2026-02", "YYYY-MM"), ("2026-02", "2026-01", "ends before"), (202601, "2026-02", "YYYY-MM")):
        with pytest.raises(FrameError, match=m):
            delivery.supplier_performance_window(perf, a, b, context=CTX)


def test_elements_per_spare_unit_counts_only_the_housing_types_in_service_and_is_null_without_spares():
    ge = pd.DataFrame({"element_type": ["transformer_station"] * 3 + ["substation", "cable", "substation"], "status": ["in_service"] * 4 + ["in_service", "planned"], "zone_key": ["Z1", "Z1", "Z2", "Z1", "Z1", "Z1"]})
    st = _st([("S1", "I1", 10.0), ("S1", "I2", 3.0), ("S1", "I9", 50.0), ("S2", "I1", 100.0)])
    r = delivery.elements_per_spare_unit(st, ge, items=["I1", "I2"], site="S1", context=CTX)
    assert r.iloc[0].tolist()[1:] == [4, 13.0, round(4 / 13, 1)] and pd.isna(r.iloc[0].zone_key), "4 housing elements; other site, other item, cable and planned are out"
    z = delivery.elements_per_spare_unit(st, ge, items=["I1"], site="S1", zone_keys=["Z2", "Z1"], context=CTX)
    assert z.zone_key.tolist() == ["Z1", "Z2"] and z.installed_elements.tolist() == [3, 1] and z.elements_per_spare_unit.tolist() == [0.3, 0.1]
    none = delivery.elements_per_spare_unit(_st([("S1", "I1", 0.0)]), ge, items=["I1"], site="S1", context=CTX)
    assert none.spare_units.tolist() == [0.0] and none.elements_per_spare_unit.isna().all() and none.installed_elements.tolist() == [4]
    assert delivery.elements_per_spare_unit(st, ge, items=["I1"], site="S1", element_types=["cable"], status="in_service", context=CTX).installed_elements.tolist() == [1]
    with pytest.raises(FrameError, match="gis.grid_element"):
        delivery.elements_per_spare_unit(st, ge.drop(columns="zone_key"), items=["I1"], site="S1", context=CTX)


def test_at_risk_items_combines_stock_slipping_lines_alerts_and_the_supplier_on_time_share():
    st = _st([("S1", "I1", 0.0), ("S1", "I2", 4.0), ("S1", "I3", 4.0), ("S1", "I4", 4.0), ("S2", "I2", 0.0)])
    ol = pd.DataFrame({"sup_key": ["S9", "S9", "S9", "S8", "S9"], "itm_key": ["I2", "I2", "I3", "I4", "I4"], "days_overdue": [5, 0, 0, 9, 0], "slip_days": [0, 0, 0, 9, 0]})
    al = pd.DataFrame({"sup_key": ["S9", "S8"], "itm_key": ["I3", "I4"]})
    wp = pd.DataFrame({"sup_key": ["S9"], "on_time_percent": [90.0]})
    a = delivery.at_risk_items(["I4", "I3", "I2", "I1"], st, ol, al, wp, site="S1", sup_key="S9", as_of=D(2026, 11, 30), context=CTX).set_index("itm_key")
    assert a.index.tolist() == ["I1", "I2", "I3", "I4"]
    assert a.stock_zero.to_dict() == {"I1": True, "I2": False, "I3": False, "I4": False}, "stock at S1 only"
    assert a.n_slipping_lines.to_dict() == {"I1": 0, "I2": 1, "I3": 0, "I4": 0}, "only this supplier, only lines overdue; zero slip and zero overdue is on plan"
    s2 = ol.assign(days_overdue=0, slip_days=[0, 0, 0, 0, 3])
    assert delivery.at_risk_items(["I4"], st, s2, al.iloc[:0], wp, site="S1", sup_key="S9", as_of=D(2026, 11, 30), context=CTX).n_slipping_lines.tolist() == [1], "promised later than requested, not yet overdue"
    assert a.lead_time_alert.to_dict() == {"I1": False, "I2": False, "I3": True, "I4": False} and a.at_risk.to_dict() == {"I1": True, "I2": True, "I3": True, "I4": False}
    assert not a.low_on_time.any()
    for pct, low in ((75.0, False), (74.9, True)):
        w = delivery.at_risk_items(["I4"], st, ol, al, wp.assign(on_time_percent=pct), site="S1", sup_key="S9", as_of=D(2026, 11, 30), context=CTX)
        assert w.low_on_time.tolist() == [low] and w.at_risk.tolist() == [low], "the threshold is below 75"
    n = delivery.at_risk_items(["I4"], st, ol, al, wp.iloc[:0], site="S1", sup_key="S9", as_of=D(2026, 11, 30), context=CTX)
    assert n.low_on_time.tolist() == [False] and n.on_time_percent.isna().all(), "no performance row: not low"


def test_review_fixes_null_keys_types_strings_and_ranges_are_refused_not_dropped():
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 10, 13))])
    st = _st([("S1", "I1", 0.0)])
    f = lambda r=rs, s=st, **k: delivery.blocked_projects(r, s, D(2026, 10, 31), items=["I1"], active=["P1"], context=CTX, **k)
    for col, val in (("site_key", None), ("needed_by_date", None), ("prj_key", None)):
        with pytest.raises(FrameError, match=col):
            f(rs.assign(**{col: val}))
    with pytest.raises(FrameError, match="qty_open must be numeric"):
        f(rs.assign(qty_open=np.nan))
    with pytest.raises(FrameError, match="on_hand must be numeric"):
        f(s=st.assign(on_hand=np.nan))
    with pytest.raises(FrameError, match="horizon_days"):
        f(horizon_days=10 ** 9)
    ge = pd.DataFrame({"element_type": ["cable", "substation"], "status": ["in_service"] * 2, "zone_key": ["Z1", "Z1"]})
    sp = _st([("S1", "I1", 10.0), ("S1", "I2", -4.0)])
    r = delivery.elements_per_spare_unit(sp, ge, items=["I1", "I2"], site="S1", element_types="cable", context=CTX).iloc[0]
    assert (r.installed_elements, r.spare_units, r.elements_per_spare_unit) == (1, 10.0, 0.1), "a text element type is one type, a negative balance does not cancel a positive one"
    assert delivery.elements_per_spare_unit(sp, ge, items=["I1"], site="S1", zone_keys=[], context=CTX).columns.tolist() == ["zone_key", "installed_elements", "spare_units", "elements_per_spare_unit"]
    for bad in ({"site": ["S1"]}, {"zone_keys": ["Z1", None]}):
        with pytest.raises(FrameError):
            delivery.elements_per_spare_unit(sp, ge, items=["I1"], **{"site": "S1", **bad}, context=CTX)
    lt = _lt([("S1", "A", D(2022, 1, 1), D(2026, 7, 31), 0.0), ("S1", "A", D(2026, 8, 1), None, 10.0), ("S1", "B", D(2026, 8, 1), D(2026, 7, 1), 5.0)])
    with pytest.raises(FrameError, match="ends before it starts"):
        delivery.lead_time_on(lt, D(2026, 8, 1), context=CTX)
    on = delivery.lead_time_on(lt.iloc[:2], D(2026, 8, 1), context=CTX)
    assert on.change_percent.isna().all() and delivery.lead_time_alerts(on, context=CTX).empty, "a previous lead time of zero gives no percent and no alert"
    with pytest.raises(FrameError, match="must be a number"):
        delivery.lead_time_alerts(on, min_rise_weeks=float("nan"), context=CTX)
    pl, po, gr = _perf_inputs()
    with pytest.raises(FrameError, match="negative quantity"):
        delivery.supplier_performance_recompute(pl, po, gr.assign(qty_accepted=-1.0), D(2026, 4, 30), context=CTX)
    with pytest.raises(FrameError, match="different types"):
        delivery.supplier_performance_recompute(pl, po, gr.assign(line_no=gr.line_no.astype(str)), D(2026, 4, 30), context=CTX)
    with pytest.raises(FrameError, match="without sup_key"):
        delivery.supplier_performance_recompute(pl, po.assign(sup_key=None), gr, D(2026, 4, 30), context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        delivery.supplier_performance_recompute(pl.assign(requested_date=None), po, gr, D(2026, 4, 30), context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        delivery.supplier_performance_recompute(pl, po, gr.assign(receipt_date=None), D(2026, 4, 30), context=CTX)
    perf = pd.DataFrame({"sup_key": ["S1", "S1"], "period": ["2026-01", "2026-02"], "lines_due": [10, 10], "lines_on_time": [5, 5]})
    for bad_period in ("2026-13", "abcd-ef", "2026-00"):
        with pytest.raises(FrameError, match="YYYY-MM"):
            delivery.supplier_performance_window(perf, bad_period, "2027-01", context=CTX)
    for bad in (pd.concat([perf, perf.iloc[:1]]), perf.assign(lines_on_time=[11, 5]), perf.assign(lines_due=[np.nan, 10]), perf.assign(sup_key=[None, "S1"])):
        with pytest.raises(FrameError):
            delivery.supplier_performance_window(bad, "2026-01", "2026-02", context=CTX)


def test_at_risk_validates_the_date_and_one_row_per_supplier():
    st, ol = _st([("S1", "I1", 4.0)]), pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []})
    al, wp = pd.DataFrame({"sup_key": [], "itm_key": []}), pd.DataFrame({"sup_key": ["S9"], "on_time_percent": [90.0]})
    for bad in ("garbage", 12345, None):
        with pytest.raises(FrameError, match="as_of"):
            delivery.at_risk_items(["I1"], st, ol, al, wp, site="S1", sup_key="S9", as_of=bad, context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        delivery.at_risk_items(["I1"], st, ol, al, pd.concat([wp, wp]), site="S1", sup_key="S9", as_of=D(2026, 1, 1), context=CTX)


def _stk(rows, day):
    return _st(rows).assign(as_of=pd.Timestamp(day))


def test_second_review_a_stock_frame_of_another_date_is_refused_not_read_as_the_stock_of_the_date():
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 10, 13))])
    stale = _stk([("S1", "I1", 5.0)], "2026-07-31")
    fresh = _stk([("S1", "I1", 0.0)], "2026-11-30")
    with pytest.raises(FrameError, match="2026-07-31, not for 2026-11-30"):
        delivery.blocked_projects(rs, stale, D(2026, 11, 30), items=["I1"], active=["P1"], context=CTX)
    assert delivery.blocked_projects(rs, fresh, "2026-11-30", items=["I1"], active=["P1"], context=CTX).items.unmet_qty.tolist() == [4.0], "a frame of the same date is read"
    with pytest.raises(FrameError, match="not for 1999-01-01"):
        delivery.at_risk_items(["I1"], fresh, pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []}), pd.DataFrame({"sup_key": [], "itm_key": []}),
                               pd.DataFrame({"sup_key": [], "on_time_percent": []}), site="S1", sup_key="S9", as_of="1999-01-01", context=CTX)
    with pytest.raises(FrameError, match="not for 2026-11-30"):
        delivery.elements_per_spare_unit(stale, pd.DataFrame({"element_type": ["substation"], "status": ["in_service"], "zone_key": ["Z1"]}), items=["I1"], site="S1", as_of="2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="more than one date|is for"):
        delivery.blocked_projects(rs, pd.concat([stale, fresh]), D(2026, 11, 30), items=["I1"], active=["P1"], context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        delivery.blocked_projects(rs, fresh.assign(as_of=pd.NaT), D(2026, 11, 30), items=["I1"], active=["P1"], context=CTX)


def test_second_review_spare_cover_counts_the_elements_commissioned_by_the_date():
    ge = pd.DataFrame({"element_type": ["substation"] * 4, "status": ["in_service"] * 4, "zone_key": ["Z1", "Z1", "Z2", "Z2"],
                       "commissioned_date": [D(2023, 1, 1), D(2024, 8, 31), D(2024, 9, 1), D(2025, 1, 1)]})
    f = lambda day, **k: delivery.elements_per_spare_unit(_stk([("S1", "I1", 2.0)], day), ge, items=["I1"], site="S1", context=CTX, **k).iloc[0]
    assert f("2024-08-30").installed_elements == 1 and f("2024-08-31").installed_elements == 2, "the commissioning day itself is in"
    assert f("2024-08-31").elements_per_spare_unit == 1.0 and f("2026-07-31").installed_elements == 4 and f("2022-12-31").installed_elements == 0
    z = delivery.elements_per_spare_unit(_st([("S1", "I1", 2.0)]), ge, items=["I1"], site="S1", as_of="2024-09-01", zone_keys=["Z2", "Z1"], context=CTX)
    assert z.installed_elements.tolist() == [2, 1], "an explicit as_of dates a stock frame without as_of column"
    assert delivery.elements_per_spare_unit(_st([("S1", "I1", 2.0)]), ge, items=["I1"], site="S1", context=CTX).installed_elements.tolist() == [4], "no date: every element of the frame"
    with pytest.raises(FrameError, match="commissioned_date"):
        delivery.elements_per_spare_unit(_st([("S1", "I1", 2.0)]), ge.drop(columns="commissioned_date"), items=["I1"], site="S1", as_of="2024-09-01", context=CTX)
    with pytest.raises(FrameError, match="more than one date"):
        delivery.elements_per_spare_unit(pd.concat([_stk([("S1", "I1", 2.0)], "2024-01-01"), _stk([("S1", "I1", 2.0)], "2024-02-01")]), ge, items=["I1"], site="S1", context=CTX)
    many = pd.DataFrame({"element_type": ["substation"] * 12, "status": ["in_service"] * 12, "zone_key": [f"Z{i:02d}" for i in range(12)]})
    zk = delivery.elements_per_spare_unit(_st([("S1", "I1", 2.0)]), many, items=["I1"], site="S1", zone_keys={f"Z{i:02d}" for i in range(11, -1, -1)}, context=CTX).zone_key.tolist()
    assert zk == sorted(zk) and len(zk) == 12, "one row per zone, in key order"


def test_second_review_a_repeated_receipt_row_is_refused_not_counted_twice():
    pl = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "qty": [10.0], "requested_date": [D(2026, 3, 10)]})
    po = pd.DataFrame({"po_key": ["PO-1"], "sup_key": ["S1"], "status": ["open"]})
    one = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "receipt_no": [1], "receipt_date": [D(2026, 3, 10)], "qty_accepted": [6.0]})
    run = lambda g, **k: delivery.supplier_performance_recompute(pl, po, g, D(2026, 4, 30), context=CTX, **k)
    assert run(one).lines_on_time.tolist() == [0], "6 of 10 is a partial receipt"
    with pytest.raises(FrameError, match="more than one row"):
        run(pd.concat([one, one]))
    with pytest.raises(FrameError, match="identical rows"):
        run(pd.concat([one, one]).drop(columns="receipt_no"))
    two = pd.concat([one, one.assign(receipt_no=2)])
    assert run(two).lines_on_time.tolist() == [1], "two receipts with their own numbers add up to 12"
    assert run(one.drop(columns="receipt_no")).lines_on_time.tolist() == [0]
    assert run(one.assign(line_no=np.int32(1)).astype({"line_no": "int32"})).lines_on_time.tolist() == [0], "int32 against int64 is the same kind"
    with pytest.raises(FrameError, match="different types"):
        run(one.assign(line_no="1"))


def test_second_review_the_alert_default_is_8_weeks_and_25_percent_exactly():
    lt = _lt([("S", "A", D(2022, 1, 1), D(2026, 7, 31), 32.0), ("S", "A", D(2026, 8, 1), None, 40.0),
              ("S", "B", D(2022, 1, 1), D(2026, 7, 31), 33.0), ("S", "B", D(2026, 8, 1), None, 41.0),
              ("S", "C", D(2022, 1, 1), D(2026, 7, 31), 8.0), ("S", "C", D(2026, 8, 1), None, 10.0),
              ("S", "D", D(2022, 1, 1), D(2026, 7, 31), 16.0), ("S", "D", D(2026, 8, 1), None, 24.0),
              ("S", "E", D(2022, 1, 1), D(2026, 7, 31), 100.0), ("S", "E", D(2026, 8, 1), None, 108.0)])
    on = delivery.lead_time_on(lt, "2026-08-01", context=CTX)
    assert delivery.lead_time_alerts(on, context=CTX).itm_key.tolist() == ["A", "D"], "A is +8 weeks and exactly +25.0 percent: in; B is +8 weeks and +24.2 percent: out; E +8 weeks and +8 percent: out"


def test_second_review_fractional_open_quantity_horizon_bound_rounding_and_the_first_completing_receipt():
    rs = _rs([("P1", "I1", "S1", 0.25, D(2026, 10, 13))])
    st = _st([("S1", "I1", 0.0)])
    assert delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1"], horizon_days=0, context=CTX).items.unmet_qty.tolist() == [0.25], "a quarter unit is still open"
    assert delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1"], horizon_days=36500, context=CTX).items.unmet_qty.tolist() == [0.25]
    with pytest.raises(FrameError, match="horizon_days"):
        delivery.blocked_projects(rs, st, D(2026, 10, 31), items=["I1"], active=["P1"], horizon_days=36501, context=CTX)
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "sup_key": ["S1"] * 3, "status": ["open"] * 3})
    pl = pd.DataFrame({"po_key": po.po_key, "line_no": [1, 1, 1], "qty": [10.0] * 3, "requested_date": [D(2026, 3, 10)] * 3})
    gr = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-2", "PO-3"], "line_no": [1] * 4, "receipt_no": [1, 2, 1, 1], "receipt_date": [D(2026, 3, 10), D(2026, 3, 30), D(2026, 3, 10), D(2026, 3, 10)], "qty_accepted": [10.0, 5.0, 10.0, 10.0]})
    r = delivery.supplier_performance_recompute(pl, po, gr, D(2026, 4, 30), context=CTX)
    assert r.lines_on_time.tolist() == [3], "PO-1 was complete on the 10th; the later extra receipt does not make it late"
    one3 = pd.DataFrame({"sup_key": ["S1"], "period": ["2026-03"], "lines_due": [3], "lines_on_time": [1]})
    assert delivery.supplier_performance_window(one3, "2026-03", "2026-03", context=CTX).on_time_percent.tolist() == [100.0 / 3], "the window share is not rounded"
    g3 = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "receipt_no": [1], "receipt_date": [D(2026, 3, 10)], "qty_accepted": [10.0]})
    p = delivery.supplier_performance_recompute(pl, po, g3, D(2026, 4, 30), context=CTX)
    assert p.lines_due.tolist() == [3] and p.lines_on_time.tolist() == [1] and p.on_time_percent.tolist() == [33.3], "one decimal"


def test_second_review_at_risk_shows_the_line_count_and_the_items_without_a_stock_row():
    st = _st([("S1", "I1", 4.0)])
    ol = pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []})
    al = pd.DataFrame({"sup_key": [], "itm_key": []})
    wp = pd.DataFrame({"sup_key": ["S9"], "on_time_percent": [0.0], "lines_due": [2]})
    a = delivery.at_risk_items(["I1", "ITM-TYPO"], st, ol, al, wp, site="S1", sup_key="S9", as_of="2026-11-30", min_lines=5, context=CTX).set_index("itm_key")
    assert a.lines_due.tolist() == [2.0, 2.0] and a.thin_window.all() and a.low_on_time.all(), "a thin window still flags, with its line count and the thin mark"
    assert a.no_stock_row.to_dict() == {"I1": False, "ITM-TYPO": True} and a.stock_zero.to_dict() == {"I1": False, "ITM-TYPO": True}
    b = delivery.at_risk_items(["I1"], st, ol, al, wp.assign(lines_due=5), site="S1", sup_key="S9", as_of="2026-11-30", min_lines=5, context=CTX)
    assert not b.thin_window.any(), "five lines is not below five"
    c = delivery.at_risk_items(["I1"], st, ol, al, wp.drop(columns="lines_due"), site="S1", sup_key="S9", as_of="2026-11-30", context=CTX)
    assert c.lines_due.isna().all() and not c.thin_window.any()
    for bad in (-1, True, 2.5):
        with pytest.raises(FrameError, match="min_lines"):
            delivery.at_risk_items(["I1"], st, ol, al, wp, site="S1", sup_key="S9", as_of="2026-11-30", min_lines=bad, context=CTX)


def test_third_review_a_raw_stock_level_table_of_many_snapshots_is_refused_not_summed_over_every_date():
    raw = pd.DataFrame({"site_key": ["S1"] * 3, "itm_key": ["I1"] * 3, "as_of_date": pd.to_datetime(["2026-09-30", "2026-10-31", "2026-11-30"]), "on_hand": [5.0, 3.0, 0.0]})
    rs = _rs([("P1", "I1", "S1", 4.0, D(2026, 10, 13))])
    ge = pd.DataFrame({"element_type": ["substation"], "status": ["in_service"], "zone_key": ["Z1"]})
    ol = pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []})
    al, wp = pd.DataFrame({"sup_key": [], "itm_key": []}), pd.DataFrame({"sup_key": [], "on_time_percent": []})
    for call in (lambda st, **k: delivery.blocked_projects(rs, st, "2026-11-30", items=["I1"], active=["P1"], context=CTX, **k),
                 lambda st, **k: delivery.elements_per_spare_unit(st, ge, items=["I1"], site="S1", context=CTX, **k),
                 lambda st, **k: delivery.at_risk_items(["I1"], st, ol, al, wp, site="S1", sup_key="S9", as_of="2026-11-30", context=CTX, **k)):
        with pytest.raises(FrameError, match="more than one date|is for"):
            call(raw)
        with pytest.raises(FrameError, match="more than one row for S1 I1"):
            call(raw.drop(columns="as_of_date"))
        with pytest.raises(FrameError, match="more than one row for S1 I1"):
            call(raw.assign(as_of_date=pd.Timestamp("2026-11-30")))
    one = raw.iloc[[2]]
    assert delivery.blocked_projects(rs, one, "2026-11-30", items=["I1"], active=["P1"], context=CTX).items.unmet_qty.tolist() == [4.0], "one snapshot of the date is read"
    with pytest.raises(FrameError, match="2026-10-31, not for 2026-11-30"):
        delivery.blocked_projects(rs, raw.iloc[[1]], "2026-11-30", items=["I1"], active=["P1"], context=CTX)
    assert np.isnan(delivery.elements_per_spare_unit(one, ge, items=["I1"], site="S1", context=CTX).elements_per_spare_unit.iloc[0]), "no spare unit on the date: null, not 8 summed"


def test_third_review_the_thinnest_window_has_no_line_at_all_and_is_marked_thin():
    st = _st([("S1", "I1", 4.0)])
    ol = pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []})
    al = pd.DataFrame({"sup_key": [], "itm_key": []})
    wp = pd.DataFrame({"sup_key": ["S8"], "on_time_percent": [50.0], "lines_due": [2]})
    run = lambda w, **k: delivery.at_risk_items(["I1"], st, ol, al, w, site="S1", sup_key="S9", as_of="2026-11-30", context=CTX, **k)
    a = run(wp, min_lines=5)
    assert a.thin_window.tolist() == [True] and a.lines_due.isna().all(), "a supplier with no row in the window frame has no lines: thin"
    assert not run(wp).thin_window.any(), "no min_lines, no thin mark"
    assert run(wp.drop(columns="lines_due").assign(sup_key="S9"), min_lines=5).thin_window.tolist() == [True], "no lines_due column: the count is unknown, thin"
    assert run(wp.assign(sup_key="S9", lines_due=5), min_lines=5).thin_window.tolist() == [False]


def test_second_review_input_hygiene_day_first_dates_null_periods_and_list_keys():
    lt = _lt([("S1", "A", D(2022, 1, 1), None, 10.0)])
    with pytest.raises(FrameError, match="ISO"):
        delivery.lead_time_on(lt, "01-08-2026", context=CTX)
    with pytest.raises(FrameError, match="ISO"):
        delivery.blocked_projects(_rs([]), _st([]), "13/08/2026", items=["I"], active=["P"], context=CTX)
    assert delivery.lead_time_on(lt, " 2026-08-01 ", context=CTX).shape[0] == 1 and delivery.lead_time_on(lt, pd.Timestamp(2026, 8, 1), context=CTX).shape[0] == 1
    perf = pd.DataFrame({"sup_key": ["S1", "S1"], "period": [None, "2026-02"], "lines_due": [10, 10], "lines_on_time": [5, 5]})
    with pytest.raises(FrameError, match="without period"):
        delivery.supplier_performance_window(perf, "2026-01", "2026-02", context=CTX)
    ok = perf.assign(period=["2026-01", "2026-02"])
    for bad in (["S1"], ("S1",), 5):
        with pytest.raises(FrameError, match="sup_key is one key"):
            delivery.supplier_performance_window(ok, "2026-01", "2026-02", sup_key=bad, context=CTX)
    st, ol = _st([("S1", "I1", 4.0)]), pd.DataFrame({"sup_key": [], "itm_key": [], "slip_days": [], "days_overdue": []})
    with pytest.raises(FrameError, match="sup_key is one key"):
        delivery.at_risk_items(["I1"], st, ol, pd.DataFrame({"sup_key": [], "itm_key": []}), pd.DataFrame({"sup_key": ["S9"], "on_time_percent": [90.0]}), site="S1", sup_key=["S9"], as_of="2026-11-30", context=CTX)


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    for n in STOCK_AND_SUPPLIER_FUNCTIONS:
        m = reg[f"halvaro.delivery.supply.{n}"]
        assert m.parameters[-1] == "context" and m.sources          # the oracle pointers of these functions are kept in a file of the closed repository
    assert registry.check() == [] and {f"halvaro.delivery.supply.{n}" for n in STOCK_AND_SUPPLIER_FUNCTIONS} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}

