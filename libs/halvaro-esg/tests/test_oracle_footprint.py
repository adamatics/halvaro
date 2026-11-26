"""Oracle tests of halvaro.esg.footprint: tender_estimate.

Hand worked example with every kilogram, cost and length written in the test, then properties: the parts add up to the footprint of the comparables, the estimate is linear in the tender cost, the inputs stay as they were.
"""
import math

import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
COMP = ["materials_kgco2e", "transport_kgco2e", "site_kgco2e", "subcontractor_kgco2e"]


def _inputs():
    cc = pd.DataFrame([("CST-MAT", "material", False), ("CST-LAB", "labour", False), ("CST-EQP", "equipment", False), ("CST-SUB", "subcontractor", False), ("CST-OTH", "other", False),
                       ("CST-GRP", "material", True)], columns=["cst_key", "category", "is_group"])
    eb = pd.DataFrame([
        ("P1", "tender", "CST-MAT", 1000.0, "DKK"), ("P1", "tender", "CST-LAB", 400.0, "DKK"), ("P1", "tender", "CST-EQP", 100.0, "DKK"), ("P1", "tender", "CST-SUB", 500.0, "DKK"),
        ("P1", "tender", "CST-OTH", 700.0, "DKK"), ("P1", "tender", "CST-GRP", 9999.0, "DKK"), ("P1", "budget", "CST-MAT", 5000.0, "DKK"),
        ("P2", "tender", "CST-MAT", 2000.0, "DKK"), ("P2", "tender", "CST-MAT", 1000.0, "DKK"), ("P2", "tender", "CST-LAB", 600.0, "DKK"),
        ("P3", "tender", "CST-MAT", 200.0, "EUR"), ("P3", "tender", "CST-SUB", 100.0, "EUR"),
        ("P4", "tender", "CST-MAT", 777.0, "DKK"),
        ("P6", "tender", "CST-MAT", 100.0, "EUR")], columns=["prj_key", "type", "cst_key", "amount", "currency"])
    pf = pd.DataFrame([
        ("P1", "2024-01", 500.0, 120.0, 200.0, 150.0, 970.0), ("P1", "2024-02", 300.0, 80.0, 100.0, 100.0, 580.0),
        ("P2", "2024-01", 1200.0, 300.0, 150.0, 0.0, 1650.0),
        ("P3", "2024-01", 50.0, 10.0, 5.0, 20.0, 85.0),
        ("P5", "2024-01", 9999.0, 0.0, 0.0, 0.0, 9999.0),
        ("P6", "2024-01", 20.0, 5.0, 0.0, 0.0, 25.0)], columns=["prj_key", "period", *COMP, "total_kgco2e"])
    p = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5", "P6"], "route_length_m": [1000.0, 500.0, 100.0, 800.0, 100.0, float("nan")]})
    tc = pd.DataFrame([("material", 2000.0, "DKK"), ("labour", 300.0, "DKK"), ("equipment", 100.0, "DKK"), ("subcontractor", 800.0, "DKK"), ("other", 5000.0, "DKK"),
                       ("material", 10.0, "EUR"), ("labour", 50.0, "EUR"), ("material", 500.0, "SEK")], columns=["category", "amount", "currency"])
    return eb, cc, pf, p, tc


def _est(*args, **kw):
    return esg.tender_estimate(*args, context=M12, **kw)


def test_oracle_tender_estimate_hand_example_rows_and_cross_check():
    """route: hand worked example; kilograms per cost unit from the comparables written out (DKK materials 2500 over 4000, site 450 over 1100, subcontractor 250 over 500, EUR materials 85 over 300), times the tender cost."""
    eb, cc, pf, p, tc = _inputs()
    kept = [x.copy(deep=True) for x in (eb, cc, pf, p, tc)]
    r = _est(eb, cc, pf, p, tc, 2000.0)
    for got, want in zip((eb, cc, pf, p, tc), kept):
        pd.testing.assert_frame_equal(got, want)
    assert list(r.rows.columns) == ["component", "currency", "intensity_kg_per_unit", "tender_cost", "estimated_kg"]
    rows = r.rows.set_index(["component", "currency"])
    want = {("materials", "DKK"): (2500 / 4000, 2000.0, 1250.0), ("site", "DKK"): (450 / 1100, 400.0, 163.6), ("subcontractor", "DKK"): (250 / 500, 800.0, 400.0), ("materials", "EUR"): (85 / 300, 10.0, 2.8)}
    assert set(rows.index) == set(want), "transport is not a row of its own; a component without a tender cost or without a comparable cost in the currency has no row; the SEK cost has no comparable"
    assert rows.estimated_kg.notna().all() and rows.intensity_kg_per_unit.notna().all()
    for k, (intensity, cost, kg) in want.items():
        assert rows.loc[k, "intensity_kg_per_unit"] == pytest.approx(intensity, abs=1e-6), k
        assert rows.loc[k, "tender_cost"] == pytest.approx(cost) and rows.loc[k, "estimated_kg"] == pytest.approx(kg, abs=1e-9), k
    assert r.estimated_kg == pytest.approx(1816.4, abs=1e-9) and r.estimated_kg == pytest.approx(rows.estimated_kg.sum(), abs=0.05)
    assert r.n_projects == 4, "P1, P2, P3 and P6 have an estimate and a footprint; P4 has no footprint and P5 no estimate"
    assert r.median_kg_per_m == pytest.approx(1.55) and r.metres == 2000.0, "median of 1.55, 3.3 and 0.85: the project without a length is left out, and the median is not the mean"
    assert r.cross_check_kg == pytest.approx(3100.0) and r.ratio == pytest.approx(0.586, abs=1e-9)
    assert r.label == "estimate, synthetic data"
    assert len(r.warnings) == 2 and "not a measurement" in r.warnings[0] and "SEK" in r.warnings[1]


def test_oracle_tender_estimate_without_a_tender_cost_gives_the_cross_check_only():
    """route: hand example; with no cost frame the rows are empty, the estimate and ratio are null and the cross-check is the median kg per metre times the metres."""
    eb, cc, pf, p, _ = _inputs()
    r = _est(eb, cc, pf, p, None, 500.0)
    assert r.rows.empty and list(r.rows.columns) == ["component", "currency", "intensity_kg_per_unit", "tender_cost", "estimated_kg"]
    assert math.isnan(r.estimated_kg) and math.isnan(r.ratio)
    assert r.median_kg_per_m == pytest.approx(1.55) and r.cross_check_kg == pytest.approx(775.0) and r.metres == 500.0 and r.n_projects == 4
    assert any("no tender cost frame" in w for w in r.warnings)


def test_oracle_tender_estimate_parts_add_up_to_the_footprint_of_the_comparables():
    """route: property; a tender that costs what the comparables cost, category by category, is estimated at exactly the footprint of the comparables (materials with transport, site, subcontractor)."""
    eb, cc, pf, p, _ = _inputs()
    two = ["P1", "P2"]
    eb2, pf2 = eb[eb.prj_key.isin(two)], pf[pf.prj_key.isin(two)]
    lines = eb2[(eb2.type == "tender") & (eb2.cst_key != "CST-GRP")].merge(cc[["cst_key", "category"]], on="cst_key")
    spent = lines.groupby(["category", "currency"], as_index=False).amount.sum()
    r = _est(eb2, cc, pf2, p, spent, 1000.0)
    footprint = pf2[COMP].sum().sum()
    assert footprint == pf2.total_kgco2e.sum() == 3200.0, "the example footprints are consistent"
    assert r.estimated_kg == pytest.approx(footprint, abs=0.15), "the cost of the other category drives no component"
    rows = r.rows.set_index("component").estimated_kg
    assert rows["materials"] == pytest.approx(pf2.materials_kgco2e.sum() + pf2.transport_kgco2e.sum(), abs=0.05)
    assert rows["site"] == pytest.approx(pf2.site_kgco2e.sum(), abs=0.05) and rows["subcontractor"] == pytest.approx(pf2.subcontractor_kgco2e.sum(), abs=0.05)
    assert r.n_projects == 2 and r.median_kg_per_m == pytest.approx(2.425)


def test_oracle_tender_estimate_is_linear_in_the_tender_cost_and_keeps_currencies_apart():
    """route: property; doubling every tender cost doubles each row within the rounding of the one decimal kept, and a tender cost in one currency never produces a row in another."""
    eb, cc, pf, p, tc = _inputs()
    one = _est(eb, cc, pf, p, tc, 2000.0).rows.set_index(["component", "currency"])
    two = _est(eb, cc, pf, p, tc.assign(amount=tc.amount * 2), 2000.0).rows.set_index(["component", "currency"])
    assert list(two.index) == list(one.index)
    for k in one.index:
        assert two.loc[k, "tender_cost"] == pytest.approx(2 * one.loc[k, "tender_cost"])
        assert two.loc[k, "estimated_kg"] == pytest.approx(2 * one.loc[k, "estimated_kg"], abs=0.15), k
        assert two.loc[k, "intensity_kg_per_unit"] == one.loc[k, "intensity_kg_per_unit"], "the intensity does not depend on the tender"
    eur_only = _est(eb, cc, pf, p, tc[tc.currency == "EUR"], 2000.0)
    assert set(eur_only.rows.currency) == {"EUR"} and eur_only.estimated_kg == pytest.approx(2.8, abs=1e-9)
    assert eur_only.cross_check_kg == _est(eb, cc, pf, p, tc, 2000.0).cross_check_kg, "the cross-check does not depend on the tender cost"
    longer = _est(eb, cc, pf, p, tc, 4000.0)
    assert longer.cross_check_kg == pytest.approx(6200.0) and longer.estimated_kg == pytest.approx(1816.4) and longer.ratio == pytest.approx(0.293, abs=1e-9)


def test_oracle_tender_estimate_estimate_type_and_category_map_are_keywords():
    """route: hand example; the lines of another estimate type, and a category map that moves 'other' to the site component, change the numbers as worked out by hand."""
    eb, cc, pf, p, tc = _inputs()
    b = _est(eb, cc, pf, p, pd.DataFrame([("material", 100.0, "DKK")], columns=["category", "amount", "currency"]), 100.0, estimate_type="budget")
    assert b.n_projects == 1 and b.rows.estimated_kg.tolist() == pytest.approx([20.0]), "P1 budget: (500 + 300 + 120 + 80) kg over 5000 per unit"
    assert b.median_kg_per_m == pytest.approx(1.55) and b.cross_check_kg == pytest.approx(155.0) and b.ratio == pytest.approx(0.129, abs=1e-9)
    moved = {"material": "materials", "labour": "site", "equipment": "site", "subcontractor": "subcontractor", "other": "site"}
    m = _est(eb, cc, pf, p, tc, 2000.0, component_of_category=moved).rows.set_index(["component", "currency"])
    assert m.loc[("site", "DKK"), "intensity_kg_per_unit"] == pytest.approx(450 / 1800, abs=1e-6), "site cost of the comparables: 400 + 100 + 700 + 600"
    assert m.loc[("site", "DKK"), "tender_cost"] == 5400.0 and m.loc[("site", "DKK"), "estimated_kg"] == pytest.approx(1350.0)


def test_oracle_tender_estimate_refusals_name_the_input():
    """route: hand inputs the estimate cannot be worked out from, and the error it must raise."""
    eb, cc, pf, p, tc = _inputs()
    for bad in (0, -5.0, True, float("nan"), float("inf")):
        with pytest.raises(FrameError, match="metres"):
            _est(eb, cc, pf, p, tc, bad)
    with pytest.raises(FrameError, match="no comparable project has both"):
        _est(eb[eb.prj_key == "P4"], cc, pf, p, tc, 100.0)
    with pytest.raises(FrameError, match="cost code"):
        _est(eb.assign(cst_key=["CST-ZZZ"] + list(eb.cst_key[1:])), cc, pf, p, tc, 100.0)
    with pytest.raises(FrameError, match="zero or more"):
        _est(eb, cc, pf, p, tc.assign(amount=[-1.0] + list(tc.amount[1:])), 100.0)
    with pytest.raises(FrameError, match="matches no component"):
        _est(eb, cc, pf, p, pd.DataFrame([("other", 10.0, "DKK")], columns=["category", "amount", "currency"]), 100.0)
    with pytest.raises(FrameError, match="one row per key"):
        _est(eb, pd.concat([cc, cc.iloc[:1]]), pf, p, tc, 100.0)
    with pytest.raises(FrameError, match="lacks column"):
        _est(eb.drop(columns="amount"), cc, pf, p, tc, 100.0)


def test_oracle_tender_estimate_every_route():
    """route: the hand worked example, the cross-check only case, the conservation and linearity properties, the keyword checks and the refusals above, run together."""
    test_oracle_tender_estimate_hand_example_rows_and_cross_check()
    test_oracle_tender_estimate_without_a_tender_cost_gives_the_cross_check_only()
    test_oracle_tender_estimate_parts_add_up_to_the_footprint_of_the_comparables()
    test_oracle_tender_estimate_is_linear_in_the_tender_cost_and_keeps_currencies_apart()
    test_oracle_tender_estimate_estimate_type_and_category_map_are_keywords()
    test_oracle_tender_estimate_refusals_name_the_input()
