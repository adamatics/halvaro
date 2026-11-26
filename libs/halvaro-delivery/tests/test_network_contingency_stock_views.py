"""experience_network, contingency_advice, minimum_stock, supply_strain_answer and the views: hand computed frames, then the baseline."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")

# ------------------------------------------------------------------------------------------------- experience network
PR = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P1", "P2", "P2"], "emp_key": ["e1", "e2", "e2", "e3", "e1", "e3"], "project_role": ["foreman", "engineer", "lead", "fitter", "foreman", "fitter"],
                   "start": ["2025-01-01", "2025-03-01", "2025-07-01", "2026-01-01", "2025-02-01", "2025-02-15"], "end": ["2025-03-31", "2025-06-30", "2025-07-31", None, "2025-02-28", "2025-03-15"],
                   "hours_total": [100.0, 50.0, 25.0, 10.0, 8.0, 9.0], "basis": ["time_entries", "time_entries", "roster", "time_entries", "roster", "roster"]})
PRJ = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "type": ["dh_network", "dh_station", "dh_network"], "soil_class": ["clay", "sand", "clay"], "country": ["DE", "DK", "DE"], "legacy": [False, True, False]})
EMP = pd.DataFrame({"emp_key": ["e1", "e2", "e3"], "leave_date": [None, "2025-12-31", "2027-01-01"]})


def test_experience_network_edges_pairs_leavers_and_filters():
    n = delivery.experience_network(PR, PRJ, ["P1", "P2"], EMP, as_of="2026-11-30", context=CTX)
    e = n.edges.set_index(["prj_key", "emp_key"])
    assert e.loc[("P1", "e2"), "roles"] == "engineer; lead" and e.loc[("P1", "e2"), "hours_total"] == 75.0 and e.loc[("P1", "e2"), "basis"] == "mixed", "two role rows are one edge"
    assert str(e.loc[("P1", "e2"), "start"].date()) == "2025-03-01" and str(e.loc[("P1", "e2"), "end"].date()) == "2025-07-31" and bool(e.loc[("P2", "e1"), "legacy"])
    assert str(e.loc[("P1", "e3"), "end"].date()) == "2026-11-30", "an open period runs to the as-of day"
    p = n.pairs.set_index(["prj_key", "emp_a", "emp_b"])
    assert p.loc[("P1", "e1", "e2"), "overlap_days"] == 31 and str(p.loc[("P1", "e1", "e2"), "overlap_start"].date()) == "2025-03-01"
    assert ("P1", "e1", "e3") not in p.index and ("P1", "e2", "e3") not in p.index and p.loc[("P2", "e1", "e3"), "overlap_days"] == 14, "both days inclusive: 15 to 28 February"
    lv = n.nodes.set_index("node_key")["leaver"]
    assert lv["e2"] and not lv["e1"] and not lv["e3"], "a leave date after the as-of day is not a leaver yet"
    assert n.nodes[n.nodes.kind == "project"].node_key.tolist() == ["P1", "P2"] and n.nodes.kind.tolist()[:3] == ["person"] * 3
    dk = delivery.experience_network(PR, PRJ, ["P1", "P2", "P3"], EMP, countries=["DK"], as_of="2026-11-30", context=CTX)
    assert set(dk.edges.prj_key) == {"P2"} and dk.pairs.prj_key.tolist() == ["P2"]
    cl = delivery.experience_network(PR, PRJ, ["P1", "P2", "P3"], None, soil_classes=["clay"], project_types=["dh_network"], as_of="2026-11-30", context=CTX)
    assert set(cl.edges.prj_key) == {"P1"} and not cl.nodes.leaver.any()
    same_day = delivery.experience_network(PR.assign(start=["2025-01-01", "2025-03-31", "2025-07-01", "2026-01-01", "2025-02-01", "2025-02-15"]), PRJ, ["P1"], as_of="2026-11-30", context=CTX)
    assert same_day.pairs.set_index(["emp_a", "emp_b"]).loc[("e1", "e2"), "overlap_days"] == 1, "one shared day"


def test_experience_network_refusals():
    with pytest.raises(FrameError, match="not in the project frame"):
        delivery.experience_network(PR, PRJ, ["P9"], context=CTX)
    with pytest.raises(FrameError, match="ends before"):
        delivery.experience_network(PR.assign(end=["2024-01-01"] + PR.end.tolist()[1:]), PRJ, ["P1"], as_of="2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="single text"):
        delivery.experience_network(PR, PRJ, ["P1"], countries="DE", context=CTX)
    with pytest.raises(FrameError, match="emp_key or start"):
        delivery.experience_network(PR.assign(start=[None] + PR.start.tolist()[1:]), PRJ, ["P1"], as_of="2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="more than one"):
        delivery.experience_network(PR, PRJ, ["P1"], pd.concat([EMP, EMP.iloc[:1]]), context=CTX)


# ------------------------------------------------------------------------------------------------- contingency
OD = pd.DataFrame({"measure": ["schedule"], "n": [10], "n_legacy": [4], "q25": [0.05], "median": [0.1], "q75": [0.2]})
CS = pd.DataFrame({"view": ["all_events"] * 3 + ["full_linked"], "cause_code": ["ground_conditions", "ground_conditions", "weather", "ground_conditions"], "days": [10, 20, 70, 99], "responsible_party": ["a", "b", "c", "a"]})
LN = pd.DataFrame({"prj_key": ["P1", "P1", "P2", "P2", "P2", "P3"], "type": ["tender"] * 5 + ["final"], "cst_key": ["CST-100", "CST-830", "CST-100", "CST-830", "CST-110", "CST-830"],
                   "amount": [950.0, 50.0, 1000.0, 60.0, 940.0, 999.0]})


def test_contingency_advice_method_net_of_the_existing_line_and_caveats():
    a = delivery.contingency_advice(OD, CS, LN, context=CTX)
    r = a.rows.set_index("measure")["value"]
    assert r["ground_share"] == 0.3 and r["schedule_overrun_q75"] == 20.0 and r["gross_percent"] == 6.0, "30 of 100 days times 20 percent"
    assert r["existing_percent"] == 4.0 and r["net_percent"] == 2.0, "CST-830 is 5 percent of P1 and 3 percent of P2 (median 4); the final type is not read"
    assert (a.n, a.n_legacy) == (10, 4) and "advice only" in a.caveats[0] and "4 of the 10" in a.caveats[1]
    assert delivery.contingency_advice(OD, CS, LN, projects=["P1"], context=CTX).rows.set_index("measure").loc["net_percent", "value"] == 1.0
    assert delivery.contingency_advice(OD.assign(q75=0.01), CS, LN, context=CTX).rows.set_index("measure").loc["net_percent", "value"] == 0.0, "never below zero"
    zero = pd.concat([LN, pd.DataFrame({"prj_key": ["P4", "P4"], "type": ["tender"] * 2, "cst_key": ["CST-100", "CST-110"], "amount": [500.0, 500.0]})])
    zr = delivery.contingency_advice(OD, CS, zero, context=CTX).rows.set_index("measure")["value"]
    assert zr["existing_percent"] == 3.0, "a project without the line counts as zero: the median of 5, 3 and 0 percent"
    none = delivery.contingency_advice(OD, CS, LN[LN.cst_key != "CST-830"], context=CTX)
    assert none.rows.set_index("measure").loc["existing_percent", "value"] == 0.0 and any("no tender estimate carries" in c for c in none.caveats)
    three = pd.concat([LN, pd.DataFrame({"prj_key": ["P5", "P5"], "type": ["tender"] * 2, "cst_key": ["CST-100", "CST-830"], "amount": [900.0, 100.0]})])
    assert delivery.contingency_advice(OD, CS, three, context=CTX).rows.set_index("measure").loc["existing_percent", "value"] == 5.0, "the median of 5, 3 and 10 percent, not the mean (6)"
    med = delivery.contingency_advice(OD, CS, LN, quantile="median", context=CTX).rows.set_index("measure")["value"]
    assert med["gross_percent"] == 3.0 and "schedule_overrun_median" in med.index
    fl = delivery.contingency_advice(OD, CS, LN, view="full_linked", context=CTX).rows.set_index("measure")["value"]
    assert fl["ground_share"] == 1.0


def test_contingency_advice_refusals():
    for kw, msg in ((dict(quantile="max"), "quantile"), (dict(ground_causes="ground_conditions"), "ground_causes"), (dict(view="x"), "no rows"), (dict(schedule_measure="cost"), "exactly one"), (dict(projects="P1"), "projects")):
        with pytest.raises(FrameError, match=msg):
            delivery.contingency_advice(OD, CS, LN, context=CTX, **kw)
    with pytest.raises(FrameError, match="zero"):
        delivery.contingency_advice(OD, CS.assign(days=0), LN, context=CTX)
    with pytest.raises(FrameError, match="null"):
        delivery.contingency_advice(OD.assign(q75=np.nan), CS, LN, context=CTX)


# ------------------------------------------------------------------------------------------------- minimum stock
MV = pd.DataFrame({"site_key": ["S"] * 6, "itm_key": ["I1", "I1", "I1", "I1", "I2", "I3"], "movement_date": ["2026-11-30", "2026-03-01", "2025-12-01", "2026-12-01", "2026-05-05", "2026-05-05"],
                   "movement_type": ["issue_project", "issue_ticket", "issue_project", "issue_project", "issue_project", "receipt"], "qty": [-5.0, -3.0, -100.0, -100.0, -1.0, 10.0]})
LT = pd.DataFrame({"sup_key": ["U", "U", "U"], "itm_key": ["I1", "I2", "I3"], "valid_from": ["2022-01-01"] * 3, "valid_to": [None] * 3, "lead_time_weeks": [10, 3, 3]})
ITEM = pd.DataFrame({"itm_key": ["I1", "I2", "I3"], "stocked": [True, False, True], "preferred_sup_key": ["U", "U", "U"]})


def test_minimum_stock_rule_window_and_stocked_items():
    m = delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", context=CTX)
    assert m.itm_key.tolist() == ["I1"], "I2 is not stocked, I3 had a receipt only, the issue after the date and the one 364 days back are outside"
    r = m.iloc[0]
    assert (r.n_issues, r.lead_time_weeks) == (2, 10.0) and r.rate_per_week == pytest.approx(8 / 52, abs=1e-4) and r.avg_issue_qty == 4.0
    assert r.min_qty == 6.0 and r.order_up_to_qty == 12.0 and r.cover_weeks == 39.0, "max(1, ceil(0.154 x 12) = 2, ceil(1.5 x 4) = 6); order up to max(7, ceil(6.92) = 7, 6 + 6)"
    long = delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", window_weeks=53, context=CTX).iloc[0]
    # 108 units in 3 issues over the 53 weeks since the first movement (2025-12-01, 365 days): rate 108 / 52.14 = 2.071; ceil(2.071 x 12) = 25; ceil(1.5 x 36) = 54 decides
    assert long.n_issues == 3 and long.avg_issue_qty == 36.0 and long.min_qty == 54.0 and long.order_up_to_qty == 108.0, "a wider window takes the issue of 2025-12-01; min = 1.5 x the average issue, order up to min + 54"
    assert delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", window_weeks=26, context=CTX).iloc[0].rate_per_week == pytest.approx(5 / 26, abs=1e-4), "the window divides the usage (only the issue of 30 November is inside 26 weeks)"
    floor = delivery.minimum_stock(MV[MV.itm_key == "I1"].assign(qty=[-1.0, -1.0, -1.0, -1.0]), LT, ITEM, "2026-11-30", min_floor=5.0, context=CTX).iloc[0]
    assert floor.min_qty == 5.0, "the floor decides when usage is small"
    with pytest.raises(FrameError, match="positive quantity"):
        delivery.minimum_stock(MV.assign(qty=[5.0] + MV.qty.tolist()[1:]), LT, ITEM, "2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="no lead time"):
        delivery.minimum_stock(MV, LT[LT.itm_key != "I1"], ITEM, "2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="ISO"):
        delivery.minimum_stock(MV, LT, ITEM, "30-11-2026", context=CTX)
    with pytest.raises(FrameError, match="usage_types"):
        delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", usage_types="issue_project", context=CTX)
    with pytest.raises(FrameError, match="window_weeks"):
        delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", window_weeks=0, context=CTX)


def test_minimum_stock_changes_with_lead_time_and_is_registered():
    mv = MV[MV.itm_key == "I1"].assign(qty=[-1.0, -1.0, -1.0, -1.0])
    fast = delivery.minimum_stock(mv, LT.assign(lead_time_weeks=[10, 3, 3]), ITEM, "2026-11-30", context=CTX).iloc[0]
    slow = delivery.minimum_stock(mv, LT.assign(lead_time_weeks=[400, 3, 3]), ITEM, "2026-11-30", context=CTX).iloc[0]
    assert fast.min_qty == 2.0 and slow.min_qty == np.ceil(2 / 52 * 402 - 1e-9) == 16.0 and slow.order_up_to_qty == 18.0, "the lead time drives the minimum: ceil(rate x (400 + 2)); order up to min + ceil(1.5 x average issue)"
    assert fast.history_weeks == 52.0
    assert "halvaro.delivery.supply.minimum_stock" in registry.registered() and "minimum_stock" in delivery.__all__


# ------------------------------------------------------------------------------------------------- supply strain answer
def test_supply_strain_answer_cuts_to_the_keys_and_names_customers():
    blocked = delivery.BlockedProjects(pd.DataFrame({"prj_key": ["P1", "P2"], "itm_key": ["I1", "I9"], "unmet_qty": [1, 2]}), pd.DataFrame({"prj_key": ["P1", "P2"]}))
    mk = lambda **k: pd.DataFrame(k)                                                                  # noqa: E731
    a = delivery.supply_strain_answer(("I1", "I2"), ("Z2", "Z1"), stock=mk(itm_key=["I1", "I9"], on_hand=[0, 5]), open_lines=mk(itm_key=["I2", "I9"], remaining=[1, 2]), blocked=blocked,
                                  lead_on=mk(sup_key=["U", "V"], itm_key=["I1", "I9"], lead_time_weeks=[16, 3]), alerts=mk(itm_key=["I1"], change_weeks=[8]), performance=mk(sup_key=["U", "V"], on_time_percent=[40, 90]),
                                  spot=mk(itm_key=["I9"], unit_price=[1.0]), thin_cover=mk(zone_key=[None, "Z1", "Z3"], elements_per_spare_unit=[1.0, 2.0, 3.0]),
                                  supply_zone=mk(zone_key=["Z1", "Z2", "Z3"], cus_key=["C1", "C2", "C3"]), customer=mk(cus_key=["C1", "C2", "C3"], name=["One", "Two", "Three"]), context=CTX)
    assert a.stock.itm_key.tolist() == ["I1"] and a.open_lines.itm_key.tolist() == ["I2"] and a.blocked_projects.prj_key.tolist() == ["P1"] and a.spot_orders.empty
    assert a.performance.sup_key.tolist() == ["U"], "only the suppliers of the listed items"
    assert a.thin_cover.zone_key.tolist()[1:] == ["Z1"] and a.thin_cover.shape[0] == 2, "the row for all zones and the listed zone"
    assert a.customers.name.tolist() == ["One", "Two"] and a.zones == ("Z1", "Z2") and a.items == ("I1", "I2"), "sorted keys, customers of the zones"
    with pytest.raises(FrameError, match="not in gis.supply_zone"):
        delivery.supply_strain_answer(("I1",), ("Z9",), stock=mk(itm_key=["I1"]), open_lines=mk(itm_key=["I1"]), blocked=blocked, lead_on=mk(sup_key=["U"], itm_key=["I1"]), alerts=mk(itm_key=["I1"]),
                                  performance=mk(sup_key=["U"]), spot=mk(itm_key=["I1"]), thin_cover=mk(zone_key=["Z1"]), supply_zone=mk(zone_key=["Z1"], cus_key=["C1"]), customer=mk(cus_key=["C1"], name=["One"]), context=CTX)
    with pytest.raises(FrameError, match="text keys"):
        delivery.supply_strain_answer((1,), ("Z1",), stock=mk(itm_key=["I1"]), open_lines=mk(itm_key=["I1"]), blocked=blocked, lead_on=mk(sup_key=["U"], itm_key=["I1"]), alerts=mk(itm_key=["I1"]),
                                  performance=mk(sup_key=["U"]), spot=mk(itm_key=["I1"]), thin_cover=mk(zone_key=["Z1"]), supply_zone=mk(zone_key=["Z1"], cus_key=["C1"]), customer=mk(cus_key=["C1"], name=["One"]), context=CTX)


# ------------------------------------------------------------------------------------------------- views
def test_views_are_chart_ready_frames_with_labels_and_no_currency_mixing():
    tl = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02", "2025-12-20"]), "kind": ["meeting", "decision", "delay_event", "risk"], "source": ["m", "d", "e", "r"],
                       "source_key": ["MTG-1", "1", "2", "3"], "text": ["y", "x", "z", "w"]})
    att = pd.DataFrame({"mtg_key": ["MTG-1"] * 3, "present": [True, False, True]})
    v = delivery.timeline_view(tl, att, {"date": "2025-12-18", "amount": 1500000, "currency": "EUR"}, as_of="2026-11-30", context=CTX)
    assert v.frame.lane.tolist() == ["meeting", "decision", "delay_event", "write_down", "risk"], "the order of the timeline is kept (a meeting before its decision on the same date); the write-down follows the last row on or before its date"
    assert v.frame.n_present.iloc[0] == 2 and v.frame.n_invited.iloc[0] == 3 and "1500000 EUR" in v.frame.label.iloc[3] and "," not in v.frame.label.iloc[3] and v.labels == ("synthetic data",) and "as of 2026-11-30" in v.caption
    with pytest.raises(FrameError, match="nulls"):
        delivery.timeline_view(tl, att.assign(present=[True, None, True]), context=CTX)
    with pytest.raises(FrameError, match="write_down"):
        delivery.timeline_view(tl, None, {"date": "2025-12-18"}, context=CTX)
    ap = pd.DataFrame({"prj_key": ["P1", "P1"], "name": ["b", "a"], "baseline_start": ["2025-02-01", "2025-01-01"], "baseline_end": ["2025-03-01", "2025-01-31"], "latest_start": ["2025-02-01", "2025-01-01"],
                       "latest_end": ["2025-03-15", "2025-01-31"], "actual_start": [None, "2025-01-05"], "actual_end": [None, "2025-02-10"], "critical": [True, False]})
    g = delivery.gantt_view(ap, context=CTX).frame
    assert g.name.tolist()[:3] == ["a", "a", "a"] and g[g.name == "b"].series.tolist() == ["baseline", "latest"], "no actual bar without an actual start; sorted by the baseline start"
    prog = ap.assign(actual_start=[None, "2025-01-05"], actual_end=[None, None])
    assert "actual" not in set(delivery.gantt_view(prog, context=CTX).frame.series) and "without an as-of day" in delivery.gantt_view(prog, context=CTX).caption
    gp = delivery.gantt_view(prog, as_of="2025-03-01", context=CTX).frame
    row = gp[(gp.name == "a") & (gp.series == "actual")].iloc[0]
    assert bool(row.in_progress) and str(row.end.date()) == "2025-03-01", "an unfinished activity runs to the as-of day"
    coded = ap.assign(activity_code=["A001", "A002"], name=["same", "same"])
    assert set(delivery.gantt_view(coded, context=CTX).frame.activity_code) == {"A001", "A002"}, "the activity code is the key, a repeated name is harmless"
    with pytest.raises(FrameError, match="more than one row"):
        delivery.gantt_view(ap.assign(name=["a", "a"], prj_key="P1"), context=CTX)
    with pytest.raises(FrameError, match="ends before"):
        delivery.gantt_view(ap.assign(baseline_end=["2024-01-01", "2025-01-31"]), context=CTX)
    ln = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P2", "P2", "P3"], "type": ["tender", "final", "final", "tender", "final", "tender"], "category": ["labour", "labour", "materials", "labour", "labour", "labour"],
                       "amount": [100.0, 130.0, 20.0, 50.0, 40.0, 999.0], "currency": ["EUR", "EUR", "EUR", "DKK", "DKK", "EUR"]})
    w = delivery.waterfall_view(ln, context=CTX)
    f = w.frame.set_index(["currency", "category"])
    assert f.loc[("EUR", "labour"), "delta"] == 30.0 and f.loc[("EUR", "total"), "delta"] == 50.0 and f.loc[("DKK", "total"), "delta"] == -10.0 and w.extra["n_projects"] == 2, "P3 has no final: left out; currencies apart"
    wn = ln.assign(category=ln.category.where(ln.index != 1, None))
    assert delivery.waterfall_view(wn, context=CTX).frame.set_index(["currency", "category"]).loc[("EUR", "total"), "delta"] == 50.0, "a null category stays in the total, as '(none)'"
    mixed = ln.assign(currency=["EUR", "DKK", "DKK", "DKK", "DKK", "EUR"])
    assert delivery.waterfall_view(mixed, context=CTX).extra["n_projects"] == 1, "a project whose two types are in different currencies has no step"
    with pytest.raises(FrameError, match="must differ"):
        delivery.waterfall_view(ln, from_type="tender", to_type="tender", context=CTX)
    cs = pd.DataFrame({"view": ["all_events"] * 3, "cause_code": ["a", "a", "b"], "days": [10, 20, 70], "events": [1, 2, 3]})
    cb = delivery.cause_bars_view(cs, context=CTX).frame
    assert cb.cause_code.tolist() == ["b", "a"] and cb.share.tolist() == [0.7, 0.3] and cb.events.tolist() == [3, 3]
    nc = delivery.cause_bars_view(cs.assign(cause_code=["a", None, "b"]), context=CTX).frame
    assert "(unknown)" in set(nc.cause_code) and nc.days.sum() == 100, "a null cause is a bar of its own, not dropped"
    assert delivery.cause_bars_view(cs, as_of="2026-11-30", legacy=4, context=CTX).caption.count("4 legacy projects") == 1
    at = pd.DataFrame({"mtg_key": ["M1", "M1", "M2"], "date": ["2025-01-05", "2025-01-05", "2025-01-20"], "present": [True, False, True], "meeting_type": ["steering"] * 3})
    h = delivery.attendance_view(at, context=CTX).frame
    assert h.n_rows.tolist() == [3] and h.n_present.tolist() == [2] and h.absence_rate.tolist() == [0.3333] and h.n_meetings.tolist() == [2]
    hv = delivery.attendance_view(at, context=CTX)
    assert (hv.x, hv.y, hv.value) == ("period", "meeting_type", "absence_rate")
    nm = delivery.attendance_view(at.assign(meeting_type=["steering", None, "steering"]), context=CTX).frame
    assert nm.n_rows.sum() == 3 and "unknown" in set(nm.meeting_type), "a null meeting type is shown, not dropped"
    with pytest.raises(FrameError, match="nulls"):
        delivery.attendance_view(at.assign(present=[True, None, True]), context=CTX)
    sk = pd.DataFrame({"as_of": ["2026-01-01"] * 2, "site_key": ["S"] * 2, "itm_key": ["I1", "I2"], "on_hand": [1.0, 2.0], "reserved": [0.0, 1.0], "available": [1.0, 1.0]})
    s = delivery.stock_view(sk, pd.DataFrame({"itm_key": ["I1"], "remaining": [3.0], "promised_date": ["2026-03-01"]}), context=CTX)
    assert len(s.frame) == 6 and s.extra["orders"].remaining.tolist() == [3.0]
    pf = delivery.performance_view(pd.DataFrame({"sup_key": ["U", "U"], "lines_due": [10, 30], "lines_on_time": [10, 15]}), context=CTX).frame
    assert pf.on_time_percent.tolist() == [62.5], "from the summed lines (25 of 40), not the mean of 100 and 50"
    with pytest.raises(FrameError, match="more lines on time"):
        delivery.performance_view(pd.DataFrame({"sup_key": ["U"], "lines_due": [10], "lines_on_time": [12]}), context=CTX)
    n = delivery.experience_network(PR, PRJ, ["P1"], EMP, as_of="2026-11-30", context=CTX)
    nv = delivery.experience_network_view(n, context=CTX)
    assert "1 leavers" in nv.caption and set(nv.extra) == {"nodes", "pairs"} and nv.n == len(n.edges)
    with pytest.raises(FrameError, match="result of experience_network"):
        delivery.experience_network_view(n.edges, context=CTX)
    for name in ("timeline_view", "gantt_view", "waterfall_view", "cause_bars_view", "attendance_view", "stock_view", "performance_view", "experience_network_view"):
        assert f"halvaro.delivery.views.{name}" in registry.registered() and name in delivery.__all__


def test_stage_refusal_of_new_functions():
    with pytest.raises(StageRefusal):
        delivery.minimum_stock(MV, LT, ITEM, "2026-11-30", context=Context(stage="month3", role="r"))


# ------------------------------------------------------------------------------------------------- baseline
@pytest.mark.release
def test_baseline_network_contingency_and_minimum_stock(load, release_dir):
    pj, role, emp = load("projects", "project"), load("projects", "project_role"), load("hr", "employee")
    comp = pj[(pj.country == "DE") & (pj.type == "dh_network") & (pj.soil_class == "clay")].prj_key.tolist()
    n = delivery.experience_network(role, pj, comp, emp, context=CTX)
    assert len(n.edges) <= len(role[role.prj_key.isin(comp)]) and n.edges.hours_total.sum() == pytest.approx(role[role.prj_key.isin(comp)].hours_total.sum(), abs=0.01), "the network is a view of the same rows (O12)"
    assert set(n.nodes[n.nodes.kind == "person"].node_key) == set(role[role.prj_key.isin(comp)].emp_key) and n.nodes.leaver.sum() > 0
    assert (n.pairs.overlap_days >= 1).all()
    pf = delivery.project_frame(pj, context=CTX).value
    ov = delivery.schedule_overrun(pf, "2026-11-30", context=CTX)
    a = delivery.contingency_advice(delivery.overrun_distribution(ov, pf, context=CTX), delivery.cause_shares(load("projects", "delay_event"), pf, context=CTX),
                                    delivery.estimate_bridge(load("projects", "estimate_version"), load("projects", "estimate_line"), load("projects", "cost_code"), context=CTX).lines, context=CTX)
    r = a.rows.set_index("measure")["value"]
    assert 0 < r["ground_share"] < 1 and a.n == 307 and a.n_legacy == 150 and r["net_percent"] == max(r["gross_percent"] - r["existing_percent"], 0)
    ms = delivery.minimum_stock(load("inventory", "stock_movement"), load("inventory", "lead_time"), load("inventory", "item"), "2026-11-30", context=CTX)
    sl = load("inventory", "stock_level")
    j = ms.merge(sl[sl.as_of_date == sl.as_of_date.max()][["site_key", "itm_key", "min_level"]], on=["site_key", "itm_key"])
    assert len(j) > 1000 and (j.min_qty >= 1).all() and (j.order_up_to_qty > j.min_qty).all()
    assert ((j.min_qty - j.min_level).abs() <= 1).mean() > 0.4, "LOW: the generator sizes the level on planned demand, the library on issues; about half the pairs are within one unit (measured, see notes)"


def test_minimum_stock_thin_history_nulls_and_missing_items():
    mv = pd.DataFrame({"site_key": ["S", "S"], "itm_key": ["I1", "I1"], "movement_date": ["2023-01-01", "2023-01-10"], "movement_type": ["receipt", "issue_project"], "qty": [50.0, -7.0]})
    m = delivery.minimum_stock(mv, LT, ITEM, "2023-01-10", context=CTX).iloc[0]
    assert m.history_weeks == pytest.approx(10 / 7, abs=1e-2) and m.rate_per_week == pytest.approx(7 / (10 / 7), abs=1e-3), "the data starts inside the window: the rate is over the weeks that exist"
    with pytest.raises(FrameError, match="nulls"):
        delivery.minimum_stock(MV.assign(qty=[np.nan] + MV.qty.tolist()[1:]), LT, ITEM, "2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="does not hold"):
        delivery.minimum_stock(MV, LT, ITEM[ITEM.itm_key != "I1"], "2026-11-30", context=CTX)
    flagged = delivery.minimum_stock(MV, LT, ITEM.assign(critical=[True, False, False]), "2026-11-30", context=CTX)
    assert flagged.critical.tolist() == [True]


def test_experience_network_gaps_are_not_overlap_and_the_network_is_as_of():
    pr = pd.DataFrame({"prj_key": ["P1"] * 4, "emp_key": ["a", "a", "b", "c"], "project_role": ["x", "x", "y", "z"], "start": ["2025-01-01", "2025-08-01", "2025-04-01", "2026-03-01"],
                       "end": ["2025-03-31", "2025-09-30", "2025-06-30", None], "hours_total": [10.0, 10.0, 5.0, 1.0], "basis": ["time_entries"] * 4})
    prj = PRJ.iloc[:1]
    n = delivery.experience_network(pr, prj, ["P1"], as_of="2026-11-30", context=CTX)
    assert ("a", "b") not in set(zip(n.pairs.emp_a, n.pairs.emp_b)), "a worked 1 Jan to 31 Mar and 1 Aug to 30 Sep; b worked April to June: they never met"
    e = n.edges.set_index("emp_key")
    assert str(e.loc["a", "start"].date()) == "2025-01-01" and str(e.loc["a", "end"].date()) == "2025-09-30"
    both = pr.assign(emp_key=["a", "a", "b", "c"], start=["2025-01-01", "2025-08-01", "2025-09-01", "2026-03-01"], end=["2025-03-31", "2025-09-30", "2025-09-15", None])
    p = delivery.experience_network(both, prj, ["P1"], as_of="2026-11-30", context=CTX).pairs.set_index(["emp_a", "emp_b"])
    assert p.loc[("a", "b"), "overlap_days"] == 15 and str(p.loc[("a", "b"), "overlap_start"].date()) == "2025-09-01", "only the second stint of a meets b"
    adjacent = pr.assign(start=["2025-01-01", "2025-04-01", "2025-04-01", "2026-03-01"], end=["2025-03-31", "2025-06-30", "2025-06-30", None])
    ap = delivery.experience_network(adjacent, prj, ["P1"], as_of="2026-11-30", context=CTX).pairs.set_index(["emp_a", "emp_b"])
    assert ap.loc[("a", "b"), "overlap_days"] == 91, "stints that touch are merged and the days are counted once"
    early = delivery.experience_network(pr, prj, ["P1"], as_of="2025-05-01", context=CTX)
    assert "c" not in set(early.edges.emp_key), "a role that starts after the day does not exist yet"
    assert str(early.edges.set_index("emp_key").loc["a", "end"].date()) == "2025-05-01" or str(early.edges.set_index("emp_key").loc["a", "end"].date()) == "2025-03-31"
    cut = delivery.experience_network(pr.assign(end=["2025-03-31", "2025-09-30", "2025-06-30", None]), prj, ["P1"], as_of="2025-08-15", context=CTX).edges.set_index("emp_key")
    assert str(cut.loc["a", "end"].date()) == "2025-08-15", "a role that ends later is cut at the day"
    nul = delivery.experience_network(pr.assign(project_role=[None, "x", "y", "z"]), prj, ["P1"], as_of="2026-11-30", context=CTX).edges.set_index("emp_key")
    assert nul.loc["a", "roles"] == "(no role); x"
    lv = delivery.experience_network(pr, prj, ["P1"], pd.DataFrame({"emp_key": ["a"], "leave_date": ["2026-11-30"]}), as_of="2026-11-30", context=CTX).nodes.set_index("node_key")["leaver"]
    assert lv["a"] and not lv["b"], "a leave date equal to the as-of day is a leaver"


def test_open_tenders_from_the_stage_history_and_boundaries():
    from test_commercial import OPP
    hist = pd.DataFrame({"opp_key": ["O1", "O1", "O2", "O2", "O3"], "stage": ["lead", "tender", "lead", "tender", "lead"], "entered_date": ["2026-02-01", "2026-06-01", "2026-01-01", "2026-12-15", "2026-10-01"]})
    t = delivery.open_tenders(OPP, "2026-11-30", hist, context=CTX)
    assert t.opp_key.tolist() == ["O1"] and t.asof_exact.all() and t.stage.tolist() == ["tender"], "O2 only entered the tender stage on 15 December"
    assert not delivery.open_tenders(OPP, "2026-11-30", context=CTX).asof_exact.any()
    on_day = delivery.open_tenders(OPP, "2026-12-15", hist, context=CTX)
    assert set(on_day.opp_key) == {"O1", "O2"}, "a stage entered on the day counts on the day"
    created = delivery.open_tenders(OPP.assign(created_date=["2026-11-30"] + OPP.created_date.tolist()[1:]), "2026-11-30", context=CTX)
    assert "O1" in set(created.opp_key), "created on the day is created"
    dl = delivery.open_tenders(OPP.assign(bid_deadline=["2026-11-30"] + OPP.bid_deadline.tolist()[1:]), "2026-11-30", context=CTX).set_index("opp_key")
    assert dl.loc["O1", "days_to_deadline"] == 0 and not dl.loc["O1", "deadline_passed"], "a deadline on the day has not passed"
    nd = delivery.open_tenders(OPP.assign(bid_deadline=[None] + OPP.bid_deadline.tolist()[1:]), "2026-11-30", context=CTX).set_index("opp_key")
    assert nd.loc["O1", "deadline_passed"] is None or pd.isna(nd.loc["O1", "deadline_passed"])
    shuffled = OPP.iloc[::-1]
    assert delivery.open_tenders(shuffled, "2026-11-30", context=CTX).opp_key.tolist() == ["O2", "O1"]


def test_customer_projects_null_guards_and_active_count_with_a_planned_project():
    from test_commercial import CUS, CON, OPP, PRJ as CP
    with pytest.raises(FrameError, match="without a customer_key"):
        delivery.customer_projects(CUS, CP.assign(customer_key=[None, "C1", "C2"]), CON, context=CTX)
    with pytest.raises(FrameError, match="without a tier"):
        delivery.customer_projects(CUS.assign(tier=[None, "standard", "occasional"]), CP, CON, context=CTX)
    c = delivery.customer_projects(CUS, CP.assign(status=["planned", "completed", "active"]), CON, context=CTX).set_index("cus_key")
    assert c.loc["C1", "n_active"] == 0 and c.loc["C2", "n_active"] == 1, "a planned project is not active"
    cat = CUS.assign(tier=CUS.tier.astype("category"))
    assert delivery.customer_projects(cat, CP, CON, by="tier", context=CTX).tier.tolist() == ["anchor", "standard", "occasional"]


def test_supply_strain_answer_refuses_duplicate_customers():
    blocked = delivery.BlockedProjects(pd.DataFrame({"prj_key": ["P1"], "itm_key": ["I1"]}), pd.DataFrame({"prj_key": ["P1"]}))
    mk = lambda **k: pd.DataFrame(k)                                                                  # noqa: E731
    with pytest.raises(FrameError, match="more than one row for a customer"):
        delivery.supply_strain_answer(("I1",), ("Z1",), stock=mk(itm_key=["I1"]), open_lines=mk(itm_key=["I1"]), blocked=blocked, lead_on=mk(sup_key=["U"], itm_key=["I1"]), alerts=mk(itm_key=["I1"]),
                                  performance=mk(sup_key=["U"]), spot=mk(itm_key=["I1"]), thin_cover=mk(zone_key=["Z1"]), supply_zone=mk(zone_key=["Z1"], cus_key=["C1"]), customer=mk(cus_key=["C1", "C1"], name=["a", "b"]), context=CTX)


@pytest.mark.release
def test_baseline_pairs_from_role_rows_stage_history_and_views_from_real_outputs(load):
    pj, role = load("projects", "project"), load("projects", "project_role")
    keys = pj[(pj.country == "DE") & (pj.soil_class == "clay") & (pj.type == "dh_network")].prj_key.tolist()
    n = delivery.experience_network(role, pj, keys, context=CTX)
    r = role[role.prj_key.isin(keys)].assign(s=lambda f: pd.to_datetime(f.start), e=lambda f: pd.to_datetime(f.end))
    chk = r[r.prj_key == "PRJ-000001"]
    a, b = chk.emp_key.iloc[0], chk.emp_key.iloc[1]
    ov = sum(max((min(x.e, y.e) - max(x.s, y.s)).days + 1, 0) for x in chk[chk.emp_key == a].itertuples() for y in chk[chk.emp_key == b].itertuples())
    got = n.pairs[(n.pairs.prj_key == "PRJ-000001") & (((n.pairs.emp_a == a) & (n.pairs.emp_b == b)) | ((n.pairs.emp_a == b) & (n.pairs.emp_b == a)))]
    assert (got.overlap_days.iloc[0] if len(got) else 0) == ov, "overlap days are counted from the role rows, gaps excluded"
    o, hist = load("crm", "opportunity"), load("crm", "opportunity_stage_history")
    t = delivery.open_tenders(o, "2026-10-31", hist, context=CTX)
    assert t.asof_exact.all() and len(t) > 20 and set(t.stage) == {"tender"}
    early = delivery.open_tenders(o, "2025-06-30", hist, context=CTX)
    assert len(early) > 30 and early.opp_key.isin(o.opp_key).all(), "open tenders of a past day are rebuilt from the history, not empty"
    att = delivery.attendance(load("projects", "meeting"), load("projects", "meeting_attendance"), context=CTX)
    av = delivery.attendance_view(att.assign(meeting_type=att["meeting_type"] if "meeting_type" in att.columns else None), context=CTX)
    assert av.frame.n_rows.sum() == len(att)
    pa = delivery.activity_plan_vs_actual(load("projects", "plan_activity"), load("projects", "actual_activity"), context=CTX)
    gv = delivery.gantt_view(pa, as_of="2026-11-30", context=CTX)
    assert gv.frame.in_progress.sum() > 100 and set(gv.frame.series) == {"baseline", "latest", "actual"} and "activity_code" in gv.frame.columns
    pfr = delivery.project_frame(pj, context=CTX).value
    cs = delivery.cause_shares(load("projects", "delay_event"), pfr, context=CTX)
    cb = delivery.cause_bars_view(cs, context=CTX)
    assert cb.frame.days.sum() == cs[cs.view == "all_events"].days.sum() and cb.frame.share.sum() == pytest.approx(1.0, abs=1e-3)
    br = delivery.estimate_bridge(load("projects", "estimate_version"), load("projects", "estimate_line"), load("projects", "cost_code"), context=CTX)
    wv = delivery.waterfall_view(br.lines, context=CTX)
    assert set(wv.frame.currency) <= {"DKK", "EUR"} and wv.extra["n_projects"] > 50


def test_gantt_as_of_before_an_actual_start_hours_prorated_and_per_pair_history():
    ap = pd.DataFrame({"prj_key": ["P1", "P1", "P1"], "activity_code": ["A1", "A2", "A3"], "name": ["a", "b", "c"], "baseline_start": ["2025-01-01"] * 3, "baseline_end": ["2025-12-31"] * 3,
                       "latest_start": ["2025-01-01"] * 3, "latest_end": ["2025-12-31"] * 3, "actual_start": ["2025-02-01", "2025-09-01", "2025-03-01"], "actual_end": [None, None, "2025-10-31"], "critical": [False] * 3})
    g = delivery.gantt_view(ap, as_of="2025-06-30", context=CTX).frame
    act = g[g.series == "actual"].set_index("activity_code")
    assert set(act.index) == {"A1", "A3"}, "A2 starts after the day: no actual bar"
    assert str(act.loc["A1", "end"].date()) == "2025-06-30" and bool(act.loc["A1", "in_progress"]), "unfinished: runs to the day"
    assert str(act.loc["A3", "end"].date()) == "2025-06-30" and bool(act.loc["A3", "in_progress"]), "finishes after the day: cut at the day and still in progress on it"
    pr = pd.DataFrame({"prj_key": ["P1"], "emp_key": ["a"], "project_role": ["x"], "start": ["2025-01-01"], "end": ["2025-01-10"], "hours_total": [100.0], "basis": ["time_entries"]})
    e = delivery.experience_network(pr, PRJ.iloc[:1], ["P1"], as_of="2025-01-05", context=CTX).edges.iloc[0]
    assert e.hours_total == pytest.approx(50.0) and str(e.end.date()) == "2025-01-05", "5 of 10 days: half of the hours"
    assert delivery.experience_network(pr, PRJ.iloc[:1], ["P1"], as_of="2025-02-01", context=CTX).edges.hours_total.iloc[0] == 100.0
    mv = pd.DataFrame({"site_key": ["S", "S", "S2", "S2"], "itm_key": ["I1", "I1", "I1", "I1"], "movement_date": ["2023-01-01", "2026-11-30", "2026-10-01", "2026-11-30"],
                       "movement_type": ["receipt", "issue_project", "receipt", "issue_project"], "qty": [50.0, -5.0, 50.0, -5.0]})
    m = delivery.minimum_stock(mv, LT, ITEM, "2026-11-30", context=CTX).set_index("site_key")
    assert m.loc["S", "history_weeks"] == 52.0 and m.loc["S2", "history_weeks"] == pytest.approx(61 / 7, abs=0.01), "a pair that starts in October has 61 days of history"
    assert m.loc["S2", "rate_per_week"] > 5 * m.loc["S", "rate_per_week"]
    with pytest.raises(FrameError, match="nulls"):
        delivery.minimum_stock(MV, LT, ITEM.assign(critical=[None, True, True]), "2026-11-30", context=CTX)
    from test_commercial import OPP
    with pytest.raises(FrameError, match="does not hold"):
        delivery.open_tenders(OPP, "2026-11-30", pd.DataFrame({"opp_key": ["OX"], "stage": ["tender"], "entered_date": ["2026-01-01"]}), context=CTX)
