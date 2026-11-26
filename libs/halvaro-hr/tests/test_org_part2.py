"""executives_on, status_on, tenure_years, term_changes, check_term_contiguity: contract on synthetic frames, gate numbers on the baseline."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, PeriodError, fact, registry

D = dt.date


def _emp(rows):
    return pd.DataFrame(rows, columns=["emp_key", "hire_date", "leave_date"])


# executives_on

def _org(rows, as_of=D(2026, 6, 1)):
    return pd.DataFrame(rows, columns=["emp_key", "active", "role_name", "dep_code", "team_key"]).assign(as_of=pd.Timestamp(as_of))


ROLES = pd.DataFrame({"name": ["CEO", "CFO", "COO", "Welder"]})


def test_executives_are_the_active_holders_of_the_named_roles_without_pay():
    org = _org([("EMP-000001", True, "CEO", "EXO", "TEAM-001"), ("EMP-000002", True, "CFO", "FIN", "TEAM-002"), ("EMP-000009", True, "CFO", "FIN", "TEAM-002"),
                ("EMP-000003", False, "COO", "EXO", "TEAM-001"), ("EMP-000004", True, "Welder", "PDL", "TEAM-003")]).assign(base_salary=1)
    res = hr.executives_on(org, ROLES, ["CEO", "CFO", "COO"])
    assert list(res.frame.columns) == ["emp_key", "role_name", "dep_code", "team_key"]
    assert res.frame.role_name.tolist() == ["CEO", "CFO", "CFO"] and res.frame.emp_key.tolist() == ["EMP-000001", "EMP-000002", "EMP-000009"]
    assert res.vacant == ("COO",), "the only COO is not active: vacant, listed, not an error"
    assert hr.executives_on(org, ROLES, "CEO").frame.emp_key.tolist() == ["EMP-000001"]
    assert hr.executives_on(org, ROLES, ["Welder"]).vacant == ()


def test_executives_refuse_unknown_roles_no_roles_and_mixed_dates():
    org = _org([("EMP-000001", True, "CEO", "EXO", "TEAM-001")])
    with pytest.raises(FrameError, match="'Chief' are not in hr.role.name|'Chief'"):
        hr.executives_on(org, ROLES, ["CEO", "Chief"])
    with pytest.raises(FrameError, match="at least one role"):
        hr.executives_on(org, ROLES, [])
    mixed = pd.concat([org, org.assign(as_of=pd.Timestamp(2027, 1, 1))])
    with pytest.raises(FrameError, match="one date, it has 2"):
        hr.executives_on(mixed, ROLES, ["CEO"])
    with pytest.raises(FrameError, match="lacks column.*dep_code"):
        hr.executives_on(org.drop(columns="dep_code"), ROLES, ["CEO"])
    with pytest.raises(FrameError, match="hr.role frame lacks"):
        hr.executives_on(org, ROLES.rename(columns={"name": "n"}), ["CEO"])


def test_a_role_change_between_two_dates_changes_the_holder():
    before = _org([("EMP-000001", True, "CFO", "FIN", "TEAM-002")], D(2024, 1, 1))
    after = _org([("EMP-000005", True, "CFO", "FIN", "TEAM-002"), ("EMP-000001", True, "Welder", "PDL", "TEAM-003")], D(2025, 1, 1))
    assert hr.executives_on(before, ROLES, ["CFO"]).frame.emp_key.tolist() == ["EMP-000001"]
    assert hr.executives_on(after, ROLES, ["CFO"]).frame.emp_key.tolist() == ["EMP-000005"]


# status_on

def _leave(rows):
    return pd.DataFrame(rows, columns=["emp_key", "leave_type", "start", "end"])


def test_status_labels_and_the_day_boundaries():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None), ("EMP-000002", D(2020, 1, 1), D(2026, 6, 1)), ("EMP-000003", D(2020, 1, 1), D(2026, 5, 31)),
                ("EMP-000004", D(2026, 6, 2), None), ("EMP-000005", D(2026, 6, 1), None), ("EMP-000006", D(2020, 1, 1), None), ("EMP-000007", D(2020, 1, 1), None),
                ("EMP-000008", D(2020, 1, 1), None), ("EMP-000009", D(2020, 1, 1), None)])
    lv = _leave([("EMP-000006", "parental", D(2026, 6, 1), D(2026, 8, 1)), ("EMP-000007", "extended_leave", D(2026, 1, 1), D(2026, 6, 1)),
                 ("EMP-000008", "parental", D(2026, 1, 1), D(2026, 5, 31)), ("EMP-000009", "holiday", D(2026, 5, 1), D(2026, 7, 1)),
                 ("EMP-000001", "sick", D(2026, 5, 1), D(2026, 7, 1)), ("EMP-000001", "parental", D(2026, 6, 2), D(2026, 7, 1))])
    got = dict(zip(*(hr.status_on(emp, lv, D(2026, 6, 1))[c] for c in ("emp_key", "status"))))
    assert got == {"EMP-000001": "available", "EMP-000002": "available", "EMP-000003": "left", "EMP-000004": "not_hired", "EMP-000005": "available",
                   "EMP-000006": "on_leave", "EMP-000007": "on_leave", "EMP-000008": "available", "EMP-000009": "available"}, "leave_date is the last day employed"


def test_status_leave_types_are_a_parameter_and_the_frame_shape():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None)])
    lv = _leave([("EMP-000001", "sick", D(2026, 5, 1), D(2026, 7, 1))])
    assert hr.status_on(emp, lv, D(2026, 6, 1)).status.tolist() == ["available"]
    assert hr.status_on(emp, lv, D(2026, 6, 1), unavailable_leave_types=("sick",)).status.tolist() == ["on_leave"]
    assert hr.status_on(emp, lv, D(2026, 6, 1), unavailable_leave_types="sick").status.tolist() == ["on_leave"]
    assert hr.status_on(emp, lv.iloc[:0], D(2026, 6, 1)).status.tolist() == ["available"]
    out = hr.status_on(emp.iloc[::-1].assign(), lv, D(2026, 6, 1))
    assert list(out.columns) == ["emp_key", "as_of", "status"] and (out.as_of == pd.Timestamp(2026, 6, 1)).all()
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.status_on(pd.concat([emp, emp]), lv, D(2026, 6, 1))
    with pytest.raises(FrameError, match="hr.leave_record frame lacks"):
        hr.status_on(emp, lv.drop(columns="end"), D(2026, 6, 1))


# tenure_years

def test_tenure_is_days_over_365_25_and_nan_before_hire():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None), ("EMP-000002", D(2026, 6, 2), None), ("EMP-000003", D(2020, 1, 1), D(2022, 1, 1)), ("EMP-000004", D(2020, 1, 1), D(2024, 1, 1))])
    t = hr.tenure_years(emp, D(2024, 1, 1))
    assert t.index.tolist() == ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"] and t.index.name == "emp_key" and t.name == "tenure_years"
    assert t["EMP-000001"] == 1461 / 365.25 == 4.0 and np.isnan(t["EMP-000002"])
    assert t["EMP-000003"] == (D(2022, 1, 1) - D(2020, 1, 1)).days / 365.25, "a leaver is measured to the leave date"
    assert t["EMP-000004"] == 4.0, "on the leave date itself"
    assert hr.tenure_years(emp, D(2024, 1, 1), days_per_year=365.0)["EMP-000001"] == 1461 / 365.0
    assert hr.tenure_years(emp, D(2026, 6, 2))["EMP-000002"] == 0.0
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.tenure_years(pd.concat([emp, emp]), D(2024, 1, 1))


# term_changes

def _term(reasons):
    return pd.DataFrame({"emp_key": [f"EMP-{i:06d}" for i in range(1, len(reasons) + 1)], "valid_from": [D(2023, 1, i + 1) for i in range(len(reasons))], "change_reason": reasons})


def test_term_changes_split_compound_reasons():
    out = hr.term_changes(_term(["hire", "pay_review+promotion", "fte_change", "window_start", "summary"]))
    assert len(out) == 6 and out.event.tolist() == ["hire", "pay_review", "promotion", "fte_change", "window_start", "summary"]
    assert out.combined.tolist() == [False, True, True, False, False, False] and list(out.columns) == ["emp_key", "valid_from", "event", "combined"]
    assert out.emp_key.tolist() == ["EMP-000001", "EMP-000002", "EMP-000002", "EMP-000003", "EMP-000004", "EMP-000005"]
    with pytest.raises(FrameError, match="unknown change_reason name.*'bonus'"):
        hr.term_changes(_term(["hire", "pay_review+bonus"]))
    with pytest.raises(FrameError, match="1 terms have no change_reason"):
        hr.term_changes(_term(["hire", None]))
    assert hr.term_changes(_term([])).empty


# check_term_contiguity

def _tc(rows):
    return pd.DataFrame(rows, columns=["emp_key", "valid_from", "valid_to"])


def _rules(term, emp):
    return sorted(zip(hr.check_term_contiguity(term, emp).key, hr.check_term_contiguity(term, emp).rule))


def test_clean_history_has_no_violations_and_the_four_generator_rules_are_found():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None), ("EMP-000002", D(2024, 3, 5), D(2024, 12, 31)), ("EMP-000003", D(2021, 1, 1), D(2022, 5, 5))])
    ok = _tc([("EMP-000001", D(2023, 1, 1), D(2023, 12, 31)), ("EMP-000001", D(2024, 1, 1), None), ("EMP-000002", D(2024, 3, 5), D(2024, 12, 31)),
              ("EMP-000003", D(2021, 1, 1), D(2022, 5, 5))])
    res = hr.check_term_contiguity(ok, emp)
    assert res.empty and list(res.columns) == ["table", "key", "rule", "detail"], "left before the window: first term starts at hire"
    gap = ok.copy(); gap.loc[0, "valid_to"] = D(2023, 12, 30)
    assert _rules(gap, emp) == [("EMP-000001", "gap")]
    overlap = ok.copy(); overlap.loc[0, "valid_to"] = D(2024, 1, 1)
    assert _rules(overlap, emp) == [("EMP-000001", "overlap")]
    first = ok.copy(); first.loc[0, "valid_from"] = D(2023, 1, 2)
    assert _rules(first, emp) == [("EMP-000001", "first_row")]
    openrow = ok.copy(); openrow.loc[1, "valid_to"] = D(2025, 1, 1)
    assert _rules(openrow, emp) == [("EMP-000001", "open_row")]
    two_open = ok.copy(); two_open.loc[0, "valid_to"] = None
    assert ("EMP-000001", "two_open") in _rules(two_open, emp)
    last = ok.copy(); last.loc[3, "valid_to"] = D(2022, 5, 4)
    assert _rules(last, emp) == [("EMP-000003", "last_row_not_leave_date")]
    assert _rules(ok.iloc[:3], emp) == [("EMP-000003", "no_terms")]
    reversed_ = ok.copy(); reversed_.loc[2, "valid_to"] = D(2024, 3, 4)
    assert ("EMP-000002", "reversed") in _rules(reversed_, emp)


def test_first_row_rule_for_a_hire_after_the_window_start_and_one_before():
    start = fact("world.window_start").value
    emp = _emp([("EMP-000001", D(2019, 5, 5), None), ("EMP-000002", D(2023, 5, 5), None)])
    wrong = _tc([("EMP-000001", D(2019, 5, 5), None), ("EMP-000002", start, None)])
    assert _rules(wrong, emp) == [("EMP-000001", "first_row"), ("EMP-000002", "first_row")], "hired before the window: starts on the window start, not the hire date"
    right = _tc([("EMP-000001", start, None), ("EMP-000002", D(2023, 5, 5), None)])
    assert hr.check_term_contiguity(right, emp).empty


def test_new_functions_are_registered_day1_and_listed():
    reg = registry.registered()
    for n in ("executives_on", "status_on", "tenure_years", "term_changes", "check_term_contiguity"):
        m = reg[f"halvaro.hr.org.{n}"]
        assert m.sources and all(s.startswith("hr.") for s in m.sources) and m.oracle
    assert reg["halvaro.hr.org.check_term_contiguity"].facts == ("world.window_start",)
    assert {"Executives", "executives_on", "status_on", "tenure_years", "term_changes", "check_term_contiguity"} <= set(hr.__all__) and registry.check() == []


# baseline


# review fixes

def test_contiguity_finds_terms_without_an_employee_and_bad_employee_dates():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None), ("EMP-000002", None, None), ("EMP-000003", D(2024, 5, 1), D(2024, 4, 1))])
    term = _tc([("EMP-000001", D(2023, 1, 1), None), ("EMP-000002", D(2023, 1, 1), None), ("EMP-000003", D(2024, 5, 1), D(2024, 4, 1)), ("EMP-000009", D(2023, 1, 1), None), (None, D(2023, 1, 1), None)])
    got = set(_rules(term, emp))
    assert {("EMP-000009", "no_employee"), ("(null)", "null_key"), ("EMP-000002", "hire_missing"), ("EMP-000003", "leave_before_hire")} <= got


def test_executives_active_flag_must_be_boolean_and_dates_clean():
    org = _org([("EMP-000001", True, "CEO", "EXO", "TEAM-001"), ("EMP-000002", True, "CFO", "FIN", "TEAM-002")])
    for bad in ([True, None], [True, float("nan")], ["True", "False"]):
        with pytest.raises(FrameError, match="org.active must be True or False"):
            hr.executives_on(org.assign(active=bad), ROLES, ["CEO"])
    assert hr.executives_on(org.assign(active=pd.Series([1, 0], dtype=object)), ROLES, ["CEO", "CFO"]).vacant == ("CFO",)
    with pytest.raises(FrameError, match="empty or null"):
        hr.executives_on(org.assign(as_of=pd.NaT), ROLES, ["CEO"])
    with pytest.raises(FrameError, match="one date, it has 0"):
        hr.executives_on(org.iloc[:0], ROLES, ["CEO"])
    with pytest.raises(FrameError, match="distinct role names"):
        hr.executives_on(org, ROLES, ["CEO", "CEO"])
    with pytest.raises(FrameError, match="distinct role names"):
        hr.executives_on(org, ROLES, ["CEO", None])
    with pytest.raises(FrameError, match="duplicate column names"):
        hr.executives_on(pd.concat([org, org[["dep_code"]]], axis=1), ROLES, ["CEO"])


def test_status_open_ended_leave_and_missing_hire_date():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None)])
    assert hr.status_on(emp, _leave([("EMP-000001", "parental", D(2026, 1, 1), None)]), D(2026, 6, 1)).status.tolist() == ["on_leave"]
    assert hr.status_on(emp, _leave([("EMP-000001", "parental", D(2026, 7, 1), None)]), D(2026, 6, 1)).status.tolist() == ["available"]
    with pytest.raises(FrameError, match="no hire_date.*EMP-000002"):
        hr.status_on(pd.concat([emp, _emp([("EMP-000002", None, None)])]), _leave([]), D(2026, 6, 1))
    for bad in (pd.Timestamp("2026-06-01", tz="UTC"), "junk", 20260601, None):
        with pytest.raises(PeriodError):
            hr.status_on(emp, _leave([]), bad)
        with pytest.raises(PeriodError):
            hr.tenure_years(emp, bad)


def test_tenure_negative_zero_and_inverted_inputs():
    emp = _emp([("EMP-000001", D(2024, 5, 1), D(2024, 4, 1)), ("EMP-000002", D(2020, 1, 1), None)])
    assert np.isnan(hr.tenure_years(emp, D(2026, 1, 1))["EMP-000001"], ) and hr.tenure_years(emp, D(2026, 1, 1))["EMP-000002"] > 0
    for bad in (0, -365.25, float("nan")):
        with pytest.raises(FrameError, match="days_per_year must be positive"):
            hr.tenure_years(emp, D(2026, 1, 1), days_per_year=bad)


def test_term_changes_sort_by_real_dates_not_by_text_or_type():
    t = pd.DataFrame({"emp_key": ["EMP-000001"] * 3, "valid_from": [D(2023, 6, 1), "2023-01-01", pd.Timestamp("2023-03-01")], "change_reason": ["pay_review", "hire", "promotion"]})
    assert hr.term_changes(t).event.tolist() == ["hire", "promotion", "pay_review"]


# survivors of the mutation review

def test_status_label_precedence_left_over_leave_and_not_hired_over_leave():
    emp = _emp([("EMP-000001", D(2020, 1, 1), D(2026, 5, 31)), ("EMP-000002", D(2026, 7, 1), None)])
    lv = _leave([("EMP-000001", "parental", D(2026, 1, 1), D(2026, 12, 31)), ("EMP-000002", "parental", D(2026, 1, 1), D(2026, 12, 31))])
    assert hr.status_on(emp, lv, D(2026, 6, 1)).status.tolist() == ["left", "not_hired"]


def test_status_output_keeps_the_employee_index_and_order():
    emp = _emp([("EMP-000003", D(2020, 1, 1), None), ("EMP-000001", D(2020, 1, 1), None), ("EMP-000002", D(2020, 1, 1), D(2020, 6, 1))])
    emp.index = [30, 10, 20]
    out = hr.status_on(emp, _leave([]), D(2026, 6, 1))
    assert out.index.tolist() == [30, 10, 20] and out.emp_key.tolist() == ["EMP-000003", "EMP-000001", "EMP-000002"] and out.status.tolist() == ["available", "available", "left"]


def test_tenure_of_a_future_leaver_runs_to_the_date():
    emp = _emp([("EMP-000001", D(2020, 1, 1), D(2030, 1, 1))])
    assert hr.tenure_years(emp, D(2024, 1, 1))["EMP-000001"] == 4.0


def test_a_last_term_that_ends_after_the_leave_date_is_flagged():
    emp = _emp([("EMP-000001", D(2020, 1, 1), D(2024, 6, 30))])
    late = _tc([("EMP-000001", D(2023, 1, 1), D(2024, 7, 1))])
    assert _rules(late, emp) == [("EMP-000001", "last_row_not_leave_date")]
    early = _tc([("EMP-000001", D(2023, 1, 1), D(2024, 6, 29))])
    assert _rules(early, emp) == [("EMP-000001", "last_row_not_leave_date")]


def test_a_leave_date_on_the_window_start_does_not_move_the_first_term():
    start = fact("world.window_start").value
    emp = _emp([("EMP-000001", D(2019, 5, 5), start)])
    on_start = _tc([("EMP-000001", start, start)])
    assert hr.check_term_contiguity(on_start, emp).empty, "left on the window start: the first term starts on the window start, not on the hire date"
    before = _emp([("EMP-000001", D(2019, 5, 5), start - dt.timedelta(days=1))])
    assert _rules(_tc([("EMP-000001", D(2019, 5, 5), start - dt.timedelta(days=1))]), before) == []


def test_term_order_in_the_input_does_not_matter():
    emp = _emp([("EMP-000001", D(2020, 1, 1), None)])
    term = _tc([("EMP-000001", D(2023, 1, 1), D(2023, 12, 31)), ("EMP-000001", D(2024, 1, 1), D(2024, 12, 31)), ("EMP-000001", D(2025, 1, 1), None)])
    assert hr.check_term_contiguity(term.iloc[::-1], emp).empty
    res = hr.check_term_contiguity(_tc([("EMP-000002", D(2023, 1, 1), None)]), _emp([("EMP-000002", D(2023, 1, 1), None), ("EMP-000003", D(2023, 1, 1), None)]))
    assert res.table.tolist() == ["hr.employment_term"] and res.key.tolist() == ["EMP-000003"] and res.rule.tolist() == ["no_terms"] and "no term" in res.detail.iloc[0]
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.check_term_contiguity(term, pd.concat([emp, emp]))
    with pytest.raises(FrameError, match="lacks column.*leave_date"):
        hr.check_term_contiguity(term, emp.drop(columns="leave_date"))
    with pytest.raises(FrameError, match="lacks column.*valid_to"):
        hr.check_term_contiguity(term.drop(columns="valid_to"), emp)


def test_executives_sorted_vacant_in_call_order_and_unused_roles_are_not_errors():
    org = _org([("EMP-000009", True, "CFO", "FIN", "TEAM-002"), ("EMP-000002", True, "CFO", "FIN", "TEAM-002"), ("EMP-000005", True, "CEO", "EXO", "TEAM-001")])
    res = hr.executives_on(org.iloc[::-1], ROLES, ["CFO", "CEO"])
    assert res.frame.role_name.tolist() == ["CEO", "CFO", "CFO"] and res.frame.emp_key.tolist() == ["EMP-000005", "EMP-000002", "EMP-000009"]
    both = hr.executives_on(org, pd.DataFrame({"name": ["CEO", "CFO", "COO", "Welder", "Analyst"]}), ["Welder", "COO", "Analyst"])
    assert both.frame.empty and both.vacant == ("Welder", "COO", "Analyst"), "known in hr.role but held by nobody: vacant, not an error"
    with pytest.raises(FrameError, match="lacks column.*role_name"):
        hr.executives_on(org.drop(columns="role_name"), ROLES, ["CEO"])


def test_term_changes_order_with_shuffled_terms_and_missing_columns():
    t = pd.DataFrame({"emp_key": ["EMP-000002", "EMP-000001", "EMP-000001", "EMP-000001"], "valid_from": [D(2023, 1, 1), D(2024, 1, 1), D(2023, 1, 1), D(2025, 1, 1)],
                      "change_reason": ["hire", "promotion+pay_review", "window_start", "fte_change"]})
    out = hr.term_changes(t)
    assert out.emp_key.tolist() == ["EMP-000001", "EMP-000001", "EMP-000001", "EMP-000001", "EMP-000002"]
    assert out.event.tolist() == ["window_start", "pay_review", "promotion", "fte_change", "hire"], "same person: by date, then by event name"
    with pytest.raises(FrameError, match="lacks column.*change_reason"):
        hr.term_changes(t.drop(columns="change_reason"))
