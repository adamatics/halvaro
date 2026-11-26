"""schedule_overrun, delay_days, plan_slip, milestone_slippage, activity_plan_vs_actual: boundaries on synthetic frames, then the baseline against the generator tests (plan oracles O3 to O5)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, PeriodError, StageRefusal, registry

CTX = Context(stage="month12", role="r")
D = dt.date
NOW = D(2026, 11, 30)


def _proj(rows):
    """rows: (prj_key, start, planned_end, actual_end, forecast_end)"""
    return pd.DataFrame(rows, columns=["prj_key", "start", "planned_end", "actual_end", "forecast_end"])


# schedule_overrun

def test_overrun_is_end_minus_planned_over_planned_days_plus_one():
    p = _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 1, 10), D(2024, 1, 15), None),        # 10 planned days, 5 late
               ("PRJ-000002", D(2024, 1, 1), D(2024, 1, 10), D(2024, 1, 10), None),        # on time: zero
               ("PRJ-000003", D(2024, 1, 1), D(2024, 1, 10), D(2024, 1, 8), None)])        # early: negative
    o = delivery.schedule_overrun(p, NOW, context=CTX).set_index("prj_key")
    assert o.planned_days.tolist() == [10.0, 10.0, 10.0] and o.overrun_days.tolist() == [5.0, 0.0, -2.0] and o.overrun.tolist() == [0.5, 0.0, -0.2]
    assert (o.basis == "actual").all() and (o.as_of == pd.Timestamp(NOW)).all()


def test_overrun_forecast_for_active_and_nothing_for_planned_or_active_without_forecast():
    p = _proj([("PRJ-000001", D(2026, 1, 1), D(2026, 12, 31), None, D(2027, 1, 30)),       # active with forecast: 30 days over 365
               ("PRJ-000002", D(2026, 1, 1), D(2026, 12, 31), None, None),                  # active without forecast: not listed
               ("PRJ-000003", D(2027, 1, 1), D(2027, 6, 30), None, D(2027, 8, 1)),          # planned: not listed
               ("PRJ-000004", D(2020, 1, 1), D(2020, 12, 31), D(2021, 3, 1), None)])        # completed
    o = delivery.schedule_overrun(p, NOW, context=CTX).set_index("prj_key")
    assert list(o.index) == ["PRJ-000001", "PRJ-000004"] and o.loc["PRJ-000001", "basis"] == "forecast" and o.loc["PRJ-000001", "overrun_days"] == 30
    assert o.loc["PRJ-000001", "planned_days"] == 365 and o.loc["PRJ-000004", "basis"] == "actual"
    assert list(delivery.schedule_overrun(p, NOW, include_forecast=False, context=CTX).prj_key) == ["PRJ-000004"]


def test_overrun_uses_the_date_not_the_stored_end():
    p = _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 1, 10), D(2024, 1, 15), None)])
    assert delivery.schedule_overrun(p, D(2024, 1, 15), context=CTX).empty, "actual_end on the date: still active, no forecast"
    assert len(delivery.schedule_overrun(p, D(2024, 1, 16), context=CTX)) == 1


def test_overrun_bad_input():
    bad = _proj([("PRJ-000001", D(2024, 2, 1), D(2024, 1, 10), D(2024, 3, 1), None)])
    with pytest.raises(FrameError, match="no planned_end or one before the start.*PRJ-000001"):
        delivery.schedule_overrun(bad, NOW, context=CTX)
    with pytest.raises(FrameError, match="lacks column.*forecast_end"):
        delivery.schedule_overrun(bad.drop(columns="forecast_end"), NOW, context=CTX)
    with pytest.raises(PeriodError):
        delivery.schedule_overrun(bad, "x", context=CTX)


# delay_days

def _ev(rows):
    return pd.DataFrame(rows, columns=["prj_key", "cause_code", "responsible_party", "days"])


def test_delay_days_by_cause_and_the_tie_to_the_date_difference():
    ev = _ev([("PRJ-000001", "ground_conditions", "shared", 10), ("PRJ-000001", "weather", "third_party", 5), ("PRJ-000001", "ground_conditions", "shared", 3),
              ("PRJ-000002", "supplier_delay", "supplier", 7)])
    p = _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 19), None),         # 18 days late, events 18: ties
               ("PRJ-000002", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 4), None),          # 3 late, events 7: does not tie
               ("PRJ-000003", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 1), None),          # no events, on time: ties at zero
               ("PRJ-000004", D(2024, 1, 1), D(2027, 2, 1), None, None)])                   # not completed: no difference
    r = delivery.delay_days(ev, p, context=CTX)
    g = r.by_cause.set_index(["prj_key", "cause_code"])
    assert g.loc[("PRJ-000001", "ground_conditions"), "days"] == 13 and g.loc[("PRJ-000001", "ground_conditions"), "events"] == 2
    t = r.tie.set_index("prj_key")
    assert t.loc["PRJ-000001", "ties"] == True and t.loc["PRJ-000002", "diff"] == 4 and t.loc["PRJ-000002", "ties"] == False  # noqa: E712
    assert t.loc["PRJ-000003", "event_days"] == 0 and t.loc["PRJ-000003", "ties"] == True and pd.isna(t.loc["PRJ-000004", "ties"])  # noqa: E712
    assert delivery.delay_days(ev, context=CTX).tie.event_days.tolist() == [18, 7]


def test_delay_days_refuses_unknown_projects_and_null_days():
    p = _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 1), None)])
    with pytest.raises(FrameError, match="not in the project frame.*PRJ-000009"):
        delivery.delay_days(_ev([("PRJ-000009", "x", "y", 1)]), p, context=CTX)
    with pytest.raises(FrameError, match="days has nulls"):
        delivery.delay_days(_ev([("PRJ-000001", "x", "y", np.nan)]), context=CTX)


# plan_slip

def _pv(rows):
    return pd.DataFrame(rows, columns=["prj_key", "plan_version", "created", "reason", "planned_end"])


def test_plan_slip_against_version_one_and_the_previous_version():
    v = _pv([("PRJ-000001", 3, D(2026, 10, 20), "ground", D(2026, 12, 18)), ("PRJ-000001", 1, D(2025, 3, 18), "baseline", D(2026, 5, 31)), ("PRJ-000001", 2, D(2025, 11, 5), "ground", D(2026, 10, 31)),
             ("PRJ-000002", 2, D(2025, 1, 1), "x", D(2026, 1, 1))])
    s = delivery.plan_slip(v, context=CTX)
    assert s.prj_key.tolist() == ["PRJ-000001"] * 3 + ["PRJ-000002"] and s.plan_version.tolist() == [1, 2, 3, 2]
    assert s.slip_days.tolist()[:3] == [0.0, 153.0, 201.0] and s.step_days.tolist()[:3] == [pytest.approx(np.nan, nan_ok=True), 153.0, 48.0]
    assert pd.isna(s.baseline_end.iloc[3]) and pd.isna(s.slip_days.iloc[3]), "no version 1: no baseline, no slip"
    assert delivery.plan_slip(v, D(2025, 12, 31), context=CTX).plan_version.tolist() == [1, 2, 2]


def test_plan_slip_refuses_duplicates_and_missing_columns():
    v = _pv([("PRJ-000001", 1, D(2025, 3, 18), "b", D(2026, 5, 31))])
    with pytest.raises(FrameError, match="sharing prj_key, plan_version"):
        delivery.plan_slip(pd.concat([v, v]), context=CTX)
    with pytest.raises(FrameError, match="lacks column.*reason"):
        delivery.plan_slip(v.drop(columns="reason"), context=CTX)


# milestone_slippage

def test_milestones_done_open_and_overdue_on_a_date():
    m = pd.DataFrame([("PRJ-000001", 1, D(2026, 11, 1), D(2026, 11, 10)),        # done 9 days late
                      ("PRJ-000001", 2, D(2026, 11, 20), D(2026, 12, 5)),        # actual after the date: not done yet, 10 days overdue
                      ("PRJ-000001", 3, D(2026, 11, 30), None),                  # due on the date: open, not overdue
                      ("PRJ-000001", 4, D(2026, 11, 29), None),                  # one day overdue
                      ("PRJ-000001", 5, D(2026, 12, 15), None)], columns=["prj_key", "milestone_no", "planned_date", "actual_date"])
    r = delivery.milestone_slippage(m, NOW, context=CTX)
    assert r.state.tolist() == ["done", "open_overdue", "open", "open_overdue", "open"]
    assert r.slip_days.tolist()[:1] == [9.0] and r.overdue_days.dropna().tolist() == [10.0, 1.0] and pd.isna(r.actual_date.iloc[1])


# activity_plan_vs_actual

def test_activity_baseline_latest_actual_and_as_of():
    pa = pd.DataFrame([("PRJ-000001", 1, "A000", "Mobilise", D(2025, 4, 1), D(2025, 5, 1), None, False), ("PRJ-000001", 2, "A000", "Mobilise", D(2025, 4, 1), D(2025, 6, 1), None, True),
                       ("PRJ-000001", 1, "A010", "Pipe", D(2025, 5, 1), D(2025, 9, 1), "A000", True)],
                      columns=["prj_key", "plan_version", "activity_code", "name", "start", "end", "predecessor", "critical"])
    aa = pd.DataFrame([("PRJ-000001", "A000", D(2025, 4, 3), D(2025, 6, 10), 100)], columns=["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"])
    r = delivery.activity_plan_vs_actual(pa, aa, context=CTX).set_index("activity_code")
    assert r.loc["A000", "end_slip_days"] == 31 and r.loc["A000", "start_slip_days"] == 2 and r.loc["A000", "plan_versions"] == 2 and bool(r.loc["A000", "critical"])
    assert pd.isna(r.loc["A010", "actual_start"]) and r.loc["A010", "predecessor"] == "A000"
    early = delivery.activity_plan_vs_actual(pa, aa, D(2025, 5, 1), context=CTX).set_index("activity_code")
    assert early.loc["A000", "actual_start"] == pd.Timestamp(2025, 4, 3) and pd.isna(early.loc["A000", "actual_end"]), "the end is after the date"
    before = delivery.activity_plan_vs_actual(pa, aa, D(2025, 4, 2), context=CTX).set_index("activity_code")
    assert pd.isna(before.loc["A000", "actual_start"]) and pd.isna(before.loc["A000", "percent_complete"])
    with pytest.raises(FrameError, match="no plan activity.*A999"):
        delivery.activity_plan_vs_actual(pa, pd.concat([aa, aa.assign(activity_code="A999")]), context=CTX)


# registry and stage

def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["schedule_overrun", "delay_days", "plan_slip", "milestone_slippage", "activity_plan_vs_actual"]
    for n in names:
        m = reg[f"halvaro.delivery.schedule.{n}"]
        assert m.oracle.startswith("py:tests/test_projects.py::") and all(s.startswith("projects.") for s in m.sources) and m.parameters[-1] == "context"
    assert registry.check() == []
    recs = {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    assert {f"halvaro.delivery.schedule.{n}" for n in names} <= recs
    for stage in ("day1", "month3"):
        with pytest.raises(StageRefusal, match="projects"):
            delivery.plan_slip(_pv([("PRJ-000001", 1, D(2025, 3, 18), "b", D(2026, 5, 31))]), context=Context(stage=stage, role="r"))


# the baseline

@pytest.mark.release
def test_cell_mean_overrun_and_every_completed_project_ties_event_days(load):
    p, ev = load("projects", "project"), load("projects", "delay_event")
    o = delivery.schedule_overrun(p, NOW, context=CTX)
    cell = p[(p.country == "DE") & (p.type == "dh_network") & (p.soil_class == "clay") & (p.prj_key != "PRJ-000001") & (pd.to_datetime(p.actual_end) < pd.Timestamp(NOW))]    # the cell of test_cell_calibration
    x = o[o.prj_key.isin(cell.prj_key) & (o.basis == "actual")]
    assert len(x) >= 15 and abs(x.overrun.mean() - 0.22) < 0.01, "test_cell_calibration"
    assert (o.basis == "forecast").sum() == len(p[(p.actual_end.isna()) & (pd.to_datetime(p.start) <= pd.Timestamp(NOW)) & p.forecast_end.notna()])
    r = delivery.delay_days(ev, p, context=CTX)
    completed = p[pd.to_datetime(p.actual_end) < pd.Timestamp(NOW)].prj_key
    t = r.tie.set_index("prj_key").loc[completed]
    story = t.index == "PRJ-000001"
    assert (t[~story].ties == True).all(), t[t.ties != True]  # noqa: E712
    assert r.tie.set_index("prj_key").loc["PRJ-000001", "event_days"] == 190 and r.tie.set_index("prj_key").loc["PRJ-000001", "events"] == 7
    g = r.by_cause[r.by_cause.prj_key == "PRJ-000001"]
    assert g[g.cause_code == "ground_conditions"].days.sum() == 80, "test_story_project: 80 ground days"


@pytest.mark.release
def test_story_project_plan_versions_and_first_event(load):
    s = delivery.plan_slip(load("projects", "plan_version"), context=CTX)
    s = s[s.prj_key == "PRJ-000001"].set_index("plan_version")
    assert s.planned_end.dt.date.astype(str).tolist() == ["2026-05-31", "2026-10-31", "2026-12-18"] and s.slip_days.tolist() == [0.0, 153.0, 201.0]
    allv = delivery.plan_slip(load("projects", "plan_version"), context=CTX)
    project = load("projects", "project").set_index("prj_key")
    full = project[project.data_depth == "full"].index
    first = allv[allv.plan_version == 1].set_index("prj_key")
    assert set(full) <= set(first.index), "version 1 exists for every full project"
    assert (first.loc[full, "created"] <= pd.to_datetime(project.loc[full, "start"])).all(), "rule 16: the first plan is created before the project starts"
    ev = load("projects", "delay_event")
    assert pd.to_datetime(ev[ev.prj_key == "PRJ-000001"].start).min() == pd.Timestamp(2025, 10, 2)


@pytest.mark.release
def test_milestones_and_activities_on_the_baseline(load):
    m = delivery.milestone_slippage(load("projects", "milestone"), NOW, context=CTX)
    assert len(m) == len(load("projects", "milestone")) and set(m.state) <= {"done", "open", "open_overdue"}
    assert (m[m.state == "done"].actual_date <= pd.Timestamp(NOW)).all() and (m[m.state != "done"].actual_date.isna()).all()
    pa, aa = load("projects", "plan_activity"), load("projects", "actual_activity")
    a = delivery.activity_plan_vs_actual(pa, aa, NOW, context=CTX)
    assert len(a) == len(pa[["prj_key", "activity_code"]].drop_duplicates()) and a.actual_start.notna().sum() <= len(aa)
    assert (pd.to_datetime(pa.start) <= pd.to_datetime(pa.end)).all(), "plan activities have start not after end"
    assert a.end_slip_days.notna().all() and (a.end_slip_days >= 0).all(), 're-plans only move the end later'
    s = a[a.prj_key == "PRJ-000001"]
    assert s.plan_versions.max() == 3 and (s.end_slip_days >= 0).all()


# review fixes: boundaries on the date, nulls and types

def test_as_of_is_inclusive_for_plans_milestones_and_actuals():
    v = _pv([("PRJ-000001", 1, D(2025, 3, 18), "b", D(2026, 5, 31)), ("PRJ-000001", 2, D(2025, 11, 5), "x", D(2026, 10, 31))])
    assert delivery.plan_slip(v, D(2025, 11, 5), context=CTX).plan_version.tolist() == [1, 2], "created on the date counts"
    assert delivery.plan_slip(v, D(2025, 11, 4), context=CTX).plan_version.tolist() == [1]
    m = pd.DataFrame([("PRJ-000001", 1, D(2026, 11, 1), D(2026, 11, 10))], columns=["prj_key", "milestone_no", "planned_date", "actual_date"])
    assert delivery.milestone_slippage(m, D(2026, 11, 10), context=CTX).state.tolist() == ["done"]
    assert delivery.milestone_slippage(m, D(2026, 11, 9), context=CTX).state.tolist() == ["open_overdue"]
    pa = pd.DataFrame([("PRJ-000001", 1, "A000", "n", D(2025, 4, 1), D(2025, 6, 1), None, False)], columns=["prj_key", "plan_version", "activity_code", "name", "start", "end", "predecessor", "critical"])
    aa = pd.DataFrame([("PRJ-000001", "A000", D(2025, 4, 3), D(2025, 6, 10), 100)], columns=["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"])
    on = delivery.activity_plan_vs_actual(pa, aa, D(2025, 6, 10), context=CTX).iloc[0]
    assert on.actual_end == pd.Timestamp(2025, 6, 10) and on.percent_complete == 100, "finished on the date: counts"
    day_before = delivery.activity_plan_vs_actual(pa, aa, D(2025, 6, 9), context=CTX).iloc[0]
    assert pd.isna(day_before.actual_end) and pd.isna(day_before.percent_complete), "not finished yet: the final percent is not known on the date"
    start_day = delivery.activity_plan_vs_actual(pa, aa, D(2025, 4, 3), context=CTX).iloc[0]
    assert start_day.actual_start == pd.Timestamp(2025, 4, 3) and pd.isna(start_day.actual_end)


def test_activity_latest_version_nulls_are_not_filled_from_other_versions():
    pa = pd.DataFrame([("PRJ-000001", 1, "A000", "Old name", D(2025, 4, 1), D(2025, 6, 1), "A0", False), ("PRJ-000001", 2, "A000", "New name", D(2025, 4, 1), D(2025, 7, 1), None, False)],
                      columns=["prj_key", "plan_version", "activity_code", "name", "start", "end", "predecessor", "critical"])
    aa = pd.DataFrame(columns=["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"])
    r = delivery.activity_plan_vs_actual(pa, aa, context=CTX).iloc[0]
    assert r["name"] == "New name" and pd.isna(r.predecessor), "the predecessor of the latest version is none, not the earlier one"
    nb = pa.copy()
    nb.loc[0, "end"] = None
    r2 = delivery.activity_plan_vs_actual(nb, aa, context=CTX).iloc[0]
    assert pd.isna(r2.baseline_end) and r2.latest_end == pd.Timestamp(2025, 7, 1) and pd.isna(r2.end_slip_days), "a missing baseline end is not borrowed from v2"


def test_delay_days_refuses_nulls_text_and_fractions_instead_of_dropping_rows():
    ok = _ev([("PRJ-000001", "a", "x", 3)])
    with pytest.raises(FrameError, match="null cause_code"):
        delivery.delay_days(pd.concat([ok, _ev([("PRJ-000001", None, "x", 4)])]), context=CTX)
    with pytest.raises(FrameError, match="null prj_key"):
        delivery.delay_days(pd.concat([ok, _ev([(None, "a", "x", 4)])]), context=CTX)
    with pytest.raises(FrameError, match="numeric"):
        delivery.delay_days(_ev([("PRJ-000001", "a", "x", "3"), ("PRJ-000001", "a", "x", "4")]), context=CTX)
    with pytest.raises(FrameError, match="whole days"):
        delivery.delay_days(_ev([("PRJ-000001", "a", "x", 3.5)]), context=CTX)


def test_plan_slip_keeps_source_columns_and_refuses_text_versions():
    v = _pv([("PRJ-000001", 1, D(2025, 3, 18), "b", D(2026, 5, 31))]).assign(approved_by_emp_key="EMP-000232")
    assert "approved_by_emp_key" in delivery.plan_slip(v, context=CTX).columns
    with pytest.raises(FrameError, match="plan_version must be numeric"):
        delivery.plan_slip(v.assign(plan_version="1"), context=CTX)
    assert delivery.plan_slip(v.assign(created=None), D(2025, 1, 1), context=CTX).plan_version.tolist() == [1], "a version with no created date is kept"
    m = pd.DataFrame([("PRJ-000001", 1, "Contract", D(2026, 11, 1), None, 10)], columns=["prj_key", "milestone_no", "name", "planned_date", "actual_date", "billing_percent"])
    assert {"name", "billing_percent"} <= set(delivery.milestone_slippage(m, NOW, context=CTX).columns)


# review round 3: percent on and after the release date, plan versions by date, the DE clay cell, ties, sorting and subsets

_PA_COLS = ["prj_key", "plan_version", "activity_code", "name", "start", "end", "predecessor", "critical"]
_AA_COLS = ["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"]


def _one_activity(percent=40, actual_start=D(2025, 4, 3), actual_end=None):
    pa = pd.DataFrame([("PRJ-000001", 1, "A000", "n", D(2025, 4, 1), D(2025, 6, 1), None, False)], columns=_PA_COLS)
    aa = pd.DataFrame([("PRJ-000001", "A000", actual_start, actual_end, percent)], columns=_AA_COLS)
    return pa, aa


def _pct(pa, aa, as_of):
    return delivery.activity_plan_vs_actual(pa, aa, as_of, context=CTX).percent_complete.iloc[0]


def test_percent_of_an_unfinished_activity_is_unknown_before_the_release_date_and_the_stored_one_from_it():
    pa, aa = _one_activity()                                        # in progress at the release, 40 percent
    assert pd.isna(_pct(pa, aa, D(2026, 11, 29))), "the day before the release the percent on the date is not in the data"
    assert _pct(pa, aa, NOW) == 40, "on the release date the stored percent is the current one"
    assert _pct(pa, aa, D(2027, 1, 1)) == 40 and _pct(pa, aa, "2030-01-01") == 40, "after it too"
    assert pd.isna(_pct(pa, aa, D(2025, 5, 1)))
    assert delivery.activity_plan_vs_actual(pa, aa, context=CTX).percent_complete.iloc[0] == 40, "no as_of: the stored percent"
    assert _pct(*_one_activity(100, D(2025, 4, 3), D(2025, 6, 10)), D(2025, 6, 10)) == 100, "a finished activity keeps its final percent at a past date"
    assert pd.isna(_pct(*_one_activity(100, D(2025, 4, 3), D(2025, 6, 10)), D(2025, 6, 9)))
    assert _pct(*_one_activity(100, D(2025, 4, 3), D(2025, 6, 10)), NOW) == 100
    pa, aa = _one_activity(0, None, None)                           # not started: no percent on any date
    assert pd.isna(_pct(pa, aa, NOW)) and pd.isna(_pct(pa, aa, D(2027, 1, 1))) and pd.isna(_pct(pa, aa, D(2025, 5, 1)))


def _plan_versions_fixture():
    pa = pd.DataFrame([("PRJ-000001", 1, "A000", "n", D(2025, 4, 1), D(2025, 6, 1), None, False), ("PRJ-000001", 2, "A000", "n", D(2025, 4, 1), D(2025, 9, 1), None, False),
                       ("PRJ-000001", 3, "A000", "n", D(2025, 4, 1), D(2026, 1, 1), None, False), ("PRJ-000001", 2, "A020", "late", D(2025, 10, 1), D(2025, 12, 1), None, False),
                       ("PRJ-000002", 1, "A000", "n", D(2025, 4, 1), D(2025, 6, 1), None, False), ("PRJ-000002", 2, "A000", "n", D(2025, 4, 1), D(2025, 7, 1), None, False)], columns=_PA_COLS)
    aa = pd.DataFrame([("PRJ-000001", "A020", D(2025, 10, 5), None, 10)], columns=_AA_COLS)
    pv = pd.DataFrame([("PRJ-000001", 1, D(2025, 3, 18)), ("PRJ-000001", 2, D(2025, 11, 5)), ("PRJ-000001", 3, D(2026, 10, 20)), ("PRJ-000002", 1, D(2025, 3, 1))],
                      columns=["prj_key", "plan_version", "created"])          # PRJ-000002 version 2 is not in the frame: kept
    return pa, aa, pv


def test_plan_versions_created_after_the_date_do_not_leak_when_the_version_frame_is_given():
    pa, aa, pv = _plan_versions_fixture()
    leak = delivery.activity_plan_vs_actual(pa, aa, D(2025, 6, 1), context=CTX).set_index(["prj_key", "activity_code"])
    assert leak.loc[("PRJ-000001", "A000"), "plan_versions"] == 3 and leak.loc[("PRJ-000001", "A000"), "end_slip_days"] == 214, "documented: without the version frame the later plans leak"
    r = delivery.activity_plan_vs_actual(pa, aa, D(2025, 6, 1), plan_version=pv, context=CTX).set_index(["prj_key", "activity_code"])
    assert r.loc[("PRJ-000001", "A000"), "plan_versions"] == 1 and r.loc[("PRJ-000001", "A000"), "end_slip_days"] == 0 and r.loc[("PRJ-000001", "A000"), "latest_end"] == pd.Timestamp(2025, 6, 1)
    assert ("PRJ-000001", "A020") not in r.index, "an activity that exists only in a later version is not listed (and its actual row is not an orphan)"
    assert r.loc[("PRJ-000002", "A000"), "plan_versions"] == 2, "a version absent from the version frame has no created date: kept"
    on = delivery.activity_plan_vs_actual(pa, aa, D(2025, 11, 5), plan_version=pv, context=CTX).set_index(["prj_key", "activity_code"])
    assert on.loc[("PRJ-000001", "A000"), "plan_versions"] == 2 and on.loc[("PRJ-000001", "A020"), "plan_versions"] == 1, "created on the date counts"
    day_before = delivery.activity_plan_vs_actual(pa, aa, D(2025, 11, 4), plan_version=pv, context=CTX).set_index(["prj_key", "activity_code"])
    assert day_before.loc[("PRJ-000001", "A000"), "plan_versions"] == 1 and ("PRJ-000001", "A020") not in day_before.index
    allv = delivery.activity_plan_vs_actual(pa, aa, NOW, plan_version=pv, context=CTX).set_index(["prj_key", "activity_code"])
    assert allv.loc[("PRJ-000001", "A000"), "plan_versions"] == 3
    nodate = delivery.activity_plan_vs_actual(pa, aa, plan_version=pv, context=CTX).set_index(["prj_key", "activity_code"])
    assert nodate.loc[("PRJ-000001", "A000"), "plan_versions"] == 3, "without as_of nothing is filtered"
    with pytest.raises(FrameError, match="lacks column.*created"):
        delivery.activity_plan_vs_actual(pa, aa, D(2025, 6, 1), plan_version=pv.drop(columns="created"), context=CTX)
    with pytest.raises(FrameError, match="no plan activity.*A999"):
        delivery.activity_plan_vs_actual(pa, pd.concat([aa, aa.assign(activity_code="A999")]), D(2025, 6, 1), plan_version=pv, context=CTX)


def test_overrun_of_an_active_project_before_the_release_date_is_on_the_current_forecast():
    p = _proj([("PRJ-000001", D(2026, 1, 1), D(2026, 12, 31), None, D(2027, 1, 30)), ("PRJ-000004", D(2020, 1, 1), D(2020, 12, 31), D(2021, 3, 1), None)])
    before = delivery.schedule_overrun(p, D(2026, 11, 29), context=CTX).set_index("prj_key")
    assert before.loc["PRJ-000001", "basis"] == "current forecast" and before.loc["PRJ-000001", "overrun_days"] == 30 and before.loc["PRJ-000004", "basis"] == "actual"
    for d in (NOW, D(2027, 1, 1)):
        assert delivery.schedule_overrun(p, d, context=CTX).set_index("prj_key").loc["PRJ-000001", "basis"] == "forecast"
    assert "current forecast" in delivery.schedule_overrun.__doc__


def test_delay_ties_distinguish_fewer_event_days_than_date_difference():
    ev = _ev([("PRJ-000001", "a", "x", 3)])
    p = _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 11), None)])         # 10 days late, 3 event days: diff -7
    t = delivery.delay_days(ev, p, context=CTX).tie.set_index("prj_key")
    assert t.loc["PRJ-000001", "diff"] == -7 and t.loc["PRJ-000001", "ties"] == False  # noqa: E712


def test_sorted_results_do_not_depend_on_the_input_order():
    ev = _ev([("PRJ-000003", "weather", "x", 2), ("PRJ-000001", "weather", "x", 1), ("PRJ-000002", "ground", "y", 4), ("PRJ-000001", "ground", "x", 5), ("PRJ-000003", "ground", "x", 6)])
    p = _proj([("PRJ-000003", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 9), None), ("PRJ-000001", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 7), None),
               ("PRJ-000002", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 5), None)])
    r = delivery.delay_days(ev, p, context=CTX)
    assert r.tie.prj_key.tolist() == ["PRJ-000001", "PRJ-000002", "PRJ-000003"] and r.tie.event_days.tolist() == [6, 4, 8]
    assert list(zip(r.by_cause.prj_key, r.by_cause.cause_code)) == [("PRJ-000001", "ground"), ("PRJ-000001", "weather"), ("PRJ-000002", "ground"), ("PRJ-000003", "ground"), ("PRJ-000003", "weather")]
    assert delivery.delay_days(ev, context=CTX).tie.prj_key.tolist() == ["PRJ-000001", "PRJ-000002", "PRJ-000003"]
    m = pd.DataFrame([("PRJ-000002", 2, D(2026, 11, 1), None), ("PRJ-000001", 2, D(2026, 11, 20), None), ("PRJ-000002", 1, D(2026, 11, 29), D(2026, 11, 29)),
                      ("PRJ-000001", 1, D(2026, 11, 1), D(2026, 11, 10))], columns=["prj_key", "milestone_no", "planned_date", "actual_date"])
    s = delivery.milestone_slippage(m, NOW, context=CTX)
    assert list(zip(s.prj_key, s.milestone_no)) == [("PRJ-000001", 1), ("PRJ-000001", 2), ("PRJ-000002", 1), ("PRJ-000002", 2)]
    assert s.state.tolist() == ["done", "open_overdue", "done", "open_overdue"] and s.slip_days.tolist()[0] == 9.0 and s.overdue_days.tolist()[3] == 29.0
    pa = pd.DataFrame([("PRJ-000002", 1, "A010", "b", D(2025, 5, 1), D(2025, 9, 1), None, False), ("PRJ-000001", 1, "A010", "c", D(2025, 5, 1), D(2025, 9, 1), None, False),
                       ("PRJ-000001", 1, "A000", "a", D(2025, 4, 1), D(2025, 5, 1), None, False)], columns=_PA_COLS)
    a = delivery.activity_plan_vs_actual(pa, pd.DataFrame(columns=_AA_COLS), context=CTX)
    assert list(zip(a.prj_key, a.activity_code)) == [("PRJ-000001", "A000"), ("PRJ-000001", "A010"), ("PRJ-000002", "A010")] and a.name.tolist() == ["a", "c", "b"]


def test_delay_days_accepts_a_project_frame_that_is_a_subset_of_the_event_projects():
    ev = _ev([("PRJ-000001", "ground", "x", 10), ("PRJ-000002", "weather", "y", 4), ("PRJ-000002", "ground", "x", 3), ("PRJ-000003", "ground", "x", 8)])
    p = _proj([("PRJ-000002", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 8), None), ("PRJ-000004", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 1), None)])      # PRJ-000004: in the frame, no events
    r = delivery.delay_days(ev, p, context=CTX)
    assert r.tie.prj_key.tolist() == ["PRJ-000002", "PRJ-000004"] and r.tie.event_days.tolist() == [7, 0] and r.tie.ties.tolist() == [True, True]
    assert r.by_cause.prj_key.unique().tolist() == ["PRJ-000002"] and r.by_cause.days.sum() == 7, "events of other projects are left out of by_cause too"
    assert r.tie.attrs["events_outside_projects"] == 2 and r.by_cause.attrs["events_outside_projects"] == 2
    whole = delivery.delay_days(ev, _proj([("PRJ-000001", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 11), None), ("PRJ-000002", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 8), None),
                                           ("PRJ-000003", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 9), None)]), context=CTX)
    assert whole.tie.attrs["events_outside_projects"] == 0 and delivery.delay_days(ev, context=CTX).tie.attrs["events_outside_projects"] == 0
    with pytest.raises(FrameError, match="not in the project frame, none of them.*PRJ-000001"):
        delivery.delay_days(ev, _proj([("PRJ-000009", D(2024, 1, 1), D(2024, 2, 1), D(2024, 2, 1), None)]), context=CTX)


def test_delay_days_refuses_repeated_events_and_days_of_zero_or_less():
    ev = _ev([("PRJ-000001", "a", "x", 3), ("PRJ-000001", "a", "x", 3)]).assign(seq=[1, 1])
    with pytest.raises(FrameError, match="sharing prj_key and seq.*PRJ-000001 1"):
        delivery.delay_days(ev, context=CTX)
    ok = delivery.delay_days(ev.assign(seq=[1, 2]), context=CTX)
    assert ok.tie.event_days.tolist() == [6], "distinct seq: both count"
    assert delivery.delay_days(_ev([("PRJ-000001", "a", "x", 3), ("PRJ-000001", "a", "x", 3)]), context=CTX).tie.event_days.tolist() == [6], "without seq loaded nothing is checked"
    for days in (0, -2):
        with pytest.raises(FrameError, match="days must be positive"):
            delivery.delay_days(_ev([("PRJ-000001", "a", "x", 3), ("PRJ-000002", "a", "x", days)]), context=CTX)


@pytest.mark.release
def test_percent_complete_known_for_every_started_activity_at_the_release_date(load):
    pa, aa = load("projects", "plan_activity"), load("projects", "actual_activity")
    a = delivery.activity_plan_vs_actual(pa, aa, NOW, context=CTX)
    assert a.percent_complete.notna().sum() == 2180 == delivery.activity_plan_vs_actual(pa, aa, context=CTX).percent_complete.notna().sum()
    s = delivery.activity_plan_vs_actual(pa, aa, "2025-06-01", plan_version=load("projects", "plan_version"), context=CTX)
    s = s[s.prj_key == "PRJ-000001"]
    assert len(s) and s.plan_versions.max() == 1 and (s.end_slip_days == 0).all(), "on 2025-06-01 only version 1 of the story project existed"
