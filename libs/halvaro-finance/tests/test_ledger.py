"""Ledger functions, part a: sign, DKK, manual journals. Synthetic frames for the contract, the baseline release for the identities (T18)."""

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import BasisError, Context, FrameError, StageRefusal, fact

CTX = Context(stage="month3", role="r")


# ---- synthetic frames


def _gl():
    return pd.DataFrame({"gl_key": ["GL-1000", "GL-2000", "GL-3300", "GL-4000", "GL-5000"], "statement": ["BS", "BS", "BS", "IS", "IS"], "normal_balance": ["debit", "credit", "credit", "credit", "debit"],
                         "dk_statutory_map": ["DK-A", "DK-B", "DK-C", "DK-D", "DK-E"], "de_statutory_map": ["DE-A", "DE-B", "DE-C", "DE-D", "DE-E"]})


# ---- natural sign


def test_natural_sign_flips_credit_accounts_only_and_refuses_unknown_accounts():
    gl = _gl()
    f = pd.DataFrame({"gl_key": ["GL-1000", "GL-4000", "GL-2000", "GL-5000"], "amount": [10.0, -20.0, -5.0, 7.0], "closing_balance": [1.0, 2.0, 3.0, 4.0]}, index=[7, 8, 9, 10])
    n = fin.to_natural_sign(f, gl, context=CTX)
    assert n.tolist() == [10.0, 20.0, 5.0, 7.0] and n.index.tolist() == [7, 8, 9, 10] and n.name == "amount"
    assert fin.to_natural_sign(f, gl, column="closing_balance", context=CTX).tolist() == [1.0, -2.0, -3.0, 4.0]
    assert f.amount.tolist() == [10.0, -20.0, -5.0, 7.0], "the input is not changed"
    with pytest.raises(FrameError, match="not in finance.gl_account.*GL-9"):
        fin.to_natural_sign(f.assign(gl_key="GL-9"), gl, context=CTX)
    with pytest.raises(FrameError, match="neither debit nor credit"):
        fin.to_natural_sign(f, gl.assign(normal_balance="both"), context=CTX)
    with pytest.raises(FrameError, match="duplicate gl_key"):
        fin.to_natural_sign(f, pd.concat([gl, gl]), context=CTX)
    assert fin.to_natural_sign(f.iloc[:0], gl, context=CTX).empty


# ---- DKK


def test_booking_basis_rounds_half_away_from_zero_and_dkk_is_identity():
    eur = fact("world.fx_eur_dkk_fixed").value
    amt = pd.Series([100.0, -0.07, 0.07, 1234.56, 0.0], index=list("abcde"))
    out = fin.dkk_amount(amt, pd.Series(["EUR"] * 5, index=amt.index), basis="booking", context=CTX)
    assert out.index.tolist() == list("abcde") and out.tolist() == [round(100 * eur, 2), -0.52, 0.52, round(1234.56 * eur, 2), 0.0]
    assert fin.dkk_amount(amt, pd.Series(["DKK"] * 5, index=amt.index), basis="booking", context=CTX).tolist() == amt.tolist()
    mixed = fin.dkk_amount(pd.Series([1.0, 1.0]), pd.Series(["EUR", "DKK"]), basis="booking", context=CTX)
    assert mixed.tolist() == [eur, 1.0]
    with pytest.raises(BasisError, match="XXX"):
        fin.dkk_amount(pd.Series([1.0]), pd.Series(["XXX"]), basis="booking", context=CTX)


def test_booking_rate_frame_must_agree_with_the_fixed_rates_and_basis_rules():
    eur = fact("world.fx_eur_dkk_fixed").value
    fx = pd.DataFrame({"currency": ["EUR", "EUR"], "rate_date": ["2023-01-02", "2023-01-03"], "rate": [7.4601, 7.4602], "quote_currency": "DKK", "booking_rate": [eur, eur]})
    assert fin.dkk_amount(pd.Series([10.0]), pd.Series(["EUR"]), basis="booking", fx_rate=fx, context=CTX).tolist() == [round(10 * eur, 2)]
    with pytest.raises(FrameError, match="differs from the fixed booking rate"):
        fin.dkk_amount(pd.Series([10.0]), pd.Series(["EUR"]), basis="booking", fx_rate=fx.assign(booking_rate=[7.5, 7.5]), context=CTX)
    with pytest.raises(BasisError, match="group statements"):
        fin.dkk_amount(pd.Series([10.0]), pd.Series(["EUR"]), basis="daily", fx_rate=fx, on=pd.Series(["2023-01-05"]), group=True, context=CTX)
    with pytest.raises(BasisError, match="not available"):
        fin.dkk_amount(pd.Series([10.0]), pd.Series(["EUR"]), basis="spot", context=CTX)
    with pytest.raises(FrameError, match="same length"):
        fin.dkk_amount(pd.Series([10.0, 1.0]), pd.Series(["EUR"]), basis="booking", context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        fin.dkk_amount(pd.Series([None, 1.0]), pd.Series(["EUR", "EUR"]), basis="booking", context=CTX)


def test_daily_basis_takes_the_latest_rate_on_or_before_the_date():
    fx = pd.DataFrame({"currency": ["EUR", "EUR", "EUR"], "rate_date": ["2023-01-02", "2023-01-05", "2023-01-09"], "rate": [7.0, 8.0, 9.0], "quote_currency": "DKK", "booking_rate": 7.46})
    amt, cur = pd.Series([10.0, 10.0, 10.0, 10.0, -0.05]), pd.Series(["EUR", "EUR", "EUR", "DKK", "EUR"])
    on = pd.Series(["2023-01-02", "2023-01-08", "2023-01-09", "2020-01-01", "2023-01-05"])
    assert fin.dkk_amount(amt, cur, basis="daily", fx_rate=fx, on=on, context=CTX).tolist() == [70.0, 80.0, 90.0, 10.0, -0.4]
    with pytest.raises(FrameError, match="no daily rate on or before"):
        fin.dkk_amount(pd.Series([1.0]), pd.Series(["EUR"]), basis="daily", fx_rate=fx, on=pd.Series(["2023-01-01"]), context=CTX)
    with pytest.raises(FrameError, match="needs fx_rate"):
        fin.dkk_amount(pd.Series([1.0]), pd.Series(["EUR"]), basis="daily", context=CTX)
    with pytest.raises(FrameError, match="other than DKK"):
        fin.dkk_amount(pd.Series([1.0]), pd.Series(["EUR"]), basis="daily", fx_rate=fx.assign(quote_currency="EUR"), on=pd.Series(["2023-01-05"]), context=CTX)


def test_manual_journals_filters_and_requires_manual_headers():
    jl = pd.DataFrame({"le_key": "LE-02", "journal_no": [7, 7, 8, 8], "line_no": [1, 2, 1, 2], "gl_key": ["GL-5190", "GL-2100", "GL-5190", "GL-2100"], "prj_key": ["PRJ-000001", "PRJ-000001", "PRJ-000002", "PRJ-000002"],
                       "amount": [5.0, -5.0, 6.0, -6.0], "amount_dkk": [37.3, -37.3, 44.76, -44.76], "currency": "EUR"})
    jh = pd.DataFrame({"le_key": "LE-02", "journal_no": [7, 8], "source": ["manual", "ar"], "posting_date": ["2025-12-18", "2025-12-19"], "description": ["write-down", "invoice"]})
    allm = fin.manual_journals(jh, jl, context=CTX)
    assert allm.journal_no.tolist() == [7, 7] and list(allm.columns) == ["le_key", "journal_no", "line_no", "posting_date", "description", "gl_key", "prj_key", "currency", "amount", "amount_dkk"]
    assert fin.manual_journals(jh, jl, gl_key="GL-5190", context=CTX).amount.tolist() == [5.0]
    assert fin.manual_journals(jh, jl, prj_key="PRJ-000002", context=CTX).empty, "journal 8 is not manual"
    assert fin.manual_journals(jh, jl, gl_key="GL-2100", prj_key="PRJ-000001", context=CTX).amount.tolist() == [-5.0]
    with pytest.raises(FrameError, match="manual journal listed twice"):
        fin.manual_journals(pd.concat([jh, jh.iloc[:1]]), jl, context=CTX)
    with pytest.raises(FrameError, match="lacks column.*description"):
        fin.manual_journals(jh.drop(columns="description"), jl, context=CTX)


# ---- stage and registry


def test_every_function_refuses_day1_and_names_finance():
    gl = _gl()
    day1 = Context(stage="day1", role="r")
    jl = pd.DataFrame({"gl_key": ["GL-1000"], "amount": [1.0], "currency": ["DKK"]})
    h = pd.DataFrame({"le_key": ["LE-01"], "journal_no": [1], "source": ["manual"], "posting_date": ["2025-01-01"], "description": ["d"]})
    ln = pd.DataFrame({"le_key": ["LE-01"], "journal_no": [1], "line_no": [1], "gl_key": ["GL-1000"], "prj_key": [None], "amount": [1.0], "amount_dkk": [1.0], "currency": ["DKK"]})
    calls = [lambda: fin.to_natural_sign(jl, gl, context=day1), lambda: fin.dkk_amount(jl.amount, jl.currency, basis="booking", context=day1),
             lambda: fin.manual_journals(h, ln, context=day1)]
    for c in calls:
        with pytest.raises(StageRefusal, match="finance"):
            c()
    with pytest.raises(TypeError):
        fin.to_natural_sign(jl, gl)


# ---- survivors of the mutation review


def test_daily_rounding_ties_go_away_from_zero_and_inputs_are_checked():
    fx = pd.DataFrame({"currency": ["EUR"], "rate_date": pd.to_datetime(["2023-01-02"]), "rate": [6.5], "quote_currency": "DKK", "booking_rate": 7.46})
    on = pd.Series(pd.to_datetime(["2023-01-05", "2023-01-05"]))
    r = fin.dkk_amount(pd.Series([0.05, -0.05]), pd.Series(["EUR", "EUR"]), basis="daily", fx_rate=fx, on=on, context=CTX)
    assert r.tolist() == [0.33, -0.33], "32.5 cents rounds to 33 away from zero, not to 32"
    with pytest.raises(FrameError, match="one date per amount"):
        fin.dkk_amount(pd.Series([0.05, 0.05]), pd.Series(["EUR", "EUR"]), basis="daily", fx_rate=fx, on=on.iloc[:1], context=CTX)
    two = pd.DataFrame({"currency": ["EUR", "EUR"], "booking_rate": [fact("world.fx_eur_dkk_fixed").value, 7.5]})
    with pytest.raises(FrameError, match="differs from the fixed booking rate"):
        fin.dkk_amount(pd.Series([1.0]), pd.Series(["EUR"]), basis="booking", fx_rate=two, context=CTX)
    with pytest.raises(FrameError, match="must be a DataFrame"):
        fin.to_natural_sign([1, 2], _gl(), context=CTX)


def test_manual_journals_are_sorted_with_a_default_index():
    h = pd.DataFrame({"le_key": ["LE-02", "LE-01", "LE-01"], "journal_no": [5, 9, 3], "source": "manual", "posting_date": ["2025-01-01"] * 3, "description": "d"})
    ln = pd.DataFrame({"le_key": ["LE-02", "LE-01", "LE-01", "LE-01"], "journal_no": [5, 9, 3, 3], "line_no": [1, 1, 2, 1], "gl_key": "GL-1000", "prj_key": None, "amount": 1.0, "amount_dkk": 1.0,
                       "currency": "DKK"}, index=[40, 30, 20, 10])
    m = fin.manual_journals(h, ln, context=CTX)
    assert m[["le_key", "journal_no", "line_no"]].values.tolist() == [["LE-01", 3, 1], ["LE-01", 3, 2], ["LE-01", 9, 1], ["LE-02", 5, 1]] and m.index.tolist() == [0, 1, 2, 3]
