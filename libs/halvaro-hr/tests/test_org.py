"""Organisation layer: synthetic frames for the contract, the baseline release for the gate numbers."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import AmbiguousKey, FrameError, PeriodError, ReleaseMismatch

D = dt.date


def _frames():
    emp = pd.DataFrame({
        "emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"],
        "gender": ["F", "M", "F", "M"],
        "hire_date": [D(2020, 1, 1), D(2023, 3, 1), D(2018, 5, 1), D(2027, 1, 1)],
        "leave_date": [None, None, D(2024, 6, 30), None],
        "legal_entity_key": ["LE-01", "LE-02", "LE-01", "LE-01"]})
    term = pd.DataFrame({
        "emp_key": ["EMP-000001", "EMP-000001", "EMP-000002", "EMP-000003"],
        "valid_from": [D(2023, 1, 1), D(2024, 1, 1), D(2023, 3, 1), D(2023, 1, 1)],
        "valid_to": [D(2023, 12, 31), None, None, D(2024, 6, 30)],
        "team_key": ["TEAM-001", "TEAM-002", "TEAM-002", "TEAM-001"], "role_key": ["ROLE-001", "ROLE-002", "ROLE-002", "ROLE-001"],
        "grade_key": ["GRA-01", "GRA-02", "GRA-02", "GRA-01"], "fte": [1.0, 1.0, 0.5, 1.0], "base_salary": [100, 120, 90, 80]})
    team = pd.DataFrame({"team_key": ["TEAM-001", "TEAM-002"], "dep_key": ["DEP-01", "DEP-02"], "cost_centre_key": ["CC-0001", "CC-0002"],
                         "legal_entity_key": ["LE-01", "LE-02"], "site_key": ["SITE-01", "SITE-05"]})
    role = pd.DataFrame({"role_key": ["ROLE-001", "ROLE-002"], "name": ["Welder", "Engineer"]})
    grade = pd.DataFrame({"gra_key": ["GRA-01", "GRA-02"], "level": [1, 2]})
    dep = pd.DataFrame({"dep_key": ["DEP-01", "DEP-02"], "dep_code": ["PDL", "ENG"]})
    site = pd.DataFrame({"site_key": ["SITE-01", "SITE-05"], "country": ["DK", "DE"]})
    return emp, term, team, role, grade, dep, site


def test_terms_on_is_inclusive_one_per_person_and_has_no_pay_column():
    _, term, *_ = _frames()
    a = hr.terms_on(term, D(2023, 12, 31))
    assert sorted(a.emp_key) == ["EMP-000001", "EMP-000002", "EMP-000003"] and a.set_index("emp_key").loc["EMP-000001", "team_key"] == "TEAM-001"
    b = hr.terms_on(term, D(2024, 1, 1))
    assert b.set_index("emp_key").loc["EMP-000001", "team_key"] == "TEAM-002" and "base_salary" not in b.columns
    assert hr.terms_on(term, D(2024, 6, 30)).emp_key.tolist().count("EMP-000003") == 1 and "EMP-000003" not in hr.terms_on(term, D(2024, 7, 1)).emp_key.tolist()
    assert hr.terms_on(term, D(2022, 12, 31)).empty


def test_terms_on_refuses_overlaps_and_missing_columns():
    _, term, *_ = _frames()
    bad = pd.concat([term, term.iloc[[1]].assign(valid_from=D(2024, 3, 1))])
    with pytest.raises(AmbiguousKey):
        hr.terms_on(bad, D(2024, 6, 1))
    with pytest.raises(FrameError, match="hr.employment_term frame lacks column.*valid_to"):
        hr.terms_on(term.drop(columns="valid_to"), D(2024, 6, 1))


def test_org_on_columns_region_and_active_flag():
    emp, term, team, role, grade, dep, site = _frames()
    out = hr.org_on(emp, term, team, role, grade, dep, site, D(2024, 6, 30)).set_index("emp_key")
    assert "base_salary" not in out.columns and len(out) == 3
    r = out.loc["EMP-000002"]
    assert (r.role_name, r.level, r.dep_code, r.country, r.region, r.fte) == ("Engineer", 2, "ENG", "DE", "DE-HH", 0.5)
    assert bool(r.active) and bool(out.loc["EMP-000003", "active"]), "leave_date is the last day employed, so the person is still active on it"
    after = hr.org_on(emp, term, team, role, grade, dep, site, D(2024, 6, 30)).set_index("emp_key")
    assert after.loc["EMP-000003", "active"]
    assert out.loc["EMP-000001", "region"] == "DE-HH" and pd.Timestamp(out.loc["EMP-000001", "as_of"]) == pd.Timestamp(D(2024, 6, 30))


def test_headcount_on_by_department_team_entity():
    emp, term, team, *_ = _frames()
    dep = hr.headcount_on(emp, term, team, D(2024, 6, 29))
    assert dep.set_index("dep_key").loc["DEP-01", "headcount"] == 1 and dep.set_index("dep_key").loc["DEP-02", "fte"] == 1.5
    assert hr.headcount_on(emp, term, team, D(2024, 6, 30), "team").headcount.sum() == 3, "EMP-000003 has leave_date 2024-06-30, the last day employed: still counted"
    assert hr.headcount_on(emp, term, team, D(2024, 7, 1), "team").headcount.sum() == 2, "and gone the day after"
    ent = hr.headcount_on(emp, term, team, D(2024, 6, 29), "entity").set_index("legal_entity_key")
    assert ent.headcount.to_dict() == {"LE-01": 2, "LE-02": 1}
    with pytest.raises(FrameError, match="level"):
        hr.headcount_on(emp, term, team, D(2024, 6, 29), "site")


def test_headcount_on_refuses_an_active_person_without_a_term():
    emp, term, team, *_ = _frames()
    ghost = pd.concat([emp, emp.iloc[[0]].assign(emp_key="EMP-000005", hire_date=D(2023, 1, 1))])
    with pytest.raises(FrameError, match="no employment term"):
        hr.headcount_on(ghost, term, team, D(2024, 6, 29))     # EMP-000005 is active and has no term


def _release(name="baseline", now="2026-11-30"):
    return pd.DataFrame([{"release": name, "now": now, "generated_at": pd.Timestamp(now), "base_seed": "halvaro-2026", "increment": 0}])


def test_data_now_returns_now_and_refuses_later_dates():
    frames = {"hr": _release(), "competence": _release()}
    assert hr.data_now(frames) == D(2026, 11, 30) and hr.data_now(frames, D(2026, 11, 30)) == D(2026, 11, 30)
    with pytest.raises(PeriodError, match="ledgers"):
        hr.data_now(frames, D(2026, 12, 1))
    with pytest.raises(ReleaseMismatch):
        hr.data_now({"hr": _release(), "competence": _release("i1")})


def test_org_on_and_headcount_refuse_dates_before_the_first_terms():
    emp, term, team, role, grade, dep, site = _frames()
    ghost = pd.concat([emp, emp.iloc[[0]].assign(emp_key="EMP-000005", hire_date=D(2020, 1, 1))])
    with pytest.raises(FrameError, match="no employment term"):
        hr.org_on(ghost, term, team, role, grade, dep, site, D(2022, 6, 1))
    with pytest.raises(FrameError, match="no employment term"):
        hr.headcount_on(ghost, term, team, D(2022, 6, 1))


def test_duplicate_reference_rows_raise_instead_of_multiplying_people():
    emp, term, team, role, grade, dep, site = _frames()
    with pytest.raises(Exception, match="not a many-to-one|many-to-one"):
        hr.org_on(emp, term, team, pd.concat([role, role.iloc[[0]]]), grade, dep, site, D(2024, 6, 30))


def test_duplicate_employee_rows_raise_a_halvaro_error():
    emp, term, team, role, grade, dep, site = _frames()
    dup = pd.concat([emp, emp.iloc[[0]]])
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.org_on(dup, term, team, role, grade, dep, site, D(2024, 6, 30))
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.headcount_on(dup, term, team, D(2024, 6, 29))


def test_headcount_refuses_a_team_missing_in_the_team_frame():
    emp, term, team, *_ = _frames()
    with pytest.raises(FrameError, match="not in the hr.team frame"):
        hr.headcount_on(emp, term, team[team.team_key != "TEAM-002"], D(2024, 6, 29))


def test_org_on_full_shape_order_and_dates():
    emp, term, team, role, grade, dep, site = _frames()
    a = hr.org_on(emp, term, team, role, grade, dep, site, D(2024, 6, 30))
    b = hr.org_on(emp, term, team, role, grade, dep, site, D(2023, 6, 30))
    assert list(a.columns) == ["emp_key", "as_of", "active", "gender", "hire_date", "leave_date", "legal_entity_key", "team_key", "role_key", "role_name",
                               "grade_key", "level", "dep_key", "dep_code", "site_key", "country", "region", "fte", "valid_from", "valid_to"]
    assert a.emp_key.tolist() == sorted(a.emp_key) and set(a.as_of) == {pd.Timestamp(D(2024, 6, 30))} and set(b.as_of) == {pd.Timestamp(D(2023, 6, 30))}
    r = a.set_index("emp_key").loc["EMP-000001"]
    assert pd.Timestamp(r.valid_from) == pd.Timestamp(D(2024, 1, 1)) and pd.isna(r.valid_to)
    assert b.set_index("emp_key").loc["EMP-000001", "team_key"] == "TEAM-001", "the term of 2023, not of 2024"


def test_active_needs_the_hire_date_on_or_before_the_date():
    emp, term, team, role, grade, dep, site = _frames()
    emp = pd.concat([emp, emp.iloc[[1]].assign(emp_key="EMP-000006", hire_date=D(2024, 6, 30)), emp.iloc[[1]].assign(emp_key="EMP-000007", hire_date=D(2024, 7, 1))])
    term = pd.concat([term, term.iloc[[2]].assign(emp_key="EMP-000006", valid_from=D(2024, 1, 1)), term.iloc[[2]].assign(emp_key="EMP-000007", valid_from=D(2024, 1, 1))])
    out = hr.org_on(emp, term, team, role, grade, dep, site, D(2024, 6, 30)).set_index("emp_key")
    assert bool(out.loc["EMP-000006", "active"]) and not bool(out.loc["EMP-000007", "active"]), "hired on the date is active, hired the day after is not"
    assert hr.headcount_on(emp, term, team, D(2024, 6, 30), "team").headcount.sum() == 4


def test_org_on_refuses_a_term_without_an_employee_row():
    emp, term, team, role, grade, dep, site = _frames()
    with pytest.raises(FrameError, match="no row in hr.employee"):
        hr.org_on(emp[emp.emp_key != "EMP-000002"], term, team, role, grade, dep, site, D(2024, 6, 30))


def test_headcount_levels_sort_and_fte_per_group():
    emp, term, team, *_ = _frames()
    t = hr.headcount_on(emp, term, team, D(2024, 6, 29), "team")
    assert t.team_key.tolist() == ["TEAM-001", "TEAM-002"] and t.headcount.tolist() == [1, 2] and t.fte.tolist() == [1.0, 1.5]
    e = hr.headcount_on(emp, term, team, D(2024, 6, 29), "entity")
    assert e.legal_entity_key.tolist() == ["LE-01", "LE-02"] and e.fte.tolist() == [2.0, 0.5]
    d = hr.headcount_on(emp, term, team, D(2024, 6, 29))
    assert d.dep_key.tolist() == ["DEP-01", "DEP-02"] and d.headcount.tolist() == [1, 2], "teams map to different departments"


def test_data_now_returns_the_frames_date_not_a_constant():
    frames = {"hr": _release(now="2025-03-31"), "competence": _release(now="2025-03-31")}
    assert hr.data_now(frames) == D(2025, 3, 31) and hr.data_now(frames, D(2025, 3, 31)) == D(2025, 3, 31)
    with pytest.raises(PeriodError):
        hr.data_now(frames, D(2025, 4, 1))
