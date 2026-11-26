"""Wrong inputs of payroll_aggregate that cannot be golden error cases (a golden frame may not hold a value in a restricted column): the error is an error of the library (issue #563)."""
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import Context, FrameError

READER = Context(stage="month12", role="analyst", restricted_ok=True)


def _frames(**changes):
    term = pd.DataFrame({"emp_key": ["EMP-1"], "valid_from": ["2025-01-01"], "valid_to": [None], "team_key": ["T"], "grade_key": ["G"], "fte": [1.0], "currency": ["DKK"], "base_salary": [1.0]}).assign(**changes)
    team = pd.DataFrame({"team_key": ["T"], "cost_centre_key": ["C"], "legal_entity_key": ["L"]})
    grade = pd.DataFrame({"gra_key": ["G"], "band_min_dkk": [1.0], "band_max_dkk": [2.0], "band_min_eur": [1.0], "band_max_eur": [2.0]})
    return term, team, grade


@pytest.mark.parametrize("column", ["fte", "base_salary"])
def test_text_in_fte_or_base_salary_is_a_frame_error(column):
    term, team, grade = _frames(**{column: "x"})
    with pytest.raises(FrameError, match="fte and base_salary must be numbers"):
        hr.payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=1, context=READER)


def test_numbers_still_work():
    term, team, grade = _frames()
    assert len(hr.payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=1, context=READER)) == 1
