"""Oracle tests of halvaro.esg.activity: check_meters, energy_cost, energy_use_mwh.

Each expected value is derived without calling the function under test: hand frames with the numbers written in the test, a Decimal or plain python reading of the baseline release, a property.
"""
import math
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
TABLE = "energy-esg.energy_meter"


def _meters(rows):
    return pd.DataFrame(rows, columns=["mtr_key", "carrier", "scope", "unit"])


# ---- check_meters


def test_oracle_check_meters_one_violation_per_rule():
    """route: hand frame in which every meter breaks at most the rules named next to it, the expected (key, rule) pairs written out."""
    m = _meters([("A", "electricity", 2, "kWh"), ("B", "diesel", 1, "l"), ("C", "natural_gas", 1, "kWh"), ("D", "petrol", 1, "l"), ("E", "district_heat", 2, "MWh"),
                 ("U", "diesel", 1, "kWh"),                   # unit only
                 ("S", "electricity", 1, "kWh"),               # scope only
                 ("X", "coal", 1, "t"),                        # unknown carrier, and nothing else is said about it
                 ("UU", "petrol", 2, "MWh"),                   # unit and scope
                 ("A", "electricity", 2, "kWh"),               # second listing of A
                 ("T", "diesel", 1, "l"), ("T", "diesel", 1, "l"), ("T", "diesel", 1, "l")])     # three listings of T
    before = m.copy(deep=True)
    r = esg.check_meters(m, context=M12)
    assert list(r.columns) == ["table", "key", "rule", "detail"]
    assert set(r.table) == {TABLE}
    assert list(zip(r.key, r.rule)) == [("A", "duplicate_meter"), ("S", "scope"), ("T", "duplicate_meter"), ("T", "duplicate_meter"), ("U", "unit"), ("UU", "scope"), ("UU", "unit"), ("X", "unknown_carrier")]
    d = dict(zip(zip(r.key, r.rule), r.detail))
    assert "diesel" in d[("U", "unit")] and " l," in d[("U", "unit")] and "kWh" in d[("U", "unit")], d[("U", "unit")]
    assert "electricity" in d[("S", "scope")] and "scope 2" in d[("S", "scope")] and "says 1" in d[("S", "scope")], d[("S", "scope")]
    assert "coal" in d[("X", "unknown_carrier")]
    pd.testing.assert_frame_equal(m, before)                  # the input is not changed


def test_oracle_check_meters_clean_list_and_the_maps_are_keywords():
    """route: hand frames; a list that follows the maps gives no row, and a map given by keyword replaces the rule for the carrier it names."""
    ok = _meters([("A", "electricity", 2, "kWh"), ("B", "diesel", 1, "l"), ("C", "natural_gas", 1, "kWh"), ("D", "petrol", 1, "l"), ("E", "district_heat", 2, "MWh")])
    clean = esg.check_meters(ok, context=M12)
    assert clean.empty and list(clean.columns) == ["table", "key", "rule", "detail"]
    assert esg.check_meters(ok.iloc[:0], context=M12).empty
    coal = _meters([("X", "coal", 1, "t")])
    assert esg.check_meters(coal, unit_by_carrier={"coal": "t"}, scope_by_carrier={"coal": 1}, context=M12).empty
    assert esg.check_meters(coal, unit_by_carrier={"coal": "t"}, scope_by_carrier={"coal": 3}, context=M12)[["rule"]].values.tolist() == [["scope"]]
    assert esg.check_meters(coal, unit_by_carrier={"coal": "kg"}, scope_by_carrier={"coal": 1}, context=M12)[["rule"]].values.tolist() == [["unit"]]
    half = esg.check_meters(coal, unit_by_carrier={"coal": "t"}, scope_by_carrier={}, context=M12)
    assert half.rule.tolist() == ["unknown_carrier"], "a carrier must be in both maps to be known"
    other = esg.check_meters(ok, unit_by_carrier={"electricity": "MWh"}, scope_by_carrier={"electricity": 2}, context=M12)
    assert sorted(zip(other.key, other.rule)) == [("A", "unit"), ("B", "unknown_carrier"), ("C", "unknown_carrier"), ("D", "unknown_carrier"), ("E", "unknown_carrier")]
    with pytest.raises(FrameError, match="scope"):
        esg.check_meters(ok.drop(columns="scope"), context=M12)


def test_oracle_check_meters_every_route():
    """route: the hand frames and refusals of the check_meters tests above. The release step (the tampered baseline meters) is a separate test that needs the closed repository."""
    test_oracle_check_meters_one_violation_per_rule()
    test_oracle_check_meters_clean_list_and_the_maps_are_keywords()


# ---- energy_cost


def _cents(cost):
    return int((Decimal(repr(float(cost))) * 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _dkk_cents(cents, currency, eur, sek):
    """DKK cents of cents of `currency`, the product rounded half away from zero (positive amounts here)."""
    rate = {"DKK": Decimal(1), "EUR": eur, "SEK": sek}[currency]
    return int((Decimal(cents) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _cost_frames():
    m = pd.DataFrame([("M1", "electricity", "kWh"), ("M2", "diesel", "l")], columns=["mtr_key", "carrier", "unit"])
    rows = [("M1", "2025-01", 1000.0, "kWh", 100.01, "EUR"), ("M1", "2025-02", 500.0, "kWh", 100.01, "EUR"), ("M1", "2025-03", 250.0, "kWh", 100.01, "EUR"), ("M1", "2025-04", 100.0, "kWh", 0.25, "EUR"),
            ("M1", "2025-05", 10.0, "kWh", 10.0, "SEK"), ("M1", "2025-06", 400.0, "kWh", 80.0, "DKK"),
            ("M2", "2025-01", 0.0, "l", 10.0, "DKK"), ("M2", "2025-02", 80.0, "l", 160.0, "EUR")]
    return pd.DataFrame(rows, columns=["mtr_key", "period", "quantity", "unit", "cost_amount", "currency"]), m


def test_oracle_energy_cost_hand_example_rows_converted_before_the_sum():
    """route: hand frame with the sums written out; the DKK of each row from Decimal arithmetic on the two fixed rates read as facts, then summed per group."""
    c, m = _cost_frames()
    eur, sek = fact("world.fx_eur_dkk_fixed"), fact("world.fx_sek_dkk_fixed")
    rate_eur, rate_sek = Decimal(repr(float(eur.value))), Decimal(repr(float(sek.value)))
    msg = f"fixed rates used: EUR {eur.value}, SEK {sek.value}"
    plain = esg.energy_cost(c, m, context=M12)
    assert list(plain.columns) == ["carrier", "unit", "currency", "quantity", "cost", "unit_price"]
    got = plain.set_index(["carrier", "unit", "currency"])
    want = {("diesel", "l", "DKK"): (0.0, 10.0, None), ("diesel", "l", "EUR"): (80.0, 160.0, 2.0), ("electricity", "kWh", "DKK"): (400.0, 80.0, 0.2),
            ("electricity", "kWh", "EUR"): (1850.0, 300.28, 0.1623), ("electricity", "kWh", "SEK"): (10.0, 10.0, 1.0)}
    assert list(got.index) == list(want), "one row per carrier, unit and currency in sorted order, the currencies never added"
    for k, (q, cost, price) in want.items():
        assert got.loc[k, "quantity"] == pytest.approx(q, abs=1e-9) and got.loc[k, "cost"] == pytest.approx(cost, abs=1e-9), k
        if price is None:
            assert math.isnan(got.loc[k, "unit_price"]), "no quantity, no unit price"
        else:
            assert got.loc[k, "unit_price"] == pytest.approx(price, abs=1e-9), k
    d = esg.energy_cost(c, m, to_dkk=True, context=M12)
    assert list(d.columns) == ["carrier", "unit", "currency", "quantity", "cost", "unit_price", "cost_dkk"]
    dkk = d.set_index(["carrier", "unit", "currency"]).cost_dkk
    rowwise = sum(_dkk_cents(_cents(x), "EUR", rate_eur, rate_sek) for x in (100.01, 100.01, 100.01, 0.25))
    sum_first = _dkk_cents(3 * _cents(100.01) + _cents(0.25), "EUR", rate_eur, rate_sek)
    assert rowwise != sum_first, "the example must tell converting each row from converting the sum"
    assert dkk[("electricity", "kWh", "EUR")] == pytest.approx(rowwise / 100, abs=1e-9), msg
    assert dkk[("electricity", "kWh", "SEK")] == pytest.approx(_dkk_cents(1000, "SEK", rate_eur, rate_sek) / 100, abs=1e-9), msg
    assert dkk[("electricity", "kWh", "DKK")] == 80.0 and dkk[("diesel", "l", "DKK")] == 10.0, "DKK rows are not converted"
    assert dkk[("diesel", "l", "EUR")] == pytest.approx(_dkk_cents(16000, "EUR", rate_eur, rate_sek) / 100, abs=1e-9), msg
    half = _dkk_cents(25, "EUR", rate_eur, rate_sek)
    assert half == int((Decimal(25) * rate_eur).to_integral_value(rounding=ROUND_HALF_UP)) and (Decimal(25) * rate_eur) % 1 == Decimal("0.5"), "the 0.25 EUR row sits on a half cent"
    only = esg.energy_cost(c.iloc[[3]], m, to_dkk=True, context=M12)
    assert only.cost_dkk.iloc[0] == pytest.approx(half / 100, abs=1e-9), "a half cent rounds away from zero: " + msg


def test_oracle_energy_cost_every_route():
    """route: the hand example of the energy_cost test above. The release step (the baseline sums per carrier, unit and currency) is a separate test that needs the closed repository."""
    test_oracle_energy_cost_hand_example_rows_converted_before_the_sum()


# ---- energy_use_mwh


def _use_frames():
    m = pd.DataFrame([("E", "electricity", "kWh"), ("H", "district_heat", "MWh"), ("D", "diesel", "l"), ("P", "petrol", "l"), ("G", "natural_gas", "kWh")], columns=["mtr_key", "carrier", "unit"])
    rows = [("E", "2025-01", 1000.0, "kWh"), ("E", "2025-02", 500.0, "kWh"), ("H", "2025-01", 2.5, "MWh"), ("D", "2025-01", 100.0, "l"), ("D", "2025-02", 50.0, "l"),
            ("P", "2025-01", 40.0, "l"), ("G", "2025-01", 1234.5678, "kWh")]
    return pd.DataFrame(rows, columns=["mtr_key", "period", "quantity", "unit"]), m


def test_oracle_energy_use_mwh_hand_example_and_boundaries():
    """route: hand frame, kWh over 1,000, MWh as is and litres times the kWh per litre given in the test over 1,000, each sum written out."""
    c, m = _use_frames()
    r = esg.energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0, "petrol": 9.0, "unused": 1.0}, context=M12)
    assert list(r.columns) == ["carrier", "unit", "quantity", "mwh"]
    got = r.set_index("carrier")
    want = {"diesel": ("l", 150.0, 1.5), "district_heat": ("MWh", 2.5, 2.5), "electricity": ("kWh", 1500.0, 1.5), "natural_gas": ("kWh", 1234.568, 1.234568), "petrol": ("l", 40.0, 0.36)}
    assert list(got.index) == sorted(want)
    for k, (unit, q, mwh) in want.items():
        assert got.loc[k, "unit"] == unit and got.loc[k, "quantity"] == pytest.approx(q, abs=1e-9), k
        assert got.loc[k, "mwh"] == pytest.approx(mwh, abs=1e-6), k
    assert got.loc["natural_gas", "mwh"] != pytest.approx(1.235, abs=1e-4), "the decimals of the sum are kept, not cut at three"
    dry = c[c.unit != "l"]
    assert esg.energy_use_mwh(dry, m, context=M12).mwh.sum() == pytest.approx(1.5 + 2.5 + 1.234568, abs=1e-6), "without litres no energy content is asked for"
    with pytest.raises(FrameError, match="petrol"):
        esg.energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0}, context=M12)
    with pytest.raises(FrameError, match="diesel"):
        esg.energy_use_mwh(c, m, context=M12)
    for bad in (0.0, -9.0):
        with pytest.raises(FrameError, match="positive"):
            esg.energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0, "petrol": bad}, context=M12)
    with pytest.raises(FrameError, match="not kWh, MWh or l"):
        esg.energy_use_mwh(c.iloc[:1].assign(unit="GJ"), m.assign(unit="GJ"), context=M12)


def test_oracle_energy_use_mwh_is_additive_over_a_split_of_the_rows():
    """route: property, the MWh of two halves of the consumption rows add up to the MWh of the whole, per carrier, and the inputs stay unchanged."""
    c, m = _use_frames()
    kw = {"diesel": 10.0, "petrol": 9.0}
    c0, m0 = c.copy(deep=True), m.copy(deep=True)
    whole = esg.energy_use_mwh(c, m, kwh_per_litre=kw, context=M12).set_index("carrier").mwh
    a = esg.energy_use_mwh(c.iloc[:3], m, kwh_per_litre=kw, context=M12).set_index("carrier").mwh
    b = esg.energy_use_mwh(c.iloc[3:], m, kwh_per_litre=kw, context=M12).set_index("carrier").mwh
    both = a.add(b, fill_value=0.0)
    assert set(both.index) == set(whole.index)
    for k in whole.index:
        assert both[k] == pytest.approx(whole[k], abs=2e-6), k
    pd.testing.assert_frame_equal(c, c0)
    pd.testing.assert_frame_equal(m, m0)


def test_oracle_energy_use_mwh_every_route():
    """route: the hand example and the additivity property above. The release step (the baseline sums per carrier and unit) is a separate test that needs the closed repository."""
    test_oracle_energy_use_mwh_hand_example_and_boundaries()
    test_oracle_energy_use_mwh_is_additive_over_a_split_of_the_rows()
