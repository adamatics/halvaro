"""Oracle of halvaro.core.access.assert_aggregate (lane L1). The expected refusal comes from a plain loop over every value of every column and index level of a frame, group sizes come
from pandas over the baseline keys. The restricted column is only a name here: its frames hold the placeholder 1.0, never a value of the data."""
import re

import pandas as pd
import pyarrow as pa
import pytest

import halvaro.core as core

KEY = re.compile(r"EMP-[0-9]{6}")
PAY = "base_salary"


def _ref_person_keys(frame: pd.DataFrame) -> list:
    """Names of the columns and index levels in which at least one value, read as text, is an EMP key, found by looping over the values (columns by position, so duplicate names work)."""
    hits = []
    for i in range(frame.shape[1]):
        if any(KEY.fullmatch(str(v)) for v in frame.iloc[:, i].tolist()):
            hits.append(str(frame.columns[i]))
    for i, name in enumerate(frame.index.names):
        if any(KEY.fullmatch(str(v)) for v in frame.index.get_level_values(i).tolist()):
            hits.append(f"index {name if name else i}")
    return hits


class _Person:
    """An object that prints as a person key, as an ORM or a wrapper type would."""

    def __init__(self, n):
        self.n = n

    def __str__(self):
        return f"EMP-{self.n:06d}"


def _frame(**cols) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame({**cols, PAY: [1.0] * n})


CASES = {
    "clean groups": _frame(dep_key=["DEP-01", "DEP-02"]),
    "pure person key column": _frame(emp_key=["EMP-000001", "EMP-000002"]),
    "person keys and an empty string": _frame(emp_key=["EMP-000001", "", "EMP-000002"]),
    "person keys and other text": _frame(emp_key=["EMP-000001", "n/a", "EMP-000002"]),
    "person keys and missing values": _frame(emp_key=["EMP-000001", None, "EMP-000002"]),
    "one person key among project keys": _frame(key=["PRJ-000001", "EMP-000003", "PRJ-000002"]),
    "person keys in a string dtype column": _frame(emp_key=pd.array(["EMP-000001", "x"], dtype="string")),
    "person keys in a categorical column": _frame(emp_key=pd.Categorical(["EMP-000001", "EMP-000002"])),
    "person keys in an Arrow large string column": _frame(emp_key=pd.array(["EMP-000001", "n/a"], dtype=pd.ArrowDtype(pa.large_string()))),
    "objects that print as person keys": _frame(emp_key=[_Person(1), _Person(2)]),
    "person keys in a categorical index": _frame(dep_key=["DEP-01", "DEP-02"]).set_index(pd.CategoricalIndex(["EMP-000001", "EMP-000002"], name="emp_key")),
    "person key in a column beside a clean one with the same name": pd.concat([_frame(dep_key=["DEP-01", "DEP-02"]), pd.DataFrame({"dep_key": ["EMP-000001", "x"]})], axis=1),
    "numbers dates and booleans": _frame(n=[1, 2], when=pd.to_datetime(["2026-01-01", "2026-01-02"]), flag=[True, False]),
    "person keys in the index": _frame(dep_key=["DEP-01", "DEP-02"]).set_index(pd.Index(["EMP-000001", "EMP-000002"], name="emp_key")),
    "person keys in one level of a two level index": _frame(dep_key=["DEP-01", "DEP-02"]).set_index(pd.MultiIndex.from_tuples([("DEP-01", "EMP-000001"), ("DEP-02", "EMP-000002")])),
    "lower case and short keys are not person keys": _frame(key=["emp-000001", "EMP-1", "EMP-0000012"]),
    "other prefixes": _frame(key=["PRJ-000001", "CNT-000002", "SITE-01"]),
}


@pytest.mark.parametrize("name", list(CASES))
def test_assert_aggregate_oracle_refusal_equals_a_loop_over_every_value(name):
    """halvaro.core.access.assert_aggregate: the guard refuses exactly when a loop over all values of all columns and index levels finds an EMP key, and the refusal names those columns."""
    frame = CASES[name]
    before = frame.copy()
    hits = _ref_person_keys(frame)
    if hits:
        with pytest.raises(core.AggregateRefusal) as e:
            core.assert_aggregate(frame, PAY)
        assert all(h in str(e.value) for h in hits), (hits, str(e.value))
    else:
        core.assert_aggregate(frame, PAY)
    pd.testing.assert_frame_equal(frame, before)


def test_assert_aggregate_oracle_the_loop_itself_finds_what_the_cases_say():
    """The reference loop is pinned on its own: the cases above split as written by hand, so a loop that finds nothing cannot make every case pass."""
    refused = {n for n, f in CASES.items() if _ref_person_keys(f)}
    assert refused == {"pure person key column", "person keys and an empty string", "person keys and other text", "person keys and missing values",
                       "one person key among project keys", "person keys in the index", "person keys in one level of a two level index", "person keys in a string dtype column",
                       "person keys in a categorical column", "person keys in an Arrow large string column", "objects that print as person keys", "person keys in a categorical index",
                       "person key in a column beside a clean one with the same name"}


def test_assert_aggregate_oracle_missing_columns_are_frame_errors():
    """halvaro.core.access.assert_aggregate: a missing restricted column, a min_group without count_column and a count column that is not in the frame each raise FrameError."""
    ok = _frame(dep_key=["DEP-01"]).assign(n=[9])
    for kw in ({"restricted_column": "nope"}, {"min_group": 3}, {"min_group": 3, "count_column": "missing"}):
        with pytest.raises(core.FrameError):
            core.assert_aggregate(ok, **{"restricted_column": PAY, **kw})


def test_assert_aggregate_oracle_a_key_with_a_final_newline_is_still_a_person_key():
    """halvaro.core.access.assert_aggregate: the guard reads a key with a trailing newline as a person key (the safe direction: the pattern ends in `$`); written down so that a change to `fullmatch`
    is a decision and not an accident."""
    with pytest.raises(core.AggregateRefusal):
        core.assert_aggregate(_frame(emp_key=["EMP-000001\n", "x"]), PAY)


def test_mark_aggregate_oracle_wraps_a_clean_frame_and_refuses_what_assert_aggregate_refuses():
    """halvaro.core.access.mark_aggregate: a clean group frame comes back in a RestrictedAggregate that holds the same frame, the restricted column, the group columns as a tuple and min_group; a frame
    with person keys is refused as by assert_aggregate (this test is what the none line of the index relies on)."""
    groups = _frame(dep_key=["DEP-01", "DEP-02"]).assign(n=[9, 4])
    got = core.mark_aggregate(groups, PAY, ["dep_key"], min_group=3, count_column="n")
    assert isinstance(got, core.RestrictedAggregate) and got.frame is groups
    assert (got.restricted_column, got.group_columns, got.min_group) == (PAY, ("dep_key",), 3)
    with pytest.raises(core.AggregateRefusal):
        core.mark_aggregate(CASES["pure person key column"], PAY)
    with pytest.raises(core.AggregateRefusal, match="fewer than 5"):
        core.mark_aggregate(groups, PAY, ["dep_key"], min_group=5, count_column="n")
