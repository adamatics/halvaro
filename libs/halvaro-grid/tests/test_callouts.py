"""Call-outs (plan 5.8): hand computed tickets, labour, rota and SLA clock (the release checks are in repo_tests of the closed repository)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")


def _tk(rows):
    return pd.DataFrame(rows, columns=["tkt_key", "team_key", "opened", "callout_kind", "labour_hours", "overtime_hours", "travel_hours"])


def _lb(rows):
    return pd.DataFrame(rows, columns=["tkt_key", "emp_key", "work_date", "team_key", "hours", "overtime_hours", "travel_hours"])


TK = _tk([("T1", "A", "2026-01-05 08:00", "office_hours", 10.0, 2.0, 1.0), ("T2", "A", "2026-01-30 20:00", "evening", 6.0, 1.0, 0.5), ("T3", "B", "2026-02-02 01:00", "night", 3.0, 3.0, 0.0)])
LB = _lb([("T1", "e1", "2026-01-05", "A", 6.0, 1.0, 0.5), ("T1", "e2", "2026-01-06", "B", 4.0, 1.0, 0.5), ("T2", "e1", "2026-01-30", "A", 4.0, 1.0, 0.5), ("T2", "e1", "2026-02-01", "A", 2.0, 0.0, 0.0),
          ("T3", "e3", "2026-02-02", "B", 3.0, 3.0, 0.0)])


def test_callout_summary_months_work_date_and_team_of_the_labour_row():
    r = grid.callout_summary(TK, LB, context=M12).set_index(["team_key", "period", "callout_kind"])
    assert r.loc[("A", "2026-01", "office_hours"), "n_tickets"] == 1 and r.loc[("A", "2026-01", "office_hours"), "labour_hours"] == 6.0, "T1: 6 h by A on the 5th"
    assert r.loc[("B", "2026-01", "office_hours"), "labour_hours"] == 4.0 and r.loc[("B", "2026-01", "office_hours"), "n_tickets"] == 0, "the helper team has hours but no ticket"
    assert r.loc[("A", "2026-01", "evening"), "labour_hours"] == 4.0 and r.loc[("A", "2026-02", "evening"), "labour_hours"] == 2.0 and r.loc[("A", "2026-02", "evening"), "n_tickets"] == 0, "T2 hours follow the work date"
    assert r.loc[("B", "2026-02", "night"), "overtime_hours"] == 3.0
    assert r.labour_hours.sum() == 19.0 and r.overtime_hours.sum() == 6.0 and r.travel_hours.sum() == 1.5
    w = grid.callout_summary(TK, LB, freq="week", window=("2026-01-05", "2026-01-11"), context=M12)
    assert w.period.unique().tolist() == ["2026-01-05"] and w.labour_hours.sum() == 10.0 and w.n_tickets.sum() == 1, "the Monday of the week, window on both sides"


def test_callout_summary_refusals():
    with pytest.raises(FrameError, match="does not hold"):
        grid.callout_summary(TK.iloc[:2], LB, context=M12)
    with pytest.raises(FrameError, match="differs"):
        grid.callout_summary(TK.assign(labour_hours=[10.0, 6.0, 9.0]), LB, context=M12)
    assert not grid.callout_summary(TK.assign(labour_hours=[10.0, 6.0, 3.019]), LB, context=M12).empty, "inside 0.02 h"
    with pytest.raises(FrameError, match="freq"):
        grid.callout_summary(TK, LB, freq="day", context=M12)
    with pytest.raises(FrameError, match="more than one"):
        grid.callout_summary(pd.concat([TK, TK.iloc[:1]]), LB, context=M12)
    with pytest.raises(FrameError, match="ends before"):
        grid.callout_summary(TK, LB, window=("2026-02-01", "2026-01-01"), context=M12)
    with pytest.raises(FrameError, match="null hours"):
        grid.callout_summary(TK, LB.assign(hours=[np.nan, 4.0, 4.0, 2.0, 3.0]), context=M12)


def test_on_call_week_boundaries_and_overlap():
    rota = pd.DataFrame({"team_key": ["A", "A", "B"], "week_start": ["2026-01-04", "2026-01-11", "2026-01-11"], "primary_emp_key": ["p1", "p2", "p3"], "secondary_emp_key": ["s1", "s2", "s3"]})
    assert grid.on_call(rota, "2026-01-10", context=M12).primary_emp_key.tolist() == ["p1"], "the last day of the first week"
    assert grid.on_call(rota, "2026-01-11", context=M12).primary_emp_key.tolist() == ["p2", "p3"]
    assert grid.on_call(rota, "2026-01-11", team_key="B", context=M12).secondary_emp_key.tolist() == ["s3"]
    assert grid.on_call(rota, "2025-12-01", context=M12).empty and grid.on_call(rota, "2026-01-18", team_key=["B"], context=M12).empty, "after the last week: nobody"
    stub = rota.assign(week_start=["2026-01-04", "2026-01-05", "2026-01-12"])
    assert grid.on_call(stub, "2026-01-04", context=M12).primary_emp_key.tolist() == ["p1"] and grid.on_call(stub, "2026-01-07", team_key="A", context=M12).primary_emp_key.tolist() == ["p2"], "a one day stub week ends where the next row starts (the baseline rota begins that way)"
    assert grid.on_call(stub, "2026-01-11", team_key="A", context=M12).empty is False and grid.on_call(stub, "2026-01-12", team_key="A", context=M12).empty, "the last row runs `days` days"
    with pytest.raises(FrameError, match="more than one row"):
        grid.on_call(pd.concat([rota, rota.iloc[:1]]), "2026-01-10", context=M12)
    with pytest.raises(FrameError, match="days"):
        grid.on_call(rota, "2026-01-10", days=0, context=M12)


def _sla(rows):
    return pd.DataFrame(rows, columns=["tkt_key", "team_key", "opened", "first_response_ts", "on_site_ts", "resolved_ts", "due_date", "ticket_type", "sla_met", "sla_response_target_h",
                                       "sla_attendance_target_h", "priority", "status", "response_h", "attendance_h"])


# DK, UTC+1 in January. T1: Friday 15:00 local to Monday 08:00 local: 1 h on Friday, 0 at the weekend, 1 h on Monday = 2.0 h; on site Monday 11:30 local = 1 + 4.5 = 5.5 h.
# T2: Monday 06:00 local, response 17:00 local: the day is clipped to 07:00 to 16:00 = 9.0 h against a target of 4. T3, T4: planned, due 2026-01-10 plus 14 days = 24 January local.
SLA = _sla([("T1", "A", "2026-01-09 14:00", "2026-01-12 07:00", "2026-01-12 10:30", "2026-01-12 14:00", None, "corrective", True, 2.0, 8.0, "high", "closed", 2.0, 5.5),
            ("T2", "A", "2026-01-12 05:00", "2026-01-12 16:00", None, "2026-01-13 10:00", None, "enquiry", True, 4.0, 8.0, "low", "closed", 9.0, np.nan),
            ("T3", "A", "2026-01-02 08:00", None, None, "2026-01-23 22:30", "2026-01-10", "preventive", True, np.nan, np.nan, "low", "closed", np.nan, np.nan),
            ("T4", "A", "2026-01-02 08:00", None, None, "2026-01-24 23:30", "2026-01-10", "inspection", True, np.nan, np.nan, "low", "closed", np.nan, np.nan),
            ("T5", "A", "2026-01-12 08:00", None, None, None, None, "corrective", None, 4.0, 8.0, "low", "cancelled", np.nan, np.nan)])


def test_sla_attainment_stored_shares_and_the_service_hours_recompute():
    s = grid.sla_attainment(SLA, by=("team_key",), context=M12)
    assert s.n_tickets.tolist() == [5] and s.n_assessed.tolist() == [4] and s.n_met.tolist() == [4] and s.share_met.tolist() == [1.0], "a cancelled ticket without a verdict is not assessed"
    r = grid.sla_attainment(SLA, by=("team_key",), team_region={"A": "DK"}, context=M12)
    assert r.n_recomputed.tolist() == [4] and r.n_recomputed_met.tolist() == [2] and r.share_recomputed_met.tolist() == [0.5]
    assert r.n_hours_differ.tolist() == [0], "2.0, 5.5 and 9.0 hours are the recomputed hours"
    assert r.n_verdict_differs.tolist() == [2], "T2 is stored as met but took 9 h against 4, and T4 resolved after the grace in local time"
    one = grid.sla_attainment(SLA.iloc[:1], by=("tkt_key",), team_region={"A": "DK"}, context=M12)
    assert one.n_recomputed_met.tolist() == [1]
    off = grid.sla_attainment(SLA.assign(response_h=[2.5, 9.0, np.nan, np.nan, np.nan]), by=("team_key",), team_region={"A": "DK"}, context=M12)
    assert off.n_hours_differ.tolist() == [1], "a stored 2.5 h against the recomputed 2.0 h"


def test_sla_attainment_holidays_and_refusals():
    # 2026-04-02 is Maundy Thursday and 04-03 Good Friday, 04-06 Easter Monday: Wednesday 15:00 to Tuesday 08:00 is 1 h + 0 + 0 + 0 + 0 + 1 h = 2 h
    hol = _sla([("T1", "A", "2026-04-01 13:00", "2026-04-07 06:00", None, "2026-04-07 10:00", None, "corrective", True, 2.0, 8.0, "high", "closed", 2.0, np.nan)])
    assert grid.sla_attainment(hol, by=("team_key",), team_region={"A": "DK"}, context=M12).n_hours_differ.tolist() == [0]
    with pytest.raises(FrameError, match="no region"):
        grid.sla_attainment(SLA, team_region={"Z": "DK"}, context=M12)
    with pytest.raises(FrameError, match="time zone country"):
        grid.sla_attainment(SLA, team_region={"A": "DK"}, country_of_region={}, context=M12)
    with pytest.raises(FrameError, match="service hours"):
        grid.sla_attainment(SLA, service_start=16, service_end=7, context=M12)
    with pytest.raises(FrameError, match="more than one"):
        grid.sla_attainment(pd.concat([SLA, SLA.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="grace_days"):
        grid.sla_attainment(SLA, team_region={"A": "DK"}, grace_days=-1, context=M12)


def test_requires_authorisation_counts_active_plans_by_team_and_type():
    p = pd.DataFrame({"net_key": ["a", "b", "c", "d"], "plan_no": [1, 1, 1, 1], "plan_type": ["x", "x", "x", "y"], "team_key": ["T", "T", "T", "T"], "status": ["active", "active", "suspended", "active"],
                      "requires_electrical_authorisation": [True, False, True, False]})
    r = grid.requires_authorisation(p, context=M12).set_index("plan_type")
    assert r.loc["x", "n_plans"] == 2 and r.loc["x", "n_requiring"] == 1 and r.loc["x", "share_requiring"] == 0.5 and r.loc["y", "n_requiring"] == 0
    assert grid.requires_authorisation(p, active_status=("suspended",), context=M12).n_requiring.tolist() == [1]
    with pytest.raises(FrameError, match="nulls"):
        grid.requires_authorisation(p.assign(requires_electrical_authorisation=[True, None, False, False]), context=M12)
    assert grid.requires_authorisation(p.iloc[:0], context=M12).empty


def test_stage_and_registration():
    reg = registry.registered()
    for n in ("callout_summary", "on_call", "sla_attainment", "requires_authorisation"):
        assert f"halvaro.grid.callouts.{n}" in reg and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.on_call(pd.DataFrame(), "2026-01-01", context=Context(stage="month3", role="r"))





def test_filtered_frames_categorical_keys_and_flags():
    shuffled = TK.iloc[::-1]
    a = grid.callout_summary(shuffled, LB, context=M12)
    b = grid.callout_summary(TK, LB, context=M12)
    assert a.equals(b), "the ticket index is not a key: a reversed or filtered frame gives the same result"
    only_a = TK[TK.team_key == "A"]
    assert grid.callout_summary(only_a, LB[LB.tkt_key.isin(only_a.tkt_key)], context=M12).n_tickets.sum() == 2
    cat = TK.assign(team_key=TK.team_key.astype("category"), callout_kind=TK.callout_kind.astype("category"))
    assert grid.callout_summary(cat, LB.assign(team_key=LB.team_key.astype("category")), context=M12).labour_hours.sum() == 19.0
    s = SLA.assign(ticket_type=SLA.ticket_type.astype("category"), priority=SLA.priority.astype("category"))
    assert grid.sla_attainment(s, by=("ticket_type", "priority"), context=M12).n_tickets.sum() == 5
    assert grid.sla_attainment(SLA.iloc[[0, 1]], by=("priority",), team_region={"A": "DK"}, context=M12).n_tickets.sum() == 2
    flat = SLA.set_index(pd.Index([7, 7, 7, 7, 7]))
    assert grid.sla_attainment(flat, by=("team_key",), team_region={"A": "DK"}, context=M12).n_recomputed.tolist() == [4], "a duplicate index is harmless"


def test_ticket_hour_columns_are_checked_for_tickets_without_labour_and_nulls_refuse():
    with pytest.raises(FrameError, match="without labour rows"):
        grid.callout_summary(TK.assign(labour_hours=[10.0, 6.0, 3.0]).iloc[:3], LB[LB.tkt_key != "T3"], context=M12)
    with pytest.raises(FrameError, match="nulls"):
        grid.callout_summary(TK.assign(overtime_hours=[2.0, np.nan, 3.0]), LB, context=M12)
    with pytest.raises(FrameError, match="on every row"):
        grid.callout_summary(TK.assign(opened=["2026-01-05 08:00", None, "2026-02-02 01:00"]), LB, context=M12)
    with pytest.raises(FrameError, match="on every row"):
        grid.callout_summary(TK, LB.assign(work_date=[None, "2026-01-06", "2026-01-30", "2026-02-01", "2026-02-02"]), context=M12)
    with pytest.raises(FrameError, match="before the ticket was opened"):
        grid.sla_attainment(SLA.assign(first_response_ts=["2026-01-08 07:00"] + SLA.first_response_ts.tolist()[1:]), team_region={"A": "DK"}, context=M12)
    with pytest.raises(FrameError, match="must be a time"):
        grid.sla_attainment(SLA.assign(opened=[None] + SLA.opened.tolist()[1:]), team_region={"A": "DK"}, context=M12)


def test_window_edges_month_end_and_attendance_hours_mutants():
    tk = _tk([("T1", "A", "2026-01-31 23:30", "night", 1.0, 0.0, 0.0), ("T2", "A", "2026-02-01 00:30", "night", 1.0, 0.0, 0.0)])
    lb = _lb([("T1", "e", "2026-02-01", "A", 1.0, 0.0, 0.0), ("T2", "e", "2026-02-01", "A", 1.0, 0.0, 0.0)])
    m = grid.callout_summary(tk, lb, context=M12).set_index("period")
    assert m.loc["2026-01", "n_tickets"] == 1 and m.loc["2026-02", "n_tickets"] == 1 and m.loc["2026-02", "labour_hours"] == 2.0, "tickets by the UTC month of opened (T24), hours by work date"
    w = grid.callout_summary(tk, lb, window=("2026-01-31", "2026-01-31"), context=M12)
    assert w.n_tickets.sum() == 1 and w.labour_hours.sum() == 0.0, "the last day of a window is included, the next day is not"
    off = grid.sla_attainment(SLA.assign(attendance_h=[9.9, np.nan, np.nan, np.nan, np.nan]), by=("team_key",), team_region={"A": "DK"}, context=M12)
    assert off.n_hours_differ.tolist() == [1], "a stored attendance that differs counts too"



def test_second_round_empty_status_filter_rota_gap_text_flags_and_time_zones():
    p = pd.DataFrame({"net_key": ["a", "b"], "plan_no": [1, 1], "plan_type": ["x", "x"], "team_key": ["T", "T"], "status": ["active", "active"], "requires_electrical_authorisation": [True, False]})
    e = grid.requires_authorisation(p, active_status=("retired",), context=M12)
    assert e.empty and list(e.columns) == ["team_key", "plan_type", "n_plans", "n_requiring", "share_requiring"], "a status that matches nothing gives an empty frame, not a row of the whole table"
    with pytest.raises(FrameError, match="single text"):
        grid.requires_authorisation(p, active_status="active", context=M12)
    rota = pd.DataFrame({"team_key": ["A", "A"], "week_start": ["2026-01-05", "2026-01-19"], "primary_emp_key": ["p1", "p2"], "secondary_emp_key": ["s1", "s2"]})
    assert grid.on_call(rota, "2026-01-11", context=M12).primary_emp_key.tolist() == ["p1"] and grid.on_call(rota, "2026-01-12", context=M12).empty, "a missing week is nobody, the earlier person does not cover 13 days"
    with pytest.raises(FrameError, match="true or false"):
        grid.sla_attainment(SLA.assign(sla_met=["True", "False", "True", "True", None]), context=M12)
    with pytest.raises(FrameError, match="at least one column"):
        grid.sla_attainment(SLA, by=(), context=M12)
    with pytest.raises(FrameError, match="time zone"):
        grid.on_call(rota, pd.Timestamp("2026-01-11", tz="UTC"), context=M12)
    with pytest.raises(FrameError, match="before the ticket was opened"):
        grid.sla_attainment(SLA.assign(first_response_ts=["2026-01-08 07:00"] + SLA.first_response_ts.tolist()[1:], opened=["2026-01-09 14:00"] + SLA.opened.tolist()[1:]), team_region={"A": "DK"}, context=M12)
