"""Project footprint (plan 5.6): hand computed lines and projects."""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _lines():
    c = ["prj_key", "le_key", "period", "scope", "category", "line_no", "ghg_category", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]
    rows = [("P1", "LE-01", "2025-03", 3, "purchased_goods", 1, "3.1", 100.0, None, None, True), ("P1", "LE-01", "2025-03", 3, "purchased_goods", 2, "3.1", 110.0, "2026-01", 1, False),
            ("P1", "LE-01", "2025-03", 3, "purchased_services", 3, "3.1", 40.0, None, None, False), ("P1", "LE-01", "2025-03", 3, "upstream_transport", 4, "3.4", 10.0, None, None, False),
            ("P1", "LE-01", "2025-03", 1, "mobile_combustion", 5, "1", 30.0, None, None, False), ("P1", "LE-01", "2025-03", 3, "fuel_and_energy_related", 6, "3.3", 6.0, None, None, False),
            ("P2", "LE-01", "2025-04", 3, "purchased_goods", 1, "3.1", 50.0, None, None, False), (None, "LE-01", "2025-04", 2, "purchased_electricity", 1, "2", 999.0, None, None, False)]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


def test_components_from_lines_current_and_first_booked_basis():
    f = esg.project_footprint_from_lines(_lines(), context=M12).set_index(["prj_key", "period"])
    assert f.loc[("P1", "2025-03")].tolist() == [110.0, 10.0, 36.0, 40.0, 196.0], "materials, transport, site (scope 1 and 3.3), subcontractors, total; the restated line replaces its original"
    assert esg.project_footprint_from_lines(_lines(), "first_booked", context=M12).set_index(["prj_key", "period"]).loc[("P1", "2025-03"), "materials_kgco2e"] == 100.0
    assert esg.project_footprint_from_lines(_lines(), context=M12).prj_key.tolist() == ["P1", "P2"], "lines without a project (scope 2) are not project footprint"
    assert list(esg.project_footprint_from_lines(_lines(), context=M12).columns) == ["prj_key", "period", "materials_kgco2e", "transport_kgco2e", "site_kgco2e", "subcontractor_kgco2e", "total_kgco2e"]
    odd = _lines().assign(ghg_category=["3.1", "3.1", "3.1", "3.5", "1", "3.3", "3.1", "2"])
    with pytest.raises(FrameError, match="fit no component"):
        esg.project_footprint_from_lines(odd, context=M12)
    ok = esg.project_footprint_from_lines(odd, component_map={("3.5", "upstream_transport"): "transport", ("3.1", "purchased_goods"): "materials", ("3.1", "purchased_services"): "subcontractor"}, context=M12)
    assert ok.set_index(["prj_key", "period"]).loc[("P1", "2025-03"), "transport_kgco2e"] == 10.0, "the map is a keyword"
    with pytest.raises(FrameError, match="null kgco2e"):
        esg.project_footprint_from_lines(_lines().assign(kgco2e=np.nan), context=M12)
    assert esg.project_footprint_from_lines(_lines().iloc[:0], context=M12).empty


def test_scope_split_per_project_and_year():
    s = esg.project_scope_split(_lines(), 2025, context=M12).set_index("prj_key")
    assert s.loc["P1"].tolist() == [30.0, 150.0, 6.0, 10.0, 196.0] and list(s.columns) == ["scope1", "scope3_1", "scope3_3", "scope3_4", "total_kgco2e"]
    assert esg.project_scope_split(_lines(), 2024, context=M12).empty
    f = esg.project_footprint_from_lines(_lines(), context=M12)
    assert abs(s.total_kgco2e.sum() - f.total_kgco2e.sum()) < 1e-9, "the split sums to the footprints of the year"
    for y in ("2025", 2025.5, True):
        with pytest.raises(FrameError, match="year"):
            esg.project_scope_split(_lines(), y, context=M12)
    with pytest.raises(FrameError, match="split covers"):
        esg.project_scope_split(_lines().assign(ghg_category="3.5", scope=3), 2025, context=M12)


def _pf():
    return pd.DataFrame({"prj_key": ["P1", "P1", "P2", "P3"], "period": ["2025-03", "2025-04", "2025-04", "2025-04"], "materials_kgco2e": [100.0, 100.0, 10.0, 5.0], "transport_kgco2e": [10.0, 10.0, 1.0, 1.0],
                         "site_kgco2e": [20.0, 20.0, 5.0, 2.0], "subcontractor_kgco2e": [70.0, 70.0, 4.0, 2.0], "total_kgco2e": [200.0, 200.0, 20.0, 10.0]})


def _p():
    return pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "route_length_m": [1000.0, 500.0, np.nan], "start": ["2022-06-01", "2024-01-01", "2025-01-01"], "status": ["completed", "active", "completed"]})


def test_per_metre_keeps_null_lengths_and_flags_the_coverage():
    r = esg.per_metre(_pf(), _p(), context=M12)
    v = r.value.set_index("prj_key")
    assert r.status == "VERIFY+synthetic" and r.facts_used[0][0] == "world.window_start"
    assert v.loc["P1", ["total_kgco2e", "route_length_m", "kgco2e_per_m", "partial_history", "active_to_date", "length_changed"]].tolist() == [400.0, 1000.0, 0.4, True, False, False]
    assert v.loc["P2", ["kgco2e_per_m", "partial_history", "active_to_date"]].tolist() == [0.04, False, True]
    assert np.isnan(v.loc["P3", "kgco2e_per_m"]) and np.isnan(v.loc["P3", "route_length_m"]), "a null length stays null, never zero"
    rc = esg.per_metre(_pf(), _p(), pd.DataFrame({"prj_key": ["P1", "P2"], "as_built_length_m": [1200.0, 500.2]}), context=M12).value.set_index("prj_key")
    assert rc.length_changed.tolist() == [True, False, False] and rc.loc["P1", "kgco2e_per_m"] == 0.4, "the planned length stays the default; 0.2 m is no change"
    for bad, msg in ((dict(P=_p().assign(route_length_m=[1000.0, 0.0, np.nan])), "positive or null"), (dict(P=pd.concat([_p(), _p().iloc[:1]])), "one row per project"), (dict(P=_p().iloc[:2]), "not in projects.project"),
                     (dict(PF=_pf().assign(total_kgco2e=np.nan)), "null totals"), (dict(RC=pd.DataFrame({"prj_key": ["P1", "P1"], "as_built_length_m": [1.0, 2.0]})), "more than one row")):
        a = dict(PF=_pf(), P=_p(), RC=None)
        a.update(bad)
        with pytest.raises(FrameError, match=msg):
            esg.per_metre(a["PF"], a["P"], a["RC"], context=M12)


def test_limit_check_counts_both_sides_and_reports_nulls():
    pm = esg.per_metre(_pf().assign(total_kgco2e=[200.0, 200.0, 20.0, 10.0]), _p().assign(route_length_m=[4.0, 0.5, np.nan]), context=M12).value        # per metre: 100, 40, null
    cs = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P9"]})
    lc = esg.limit_check(pm, cs, 70.0, context=M12)
    assert (lc.n, lc.n_null, lc.median, lc.limit, lc.gap, lc.n_above, lc.n_below, lc.headroom_percent) == (2, 2, 70.0, 70.0, 0.0, 1, 1, 0.0), "nulls and projects outside pm are reported, not counted"
    assert esg.limit_check(pm, cs.iloc[:2], 100.0, context=M12).n_above == 0, "a value at the limit is neither above nor below"
    assert esg.limit_check(pm, cs.iloc[:2], 100.0, context=M12).n_below == 1
    for bad in (0, -1.0, np.nan, True, "90"):
        with pytest.raises(FrameError, match="limit"):
            esg.limit_check(pm, cs, bad, context=M12)
    with pytest.raises(FrameError, match="no project of the comparable set"):
        esg.limit_check(pm, cs.iloc[2:], 90.0, context=M12)
    with pytest.raises(FrameError, match="one row per project"):
        esg.limit_check(pm, pd.concat([cs, cs]), 90.0, context=M12)


def test_component_split_is_the_median_of_the_projects_with_a_length():
    P = _p().assign(route_length_m=[1000.0, 500.0, 100.0])
    c = esg.component_split(_pf(), P, pd.DataFrame({"prj_key": ["P1", "P2", "P3"]}), context=M12).set_index("component")
    assert c.loc["materials", "median_kgco2e_per_m"] == 0.05 and c.loc["materials", "n"] == 3, "materials per metre: P1 0.2, P2 0.02, P3 0.05"
    assert c.index.tolist() == ["materials", "transport", "site", "subcontractor"]
    c2 = esg.component_split(_pf(), _p(), pd.DataFrame({"prj_key": ["P1", "P2", "P3"]}), context=M12).set_index("component")
    assert c2.loc["materials", "n"] == 2 and c2.loc["materials", "median_kgco2e_per_m"] == 0.11, "the project without a length is left out"
    assert esg.component_split(_pf(), P, pd.DataFrame({"prj_key": ["P9"]}), context=M12).n.tolist() == [0, 0, 0, 0]
    with pytest.raises(FrameError, match="one row per project"):
        esg.component_split(_pf(), P, pd.DataFrame({"prj_key": ["P1", "P1"]}), context=M12)


def test_per_metre_boundaries_nullable_dtypes_and_route_change_tolerance():
    pf = _pf()
    p = _p().assign(start=["2022-12-31", "2023-01-01", "2023-01-02"], route_length_m=[1000.0, 500.0, 250.0])
    v = esg.per_metre(pf, p, context=M12).value
    assert v.partial_history.tolist() == [True, False, False], "a project that starts on world.window_start (2023-01-01) has the full history"
    assert v.prj_key.tolist() == sorted(v.prj_key), "sorted by prj_key"
    rc = lambda x: esg.per_metre(pf, p, pd.DataFrame({"prj_key": ["P1"], "as_built_length_m": [x]}), context=M12).value.set_index("prj_key").length_changed["P1"]
    assert not rc(1000.5) and rc(1000.6) and rc(999.4) and not rc(999.5), "a difference of 0.5 m is no change, more is"
    nul = _p().assign(route_length_m=pd.array([1000, 500, None], dtype="Int64"))
    assert np.isnan(esg.per_metre(pf, nul, context=M12).value.set_index("prj_key").loc["P3", "kgco2e_per_m"])
    flt = _p().assign(route_length_m=pd.array([1000.0, 500.0, None], dtype="Float64"))
    assert esg.per_metre(pf, flt, context=M12).value.set_index("prj_key").loc["P1", "kgco2e_per_m"] == 0.4
    ab = pd.DataFrame({"prj_key": ["P1", "P2"], "as_built_length_m": pd.array([1200, None], dtype="Int64")})
    assert esg.per_metre(pf, _p(), ab, context=M12).value.length_changed.tolist() == [True, False, False]
    with pytest.raises(FrameError, match="finite"):
        esg.per_metre(pf, _p().assign(route_length_m=[1000.0, 500.0, np.inf]), context=M12)


def test_limit_check_ties_headroom_sign_even_median_and_rounding():
    mk = lambda vals: pd.DataFrame({"prj_key": [f"P{i}" for i in range(len(vals))], "kgco2e_per_m": vals})
    cs = lambda n: pd.DataFrame({"prj_key": [f"P{i}" for i in range(n)]})
    lc = esg.limit_check(mk([100.0, 80.0, 60.0, 40.0]), cs(4), 50.0, context=M12)
    assert (lc.median, lc.gap, lc.headroom_percent, lc.n_above, lc.n_below, lc.n_at) == (70.0, 20.0, -40.0, 3, 1, 0), "even n: the median is the mean of the two middle values; above the limit gives a negative headroom"
    lc = esg.limit_check(mk([40.0, 60.0]), cs(2), 100.0, context=M12)
    assert (lc.median, lc.gap, lc.headroom_percent) == (50.0, -50.0, 50.0)
    t = esg.limit_check(mk([50.0, 50.0, 60.0]), cs(3), 50.0, context=M12)
    assert (t.n_above, t.n_below, t.n_at) == (1, 0, 2), "a tie is counted in n_at; the generator truth reads it as below"
    pm = esg.per_metre(_pf(), _p().assign(route_length_m=[1000.0, 500.0, 3.0]), context=M12).value        # P3: 10 / 3 = 3.333..., displayed 3.333
    one = pm[pm.prj_key == "P3"]
    assert esg.limit_check(one, pd.DataFrame({"prj_key": ["P3"]}), 3.333, context=M12).n_above == 1, "compared unrounded: 3.3333 is above 3.333"
    with pytest.raises(FrameError, match="prj_key in every row"):
        esg.limit_check(mk([1.0]).assign(prj_key=[None]), cs(1), 5.0, context=M12)
    nul = esg.limit_check(mk([np.nan, 30.0]), cs(2), 50.0, context=M12)
    assert (nul.n, nul.n_null) == (1, 1)


def test_component_split_validation_and_even_median():
    cs = pd.DataFrame({"prj_key": ["P1", "P2"]})
    P = _p().assign(route_length_m=[1000.0, 500.0, 100.0])
    c = esg.component_split(_pf(), P, cs, context=M12).set_index("component")
    assert c.loc["materials", "median_kgco2e_per_m"] == 0.11 and c.loc["materials", "n"] == 2, "(0.2 + 0.02) / 2"
    with pytest.raises(FrameError, match="positive or null"):
        esg.component_split(_pf(), P.assign(route_length_m=[1000.0, 0.0, 100.0]), cs, context=M12)
    with pytest.raises(FrameError, match="null components"):
        esg.component_split(_pf().assign(site_kgco2e=[np.nan, 20.0, 5.0, 2.0]), P, cs, context=M12)
    with pytest.raises(FrameError, match="one row per project and period"):
        esg.component_split(pd.concat([_pf(), _pf().iloc[:1]]), P, cs, context=M12)
    with pytest.raises(FrameError, match="not in projects.project"):
        esg.component_split(_pf(), P.iloc[:1], cs, context=M12)
    assert esg.component_split(_pf(), P.assign(route_length_m=pd.array([1000, 500, None], dtype="Int64")), cs, context=M12).n.tolist() == [2, 2, 2, 2]


def test_lines_with_null_project_keys_period_scope_and_nullable_scope():
    ok = _lines().assign(scope=_lines().scope.astype("Int64"))
    assert esg.project_footprint_from_lines(ok, context=M12).total_kgco2e.tolist() == [196.0, 50.0], "Int64 scope is fine"
    n = _lines().assign(kgco2e=lambda d: d.kgco2e.where(d.prj_key.notna(), np.nan))
    assert esg.project_footprint_from_lines(n, context=M12).prj_key.tolist() == ["P1", "P2"], "a null kgco2e on a line without a project does not matter"
    with pytest.raises(FrameError, match="without a period"):
        esg.project_footprint_from_lines(_lines().assign(period=lambda d: d.period.where(d.index != 2, None)), context=M12)
    with pytest.raises(FrameError, match="without a scope"):
        esg.project_scope_split(ok.assign(scope=pd.array([3, 3, pd.NA, 3, 1, 3, 3, 2], dtype="Int64")), 2025, context=M12)


def test_round2_component_map_scope_classification_ties_and_strict_numbers():
    m = {("3.1", "purchased_goods"): "material", ("3.1", "purchased_services"): "subcontractor", ("3.4", "upstream_transport"): "transport"}
    with pytest.raises(FrameError, match="component_map"):
        esg.project_footprint_from_lines(_lines(), component_map=m, context=M12)
    bad_scope = _lines().assign(scope=["3", "3", "3", "3", "zz", "3", "3", "2"])
    for call in (lambda: esg.project_footprint_from_lines(bad_scope, context=M12), lambda: esg.project_scope_split(bad_scope, 2025, context=M12)):
        with pytest.raises(FrameError, match="number"):
            call()
    with pytest.raises(FrameError, match="number"):
        esg.project_scope_split(_lines().assign(scope=True), 2025, context=M12)
    odd = _lines().assign(scope=3, ghg_category=["3.1", "3.1", "3.1", "4", "3.3", "3.3", "3.1", "2"])
    for call in (lambda: esg.project_footprint_from_lines(odd, context=M12), lambda: esg.project_scope_split(odd, 2025, context=M12)):
        with pytest.raises(FrameError):
            call()
    with pytest.raises(FrameError, match="start with the year"):
        esg.project_scope_split(_lines().assign(period=lambda d: d.period.where(d.index != 2, "03/2025")), 2025, context=M12)
    # a decimal tie through float noise
    pf = pd.DataFrame({"prj_key": ["P"] * 3, "period": ["2025-01", "2025-02", "2025-03"], "total_kgco2e": [732.724, 764.833, 757.243]})
    p = pd.DataFrame({"prj_key": ["P"], "route_length_m": [400.0], "start": ["2024-01-01"], "status": ["active"]})
    pm = esg.per_metre(pf, p, context=M12).value
    t = esg.limit_check(pm, pd.DataFrame({"prj_key": ["P"]}), 5.637, context=M12)
    assert (t.n_above, t.n_below, t.n_at) == (0, 0, 1), "2254.8 / 400 = 5.637 is a tie whatever the float noise"
    for lim in (np.float32(90.1), np.float16(90.1), True, 10 ** 400):
        with pytest.raises(FrameError, match="limit"):
            esg.limit_check(pm, pd.DataFrame({"prj_key": ["P"]}), lim, context=M12)
    for bad in ("abc", np.inf, True):
        with pytest.raises(FrameError):
            esg.component_split(_pf().assign(materials_kgco2e=[bad, 100.0, 10.0, 5.0]), _p().assign(route_length_m=1.0), pd.DataFrame({"prj_key": ["P1"]}), context=M12)
    with pytest.raises(FrameError):
        esg.per_metre(_pf().assign(total_kgco2e=["x", "y", "z", "w"]), _p(), context=M12)


def test_round2_per_metre_start_status_rounding_and_population():
    pf, p = _pf(), _p().assign(route_length_m=[1000.0, 3.0, 100.0])
    v = esg.per_metre(pf, p, context=M12).value.set_index("prj_key")
    assert v.loc["P2", "kgco2e_per_m"] == 6.667 and v.loc["P2", "per_m_exact"] == 20 / 3, "three decimals shown, the exact value kept"
    st = esg.per_metre(pf, p.assign(start=["2024-01-01", None, "2025-01-01"], status=["planned", "Active", "active"]), context=M12).value.set_index("prj_key")
    assert pd.isna(st.loc["P2", "partial_history"]) and st.loc["P1", "partial_history"] is not None
    assert st.active_to_date.tolist() == [False, False, True], "only the status active; planned and a different case are not active"
    for bad in (dict(start=[2022, 2022, 2022]), dict(start=["garbage", "2024-01-01", "2024-01-01"])):
        with pytest.raises(FrameError):
            esg.per_metre(pf, p.assign(**bad), context=M12)
    extra = pd.concat([p, p.iloc[:1].assign(prj_key="P9")])
    assert esg.per_metre(pf, extra, context=M12).value.prj_key.tolist() == ["P1", "P2", "P3"], "projects without a footprint are not listed"
    with pytest.raises(FrameError, match="one row per project"):
        esg.per_metre(pd.concat([pf, pf.iloc[:1]]), p, context=M12)
    lc = pd.DataFrame({"prj_key": ["P1", "P1"], "kgco2e_per_m": [1.0, 2.0]})
    with pytest.raises(FrameError, match="one row per project"):
        esg.limit_check(lc, pd.DataFrame({"prj_key": ["P1"]}), 5.0, context=M12)
    with pytest.raises(FrameError, match="one row per project"):
        esg.component_split(pf, pd.concat([p, p.iloc[:1]]), pd.DataFrame({"prj_key": ["P1"]}), context=M12)
    with pytest.raises(FrameError, match="prj_key in every row"):
        esg.component_split(pf, p, pd.DataFrame({"prj_key": ["P1", None]}), context=M12)
    unsorted = _lines().iloc[::-1]
    assert esg.project_footprint_from_lines(unsorted, context=M12).prj_key.tolist() == ["P1", "P2"]
    cat = _lines().assign(prj_key=_lines().prj_key.astype("category"), category=_lines().category.astype("category"))
    assert esg.project_footprint_from_lines(cat, context=M12).total_kgco2e.tolist() == [196.0, 50.0]
