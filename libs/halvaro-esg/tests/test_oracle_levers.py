"""Oracles of the three levers (plan 5.7): hand worked numbers, then a direct pandas or plain python recomputation from the baseline release."""
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
LCOLS = ["prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"]


def _lines(rows):
    return pd.DataFrame(rows, columns=LCOLS).astype({"supersedes_line_no": "Int64"})


def _factors(rows):
    return pd.DataFrame(rows, columns=["efac_key", "category", "region", "factor_set", "kgco2e_per_unit", "unit"])


F = _factors([("E-D", "fuel_diesel", "DK", "FS-A", 2.5, "l"), ("E-W", "fuel_wtt_diesel", "EU", "FS-A", 0.5, "l"), ("E-H", "fuel_hvo", "DK", "FS-A", 0.25, "l"), ("E-WH", "fuel_wtt_hvo", "EU", "FS-A", 0.125, "l"), ("E-D2", "fuel_diesel", "DK", "FS-A", 2.4, "l")])


def test_oracle_lever_fuel_switch_hand_worked_numbers():
    """route: hand arithmetic. Project A: 100 l diesel (250 kg), 50 l restated diesel (120 kg, replacing an original of 125 kg) and 100 l well to tank (50 kg), priced again at 0.25 and 0.125 per litre; the superseded original and a line without a project do not count."""
    L = _lines([("PRJ-A", "LE-01", "2025-03", 1, "mobile_combustion", 1, 100.0, "E-D", 250.0, False, None, None, "l"),
                ("PRJ-A", "LE-01", "2025-03", 3, "fuel_and_energy_related", 2, 100.0, "E-W", 50.0, False, None, None, "l"),
                ("PRJ-A", "LE-01", "2025-04", 1, "mobile_combustion", 3, 50.0, "E-D", 125.0, True, None, None, "l"),
                ("PRJ-A", "LE-01", "2025-04", 1, "mobile_combustion", 6, 50.0, "E-D2", 120.0, False, "2026-01", 3, "l"),
                ("PRJ-B", "LE-01", "2025-03", 1, "mobile_combustion", 4, 40.0, "E-D", 100.0, False, None, None, "l"),
                (None, "LE-01", "2025-03", 1, "mobile_combustion", 5, 999.0, "E-D", 2497.5, False, None, None, "l")])
    P = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B"], "route_length_m": [1000.0, 200.0]})
    r = esg.lever_fuel_switch(L, F, P, context=M12)
    v = r.value.set_index("prj_key")
    assert list(v.index) == ["PRJ-A", "PRJ-B"]
    assert v.loc["PRJ-A", "diesel_litres"] == 150.0 and v.loc["PRJ-A", "diesel_kgco2e"] == 250.0 + 120.0 + 50.0
    assert v.loc["PRJ-A", "switched_kgco2e"] == 150 * 0.25 + 100 * 0.125 and v.loc["PRJ-A", "saved_kgco2e"] == 420.0 - 50.0
    assert v.loc["PRJ-B", "diesel_litres"] == 40.0 and v.loc["PRJ-B", "saved_kgco2e"] == 100.0 - 40 * 0.25
    assert v.loc["PRJ-A", "saved_kgco2e_per_m"] == pytest.approx(370.0 / 1000, abs=1e-3) and v.loc["PRJ-B", "saved_kgco2e_per_m"] == pytest.approx(90.0 / 200, abs=1e-3)
    assert not v["worse"].any() and r.status == "VERIFY+synthetic"
    worse = F.assign(kgco2e_per_unit=[2.5, 0.5, 3.0, 0.125, 2.4])                       # an HVO factor above diesel: the saving turns negative
    w = esg.lever_fuel_switch(L, worse, context=M12).value.set_index("prj_key")
    assert w.loc["PRJ-B", "saved_kgco2e"] == 100.0 - 40 * 3.0 and bool(w.loc["PRJ-B", "worse"])
    with pytest.raises(FrameError, match="no hvo100 factor row"):
        esg.lever_fuel_switch(L, F.iloc[[0, 1, 3, 4]], context=M12)


def _items(rows):
    return pd.DataFrame(rows, columns=["itm_key", "category", "unit", "footprint_kgco2e_per_unit"])


SHARE = pd.DataFrame({"efac_key": ["E-P"], "category": ["purchased_goods_product_footprint"], "kgco2e_per_unit": [0.25]})
ITEMS = _items([("I-A", "valve", "pcs", 100.0), ("I-B", "valve", "pcs", 60.0), ("I-C", "valve", "pcs", 120.0), ("I-X", "pipe", "pcs", 5.0), ("I-U", "valve", "m", 1.0)])
EPD = pd.DataFrame({"itm_key": ["I-B", "I-B", "I-C"], "source": ["s", "s", "s"], "verification": [None, "third party", None], "valid_from": ["2023-01-01", "2024-01-01", "2024-01-01"]})


def test_oracle_lever_material_substitution_hand_worked_numbers():
    """route: hand arithmetic (footprint difference times quantity times the one counted share of 0.25)."""
    G = pd.DataFrame({"itm_key": ["I-A", "I-A", "I-B"], "quantity": [4.0, 6.0, 10.0]})
    r = esg.lever_material_substitution(G, ITEMS, EPD, {"I-A": "I-B", "I-B": "I-C"}, SHARE, context=M12)
    v = r.value.set_index("itm_key")
    assert v.loc["I-A", "quantity"] == 10.0, "two rows of the same item are summed"
    assert v.loc["I-A", "saved_kgco2e"] == (100.0 - 60.0) * 10.0 * 0.25 == 100.0 and not bool(v.loc["I-A", "worse"])
    assert v.loc["I-B", "saved_kgco2e"] == (60.0 - 120.0) * 10.0 * 0.25 == -150.0 and bool(v.loc["I-B", "worse"]), "a candidate with a higher footprint saves a negative amount"
    assert bool(v.loc["I-A", "cand_epd_verified"]) is True and bool(v.loc["I-B", "cand_epd_verified"]) is False, "latest EPD row of the candidate decides"
    assert (v["equivalence"] == "unverified").all() and (v["counted_share"] == 0.25).all() and r.status == "VERIFY+synthetic"
    same = esg.lever_material_substitution(G.iloc[[0]], ITEMS, EPD, {"I-A": "I-A"}, SHARE, context=M12).value
    assert same["saved_kgco2e"].tolist() == [0.0]
    for bad in ({"I-A": "I-X"}, {"I-A": "I-U"}):
        with pytest.raises(FrameError, match="same category and unit"):
            esg.lever_material_substitution(G, ITEMS, EPD, bad, SHARE, context=M12)


def test_oracle_lever_report_hand_worked_numbers_and_ordering():
    """route: hand arithmetic for a project of 1,000 m at 120 kg per metre against a limit of 100: the gap is 20 per metre and each lever closes its saved kilograms over 1,000 metres of it."""
    pm = pd.DataFrame({"prj_key": ["PRJ-A"], "route_length_m": [1000.0], "kgco2e_per_m": [120.0]})
    lv = pd.DataFrame({"lever": ["b", "a", "c", "d", "e"], "saved_kgco2e": [5000.0, 15000.0, 0.0, -3.0, 5000.0]})
    r = esg.lever_report(pm, lv, 100.0, context=M12)
    assert r["lever"].tolist() == ["a", "b"] and r["rank"].tolist() == [1, 2], "largest saving first; a tie (b, e) is broken by the lever name; zero and negative savings are not ranked"
    assert r["saved_per_m"].tolist() == [15.0, 5.0] and r["gap_per_m"].tolist() == [20.0, 20.0]
    assert r["share_of_gap_closed"].tolist() == [0.75, 0.25] and r["per_m_after"].tolist() == [105.0, 115.0] and r["below_limit_after"].tolist() == [False, False]
    exact = esg.lever_report(pm, pd.DataFrame({"lever": ["x"], "saved_kgco2e": [20000.0]}), 100.0, context=M12)
    assert exact["per_m_after"].tolist() == [100.0] and exact["below_limit_after"].tolist() == [True], "a footprint exactly at the limit is not above it"
    assert esg.lever_report(pm, lv, 100.0, top=3, context=M12)["lever"].tolist() == ["a", "b", "e"]
    under = esg.lever_report(pm, lv, 150.0, context=M12)
    assert under["gap_per_m"].tolist() == [0.0, 0.0] and under["share_of_gap_closed"].isna().all(), "no gap: the share is null"
    before = lv.copy()
    esg.lever_report(pm, lv, 100.0, context=M12)
    pd.testing.assert_frame_equal(lv, before)
    for bad in (dict(limit=0), dict(limit=-1.0), dict(limit=100.0, top=0)):
        with pytest.raises(FrameError):
            esg.lever_report(pm, lv, **{"limit": 100.0, **bad}, context=M12)
    with pytest.raises(FrameError, match="exactly one row"):
        esg.lever_report(pd.concat([pm, pm]), lv, 100.0, context=M12)
