"""Oracle of halvaro.core.money.from_cents (lane L1): hand worked cents, a round trip with to_cents, nulls that stay missing, and the baseline invoice amounts."""
import warnings

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def test_from_cents_oracle_hand_worked_cents():
    """halvaro.core.money.from_cents: whole cents become amounts with two decimals, written out by hand, for positive, negative and zero values and for a Python list, an array and a scalar."""
    cents = [0, 1, 99, 100, 12345, -5, -12345, 100000001]
    amounts = [0.0, 0.01, 0.99, 1.0, 123.45, -0.05, -123.45, 1000000.01]
    assert core.from_cents(np.array(cents)).tolist() == amounts
    assert core.from_cents(cents).tolist() == amounts
    assert core.from_cents(pd.Series(cents)).tolist() == amounts
    assert float(core.from_cents(12345)) == 123.45 and float(core.from_cents(-5)) == -0.05


def test_from_cents_oracle_fractional_cents_are_cut_toward_zero_and_text_is_refused():
    """halvaro.core.money.from_cents: a value that is not a whole number of cents is cut toward zero (100.7 is one euro, -100.7 minus one euro, -0.4 is zero and not minus zero), as before the fix;
    text that is not a whole number is refused with ValueError, not converted."""
    out = core.from_cents(pd.Series([100.7, -100.7, -0.4, 0.4]))
    assert out.tolist() == [1.0, -1.0, 0.0, 0.0] and not np.signbit(out[out == 0]).any(), "no negative zero"
    for text in (["1.5"], ["nan"]):
        with pytest.raises(ValueError):
            core.from_cents(text)


def test_from_cents_oracle_round_trip_with_to_cents_and_index_kept():
    """halvaro.core.money.from_cents: to_cents of the result is the cents we started with for 20000 random values, the index of a Series is kept and the input is not changed."""
    rng = np.random.default_rng(7)
    c = rng.integers(-10**12, 10**12, 20000)
    assert (core.to_cents(core.from_cents(c)) == c).all()
    s = pd.Series(c[:5], index=list("abcde"))
    before = s.copy()
    out = core.from_cents(s)
    assert out.index.tolist() == list("abcde") and out.tolist() == [v / 100 for v in c[:5].tolist()]
    pd.testing.assert_series_equal(s, before)


@pytest.mark.parametrize("make", [
    lambda: pd.Series([100, None, 5]),                                  # float with NaN
    lambda: pd.Series([100, pd.NA, 5], dtype="Int64"),                  # nullable integer
    lambda: pd.Series([100, None, 5], dtype=object),                    # object with None
    lambda: pd.Series([100, pd.NA, 5], dtype=object),                   # object with pd.NA
    lambda: [100, None, 5],                                              # list with None
    lambda: np.array([100.0, np.nan, 5.0]),                             # float array
])
def test_from_cents_oracle_a_missing_value_stays_missing_and_the_rest_is_exact(make):
    """halvaro.core.money.from_cents: a null in the cents is NaN in the amount, the other values are cents divided by 100, and no numpy warning is raised for the cast."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = np.asarray(core.from_cents(make()), dtype=float)
    assert np.isnan(out[1]) and out[0] == 1.0 and out[2] == 0.05
