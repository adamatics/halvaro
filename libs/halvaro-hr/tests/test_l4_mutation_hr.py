"""Tests for the input checks of the L4.3 branch that no other test caught (third round, issue #563)."""
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, PeriodError

D = "2026-03-31"


def _expiry(as_of=D, **kw):
    cert = pd.DataFrame({"emp_key": [], "qual_key": [], "issued": [], "expires": []})
    booked = pd.DataFrame({"emp_key": [], "qual_key": [], "course_date": [], "course_end": [], "event_no": [], "free_seats": []})
    event = pd.DataFrame({"event_no": [], "qual_key": [], "date": [], "capacity": [], "seats_taken": [], "country": [], "location_site_key": []})
    emp = pd.DataFrame({"emp_key": [], "leave_date": [], "legal_entity_key": []})
    leave = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
    kw.setdefault("expiry_date", D)
    return hr.expiry_report(cert, booked, event, emp, leave, as_of, qual_key="QUAL-01", **kw)


def _cover(**kw):
    skill = pd.DataFrame({"emp_key": ["EMP-1"], "skl_key": ["SKL-1"], "level": [2]})
    org = pd.DataFrame({"emp_key": ["EMP-1"], "active": [True], "country": ["DK"], "role_name": ["r"], "legal_entity_key": ["L"]})
    cert = pd.DataFrame({"emp_key": [], "qual_key": [], "issued": [], "expires": []})
    qual = pd.DataFrame({"qual_key": ["QUAL-1"], "prerequisite_qual_key": [None], "country_scope": [None]})
    event = pd.DataFrame({"event_no": [], "qual_key": [], "date": [], "capacity": [], "seats_taken": [], "country": []})
    plan = pd.DataFrame({"prj_key": [], "emp_key": [], "percent": []})
    leave = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
    args = dict(qual_key="QUAL-1", skl_key="SKL-1", prj_key="PRJ-1", crew=[], country="DK", start=pd.Timestamp(D).date(), now=pd.Timestamp(D).date(),
                list_level=1, plausible_level=1, leave_days=1, seat_days=1, leave_types=["extended_leave"])
    args.update(kw)
    return hr.cover_candidates(skill, org, cert, qual, event, plan, leave, **args)


def _audit(role_groups):
    f = lambda *c: pd.DataFrame({k: pd.Series([], dtype=object) for k in c})
    return hr.controlled_work_audit(
        f("emp_key", "work_date", "prj_key", "cst_key"), f("emp_key", "prj_key", "start", "end"), f("prj_key", "type"),
        f("emp_key", "valid_from", "valid_to", "role_key"), f("role_key", "name"), f("emp_key", "legal_entity_key", "hire_date"),
        f("emp_key", "qual_key", "issued", "expires"), f("rule_id", "qual_key", "roles", "entity", "project_types", "cst", "allocation"),
        D, role_groups=role_groups)


def test_valid_inputs_still_work():
    assert len(_expiry().frame) == 0
    assert len(_expiry(unavailable_leave_types=["extended_leave"]).frame) == 0
    assert len(_cover()) == 1
    _audit({"G": ["r"]})
    _audit(None)


@pytest.mark.parametrize("value", [5, 2.5])
def test_a_number_as_date_names_the_argument(value):
    with pytest.raises(PeriodError, match=f"^as_of {value!r} is a number"):
        _expiry(as_of=value)
    with pytest.raises(PeriodError, match=f"^expiry_date {value!r} is a number"):
        _expiry(expiry_date=value)


def test_text_that_is_no_date_names_the_argument():
    with pytest.raises(PeriodError, match="^as_of 'nonsense' is not a date"):
        _expiry(as_of="nonsense")
    with pytest.raises(PeriodError, match="^expiry_date 'nonsense' is not a date"):
        _expiry(expiry_date="nonsense")


@pytest.mark.parametrize("bad", [["a"], 5, "G"])
def test_role_groups_that_is_not_a_mapping_is_a_frame_error(bad):
    with pytest.raises(FrameError, match="role_groups must be None or a mapping"):
        _audit(bad)


@pytest.mark.parametrize("arg", ["list_level", "plausible_level", "leave_days", "seat_days"])
def test_a_text_policy_number_names_its_argument(arg):
    with pytest.raises(FrameError, match=f"{arg}"):
        _cover(**{arg: "x"})


def test_a_number_as_crew_is_a_frame_error():
    with pytest.raises(FrameError, match="crew must be a list of emp_key"):
        _cover(crew=5)


def test_a_number_as_leave_types_names_the_argument():
    with pytest.raises(FrameError, match="^unavailable_leave_types must be a leave type name"):
        _expiry(unavailable_leave_types=5)
    with pytest.raises(FrameError, match="^leave_types must be a leave type name"):
        _cover(leave_types=5)
