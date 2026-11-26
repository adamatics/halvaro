"""C3: money basics, converted against the generator's own conv."""

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def test_to_cents_and_from_cents():
    assert core.to_cents([1.005, 2.5, -0.125, 0.0]).tolist() == [100, 250, -12, 0], "rint of x100 (half to even on the float value)"
    assert core.from_cents(np.array([100, -5, 12345])).tolist() == [1.0, -0.05, 123.45]
    s = pd.Series([1.5, 2.25], index=[7, 9])
    assert core.to_cents(s).index.tolist() == [7, 9] and core.from_cents(core.to_cents(s)).tolist() == [1.5, 2.25]


def test_rdiv_rounds_half_away_from_zero():
    assert core.rdiv([5, -5, 4, -4, 6, -6, 0], 2).tolist() == [3, -3, 2, -2, 3, -3, 0]
    assert core.rdiv([1, -1, 2, -2], 3).tolist() == [0, 0, 1, -1] and core.rdiv([3, -3], 6).tolist() == [1, -1]


def test_convert_group_pay_and_booking():
    assert core.convert([10000], "EUR", "DKK", basis="group_pay").tolist() == [74600]
    assert core.convert([74600], "DKK", "EUR", basis="group_pay").tolist() == [10000]
    assert core.convert([100], "SEK", "DKK", basis="booking").tolist() == [67] and core.convert([67], "DKK", "SEK", basis="booking").tolist() == [100]
    assert core.convert([123], "DKK", "DKK", basis="group_pay").tolist() == [123]
    assert core.convert(pd.Series([100], index=["x"]), "EUR", "DKK", basis="booking").index.tolist() == ["x"]


def test_convert_refuses_missing_unknown_and_unavailable_bases():
    with pytest.raises(TypeError):
        core.convert([1], "EUR", "DKK")
    for kw in ({"basis": "daily"}, {"basis": "spot"}):
        with pytest.raises(core.BasisError):
            core.convert([1], "EUR", "DKK", **kw)
    with pytest.raises(core.BasisError, match="SEK"):
        core.convert([1], "SEK", "DKK", basis="group_pay")
    with pytest.raises(core.BasisError, match="USD"):
        core.convert([1], "USD", "DKK", basis="booking")
