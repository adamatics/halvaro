"""Oracle of halvaro.core.money.to_cents (lane P1): hand worked amounts, the round trip with from_cents, and the refusal of nulls and infinities that used to turn into the smallest
64 bit integer."""
import warnings

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def test_to_cents_oracle_hand_worked_amounts_and_the_round_trip_with_from_cents():
    """halvaro.core.money.to_cents: amounts with two decimals become whole cents, written out by hand, for a list, an array, a Series (index kept) and a scalar; a tie goes to the even cent as the
    docstring says; to_cents of from_cents is the cents we started with for 20000 random values; the input is not changed."""
    amounts = [0.0, 0.01, 0.99, 1.0, 123.45, -0.05, -123.45, 1000000.01]
    cents = [0, 1, 99, 100, 12345, -5, -12345, 100000001]
    assert core.to_cents(np.array(amounts)).tolist() == core.to_cents(amounts).tolist() == cents
    s = pd.Series(amounts[:3], index=list("abc"))
    before = s.copy()
    out = core.to_cents(s)
    assert out.to_dict() == {"a": 0, "b": 1, "c": 99} and out.dtype == np.int64
    pd.testing.assert_series_equal(s, before)
    assert int(core.to_cents(12.34)) == 1234 and int(core.to_cents(-0.004)) == 0
    assert core.to_cents([0.125, 0.135, 0.145, 2.5e-3]).tolist() == [12, 14, 14, 0], "0.125 is exactly 12.5 cents and goes to the even cent 12; 0.135 and 0.145 are not exact in binary and give 14; a quarter cent gives 0"
    rng = np.random.default_rng(9)
    c = rng.integers(-10**12, 10**12, 20000)
    assert (core.to_cents(core.from_cents(c)) == c).all()


@pytest.mark.parametrize("make, count", [
    (lambda: pd.Series([1.5, None, np.nan]), 2),                       # float with two nulls
    (lambda: pd.Series([1, pd.NA], dtype="Int64"), 1),                  # nullable integer
    (lambda: np.array([None, 1, None], dtype=object), 2),               # object with None
    (lambda: [1.0, float("nan")], 1),                                   # list
    (lambda: float("nan"), 1),                                          # scalar
])
def test_to_cents_oracle_a_null_is_refused_with_its_count_never_turned_into_a_number(make, count):
    """halvaro.core.money.to_cents: a null amount (NaN, None, pd.NA) raises FrameError that names how many nulls there are; no numpy warning, no result (before: the smallest 64 bit integer)."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(core.FrameError, match=rf"got {count} null amount"):
            core.to_cents(make())


def test_to_cents_oracle_an_infinite_amount_is_refused_and_a_clean_series_still_works():
    """halvaro.core.money.to_cents: plus and minus infinity raise FrameError naming the count; a frame column without nulls is converted as before."""
    with pytest.raises(core.FrameError, match="got 2 infinite amount"):
        core.to_cents(pd.Series([1.0, float("inf"), float("-inf")]))
    assert core.to_cents(pd.Series([1.0, 2.0])).tolist() == [100, 200]


def test_to_cents_oracle_an_amount_whose_cents_do_not_fit_in_64_bits_is_refused_and_the_largest_fitting_one_is_kept():
    """halvaro.core.money.to_cents: 9.2e16 and more has no cents in a 64 bit integer (it came out as the smallest integer before) and raises FrameError naming how many amounts; 9.0e16 gives 9000000000000000000 cents,
    by hand; a frame with a null and an infinity names the nulls first."""
    assert core.to_cents([9.0e16, -9.0e16]).tolist() == [9_000_000_000_000_000_000, -9_000_000_000_000_000_000]
    with pytest.raises(core.FrameError, match="got 2 amount"):
        core.to_cents([1e17, -1e30, 5.0])
    with pytest.raises(core.FrameError, match="got 1 amount"):
        core.to_cents([9.3e16]), "9.3e16 is 9.3e18 cents, above the largest 64 bit integer (9.22e18)"
    with pytest.raises(core.FrameError, match="got 1 null amount"):
        core.to_cents([float("nan"), float("inf")])
