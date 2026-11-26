"""with_education, education_explained_share, education_level, skill_latest: synthetic frames (the baseline tests are in the closed repository)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import Context, FrameError, RestrictedColumnRefusal

HR = Context.from_profile("mcp_people_hr", stage="month12")
GENERIC = Context.from_profile("mcp_people", stage="month12")
D = dt.date


def _edu(rows):
    return pd.DataFrame(rows, columns=["emp_key", "seq", "level_rank"])


def test_education_level_is_the_highest_rank_per_person():
    s = hr.education_level(_edu([("EMP-000002", 1, 4), ("EMP-000002", 2, 2), ("EMP-000001", 1, 1)]))
    assert s.to_dict() == {"EMP-000001": 1, "EMP-000002": 4} and s.name == "education_rank" and s.dtype == "int64"
    assert hr.education_level(_edu([])).empty
    with pytest.raises(FrameError, match="nulls"):
        hr.education_level(_edu([("EMP-000001", 1, None)]))
    with pytest.raises(FrameError, match="lacks column"):
        hr.education_level(_edu([]).drop(columns="level_rank"))


def _frame(n=40, seed=3):
    """A pay frame: men and women, two grades, one entity, rate = grade effect + education effect + a gap for women."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        g = "F" if i % 2 == 0 else "M"
        lvl = 4 + (i // 2) % 2
        rows.append({"emp_key": f"EMP-{i + 1:06d}", "gender": g, "legal_entity_key": "LE-01", "level": lvl, "tenure_years": float(i % 7), "dep_key": "DEP-03",
                     "rate_dkk": 40000 * (1 + 0.1 * (lvl - 4)) * (0.9 if g == "F" else 1.0) * (1 + 0.02 * rng.normal())})
    return pd.DataFrame(rows)


def test_with_education_adds_rank_zero_without_a_record_and_leaves_the_input_alone():
    f = _frame(6)
    before = f.copy(deep=True)
    out = hr.with_education(f, _edu([("EMP-000001", 1, 3), ("EMP-000001", 2, 5), ("EMP-000003", 1, 2)]), context=HR)
    assert out.education_rank.tolist() == [5, 0, 2, 0, 0, 0] and out.has_education_record.tolist() == [True, False, True, False, False, False]
    pd.testing.assert_frame_equal(f, before)
    with pytest.raises(FrameError, match="already has"):
        hr.with_education(out, _edu([]), context=HR)
    with pytest.raises(RestrictedColumnRefusal):
        hr.with_education(f, _edu([]), context=GENERIC)


def test_explained_share_is_gap_without_minus_gap_with_and_suppressed_below_the_minimum_group():
    f = _frame(60)
    edu = _edu([(e, 1, 2 + int(k % 3)) for k, e in enumerate(f.emp_key)])
    w = hr.with_education(f, edu, context=HR)
    r = hr.education_explained_share(w, context=HR)
    assert r["n_women"] == 30 and r["n_men"] == 30 and not r["suppressed"] and r["n_without_record"] == 0
    assert r["explained_pp"] == pytest.approx(r["gap_without_education_pct"] - r["gap_with_education_pct"])
    assert r["gap_without_education_pct"] == pytest.approx(hr.adjusted_gap(w, context=HR)["adjusted_gap_pct"]), "the first number is the adjusted gap"
    assert 5 < r["gap_without_education_pct"] < 15, "the gap of about 10 percent built into the frame is found"
    small = hr.education_explained_share(w.head(12), context=HR)
    assert small["suppressed"] and np.isnan(small["explained_pp"]) and np.isnan(small["gap_with_education_pct"])
    # education that really explains pay: women hold lower ranks and rank drives the rate
    g = w.copy()
    g["education_rank"] = np.where(g.gender == "F", 1, 2) + (np.arange(len(g)) // 3) % 2        # women rank 1 or 2, men 2 or 3, not collinear with the grade pattern
    g["rate_dkk"] = 30000 * (1 + 0.1 * g.education_rank)
    ex = hr.education_explained_share(g, context=HR)
    assert ex["gap_without_education_pct"] > 5 and abs(ex["gap_with_education_pct"]) < 0.5 and ex["explained_pp"] > 5, "rank explains the gap in this frame"
    with pytest.raises(FrameError, match="from with_education"):
        hr.education_explained_share(f, context=HR)


def test_adjusted_gap_extra_control_is_optional_and_checked():
    f = _frame(60)
    base = hr.adjusted_gap(f, context=HR)
    assert hr.adjusted_gap(f, context=HR, extra_controls=()) == base
    with pytest.raises(FrameError, match="lacks column"):
        hr.adjusted_gap(f, context=HR, extra_controls=["nope"])
    with pytest.raises(FrameError, match="missing"):
        hr.adjusted_gap(f.assign(education_rank=np.where(f.index == 0, np.nan, 1.0)), context=HR, extra_controls="education_rank")


def _sr(rows):
    return pd.DataFrame(rows, columns=["emp_key", "skl_key", "level", "assessed_on", "round_no"])


def test_skill_latest_takes_the_last_assessment_with_ties_by_round_then_level():
    sk = pd.DataFrame({"skl_key": ["SKL-001", "SKL-002"], "name": ["Jointing", "Switching"]})
    r = _sr([("EMP-000001", "SKL-001", 2, D(2020, 1, 1), 1), ("EMP-000001", "SKL-001", 4, D(2022, 1, 1), 2), ("EMP-000001", "SKL-001", 3, D(2022, 1, 1), 3),
             ("EMP-000001", "SKL-002", 5, D(2021, 6, 1), 1), ("EMP-000002", "SKL-001", 1, D(2019, 1, 1), 1)])
    out = hr.skill_latest(r, sk)
    assert out[["emp_key", "skl_key", "level"]].values.tolist() == [["EMP-000001", "SKL-001", 3], ["EMP-000001", "SKL-002", 5], ["EMP-000002", "SKL-001", 1]] and out.name.tolist() == ["Jointing", "Switching", "Jointing"]
    on = hr.skill_latest(r, sk, D(2021, 12, 31))
    assert on[(on.emp_key == "EMP-000001") & (on.skl_key == "SKL-001")].level.iloc[0] == 2, "an assessment after the date does not exist yet"
    assert hr.skill_latest(r, sk, D(2022, 1, 1)).query("emp_key == 'EMP-000001' and skl_key == 'SKL-001'").level.iloc[0] == 3, "assessed on the date counts"
    assert hr.skill_latest(r.drop(columns="round_no"), sk).query("emp_key == 'EMP-000001' and skl_key == 'SKL-001'").level.iloc[0] == 4, "without round_no the higher level on the same day"
    with pytest.raises(FrameError, match="not in competence.skill"):
        hr.skill_latest(r, sk.iloc[:1])
    with pytest.raises(FrameError, match="duplicate skl_key"):
        hr.skill_latest(r, pd.concat([sk, sk]))


# the baseline


def test_review_guards_skill_nulls_extra_controls_and_suppression_of_the_education_fit():
    sk = pd.DataFrame({"skl_key": ["SKL-001"], "name": ["J"]})
    r = _sr([("EMP-000001", "SKL-001", 4, D(2024, 1, 1), 1), ("EMP-000001", "SKL-001", 1, None, 2)])
    with pytest.raises(FrameError, match="null emp_key, skl_key, level or assessed_on"):
        hr.skill_latest(r, sk)
    f = _frame(60)
    for bad in (["rate_dkk"], ["tenure_years"], ["level"], ["x", "x"]):
        with pytest.raises(FrameError, match="already a column|given twice"):
            hr.adjusted_gap(f.assign(x=1.0), context=HR, extra_controls=bad)
    with pytest.raises(FrameError, match="must be numeric"):
        hr.adjusted_gap(f.assign(x="a"), context=HR, extra_controls=["x"])
    with pytest.raises(FrameError, match="x have missing values"):
        hr.adjusted_gap(f.assign(x=np.where(f.index == 0, np.nan, 1.0)), context=HR, extra_controls=["x"])
    with pytest.raises(FrameError, match="whole numbers"):
        hr.with_education(f, _edu([("EMP-000001", 1, 3.7)]), context=HR)
    with pytest.raises(FrameError, match="whole numbers"):
        hr.with_education(f, _edu([("EMP-000001", 1, -2)]), context=HR)
    # 8 and 8 with nine entities: the base fit runs, the fit with one more column has no degrees of freedom left
    g = _frame(16)
    g["legal_entity_key"] = [f"LE-0{1 + i % 9}" for i in range(16)]
    g["level"] = [4 + i % 3 for i in range(16)]
    w = hr.with_education(g, _edu([(e, 1, 2 + i % 3) for i, e in enumerate(g.emp_key)]), context=HR)
    out = hr.education_explained_share(w, context=HR)
    assert not np.isnan(out["gap_without_education_pct"]) and np.isnan(out["gap_with_education_pct"]) and np.isnan(out["explained_pp"]) and out["suppressed"], "suppressed follows the fit used for the difference"


# second review: education_level refuses what with_education refuses

@pytest.mark.parametrize("rows, match", [
    ([("EMP-000001", 1, 3.7)], "whole numbers"),
    ([("EMP-000001", 1, -2)], "zero or more"),
    ([("EMP-000001", 1, "3"), ("EMP-000001", 2, "10")], "whole numbers"),
    ([("EMP-000001", 1, 3), ("EMP-000002", 2, None)], "without nulls"),
    ([(None, 1, 3)], "null emp_key"),
])
def test_education_level_refuses_what_with_education_refuses(rows, match):
    edu = _edu(rows)
    with pytest.raises(FrameError, match=match):
        hr.education_level(edu)
    if "emp_key" not in match:
        with pytest.raises(FrameError, match=match):
            hr.with_education(_frame(2), edu, context=HR)


def test_education_level_still_accepts_whole_floats_zero_and_an_empty_frame():
    s = hr.education_level(_edu([("EMP-000001", 1, 0.0), ("EMP-000001", 2, 3.0), ("EMP-000002", 1, 0)]))
    assert s.to_dict() == {"EMP-000001": 3, "EMP-000002": 0} and s.dtype == "int64"
    assert hr.education_level(_edu([])).empty


def test_skill_latest_same_day_null_round_no_loses_to_a_number():
    skill = pd.DataFrame({"skl_key": ["SKL-001"], "name": ["x"]})
    day = D(2026, 3, 1)
    r = pd.DataFrame({"emp_key": "EMP-000001", "skl_key": "SKL-001", "level": [5, 2, 3], "assessed_on": [day] * 3, "round_no": [np.nan, 1.0, 2.0]})
    for order in ([0, 1, 2], [2, 1, 0], [1, 0, 2]):
        assert hr.skill_latest(r.iloc[order], skill).level.tolist() == [3], "the highest round_no wins, the null round_no row never does"
    only = r.iloc[[0, 1]]
    assert hr.skill_latest(only, skill).level.tolist() == [2]
    both_null = r.assign(round_no=np.nan).iloc[[1, 2]]
    assert hr.skill_latest(both_null, skill).level.tolist() == [3], "with no round numbers the higher level wins"
