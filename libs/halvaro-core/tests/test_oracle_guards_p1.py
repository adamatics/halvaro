"""Oracles of three guards of halvaro.core (lane P1): a restricted column under its full id, a result with an extra column, and a group without a count. The restricted columns appear by name
only; frames hold placeholders."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import snapshot, testing


def test_strip_restricted_oracle_a_restricted_column_is_dropped_under_its_bare_name_and_under_its_full_id():
    """halvaro.core.access.strip_restricted: for a role without restricted access every column of the restricted list is dropped, whether the header is the bare name, 'table.column' or the full 'source.table.column'
    id; other columns, also names that contain a restricted name, stay; a role with restricted access gets the frame back unchanged."""
    restricted = snapshot.load()["restricted_columns"]
    assert len(restricted) >= 2
    bare = [c.split(".")[-1] for c in restricted]
    qualified = [".".join(c.split(".")[-2:]) for c in restricted]
    frame = pd.DataFrame({**{c: [1.0] for c in restricted}, **{b: [1.0] for b in bare}, **{q: [1.0] for q in qualified}, "team_key": ["TEAM-001"], bare[0] + "_band": [1.0]})
    plain = core.Context(stage="day1", role="mcp_people")
    out = core.strip_restricted(frame, plain)
    assert list(out.columns) == ["team_key", bare[0] + "_band"], "full ids and bare names go, the rest stays in order"
    hr = core.Context(stage="day1", role="mcp_people_hr", restricted_ok=True)
    pd.testing.assert_frame_equal(core.strip_restricted(frame, hr), frame)
    assert list(frame.columns)[:len(restricted)] == restricted, "the input is not changed"


def _call(frame):
    return lambda frames, as_of: frames["t"]


def test_asof_stable_oracle_a_column_that_exists_in_one_result_only_is_a_difference():
    """halvaro.core.testing.asof_stable: the same rows with an extra column in the later release, or with a column missing there, raise AssertionError naming the column (the common columns were compared
    and the rest ignored); identical results still pass and the allowed keys still excuse rows."""
    base = pd.DataFrame({"k": ["A", "B"], "v": [1, 2]})
    when = dt.date(2026, 1, 1)
    assert testing.asof_stable(_call(base), {"t": base}, {"t": base.copy()}, when, key="k") is True
    with pytest.raises(AssertionError, match=r"different columns.*\['new'\]"):
        testing.asof_stable(_call(base), {"t": base}, {"t": base.assign(new=[5, 6])}, when, key="k")
    with pytest.raises(AssertionError, match=r"different columns.*\['v'\]"):
        testing.asof_stable(_call(base), {"t": base}, {"t": base.drop(columns="v")}, when, key="k")
    changed = base.assign(v=[1, 9])
    assert testing.asof_stable(_call(base), {"t": base}, {"t": changed}, when, key="k", allowed_keys=["B"]) is True


@pytest.mark.parametrize("counts, refused", [([5, None, 4], 1), ([None, None], 2), ([5, 6, 7], 0), ([2, None, 3, None], 3)])
def test_assert_aggregate_oracle_a_group_without_a_count_is_too_small(counts, refused):
    """halvaro.core.access.assert_aggregate: with min_group a group whose count is missing is counted with the groups that are too small and the refusal says so (it passed before); a group exactly at
    the minimum passes; the number named equals the number of groups below the minimum or without a count."""
    frame = pd.DataFrame({"dep_key": [f"DEP-{i:02d}" for i in range(len(counts))], "n": counts, "base_salary": [1.0] * len(counts)})
    if refused:
        with pytest.raises(core.AggregateRefusal, match=rf"^{refused} groups have fewer than 3 people or no count"):
            core.assert_aggregate(frame, "base_salary", min_group=3, count_column="n")
    else:
        core.assert_aggregate(frame, "base_salary", min_group=3, count_column="n")
    ok = pd.DataFrame({"dep_key": ["DEP-01"], "n": [3], "base_salary": [1.0]})
    core.assert_aggregate(ok, "base_salary", min_group=3, count_column="n")
