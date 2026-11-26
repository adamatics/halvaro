"""Oracles of halvaro.core.money (lane L1). Expected sums come from pandas groupby over the baseline and from hand worked frames."""
import pandas as pd
import pytest

import halvaro.core as core


def test_guarded_sum_oracle_nulls_empty_groups_and_no_mutation():
    """halvaro.core.money.guarded_sum: null values are skipped, an all null group is 0, the input frame is not changed, a column name in `by` as text works."""
    df = pd.DataFrame({"currency": ["DKK", "DKK", "EUR", "EUR"], "g": ["a", "a", "b", "b"], "v": [1.5, None, None, None]})
    before = df.copy()
    out = core.guarded_sum(df, "v", by=["g"])
    assert out["g"].tolist() == ["a", "b"] and out["v"].tolist() == [1.5, 0.0]
    pd.testing.assert_frame_equal(df, before)
    assert core.guarded_sum(df, "v", by="g").equals(out)
    assert core.guarded_sum(df.iloc[:0], "v", by=["g"]).empty
    flat = pd.DataFrame({"currency": ["DKK"] * 3, "v": [1.5, 2.5, None]})
    assert core.guarded_sum(flat, "v")["v"].tolist() == [4.0], "without `by` the sum is one row, nulls skipped"
    assert core.guarded_sum(flat, "v", by="currency")["v"].tolist() == [4.0]
    own = pd.DataFrame({"kind": ["a", "a", "b"], "grp": ["x", "x", "x"], "v": [1.0, 2.0, 4.0]})
    with pytest.raises(core.SumGuardError, match="kind"):
        core.guarded_sum(own, "v", by="grp", guard="kind")
    assert core.guarded_sum(own, "v", by="kind", guard="kind")["v"].tolist() == [3.0, 4.0], "a guard column of the caller, grouped on it, gives one sum per value"
