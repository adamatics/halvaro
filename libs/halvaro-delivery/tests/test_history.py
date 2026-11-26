"""first_record, attendance, executive_attendance, executive_gap, decisions, minutes_refs, roster, timeline: synthetic frames, then the rosters on the baseline."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")
D = dt.date


def _diary(rows):
    return pd.DataFrame(rows, columns=["prj_key", "diary_date", "notes", "author_emp_key", "delay_seq"])


def test_first_record_is_the_earliest_diary_row_with_delay_seq_one_of_the_project():
    d = _diary([("P1", D(2025, 10, 9), "later", "EMP1", 1), ("P1", D(2025, 10, 2), "first", "EMP2", 1), ("P1", D(2025, 9, 1), "no delay", "EMP3", None), ("P1", D(2025, 9, 20), "second event", "EMP3", 2), ("P2", D(2025, 8, 1), "other", "EMP4", 1)])
    r = delivery.first_record(d, "P1", context=CTX)
    assert r.diary_date.tolist() == [D(2025, 10, 2)] and r.notes.tolist() == ["first"] and r.author_emp_key.tolist() == ["EMP2"]
    assert delivery.first_record(d, "P3", context=CTX).empty and list(delivery.first_record(d, "P3", context=CTX).columns)[:2] == ["prj_key", "diary_date"]
    with pytest.raises(FrameError, match="lacks column"):
        delivery.first_record(d.drop(columns="delay_seq"), "P1", context=CTX)


def _m(rows):
    return pd.DataFrame(rows, columns=["mtg_key", "prj_key", "date", "meeting_type"])


def _a(rows):
    return pd.DataFrame(rows, columns=["mtg_key", "attendee_type", "emp_key", "cnt_key", "status", "role_in_meeting"])


def test_attendance_resolves_by_type_flags_leavers_and_inactive_contacts():
    m = _m([("M1", "P1", D(2025, 12, 9), "steering")])
    a = _a([("M1", "employee", "EMP1", None, "present", "chair"), ("M1", "employee", "EMP2", None, "apology", "x"), ("M1", "external", None, "C1", "present", "customer representative"),
            ("M1", "external", None, "C2", "present", "customer representative")])
    emp = pd.DataFrame({"emp_key": ["EMP1", "EMP2"], "leave_date": [D(2025, 12, 8), None]})            # EMP1 left the day before the meeting
    con = pd.DataFrame({"cnt_key": ["C1", "C2"], "inactive_since": [D(2025, 12, 9), D(2025, 12, 8)]})   # C2 inactive before, C1 on the day
    r = delivery.attendance(m, a, employee=emp, contact=con, context=CTX).set_index("person_key")
    assert r.leaver.to_dict() == {"C1": False, "C2": False, "EMP1": True, "EMP2": False} and r.inactive_contact.to_dict() == {"C1": False, "C2": True, "EMP1": False, "EMP2": False}
    assert r.loc["EMP1", "status"] == "present" and r.loc["EMP2", "status"] == "apology" and (r.date == pd.Timestamp(2025, 12, 9)).all()
    assert "leaver" not in delivery.attendance(m, a, context=CTX).columns
    with pytest.raises(FrameError, match="exactly one of emp_key"):
        delivery.attendance(m, _a([("M1", "employee", "EMP1", "C1", "present", "x")]), context=CTX)
    with pytest.raises(FrameError, match="unknown value 'robot'"):
        delivery.attendance(m, _a([("M1", "robot", "EMP1", None, "present", "x")]), context=CTX)
    with pytest.raises(FrameError, match="not in projects.meeting.*M9"):
        delivery.attendance(m, _a([("M9", "employee", "EMP1", None, "present", "x")]), context=CTX)


def test_executive_set_is_per_meeting_date_apologies_do_not_count_and_the_gap_is_counted_from_the_first_record():
    m = _m([("M1", "P1", D(2025, 10, 2), "site"), ("M2", "P1", D(2025, 10, 14), "steering"), ("M3", "P1", D(2025, 12, 9), "steering"), ("M4", "P1", D(2025, 4, 1), "kickoff")])
    a = _a([("M1", "employee", "EMP9", None, "present", "chair"), ("M2", "employee", "EMP1", None, "apology", "x"), ("M3", "employee", "EMP1", None, "present", "x"), ("M3", "employee", "EMP2", None, "present", "x"),
            ("M4", "employee", "EMP1", None, "present", "x")])
    at = delivery.attendance(m, a, context=CTX)
    ex = pd.DataFrame({"emp_key": ["EMP1", "EMP1", "EMP1", "EMP1"], "role_name": ["Chief Financial Officer", "Chief Financial Officer", "Chief Financial Officer", "Chief Financial Officer"],
                       "as_of": [D(2025, 4, 1), D(2025, 10, 14), D(2025, 12, 9), D(2025, 10, 2)]})
    ea = delivery.executive_attendance(at, ex, context=CTX)
    assert ea.mtg_key.tolist() == ["M4", "M3"] and ea.emp_key.unique().tolist() == ["EMP1"], "present only; the apology of M2 and the non executive EMP2 are out"
    fr = pd.DataFrame({"prj_key": ["P1"], "diary_date": [D(2025, 10, 2)]})
    g = delivery.executive_gap(fr, ea, "P1", context=CTX).iloc[0]
    assert g.gap_days == 68 and g.first_executive_meeting == pd.Timestamp(2025, 12, 9) and g.first_executive_role == "Chief Financial Officer", "the April meeting is before the first record"
    on = ea.assign(date=pd.Timestamp(2025, 10, 2))
    assert delivery.executive_gap(fr, on, "P1", context=CTX).iloc[0].gap_days == 0, "an executive at the first meeting on the first record day: gap zero"
    never = delivery.executive_gap(fr, ea.iloc[:0], "P1", context=CTX).iloc[0]
    assert pd.isna(never.gap_days) and pd.isna(never.first_executive_meeting), "no executive yet: a gap that has not closed"
    # the holder of a role changes: EMP1 held the role in April only, so a December attendance does not count
    changed = pd.DataFrame({"emp_key": ["EMP1", "EMP7", "EMP7"], "role_name": ["Chief Financial Officer"] * 3, "as_of": [D(2025, 4, 1), D(2025, 10, 2), D(2025, 12, 9)]})      # EMP7 holds it on the later dates
    assert delivery.executive_attendance(at, changed, context=CTX).mtg_key.tolist() == ["M4"]
    with pytest.raises(FrameError, match="no first record"):
        delivery.executive_gap(fr.iloc[:0], ea, "P1", context=CTX)


def test_decisions_carry_project_date_write_down_flag_and_delay_cause():
    dec = pd.DataFrame({"mtg_key": ["M1", "M1", "M2"], "seq": [1, 2, 1], "text": "t", "decision_type": ["schedule", "commercial", "write_down"], "impact_cost": [0.0, 5.0, 707000.0],
                        "impact_days": [0, 3, 0], "currency": "EUR", "delay_seq": [1, None, None], "co_no": [None, 2, None]})
    m = _m([("M1", "P1", D(2025, 10, 2), "site"), ("M2", "P1", D(2025, 12, 18), "steering")])
    de = pd.DataFrame({"prj_key": ["P1"], "seq": [1], "cause_code": ["ground_conditions"]})
    r = delivery.decisions(dec, m, de, context=CTX)
    assert r.write_down.tolist() == [False, False, True] and r.delay_cause.tolist()[0] == "ground_conditions" and r.delay_cause.isna().tolist() == [False, True, True]
    assert r.date.tolist() == [pd.Timestamp(2025, 10, 2), pd.Timestamp(2025, 10, 2), pd.Timestamp(2025, 12, 18)] and (r.prj_key == "P1").all() and r.currency.eq("EUR").all()
    with pytest.raises(FrameError, match="not in projects.meeting"):
        delivery.decisions(dec, m.iloc[:1], context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        delivery.decisions(pd.concat([dec, dec]), m, context=CTX)


def test_minutes_refs_report_the_null_share():
    m = _m([("M1", "P1", D(2025, 10, 2), "site"), ("M2", "P1", D(2025, 10, 3), "site")]).assign(minutes_ref=["minutes/P1/M1.md", None])
    r = delivery.minutes_refs(m, context=CTX)
    assert r.null_share == 0.5 and r.frame.minutes_ref.tolist()[0] == "minutes/P1/M1.md"
    assert delivery.minutes_refs(m.iloc[:0], context=CTX).null_share == 0.0


def test_roster_keeps_rows_as_stored_adds_legacy_and_refuses_unknown_projects():
    pr = pd.DataFrame({"prj_key": ["P1", "P1", "P2", "P3"], "emp_key": ["EMP2", "EMP1", "EMP1", "EMP1"], "project_role": "lead engineer", "start": D(2020, 1, 1), "end": D(2021, 1, 1),
                       "hours_total": [10.0, 20.0, 30.0, 40.0], "basis": ["roster", "time_entries", "roster", "roster"]})
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "legacy": [False, True, True]})
    r = delivery.roster(pr, proj, ["P1", "P2", "P9"][:2], context=CTX)
    assert r.emp_key.tolist() == ["EMP1", "EMP2", "EMP1"] and r.legacy.tolist() == [False, False, True] and r.hours_total.sum() == 60.0
    assert delivery.roster(pr, proj, "P3", context=CTX).prj_key.tolist() == ["P3"] and delivery.roster(pr, proj, [], context=CTX).empty
    with pytest.raises(FrameError, match="not in the project frame.*P9"):
        delivery.roster(pr, proj, ["P1", "P9"], context=CTX)


def test_timeline_orders_events_and_lists_only_the_first_diary_row_of_each_delay():
    sd = _diary([("P1", D(2025, 10, 2), "ground", "EMP1", 1), ("P1", D(2025, 10, 3), None, "EMP1", 1), ("P1", D(2025, 11, 1), "utilities", "EMP1", 2), ("P2", D(2025, 9, 1), "x", "EMP1", 1)])
    rk = pd.DataFrame({"prj_key": ["P1"], "risk_no": [1], "raised": [D(2025, 10, 6)], "title": ["Ground risk"], "status": ["occurred"]})
    m = pd.DataFrame({"mtg_key": ["M1", "M9"], "prj_key": ["P1", "P2"], "date": [D(2025, 10, 2), D(2025, 9, 9)], "meeting_type": "site", "title": ["Site meeting", "Other"]})
    dec = pd.DataFrame({"mtg_key": ["M1", "M9"], "seq": [1, 1], "text": ["Stop trenching", "x"], "decision_type": "schedule"})
    de = pd.DataFrame({"prj_key": ["P1", "P2"], "seq": [1, 1], "start": [D(2025, 10, 2), D(2025, 9, 1)], "days": [52, 3], "cause_code": ["ground_conditions", "weather"]})
    pv = pd.DataFrame({"prj_key": ["P1"], "plan_version": [2], "created": [D(2025, 11, 5)], "reason": ["ground"]})
    t = delivery.timeline("P1", site_diary=sd, risk=rk, meeting=m, decision=dec, delay_event=de, plan_version=pv, context=CTX)
    assert t.date.is_monotonic_increasing and set(t.kind) == {"first_diary_delay", "delay_event", "meeting", "decision", "risk", "plan_version"}
    assert t[t.kind == "first_diary_delay"].source_key.tolist() == ["1", "2"] and t[t.kind == "decision"].source_key.tolist() == ["M1/1"] and "P2" not in " ".join(t.text)
    assert t[t.kind == "delay_event"].text.iloc[0] == "ground_conditions, 52 days"
    lim = delivery.timeline("P1", site_diary=sd, risk=rk, meeting=m, decision=dec, delay_event=de, plan_version=pv, start=D(2025, 10, 6), end=D(2025, 10, 31), context=CTX)
    assert lim.kind.tolist() == ["risk"], "start and end are inclusive"
    empty = delivery.timeline("P7", site_diary=sd, risk=rk, meeting=m, decision=dec, delay_event=de, plan_version=pv, context=CTX)
    assert empty.empty and list(empty.columns) == ["date", "kind", "source", "source_key", "text"]


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["first_record", "attendance", "executive_attendance", "executive_gap", "decisions", "minutes_refs", "roster", "timeline"]
    for n in names:
        m = reg[f"halvaro.delivery.history.{n}"]
        assert m.oracle.startswith("py:tests/") and m.parameters[-1] == "context" and all(s.startswith("projects.") for s in m.sources)
    assert registry.check() == [] and {f"halvaro.delivery.history.{n}" for n in names} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    with pytest.raises(StageRefusal, match="projects"):
        delivery.minutes_refs(_m([]).assign(minutes_ref=None), context=Context(stage="month3", role="r"))


# the baseline: the rosters


@pytest.mark.release
def test_roster_hours_of_full_projects_equal_time_entries(load, release_dir):
    p, pr = load("projects", "project"), load("projects", "project_role")
    full = p[p.data_depth == "full"].prj_key
    r = delivery.roster(pr, p, full, context=CTX)
    te = pd.read_parquet(release_dir / "projects" / "parquet" / "time_entry.parquet", columns=["prj_key", "emp_key", "hours"]).groupby(["prj_key", "emp_key"]).hours.sum()
    mine = r.groupby(["prj_key", "emp_key"]).hours_total.sum()
    both = pd.concat([mine, te], axis=1, keys=["roster", "time"]).dropna()
    assert len(both) > 1000 and ((both.roster - both.time).abs() <= 0.5 + 1e-6).all(), "test_rule18: roster hours equal time entries (0.5 per person and project)"
    assert not r.legacy.any() and set(delivery.roster(pr, p, p[p.legacy].prj_key, context=CTX).basis) == {"roster"}, "legacy roster rows are estimates"


# review fixes: nulls, types, duplicates and the boundaries mutations must break

def test_first_record_and_gap_refuse_null_dates_and_text_delay_seq():
    with pytest.raises(FrameError, match="have no diary_date"):
        delivery.first_record(_diary([("P", None, "b", "E", 1)]), "P", context=CTX)
    with pytest.raises(FrameError, match="delay_seq must be numeric"):
        delivery.first_record(_diary([("P", D(2025, 1, 1), "b", "E", "1")]), "P", context=CTX)
    d = _diary([("P", pd.Timestamp("2025-10-02 13:00"), "later", "E", 1), ("P", pd.Timestamp("2025-10-02 09:00"), "earlier", "E", 1)])
    assert delivery.first_record(d, "P", context=CTX).notes.tolist() == ["earlier"], "the time stamp decides on the same day"
    with pytest.raises(FrameError, match="2 first records"):
        delivery.executive_gap(pd.DataFrame({"prj_key": ["P", "P"], "diary_date": [D(2025, 1, 1), D(2025, 1, 2)]}), pd.DataFrame(columns=["mtg_key", "prj_key", "date", "emp_key", "role_name"]), "P", context=CTX)
    with pytest.raises(FrameError, match="no diary_date"):
        delivery.executive_gap(pd.DataFrame({"prj_key": ["P"], "diary_date": [None]}), pd.DataFrame(columns=["mtg_key", "prj_key", "date", "emp_key", "role_name"]), "P", context=CTX)


def test_attendance_status_values_present_flag_and_duplicate_persons():
    m = _m([("M1", "P1", D(2025, 12, 9), "steering")])
    a = _a([("M1", "employee", "EMP1", None, "present", "x"), ("M1", "employee", "EMP2", None, "absent", "x"), ("M1", "employee", "EMP3", None, "apology", "x")])
    r = delivery.attendance(m, a, context=CTX).set_index("person_key")
    assert r.present.to_dict() == {"EMP1": True, "EMP2": False, "EMP3": False}, "only present is attendance"
    with pytest.raises(FrameError, match="unknown value.*Present"):
        delivery.attendance(m, _a([("M1", "employee", "EMP1", None, "Present", "x")]), context=CTX)
    with pytest.raises(FrameError, match="more than once in meeting M1"):
        delivery.attendance(m, _a([("M1", "employee", "EMP1", None, "present", "x"), ("M1", "employee", "EMP1", None, "apology", "x")]), context=CTX)


def test_executive_attendance_accepts_dates_with_a_time_and_text_and_ignores_repeated_executive_rows():
    at = pd.DataFrame({"mtg_key": ["M1"], "prj_key": ["P1"], "date": [pd.Timestamp("2025-12-09 09:00")], "emp_key": ["EMP1"], "status": ["present"]})
    ex = pd.DataFrame({"emp_key": ["EMP1", "EMP1"], "role_name": ["CFO", "CFO"], "as_of": ["2025-12-09", D(2025, 12, 9)]})
    r = delivery.executive_attendance(at, ex, context=CTX)
    assert r.mtg_key.tolist() == ["M1"] and r.role_name.tolist() == ["CFO"], "a time of day does not hide the executive; the same row from two calls counts once"
    with pytest.raises(FrameError, match="appears more than once"):
        delivery.executive_attendance(pd.concat([at, at.assign(status="apology")]), ex, context=CTX)
    with pytest.raises(FrameError, match="unknown value"):
        delivery.executive_attendance(at.assign(status="Present"), ex, context=CTX)
    with pytest.raises(FrameError, match="differs in type"):
        delivery.executive_attendance(at.assign(emp_key=1), ex, context=CTX)
    assert delivery.executive_attendance(at.assign(status="absent"), ex, context=CTX).empty


def test_boundaries_null_share_timeline_end_ordering_and_decision_order():
    m = _m([("M1", "P1", D(2025, 10, 3), "site"), ("M2", "P1", D(2025, 10, 2), "site"), ("M3", "P1", D(2025, 10, 4), "site")]).assign(minutes_ref=["a.md", None, ""])
    r = delivery.minutes_refs(m, context=CTX)
    assert r.null_share == pytest.approx(2 / 3) and r.frame.mtg_key.tolist() == ["M2", "M1", "M3"], "null and empty text are missing; sorted by date"
    dec = pd.DataFrame({"mtg_key": ["M1", "M2", "M2"], "seq": [1, 2, 1], "text": "t", "decision_type": "schedule", "impact_cost": 0.0, "impact_days": 0, "currency": "EUR", "delay_seq": [None] * 3, "co_no": [None] * 3})
    assert delivery.decisions(dec, m.drop(columns="minutes_ref"), context=CTX)[["mtg_key", "seq"]].values.tolist() == [["M2", 1], ["M2", 2], ["M1", 1]], "by date, meeting, sequence"
    with pytest.raises(FrameError, match="already has column"):
        delivery.decisions(dec.assign(date=1), m.drop(columns="minutes_ref"), context=CTX)
    at = delivery.attendance(m.drop(columns="minutes_ref"), _a([("M1", "employee", "EMP1", None, "present", "x"), ("M1", "employee", "EMP0", None, "present", "x")]), context=CTX)
    assert at.person_key.tolist() == ["EMP0", "EMP1"], "sorted by person within a meeting"
    sd = _diary([("P1", D(2025, 10, 2), "n", "E", 1)])
    rk = pd.DataFrame({"prj_key": ["P1"], "risk_no": [1], "raised": [D(2025, 10, 2)], "title": ["R"], "status": ["occurred"]})
    mt = pd.DataFrame({"mtg_key": ["M1"], "prj_key": ["P1"], "date": [D(2025, 10, 2)], "meeting_type": "site", "title": ["T"]})
    de = pd.DataFrame({"prj_key": ["P1"], "seq": [1], "start": [D(2025, 10, 2)], "days": [3], "cause_code": ["ground"]})
    dc = pd.DataFrame({"mtg_key": ["M1"], "seq": [1], "text": ["x"], "decision_type": "schedule"})
    pv = pd.DataFrame({"prj_key": ["P1"], "plan_version": [2], "created": [D(2025, 10, 2)], "reason": ["g"]})
    t = delivery.timeline("P1", site_diary=sd, risk=rk, meeting=mt, decision=dc, delay_event=de, plan_version=pv, context=CTX)
    assert t.kind.tolist() == ["meeting", "decision", "delay_event", "first_diary_delay", "risk", "plan_version"], "same date: the explicit kind order, a decision after its meeting"
    on_end = delivery.timeline("P1", site_diary=sd, risk=rk, meeting=mt, decision=dc, delay_event=de, plan_version=pv, start=D(2025, 10, 2), end=D(2025, 10, 2), context=CTX)
    assert len(on_end) == 6, "start and end are inclusive on the day itself"
    assert delivery.timeline("P1", site_diary=sd, risk=rk, meeting=mt, decision=dc, delay_event=de, plan_version=pv, end=D(2025, 10, 1), context=CTX).empty
    many = de.iloc[:1].loc[[0] * 12].assign(seq=range(1, 13))
    keys = delivery.timeline("P1", site_diary=sd.iloc[:0], risk=rk.iloc[:0], meeting=mt.iloc[:0], decision=dc.iloc[:0], delay_event=many, plan_version=pv.iloc[:0], context=CTX).source_key.tolist()
    assert keys == [str(i) for i in range(1, 13)], "numeric order of the key, 10 after 9"
    with pytest.raises(FrameError, match="whole numbers"):
        delivery.timeline("P1", site_diary=sd, risk=rk, meeting=mt, decision=dc, delay_event=de.assign(days=None), plan_version=pv, context=CTX)
    with pytest.raises(FrameError, match="more than one row for a meeting"):
        delivery.timeline("P1", site_diary=sd, risk=rk, meeting=pd.concat([mt, mt]), decision=dc, delay_event=de, plan_version=pv, context=CTX)


# second review: a missing executive set, boundaries, project scoped joins, kind order

def _ex_at(rows):
    return pd.DataFrame(rows, columns=["mtg_key", "prj_key", "date", "emp_key", "status"])


def test_executive_attendance_refuses_a_meeting_date_without_any_executive_row_but_not_a_non_executive():
    at = _ex_at([("M1", "P1", D(2025, 10, 2), "EMP1", "present"), ("M2", "P1", D(2025, 12, 9), "EMP1", "present"), ("M3", "P1", D(2025, 12, 20), "EMP1", "present")])
    full = pd.DataFrame({"emp_key": ["EMP1"] * 3, "role_name": "CFO", "as_of": [D(2025, 10, 2), D(2025, 12, 9), D(2025, 12, 20)]})
    assert delivery.executive_attendance(at, full, context=CTX).mtg_key.tolist() == ["M1", "M2", "M3"]
    with pytest.raises(FrameError, match="2025-12-09"):
        delivery.executive_attendance(at, full[full.as_of != D(2025, 12, 9)], context=CTX)
    with pytest.raises(FrameError, match="2025-12-09"):
        delivery.executive_attendance(at, full[~full.as_of.isin([D(2025, 12, 9), D(2025, 12, 20)])], context=CTX)
    other = full.assign(emp_key="EMP8")      # the dates are loaded, EMP1 is simply not an executive on them
    assert delivery.executive_attendance(at, other, context=CTX).empty
    ok = delivery.executive_attendance(at.assign(status=["present", "apology", "absent"]), full[full.as_of == D(2025, 10, 2)], context=CTX)
    assert ok.mtg_key.tolist() == ["M1"], "a date of an attendee who was not present needs no executive row"


def test_a_date_without_an_executive_set_is_declared_by_an_empty_row_and_then_accepted():
    at = _ex_at([("M1", "P1", D(2021, 5, 1), "EMP1", "present"), ("M2", "P1", D(2025, 12, 9), "EMP1", "present")])
    full = pd.DataFrame({"emp_key": ["EMP1"], "role_name": ["CFO"], "as_of": [D(2025, 12, 9)]})
    with pytest.raises(FrameError, match="2021-05-01"):
        delivery.executive_attendance(at, full, context=CTX)
    declared = pd.concat([full, pd.DataFrame({"emp_key": [None], "role_name": [None], "as_of": [D(2021, 5, 1)]})], ignore_index=True)
    assert delivery.executive_attendance(at, declared, context=CTX).mtg_key.tolist() == ["M2"], "nobody was an executive on the declared date"


def test_executive_gap_names_all_executives_present_at_the_first_executive_meeting_and_the_lowest_emp_key():
    ea = pd.DataFrame({"mtg_key": ["M2", "M2", "M2", "M3"], "prj_key": "P1", "date": pd.Timestamp(2025, 12, 9), "emp_key": ["EMP5", "EMP2", "EMP5", "EMP1"],
                       "role_name": ["Chief Financial Officer", "Commercial Director", "Chief Executive Officer", "Chief Executive Officer"]}).assign(date=[pd.Timestamp(2025, 12, 9)] * 3 + [pd.Timestamp(2025, 12, 20)])
    fr = pd.DataFrame({"prj_key": ["P1"], "diary_date": [D(2025, 10, 2)]})
    g = delivery.executive_gap(fr, ea, "P1", context=CTX)
    assert list(g.columns)[:6] == ["prj_key", "first_record", "first_executive_meeting", "first_executive_emp", "first_executive_role", "gap_days"]
    r = g.iloc[0]
    assert r.first_executive_emp == "EMP2" and r.first_executive_role == "Commercial Director", "the lowest emp_key, not the most senior role"
    assert r.executives_present == "EMP2,EMP5", "sorted, each person once, the later meeting is not included"
    never = delivery.executive_gap(fr, ea.iloc[:0], "P1", context=CTX).iloc[0]
    assert never.executives_present is None and list(delivery.executive_gap(fr, ea.iloc[:0], "P1", context=CTX).columns) == list(g.columns)


def test_leaver_is_strictly_before_the_meeting_date_and_a_person_on_the_leave_date_is_not_a_leaver():
    m = _m([("M1", "P1", D(2025, 12, 9), "steering")])
    a = _a([("M1", "employee", "EMP1", None, "present", "x"), ("M1", "employee", "EMP2", None, "present", "x")])
    emp = pd.DataFrame({"emp_key": ["EMP1", "EMP2"], "leave_date": [D(2025, 12, 9), D(2025, 12, 8)]})
    r = delivery.attendance(m, a, employee=emp, context=CTX).set_index("person_key")
    assert r.leaver.to_dict() == {"EMP1": False, "EMP2": True}


def test_timeline_lists_the_earliest_diary_row_of_a_delay_whatever_the_input_order():
    sd = _diary([("P1", D(2025, 10, 9), "later", "E", 1), ("P1", D(2025, 10, 2), "earliest", "E", 1), ("P1", D(2025, 10, 5), "middle", "E", 1)])
    e = pd.DataFrame({"prj_key": [], "risk_no": [], "raised": [], "title": [], "status": []})
    t = delivery.timeline("P1", site_diary=sd, risk=e, meeting=pd.DataFrame({"mtg_key": [], "prj_key": [], "date": [], "meeting_type": [], "title": []}),
                          decision=pd.DataFrame({"mtg_key": [], "seq": [], "text": [], "decision_type": []}), delay_event=pd.DataFrame({"prj_key": [], "seq": [], "start": [], "days": [], "cause_code": []}),
                          plan_version=pd.DataFrame({"prj_key": [], "plan_version": [], "created": [], "reason": []}), context=CTX)
    assert t.text.tolist() == ["earliest"] and t.date.tolist() == [pd.Timestamp(2025, 10, 2)]


def test_decisions_match_the_delay_event_of_their_own_project_when_delay_seq_collides():
    dec = pd.DataFrame({"mtg_key": ["M1", "M2", "M3"], "seq": [1, 1, 1], "text": "t", "decision_type": "schedule", "impact_cost": 0.0, "impact_days": 0, "currency": "EUR",
                        "delay_seq": [1, 1, 2], "co_no": [None] * 3})
    m = _m([("M1", "P1", D(2025, 10, 2), "site"), ("M2", "P2", D(2025, 10, 3), "site"), ("M3", "P1", D(2025, 10, 4), "site")])
    de = pd.DataFrame({"prj_key": ["P1", "P2", "P2"], "seq": [1, 1, 2], "cause_code": ["ground", "weather", "strike"]})
    r = delivery.decisions(dec, m, de, context=CTX).set_index("mtg_key")
    assert r.delay_cause.loc["M1"] == "ground" and r.delay_cause.loc["M2"] == "weather"
    assert pd.isna(r.delay_cause.loc["M3"]), "P1 has no delay 2: the event 2 of P2 must not be taken"
    assert len(r) == 3, "no row is duplicated by the join"


def test_timeline_kind_order_on_one_date_puts_a_meeting_before_its_decisions_and_dates_first():
    sd = _diary([("P1", D(2025, 10, 2), "n", "E", 1)])
    rk = pd.DataFrame({"prj_key": ["P1", "P1"], "risk_no": [1, 2], "raised": [D(2025, 10, 2), D(2025, 10, 1)], "title": ["R1", "R0"], "status": "open"})
    mt = pd.DataFrame({"mtg_key": ["MB", "MA"], "prj_key": "P1", "date": [D(2025, 10, 2), D(2025, 10, 2)], "meeting_type": "site", "title": ["TB", "TA"]})
    de = pd.DataFrame({"prj_key": ["P1"], "seq": [1], "start": [D(2025, 10, 2)], "days": [3], "cause_code": ["g"]})
    dc = pd.DataFrame({"mtg_key": ["MA", "MA", "MB"], "seq": [2, 1, 1], "text": ["a2", "a1", "b1"], "decision_type": "schedule"})
    pv = pd.DataFrame({"prj_key": ["P1"], "plan_version": [2], "created": [D(2025, 10, 2)], "reason": ["g"]})
    t = delivery.timeline("P1", site_diary=sd, risk=rk, meeting=mt, decision=dc, delay_event=de, plan_version=pv, context=CTX)
    assert t.kind.tolist() == ["risk"] + ["meeting"] * 2 + ["decision"] * 3 + ["delay_event", "first_diary_delay", "risk", "plan_version"], "an earlier date first, then meeting, decision, delay_event, first_diary_delay, risk, plan_version"
    assert t[t.kind == "decision"].source_key.tolist() == ["MA/1", "MA/2", "MB/1"] and t[t.kind == "meeting"].source_key.tolist() == ["MB", "MA"], "meetings keep the frame order"


# third review: text and numeric dates of first_record, a fractional delay_seq of decisions, ties of the first diary rows

def test_first_record_refuses_text_that_is_no_date_numbers_and_time_zones_and_accepts_mixed_text():
    with pytest.raises(FrameError, match="not a date"):
        delivery.first_record(_diary([("P", "not a date", "b", "E", 1)]), "P", context=CTX)
    for bad in (20251002, 2025, 20251002.0, True):
        with pytest.raises(FrameError, match="numbers, not dates"):
            delivery.first_record(_diary([("P", bad, "b", "E", 1)]), "P", context=CTX)
    with pytest.raises(FrameError, match="time zone"):
        delivery.first_record(_diary([("P", pd.Timestamp("2025-10-02", tz="UTC"), "b", "E", 1)]), "P", context=CTX)
    d = _diary([("P", "2025-10-02 13:00", "later", "E", 1), ("P", "2025-10-02", "midnight", "E", 1)])
    assert delivery.first_record(d, "P", context=CTX).notes.tolist() == ["midnight"], "text dates with and without a time of day in one column"


def test_decisions_refuse_a_fractional_delay_seq():
    dec = pd.DataFrame({"mtg_key": ["M1"], "seq": [1], "text": "t", "decision_type": "schedule", "impact_cost": 0.0, "impact_days": 0, "currency": "EUR", "delay_seq": [1.5], "co_no": [None]})
    with pytest.raises(FrameError, match="whole numbers"):
        delivery.decisions(dec, _m([("M1", "P1", D(2025, 10, 2), "site")]), context=CTX)
    assert len(delivery.decisions(dec.assign(delay_seq=[2.0]), _m([("M1", "P1", D(2025, 10, 2), "site")]), context=CTX)) == 1, "whole numbers stored as float are fine"


def test_timeline_first_diary_rows_on_one_date_are_ordered_by_delay_seq_whatever_the_input_order():
    rows = [("P1", D(2025, 10, 2), f"n{k}", "E", k) for k in range(1, 41)]
    e = lambda cols: pd.DataFrame({c: [] for c in cols})
    results = set()
    for seed in range(6):
        sd = _diary(rows).sample(frac=1, random_state=seed)
        t = delivery.timeline("P1", site_diary=sd, risk=e(["prj_key", "risk_no", "raised", "title", "status"]), meeting=e(["mtg_key", "prj_key", "date", "meeting_type", "title"]),
                              decision=e(["mtg_key", "seq", "text", "decision_type"]), delay_event=e(["prj_key", "seq", "start", "days", "cause_code"]), plan_version=e(["prj_key", "plan_version", "created", "reason"]), context=CTX)
        results.add(tuple(t.source_key))
    assert results == {tuple(str(k) for k in range(1, 41))}
