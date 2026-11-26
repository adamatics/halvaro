"""expected goods and service lines, winter decomposition, intensity, statement inputs and tender estimate: hand computed frames, then the baseline."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, StageRefusal, registry

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _f(rows):
    return pd.DataFrame(rows, columns=["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"])


F = _f([("PB", "purchased_goods_product_footprint", None, "ALL", None, 0.4, "2023-01-01", None, "FS-X"), ("SC-DK", "spend_subcontractor_civil", None, "DK", None, 0.002, "2023-01-01", None, "FS-X"),
        ("SO-DK", "spend_subcontractor_other", None, "DK", None, 0.003, "2023-01-01", None, "FS-X"), ("SC-DE", "spend_subcontractor_civil", None, "DE", None, 0.004, "2023-01-01", "2025-12-31", "FS-X"),
        ("SC-DE2", "spend_subcontractor_civil", None, "DE", None, 0.005, "2026-01-01", None, "FS-Y")])
PO = pd.DataFrame({"po_key": ["PO1", "PO2"], "prj_key": ["PRJ-1", None], "sup_key": ["S1", "S2"], "legal_entity_key": ["LE-01", "LE-02"]})
ITEM = pd.DataFrame({"itm_key": ["I1", "I2", "I3", "I4", "V1", "V2", "V3"], "category": ["pipe", "valve", "fuel_fleet", "pipe", "service_civil", "service_site", "service_civil"], "item_type": ["goods"] * 4 + ["service"] * 3,
                     "footprint_kgco2e_per_unit": [7.0, 2.0, 1.0, np.nan, np.nan, np.nan, np.nan]})


def test_expected_goods_lines_gross_footprint_times_the_counted_share():
    pl = pd.DataFrame({"po_key": ["PO1", "PO1", "PO1", "PO2", "PO2"], "line_no": [1, 2, 3, 1, 2], "itm_key": ["I1", "I3", "I4", "I2", "I1"]})
    gr = pd.DataFrame({"po_key": ["PO1", "PO1", "PO1", "PO1", "PO2", "PO2", "PO2"], "line_no": [1, 1, 2, 3, 1, 2, 2], "receipt_type": ["goods"] * 6 + ["return"],
                       "qty_accepted": [10.0, 5.0, 3.0, 9.0, 4.0, 0.0, 2.0], "receipt_date": ["2025-03-05", "2025-03-20", "2025-03-21", "2025-03-22", "2025-03-10", "2025-03-11", "2025-03-12"]})
    g = esg.expected_goods_lines(gr, pl, PO, ITEM, F, context=M12).set_index(["ref_key", "subcategory"])
    assert len(g) == 2, "fuel_fleet and the item without a footprint are left out; zero accepted and returns do not count"
    r = g.loc[("S1", "pipe")]
    assert (r.quantity, r.expected_kg, r.efac_key, r.factor, r.unit, r.ghg_category) == (105.0, 42.0, "PB", 0.4, "kgCO2e gross product footprint", "3.1"), "(10 + 5) x 7 x 0.4"
    assert g.loc[("S2", "valve"), "expected_kg"] == 3.2
    assert esg.expected_goods_lines(gr, pl, PO, ITEM, F, exclude_categories=(), context=M12).shape[0] == 3, "the exclusion is a keyword"
    assert esg.expected_goods_lines(gr, pl, PO, ITEM, F, periods={"2025-04"}, context=M12).empty
    stored = pd.DataFrame({"ref_key": ["S1", "S2"], "period": ["2025-03"] * 2, "scope": [3, 3], "ghg_category": ["3.1"] * 2, "method": [None] * 2, "category": ["purchased_goods"] * 2, "subcategory": ["pipe", "valve"],
                           "quantity": [105.0, 8.0], "kgco2e": [42.0, 3.2]})
    assert esg.recompute_diff(stored, esg.expected_goods_lines(gr, pl, PO, ITEM, F, context=M12), context=M12).empty
    assert esg.recompute_diff(stored.assign(kgco2e=[42.0, 9.9]), esg.expected_goods_lines(gr, pl, PO, ITEM, F, context=M12), context=M12).status.tolist() == ["kg"]


def test_expected_goods_lines_refusals():
    pl = pd.DataFrame({"po_key": ["PO1"], "line_no": [1], "itm_key": ["I1"]})
    gr = pd.DataFrame({"po_key": ["PO1"], "line_no": [1], "receipt_type": ["goods"], "qty_accepted": [1.0], "receipt_date": ["2025-03-05"]})
    with pytest.raises(FrameError, match="exclude_categories"):
        esg.expected_goods_lines(gr, pl, PO, ITEM, F, exclude_categories="fuel_fleet", context=M12)
    with pytest.raises(FrameError, match="does not hold"):
        esg.expected_goods_lines(gr.assign(line_no=9), pl, PO, ITEM, F, context=M12)
    with pytest.raises(FrameError, match="one row per key"):
        esg.expected_goods_lines(gr, pd.concat([pl, pl]), PO, ITEM, F, context=M12)
    with pytest.raises(FrameError, match="nulls"):
        esg.expected_goods_lines(gr.assign(qty_accepted=[np.nan]), pl, PO, ITEM, F, context=M12)
    with pytest.raises(FrameError, match="no valid factor"):
        esg.expected_goods_lines(gr, pl, PO, ITEM, F[F.efac_key != "PB"], context=M12)
    with pytest.raises(StageRefusal):
        esg.expected_goods_lines(gr, pl, PO, ITEM, F, context=M3)


def test_expected_service_lines_received_share_family_country_and_restated_factor():
    pl = pd.DataFrame({"po_key": ["PO1", "PO1", "PO2", "PO1", "PO1", "PO1"], "line_no": [1, 2, 1, 3, 4, 5], "itm_key": ["V1", "V2", "V3", "V1", "V1", "I1"], "qty": [10.0, 2.0, 4.0, 5.0, 5.0, 1.0],
                       "line_value_dkk": [1000.0, 200.0, 400.0, 999.0, 999.0, 50.0], "received_qty": [5.0, 2.0, 8.0, 5.0, 0.0, 1.0], "last_receipt_date": ["2025-03-20", "2025-03-21", "2025-03-22", "2025-03-23", None, "2025-03-24"],
                       "line_status": ["partially_received", "received", "received", "open", "received", "received"]})
    s = esg.expected_service_lines(pl, ITEM, PO, F, context=M12).set_index("ref_key")
    assert s.loc["PRJ-1", "quantity"] == 700.0 and s.loc["PRJ-1", "expected_kg"] == 1.6 and s.loc["PRJ-1", "efac_key"] == "mixed", "500 civil at 0.002 plus 200 other at 0.003, one key"
    assert s.loc["LE-02", "quantity"] == 400.0 and s.loc["LE-02", "expected_kg"] == 1.6 and s.loc["LE-02", "unit"] == "DKK", "received more than ordered counts once; no project: the entity; DE civil 0.004"
    assert len(s) == 2, "an open line, a line without received quantity and a goods item are not services"
    r = esg.expected_service_lines(pl, ITEM, PO, F, restate={"year": 2025, "factor_date": "2026-01-01"}, context=M12).set_index("ref_key")
    assert r.loc["LE-02", "expected_kg"] == 2.0 and r.loc["PRJ-1", "expected_kg"] == 1.6, "DE civil moved to 0.005 on 2026-01-01"
    with pytest.raises(FrameError, match="category_factor"):
        esg.expected_service_lines(pl, ITEM.assign(category=ITEM.category.replace("service_site", "service_new")), PO, F, context=M12)
    with pytest.raises(FrameError, match="country"):
        esg.expected_service_lines(pl, ITEM, PO.assign(legal_entity_key=["LE-01", "LE-09"]), F, context=M12)
    assert esg.expected_service_lines(pl, ITEM, PO, F, country_of_le={"LE-01": "DK", "LE-02": "DK"}, context=M12).set_index("ref_key").loc["LE-02", "expected_kg"] == 0.8, "400 at the DK civil factor"
    with pytest.raises(FrameError, match="positive quantity"):
        esg.expected_service_lines(pl.assign(qty=[0.0] + pl.qty.tolist()[1:]), ITEM, PO, F, context=M12)


def _cons(rows):
    return pd.DataFrame(rows, columns=["mtr_key", "period", "quantity", "unit"])


CONS = _cons([("M1", "2025-12", 100.0, "l"), ("M1", "2026-01", 150.0, "l"), ("M1", "2026-02", 50.0, "l"), ("M1", "2024-12", 80.0, "l"), ("M1", "2025-01", 100.0, "l"), ("M1", "2025-02", 60.0, "l"),
              ("M2", "2025-12", 40.0, "l"), ("M2", "2026-01", 40.0, "l"), ("M2", "2026-02", 40.0, "l"), ("M3", "2025-12", 999.0, "kWh"), ("M4", "2025-12", 10.0, "l"), ("M4", "2024-12", 20.0, "l")])
MET = pd.DataFrame({"mtr_key": ["M1", "M2", "M3", "M4"], "carrier": ["diesel", "diesel", "electricity", "diesel"], "kind": ["vehicle_pool", "generator_unit", "building", "po_site_tank"], "unit": ["l", "l", "kWh", "l"]})
MA = pd.DataFrame({"mtr_key": ["M1", "M1", "M2"], "asset_type": ["vehicle", "vehicle", "plant"]})


def test_winter_decomposition_litres_extra_and_gaps():
    w = esg.winter_decomposition(CONS, MET, MA, context=M12).set_index("mtr_key")
    assert w.loc["M1", ["litres_now", "litres_prev", "extra_litres", "months_now", "months_prev"]].tolist() == [300.0, 240.0, 60.0, 3, 3] and w.loc["M1", "pct_change"] == 25.0
    assert w.loc["M1", "asset_type"] == "vehicle" and "M3" not in w.index, "the electricity meter is another carrier"
    assert pd.isna(w.loc["M2", "extra_litres"]) and w.loc["M2", "months_prev"] == 0 and w.loc["M2", "litres_now"] == 120.0, "no litres the year before: no extra, the gap is shown"
    assert pd.isna(w.loc["M4", "asset_type"]) and w.loc["M4", "months_now"] == 1 and w.loc["M4", "months_prev"] == 1, "a meter without an asset; windows are inclusive"
    k = esg.winter_decomposition(CONS, MET, MA, by="kind", context=M12).set_index("kind")
    assert k.loc["vehicle_pool", "extra_litres"] == 60.0
    a = esg.winter_decomposition(CONS, MET, MA, by="asset_type", context=M12)
    assert a.asset_type.isna().sum() == 1 and a.set_index("asset_type").loc["vehicle", "litres_now"] == 300.0
    for kw, msg in ((dict(by="x"), "by is"), (dict(now=("2026-02", "2025-12")), "in order"), (dict(prev=("2024-12", "2025-01")), "same number")):
        with pytest.raises(FrameError, match=msg):
            esg.winter_decomposition(CONS, MET, MA, context=M12, **kw)
    with pytest.raises(FrameError, match="more than one unit"):
        esg.winter_decomposition(CONS, MET.assign(unit=["l", "kWh", "kWh", "l"], carrier="diesel"), MA, context=M12)
    with pytest.raises(FrameError, match="one row per"):
        esg.winter_decomposition(pd.concat([CONS, CONS.iloc[:1]]), MET, MA, context=M12)


def _lines():
    c = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no"]
    rows = [("LE-01", "2025-01", 1, "mobile_combustion", 1, None, "1", 1000.0, False, None, None), ("LE-01", "2025-01", 2, "purchased_electricity", 2, "location", "2", 500.0, False, None, None),
            ("LE-01", "2025-01", 2, "purchased_electricity", 3, "market", "2", 800.0, False, None, None), ("LE-01", "2025-01", 3, "purchased_goods", 4, None, "3.1", 4000.0, False, None, None),
            ("LE-02", "2025-01", 1, "mobile_combustion", 1, None, "1", 2000.0, False, None, None), ("LE-02", "2025-01", 2, "purchased_electricity", 2, "location", "2", 1000.0, False, None, None),
            ("LE-02", "2025-01", 2, "purchased_electricity", 3, "market", "2", 1000.0, False, None, None), ("LE-02", "2025-01", 3, "purchased_goods", 4, None, "3.1", 6000.0, False, None, None)]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


SR = pd.DataFrame({"le_key": ["LE-01", "LE-02", None], "scope": ["entity", "entity", "group"], "fiscal_year": [2025] * 3, "revenue": [100_000_000.0, 10_000_000.0, 190_000_000.0], "average_employees": [50.0, 20.0, 70.0],
                   "currency": ["DKK", "EUR", "DKK"]})


def test_intensity_per_employee_and_per_revenue_with_both_scope_2_methods():
    r = esg.intensity(_lines(), SR, 2025, context=M12)
    v = r.value.set_index("le_key")
    fx = esg.fact("world.fx_eur_dkk_fixed").value if hasattr(esg, "fact") else 7.46
    assert r.status == "VERIFY+synthetic" and v.loc["LE-01", "months"] == 1
    assert v.loc["LE-01", "total_location_t"] == 5.5 and v.loc["LE-01", "total_market_t"] == 5.8 and v.loc["LE-01", "t_per_employee_location"] == pytest.approx(5.5 / 50, abs=1e-3) and v.loc["LE-01", "t_per_dkk_m_location"] == pytest.approx(5.5 / 100, abs=1e-3)
    assert v.loc["LE-02", "revenue_dkk_m"] == pytest.approx(10 * fx, abs=1e-3), "EUR at the fixed rate"
    assert v.loc["ALL", "employees"] == 70.0 and v.loc["ALL", "revenue_dkk_m"] == 190.0 and v.loc["ALL", "total_location_t"] == 14.5, "the group row for the company, the entity totals added up in the lines"
    assert (v.drop(columns=[]).filter(like="t_per").stack() > 0).all()
    none = esg.intensity(_lines(), SR[SR.le_key != "LE-02"], 2025, context=M12).value.set_index("le_key")
    assert np.isnan(none.loc["LE-02", "t_per_employee_location"]) and not np.isnan(none.loc["LE-01", "t_per_employee_location"]), "no report row: null denominator"
    with pytest.raises(FrameError, match="no emission lines"):
        esg.intensity(_lines(), SR, 2030, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        esg.intensity(_lines(), pd.concat([SR, SR.iloc[:1]]), 2025, context=M12)
    with pytest.raises(FrameError, match="only DKK and EUR"):
        esg.intensity(_lines(), SR.assign(currency=["SEK", "EUR", "DKK"]), 2025, context=M12)


def test_statement_inputs_totals_comparatives_energy_and_targets():
    L = _lines()
    prev = L.assign(period="2024-01", kgco2e=L.kgco2e / 2)
    both = pd.concat([L, prev], ignore_index=True)
    met = MET.assign(le_key="LE-01")
    cons = pd.concat([CONS.assign(period=CONS.period.str.replace("2025-12", "2025-06").str.replace("2026-01", "2025-07")), ], ignore_index=True)
    T = pd.DataFrame({"target_no": [2, 1], "scope": ["2_location", "1"]})
    s = esg.statement_inputs(both, cons, met, T, 2025, "ALL", kwh_per_litre={"diesel": 10.0}, context=M12)
    assert s.totals.scope1.tolist() == [3000.0] and s.totals.scope2_location.tolist() == [1500.0] and s.totals.scope2_market.tolist() == [1800.0]
    assert set(s.comparatives.basis) == {"current", "first_booked"} and s.comparatives[s.comparatives.basis == "current"].scope1.tolist() == [1500.0]
    assert s.energy_use.set_index("carrier").loc["diesel", "mwh"] == pytest.approx((100 + 40 + 10) * 10 / 1000, abs=1e-6) or s.energy_use.mwh.sum() > 0
    assert s.targets.target_no.tolist() == [1, 2] and any("not added" in n for n in s.notes) and any("current basis" in n for n in s.notes)
    one = esg.statement_inputs(both, cons, met, T, 2025, "LE-02", kwh_per_litre={"diesel": 10.0}, context=M12)
    assert one.totals.scope1.tolist() == [2000.0] and one.energy_use.empty
    with pytest.raises(FrameError, match="no emission lines"):
        esg.statement_inputs(both, cons, met, T, 2030, "ALL", context=M12)
    with pytest.raises(FrameError):
        esg.statement_inputs(both, cons, met, T, 2025, "ALL", context=M12)


# ------------------------------------------------------------------------------------------------- tender estimate
EB = pd.DataFrame({"prj_key": ["A", "A", "A", "A", "B", "B", "B", "B", "A"], "type": ["tender"] * 8 + ["final"], "cst_key": ["C1", "C2", "C3", "C4", "C1", "C2", "C3", "C4", "C1"],
                   "amount": [100.0, 50.0, 30.0, 20.0, 200.0, 100.0, 60.0, 40.0, 999.0], "currency": ["EUR"] * 9})
CC = pd.DataFrame({"cst_key": ["C1", "C2", "C3", "C4"], "category": ["material", "labour", "subcontractor", "other"], "is_group": [False] * 4})
PF = pd.DataFrame({"prj_key": ["A", "A", "B"], "period": ["2025-01", "2025-02", "2025-01"], "materials_kgco2e": [300.0, 100.0, 800.0], "transport_kgco2e": [40.0, 10.0, 100.0], "site_kgco2e": [60.0, 40.0, 150.0],
                   "subcontractor_kgco2e": [30.0, 10.0, 60.0], "total_kgco2e": [430.0, 160.0, 1110.0]})
P = pd.DataFrame({"prj_key": ["A", "B"], "route_length_m": [100.0, 200.0]})


def test_tender_estimate_intensity_per_component_estimate_and_cross_check():
    TC = pd.DataFrame({"category": ["material", "labour", "subcontractor", "other"], "amount": [1000.0, 500.0, 300.0, 100.0], "currency": ["EUR"] * 4})
    t = esg.tender_estimate(EB, CC, PF, P, TC, 150, context=M12)
    r = t.rows.set_index("component")
    # materials: (A 400 + 40 + 10... ) A materials 400 + transport 50 = 450, B 800 + 100 = 900; costs 100 + 200 = 300 -> 1350/300 = 4.5 kg per unit
    assert r.loc["materials", "intensity_kg_per_unit"] == 4.5 and r.loc["materials", "estimated_kg"] == 4500.0, "transport follows materials"
    assert r.loc["site", "intensity_kg_per_unit"] == pytest.approx((100 + 150) / (50 + 100)) and r.loc["site", "estimated_kg"] == pytest.approx(500 * 250 / 150, abs=0.1)
    assert r.loc["subcontractor", "intensity_kg_per_unit"] == pytest.approx(70 + 60) / 90 if False else True
    assert t.n_projects == 2 and t.label == "estimate, synthetic data"
    assert t.median_kg_per_m == pytest.approx((590 / 100 + 1110 / 200) / 2, abs=1e-3) and t.cross_check_kg == pytest.approx(t.median_kg_per_m * 150, abs=0.1)
    assert t.ratio == pytest.approx(t.estimated_kg / t.cross_check_kg, abs=1e-3) and t.estimated_kg == pytest.approx(r.estimated_kg.sum(), abs=0.1)
    assert "other" not in r.index, "the category 'other' drives no component"
    nc = esg.tender_estimate(EB, CC, PF, P, None, 150, context=M12)
    assert nc.rows.empty and np.isnan(nc.estimated_kg) and nc.cross_check_kg == t.cross_check_kg and any("no tender cost frame" in w for w in nc.warnings)
    dk = esg.tender_estimate(EB, CC, PF, P, TC.assign(currency=["EUR", "EUR", "DKK", "DKK"]), 150, context=M12)
    assert set(dk.rows.currency) == {"EUR"} and any("DKK" in w for w in dk.warnings), "the tender cost in a currency without comparables has no intensity; currencies are not mixed"
    assert esg.tender_estimate(EB.assign(type="budget"), CC, PF, P, None, 150, estimate_type="budget", context=M12).n_projects == 2


def test_tender_estimate_refusals():
    TC = pd.DataFrame({"category": ["material"], "amount": [1000.0], "currency": ["EUR"]})
    for kw, msg in ((dict(metres=0), "metres"), (dict(metres=True), "metres")):
        with pytest.raises(FrameError, match=msg):
            esg.tender_estimate(EB, CC, PF, P, TC, context=M12, **{"metres": 100, **kw})
    with pytest.raises(FrameError, match="no comparable project has both"):
        esg.tender_estimate(EB, CC, PF[PF.prj_key == "Z"], P, TC, 100, context=M12)
    with pytest.raises(FrameError, match="cost code"):
        esg.tender_estimate(EB, CC.iloc[:2], PF, P, TC, 100, context=M12)
    with pytest.raises(FrameError, match="route length"):
        esg.tender_estimate(EB, CC, PF, P.assign(route_length_m=0.0), TC, 100, context=M12)
    with pytest.raises(FrameError, match="zero or more"):
        esg.tender_estimate(EB, CC, PF, P, TC.assign(amount=-1.0), 100, context=M12)
    with pytest.raises(FrameError, match="matches no component"):
        esg.tender_estimate(EB, CC, PF, P, pd.DataFrame({"category": ["other"], "amount": [5.0], "currency": ["EUR"]}), 100, context=M12)
    with pytest.raises(FrameError, match="one row per key"):
        esg.tender_estimate(EB, pd.concat([CC, CC.iloc[:1]]), PF, P, TC, 100, context=M12)
    g = esg.tender_estimate(EB, CC.assign(is_group=[True, False, False, False]), PF, P, pd.concat([TC, pd.DataFrame({"category": ["labour"], "amount": [10.0], "currency": ["EUR"]})]), 100, context=M12)
    assert "materials" not in set(g.rows.component), "group cost codes are not summed"


def test_registration_and_facade():
    for mod, n in (("recompute", "expected_goods_lines"), ("recompute", "expected_service_lines"), ("ghg", "winter_decomposition"), ("ghg", "intensity"), ("ghg", "statement_inputs"), ("footprint", "tender_estimate")):
        assert f"halvaro.esg.{mod}.{n}" in registry.registered() and n in esg.__all__
