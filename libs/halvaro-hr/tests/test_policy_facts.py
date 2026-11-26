"""Policy facts of hr plan 4.4 (authored, status proposed) and the three hr parameters that read them. Synthetic frames only."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import combine_status, fact

D = dt.date


def test_proposed_counts_as_verify_in_an_envelope_status():
    assert combine_status([fact("policy.offboarding.asset_return_days").status]) == ("VERIFY" if fact("policy.offboarding.asset_return_days").status == "proposed" else "ok")      # lane F3 (issue #543), approved edit
    assert combine_status(["proposed", "synthetic"]) == "VERIFY+synthetic" and combine_status(["verified", "proposed"]) == "VERIFY"


def _emp():
    return pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"], "hire_date": [D(2020, 1, 1)] * 4, "leave_date": [None] * 4})


def _leave(types):
    return pd.DataFrame({"emp_key": [f"EMP-00000{i + 1}" for i in range(len(types))], "leave_type": types, "start": [D(2026, 1, 1)] * len(types), "end": [None] * len(types)})


def test_status_on_default_leave_types_come_from_the_fact_and_can_be_overridden():
    lr = _leave(["extended_leave", "parental", "sick", "holiday"])
    assert hr.status_on(_emp(), lr, D(2026, 6, 1)).status.tolist() == ["on_leave", "on_leave", "available", "available"]
    assert hr.status_on(_emp(), lr, D(2026, 6, 1), unavailable_leave_types=["sick"]).status.tolist() == ["available", "available", "on_leave", "available"]
    assert hr.status_on(_emp(), lr, D(2026, 6, 1), unavailable_leave_types="holiday").status.tolist() == ["available", "available", "available", "on_leave"]


def test_expiring_default_window_is_the_fact_and_an_explicit_window_wins():
    days = fact("policy.certificates.expiry_warning_days").value
    c = pd.DataFrame([("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2026, 11, 30) + dt.timedelta(days=days), "valid", "course", None, 1),
                      ("EMP-000002", "QUAL-001", D(2023, 1, 1), D(2026, 11, 30) + dt.timedelta(days=days + 1), "valid", "course", None, 1)],
                     columns=["emp_key", "qual_key", "issued", "expires", "status", "origin", "renews_issued", "event_no"])
    v = hr.valid_on(c, D(2026, 11, 30))
    b = pd.DataFrame(columns=["emp_key", "qual_key", "course_date", "course_end", "event_no", "free_seats"])
    assert hr.expiring(v, b, D(2026, 11, 30)).emp_key.tolist() == ["EMP-000001"], "the day after the warning window is not listed"
    assert hr.expiring(v, b, D(2026, 11, 30), window_days=days + 1).emp_key.tolist() == ["EMP-000001", "EMP-000002"]


def test_resolve_assignments_default_return_days_is_the_fact_and_the_diagnostics_say_so():
    idx = pd.DataFrame({"username": ["c.gone"], "kind": ["employee"], "holder": ["EMP-000001"], "emp_key": ["EMP-000001"], "team_key": [None], "valid_from": [D(2020, 1, 1)], "valid_to": [None]})
    emp = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": [D(2020, 1, 1)], "leave_date": [D(2023, 6, 30)]})
    a = pd.DataFrame([("AST-000001", D(2023, 1, 1), None, "c.gone", None, "named")], columns=["ast_key", "valid_from", "valid_to", "assigned_username", "pool_team_key", "assignment_type"])
    days = fact("policy.offboarding.asset_return_days").value
    on = hr.resolve_assignments(a, idx, emp, D(2023, 6, 30) + dt.timedelta(days=days))
    over = hr.resolve_assignments(a, idx, emp, D(2023, 6, 30) + dt.timedelta(days=days + 1))
    assert not on.frame.late_return.iloc[0] and over.frame.late_return.iloc[0]
    assert on.diagnostics["asset_return_days"] == days and on.diagnostics["asset_return_days_status"] == fact("policy.offboarding.asset_return_days").status      # lane F3 (issue #543), approved edit
    given = hr.resolve_assignments(a, idx, emp, D(2023, 7, 1), asset_return_days=0)
    assert given.frame.late_return.iloc[0] and given.diagnostics["asset_return_days_status"] == "given"


def test_policy_defaults_print_as_the_fact_id_in_the_signature():
    assert repr(hr.org.UNAVAILABLE_LEAVE_TYPES) == "policy:policy.staffing.unavailable_leave_types"


def test_defaults_read_the_fact_at_call_time(monkeypatch):
    """A default that was a hard coded literal would not change when the fact does."""
    import halvaro.hr.certs as certs
    import halvaro.hr.crosswalk as crosswalk
    import halvaro.hr.org as org
    from halvaro.core.facts import Fact

    def fake(fid):
        return Fact(fid, {"policy.staffing.unavailable_leave_types": "sick", "policy.certificates.expiry_warning_days": 5, "policy.offboarding.asset_return_days": 0}[fid], "proposed", "test")
    for mod in (org, certs, crosswalk):
        monkeypatch.setattr(mod, "fact", fake)
    assert hr.status_on(_emp(), _leave(["extended_leave", "sick", "sick", "holiday"]), D(2026, 6, 1)).status.tolist() == ["available", "on_leave", "on_leave", "available"]
    c = pd.DataFrame([("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2026, 12, 5), "valid", "course", None, 1), ("EMP-000002", "QUAL-001", D(2023, 1, 1), D(2026, 12, 6), "valid", "course", None, 1)],
                     columns=["emp_key", "qual_key", "issued", "expires", "status", "origin", "renews_issued", "event_no"])
    b = pd.DataFrame(columns=["emp_key", "qual_key", "course_date", "course_end", "event_no", "free_seats"])
    assert hr.expiring(hr.valid_on(c, D(2026, 11, 30)), b, D(2026, 11, 30)).emp_key.tolist() == ["EMP-000001"]
    idx = pd.DataFrame({"username": ["c.gone"], "kind": ["employee"], "holder": ["EMP-000001"], "emp_key": ["EMP-000001"], "team_key": [None], "valid_from": [D(2020, 1, 1)], "valid_to": [None]})
    emp = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": [D(2020, 1, 1)], "leave_date": [D(2023, 6, 30)]})
    a = pd.DataFrame([("AST-000001", D(2023, 1, 1), None, "c.gone", None, "named")], columns=["ast_key", "valid_from", "valid_to", "assigned_username", "pool_team_key", "assignment_type"])
    assert hr.resolve_assignments(a, idx, emp, D(2023, 7, 1)).diagnostics["asset_return_days"] == 0


def test_a_policy_fact_that_is_not_a_whole_number_is_a_frame_error(monkeypatch):
    import halvaro.hr.certs as certs
    from halvaro.core import FrameError
    from halvaro.core.facts import Fact
    monkeypatch.setattr(certs, "fact", lambda fid: Fact(fid, "upper end of the lead months", "proposed", "test"))
    v = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-001"], "expires": [pd.Timestamp(2027, 1, 1)]})
    b = pd.DataFrame(columns=["emp_key", "qual_key", "course_date", "event_no", "free_seats"])
    with pytest.raises(FrameError, match="whole number"):
        hr.expiring(v, b, D(2026, 11, 30))


def test_a_default_that_reads_a_proposed_fact_says_so_on_the_frame_and_an_explicit_value_does_not():
    lr = _leave(["sick"])
    s = hr.status_on(_emp(), lr, D(2026, 6, 1))
    assert s.attrs["policy_status"] == {"policy.staffing.unavailable_leave_types": fact("policy.staffing.unavailable_leave_types").status}      # lane F3 (issue #543), approved edit
    assert "policy_status" not in hr.status_on(_emp(), lr, D(2026, 6, 1), unavailable_leave_types=["sick"]).attrs
    c = pd.DataFrame([("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2026, 12, 15), "valid", "course", None, 1)],
                     columns=["emp_key", "qual_key", "issued", "expires", "status", "origin", "renews_issued", "event_no"])
    v = hr.valid_on(c, D(2026, 11, 30))
    b = pd.DataFrame(columns=["emp_key", "qual_key", "course_date", "course_end", "event_no", "free_seats"])
    assert hr.expiring(v, b, D(2026, 11, 30)).attrs["policy_status"] == {"policy.certificates.expiry_warning_days": fact("policy.certificates.expiry_warning_days").status}
    assert "policy_status" not in hr.expiring(v, b, D(2026, 11, 30), window_days=30).attrs
