"""Maintenance (plan 5.7): hand computed plans and tickets, then the baseline release."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")


def _mp(rows):
    return pd.DataFrame(rows, columns=["net_key", "plan_no", "plan_type", "interval_months", "next_due", "last_done", "valid_from", "team_key", "status"])


PLANS = _mp([("A", 1, "annual_service", 12, "2026-11-01", "2025-11-01", "2023-01-01", "T1", "active"), ("A", 2, "condition_inspection", 32, "2026-11-16", None, "2023-01-01", "T1", "active"),
             ("B", 1, "annual_service", 12, "2026-11-16", "2025-11-15", "2023-01-01", "T2", "active"), ("B", 2, "condition_inspection", 12, "2026-12-10", "2026-01-01", "2026-03-01", "T2", "active"),
             ("C", 1, "annual_service", 12, "2026-08-01", None, "2023-01-01", "T2", "suspended"), ("C", 2, "annual_service", 12, None, None, "2023-01-01", "T2", "active")])


def test_overdue_plans_grace_status_and_missing_dates():
    r = grid.overdue_plans(PLANS, "2026-11-30", context=M12)
    assert r.net_key.tolist() == ["A"] and r.plan_no.tolist() == [1] and r.days_overdue.tolist() == [15], "due 1 November + 14 days grace = 15 November; 15 days later on 30 November"
    assert grid.overdue_plans(PLANS, "2026-11-15", context=M12).empty and grid.overdue_plans(PLANS, "2026-11-30", grace_days=29, context=M12).empty
    assert grid.overdue_plans(PLANS, "2026-11-30", active_status=("active", "suspended"), context=M12).net_key.tolist() == ["C", "A"], "the most overdue first"
    with pytest.raises(FrameError, match="grace_days"):
        grid.overdue_plans(PLANS, "2026-11-30", grace_days=-1, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.overdue_plans(pd.concat([PLANS, PLANS.iloc[:1]]), "2026-11-30", context=M12)


def test_due_within_counts_by_team_and_type():
    d = grid.due_within(PLANS, "2026-11-16", 30, context=M12).set_index(["team_key", "plan_type"])
    assert d.loc[("T1", "condition_inspection"), "n_plans"] == 1 and d.loc[("T2", "annual_service"), "n_plans"] == 1 and d.loc[("T2", "condition_inspection"), "first_due"] == pd.Timestamp("2026-12-10")
    assert ("T2", "annual_service") in d.index and len(d) == 3, "16 November and 16 December are inside (both inclusive), the suspended plan is not"
    assert grid.due_within(PLANS, "2026-11-16", 0, context=M12).n_plans.sum() == 2 and grid.due_within(PLANS, "2030-01-01", 10, context=M12).empty
    with pytest.raises(FrameError, match="horizon_days"):
        grid.due_within(PLANS, "2026-11-15", -3, context=M12)


def test_planned_backlog_by_team_and_month_with_due_date_counting_to_its_end():
    tk = pd.DataFrame({"tkt_key": [f"K{i}" for i in range(6)], "source": ["planned_maintenance"] * 5 + ["customer_call"], "team_key": ["T1", "T1", "T1", "T2", "T1", "T1"],
                       "due_date": ["2026-01-10", "2026-01-10", "2026-01-20", "2026-01-10", None, "2026-01-10"],
                       "resolved_ts": ["2026-01-10 18:00", "2026-01-13 12:00", "2026-01-19 12:00", "2026-01-11 00:00", "2026-01-10 00:00", "2026-01-30 00:00"]})
    r = grid.planned_backlog(tk, context=M12).set_index(["team_key", "period"])
    a = r.loc[("T1", "2026-01")]
    assert (a.n_planned, a.n_late) == (3, 1) and a.mean_days_late == 2.5 and a.max_days_late == 2.5 and a.late_share == pytest.approx(0.3333, abs=1e-4), "resolved on the due day is on time; K1 is 2.5 days after the end of the due day"
    assert a.mean_lateness_days == pytest.approx((-0.25 + 2.5 - 1.5) / 3, abs=0.01), "K0 early by 0.25 day, K1 late by 2.5, K2 early by 1.5"
    assert r.loc[("T2", "2026-01"), "n_late"] == 0 and np.isnan(r.loc[("T2", "2026-01"), "mean_days_late"]), "midnight after the due day is on time"
    assert grid.planned_backlog(tk, grace_days=3, context=M12).n_late.sum() == 0 and grid.planned_backlog(tk, sources=("customer_call",), context=M12).n_late.sum() == 1
    with pytest.raises(FrameError, match="more than one row"):
        grid.planned_backlog(pd.concat([tk, tk.iloc[:1]]), context=M12)


def test_inspection_interval_check_rule_rounding_and_unknown_classes():
    ge = pd.DataFrame({"net_key": ["A", "B", "C", "D"], "condition_class": ["D", "E", "A", None], "element_type": ["cable_section", "pipe_segment", "valve", "cable_section"]})
    mp = _mp([("A", 1, "condition_inspection", 32, "2027-01-01", None, "2023-01-01", "T", "active"), ("B", 1, "condition_inspection", 32, "2027-01-01", None, "2023-01-01", "T", "active"),
              ("C", 1, "condition_inspection", 120, "2027-01-01", None, "2023-01-01", "T", "active"), ("D", 1, "condition_inspection", 12, "2027-01-01", None, "2023-01-01", "T", "active"),
              ("A", 2, "annual_service", 12, "2027-01-01", None, "2023-01-01", "T", "active")])
    r = grid.inspection_interval_check(mp, ge, context=M12).set_index("net_key")
    assert r.index.tolist() == ["C", "D"], "E pipe: 26 x 1.25 = 32.5 rounds to 32 (half to even), so B is on the rule; C (valve, A) should be 144"
    assert r.loc["C", "expected_months"] == 144 and np.isnan(r.loc["D", "expected_months"])
    assert grid.inspection_interval_check(mp, ge, cycle_months={"A": 100, "D": 32, "E": 26}, context=M12).index.size == 1, "with class A at 100 months a valve is 120 and C is on the rule; D has no class"
    with pytest.raises(FrameError, match="more than one row"):
        grid.inspection_interval_check(mp, pd.concat([ge, ge.iloc[:1]]), context=M12)


def test_stage_registry_and_facade_for_maintenance():
    reg = registry.registered()
    for n in ("overdue_plans", "due_within", "planned_backlog", "inspection_interval_check"):
        assert f"halvaro.grid.maintenance.{n}" in reg and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.due_within(pd.DataFrame(), "2026-01-01", 1, context=Context(stage="month3", role="r"))



def test_planned_backlog_empty_result_and_string_arguments():
    tk = pd.DataFrame({"tkt_key": ["K0", "K1"], "source": ["customer_call", "planned_maintenance"], "team_key": ["T1", "T1"], "due_date": ["2026-01-10", "2026-01-10"], "resolved_ts": ["2026-01-12 00:00", None]})
    e = grid.planned_backlog(tk, context=M12)
    assert e.empty and "n_late" in e.columns, "nothing resolved: an empty frame with the columns, not a KeyError"
    assert grid.planned_backlog(tk.iloc[:0], context=M12).empty
    with pytest.raises(FrameError, match="single text"):
        grid.planned_backlog(tk, sources="inspection", context=M12)
    with pytest.raises(FrameError, match="team_key"):
        grid.planned_backlog(tk.assign(source="planned_maintenance", team_key=[None, "T1"], resolved_ts=["2026-01-12 00:00"] * 2), context=M12)
    with pytest.raises(FrameError, match="active_status"):
        grid.overdue_plans(PLANS, "2026-11-30", active_status="active", context=M12)
