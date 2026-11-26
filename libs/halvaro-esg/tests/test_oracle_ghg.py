"""Oracle tests of halvaro.esg.ghg: intensity, scope3_coverage, winter_decomposition.

Hand frames with the numbers written in the test, then the baseline release read directly with pandas masks and python loops; facts (the fixed EUR rate, the day of the world) are read through halvaro.core.fact.
"""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
LINE_COLS = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]
CATEGORIES = [f"3.{i}" for i in range(1, 16)]


def _lines(rows):
    return pd.DataFrame(rows, columns=LINE_COLS).astype({"supersedes_line_no": "Int64"})


def _line(le, period, scope, kg, *, ghg=None, method=None, no=1, category="c", sup=False, restated=None, replaces=None):
    return (le, period, scope, category, no, method, ghg if ghg is not None else ("1" if scope == 1 else "2" if scope == 2 else "3.1"), kg, restated, replaces, sup)


def _world_year():
    now = fact("world.now")
    return now, pd.Timestamp(now.value).year - 1


# ---- scope3_coverage


def _s3_lines(y):
    p = lambda m, yy=y: f"{yy}-{m:02d}"
    return _lines([
        _line("LE-01", p(1), 3, 100.0, ghg="3.1", no=1), _line("LE-01", p(2), 3, 50.5, ghg="3.1", no=1), _line("LE-02", p(2), 3, 0.0, ghg="3.4", no=1),
        _line("LE-01", p(3), 3, 7.0, ghg="3.10", no=1), _line("LE-01", p(3), 3, 10.12345, ghg="3.7", no=2),
        _line("LE-01", p(4), 3, 12.0, ghg="3.5", no=1, sup=True), _line("LE-01", p(4), 3, 20.0, ghg="3.5", no=2, restated="2026-01", replaces=1),
        _line("LE-01", p(1), 1, 999.0, no=1), _line("LE-01", p(1), 2, 888.0, ghg="2", method="location", no=1), _line("LE-01", p(1), 2, 777.0, ghg="2", method="market", no=2),
        _line("LE-01", p(5, y - 1), 3, 5.0, ghg="3.2", no=1)])


def test_oracle_scope3_coverage_hand_example_all_fifteen_categories():
    """route: hand lines of one year; present, line count and kilograms per category worked out by hand (one zero line, one superseded original, lines of other scopes and of the year before), reasons from the mapping given."""
    L = _s3_lines(2025)
    L0 = L.copy(deep=True)
    scr = {"3.2": "screened out: capital goods are in 3.1", "3.11": "use phase not relevant", "3.1": "must be ignored"}
    r = esg.scope3_coverage(L, scr, 2025, context=M12)
    pd.testing.assert_frame_equal(L, L0)
    v = r.value
    assert list(v.columns) == ["ghg_category", "present", "n_lines", "kgco2e", "reason"]
    assert v.ghg_category.tolist() == CATEGORIES, "fifteen rows in category order, 3.10 after 3.9"
    got = v.set_index("ghg_category")
    present = {"3.1": (2, 150.5), "3.4": (1, 0.0), "3.5": (1, 20.0), "3.7": (1, 10.123), "3.10": (1, 7.0)}
    for c in CATEGORIES:
        if c in present:
            assert bool(got.loc[c, "present"]) and (got.loc[c, "n_lines"], got.loc[c, "kgco2e"]) == (present[c][0], pytest.approx(present[c][1], abs=1e-9)), c
            assert got.loc[c, "reason"] is None, c
        else:
            assert not bool(got.loc[c, "present"]) and got.loc[c, "n_lines"] == 0 and got.loc[c, "kgco2e"] == 0.0, c
            assert got.loc[c, "reason"] == scr.get(c, "not screened: decision needed"), c
    assert str(got.n_lines.dtype).startswith("int")
    assert any("3.1" in w and "ignored" in w for w in r.warnings) and len(r.warnings) == 2, "the synthetic note and the ignored reason"
    assert not any("3.2" in w for w in r.warnings)
    plain = esg.scope3_coverage(L, None, 2025, context=M12)
    assert plain.value.reason.tolist() == [None if c in present else "not screened: decision needed" for c in CATEGORIES] and len(plain.warnings) == 1
    assert esg.scope3_coverage(L, {}, 2025, context=M12).value.equals(plain.value)


def test_oracle_scope3_coverage_basis_and_year_select_the_lines():
    """route: hand lines; the first booked basis keeps the superseded original and drops the restated line, another year has its own categories, a year without lines has none present."""
    L = _s3_lines(2025)
    first = esg.scope3_coverage(L, None, 2025, "first_booked", context=M12).value.set_index("ghg_category")
    assert (first.loc["3.5", "n_lines"], first.loc["3.5", "kgco2e"]) == (1, 12.0) and first.loc["3.1", "kgco2e"] == 150.5
    prev = esg.scope3_coverage(L, None, 2024, context=M12).value.set_index("ghg_category")
    assert prev.present.tolist().count(True) == 1 and bool(prev.loc["3.2", "present"]) and prev.loc["3.2", "kgco2e"] == 5.0 and prev.loc["3.2", "n_lines"] == 1
    assert prev.loc["3.1", "reason"] == "not screened: decision needed"
    empty = esg.scope3_coverage(L, None, 2030, context=M12).value
    assert not empty.present.any() and (empty.n_lines == 0).all() and (empty.kgco2e == 0).all() and len(empty) == 15
    now, y = _world_year()
    dflt = esg.scope3_coverage(_s3_lines(y), None, context=M12).value
    assert dflt.equals(esg.scope3_coverage(_s3_lines(y), None, y, context=M12).value) and dflt.present.sum() == 5, f"the default year is the year before world.now ({now.value})"


def test_oracle_scope3_coverage_refusals_name_the_input():
    """route: hand lines, each input the coverage cannot be worked out from and the error it must raise."""
    L = _s3_lines(2025)
    with pytest.raises(FrameError, match="mapping"):
        esg.scope3_coverage(L, 2025, context=M12)
    with pytest.raises(FrameError, match="not a scope 3 category"):
        esg.scope3_coverage(L, {"3.16": "x"}, 2025, context=M12)
    bad = pd.concat([L, _lines([_line("LE-01", "2025-06", 3, 1.0, ghg="3.16", no=9)])], ignore_index=True)
    with pytest.raises(FrameError, match="3.16"):
        esg.scope3_coverage(bad, None, 2025, context=M12)
    with pytest.raises(FrameError, match="ghg_category"):
        esg.scope3_coverage(pd.concat([L, _lines([_line("LE-01", "2025-06", 3, 1.0, ghg=None, no=9)]).assign(ghg_category=None)], ignore_index=True), None, 2025, context=M12)
    with pytest.raises(FrameError, match="null kgco2e"):
        esg.scope3_coverage(L.assign(kgco2e=[np.nan] + list(L.kgco2e[1:])), None, 2025, context=M12)
    with pytest.raises(FrameError, match="basis"):
        esg.scope3_coverage(L, None, 2025, "all", context=M12)


def test_oracle_scope3_coverage_every_route():
    """route: the hand lines, basis, year and refusal checks above. The release step (the baseline lines counted per category) is a separate test that needs the closed repository."""
    test_oracle_scope3_coverage_hand_example_all_fifteen_categories()
    test_oracle_scope3_coverage_basis_and_year_select_the_lines()
    test_oracle_scope3_coverage_refusals_name_the_input()


# ---- winter_decomposition


def _winter_hand():
    m = pd.DataFrame([("M1", "diesel", "a", "l"), ("M2", "diesel", "a", "l"), ("M3", "diesel", "b", "l"), ("M5", "diesel", "b", "l"), ("M4", "petrol", "a", "l"), ("M6", "diesel", "c", "l")],
                     columns=["mtr_key", "carrier", "kind", "unit"])
    ma = pd.DataFrame([("M1", "vehicle"), ("M1", "plant"), ("M2", "vehicle"), ("M2", "vehicle"), ("M2", "plant")], columns=["mtr_key", "asset_type"])
    rows = [("M1", "2025-12", 100.0), ("M1", "2026-01", 200.0), ("M1", "2026-02", 300.0), ("M1", "2024-12", 50.0), ("M1", "2025-01", 100.0), ("M1", "2024-11", 9999.0), ("M1", "2026-03", 9999.0), ("M1", "2025-03", 9999.0),
            ("M2", "2025-12", 10.0), ("M3", "2025-02", 40.0), ("M5", "2026-01", 25.0), ("M5", "2025-01", 0.0), ("M4", "2025-12", 5555.0), ("M6", "2023-01", 1.0)]
    c = pd.DataFrame(rows, columns=["mtr_key", "period", "quantity"]).assign(unit="l")
    return c, m, ma


def _nan_equal(a, b):
    return (pd.isna(a) and pd.isna(b)) or a == pytest.approx(b, abs=1e-9)


def test_oracle_winter_decomposition_hand_example_per_meter():
    """route: hand consumption rows with a gap, a missing window, a zero previous window and rows just outside both windows; litres, months, difference and percent written out per meter."""
    c, m, ma = _winter_hand()
    kept = [x.copy(deep=True) for x in (c, m, ma)]
    r = esg.winter_decomposition(c, m, ma, context=M12)
    for got, want in zip((c, m, ma), kept):
        pd.testing.assert_frame_equal(got, want)
    assert list(r.columns) == ["mtr_key", "kind", "asset_type", "litres_now", "litres_prev", "extra_litres", "months_now", "months_prev", "pct_change"]
    assert r.mtr_key.tolist() == ["M1", "M2", "M3", "M5"], "meters of another carrier and meters with no row in either window are left out"
    v = r.set_index("mtr_key")
    nan = float("nan")
    want = {"M1": ("a", "plant", 600.0, 150.0, 450.0, 3, 2, 300.0), "M2": ("a", "vehicle", 10.0, nan, nan, 1, 0, nan), "M3": ("b", None, nan, 40.0, nan, 0, 1, nan), "M5": ("b", None, 25.0, 0.0, 25.0, 1, 1, nan)}
    for k, (kind, asset, now, prev, extra, mn, mp, pct) in want.items():
        row = v.loc[k]
        assert row.kind == kind and (row.asset_type == asset or (asset is None and pd.isna(row.asset_type))), k
        assert _nan_equal(row.litres_now, now) and _nan_equal(row.litres_prev, prev) and _nan_equal(row.extra_litres, extra) and _nan_equal(row["pct_change"], pct), k
        assert (row.months_now, row.months_prev) == (mn, mp), k
    assert str(v.months_now.dtype).startswith("int") and str(v.months_prev.dtype).startswith("int")


def test_oracle_winter_decomposition_hand_example_by_kind_and_asset_type():
    """route: hand consumption rows; the groups by kind and by asset type counted from the rows, the months of a group being the distinct periods of its rows and not the meter months added."""
    c, m, ma = _winter_hand()
    k = esg.winter_decomposition(c, m, ma, by="kind", context=M12).set_index("kind")
    assert k.index.tolist() == ["a", "b"] and list(k.columns) == ["litres_now", "litres_prev", "extra_litres", "months_now", "months_prev", "pct_change"]
    assert k.loc["a", ["litres_now", "litres_prev", "extra_litres", "months_now", "months_prev"]].tolist() == [610.0, 150.0, 460.0, 3, 2]
    assert k.loc["a", "pct_change"] == pytest.approx(306.67, abs=1e-9)
    assert k.loc["b", ["litres_now", "litres_prev", "extra_litres", "months_now", "months_prev"]].tolist() == [25.0, 40.0, -15.0, 1, 2]
    assert k.loc["b", "pct_change"] == pytest.approx(-37.5, abs=1e-9)
    a = esg.winter_decomposition(c, m, ma, by="asset_type", context=M12)
    assert a.asset_type.tolist()[:2] == ["plant", "vehicle"] and pd.isna(a.asset_type.iloc[2]) and len(a) == 3, "meters without an asset form their own last group"
    assert a.litres_now.tolist() == pytest.approx([600.0, 10.0, 25.0]) and a.litres_prev.iloc[[0, 2]].tolist() == pytest.approx([150.0, 40.0]) and pd.isna(a.litres_prev.iloc[1])
    assert a.months_now.tolist() == [3, 1, 1] and a.months_prev.tolist() == [2, 0, 2]
    p = esg.winter_decomposition(c, m, ma, carrier="petrol", context=M12)
    assert p.mtr_key.tolist() == ["M4"] and p.litres_now.tolist() == [5555.0] and p.months_prev.tolist() == [0]


def test_oracle_winter_decomposition_windows_and_refusals():
    """route: hand rows; windows given by keyword move the months counted, and inputs the decomposition cannot be built from raise."""
    c, m, ma = _winter_hand()
    wide = esg.winter_decomposition(c, m, ma, now=("2025-12", "2026-03"), prev=("2024-11", "2025-02"), context=M12).set_index("mtr_key")
    assert wide.loc["M1", ["litres_now", "litres_prev", "months_now", "months_prev"]].tolist() == [10599.0, 10149.0, 4, 3]
    with pytest.raises(FrameError, match="same number of months"):
        esg.winter_decomposition(c, m, ma, now=("2025-12", "2026-03"), context=M12)
    with pytest.raises(FrameError, match="in order"):
        esg.winter_decomposition(c, m, ma, now=("2026-02", "2025-12"), prev=("2025-02", "2024-12"), context=M12)
    with pytest.raises(FrameError, match="by is"):
        esg.winter_decomposition(c, m, ma, by="site", context=M12)
    with pytest.raises(FrameError, match="more than one unit"):
        esg.winter_decomposition(c, m.assign(unit=["l", "kWh", "l", "l", "l", "l"]), ma, context=M12)
    with pytest.raises(FrameError, match="null quantities"):
        esg.winter_decomposition(c.assign(quantity=[np.nan] + list(c.quantity[1:])), m, ma, context=M12)
    with pytest.raises(FrameError, match="one row per meter"):
        esg.winter_decomposition(pd.concat([c, c.iloc[:1]]), m, ma, context=M12)
    none = esg.winter_decomposition(c.iloc[:0], m, ma, context=M12)
    assert none.empty and list(none.columns) == ["mtr_key", "kind", "asset_type", "litres_now", "litres_prev", "extra_litres", "months_now", "months_prev", "pct_change"]


def test_oracle_winter_decomposition_every_route():
    """route: the hand examples, windows and refusals above. The release step (the baseline consumption summed per meter, kind and asset type) is a separate test that needs the closed repository."""
    test_oracle_winter_decomposition_hand_example_per_meter()
    test_oracle_winter_decomposition_hand_example_by_kind_and_asset_type()
    test_oracle_winter_decomposition_windows_and_refusals()


# ---- intensity


def _intensity_hand(basis_lines=True):
    L = _lines([
        _line("LE-01", "2025-01", 1, 1000.0, no=1), _line("LE-01", "2025-01", 2, 500.0, ghg="2", method="location", no=2), _line("LE-01", "2025-01", 2, 200.0, ghg="2", method="market", no=3),
        _line("LE-01", "2025-02", 3, 2000.0, ghg="3.1", no=1),
        _line("LE-02", "2025-02", 1, 400.0, no=1), _line("LE-02", "2025-02", 2, 100.0, ghg="2", method="location", no=2), _line("LE-02", "2025-02", 2, 60.0, ghg="2", method="market", no=3),
        _line("LE-02", "2025-02", 3, 500.0, ghg="3.1", no=4),
        _line("LE-01", "2024-01", 1, 77.0, no=1)])
    SR = pd.DataFrame([("LE-01", "entity", 2025, 100.0, 50_000_000.0, "DKK"), ("LE-02", "entity", 2025, 20.0, 4_000_000.0, "EUR"), (None, "group", 2025, 125.0, 70_000_000.0, "DKK"),
                       ("LE-01", "entity", 2024, 90.0, 40_000_000.0, "DKK")], columns=["le_key", "scope", "fiscal_year", "average_employees", "revenue", "currency"])
    return L, SR


def test_oracle_intensity_hand_example_per_entity_and_company():
    """route: hand lines and reports; tonnes from the kilograms written out (location and market totals apart), divided by employees and by DKK million, the EUR revenue times the fixed rate read as a fact."""
    L, SR = _intensity_hand()
    L0, SR0 = L.copy(deep=True), SR.copy(deep=True)
    eur = fact("world.fx_eur_dkk_fixed")
    msg = f"fixed EUR rate used: {eur.value}"
    r = esg.intensity(L, SR, 2025, context=M12)
    pd.testing.assert_frame_equal(L, L0)
    pd.testing.assert_frame_equal(SR, SR0)
    assert r.facts_used and eur.id in [f[0] for f in r.facts_used] and r.status == "VERIFY+synthetic"
    assert list(r.value.columns) == ["le_key", "year", "months", "employees", "revenue_dkk_m", "total_location_t", "total_market_t", "t_per_employee_location", "t_per_employee_market", "t_per_dkk_m_location", "t_per_dkk_m_market"]
    v = r.value.set_index("le_key")
    assert sorted(v.index) == ["ALL", "LE-01", "LE-02"] and (v.year == 2025).all()
    assert v.loc[["LE-01", "LE-02", "ALL"], "months"].tolist() == [2, 1, 2]
    assert v.loc[["LE-01", "LE-02", "ALL"], "employees"].tolist() == [100.0, 20.0, 125.0], "the company row takes the group report"
    rev2 = 4.0 * float(eur.value)
    assert v.loc[["LE-01", "LE-02", "ALL"], "revenue_dkk_m"].tolist() == pytest.approx([50.0, round(rev2, 3), 70.0], abs=1e-9), msg
    assert v.loc[["LE-01", "LE-02", "ALL"], "total_location_t"].tolist() == pytest.approx([3.5, 1.0, 4.5]) and v.loc[["LE-01", "LE-02", "ALL"], "total_market_t"].tolist() == pytest.approx([3.2, 0.96, 4.16])
    assert v.loc["LE-01", ["t_per_employee_location", "t_per_employee_market", "t_per_dkk_m_location", "t_per_dkk_m_market"]].tolist() == pytest.approx([0.035, 0.032, 0.07, 0.064])
    assert v.loc["ALL", ["t_per_employee_location", "t_per_employee_market", "t_per_dkk_m_location", "t_per_dkk_m_market"]].tolist() == pytest.approx([0.036, 0.033, 0.064, 0.059])
    assert v.loc["LE-02", ["t_per_employee_location", "t_per_employee_market"]].tolist() == pytest.approx([0.05, 0.048])
    assert v.loc["LE-02", ["t_per_dkk_m_location", "t_per_dkk_m_market"]].tolist() == pytest.approx([round(1.0 / rev2, 3), round(0.96 / rev2, 3)], abs=1e-9), msg
    assert v.loc["ALL", "total_location_t"] == pytest.approx(v.loc["LE-01", "total_location_t"] + v.loc["LE-02", "total_location_t"]) and (v.drop(columns=["year", "months"]) > 0).all().all()


def test_oracle_intensity_basis_year_and_missing_denominators():
    """route: hand lines and reports; a restated line changes the current basis total only, a year without a report row has null denominators, zero denominators give null ratios, and the default year follows the day of the world."""
    L, SR = _intensity_hand()
    restated = pd.concat([L, _lines([_line("LE-01", "2025-01", 1, 1100.0, no=9, restated="2026-02", replaces=1)])], ignore_index=True)
    restated.loc[(restated.le_key == "LE-01") & (restated.period == "2025-01") & (restated.scope == 1) & (restated.line_no == 1), "is_superseded"] = True
    cur = esg.intensity(restated, SR, 2025, context=M12).value.set_index("le_key")
    first = esg.intensity(restated, SR, 2025, "first_booked", context=M12).value.set_index("le_key")
    assert cur.loc["LE-01", "total_location_t"] == pytest.approx(3.6) and first.loc["LE-01", "total_location_t"] == pytest.approx(3.5) and cur.loc["LE-02", "total_location_t"] == first.loc["LE-02", "total_location_t"] == pytest.approx(1.0)
    assert cur.loc["LE-01", "t_per_employee_location"] == pytest.approx(0.036) and first.loc["LE-01", "t_per_employee_location"] == pytest.approx(0.035)
    gap = esg.intensity(L, SR[SR.le_key != "LE-02"], 2025, context=M12).value.set_index("le_key")
    assert gap.loc[["LE-02"], ["employees", "revenue_dkk_m", "t_per_employee_location", "t_per_employee_market", "t_per_dkk_m_location", "t_per_dkk_m_market"]].isna().all().all()
    assert gap.loc["LE-02", "total_location_t"] == pytest.approx(1.0) and gap.loc["LE-01", "t_per_employee_location"] == pytest.approx(0.035)
    zero = esg.intensity(L, SR.assign(average_employees=[0.0, 20.0, 125.0, 90.0], revenue=[0.0, 4_000_000.0, 70_000_000.0, 40_000_000.0]), 2025, context=M12).value.set_index("le_key")
    assert zero.loc["LE-01", ["t_per_employee_location", "t_per_employee_market", "t_per_dkk_m_location", "t_per_dkk_m_market"]].isna().all() and zero.loc["LE-01", "employees"] == 0.0
    assert zero.loc["LE-02", "t_per_employee_location"] == pytest.approx(0.05)
    only24 = esg.intensity(L, SR, 2024, context=M12).value
    assert sorted(only24.le_key) == ["ALL", "LE-01"]
    assert only24.set_index("le_key").loc["LE-01", "t_per_employee_location"] == pytest.approx(0.077 / 90, abs=5e-4)
    now, y = _world_year()
    dflt = esg.intensity(_intensity_year(L, y), _intensity_year(SR, y, col="fiscal_year"), context=M12).value
    assert (dflt.year == y).all(), f"the default year is the year before world.now ({now.value})"


def _intensity_year(frame, y, col=None):
    """The frame moved from 2025 to the year y."""
    if col:
        return frame.assign(**{col: frame[col] + (y - 2025)})
    return frame.assign(period=frame.period.map(lambda p: f"{int(p[:4]) + y - 2025}{p[4:]}"))


def test_oracle_intensity_refusals_name_the_input():
    """route: hand lines and reports, each input the ratios cannot be worked out from and the error it must raise."""
    L, SR = _intensity_hand()
    with pytest.raises(FrameError, match="no emission lines"):
        esg.intensity(L, SR, 2030, context=M12)
    with pytest.raises(FrameError, match="only DKK and EUR"):
        esg.intensity(L, SR.assign(currency=["DKK", "SEK", "DKK", "DKK"]), 2025, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        esg.intensity(L, pd.concat([SR, SR.iloc[:1]]), 2025, context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        esg.intensity(L, SR.drop(columns="currency"), 2025, context=M12)
    with pytest.raises(FrameError, match="basis"):
        esg.intensity(L, SR, 2025, "all", context=M12)


def test_oracle_intensity_every_route():
    """route: the hand example, basis and year cases and refusals above. The release step (the baseline lines and reports per entity, year and basis) is a separate test that needs the closed repository."""
    test_oracle_intensity_hand_example_per_entity_and_company()
    test_oracle_intensity_basis_year_and_missing_denominators()
    test_oracle_intensity_refusals_name_the_input()
