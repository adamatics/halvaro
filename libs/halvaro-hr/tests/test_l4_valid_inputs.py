"""Inputs the bodies accepted before the L4.3 checks keep their result; an infinite skill level gives the FrameError (review of #563)."""
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError

D = "2026-03-31"


def _call(level):
    skill = pd.DataFrame({"emp_key": ["EMP-1"], "skl_key": ["SKL-1"], "level": [level]})
    org = pd.DataFrame({"emp_key": ["EMP-1"], "active": [True], "country": ["DK"], "role_name": ["r"], "legal_entity_key": ["L"]})
    cert = pd.DataFrame({"emp_key": [], "qual_key": [], "issued": [], "expires": []})
    qual = pd.DataFrame({"qual_key": ["QUAL-1"], "prerequisite_qual_key": [None], "country_scope": [None]})
    event = pd.DataFrame({"event_no": [], "qual_key": [], "date": [], "capacity": [], "seats_taken": [], "country": []})
    plan = pd.DataFrame({"prj_key": [], "emp_key": [], "percent": []})
    leave = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
    return hr.cover_candidates(skill, org, cert, qual, event, plan, leave, qual_key="QUAL-1", skl_key="SKL-1", prj_key="PRJ-1", crew=[], country="DK",
                               start=pd.Timestamp(D).date(), now=pd.Timestamp(D).date(), list_level=1, plausible_level=1, leave_days=1, seat_days=1, leave_types=["extended_leave"])


def test_a_finite_level_is_still_read():
    low, high = _call(0), _call(2.0)          # level 0 is below list_level 1: nobody; level 2 reaches it: one person by hand
    assert len(low) == 0
    assert high["emp_key"].tolist() == ["EMP-1"] and high["skill_level"].tolist() == [2]
    assert high["plausible"].tolist() == [False]      # no training seat is open before the start
    assert high["reasons"].iloc[0] == ["no_seat_before_start_plus_1d"]


@pytest.mark.parametrize("level", [float("inf"), float("-inf")])
def test_an_infinite_level_is_the_frame_error_of_a_non_numeric_level(level):
    with pytest.raises(FrameError, match="level that is not a number"):
        _call(level)
