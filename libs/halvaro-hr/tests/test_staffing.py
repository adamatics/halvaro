"""allocation_load, handover_report, experience_summary, staffing_candidates, planned_vs_actual_hours on synthetic frames (the baseline tests are in the closed repository)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, registry

D = dt.date


def _al(rows):
    return pd.DataFrame(rows, columns=["emp_key", "prj_key", "start", "end", "percent"])


def test_load_is_the_sum_over_overlapping_stints_in_segments_and_flags_the_limit():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 31), 60), ("EMP-1", "P2", D(2026, 1, 20), D(2026, 2, 10), 50), ("EMP-2", "P1", D(2026, 1, 1), D(2026, 1, 5), 100), ("EMP-2", "P3", D(2026, 1, 6), D(2026, 1, 9), 100)])
    l = hr.allocation_load(a)
    e1 = l[l.emp_key == "EMP-1"][["start", "end", "load", "over_limit"]].values.tolist()
    assert e1 == [[pd.Timestamp(2026, 1, 1), pd.Timestamp(2026, 1, 19), 60.0, False], [pd.Timestamp(2026, 1, 20), pd.Timestamp(2026, 1, 31), 110.0, True],
                  [pd.Timestamp(2026, 2, 1), pd.Timestamp(2026, 2, 10), 50.0, False]]
    e2 = l[l.emp_key == "EMP-2"]
    assert e2.load.tolist() == [100.0] and not e2.over_limit.any() and e2.start.tolist() == [pd.Timestamp(2026, 1, 1)] and e2.end.tolist() == [pd.Timestamp(2026, 1, 9)], \
        "back to back stints of 100 percent are not 200, and equal neighbours are one segment"
    assert hr.allocation_load(a, limit=55).over_limit.tolist() == [True, True, False, True], "the limit is a parameter"


def test_load_open_allocation_and_bad_input():
    l = hr.allocation_load(_al([("EMP-1", "P1", D(2026, 1, 1), None, 40)]))
    assert l.load.tolist() == [40.0] and pd.isna(l.end.iloc[0])
    with pytest.raises(FrameError, match="end before they start"):
        hr.allocation_load(_al([("EMP-1", "P1", D(2026, 2, 1), D(2026, 1, 1), 40)]))
    with pytest.raises(FrameError, match="percent must be numeric"):
        hr.allocation_load(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 2), None)]))
    with pytest.raises(FrameError, match="lacks column"):
        hr.allocation_load(_al([]).drop(columns="percent"))
    assert hr.allocation_load(_al([])).empty


def _lv(rows):
    return pd.DataFrame(rows, columns=["emp_key", "leave_type", "start", "end"])


def test_handover_ends_before_replacement_window_and_planned_return():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50), ("EMP-1", "P2", D(2026, 1, 1), D(2026, 5, 1), 40),         # P2 ended long before: not a handover
             ("EMP-1", "P1", D(2027, 3, 1), D(2027, 9, 1), 50),                                                          # planned return
             ("EMP-7", "P1", D(2026, 6, 15), D(2026, 12, 18), 50), ("EMP-8", "P1", D(2026, 6, 21), D(2026, 12, 18), 50)])    # EMP-7 starts 2 days after the leave start, EMP-8 8 days
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 13), D(2027, 2, 28)), ("EMP-1", "holiday", D(2026, 8, 1), D(2026, 8, 5))])
    h = hr.handover_report(a, lv)
    assert h.kind.tolist() == ["ends_before_leave", "replacement", "planned_return"] and h.emp_key.tolist() == ["EMP-1", "EMP-7", "EMP-1"], "a holiday is not a long leave; EMP-8 starts outside 7 days"
    assert h[h.kind == "replacement"].start.iloc[0] == pd.Timestamp(2026, 6, 15)
    wide = hr.handover_report(a, lv, replacement_days=8)
    assert wide.emp_key.tolist() == ["EMP-1", "EMP-7", "EMP-8", "EMP-1"]
    assert (hr.handover_report(a, lv, lookback_days=0).kind != "ends_before_leave").all(), "the allocation ended the day before the leave: outside a lookback of zero"
    openleave = hr.handover_report(a, _lv([("EMP-1", "parental", D(2026, 6, 13), None)]))
    assert "planned_return" not in set(openleave.kind), "no return while the leave has no end"
    with pytest.raises(FrameError, match="whole number"):
        hr.handover_report(a, lv, lookback_days=-1)


def _roster(rows):
    return pd.DataFrame(rows, columns=["prj_key", "emp_key", "project_role", "hours_total", "basis", "legacy"])


def test_experience_total_over_both_bases_lead_flag_rank_and_leavers():
    r = _roster([("P1", "EMP-1", "lead engineer", 100.0, "time_entries", False), ("P2", "EMP-1", "lead engineer", 50.0, "roster", True), ("P1", "EMP-2", "engineer", 160.0, "time_entries", False),
                 ("P1", "EMP-3", "engineer", 150.0, "time_entries", False), ("P2", "EMP-3", "engineer", 0.0, "roster", True)])
    emp = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3"], "leave_date": [None, D(2025, 5, 1), None]})
    x = hr.experience_summary(r, emp)
    assert x.set_index("emp_key").hours.to_dict() == {"EMP-1": 150.0, "EMP-2": 160.0, "EMP-3": 150.0}
    assert x.emp_key.tolist() == ["EMP-2", "EMP-1", "EMP-3"], "by hours, ties by emp_key"
    e1 = x.set_index("emp_key").loc["EMP-1"]
    assert (e1.hours_time_entries, e1.hours_roster, e1.n_projects, e1.is_lead, e1.legacy_projects) == (100.0, 50.0, 2, True, 1) and e1.lead_roles == ["lead engineer"]
    assert x.set_index("emp_key").leaver.to_dict() == {"EMP-1": False, "EMP-2": True, "EMP-3": False} and x["rank"].tolist() == [1, 2, 3]
    assert hr.experience_summary(r, lead_roles=["engineer"]).set_index("emp_key").is_lead.to_dict() == {"EMP-1": False, "EMP-2": True, "EMP-3": True}, "the lead roles are a parameter"
    with pytest.raises(FrameError, match="hours_total must be numeric"):
        hr.experience_summary(r.assign(hours_total=None))


def test_candidates_keep_the_rank_show_leavers_and_check_certificates():
    r = _roster([("P1", "EMP-1", "lead engineer", 100.0, "time_entries", False), ("P1", "EMP-2", "foreman", 90.0, "time_entries", False), ("P1", "EMP-3", "foreman", 80.0, "time_entries", False)])
    x = hr.experience_summary(r)
    s1 = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "status": ["on_leave", "left"]})
    s2 = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3"], "status": ["available", "left", "available"]})
    valid = {"mar": pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-3"], "qual_key": ["QUAL-001", "QUAL-002", "QUAL-001"]})}
    c = hr.staffing_candidates(x, {"jan": s1, "mar": s2}, valid=valid, qual_keys=["QUAL-001", "QUAL-002"])
    assert c.emp_key.tolist() == ["EMP-1", "EMP-2", "EMP-3"], "order of the experience frame"
    assert c.staffable_jan.tolist() == [False, False, False] and c.staffable_mar.tolist() == [True, False, True] and pd.isna(c.status_jan.iloc[2]), "missing from a status frame: not staffable"
    assert c.certs_mar.tolist() == [True, False, False], "EMP-3 holds only one of the two qualifications"
    with pytest.raises(FrameError, match="more than one row"):
        hr.staffing_candidates(x, {"jan": pd.concat([s1, s1])})
    with pytest.raises(FrameError, match="qual_keys"):
        hr.staffing_candidates(x, {"jan": s1}, valid=valid)


def test_plan_hours_against_booked_hours():
    ev = pd.DataFrame({"prj_key": ["P1", "P1", "P2"], "estimate_version": [1, 2, 1], "type": ["tender", "budget", "budget"]})
    el = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P2"], "estimate_version": [1, 2, 2, 1], "cst_key": ["CST-110", "CST-110", "CST-200", "CST-430"], "quantity": [999.0, 100.0, 5000.0, 40.0]})
    te = pd.DataFrame({"prj_key": ["P1", "P1", "P3"], "hours": [60.0, 70.0, 5.0]})
    p = hr.planned_vs_actual_hours(ev, el, te).set_index("prj_key")
    assert p.plan_hours.to_dict() == {"P1": 100.0, "P2": 40.0, "P3": 0.0} and p.actual_hours.to_dict() == {"P1": 130.0, "P2": 0.0, "P3": 5.0}
    assert p.loc["P1", "ratio"] == 1.3 and p.loc["P2", "ratio"] == 0.0 and pd.isna(p.loc["P3", "ratio"]), "no plan hours: no ratio"
    assert hr.planned_vs_actual_hours(ev, el, te, version_type="tender").set_index("prj_key").plan_hours.to_dict() == {"P1": 999.0, "P3": 0.0}
    with pytest.raises(FrameError, match="more than one budget"):
        hr.planned_vs_actual_hours(pd.concat([ev, ev[ev.type == "budget"]]), el, te)


def test_registered():
    reg = registry.registered()
    for n in ("allocation_load", "handover_report", "experience_summary", "staffing_candidates", "planned_vs_actual_hours"):
        m = reg[f"halvaro.hr.staffing.{n}"]
        assert m.sources
    assert registry.check() == []


# the baseline


# review fixes

def test_float_percents_leave_no_phantom_segment_and_bad_input_is_refused():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 10), 33.3), ("EMP-1", "P2", D(2026, 1, 1), D(2026, 1, 10), 33.3), ("EMP-1", "P3", D(2026, 1, 1), D(2026, 1, 10), 33.4),
             ("EMP-2", "P1", D(2026, 1, 1), D(2026, 1, 3), 66.6), ("EMP-2", "P2", D(2026, 1, 1), D(2026, 1, 3), 0.3), ("EMP-2", "P3", D(2026, 1, 4), D(2026, 1, 6), 12.7)])
    l = hr.allocation_load(a)
    assert l[l.emp_key == "EMP-1"].load.tolist() == [100.0] and not l.over_limit.any(), "33.3 + 33.3 + 33.4 is 100, not 99.99999999999999"
    assert l[l.emp_key == "EMP-2"].load.tolist() == [66.9, 12.7] and (l.load > 1e-6).all(), "no segment of float dust between and after stints"
    for bad, match in ((_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 2), -5)]), "zero or more"), (_al([(None, "P1", D(2026, 1, 1), D(2026, 1, 2), 5)]), "without emp_key"),
                       (_al([("EMP-1", "P1", D(2026, 1, 1), D(2250, 1, 2), 5)]), "2200")):
        with pytest.raises(FrameError, match=match):
            hr.allocation_load(bad)
    with pytest.raises(FrameError, match="limit must be a number"):
        hr.allocation_load(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 2), 5)]), limit=None)


def test_handover_boundaries_overlap_return_window_and_input_checks():
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 13), D(2026, 6, 30))])
    for end, kind in ((D(2026, 6, 12), "ends_before_leave"), (D(2026, 6, 13), "overlaps_leave"), (D(2026, 9, 1), "overlaps_leave"), (None, "overlaps_leave")):
        h = hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), end, 50)]), lv)
        assert h.kind.tolist() == [kind], (end, "an allocation still running on the leave start day is flagged")
    assert hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 6), 50)]), lv).kind.tolist() == ["ends_before_leave"], "exactly the lookback before the leave"
    assert hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 6), 50)]), lv, lookback_days=6).empty, "one day outside a lookback of six"
    assert hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 5), 50)]), lv).empty, "one day outside the default lookback"
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50), ("EMP-1", "P1", D(2026, 7, 1), D(2026, 9, 1), 50), ("EMP-1", "P1", D(2029, 1, 1), D(2029, 6, 1), 50), ("EMP-1", "P2", D(2026, 7, 15), D(2026, 9, 1), 20)])
    two = _lv([("EMP-1", "extended_leave", D(2026, 6, 13), D(2026, 6, 30)), ("EMP-1", "parental", D(2028, 1, 1), D(2028, 3, 1))])
    h = hr.handover_report(a, two)
    back = h[(h.kind == "planned_return") & (h.leave_type == "extended_leave")]
    assert back.start.tolist() == [pd.Timestamp(2026, 7, 1), pd.Timestamp(2026, 7, 15)] and back.prj_key.tolist() == ["P1", "P2"], "the first return allocation per project, none from 2029"
    assert h[(h.kind == "planned_return") & (h.leave_type == "parental")].start.tolist() == [pd.Timestamp(2029, 1, 1)]
    start_day = hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50), ("EMP-9", "P1", D(2026, 6, 13), D(2026, 7, 1), 50)]), lv)
    assert start_day.kind.tolist() == ["ends_before_leave", "replacement"], "a replacement starting on the leave start day counts"
    assert hr.handover_report(a, pd.concat([lv, lv])).equals(hr.handover_report(a, lv)), "duplicate leave rows are reported once"
    with pytest.raises(FrameError, match="end before they start"):
        hr.handover_report(_al([("EMP-1", "P1", D(2026, 2, 1), D(2026, 1, 1), 5)]), lv)
    with pytest.raises(FrameError, match="leave records end before"):
        hr.handover_report(a, _lv([("EMP-1", "parental", D(2026, 3, 1), D(2026, 2, 1))]))
    with pytest.raises(FrameError, match="leave_types"):
        hr.handover_report(a, lv, leave_types=None)
    assert hr.handover_report(a, _lv([("EMP-1", "holiday", D(2026, 6, 13), D(2026, 6, 30))])).empty and hr.handover_report(a, _lv([("EMP-1", "parental", D(2026, 6, 13), D(2026, 6, 30))])).kind.iloc[0] == "ends_before_leave", "parental is a long leave"


def test_experience_checks_ties_empty_roster_as_of_and_basis():
    r = _roster([("P1", "EMP-1", "lead engineer", 0.1 + 0.2, "time_entries", False), ("P1", "EMP-2", "engineer", 0.3, "time_entries", False)])
    assert hr.experience_summary(r).emp_key.tolist() == ["EMP-1", "EMP-2"] and hr.experience_summary(r.iloc[::-1]).emp_key.tolist() == ["EMP-1", "EMP-2"], "float noise does not break the tie"
    e = hr.experience_summary(r.iloc[:0].astype({"hours_total": float}), pd.DataFrame({"emp_key": [], "leave_date": []}))
    assert e.empty and {"rank", "emp_key", "hours", "leaver"} <= set(e.columns), "an empty roster keeps its columns"
    emp = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "leave_date": [D(2099, 1, 1), D(2025, 5, 1)]})
    assert hr.experience_summary(r, emp).leaver.tolist() == [True, True]
    assert hr.experience_summary(r, emp, as_of=D(2026, 11, 30)).leaver.tolist() == [False, True], "a future leave date is not a leaver on the date"
    assert hr.experience_summary(r, emp.iloc[:1]).set_index("emp_key").leaver.to_dict() == {"EMP-1": True, "EMP-2": False}, "a person missing from the employee frame is not a leaver"
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.experience_summary(r, pd.concat([emp, emp]))
    with pytest.raises(FrameError, match="basis must be"):
        hr.experience_summary(r.assign(basis="estimate"))
    with pytest.raises(FrameError, match="null emp_key"):
        hr.experience_summary(r.assign(emp_key=[None, "EMP-2"]))
    with pytest.raises(FrameError, match="legacy must be"):
        hr.experience_summary(r.assign(legacy="True"))
    two = _roster([("P1", "EMP-1", "foreman", 10.0, "time_entries", True), ("P1", "EMP-1", "engineer", 5.0, "roster", True), ("P2", "EMP-1", "engineer", 5.0, "roster", False)])
    row = hr.experience_summary(two).iloc[0]
    assert (row.n_projects, row.legacy_projects, row.is_lead, row.hours_time_entries + row.hours_roster == row.hours) == (2, 1, True, True), "projects are counted once, not per row"
    assert hr.experience_summary(two[two.project_role == "foreman"]).iloc[0].is_lead, "foreman is a lead role by default"


def test_candidates_count_distinct_qualifications_and_plan_hours_reject_bad_codes():
    r = _roster([("P1", "EMP-1", "engineer", 1.0, "time_entries", False)])
    x = hr.experience_summary(r)
    v = {"d": pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-1"], "qual_key": ["QUAL-001", "QUAL-001", "QUAL-002"]})}
    assert hr.staffing_candidates(x, {}, valid=v, qual_keys=["QUAL-001", "QUAL-002"]).certs_d.tolist() == [True], "two distinct qualifications held"
    assert hr.staffing_candidates(x, {}, valid={"d": v["d"].iloc[:2]}, qual_keys=["QUAL-001", "QUAL-002"]).certs_d.tolist() == [False], "a repeated row is not a second qualification"
    ev = pd.DataFrame({"prj_key": ["P1"], "estimate_version": [1], "type": ["budget"]})
    te = pd.DataFrame({"prj_key": ["P1"], "hours": [1.0]})
    ok = pd.DataFrame({"prj_key": ["P1"], "estimate_version": [1], "cst_key": ["CST-110"], "quantity": [5.0]})
    for bad, match in ((ok.assign(cst_key="CST-ABC"), "CST-<digits>"), (ok.assign(cst_key="XX-110"), "CST-<digits>"), (ok.assign(cst_key=None), "CST-<digits>"), (ok.assign(estimate_version="1"), "differs in type")):
        with pytest.raises(FrameError, match=match):
            hr.planned_vs_actual_hours(ev, bad, te)
    with pytest.raises(FrameError, match="whole cost code"):
        hr.planned_vs_actual_hours(ev, ok, te, labour_cost_codes="110")
    with pytest.raises(FrameError, match="hours must be numeric"):
        hr.planned_vs_actual_hours(ev, ok, te.assign(hours="1"))
    assert hr.planned_vs_actual_hours(ev, ok, te).ratio.tolist() == [0.2]


# second review: crew plan, leaver boundary, vectorised handover, boundaries and bad input

def _cp(rows):
    return pd.DataFrame(rows, columns=["emp_key", "prj_key", "planned_start", "planned_end", "percent"])


def _handover_reference(allocation, leave_record, leave_types, lookback_days=7, replacement_days=7):
    """The first, loop based handover_report (O(leaves x allocations)), kept as the reference the vectorised version must equal."""
    types = [leave_types] if isinstance(leave_types, str) else list(leave_types)
    lv = leave_record[leave_record["leave_type"].isin(types)][["emp_key", "leave_type", "start", "end"]].copy()
    al = allocation[["emp_key", "prj_key", "start", "end", "percent"]].copy()
    for f, cs in ((lv, ("start", "end")), (al, ("start", "end"))):
        for c in cs:
            f[c] = pd.to_datetime(f[c])
    lv = lv.drop_duplicates().sort_values(["emp_key", "start", "leave_type"]).reset_index(drop=True)
    rows = []
    for r, next_start in zip(lv.itertuples(), lv.groupby("emp_key")["start"].shift(-1)):
        head = {"leave_emp_key": r.emp_key, "leave_type": r.leave_type, "leave_start": r.start, "leave_end": r.end}
        own = al[al["emp_key"] == r.emp_key]

        def add(kind, frame):
            for x in frame.sort_values(["prj_key", "start", "emp_key"]).itertuples():
                rows.append({**head, "kind": kind, "prj_key": x.prj_key, "emp_key": x.emp_key, "percent": x.percent, "start": x.start, "end": x.end})
        before = own[(own["end"] >= r.start - pd.DateOffset(days=lookback_days)) & (own["end"] < r.start)]
        running = own[(own["start"] <= r.start) & (own["end"].isna() | (own["end"] >= r.start))]
        add("ends_before_leave", before)
        add("overlaps_leave", running)
        for prj in sorted(set(before["prj_key"]) | set(running["prj_key"])):
            add("replacement", al[(al["prj_key"] == prj) & (al["emp_key"] != r.emp_key) & (al["start"] >= r.start) & (al["start"] <= r.start + pd.DateOffset(days=replacement_days))])
        if pd.notna(r.end):
            back = own[own["start"] > r.end]
            if pd.notna(next_start):
                back = back[back["start"] < next_start]
            add("planned_return", back.sort_values("start").drop_duplicates("prj_key", keep="first"))
    return pd.DataFrame(rows, columns=["leave_emp_key", "leave_type", "leave_start", "leave_end", "kind", "prj_key", "emp_key", "percent", "start", "end"])


def test_the_vectorised_handover_equals_the_loop_reference_on_random_input():
    rng = np.random.default_rng(7)
    day0 = pd.Timestamp(2026, 1, 1)

    def d(n):
        return (day0 + pd.Timedelta(days=int(n))).date()
    al = []
    for i in range(160):
        s = int(rng.integers(0, 120))
        al.append((f"E{rng.integers(0, 6)}", f"P{rng.integers(0, 4)}", d(s), None if rng.random() < 0.15 else d(s + int(rng.integers(0, 40))), int(rng.integers(1, 100))))
    al = _al(list(dict.fromkeys(al)))
    lv = []
    for i in range(40):
        s = int(rng.integers(0, 120))
        lv.append((f"E{rng.integers(0, 6)}", str(rng.choice(["extended_leave", "parental", "holiday"])), d(s), None if rng.random() < 0.15 else d(s + int(rng.integers(0, 30)))))
    lv = _lv(lv)
    for types in (("extended_leave", "parental"), ("extended_leave", "parental", "holiday"), "holiday"):
        for lb, rd in ((7, 7), (0, 0), (3, 12)):
            want = _handover_reference(al, lv, types, lb, rd)
            got = hr.handover_report(al, lv, leave_types=types, lookback_days=lb, replacement_days=rd)
            pd.testing.assert_frame_equal(got, want)
    assert hr.handover_report(al, lv, leave_types=("extended_leave", "parental", "holiday")).kind.nunique() == 4, "the random frames exercise all four kinds"


def test_handover_boundaries_on_the_leave_start_and_end_day_and_the_next_leave():
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 13), D(2026, 6, 30)), ("EMP-1", "parental", D(2026, 12, 1), D(2026, 12, 31))])

    def kinds(rows, **kw):
        h = hr.handover_report(_al(rows), lv, **kw)
        return list(zip(h.leave_type, h.kind, h.start))
    first = lambda *x: [t for t in kinds(*x) if t[0] == "extended_leave"]            # noqa: E731
    # an allocation that starts exactly on the leave start day runs on that day; one day later it does not
    assert first([("EMP-1", "P1", D(2026, 6, 13), D(2026, 7, 31), 50)])[0][:2] == ("extended_leave", "overlaps_leave")
    assert not any(k == "overlaps_leave" for _, k, _ in first([("EMP-1", "P1", D(2026, 6, 14), D(2026, 7, 31), 50)])), "starting the day after the leave started is not running on the start day"
    # the return: not on the leave end day, yes on the day after
    assert not any(k == "planned_return" for _, k, _ in first([("EMP-1", "P1", D(2026, 6, 30), D(2026, 7, 31), 50)]))
    assert first([("EMP-1", "P1", D(2026, 7, 1), D(2026, 7, 31), 50)]) == [("extended_leave", "planned_return", pd.Timestamp(2026, 7, 1))]
    # the next long leave bounds the return: starting on its first day belongs to the next leave, the day before to this one
    assert not any(k == "planned_return" for _, k, _ in first([("EMP-1", "P1", D(2026, 12, 1), D(2026, 12, 20), 50)])), "equal to the next leave start is not before it"
    assert first([("EMP-1", "P1", D(2026, 11, 30), D(2026, 12, 20), 50)]) == [("extended_leave", "planned_return", pd.Timestamp(2026, 11, 30))]
    # one return per project, the earliest, whatever the order of the input
    rows = [("EMP-1", "P1", D(2026, 9, 1), D(2026, 9, 30), 20), ("EMP-1", "P1", D(2026, 7, 1), D(2026, 7, 31), 50), ("EMP-1", "P1", D(2026, 8, 1), D(2026, 8, 31), 30), ("EMP-1", "P2", D(2026, 8, 5), D(2026, 8, 9), 10)]
    for order in (rows, rows[::-1]):
        h = hr.handover_report(_al(order), lv)
        h = h[(h.leave_type == "extended_leave") & (h.kind == "planned_return")]
        assert h.prj_key.tolist() == ["P1", "P2"] and h.start.tolist() == [pd.Timestamp(2026, 7, 1), pd.Timestamp(2026, 8, 5)] and h.percent.tolist() == [50, 10]


def test_float_dust_rounding_is_nine_decimals():
    one = lambda p: hr.allocation_load(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 5), p)]))            # noqa: E731
    assert one(4e-10).empty, "below nine decimals is dust, not a segment"
    assert one(4e-7).load.tolist() == [4e-7], "above nine decimals is load: a coarser rounding would drop it"
    both = hr.allocation_load(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 5), 40), ("EMP-1", "P2", D(2026, 1, 1), D(2026, 1, 5), 4e-7)]))
    assert both.load.tolist() == [40.0000004], "40 + 4e-7 keeps its seventh decimal"
    assert one(0.1 + 0.2).load.tolist() == [0.3]


def test_rank_ties_are_hours_equal_to_six_decimals():
    def order(h1, h2):
        r = _roster([("P1", "EMP-1", "engineer", h1, "time_entries", False), ("P1", "EMP-2", "engineer", h2, "time_entries", False)])
        return hr.experience_summary(r).emp_key.tolist()
    assert order(1.0, 1.0000004) == ["EMP-1", "EMP-2"], "four tenths of a millionth tie: emp_key decides"
    assert order(1.0, 1.000002) == ["EMP-2", "EMP-1"], "two millionths are a difference"
    assert order(1.0000004, 1.0) == ["EMP-1", "EMP-2"]


def test_leaver_is_strictly_before_the_date_like_status_on():
    emp = pd.DataFrame({"emp_key": ["ON", "BEFORE", "AFTER"], "leave_date": [D(2026, 11, 30), D(2026, 11, 29), D(2026, 12, 1)]})
    r = _roster([("P1", k, "engineer", 1.0, "time_entries", False) for k in ("ON", "BEFORE", "AFTER")])
    x = hr.experience_summary(r, emp, as_of=D(2026, 11, 30)).set_index("emp_key").leaver.to_dict()
    assert x == {"ON": False, "BEFORE": True, "AFTER": False}, "on the leave date the person is still there"
    assert hr.experience_summary(r, emp).leaver.all(), "without a date any leave date makes a leaver"
    full = emp.assign(hire_date=D(2020, 1, 1))
    st = hr.status_on(full, _lv([]), D(2026, 11, 30)).set_index("emp_key").status.to_dict()
    assert st == {"ON": "available", "BEFORE": "left", "AFTER": "available"}
    ex = hr.experience_summary(r, emp, as_of=D(2026, 11, 30))
    c = hr.staffing_candidates(ex, {"d": hr.status_on(full, _lv([]), D(2026, 11, 30))}).set_index("emp_key")
    assert c.staffable_d.to_dict() == {"ON": True, "BEFORE": False, "AFTER": True}  and c.leaver.to_dict() == {"ON": False, "BEFORE": True, "AFTER": False}, "a leaver on the date is never staffable, and the leaver flag agrees with the status"


def test_crew_plan_gives_the_planned_return():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50)])
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 15), D(2027, 2, 28)), ("EMP-1", "parental", D(2028, 1, 1), D(2028, 3, 1))])
    plan = _cp([("EMP-1", "P5", D(2027, 1, 11), D(2027, 12, 11), 25), ("EMP-1", "P6", D(2027, 2, 28), D(2027, 3, 31), 25), ("EMP-1", "P7", D(2027, 3, 1), D(2028, 2, 28), 25),
                ("EMP-1", "P8", D(2028, 1, 1), D(2028, 6, 1), 25), ("EMP-9", "P9", D(2027, 3, 1), D(2027, 6, 1), 25), ("EMP-1", "P3", D(2027, 4, 1), None, 10)])
    plain = hr.handover_report(a, lv)
    assert "source" not in plain.columns and plain.kind.tolist() == ["ends_before_leave"], "without a crew plan: the old output"
    h = hr.handover_report(a, lv, crew_plan=plan)
    assert list(h.columns) == list(plain.columns) + ["source"]
    back = h[h.kind == "planned_return"]
    assert back.prj_key.tolist() == ["P3", "P7"] and back.start.tolist() == [pd.Timestamp(2027, 4, 1), pd.Timestamp(2027, 3, 1)] and back.source.tolist() == ["crew_plan", "crew_plan"], \
        "not P5 (inside the leave), not P6 (the leave end day), not P8 (the next leave start), not another person's plan"
    assert back.end.iloc[1] == pd.Timestamp(2028, 2, 28) and pd.isna(back.end.iloc[0]) and back.percent.tolist() == [10, 25], "a null planned_end is open"
    assert h[~h.kind.isin(["planned_return", "plan_during_leave"])].source.eq("allocation").all()
    pd.testing.assert_frame_equal(h[h.kind == "ends_before_leave"].drop(columns="source").reset_index(drop=True), plain)
    # the day after the leave ended starts the return; an allocation wins a tie, an earlier plan wins over a later allocation
    assert hr.handover_report(a, lv, crew_plan=_cp([("EMP-1", "P1", D(2027, 3, 1), D(2027, 4, 1), 25)])).query("kind == 'planned_return'").start.tolist() == [pd.Timestamp(2027, 3, 1)]
    tie = hr.handover_report(pd.concat([a, _al([("EMP-1", "P1", D(2027, 3, 1), D(2027, 3, 31), 60)])]), lv, crew_plan=_cp([("EMP-1", "P1", D(2027, 3, 1), D(2027, 4, 1), 25)]))
    assert tie[tie.kind == "planned_return"][["source", "percent"]].values.tolist() == [["allocation", 60]]
    early = hr.handover_report(pd.concat([a, _al([("EMP-1", "P1", D(2027, 5, 1), D(2027, 5, 31), 60)])]), lv, crew_plan=_cp([("EMP-1", "P1", D(2027, 3, 1), D(2027, 4, 1), 25)]))
    assert early[early.kind == "planned_return"][["source", "percent"]].values.tolist() == [["crew_plan", 25]]
    empty = hr.handover_report(a.iloc[:0], lv, crew_plan=plan.iloc[:0])
    assert empty.empty and list(empty.columns)[-1] == "source"
    for bad, match in ((plan.assign(planned_start=[None] + [D(2027, 3, 1)] * 5), "no planned_start"), (pd.concat([plan, plan.iloc[:1]]), "duplicate rows"),
                       (_cp([("EMP-1", "P5", D(2027, 5, 1), D(2027, 4, 1), 25)]), "end before they start"), (plan.drop(columns="percent"), "lacks column")):
        with pytest.raises(FrameError, match=match):
            hr.handover_report(a, lv, crew_plan=bad)


def test_allocation_rows_without_a_start_or_repeated_are_refused():
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 13), D(2026, 6, 30))])
    ok = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50), ("EMP-2", "P1", D(2026, 6, 14), D(2026, 7, 12), 50)])
    assert hr.handover_report(ok, lv).kind.tolist() == ["ends_before_leave", "replacement"]
    with pytest.raises(FrameError, match="no start date"):
        hr.handover_report(ok.assign(start=[D(2026, 1, 1), None]), lv)
    with pytest.raises(FrameError, match="duplicate rows"):
        hr.handover_report(pd.concat([ok, ok.iloc[:1]]), lv)
    with pytest.raises(FrameError, match="duplicate rows"):
        hr.handover_report(ok.assign(alc_key=["ALC-1", "ALC-1"]), lv)
    assert hr.handover_report(ok.assign(alc_key=["ALC-1", "ALC-2"]), lv).kind.tolist() == ["ends_before_leave", "replacement"], "distinct keys are fine"
    assert hr.handover_report(_al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50), ("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 40)]), lv).shape[0] == 2, "same dates but another percent is another row"


def test_plan_hours_refuse_unknown_version_type_nan_negative_and_unbooked_hours():
    ev = pd.DataFrame({"prj_key": ["P1"], "estimate_version": [1], "type": ["budget"]})
    el = pd.DataFrame({"prj_key": ["P1", "P1"], "estimate_version": [1, 1], "cst_key": ["CST-110", "CST-120"], "quantity": [5.0, 3.0]})
    te = pd.DataFrame({"prj_key": ["P1"], "hours": [4.0]})
    assert hr.planned_vs_actual_hours(ev, el, te).plan_hours.tolist() == [8.0]
    with pytest.raises(FrameError, match="no estimate version of type 'Budget'"):
        hr.planned_vs_actual_hours(ev, el, te, version_type="Budget")
    with pytest.raises(FrameError, match="no estimate version of type"):
        hr.planned_vs_actual_hours(ev.assign(type="final"), el, te)
    with pytest.raises(FrameError, match="quantity must be numeric"):
        hr.planned_vs_actual_hours(ev, el.assign(quantity=[5.0, np.nan]), te)
    with pytest.raises(FrameError, match="quantity must be numeric"):
        hr.planned_vs_actual_hours(ev, el.assign(quantity=["5", "3"]), te)
    with pytest.raises(FrameError, match="no prj_key"):
        hr.planned_vs_actual_hours(ev, el, pd.DataFrame({"prj_key": ["P1", None], "hours": [4.0, 1.0]}))
    with pytest.raises(FrameError, match="negative plan hours"):
        hr.planned_vs_actual_hours(ev, el.assign(quantity=[5.0, -0.5]), te)
    assert hr.planned_vs_actual_hours(ev, el.assign(cst_key=["CST-110", "CST-200"], quantity=[5.0, -3.0]), te).plan_hours.tolist() == [5.0], "a negative quantity on a line that is not labour is not plan hours"


def _brute_load(allocation):
    """Daily expansion of the allocations up to a horizon past every date, then runs of equal load per person (a run that reaches the horizon of a person with an open allocation is open): the reference for allocation_load."""
    dates = pd.to_datetime(pd.concat([allocation["start"], allocation["end"].dropna()]))
    horizon = dates.max() + pd.Timedelta(days=30)
    out = []
    for emp, g in allocation.groupby("emp_key"):
        total = {}
        for r in g.itertuples():
            last = horizon if r.end is None or pd.isna(r.end) else pd.Timestamp(r.end)
            for x in pd.date_range(pd.Timestamp(r.start), last, freq="D"):
                total[x] = total.get(x, 0) + r.percent
        runs = []
        for x in sorted(total):
            if runs and runs[-1][1] + pd.Timedelta(days=1) == x and runs[-1][2] == total[x]:
                runs[-1][1] = x
            else:
                runs.append([x, x, total[x]])
        for s, e, v in runs:
            out.append((emp, s, pd.NaT if g["end"].isna().any() and e == horizon else e, float(v)))
    return pd.DataFrame(out, columns=["emp_key", "start", "end", "load"])


def test_allocation_load_equals_a_daily_expansion():
    rng = np.random.default_rng(3)
    base = pd.Timestamp(2026, 1, 1)
    rows = []
    for i in range(60):
        s = int(rng.integers(0, 90))
        rows.append((f"E{rng.integers(0, 5)}", "P1", (base + pd.Timedelta(days=s)).date(),
                     None if rng.random() < 0.1 else (base + pd.Timedelta(days=s + int(rng.integers(0, 25)))).date(), int(rng.choice([10, 20, 50]))))
    a = _al(rows)
    got = hr.allocation_load(a).drop(columns="over_limit")
    pd.testing.assert_frame_equal(got, _brute_load(a))
    assert len(got) > 25 and got.end.isna().sum() == a[a.end.isna()].emp_key.nunique() > 0, "enough segments, and the open allocations give one open segment per person"
    fixed = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 10), 50), ("EMP-1", "P2", D(2026, 1, 11), D(2026, 1, 20), 50), ("EMP-1", "P3", D(2026, 1, 25), None, 30), ("EMP-1", "P4", D(2026, 1, 26), None, 30)])
    g = hr.allocation_load(fixed)
    assert g.start.tolist() == [pd.Timestamp(2026, 1, 1), pd.Timestamp(2026, 1, 25), pd.Timestamp(2026, 1, 26)] and g.load.tolist() == [50.0, 30.0, 60.0]
    assert g.end.iloc[0] == pd.Timestamp(2026, 1, 20) and g.end.iloc[1] == pd.Timestamp(2026, 1, 25) and g.end.iloc[2:].isna().all()


def test_a_plan_row_that_starts_inside_the_leave_is_reported_as_plan_during_leave():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 6, 12), 50)])
    lv = _lv([("EMP-1", "extended_leave", D(2026, 6, 15), D(2027, 2, 28)), ("EMP-2", "extended_leave", D(2026, 6, 15), None)])
    plan = _cp([("EMP-1", "P5", D(2027, 1, 11), D(2027, 12, 11), 25),      # inside the leave
                ("EMP-1", "P6", D(2026, 6, 15), D(2027, 3, 31), 25),       # on the leave start day
                ("EMP-1", "P7", D(2027, 2, 28), D(2027, 3, 31), 25),       # on the leave end day (still on leave)
                ("EMP-1", "P8", D(2027, 3, 1), D(2027, 6, 1), 25),         # after: planned_return, not during
                ("EMP-1", "P9", D(2026, 6, 14), D(2027, 6, 1), 25),        # started before the leave: not looked at
                ("EMP-2", "P2", D(2030, 1, 1), None, 10),                  # the leave of EMP-2 has no end: any day from its start is inside
                ("EMP-2", "P3", D(2026, 6, 14), None, 10),
                ("EMP-9", "P4", D(2027, 1, 11), None, 10)])                # nobody on leave
    h = hr.handover_report(a, lv, crew_plan=plan)
    during = h[h.kind == "plan_during_leave"]
    assert during[["leave_emp_key", "prj_key", "source"]].values.tolist() == [["EMP-1", "P5", "crew_plan"], ["EMP-1", "P6", "crew_plan"], ["EMP-1", "P7", "crew_plan"], ["EMP-2", "P2", "crew_plan"]]
    assert during.start.tolist() == [pd.Timestamp(2027, 1, 11), pd.Timestamp(2026, 6, 15), pd.Timestamp(2027, 2, 28), pd.Timestamp(2030, 1, 1)] and during.percent.tolist() == [25, 25, 25, 10]
    assert h[h.kind == "planned_return"].prj_key.tolist() == ["P8"], "the return is unchanged: a row after the leave end"
    assert list(h.columns)[-1] == "source"
    last = h[h.leave_emp_key == "EMP-1"].kind.tolist()
    assert last.index("plan_during_leave") > last.index("planned_return"), "the new kind comes last per leave: existing kinds keep their order"
    plain = hr.handover_report(a, lv)
    assert "plan_during_leave" not in set(plain.kind) and "source" not in plain.columns, "without a crew plan the output is as before"
    assert hr.handover_report(a, lv, crew_plan=plan.iloc[:0]).kind.tolist() == plain.kind.tolist()


def test_an_empty_estimate_version_frame_gives_no_plan_hours_instead_of_an_error():
    ev = pd.DataFrame({"prj_key": ["P1"], "estimate_version": [1], "type": ["budget"]})
    el = pd.DataFrame({"prj_key": ["P1", "P1"], "estimate_version": [1, 1], "cst_key": ["CST-110", "CST-120"], "quantity": [5.0, 3.0]})
    te = pd.DataFrame({"prj_key": ["P1", "P2"], "hours": [4.0, 2.0]})
    r = hr.planned_vs_actual_hours(ev.iloc[:0], el, te)
    assert r.prj_key.tolist() == ["P1", "P2"] and r.plan_hours.tolist() == [0.0, 0.0] and r.actual_hours.tolist() == [4.0, 2.0] and r.ratio.isna().all(), "a project subset or a release not loaded yet: booked hours without plan"
    r = hr.planned_vs_actual_hours(ev.iloc[:0], el.iloc[:0], te.iloc[:0])
    assert r.empty and list(r.columns) == ["prj_key", "plan_hours", "actual_hours", "ratio"]
    nothing = hr.planned_vs_actual_hours(pd.DataFrame({"prj_key": [], "estimate_version": [], "type": []}), el, te)
    assert nothing.plan_hours.tolist() == [0.0, 0.0], "an empty frame of another dtype is no reason to refuse"
    with pytest.raises(FrameError, match="no estimate version of type 'tender'"):
        hr.planned_vs_actual_hours(ev, el, te, version_type="tender")


def test_staffing_defaults_are_policy_facts_and_carry_their_status():
    a = _al([("EMP-1", "P1", D(2026, 1, 1), D(2026, 1, 31), 60), ("EMP-1", "P2", D(2026, 1, 20), D(2026, 2, 10), 50)])
    out = hr.allocation_load(a)
    from halvaro.core import fact      # lane F3 (issue #543), approved edit: the status of the fact, whichever it is
    assert out.attrs["policy_status"] == {"policy.staffing.max_allocation_percent": fact("policy.staffing.max_allocation_percent").status} and out.over_limit.any()
    assert not hr.allocation_load(a, limit=120).over_limit.any() and "policy_status" not in hr.allocation_load(a, limit=120).attrs
    lv = pd.DataFrame({"emp_key": ["EMP-1"], "leave_type": ["parental"], "start": [D(2026, 3, 1)], "end": [D(2026, 3, 31)]})
    h = hr.handover_report(a, lv)
    assert h.attrs["policy_status"] == {"policy.staffing.unavailable_leave_types": fact("policy.staffing.unavailable_leave_types").status}      # lane F3 (issue #543), approved edit: the status of the fact, whichever it is
    assert "policy_status" not in hr.handover_report(a, lv, leave_types=["parental"]).attrs and hr.handover_report(a, lv, leave_types="sick").empty
