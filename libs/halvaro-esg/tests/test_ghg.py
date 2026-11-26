"""GHG totals (plan 5.5): hand computed lines, then the baseline release against the truth (scope totals, renewable effect, winter ratio)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, fact

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _lines():
    c = ["le_key", "period", "scope", "category", "line_no", "ghg_category", "method", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]
    rows = [("LE-01", "2025-01", 1, "mobile_combustion", 1, "1", None, 100.0, None, None, True), ("LE-01", "2025-01", 1, "mobile_combustion", 2, "1", None, 110.0, "2026-01", 1, False),
            ("LE-01", "2025-02", 1, "mobile_combustion", 1, "1", None, 50.0, None, None, False),
            ("LE-01", "2025-01", 2, "purchased_electricity", 1, "2", "location", 40.0, None, None, False), ("LE-01", "2025-01", 2, "purchased_electricity", 2, "2", "market", 80.0, None, None, False),
            ("LE-01", "2025-01", 2, "purchased_heat", 3, "2", "location", 10.0, None, None, False), ("LE-01", "2025-01", 2, "purchased_heat", 4, "2", "market", 10.0, None, None, False),
            ("LE-02", "2025-02", 3, "purchased_goods", 1, "3.1", None, 1000.0, None, None, False), ("LE-02", "2025-02", 3, "fuel_and_energy_related", 2, "3.3", None, 20.0, None, None, False),
            ("LE-01", "2024-12", 1, "mobile_combustion", 1, "1", None, 7.0, None, None, False)]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


def test_scope_totals_on_one_basis_never_adding_the_two_methods():
    t = esg.scope_totals(_lines(), 2025, context=M12)
    v = t.value.set_index("le_key")
    assert t.status == "VERIFY+synthetic" and t.synthetic and "synthetic" in t.warnings[0] and t.facts_used[0][0] == "world.now"
    assert v.loc["LE-01", ["months", "scope1", "scope2_location", "scope2_market", "scope3", "total_location_based", "total_market_based"]].tolist() == [2, 160.0, 50.0, 90.0, 0.0, 210.0, 250.0]
    assert v.loc["LE-02", ["scope3", "scope3_3.1", "scope3_3.3", "total_location_based"]].tolist() == [1020.0, 1000.0, 20.0, 1020.0] and v.loc["ALL", "scope1"] == 160.0 and v.loc["ALL", "scope3"] == 1020.0
    f = esg.scope_totals(_lines(), 2025, "first_booked", context=M12).value.set_index("le_key")
    assert f.loc["LE-01", "scope1"] == 150.0, "as first booked: the original of January, not the restated line"
    assert esg.scope_totals(_lines(), 2025, le="LE-02", context=M12).value.le_key.tolist() == ["LE-02"]
    assert esg.scope_totals(_lines(), context=M12).value.year.unique().tolist() == [pd.Timestamp(fact("world.now").value).year - 1]
    assert esg.scope_totals(_lines(), 2030, context=M12).value.empty
    for y in ("2025", 2025.5, True, 1800):
        with pytest.raises(FrameError, match="year"):
            esg.scope_totals(_lines(), y, context=M12)
    with pytest.raises(FrameError, match="basis must be"):
        esg.scope_totals(_lines(), 2025, "all", context=M12)
    with pytest.raises(FrameError, match="null kgco2e"):
        esg.scope_totals(_lines().assign(kgco2e=np.nan), 2025, context=M12)
    with pytest.raises(FrameError, match="need the method"):
        esg.scope_totals(_lines().assign(method=None), 2025, context=M12)


def test_scope2_dual_scope3_categories_and_coverage():
    d = esg.scope2_dual(_lines(), 2025, context=M12).value.set_index("category")
    assert d.loc["purchased_electricity", ["location_kg", "market_kg", "market_vs_location_percent"]].tolist() == [40.0, 80.0, 100.0] and d.loc["purchased_heat", "market_vs_location_percent"] == 0.0
    with pytest.raises(FrameError, match="location or market"):
        esg.scope2_dual(_lines().assign(method=["location"] * 3 + ["avg"] * 7), 2025, context=M12)
    c3 = esg.scope3_by_category(_lines(), 2025, context=M12).value
    assert c3[["ghg_category", "category", "n_lines", "kgco2e"]].values.tolist() == [["3.1", "purchased_goods", 1, 1000.0], ["3.3", "fuel_and_energy_related", 1, 20.0]]
    cov = esg.scope3_coverage(_lines(), {"3.2": "capital goods are in 3.1"}, 2025, context=M12).value.set_index("ghg_category")
    assert cov.loc["3.1", ["present", "n_lines", "kgco2e", "reason"]].tolist()[:3] == [True, 1, 1000.0] and cov.loc["3.1", "reason"] is None
    assert cov.loc["3.2", "reason"] == "capital goods are in 3.1" and cov.loc["3.4", "reason"] == "not screened: decision needed" and len(cov) == 15
    for bad, msg in (({"4.1": "x"}, "not a scope 3 category"),):
        with pytest.raises(FrameError, match=msg):
            esg.scope3_coverage(_lines(), bad, 2025, context=M12)
    with pytest.raises(FrameError, match="not a scope 3 category"):
        esg.scope3_coverage(_lines().assign(ghg_category=["1"] * 7 + ["3.99", "3.3", "1"]), None, 2025, context=M12)


def _monthly():
    rows = []
    for i in range(1, 13):
        p = f"2025-{i:02d}"
        rows += [("LE-01", p, 2, "purchased_electricity", i * 10 + 1, "2", "location", 100.0, None, None, False), ("LE-01", p, 2, "purchased_electricity", i * 10 + 2, "2", "market", 120.0, None, None, False),
                 ("LE-01", p, 2, "purchased_heat", i * 10 + 3, "2", "location", 50.0, None, None, False), ("LE-01", p, 2, "purchased_heat", i * 10 + 4, "2", "market", 50.0, None, None, False)]
    for p in ("2026-01", "2026-02"):
        rows += [("LE-01", p, 2, "purchased_electricity", 1, "2", "location", 100.0, None, None, False), ("LE-01", p, 2, "purchased_electricity", 2, "2", "market", 30.0, None, None, False),
                 ("LE-01", p, 2, "purchased_heat", 3, "2", "location", 50.0, None, None, False), ("LE-01", p, 2, "purchased_heat", 4, "2", "market", 50.0, None, None, False)]
    c = ["le_key", "period", "scope", "category", "line_no", "ghg_category", "method", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


def test_renewable_effect_windows_from_the_data_and_explicit():
    C = pd.DataFrame({"period": [f"2025-{i:02d}" for i in range(1, 13)] + ["2026-01", "2026-02"], "contract_type": ["grid_mix"] * 12 + ["renewable_certified"] * 2})
    r = esg.renewable_effect(_monthly(), C, context=M12).value.set_index("measure")
    assert r.loc["market_electricity", ["avg_before_kg", "avg_after_kg", "change_percent", "months_before", "months_after"]].tolist() == [120.0, 30.0, -75.0, 12, 2]
    assert r.loc["location_electricity", "change_percent"] == 0.0 and r.loc["market_all", "change_percent"] == round((80 / 170 - 1) * 100, 3) and r.loc["location_all", "avg_after_kg"] == 150.0
    e = esg.renewable_effect(_monthly(), C, before=("2025-07", "2025-12"), after=("2026-01", "2026-02"), context=M12).value
    assert e.months_before.unique().tolist() == [6]
    only_before = esg.renewable_effect(_monthly(), C, before=("2025-07", "2025-12"), context=M12).value
    assert only_before.months_before.unique().tolist() == [6], "an explicit before window is used, the after window comes from the data"
    for kw, msg in ((dict(before=("2025-12", "2026-01"), after=("2026-01", "2026-02")), "overlap"), (dict(before=("2025-12", "2025-01"), after=("2026-01", "2026-02")), "in order"),
                    (dict(before=("2024-01", "2024-12"), after=("2026-01", "2026-02")), "0 of 12 months"), (dict(before=("2025-07", "2025-12"), after=("2026-01", "2026-12")), "2 of 12 months")):
        with pytest.raises(FrameError, match=msg):
            esg.renewable_effect(_monthly(), C, context=M12, **kw)
    with pytest.raises(FrameError, match="no consumption on a renewable_certified"):
        esg.renewable_effect(_monthly(), C.assign(contract_type="grid_mix"), context=M12)


def test_review_stale_originals_missing_method_months_nulls_and_unknown_categories():
    C = pd.DataFrame({"period": [f"2025-{i:02d}" for i in range(1, 13)] + ["2026-01", "2026-02"], "contract_type": ["grid_mix"] * 12 + ["renewable_certified"] * 2})
    L = _lines()
    stale = L.assign(is_superseded=[False] + L.is_superseded.tolist()[1:])
    for call in (lambda: esg.scope_totals(stale, 2025, context=M12), lambda: esg.winter_ratio(stale, prev=("2024-12", "2025-01"), now=("2025-12", "2026-01"), context=M12)):
        with pytest.raises(FrameError, match="not flagged is_superseded|scope 1 lines"):
            call()
    unlinked = L.assign(supersedes_line_no=pd.array([pd.NA] * len(L), dtype="Int64"))
    with pytest.raises(FrameError, match="no supersedes_line_no"):
        esg.scope_totals(unlinked, 2025, context=M12)
    M = _monthly()
    no_market = M[~((M.period == "2026-01") & (M.method == "market") & (M.category == "purchased_electricity"))]
    with pytest.raises(FrameError, match="market purchased_electricity lines for 1 of 2 months"):
        esg.renewable_effect(no_market, C, context=M12)
    with pytest.raises(FrameError, match="null kgco2e"):
        esg.renewable_effect(M.assign(kgco2e=M.kgco2e.where(M.index != 0, np.nan)), C, context=M12)
    nul = _lines().assign(kgco2e=lambda d: d.kgco2e.where(d.index != 2, np.nan))
    with pytest.raises(FrameError, match="null kgco2e"):
        esg.winter_ratio(nul, prev=("2024-12", "2025-01"), now=("2025-12", "2026-01"), context=M12)
    with pytest.raises(FrameError, match="not a scope 3 category"):
        esg.scope_totals(_lines().assign(ghg_category=lambda d: d.ghg_category.where(d.index != 7, "3.16")), 2025, context=M12)


def test_winter_ratio_on_both_bases():
    L = _lines()
    L = pd.concat([L, L.iloc[[2]].assign(period="2026-01", line_no=9), L.iloc[[2]].assign(period="2026-02", line_no=10)], ignore_index=True)
    w = esg.winter_ratio(L, prev=("2025-01", "2025-02"), now=("2026-01", "2026-02"), context=M12).value.set_index("basis")
    assert w.loc["current", ["scope1_prev_kg", "scope1_now_kg", "ratio"]].tolist() == [160.0, 100.0, 0.625] and w.loc["first_booked", "scope1_prev_kg"] == 150.0 and w.loc["first_booked", "ratio"] == 0.667
    for bad in (("2025-02", "2025-01"), ("2025", "2026"), ("2025-01",)):
        with pytest.raises(FrameError):
            esg.winter_ratio(L, prev=bad, context=M12)
    for prev, now, msg in ((("2020-01", "2020-02"), ("2026-01", "2026-02"), "prev window"), (("2025-01", "2025-02"), ("2026-01", "2026-03"), "same number of months"), (("2025-01", "2025-02"), ("2026-01", "2026-04"), "same number")):
        with pytest.raises(FrameError, match=msg):
            esg.winter_ratio(L, prev=prev, now=now, context=M12)


def test_review_cases_silent_drops_ordering_entities_and_dtypes():
    L = _lines()
    for bad, msg in ((L.assign(ghg_category=[g if s != 3 else None for g, s in zip(L.ghg_category, L.scope)]), "without a ghg_category"), (L.assign(method=["Location"] * 10), "need the method"),
                     (L.assign(scope=[1, 1, 7] + [1] * 7), "scopes are 1, 2 and 3")):
        with pytest.raises(FrameError, match=msg):
            esg.scope_totals(bad, 2025, context=M12)
        with pytest.raises(FrameError, match=msg):
            esg.scope3_by_category(bad, 2025, context=M12)
    assert esg.scope_totals(L, 2025, le="ALL", context=M12).value.le_key.tolist() == ["ALL"] and esg.scope_totals(L, 2025, le="LE-01", context=M12).value.le_key.tolist() == ["LE-01"]
    with pytest.raises(FrameError, match="no lines of the entity"):
        esg.scope_totals(L, 2025, le="LE-09", context=M12)
    many = pd.concat([L, L.iloc[[7]].assign(ghg_category="3.10", line_no=50, kgco2e=1.0), L.iloc[[7]].assign(ghg_category="3.2", line_no=51, kgco2e=2.0)], ignore_index=True)
    cols = [c for c in esg.scope_totals(many, 2025, context=M12).value.columns if c.startswith("scope3_")]
    assert cols == ["scope3_3.1", "scope3_3.2", "scope3_3.3", "scope3_3.10"], "categories in their natural order, 3.10 after 3.3"
    assert esg.scope3_by_category(many, 2025, context=M12).value.ghg_category.tolist() == ["3.1", "3.2", "3.3", "3.10"]
    v = esg.scope_totals(many, 2025, context=M12).value.set_index("le_key")
    assert v.loc["LE-01", "scope3_3.1"] == 0.0, "a category the entity has no line in is 0"
    cat = L.assign(le_key=L.le_key.astype("category"), category=L.category.astype("category"), ghg_category=L.ghg_category.astype("category"), method=L.method.astype("category"))
    assert esg.scope2_dual(cat, 2025, context=M12).value.shape[0] == 2 and len(esg.scope3_by_category(cat, 2025, context=M12).value) == 2
    only_loc = esg.scope2_dual(L[~((L.category == "purchased_electricity") & (L.method == "market"))], 2025, context=M12).value.set_index("category")
    assert np.isnan(only_loc.loc["purchased_electricity", "market_kg"]) and np.isnan(only_loc.loc["purchased_electricity", "market_vs_location_percent"]), "a missing method is null, not 0"
    with pytest.raises(FrameError, match="mapping"):
        esg.scope3_coverage(_lines(), 2025, context=M12)
    c = esg.scope3_coverage(L, {"3.1": "x"}, 2025, context=M12)
    assert c.warnings[-1].startswith("screening gives a reason for 3.1")
