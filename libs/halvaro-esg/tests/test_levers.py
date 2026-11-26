"""Levers (plan 5.7): hand computed fuel switch and material substitution, then the baseline properties."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, StageRefusal, registry

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")

F = pd.DataFrame({"efac_key": ["D", "W", "H", "WH", "PB"], "category": ["fuel_diesel", "fuel_wtt_diesel", "fuel_hvo", "fuel_wtt_hvo", "purchased_goods_product_footprint"],
                  "region": ["DK"] * 5, "factor_set": ["FS-1"] * 4 + [None], "kgco2e_per_unit": [2.6, 0.6, 0.5, 0.2, 0.4], "unit": ["l"] * 4 + ["kgCO2e"]})


def _lines(rows):
    c = ["prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


L = _lines([("P1", "LE-01", "2025-03", 1, "mobile_combustion", 1, 100.0, "D", 260.0, True, None, None, "l"), ("P1", "LE-01", "2025-03", 1, "mobile_combustion", 2, 120.0, "D", 312.0, False, "2026-01", 1, "l"),
            ("P1", "LE-01", "2025-03", 3, "fuel_and_energy_related", 3, 120.0, "W", 72.0, False, None, None, "l"), ("P2", "LE-01", "2025-04", 1, "stationary_combustion", 1, 10.0, "D", 26.0, False, None, None, "l"),
            (None, "LE-01", "2025-04", 1, "mobile_combustion", 2, 999.0, "D", 2597.4, False, None, None, "l")])
P = pd.DataFrame({"prj_key": ["P1", "P2"], "route_length_m": [1000.0, 0.0]})


def test_fuel_switch_prices_current_basis_diesel_again_with_hvo_of_the_same_set():
    r = esg.lever_fuel_switch(L, F, P, context=M12)
    v = r.value.set_index("prj_key")
    assert r.status == "VERIFY+synthetic" and any("biogenic" in w for w in r.warnings)
    assert v.loc["P1", "diesel_litres"] == 120.0, "the restated line replaces its original"
    assert (v.loc["P1", "diesel_kgco2e"], v.loc["P1", "switched_kgco2e"], v.loc["P1", "saved_kgco2e"]) == (384.0, 84.0, 300.0) and v.loc["P1", "saved_kgco2e_per_m"] == 0.3
    assert v.loc["P2", "saved_kgco2e"] == 21.0 and np.isnan(v.loc["P2", "saved_kgco2e_per_m"]), "a route length of zero gives no per metre value"
    assert "P1" in v.index and len(v) == 2, "a line without a project is not a project saving"
    assert (v.saved_kgco2e >= 0).all() and (v.saved_kgco2e <= v.diesel_kgco2e).all() and not v.worse.any(), "property of the plan"


def test_fuel_switch_refusals_and_a_worse_target():
    with pytest.raises(FrameError, match="unknown target"):
        esg.lever_fuel_switch(L, F, P, to="ammonia", context=M12)
    with pytest.raises(FrameError, match="no hvo100 factor"):
        esg.lever_fuel_switch(L, F[F.efac_key != "WH"], context=M12)
    with pytest.raises(FrameError, match="does not hold"):
        esg.lever_fuel_switch(L, F[F.efac_key != "W"], context=M12)
    with pytest.raises(FrameError, match="two target rows"):
        esg.lever_fuel_switch(L, pd.concat([F, F.iloc[[2]].assign(efac_key="HV2")]), context=M12)
    worse = F.assign(kgco2e_per_unit=[2.6, 0.6, 3.5, 0.2, 0.4])
    assert esg.lever_fuel_switch(L, worse, context=M12).value.set_index("prj_key").loc["P1", "worse"], "HVO factor above diesel: flagged, not hidden"
    with pytest.raises(StageRefusal):
        esg.lever_fuel_switch(L, F, context=M3)


ITEM = pd.DataFrame({"itm_key": ["A", "B", "C", "D"], "category": ["pipe", "pipe", "pipe", "valve"], "unit": ["m", "m", "pcs", "m"], "footprint_kgco2e_per_unit": [10.0, 6.0, 5.0, 1.0]})
EPD = pd.DataFrame({"itm_key": ["A", "B"], "source": ["x", "y"], "verification": [None, "third party verified (synthetic)"]})


def test_material_substitution_counted_share_same_item_and_refusals():
    r = esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A", "A", "B"], "quantity": [100.0, 50.0, 10.0]}), ITEM, EPD, {"A": "B", "B": "B"}, F, context=M12)
    v = r.value.set_index("itm_key")
    assert v.loc["A", "quantity"] == 150.0 and v.loc["A", "counted_share"] == 0.4 and v.loc["A", "saved_kgco2e"] == 240.0, "(10 - 6) x 150 x 0.4"
    assert v.loc["B", "saved_kgco2e"] == 0.0 and bool(v.loc["A", "cand_epd_verified"]) and (v.equivalence == "unverified").all(), "the same item gives zero"
    w = esg.lever_material_substitution(pd.DataFrame({"itm_key": ["B"], "quantity": [10.0]}), ITEM, EPD, {"B": "A"}, F, context=M12).value.iloc[0]
    assert w.saved_kgco2e == -16.0 and bool(w.worse) and not bool(w.cand_epd_verified)
    for cand, msg in (({"A": "C"}, "same category and unit"), ({"A": "D"}, "same category and unit"), ({"A": "Z"}, "does not hold")):
        with pytest.raises(FrameError, match=msg):
            esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A"], "quantity": [1.0]}), ITEM, EPD, cand, F, context=M12)
    with pytest.raises(FrameError, match="quantities"):
        esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A"], "quantity": [-1.0]}), ITEM, EPD, {"A": "B"}, F, context=M12)
    with pytest.raises(FrameError, match="no footprint"):
        esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A"], "quantity": [1.0]}), ITEM.assign(footprint_kgco2e_per_unit=[10.0, np.nan, 5.0, 1.0]), EPD, {"A": "B"}, F, context=M12)
    with pytest.raises(FrameError, match="one is expected"):
        esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A"], "quantity": [1.0]}), ITEM, EPD, {"A": "B"}, F.iloc[:4], context=M12)


def test_lever_report_two_best_per_metre_share_of_gap_and_limit():
    pm = pd.DataFrame({"prj_key": ["P1"], "route_length_m": [1000.0], "kgco2e_per_m": [100.0]})
    lv = pd.DataFrame({"lever": ["fuel", "steel", "other"], "saved_kgco2e": [8000.0, 3000.0, 8000.0]})
    r = esg.lever_report(pm, lv, 90.0, context=M12)
    assert r.lever.tolist() == ["fuel", "other"] and r.saved_per_m.tolist() == [8.0, 8.0], "ties by name"
    assert r.gap_per_m.tolist() == [10.0, 10.0] and r.share_of_gap_closed.tolist() == [0.8, 0.8] and r.per_m_after.tolist() == [92.0, 92.0] and not r.below_limit_after.any()
    ok = esg.lever_report(pm, lv.assign(saved_kgco2e=[12000.0, 3000.0, 1.0]), 90.0, top=1, context=M12)
    assert ok.below_limit_after.tolist() == [True] and ok.share_of_gap_closed.tolist() == [1.2], "more than the gap: the share is above 1, not capped"
    assert esg.lever_report(pm, lv, 120.0, context=M12).share_of_gap_closed.isna().all(), "no gap: no share"
    for kw, msg in ((dict(limit=0), "limit"), (dict(limit=90.0, top=0), "top")):
        with pytest.raises(FrameError, match=msg):
            esg.lever_report(pm, lv, **kw, context=M12)
    with pytest.raises(FrameError, match="exactly one row"):
        esg.lever_report(pd.concat([pm, pm]), lv, 90.0, context=M12)
    with pytest.raises(FrameError, match="route length"):
        esg.lever_report(pm.assign(route_length_m=0.0), lv, 90.0, context=M12)
    with pytest.raises(FrameError, match="twice"):
        esg.lever_report(pm, pd.concat([lv, lv.iloc[:1]]), 90.0, context=M12)


def test_registration_and_stage():
    for n in ("lever_fuel_switch", "lever_material_substitution", "lever_report"):
        assert f"halvaro.esg.levers.{n}" in registry.registered() and n in esg.__all__


def test_fuel_switch_null_guards_and_lever_report_boundaries():
    for bad_f, msg in ((F.assign(kgco2e_per_unit=[2.6, 0.6, np.nan, 0.2, 0.4]), "no kgco2e_per_unit"), (F.assign(kgco2e_per_unit=[2.6, 0.6, 0.5, np.nan, 0.4]), "no kgco2e_per_unit")):
        with pytest.raises(FrameError, match=msg):
            esg.lever_fuel_switch(L, bad_f, context=M12)
    with pytest.raises(FrameError, match="no efac_key"):
        esg.lever_fuel_switch(L.assign(efac_key=[L.efac_key[0], None] + L.efac_key.tolist()[2:]), F, context=M12)
    with pytest.raises(FrameError, match="quantity or kgco2e"):
        esg.lever_fuel_switch(L.assign(kgco2e=[260.0, np.nan, 72.0, 26.0, 2597.4]), F, context=M12)
    with pytest.raises(FrameError, match="unit"):
        esg.lever_fuel_switch(L.assign(unit=["l", "kWh", "l", "l", "l"]), F, context=M12)
    pm = pd.DataFrame({"prj_key": ["P1"], "route_length_m": [1000.0], "kgco2e_per_m": [100.0]})
    exact = esg.lever_report(pm, pd.DataFrame({"lever": ["a"], "saved_kgco2e": [10000.0]}), 90.0, context=M12)
    assert exact.share_of_gap_closed.tolist() == [1.0] and exact.below_limit_after.tolist() == [True], "exactly at the limit is not above it"
    rank = esg.lever_report(pm, pd.DataFrame({"lever": ["b", "a"], "saved_kgco2e": [1000.0004, 1000.0]}), 90.0, context=M12)
    assert rank.lever.tolist() == ["b", "a"], "ranking on the unrounded saving"
    none = esg.lever_report(pm, pd.DataFrame({"lever": ["a"], "saved_kgco2e": [-5.0]}), 90.0, context=M12)
    assert none.empty, "a lever that makes it worse is not a best lever"
    with pytest.raises(FrameError, match="finite"):
        esg.lever_material_substitution(pd.DataFrame({"itm_key": ["A"], "quantity": [float("inf")]}), ITEM, EPD, {"A": "B"}, F, context=M12)
    cat = L.assign(prj_key=L.prj_key.astype("category"))
    assert len(esg.lever_fuel_switch(cat, F, context=M12).value) == 2
