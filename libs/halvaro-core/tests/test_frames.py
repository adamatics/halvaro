"""Frame joins with an unmatched report, and the source column check."""
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import Context, FrameError, UnmatchedKeys


def _l():
    return pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000002", "EMP-000009", None], "hours": [1, 2, 3, 4, 5]})


def _r():
    return pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000007", None], "name": ["a", "b", "c", "n"]})


def test_join_report_equals_pandas_merge_when_keys_are_complete():
    left = pd.DataFrame({"k": ["a", "b", "b", "c"], "x": [1, 2, 3, 4]})
    right = pd.DataFrame({"k": ["a", "b", "d"], "y": [10, 20, 40]})
    for how in ("inner", "left", "right", "outer"):
        res = core.join_report(left, right, "k", how=how)
        want = left.merge(right, on="k", how=how, suffixes=("", "_right"))
        assert res.frame.sort_values(["k", "x"], na_position="last").reset_index(drop=True).equals(want.sort_values(["k", "x"], na_position="last").reset_index(drop=True)), how
    r = core.join_report(left, right, "k").report
    assert r.left_only.k.tolist() == ["c"] and r.right_only.k.tolist() == ["d"] and r.counts["left_only_rows"] == 1 and r.counts["right_only_rows"] == 1


def test_a_null_key_never_matches_and_is_reported():
    res = core.join_report(_l(), _r(), "emp_key", how="outer")
    assert int(res.frame.name.eq("n").sum()) == 1 and res.frame.loc[res.frame.name == "n", "hours"].isna().all(), "the null of the right frame does not meet the null of the left frame"
    assert res.frame.loc[res.frame.hours == 5, "name"].isna().all()
    rep = res.report
    assert rep.left_only["class"].tolist().count("null_key") == 1 and rep.right_only["class"].tolist().count("null_key") == 1
    assert rep.counts["left_null_key_rows"] == 1 and rep.counts["right_null_key_rows"] == 1
    inner = core.join_report(_l(), _r(), "emp_key", how="inner").frame
    assert len(inner) == 3 and inner.emp_key.notna().all()


def test_null_key_rows_are_present_exactly_when_the_join_keeps_their_side():
    want = {"inner": (3, 0, 0), "left": (5, 1, 0), "right": (5, 0, 1), "outer": (7, 1, 1)}      # rows, left null row present, right null row present
    for how, (rows, ln, rn) in want.items():
        f = core.join_report(_l(), _r(), "emp_key", how=how).frame
        assert (len(f), int((f.hours == 5).sum()), int((f.name == "n").sum())) == (rows, ln, rn), how
        assert f.emp_key.isna().sum() == ln + rn, how
    left = core.join_report(_l(), _r(), "emp_key", how="left").frame
    assert left.emp_key.tolist()[-1] is None or pd.isna(left.emp_key.tolist()[-1]), "null key rows follow the matched rows"


def test_suffixes_and_overlapping_columns_are_kept_for_null_key_rows():
    left = pd.DataFrame({"k": ["A", None], "v": [1, 2]})
    right = pd.DataFrame({"k": ["A", "C", None], "v": [10, 30, 40]})
    f = core.join_report(left, right, "k", how="outer", suffixes=("_x", "_y")).frame
    assert list(f.columns) == ["k", "v_x", "v_y"]
    assert sorted(zip(f.v_x.fillna(-1).astype(int), f.v_y.fillna(-1).astype(int))) == [(-1, 30), (-1, 40), (1, 10), (2, -1)]
    f2 = core.join_report(left, right, "k", how="outer").frame
    assert list(f2.columns) == ["k", "v", "v_right"] and f2.loc[f2.v_right == 40, "v"].isna().all()
    other = pd.DataFrame({"b": ["A", None], "a": [5, 6]})
    g = core.join_report(pd.DataFrame({"a": ["A"], "v": [1]}), other, left_on="a", right_on="b", how="right").frame
    assert len(g) == 2 and list(g.columns) == ["a", "v", "b", "a_right"] and g.loc[g.a_right == 6, "a"].isna().all()


def test_report_counts_rows_and_keys_and_sorts_stably():
    rep = core.join_report(_l(), _r(), "emp_key").report
    assert rep.left_only.emp_key.tolist()[0] == "EMP-000009" and rep.counts["left_keys"] == 4 and rep.counts["left_only_keys"] == 2 and rep.counts["right_only_keys"] == 2
    assert rep.counts["left_rows"] == 5 and rep.counts["right_rows"] == 4 and rep.counts["left_only_rows"] == 2
    again = core.join_report(_l().sample(frac=1, random_state=1), _r().sample(frac=1, random_state=2), "emp_key").report
    assert again.left_only.equals(rep.left_only) and again.right_only.equals(rep.right_only), "the order of the input does not change the report"
    assert rep.classes() == {"orphan": 1, "null_key": 1}
    assert rep.counts["right_keys"] == 4 and rep.counts["right_only_rows"] == 2


def test_repeated_unmatched_keys_count_once_as_keys_and_each_time_as_rows():
    left = pd.DataFrame({"k": ["EMP-000009", "EMP-000003", "EMP-000009", "EMP-000001", "EMP-000009", None, None], "x": range(7)})
    right = pd.DataFrame({"k": ["EMP-000001", "EMP-000008", "EMP-000007", "EMP-000008", "EMP-000008", None], "y": range(6)})
    rep = core.join_report(left, right, "k").report
    assert rep.left_only.k.tolist()[:2] == ["EMP-000003", "EMP-000009"] and rep.left_only["class"].tolist() == ["orphan", "orphan", "null_key"]
    assert rep.counts["left_only_keys"] == 3 and rep.counts["left_only_rows"] == 1 + 3 + 2
    assert rep.right_only.k.tolist()[:2] == ["EMP-000007", "EMP-000008"] and rep.counts["right_only_keys"] == 3
    assert rep.counts["right_only_rows"] == 1 + 3 + 1 and rep.counts["right_keys"] == 4 and rep.counts["left_keys"] == 4
    assert rep.classes("right") == {"orphan": 2, "null_key": 1} and rep.has_orphans()
    only_right = core.join_report(left[left.k == "EMP-000001"], right, "k").report
    assert not only_right.left_only.shape[0] and only_right.has_orphans(), "orphans on the right side count"


def test_different_and_composite_key_names():
    left = pd.DataFrame({"a": ["x", "x", "y"], "b": [1, 2, 3], "v": [1, 2, 3]})
    right = pd.DataFrame({"c": ["x", "y"], "d": [1, 9], "w": [10, 20]})
    res = core.join_report(left, right, left_on=["a", "b"], right_on=["c", "d"], how="outer")
    assert len(res.frame) == 4 and res.report.left_only[["a", "b"]].values.tolist() == [["x", 2], ["y", 3]] and res.report.right_only[["c", "d"]].values.tolist() == [["y", 9]]
    with pytest.raises(FrameError, match="same length"):
        core.join_report(left, right, left_on=["a", "b"], right_on=["c"])
    with pytest.raises(FrameError, match="lacks key column"):
        core.join_report(left, right, "zz")
    with pytest.raises(FrameError, match="how"):
        core.join_report(left, right, left_on="a", right_on="c", how="cross")
    with pytest.raises(FrameError, match="name the key columns"):
        core.join_report(left, right)


def test_composite_keys_with_one_null_part_never_match():
    left = pd.DataFrame({"a": ["x", "x", None], "b": [1, None, 2], "v": [1, 2, 3]})
    right = pd.DataFrame({"c": ["x", "y", "y"], "d": [1, None, 2], "w": [10, 20, 30]})
    res = core.join_report(left, right, left_on=["a", "b"], right_on=["c", "d"], how="outer")
    assert res.report.classes() == {"null_key": 2} and res.report.classes("right") == {"orphan": 1, "null_key": 1}
    assert res.report.counts["left_null_key_rows"] == 2 and res.report.counts["right_null_key_rows"] == 1
    assert len(res.frame) == 1 + 2 + 2 and res.frame.loc[res.frame.w == 20, "a"].isna().all()
    r = core.join_report(left, right, left_on=["a", "b"], right_on=["c", "d"], how="right").frame
    assert r.loc[r.w == 20, "c"].tolist() == ["y"] and r.loc[r.w == 30, "d"].tolist() == [2]


def test_strict_failure_with_composite_keys_lists_tuples_and_names_the_side():
    left = pd.DataFrame({"a": ["x", "y"], "b": [1, 2]})
    right = pd.DataFrame({"c": ["x"], "d": [1]})
    with pytest.raises(UnmatchedKeys) as e:
        core.join_report(left, right, left_on=["a", "b"], right_on=["c", "d"], strict=True)
    assert e.value.side == "left" and e.value.keys == (("y", 2),)
    with pytest.raises(UnmatchedKeys) as e2:
        core.join_report(right, left, left_on=["c", "d"], right_on=["a", "b"], how="inner", strict=True)
    assert e2.value.side == "right" and e2.value.keys == (("y", 2),)
    core.join_report(right, left, left_on=["c", "d"], right_on=["a", "b"], how="left", strict=True)      # right-only keys are what a left join expects
    with pytest.raises(FrameError, match="right frame lacks key column.*d"):
        core.join_report(left, right.rename(columns={"d": "e"}), left_on=["a", "b"], right_on=["c", "d"])
    with pytest.raises(FrameError, match="left frame lacks key column.*b"):
        core.join_report(left.drop(columns="b"), right, left_on=["a", "b"], right_on=["c", "d"])


def test_argument_conflicts_are_refused():
    f = pd.DataFrame({"k": ["a"], "j": ["a"]})
    with pytest.raises(FrameError, match="not both"):
        core.join_report(f, f, "k", right_on="j")
    with pytest.raises(FrameError, match="class"):
        core.join_report(pd.DataFrame({"class": ["a"]}), pd.DataFrame({"class": ["a"]}), "class")


def test_a_key_whose_master_is_above_the_stage_is_not_an_orphan():
    left = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000002"], "emp_key": ["EMP-000001", "EMP-000002"]})
    empty = pd.DataFrame({"prj_key": pd.Series([], dtype=object)})
    day1 = Context(stage="day1", role="r")
    r = core.join_report(left, empty, "prj_key", context=day1).report
    assert r.left_only["class"].tolist() == ["master_not_visible_at_stage"] * 2 and not r.has_orphans()
    r12 = core.join_report(left, empty, "prj_key", context=Context(stage="month12", role="r")).report
    assert r12.left_only["class"].tolist() == ["orphan"] * 2 and r12.has_orphans()
    assert core.join_report(left, empty, "prj_key").report.left_only["class"].tolist() == ["orphan"] * 2, "without a context there is no stage to excuse a key"
    emp = core.join_report(left, pd.DataFrame({"emp_key": ["EMP-000001"]}), "emp_key", context=day1).report
    assert emp.left_only.emp_key.tolist() == ["EMP-000002"] and emp.left_only["class"].tolist() == ["orphan"], "EMP is mastered by hr at day1: visible, so an orphan"
    right_side = core.join_report(pd.DataFrame({"prj_key": []}), left, "prj_key", context=day1).report
    assert right_side.right_only["class"].tolist() == ["master_not_visible_at_stage"] * 2 and not right_side.has_orphans()
    month3 = Context(stage="month3", role="r")
    assert core.join_report(left, empty, "prj_key", context=month3).report.left_only["class"].tolist() == ["master_not_visible_at_stage"] * 2, "PRJ is a month12 master, above month3"
    assert core.join_report(empty, left, "prj_key", context=month3).report.right_only["class"].tolist() == ["master_not_visible_at_stage"] * 2
    mixed = core.join_report(pd.DataFrame({"u": ["ghost"]}), pd.DataFrame({"u": []}), "u", context=day1).report
    assert mixed.left_only["class"].tolist() == ["orphan"], "not a typed key: nothing to excuse"


def test_strict_mode_raises_for_orphans_only():
    left = pd.DataFrame({"prj_key": ["PRJ-000001"], "emp_key": ["EMP-000002"]})
    day1 = Context(stage="day1", role="r")
    core.join_report(left, pd.DataFrame({"prj_key": []}), "prj_key", context=day1, strict=True)         # master above the stage: no error
    with pytest.raises(UnmatchedKeys) as e:
        core.join_report(left, pd.DataFrame({"emp_key": ["EMP-000001"]}), "emp_key", context=day1, strict=True)
    assert e.value.side == "left" and e.value.keys == ("EMP-000002",)
    with pytest.raises(UnmatchedKeys) as e2:
        core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000009"]}), "emp_key", how="inner", strict=True)
    assert e2.value.side == "right" and e2.value.keys == ("EMP-000009",)
    core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), pd.DataFrame({"emp_key": ["EMP-000001"]}), "emp_key", strict=True)
    core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000009"]}), "emp_key", strict=True)      # how='left': right-only keys are expected
    extra_right = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000009"]})
    core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), extra_right, "emp_key", strict="left")      # only the left side is checked
    with pytest.raises(UnmatchedKeys):
        core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), extra_right, "emp_key", strict="right")
    with pytest.raises(FrameError, match="strict"):
        core.join_report(pd.DataFrame({"emp_key": ["EMP-000001"]}), extra_right, "emp_key", strict="both")


def test_validate_catches_duplicate_keys_in_the_right_frame():
    right = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "n": [1, 2]})
    with pytest.raises(Exception, match="not unique|one-to-many|many-to-one"):
        core.join_report(_l(), right, "emp_key", validate="many_to_one")


def test_require_frame_columns():
    f = pd.DataFrame({"emp_key": [], "hire_date": []})
    core.require_frame_columns(f, "hr.employee", ["emp_key", "hire_date"])
    with pytest.raises(FrameError, match="lacks column.*username"):
        core.require_frame_columns(f, "hr.employee", ["emp_key", "username"])
    with pytest.raises(FrameError, match="not column.*hire_dat"):
        core.require_frame_columns(f, "hr.employee", ["hire_dat"])
    with pytest.raises(FrameError, match="not a table"):
        core.require_frame_columns(f, "hr.nope", ["emp_key"])
    for bad in ("hr", "hr.emp", "hr.employee.emp_key"):
        with pytest.raises(FrameError, match="not a table"):
            core.require_frame_columns(f, bad, ["emp_key"])
    with pytest.raises(FrameError, match=r"hire_dat, usernam.* are not column"):
        core.require_frame_columns(f, "hr.employee", ["hire_dat", "emp_key", "usernam"])
    core.require_frame_columns(f, "hr.employee", "emp_key")
    with pytest.raises(FrameError, match="lacks column.*username"):
        core.require_frame_columns(f, "hr.employee", "username")
    with pytest.raises(FrameError, match="without renaming"):
        core.require_frame_columns(f.rename(columns={"emp_key": "id"}), "hr.employee", ["emp_key"])


def test_the_new_functions_are_registered():
    ids = {r["id"] for r in core.registry.export_index()}
    assert {"halvaro.core.frames.join_report", "halvaro.core.frames.require_frame_columns"} <= ids and core.registry.check() == []
