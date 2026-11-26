"""Oracles of halvaro.core.keys (lane L1). The expected values are read from the baseline with pandas, from the data dictionary with csv or written by hand in the test; no library
function computes an expected value. Release tests skip without HALVARO_RELEASE_DIR."""
import pandas as pd
import pytest

import halvaro.core as core


def test_column_prefixes_unknown_column_is_refused():
    """halvaro.core.keys.column_prefixes: a column outside the dictionary raises FrameError instead of returning ()."""
    for bad in ("hr.employee.nope", "hr.nope.emp_key", "emp_key", ""):
        with pytest.raises(core.FrameError):
            core.column_prefixes(bad)


def test_check_key_column_oracle_hand_worked_classes():
    """halvaro.core.keys.check_key_column: null once per null row, each bad value once however often it repeats, classes by hand, allow_null drops the null rows."""
    df = pd.DataFrame({"k": ["EMP-000001", "EMP-000001", None, None, "emp-000002", "emp-000002", "ZZZ-000003", "PRJ-000004", "EMP-0000005", "BUD-2025", "BUD-25"]})
    v = core.check_key_column(df, "k", "hr.employment_term.manager_emp_key")
    got = sorted((r.key, r.rule) for r in v.itertuples())
    assert got == sorted([("", "null"), ("", "null"), ("emp-000002", "bad_format"), ("ZZZ-000003", "unknown_prefix"), ("PRJ-000004", "wrong_prefix"), ("EMP-0000005", "bad_format"),
                          ("BUD-2025", "wrong_prefix"), ("BUD-25", "bad_format")])
    assert len(core.check_key_column(df, "k", "hr.employment_term.manager_emp_key", allow_null=True)) == 6
    free = sorted((r.key, r.rule) for r in core.check_key_column(df, "k").itertuples())
    assert free == sorted([("", "null"), ("", "null"), ("emp-000002", "bad_format"), ("ZZZ-000003", "unknown_prefix"), ("EMP-0000005", "bad_format"), ("BUD-25", "bad_format")]), \
        "without a target the PRJ key and the natural label BUD-2025 are fine"
    with pytest.raises(core.FrameError):
        core.check_key_column(df, "missing")
    before = df.copy()
    core.check_key_column(df, "k", "hr.employment_term.manager_emp_key")
    pd.testing.assert_frame_equal(df, before)


def test_check_polymorphic_oracle_type_column_holds_the_prefix():
    """halvaro.core.keys.check_polymorphic: with mapping None the type column is the prefix; nulls in the key are skipped; the same pair is reported once."""
    df = pd.DataFrame({"t": ["EMP", "EMP", "PRJ", "CNT", "EMP"], "k": ["EMP-000001", "PRJ-000002", "PRJ-000003", None, "PRJ-000002"]})
    v = core.check_polymorphic(df, "k", "t")
    assert sorted((r.key, r.rule) for r in v.itertuples()) == [("PRJ-000002", "wrong_prefix")], "the pair (EMP, PRJ-000002) appears twice and is one violation; the null key is skipped"
