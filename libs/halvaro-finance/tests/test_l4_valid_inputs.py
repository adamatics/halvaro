"""Inputs the bodies accepted before the L4.3 checks still give the same numbers; only wrong input raises FrameError. Expected values are worked by hand from the documented rule."""
from decimal import Decimal

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
CTRY = {"LE-A": "DK"}


def _gross(overtime):
    return pd.DataFrame({"le_key": ["LE-A", "LE-A"], "cc_key": ["CC-1", "CC-2"], "period": "2026-01", "gross_salary": [1000.0, 2000.0], "overtime": overtime})


@pytest.mark.parametrize("overtime", [pd.Series([pd.NA, 5], dtype=object), pd.array([pd.NA, 5.0], dtype="Float64"), pd.Series([None, 5], dtype=object), [float("nan"), 5.0]])
def test_employer_oncosts_takes_a_null_overtime_as_zero(overtime):
    out = fin.employer_oncosts(_gross(overtime), country_of=CTRY, context=M12).value
    # DK pension 8 percent and social 1.2 percent: base 1000 and 2000 + 5; 80, 160.4 and 12, 24.06
    assert out["base_amount"].tolist() == [1000.0, 2005.0]
    assert out["employer_pension"].tolist() == [80.0, 160.4]
    assert out["employer_social"].tolist() == [12.0, 24.06]


def test_employer_oncosts_base_gross_never_reads_overtime():
    out = fin.employer_oncosts(_gross(["x", "y"]), country_of=CTRY, base="gross", context=M12).value
    assert out["base_amount"].tolist() == [1000.0, 2000.0]
    assert out["employer_pension"].tolist() == [80.0, 160.0]


def test_employer_oncosts_text_overtime_still_raises_under_gross_plus_overtime():
    with pytest.raises(FrameError, match="overtime"):
        fin.employer_oncosts(_gross(["x", 5.0]), country_of=CTRY, context=M12)


def _jl():
    rows = [("LE-01", "2025-01", "GL-6100", 100.0), ("LE-01", "2025-01", "GL-7900", -100.0), ("LE-01", "2025-01", "GL-6610", 90.0), ("LE-01", "2025-01", "GL-7910", -100.0)]
    return pd.DataFrame(rows, columns=["le_key", "period", "gl_key", "amount"])


def test_labour_absorption_accepts_a_decimal_share():
    # service 90 of 100 absorbed: the rest 10 is 10 percent of 100, inside 20 percent, outside 5 percent
    assert fin.labour_absorption_check(_jl(), max_warranty_share=Decimal("0.2"), context=M12).empty
    r = fin.labour_absorption_check(_jl(), max_warranty_share=Decimal("0.05"), context=M12)
    assert r["rule"].tolist() == ["service_labour_not_absorbed"]


@pytest.mark.parametrize("share", ["0.2", None])
def test_labour_absorption_refuses_a_share_that_is_not_a_number(share):
    with pytest.raises(FrameError, match="max_warranty_share"):
        fin.labour_absorption_check(_jl(), max_warranty_share=share, context=M12)


def test_cost_per_metre_null_route_length_is_a_frame_error():
    cs = pd.DataFrame({"prj_key": ["PRJ-A"], "legacy": [False]})
    cb = pd.DataFrame({"prj_key": ["PRJ-A"], "period": ["2026-01"], "cst_key": ["CST-1"], "currency": ["DKK"], "actual_amount": [500.0], "incurred_in_period": [500.0], "estimate_amount": [600.0]})
    ok = fin.cost_per_metre_by_cost_code(cs, cb, pd.DataFrame({"prj_key": ["PRJ-A"], "route_length_m": [100.0]}), context=M12)
    assert ok.per_project["per_metre"].tolist() == [5.0]
    with pytest.raises(FrameError, match="null"):
        fin.cost_per_metre_by_cost_code(cs, cb, pd.DataFrame({"prj_key": ["PRJ-A"], "route_length_m": pd.Series([pd.NA], dtype=object)}), context=M12)


def test_a_null_in_the_prior_year_column_is_allowed_and_a_text_is_named_even_after_a_null():
    """statements_check: the prior year amount may be null (pd.NA too); a text next to a null is the value that the message names."""
    import pandas as pd
    import pytest
    from halvaro.core import FrameError
    from halvaro.finance import _util
    frame = pd.DataFrame({"amount": [1.0, 2.0], "prior_year_amount": [pd.NA, 3.0]}, dtype=object)
    _util._numeric(frame, ["amount", "prior_year_amount"], "t", allow_null=["prior_year_amount"])               # no error
    with pytest.raises(FrameError, match="must hold numbers, not 'abc'"):
        _util._numeric(pd.DataFrame({"prior_year_amount": [None, "abc"]}), ["prior_year_amount"], "t")
    with pytest.raises(FrameError, match="has a null"):
        _util._numeric(pd.DataFrame({"amount": [1.0, pd.NA]}, dtype=object), ["amount"], "t")
