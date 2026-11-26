"""project_requirements, project_crew, coverage_gap, cover_candidates: boundaries on synthetic frames (the baseline tests are in the closed repository)."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, registry

D = dt.date
START = D(2027, 1, 18)


def _req(rows):
    return pd.DataFrame(rows, columns=["scope_type", "scope_key", "qual_key", "min_headcount", "requirement_level"])


def _proj(rows):
    return pd.DataFrame(rows, columns=["prj_key", "type", "contract_key"])


def _cert(rows):
    return pd.DataFrame([(e, q, i, x, "valid", "course", None, 1) for e, q, i, x in rows], columns=["emp_key", "qual_key", "issued", "expires", "status", "origin", "renews_issued", "event_no"])


def _booked(rows):
    return pd.DataFrame(rows, columns=["emp_key", "qual_key", "course_date"])


def _leave(rows):
    return pd.DataFrame(rows, columns=["emp_key", "leave_type", "start", "end"])


# project_requirements

def test_requirements_per_scope_never_merged_and_unknown_scope_refused():
    req = _req([("project", "PRJ-000001", "QUAL-001", 2, "required"), ("project", "PRJ-000002", "QUAL-001", 9, "required"), ("contract", "CON-000001", "QUAL-002", 1, "required"),
                ("project_type", "substation", "QUAL-001", 3, "required"), ("project_type", "dh_network", "QUAL-009", 3, "required"), ("role", "ROLE-001", "QUAL-003", None, "mandatory")])
    proj = _proj([("PRJ-000001", "substation", "CON-000001"), ("PRJ-000002", "dh_network", None)])
    r = hr.project_requirements(req, proj, "PRJ-000001", role_keys=["ROLE-001", "ROLE-777"])
    assert r.via.tolist() == ["project", "contract", "project_type", "role"] and r.qual_key.tolist() == ["QUAL-001", "QUAL-002", "QUAL-001", "QUAL-003"], "QUAL-001 appears twice: once per scope"
    assert r.min_headcount.tolist()[:3] == [2, 1, 3] and pd.isna(r.min_headcount.iloc[3])
    assert hr.project_requirements(req, proj, "PRJ-000002").via.tolist() == ["project", "project_type"], "no contract key: no contract scope"
    with pytest.raises(FrameError, match="unknown value.*galaxy"):
        hr.project_requirements(req.assign(scope_type="galaxy"), proj, "PRJ-000001")
    with pytest.raises(FrameError, match="not in the projects.project frame exactly once"):
        hr.project_requirements(req, proj, "PRJ-999999")


# project_crew

def test_crew_from_allocation_else_from_the_plan_and_boundaries_inclusive():
    alloc = pd.DataFrame([("EMP-000001", "PRJ-000001", D(2027, 1, 18), D(2027, 2, 28), 50), ("EMP-000001", "PRJ-000001", D(2027, 1, 1), D(2027, 2, 1), 80), ("EMP-000002", "PRJ-000001", D(2027, 1, 19), D(2027, 3, 1), 100)],
                         columns=["emp_key", "prj_key", "start", "end", "percent"])
    plan = pd.DataFrame([("PRJ-000001", "EMP-000009", D(2027, 1, 1), D(2027, 12, 31), 100), ("PRJ-000002", "EMP-000008", D(2027, 1, 18), D(2027, 1, 18), 60), ("PRJ-000002", "EMP-000007", D(2027, 1, 19), D(2027, 2, 1), 60)],
                        columns=["prj_key", "emp_key", "planned_start", "planned_end", "percent"])
    c = hr.project_crew(alloc, plan, "PRJ-000001", START)
    assert c.emp_key.tolist() == ["EMP-000001"] and c.percent.tolist() == [80] and c.source.tolist() == ["allocation"], "starts on the date counts; the larger percent; the plan is not mixed in"
    assert hr.project_crew(alloc, plan, "PRJ-000001", D(2027, 3, 1)).emp_key.tolist() == ["EMP-000002"], "ends on the date counts"
    p = hr.project_crew(alloc, plan, "PRJ-000002", START)
    assert p.emp_key.tolist() == ["EMP-000008"] and p.source.tolist() == ["crew_plan"], "planned projects use the crew plan"
    assert hr.project_crew(alloc, plan, "PRJ-000002", D(2026, 1, 1)).empty


# coverage_gap

def test_gap_on_record_including_booked_leave_and_the_closing_date():
    req = _req([("project", "PRJ-000001", "QUAL-001", 4, "required"), ("role", "ROLE-001", "QUAL-001", None, "mandatory")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 6, 30)),      # valid, expires in the project: first expiry
                  ("EMP-000002", "QUAL-001", D(2020, 1, 1), D(2027, 1, 17)),       # expired the day before the start
                  ("EMP-000003", "QUAL-001", D(2027, 1, 18), None)])               # issued on the start day: valid, open
    booked = _booked([("EMP-000002", "QUAL-001", D(2027, 2, 10)), ("EMP-000004", "QUAL-001", D(2027, 1, 18))])      # one course on the start day, one later
    leave = _leave([("EMP-000003", "extended_leave", D(2026, 12, 1), D(2027, 2, 28)), ("EMP-000001", "holiday", D(2027, 1, 18), D(2027, 1, 18))])
    g = hr.coverage_gap(req, crew, cert, booked, leave, START).iloc[0]
    assert (g.required, g.crew_with_cert, g.available, g.available_incl_booked) == (4, 2, 0, 1), "EMP-000001 on holiday that day, EMP-000003 on extended leave, EMP-000004 booked on the day"
    assert (g.gap_on_record, g.gap_incl_booked) == (4, 3) and g.on_leave == ["EMP-000001", "EMP-000003"] and g.without_cert == ["EMP-000002", "EMP-000004"]
    assert g.booked_for_crew == ["EMP-000002", "EMP-000004"] and g.first_expiry == pd.Timestamp(2027, 6, 30) and g.first_expiry_emp == "EMP-000001"
    assert g.gap_closes_on == pd.Timestamp(2027, 3, 1), "needs all 4: EMP-000001 (back 19 Jan), EMP-000004 (booked), EMP-000002 (booked 10 Feb) and EMP-000003 back on 1 March"
    only_ext = hr.coverage_gap(req, crew, cert, booked, leave, START, leave_types=["extended_leave"]).iloc[0]
    assert only_ext.available == 1 and only_ext.on_leave == ["EMP-000003"], "a holiday does not count when only extended leave makes people unavailable"
    assert len(hr.coverage_gap(req, crew, cert, booked, leave, START)) == 1, "the role row has no head count and is not a gap row"


def test_gap_never_closes_is_null_and_a_booking_is_not_a_cover_before_its_date():
    req = _req([("project", "PRJ-000001", "QUAL-001", 2, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), None)])
    g = hr.coverage_gap(req, crew, cert, _booked([]), _leave([]), START).iloc[0]
    assert pd.isna(g.gap_closes_on) and g.gap_on_record == 1 and g.gap_incl_booked == 1
    later = hr.coverage_gap(req, crew, cert, _booked([("EMP-000002", "QUAL-001", D(2027, 1, 19))]), _leave([]), START).iloc[0]
    assert later.available_incl_booked == 1 and later.gap_closes_on == pd.Timestamp(2027, 1, 19), "booked a day after the start: not a cover on the start day"
    with pytest.raises(FrameError, match="lacks column"):
        hr.coverage_gap(req.drop(columns="qual_key"), crew, cert, _booked([]), _leave([]), START)


# cover_candidates

def test_candidate_reasons_and_order():
    org = pd.DataFrame({"emp_key": [f"EMP-00000{i}" for i in range(1, 9)], "active": [True] * 7 + [False], "country": ["DE", "DE", "DK", "DE", "DE", "DE", "DE", "DE"],
                        "role_name": ["r"] * 8, "legal_entity_key": ["LE-02"] * 8})
    sk = pd.DataFrame({"emp_key": org.emp_key, "skl_key": "SKL-001", "level": [4, 3, 3, 2, 5, 3, 1, 5]})
    qual = pd.DataFrame({"qual_key": ["QUAL-001", "QUAL-002"], "prerequisite_qual_key": ["QUAL-002", None], "country_scope": ["DE", "DE"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2030, 1, 1)), ("EMP-000002", "QUAL-002", D(2020, 1, 1), D(2030, 1, 1)), ("EMP-000004", "QUAL-002", D(2020, 1, 1), D(2030, 1, 1)),
                  ("EMP-000005", "QUAL-002", D(2020, 1, 1), D(2030, 1, 1)), ("EMP-000006", "QUAL-002", D(2020, 1, 1), D(2030, 1, 1))])
    ev = pd.DataFrame({"event_no": [1, 2, 3], "qual_key": "QUAL-001", "date": [D(2027, 1, 5), D(2027, 2, 1), D(2027, 3, 20)], "capacity": [10, 10, 10], "seats_taken": [10, 3, 3], "country": ["DE", "DE", "DE"]})
    cp = pd.DataFrame({"prj_key": ["PRJ-000009"], "emp_key": ["EMP-000005"], "percent": [100]})
    lv = _leave([("EMP-000006", "parental", D(2027, 3, 1), None), ("EMP-000002", "holiday", D(2027, 1, 18), D(2027, 2, 1))])
    r = hr.cover_candidates(sk, org, cert, qual, ev, cp, lv, qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=["EMP-000008"], country="DE", start=START, now=D(2026, 11, 30)).set_index("emp_key")
    assert "EMP-000001" not in r.index, "already valid on the start day"
    assert "EMP-000007" not in r.index and "EMP-000008" not in r.index, "level 1 is not listed; EMP-000008 is crew (and inactive)"
    assert r.loc["EMP-000002", "reasons"] == [] and r.loc["EMP-000002", "plausible"] and r.loc["EMP-000002", "next_seat_event"] == 2, "event 1 is full, event 2 is the first seat; a holiday is not long leave"
    assert r.loc["EMP-000003", "reasons"] == ["country_scope_mismatch", "prerequisite_missing", "no_seat_before_start_plus_60d"], "DK person, DE scope, no prerequisite, no DK course"
    assert r.loc["EMP-000004", "reasons"] == ["skill_level_below_3"] and r.loc["EMP-000005", "reasons"] == ["planned_on_other_project"]
    assert r.loc["EMP-000006", "reasons"] == ["long_leave"], "parental leave starting 42 days after the start is inside 90 days"
    assert r.plausible.tolist() == sorted(r.plausible.tolist(), reverse=True) and r.index[0] == "EMP-000002", "plausible first"
    full = hr.cover_candidates(sk, org, cert, qual, ev, cp, lv, qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=["EMP-000008"], country="DE", start=START, now=D(2026, 11, 30))
    assert set(full.attrs["policy_status"]) == {"policy.certificates.candidate_list_level", "policy.certificates.candidate_plausible_level", "policy.certificates.candidate_leave_days",
                                                "policy.certificates.candidate_seat_days", "policy.staffing.unavailable_leave_types"} and full.attrs["policy_status"] == {k: __import__("halvaro.core", fromlist=["fact"]).fact(k).status for k in full.attrs["policy_status"]}, "defaults come from the facts"      # lane F3 (issue #543), approved edit: the status of each fact, whichever it is
    given = hr.cover_candidates(sk, org, cert, qual, ev, cp, lv, qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=["EMP-000008"], country="DE", start=START, now=D(2026, 11, 30),
                                list_level=2, plausible_level=3, leave_days=90, seat_days=60, leave_types=("extended_leave", "parental"))
    assert "policy_status" not in given.attrs and given.drop(columns=[]).equals(full), "the same numbers given by the caller give the same frame"
    assert hr.cover_candidates(sk, org, cert, qual, ev, cp, lv, qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=[], country="DE", start=START, now=D(2026, 11, 30),
                               seat_days=10).set_index("emp_key").loc["EMP-000002", "reasons"] == ["no_seat_before_start_plus_10d"], "the seat window is a parameter"
    with pytest.raises(FrameError, match="QUAL-777"):
        hr.cover_candidates(sk, org, cert, qual, ev, cp, lv, qual_key="QUAL-777", skl_key="SKL-001", prj_key="PRJ-000001", crew=[], country="DE", start=START, now=D(2026, 11, 30))


def test_registered_with_sources():
    reg = registry.registered()
    for n in ("project_requirements", "project_crew", "coverage_gap", "cover_candidates", "education_level", "skill_latest"):
        m = next(v for k, v in reg.items() if k.endswith("." + n) and k.startswith("halvaro.hr."))
        assert m.sources
    assert registry.check() == []


# review fixes: boundaries that a mutation must break

def test_certificate_boundaries_on_the_date_and_first_expiry_is_inclusive():
    req = _req([("project", "PRJ-000001", "QUAL-001", 1, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001"]})
    on_day = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), START)])                       # expires on the start day: still valid
    g = hr.coverage_gap(req, crew, on_day, _booked([]), _leave([]), START).iloc[0]
    assert g.crew_with_cert == 1 and g.first_expiry == pd.Timestamp(START) and g.first_expiry_emp == "EMP-000001"
    day_after = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 1, 17))])
    assert hr.coverage_gap(req, crew, day_after, _booked([]), _leave([]), START).iloc[0].crew_with_cert == 0
    starts_on = _cert([("EMP-000001", "QUAL-001", START, None)])
    g2 = hr.coverage_gap(req, crew, starts_on, _booked([]), _leave([]), START).iloc[0]
    assert g2.crew_with_cert == 1 and pd.isna(g2.first_expiry), "issued on the start day is valid; an open certificate never expires"


def test_open_ended_and_chained_leave_decide_availability_and_the_closing_date():
    req = _req([("project", "PRJ-000001", "QUAL-001", 1, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), None)])
    open_end = hr.coverage_gap(req, crew, cert, _booked([]), _leave([("EMP-000001", "extended_leave", D(2027, 1, 1), None)]), START).iloc[0]
    assert open_end.available == 0 and pd.isna(open_end.gap_closes_on), "an open ended leave never ends"
    chained = _leave([("EMP-000001", "holiday", D(2027, 1, 10), D(2027, 1, 25)), ("EMP-000001", "holiday", D(2027, 1, 26), D(2027, 3, 1))])
    assert hr.coverage_gap(req, crew, cert, _booked([]), chained, START).iloc[0].gap_closes_on == pd.Timestamp(2027, 3, 2), "back after the last of two adjacent leaves"
    later = _leave([("EMP-000001", "holiday", D(2027, 1, 10), D(2027, 1, 25)), ("EMP-000001", "holiday", D(2027, 1, 20), D(2027, 3, 1))])
    assert hr.coverage_gap(req, crew, cert, _booked([]), later, START).iloc[0].gap_closes_on == pd.Timestamp(2027, 3, 2), "overlapping leave"
    ends_before = _leave([("EMP-000001", "holiday", D(2027, 1, 1), D(2027, 1, 17))])
    assert hr.coverage_gap(req, crew, cert, _booked([]), ends_before, START).iloc[0].available == 1, "leave that ended the day before does not count"


def test_crew_open_allocation_start_day_and_no_mixing_of_plan_and_allocation():
    plan = pd.DataFrame([("PRJ-000001", "EMP-000009", D(2027, 1, 1), D(2027, 12, 31), 100)], columns=["prj_key", "emp_key", "planned_start", "planned_end", "percent"])
    alloc = pd.DataFrame([("EMP-000001", "PRJ-000001", START, None, 100), ("EMP-000002", "PRJ-000001", D(2027, 1, 19), None, 100)], columns=["emp_key", "prj_key", "start", "end", "percent"])
    assert hr.project_crew(alloc, plan, "PRJ-000001", START).emp_key.tolist() == ["EMP-000001"], "open ended allocation counts, starts on the date counts, the plan is not mixed in"
    assert hr.project_crew(alloc, plan, "PRJ-000001", D(2027, 1, 17)).empty, "allocations exist but none covers the date: empty, not the plan"
    with pytest.raises(FrameError, match="null emp_key"):
        hr.coverage_gap(_req([("project", "PRJ-000001", "QUAL-001", 1, "required")]), pd.DataFrame({"emp_key": [None]}), _cert([]), _booked([]), _leave([]), START)
    with pytest.raises(FrameError, match="whole number"):
        hr.coverage_gap(_req([("project", "PRJ-000001", "QUAL-001", 2.7, "required")]), pd.DataFrame({"emp_key": ["E"]}), _cert([]), _booked([]), _leave([]), START)


def _cand_inputs(**over):
    org = pd.DataFrame({"emp_key": ["EMP-000001"], "active": [True], "country": ["DE"], "role_name": ["r"], "legal_entity_key": ["LE-02"]})
    sk = pd.DataFrame({"emp_key": ["EMP-000001"], "skl_key": "SKL-001", "level": [3]})
    qual = pd.DataFrame({"qual_key": ["QUAL-001", "QUAL-002"], "prerequisite_qual_key": [None, None], "country_scope": ["DE", "DE"]})
    ev = pd.DataFrame({"event_no": [1], "qual_key": "QUAL-001", "date": [D(2027, 1, 30)], "capacity": [10], "seats_taken": [3], "country": ["DE"]})
    base = dict(skill_latest=sk, org=org, cert=_cert([]), qualification=qual, event=ev, crew_plan=pd.DataFrame(columns=["prj_key", "emp_key", "percent"]), leave_record=_leave([]))
    base.update(over)
    return base


def _reasons(**over):
    kw = dict(qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=[], country="DE", start=START, now=D(2026, 11, 30))
    kw.update({k: over.pop(k) for k in list(over) if k in kw})
    r = hr.cover_candidates(**_cand_inputs(**over), **kw)
    return r.iloc[0].reasons if len(r) else None


def test_seat_window_long_leave_window_other_project_and_prerequisite_edges():
    ev = lambda d: pd.DataFrame({"event_no": [1], "qual_key": "QUAL-001", "date": [d], "capacity": [10], "seats_taken": [3], "country": ["DE"]})
    assert _reasons(event=ev(D(2027, 3, 19))) == [] and _reasons(event=ev(D(2027, 3, 20))) == ["no_seat_before_start_plus_60d"], "start plus 60 days is the last seat day"
    assert _reasons(event=ev(D(2026, 12, 1))) == [] and _reasons(event=ev(D(2026, 11, 30))) == ["no_seat_before_start_plus_60d"], "a course must be after now"
    full = ev(D(2027, 1, 30)).assign(seats_taken=10)
    assert _reasons(event=full) == ["no_seat_before_start_plus_60d"]
    parental = lambda s, e: _leave([("EMP-000001", "parental", s, e)])
    assert _reasons(leave_record=parental(D(2027, 4, 18), None)) == ["long_leave"], "starts on start plus 90 days"
    assert _reasons(leave_record=parental(D(2027, 4, 19), None)) == []
    assert _reasons(leave_record=parental(D(2026, 12, 1), START)) == ["long_leave"], "ends on the start day"
    assert _reasons(leave_record=parental(D(2026, 12, 1), D(2027, 1, 17))) == []
    own = pd.DataFrame({"prj_key": ["PRJ-000001"], "emp_key": ["EMP-000001"], "percent": [100]})
    assert _reasons(crew_plan=own) == [], "planned on this very project is not planned elsewhere"
    assert _reasons(crew_plan=own.assign(prj_key="PRJ-000002")) == ["planned_on_other_project"]
    assert _reasons(crew_plan=own.assign(prj_key="PRJ-000002", percent=99)) == []
    qual = pd.DataFrame({"qual_key": ["QUAL-001", "QUAL-002"], "prerequisite_qual_key": ["QUAL-002", None], "country_scope": ["DE", "DE"]})
    pre = _cert([("EMP-000001", "QUAL-002", D(2020, 1, 1), D(2027, 1, 10))])         # valid today, expired before the start
    assert _reasons(qualification=qual, cert=pre) == ["prerequisite_missing"], "the prerequisite is checked on the start day, not today"
    assert _reasons(country="DK") == ["other_country"], "a DE person on a DK project, DE scoped qualification"
    assert _reasons(qualification=_cand_inputs()["qualification"].assign(country_scope="DK"), country="DE") == ["country_scope_mismatch"], "scoped to DK, the person is in DE"


def test_candidates_accept_a_crew_frame_and_refuse_duplicates_and_null_levels():
    r = hr.cover_candidates(**_cand_inputs(), qual_key="QUAL-001", skl_key="SKL-001", prj_key="PRJ-000001", crew=pd.DataFrame({"emp_key": ["EMP-000001"]}), country="DE", start=START, now=D(2026, 11, 30))
    assert r.empty, "a person in the crew frame is not a candidate"
    with pytest.raises(FrameError, match="more than one row for a person and skill"):
        _reasons(skill_latest=pd.concat([_cand_inputs()["skill_latest"]] * 2))
    with pytest.raises(FrameError, match="null level"):
        _reasons(skill_latest=_cand_inputs()["skill_latest"].assign(level=[None]))
    with pytest.raises(FrameError, match="more than one row for a person"):
        _reasons(org=pd.concat([_cand_inputs()["org"]] * 2))


# second review: renewed-aware expiry, reusable intervals, open plans, boundaries

def test_first_expiry_keeps_the_generator_rule_and_the_renewed_aware_column_follows_the_latest_valid_certificate():
    req = _req([("project", "PRJ-000001", "QUAL-001", 1, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 2, 11)),             # renewed before it ran out: still overlaps the date
                  ("EMP-000001", "QUAL-001", D(2027, 1, 10), D(2029, 1, 9)),             # the renewal, issued before the start
                  ("EMP-000002", "QUAL-001", D(2020, 1, 1), D(2027, 6, 30)),
                  ("EMP-000003", "QUAL-001", D(2020, 1, 1), D(2027, 3, 1)),
                  ("EMP-000003", "QUAL-001", D(2027, 1, 18), None)])                      # an open renewal: this person never expires
    g = hr.coverage_gap(req, crew, cert, _booked([]), _leave([]), START).iloc[0]
    assert (g.first_expiry, g.first_expiry_emp) == (pd.Timestamp(2027, 2, 11), "EMP-000001"), "generator parity: the earliest expiry among overlapping certificates, a renewed one included"
    assert (g.first_expiry_renewed_aware, g.first_expiry_renewed_aware_emp) == (pd.Timestamp(2027, 6, 30), "EMP-000002"), "EMP-000001 is valid to 2029-01-09, EMP-000003 never expires"
    valid = hr.valid_on(cert, START).set_index("emp_key").expires
    assert valid["EMP-000001"] == pd.Timestamp(2029, 1, 9), "the certs.valid_on rule gives the later date"
    only_open = hr.coverage_gap(req, crew.iloc[[2]], cert, _booked([]), _leave([]), START).iloc[0]
    assert pd.isna(only_open.first_expiry_renewed_aware) and only_open.first_expiry_renewed_aware_emp is None and only_open.first_expiry == pd.Timestamp(2027, 3, 1)
    not_yet = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 2, 11)), ("EMP-000001", "QUAL-001", D(2027, 1, 19), D(2029, 1, 9))])      # the renewal is issued after the date
    n = hr.coverage_gap(req, crew.iloc[[0]], not_yet, _booked([]), _leave([]), START).iloc[0]
    assert n.first_expiry_renewed_aware == pd.Timestamp(2027, 2, 11), "a certificate issued after the date is not valid on it"


def test_intervals_helper_gives_the_same_frame_and_is_registered_and_validates_the_certificates():
    req = _req([("project", "PRJ-000001", "QUAL-001", 2, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 6, 30)), ("EMP-000002", "QUAL-001", D(2027, 1, 18), None)])
    iv = hr.cert_intervals(cert)
    assert set(iv) == {("EMP-000001", "QUAL-001"), ("EMP-000002", "QUAL-001")}
    pd.testing.assert_frame_equal(hr.coverage_gap(req, crew, cert, _booked([]), _leave([]), START), hr.coverage_gap(req, crew, cert, _booked([]), _leave([]), START, intervals=iv))
    assert hr.coverage_gap(req, crew, cert.iloc[:0], _booked([]), _leave([]), START, intervals=iv).iloc[0].crew_with_cert == 2, "the intervals are used, not the cert frame"
    with pytest.raises(FrameError, match="expire before"):
        hr.cert_intervals(_cert([("EMP-000001", "QUAL-001", D(2020, 1, 2), D(2020, 1, 1))]))
    m = registry.registered()["halvaro.hr.coverage.cert_intervals"]
    assert m.oracle.startswith("py:") and m.sources and registry.check() == []


def test_open_crew_plan_and_null_allocation_start():
    plan = pd.DataFrame([("PRJ-000002", "EMP-000008", D(2027, 1, 1), None, 60), ("PRJ-000002", "EMP-000007", D(2027, 1, 1), D(2027, 1, 17), 60)],
                        columns=["prj_key", "emp_key", "planned_start", "planned_end", "percent"])
    alloc = pd.DataFrame([("EMP-000001", "PRJ-000001", START, None, 100)], columns=["emp_key", "prj_key", "start", "end", "percent"])
    c = hr.project_crew(alloc, plan, "PRJ-000002", D(2030, 1, 1))
    assert c.emp_key.tolist() == ["EMP-000008"] and c.source.tolist() == ["crew_plan"], "a plan row with no planned_end is open, as an allocation with no end"
    assert hr.project_crew(alloc, plan, "PRJ-000002", D(2026, 12, 31)).empty, "an open plan row still starts on its planned_start"
    bad = pd.DataFrame([("EMP-000001", "PRJ-000001", None, D(2027, 2, 1), 100), ("EMP-000002", "PRJ-000001", START, None, 100)], columns=["emp_key", "prj_key", "start", "end", "percent"])
    with pytest.raises(FrameError, match="null start.*EMP-000001"):
        hr.project_crew(bad, plan, "PRJ-000001", START)
    assert hr.project_crew(bad, plan, "PRJ-000002", START).emp_key.tolist() == ["EMP-000008"], "a null start on another project is not this project's problem"


def test_leave_ending_on_the_date_is_unavailable_that_day_and_available_the_next():
    req = _req([("project", "PRJ-000001", "QUAL-001", 1, "required")])
    crew = pd.DataFrame({"emp_key": ["EMP-000001"]})
    cert = _cert([("EMP-000001", "QUAL-001", D(2020, 1, 1), None)])
    lv = _leave([("EMP-000001", "extended_leave", D(2026, 12, 1), START)])
    on = hr.coverage_gap(req, crew, cert, _booked([]), lv, START).iloc[0]
    assert on.available == 0 and on.on_leave == ["EMP-000001"] and on.gap_closes_on == pd.Timestamp(2027, 1, 19)
    nxt = hr.coverage_gap(req, crew, cert, _booked([]), lv, D(2027, 1, 19)).iloc[0]
    assert nxt.available == 1 and nxt.on_leave == [] and nxt.gap_closes_on == pd.Timestamp(2027, 1, 19)
    starts = hr.coverage_gap(req, crew, cert, _booked([]), _leave([("EMP-000001", "holiday", START, START)]), START).iloc[0]
    assert starts.available == 0, "a one day leave on the date itself"


def test_requirements_are_sorted_by_scope_then_qual_key_then_scope_key():
    req = _req([("role", "ROLE-002", "QUAL-001", None, "mandatory"), ("role", "ROLE-001", "QUAL-001", None, "mandatory"), ("role", "ROLE-001", "QUAL-000", None, "mandatory"),
                ("project_type", "substation", "QUAL-009", 1, "required"), ("project_type", "substation", "QUAL-002", 1, "required"),
                ("contract", "CON-000001", "QUAL-005", 1, "required"), ("project", "PRJ-000001", "QUAL-007", 1, "required"), ("project", "PRJ-000001", "QUAL-003", 1, "required")])
    r = hr.project_requirements(req, _proj([("PRJ-000001", "substation", "CON-000001")]), "PRJ-000001", role_keys=["ROLE-002", "ROLE-001"])
    assert list(zip(r.via, r.qual_key, r.scope_key)) == [("project", "QUAL-003", "PRJ-000001"), ("project", "QUAL-007", "PRJ-000001"), ("contract", "QUAL-005", "CON-000001"),
                                                          ("project_type", "QUAL-002", "substation"), ("project_type", "QUAL-009", "substation"),
                                                          ("role", "QUAL-000", "ROLE-001"), ("role", "QUAL-001", "ROLE-001"), ("role", "QUAL-001", "ROLE-002")]
    assert r.index.tolist() == list(range(8))
