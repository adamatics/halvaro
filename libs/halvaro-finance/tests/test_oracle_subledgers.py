"""Oracle tests of subledgers.customer_exposure: hand worked customers at the fixed rates read through the fact ids, and baseline invoices summed per customer with exact decimals."""
import math
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
FX_EUR, FX_SEK = "world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed"
COLS = ["cus_key", "credit_limit", "limit_currency", "limit_dkk", "open_dkk", "utilisation", "over_limit"]


def _rates():
    eur, sek = fact(FX_EUR), fact(FX_SEK)
    msg = f"{FX_EUR} read as {eur.value} ({eur.status}), {FX_SEK} read as {sek.value} ({sek.status})"
    return {"DKK": Decimal(1), "EUR": Decimal(repr(float(eur.value))), "SEK": Decimal(repr(float(sek.value)))}, msg


def _dkk(amount, currency, rates) -> Decimal:
    """One amount in DKK at the fixed rate, exact decimals, rounded to the cent with ties away from zero."""
    return (Decimal(repr(float(amount))) * rates[currency]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _items(rows):
    """rows: (cus_key, open_amount, currency)."""
    return pd.DataFrame({"le_key": "LE-01", "cus_key": [r[0] for r in rows], "open_amount": [r[1] for r in rows], "currency": [r[2] for r in rows]})


def _customers(rows):
    """rows: (cus_key, credit_limit, currency)."""
    return pd.DataFrame({"cus_key": [r[0] for r in rows], "credit_limit": [r[1] for r in rows], "currency": [r[2] for r in rows]})


def test_oracle_customer_exposure_hand_customers_against_their_limits():
    """route: hand worked customers, the open amounts and limits converted with exact decimals at the rates read through the fact ids, over_limit written out by hand per customer."""
    rates, msg = _rates()
    cust = _customers([("C8", 10.0, "EUR"), ("C3", 5000.0, "SEK"), ("C1", 1000.0, "DKK"), ("C7", 1000.0, "DKK"), ("C2", 100.0, "EUR"), ("C6", 100.0, "EUR"), ("C5", 0.0, "DKK"), ("C4", np.nan, "DKK")])
    items = _items([("C1", 700.0, "DKK"), ("C2", 50.0, "EUR"), ("C3", 4000.0, "SEK"), ("C1", 500.0, "DKK"), (None, 7.0, "DKK"), ("C7", 400.0, "DKK"), ("C3", 100.0, "EUR"), ("C4", 100.0, "DKK"),
                    ("C1", -150.0, "DKK"), ("C2", 30.0, "EUR"), ("C5", 10.0, "DKK"), ("C7", 600.0, "DKK"), ("C8", 0.05, "EUR"), ("C8", 0.05, "EUR")])
    kept = (items.copy(deep=True), cust.copy(deep=True))
    r = fin.customer_exposure(items, cust, context=M12)
    assert list(r.columns) == COLS and r.cus_key.tolist() == ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"], f"one row per customer, sorted; {msg}"
    v = r.set_index("cus_key")
    want_open = {"C1": Decimal("1050.00"), "C2": _dkk(50, "EUR", rates) + _dkk(30, "EUR", rates), "C3": _dkk(4000, "SEK", rates) + _dkk(100, "EUR", rates), "C4": Decimal("100.00"),
                 "C5": Decimal("10.00"), "C6": Decimal("0.00"), "C7": Decimal("1000.00"), "C8": _dkk(0.05, "EUR", rates) * 2}
    want_limit = {"C1": Decimal("1000.00"), "C2": _dkk(100, "EUR", rates), "C3": _dkk(5000, "SEK", rates), "C5": Decimal("0.00"), "C6": _dkk(100, "EUR", rates), "C7": Decimal("1000.00"), "C8": _dkk(10, "EUR", rates)}
    for k, x in want_open.items():
        assert abs(v.loc[k, "open_dkk"] - float(x)) < 0.0001, f"{k} open: {msg}"
    for k in v.index:
        if k in want_limit:
            assert abs(v.loc[k, "limit_dkk"] - float(want_limit[k])) < 0.0001, f"{k} limit: {msg}"
        else:
            assert math.isnan(v.loc[k, "limit_dkk"]), f"{k} has no limit: {msg}"
    assert v.over_limit.tolist() == [True, False, True, False, True, False, False, False], f"C1 1050 over 1000; C2 80 EUR under 100 EUR; C3 over; C4 no limit; C5 10 over a limit of 0; C6 nothing open; C7 equal to the limit; C8 under: {msg}"
    assert v.over_limit.dtype == bool, "yes or no, never missing"
    assert abs(v.loc["C1", "utilisation"] - 1.05) < 1e-12 and abs(v.loc["C7", "utilisation"] - 1.0) < 1e-12 and v.loc["C6", "utilisation"] == 0.0
    assert abs(v.loc["C2", "utilisation"] - float(want_open["C2"] / want_limit["C2"])) < 1e-12, msg
    assert v.loc[["C4", "C5"], "utilisation"].isna().all(), "no limit and a limit of zero give no utilisation"
    assert v.credit_limit.dropna().to_dict() == {"C8": 10.0, "C3": 5000.0, "C1": 1000.0, "C7": 1000.0, "C2": 100.0, "C6": 100.0, "C5": 0.0} and v.limit_currency.to_dict() == {
        "C1": "DKK", "C2": "EUR", "C3": "SEK", "C4": "DKK", "C5": "DKK", "C6": "EUR", "C7": "DKK", "C8": "EUR"}, "the limit is returned as stored"
    pd.testing.assert_frame_equal(items, kept[0])
    pd.testing.assert_frame_equal(cust, kept[1])


def test_oracle_customer_exposure_hand_refusals_and_an_empty_item_frame():
    """route: hand frames: a customer with open items that crm does not have, a repeated customer, a null amount and no items at all."""
    cust = _customers([("C1", 100.0, "DKK"), ("C2", 50.0, "DKK")])
    none = fin.customer_exposure(_items([]).astype({"open_amount": float}), cust, context=M12)
    assert none.cus_key.tolist() == ["C1", "C2"] and none.open_dkk.tolist() == [0.0, 0.0] and none.over_limit.tolist() == [False, False] and none.utilisation.tolist() == [0.0, 0.0]
    with pytest.raises(FrameError, match="not in crm.customer.*C9"):
        fin.customer_exposure(_items([("C9", 1.0, "DKK")]), cust, context=M12)
    with pytest.raises(FrameError, match="duplicate cus_key"):
        fin.customer_exposure(_items([("C1", 1.0, "DKK")]), pd.concat([cust, cust.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="null"):
        fin.customer_exposure(_items([("C1", np.nan, "DKK")]), cust, context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        fin.customer_exposure(_items([("C1", 1.0, "DKK")]).drop(columns="currency"), cust, context=M12)
