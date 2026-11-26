"""Recomputation of the emission lines (plan 5.3): hand computed meters and factors, then the baseline release against the stored lines."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _f():
    cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
    rows = [("F1", "fuel_diesel", "diesel", "DK", None, 2.6, "2025-01-01", "2025-12-31", "FS-2025"), ("F2", "fuel_diesel", "diesel", "DK", None, 2.7, "2026-01-01", None, "FS-2026"),
            ("W1", "fuel_wtt_diesel", "diesel", "EU", None, 0.6, "2025-01-01", None, "FS-2025"),
            ("EL1", "electricity_grid_average", "electricity", "DK", "location", 0.1, "2025-01-01", None, "FS-2025"), ("EL2", "electricity_residual_mix", "electricity", "DK", "market", 0.3, "2025-01-01", None, "FS-2025"),
            ("EL3", "electricity_certified_renewable", "electricity", "DK", "market", 0.01, "2025-01-01", None, "FS-2025"),
            ("DH1", "district_heat_network_average", "district_heat", "DK-AARHUS", "location", 50.0, "2025-01-01", None, "FS-2025"), ("DH2", "district_heat_supplier_specific", "district_heat", "DK-AARHUS", "market", 40.0, "2025-01-01", None, "FS-2025"),
            ("G1", "waste_general", None, "EU", None, 0.5, "2025-01-01", None, "FS-2025"), ("G2", "waste_paper_cardboard", None, "EU", None, 0.1, "2025-01-01", None, "FS-2025")]
    return pd.DataFrame(rows, columns=cols)


def _m():
    cols = ["mtr_key", "carrier", "unit", "kind", "country", "site_key", "le_key"]
    return pd.DataFrame([("M1", "diesel", "l", "vehicle_pool", "DK", "SITE-01", "LE-01"), ("M2", "diesel", "l", "generator_pool", "DK", "SITE-01", "LE-01"), ("M3", "electricity", "kWh", "building", "DK", "SITE-01", "LE-01"),
                         ("M4", "district_heat", "MWh", "building", "DK", "SITE-01", "LE-01"), ("M5", "diesel", "l", "po_site_tank", "DK", "SITE-01", "LE-01")], columns=cols)


def _c():
    cols = ["mtr_key", "period", "quantity", "unit", "contract_type"]
    return pd.DataFrame([("M1", "2025-03", 100.0, "l", None), ("M2", "2025-03", 10.0, "l", None), ("M3", "2025-03", 1000.0, "kWh", "grid_mix"), ("M3", "2025-04", 1000.0, "kWh", "renewable_certified"),
                         ("M4", "2025-03", 2.0, "MWh", "supplier"), ("M5", "2025-03", 50.0, "l", None), ("M1", "2025-04", 0.0, "l", None)], columns=cols)


HR = {"SITE-01": "DK-AARHUS"}


def test_expected_lines_per_meter_month_family_and_factor_date():
    e = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, context=M12)
    by = e.set_index(["ref_key", "scope", "ghg_category", "method", "period"], drop=False)
    g = lambda *k: by.loc[k]
    assert g("M1", 1, "1", None, "2025-03") is not None
    one = e[(e.ref_key == "M1") & (e.scope == 1)].iloc[0]
    assert (one.category, one.efac_key, one.expected_kg, one.quantity, one.unit) == ("mobile_combustion", "F1", 260.0, 100.0, "l")
    assert e[(e.ref_key == "M2") & (e.scope == 1)].iloc[0].category == "stationary_combustion", "generators are stationary combustion"
    wtt = e[(e.ref_key == "M1") & (e.ghg_category == "3.3")].iloc[0]
    assert (wtt.category, wtt.efac_key, wtt.expected_kg) == ("fuel_and_energy_related", "W1", 60.0)
    el = e[e.ref_key == "M3"].set_index(["period", "method"])
    assert el.loc[("2025-03", "location"), "expected_kg"] == 100.0 and el.loc[("2025-03", "market"), ["efac_key", "expected_kg"]].tolist() == ["EL2", 300.0], "residual mix with a grid mix contract"
    assert el.loc[("2025-04", "market"), ["efac_key", "expected_kg"]].tolist() == ["EL3", 10.0], "certified renewable in the month the contract says so"
    h = e[e.ref_key == "M4"].set_index("method")
    assert h.loc["location", ["efac_key", "expected_kg", "category"]].tolist() == ["DH1", 100.0, "purchased_heat"] and h.loc["market", "expected_kg"] == 80.0
    assert "M5" not in set(e.ref_key) and not ((e.ref_key == "M1") & (e.period == "2025-04")).any(), "tank meters and months without consumption are left out"
    assert "M5" in set(esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, include_tanks=True, context=M12).ref_key)


def test_the_restated_basis_takes_the_factor_of_the_given_date():
    r = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, restate={"year": 2025, "factor_date": "2026-01-01"}, context=M12)
    one = r[(r.ref_key == "M1") & (r.scope == 1)].iloc[0]
    assert one.efac_key == "F2" and one.expected_kg == 270.0, "2025 on the FS-2026 factor"
    assert r[(r.ref_key == "M3") & (r.method == "location")].iloc[0].efac_key == "EL1", "a family with one factor is unchanged"
    for bad in ({"year": 2025}, {"year": 2025, "factor_date": "2026-01-01", "x": 1}):
        with pytest.raises(FrameError, match="restate is"):
            esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, restate=bad, context=M12)


def test_refusals():
    with pytest.raises(FrameError, match="heat_region_by_site"):
        esg.expected_lines_s123(_c(), _m(), _f(), context=M12)
    with pytest.raises(FrameError, match="heat_region_by_site"):
        esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site={"SITE-09": "X"}, context=M12)
    with pytest.raises(FrameError, match="no valid factor"):
        esg.expected_lines_s123(_c().iloc[:1].assign(period="2024-03"), _m(), _f(), heat_region_by_site=HR, context=M12)
    dup = pd.concat([_f(), _f().iloc[[0]].assign(efac_key="F9")])
    with pytest.raises(FrameError, match="more than one valid factor"):
        esg.expected_lines_s123(_c(), _m(), dup, heat_region_by_site=HR, context=M12)
    with pytest.raises(FrameError, match="another unit"):
        esg.expected_lines_s123(_c().assign(unit="MWh"), _m(), _f(), heat_region_by_site=HR, context=M12)
    with pytest.raises(FrameError, match="no factor family"):
        esg.expected_lines_s123(_c(), _m().assign(carrier=["coal"] + ["diesel"] * 4), _f(), heat_region_by_site=HR, context=M12)
    with pytest.raises(FrameError, match="one row per"):
        esg.expected_lines_s123(pd.concat([_c(), _c().iloc[:1]]), _m(), _f(), heat_region_by_site=HR, context=M12)
    assert esg.expected_lines_s123(_c().iloc[:0], _m(), _f(), context=M12).empty


def _w():
    return pd.DataFrame({"site_key": "SITE-01", "period": "2025-03", "fraction": ["general_waste", "paper_cardboard", "wood"], "tonnes": [2.0, 1.5, 0.0]})


def test_expected_waste_lines():
    e = esg.expected_waste_lines(_w(), _f(), context=M12)
    assert e[["ref_key", "subcategory", "category", "quantity", "unit", "efac_key", "expected_kg", "ghg_category"]].values.tolist() == [["SITE-01", "general_waste", "waste_generated", 2.0, "t", "G1", 1.0, "3.5"], ["SITE-01", "paper_cardboard", "waste_generated", 1.5, "t", "G2", 0.15, "3.5"]]
    with pytest.raises(FrameError, match="more than one row"):
        esg.expected_waste_lines(pd.concat([_w(), _w().iloc[:1]]), _f(), context=M12)
    with pytest.raises(FrameError, match="tonnes"):
        esg.expected_waste_lines(_w().assign(tonnes=-1.0), _f(), context=M12)
    with pytest.raises(FrameError, match="no valid factor"):
        esg.expected_waste_lines(_w().iloc[:1].assign(fraction="soil_rubble"), _f(), context=M12)
    assert esg.expected_waste_lines(_w().assign(tonnes=0.0), _f(), context=M12).empty


def _lines_for(expected):
    return expected.rename(columns={"expected_kg": "kgco2e"}).drop(columns=["efac_key", "factor"])


def test_recompute_diff_reports_both_directions_and_sums_split_lines():
    e = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, context=M12)
    lines = _lines_for(e)
    assert esg.recompute_diff(lines, e, context=M12).empty
    # scope 1 split over two projects: the sum per meter ties
    first = lines[(lines.ref_key == "M1") & (lines.scope == 1)].iloc[0]
    split = pd.concat([lines.drop(first.name), pd.DataFrame([first, first]).assign(quantity=[60.0, 40.0], kgco2e=[156.0, 104.0])], ignore_index=True)
    assert esg.recompute_diff(split, e, context=M12).empty
    d = esg.recompute_diff(lines.iloc[1:], e, context=M12)
    assert d.status.tolist() == ["missing_line"] and d.n_lines.tolist() == [0]
    extra = pd.concat([lines, lines.iloc[[0]].assign(ref_key="M9")])
    assert esg.recompute_diff(extra, e, context=M12).status.tolist() == ["missing_expected"]
    bump = lambda df, col, d: df.assign(**{col: df[col].where(df.index != df.index[0], df[col] + d)})
    q = bump(lines, "quantity", 0.009)
    assert esg.recompute_diff(q, e, context=M12).empty and esg.recompute_diff(bump(q, "quantity", 0.003), e, context=M12).status.tolist() == ["quantity"], "0.009 is inside the tolerance, 0.012 is not"
    k = bump(lines, "kgco2e", 0.0021)
    assert esg.recompute_diff(k, e, context=M12).status.tolist() == ["kg"] and esg.recompute_diff(k, e, kg_tolerance_per_line=0.003, context=M12).empty
    for kw in (dict(quantity_tolerance=-1), dict(kg_tolerance_per_line=np.nan), dict(quantity_tolerance=True)):
        with pytest.raises(FrameError, match="tolerance"):
            esg.recompute_diff(lines, e, context=M12, **kw)
    with pytest.raises(FrameError, match="lacks column"):
        esg.recompute_diff(lines.drop(columns="kgco2e"), e, context=M12)


def test_recompute_diff_full_keys_units_and_text_keys():
    e = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, context=M12)
    lines = e.rename(columns={"expected_kg": "kgco2e"}).drop(columns=["factor"])
    assert esg.recompute_diff(lines, e, context=M12).empty, "unit is compared when both frames carry it"
    u = lines.assign(unit=lines.unit.where(lines.index != 0, "kWh"))
    assert esg.recompute_diff(u, e, context=M12).status.tolist() == ["unit"]
    f = lines.assign(efac_key=lines.efac_key.where(lines.index != 0, "F2"))
    assert esg.recompute_diff(f, e, context=M12).empty, "another factor row with the same kg is no mismatch (an unchanged factor keeps its old row on restatement)"
    # null parts of any key column match each other and no row is dropped
    nulled = e.assign(category=e.category.where(e.index != 0, None))
    d = esg.recompute_diff(nulled.rename(columns={"expected_kg": "kgco2e"}), e, context=M12)
    assert sorted(d.status) == ["missing_expected", "missing_line"], "a null category is a key part, not a dropped row"
    both_null = nulled.rename(columns={"expected_kg": "kgco2e"})
    assert esg.recompute_diff(both_null, nulled, context=M12).empty
    # categorical, string-typed and float scopes tie
    cat = lines.assign(category=lines.category.astype("category"), scope=lines.scope.astype(float))
    assert esg.recompute_diff(cat, e, context=M12).empty
    for col in ("ref_key", "period", "scope"):
        with pytest.raises(FrameError, match="null"):
            esg.recompute_diff(lines.assign(**{col: lines[col].where(lines.index != 0, None)}), e, context=M12)


def test_restate_is_validated_and_period_types_and_series_regions():
    kw = dict(heat_region_by_site=HR, context=M12)
    for bad in ({}, {"year": 2025.5, "factor_date": "2026-01-01"}, {"year": 1800, "factor_date": "2026-01-01"}, {"year": True, "factor_date": "2026-01-01"}, {"year": 2025, "factor_date": "garbage"},
                {"year": 2025, "factor_date": 5}, {"year": 2025, "factor_date": "2026-01-01T00:00:00+02:00"}, "x"):
        with pytest.raises(FrameError):
            esg.expected_lines_s123(_c(), _m(), _f(), restate=bad, **kw)
    r = esg.expected_lines_s123(_c(), _m(), _f(), restate={"year": 2025, "factor_date": pd.Timestamp("2026-01-01 13:00")}, **kw)
    assert r[(r.ref_key == "M1") & (r.scope == 1)].iloc[0].efac_key == "F2", "a time of day is cut off"
    two = pd.concat([_c().iloc[:1], _c().iloc[:1].assign(period="2024-03")], ignore_index=True)
    ff = _f().assign(valid_from=lambda d: d.valid_from.where(d.valid_from != "2025-01-01", "2024-01-01"))
    other = esg.expected_lines_s123(two, _m(), ff, restate={"year": 2025, "factor_date": "2026-01-01"}, **kw)
    o1 = other[(other.ref_key == "M1") & (other.scope == 1)].set_index("period")
    assert o1.loc["2024-03", "efac_key"] == "F1" and o1.loc["2025-03", "efac_key"] == "F2", "other years keep their own factor"
    with pytest.raises(FrameError, match="no period in the data"):
        esg.expected_lines_s123(two, _m(), ff, restate={"year": 2031, "factor_date": "2026-01-01"}, **kw)
    s = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=pd.Series(HR), context=M12)
    assert len(s) == len(esg.expected_lines_s123(_c(), _m(), _f(), **kw))
    with pytest.raises(FrameError, match="mapping"):
        esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=["SITE-01"], context=M12)
    with pytest.raises(FrameError, match="factor_set"):
        esg.expected_lines_s123(_c(), _m(), _f().drop(columns="factor_set"), **kw)
    cat = _c().assign(period=_c().period.astype("category"))
    assert len(esg.expected_lines_s123(cat, _m(), _f(), **kw)) == len(esg.expected_lines_s123(_c(), _m(), _f(), **kw))


def test_factor_validity_is_inclusive_at_valid_to_and_tanks_are_optional():
    f = _f().assign(valid_to=_f().valid_to.where(_f().efac_key != "F1", "2025-03-01"))
    r = esg.expected_lines_s123(_c().iloc[:1], _m(), f, **dict(heat_region_by_site=HR, context=M12))
    assert r[r.scope == 1].iloc[0].efac_key == "F1", "valid_to is inclusive: the line of March uses the factor valid until 1 March"
    g = f.assign(valid_to=f.valid_to.where(f.efac_key != "F1", "2025-02-28"))
    with pytest.raises(FrameError, match="no valid factor"):
        esg.expected_lines_s123(_c().iloc[:1], _m(), g, heat_region_by_site=HR, context=M12)


def test_round2_key_normalisation_tolerance_boundaries_one_sided_and_inputs():
    e = esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=HR, context=M12)
    lines = _lines_for(e)
    flt = lines.assign(ghg_category=lines.ghg_category.map(lambda g: float(g) if g in ("1", "2") else g), ref_key=lines.ref_key)
    assert esg.recompute_diff(flt, e, context=M12).empty, "ghg_category 1.0 equals '1'"
    pad = lines.assign(category=lines.category + " ", ref_key=" " + lines.ref_key)
    assert esg.recompute_diff(pad, e, context=M12).empty, "spaces at the ends of a key part are ignored"
    dash = e.assign(subcategory=e.subcategory.where(e.index != 0, "-"))
    assert not esg.recompute_diff(_lines_for(dash), e, context=M12).empty, "a real '-' is not a null"
    mixed = _lines_for(e).assign(method=lambda d: d.method.where(d.method.notna(), np.nan))
    assert esg.recompute_diff(mixed, e, context=M12).empty, "None and NaN are both null"
    # one sided: a stored line below the expected one is found
    low = lines.assign(kgco2e=lambda d: d.kgco2e.where(d.index != d.index[0], d.kgco2e - 0.01))
    assert esg.recompute_diff(low, e, context=M12).status.tolist() == ["kg"]
    lowq = lines.assign(quantity=lambda d: d.quantity.where(d.index != d.index[0], d.quantity - 0.02))
    assert esg.recompute_diff(lowq, e, context=M12).status.tolist() == ["quantity"]
    # the boundary: exactly the tolerance passes whatever the magnitude
    for q in (1.0, 100.0, 0.5, 12345.67, 3.0, 7.77):
        a = e.iloc[:1].assign(quantity=q)
        assert esg.recompute_diff(a.rename(columns={"expected_kg": "kgco2e"}).assign(quantity=q + 0.01), a, context=M12).empty, q
        assert not esg.recompute_diff(a.rename(columns={"expected_kg": "kgco2e"}).assign(quantity=q + 0.0101), a, context=M12).empty, q
    k = lines.assign(kgco2e=lambda d: d.kgco2e.where(d.index != d.index[0], d.kgco2e + 0.002))
    assert esg.recompute_diff(k, e, context=M12).empty and not esg.recompute_diff(lines.assign(kgco2e=lambda d: d.kgco2e.where(d.index != d.index[0], d.kgco2e + 0.0021)), e, context=M12).empty
    # nulls, text and scope
    for col in ("kgco2e", "quantity"):
        with pytest.raises(FrameError, match="nulls"):
            esg.recompute_diff(lines.assign(**{col: lambda d: d[col].where(d.index != 0, np.nan)}), e, context=M12)
        with pytest.raises(FrameError, match="numbers"):
            esg.recompute_diff(lines.assign(**{col: lambda d: d[col].astype(object).where(d.index != 0, "x")}), e, context=M12)
    for sc in (1.5, "x", True):
        with pytest.raises(FrameError, match="scope"):
            esg.recompute_diff(lines.assign(scope=lambda d: d.scope.astype(object).where(d.index != 0, sc)), e, context=M12)
    # one sided unit
    assert esg.recompute_diff(lines.drop(columns="unit"), e, context=M12).empty


def test_round2_expected_lines_inputs_nullable_kind_contract_unit_and_regions():
    kw = dict(heat_region_by_site=HR, context=M12)
    base = esg.expected_lines_s123(_c(), _m(), _f(), **kw)
    nk = esg.expected_lines_s123(_c(), _m().assign(kind=_m().kind.astype("string")).assign(kind=lambda d: d.kind.where(d.mtr_key != "M1", pd.NA)), _f(), **kw)
    assert (nk.ref_key == "M1").sum() == (base.ref_key == "M1").sum() and nk[(nk.ref_key == "M1") & (nk.scope == 1)].category.iloc[0] == "mobile_combustion", "a null kind keeps the meter"
    assert len(esg.expected_lines_s123(_c(), _m().assign(kind=_m().kind.astype("string")), _f(), include_tanks=True, **kw)) > len(base)
    for q in (-5.0, np.nan):
        with pytest.raises(FrameError, match="quantity"):
            esg.expected_lines_s123(_c().assign(quantity=lambda d: d.quantity.where(d.index != 0, q)), _m(), _f(), **kw)
    with pytest.raises(FrameError, match="numbers"):
        esg.expected_lines_s123(_c().assign(quantity=lambda d: d.quantity.astype(object).where(d.index != 0, "5")), _m(), _f(), **kw)
    for ct in ("Renewable_Certified", " renewable_certified", "bogus"):
        with pytest.raises(FrameError, match="contract_type"):
            esg.expected_lines_s123(_c().assign(contract_type=lambda d: d.contract_type.where(d.mtr_key != "M3", ct)), _m(), _f(), **kw)
    assert len(esg.expected_lines_s123(_c().assign(contract_type=lambda d: d.contract_type.where(d.mtr_key != "M3", "spot")), _m(), _f(), contract_types=("spot", "grid_mix", "renewable_certified"), **kw)) == len(base)
    f_unit = _f().assign(unit="l")
    with pytest.raises(FrameError, match="per l"):
        esg.expected_lines_s123(_c(), _m(), f_unit, **kw)
    with pytest.raises(FrameError, match="no region"):
        esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site={"SITE-01": None}, context=M12)
    with pytest.raises(FrameError, match="twice"):
        esg.expected_lines_s123(_c(), _m(), _f(), heat_region_by_site=pd.Series(["X", "DK-AARHUS"], index=["SITE-01", "SITE-01"]), context=M12)
    with pytest.raises(FrameError, match="YYYY-MM"):
        esg.expected_lines_s123(_c().assign(period=lambda d: d.period.where(d.index != 0, "2025-3")), _m(), _f(), **kw)
    with pytest.raises(FrameError, match="tonnes"):
        esg.expected_waste_lines(_w().assign(tonnes=lambda d: d.tonnes.where(d.index != 0, np.nan)), _f(), context=M12)
    with pytest.raises(FrameError, match="restate"):
        esg.expected_lines_s123(_c(), _m(), _f(), restate={"year": 2201, "factor_date": "2026-01-01"}, **kw)
