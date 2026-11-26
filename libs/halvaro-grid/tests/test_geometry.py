"""Geometry versions, route change, element age, condition class (plan 5.5): hand computed frames."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def test_parse_geom_reads_points_lines_and_polygons_without_a_geometry_library():
    s = pd.Series(["POINT (10 20)", "LINESTRING (0 0, 3 4, 3 10)", "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (2 2, 4 2, 4 4, 2 4, 2 2))", "LINESTRING (0 0, 0 0)"], index=[5, 6, 7, 8])
    r = grid.parse_geom(s, context=M12)
    assert r.index.tolist() == [5, 6, 7, 8] and r.kind.tolist() == ["POINT", "LINESTRING", "POLYGON", "LINESTRING"]
    assert r.length_m.iloc[1] == 11.0 and r.length_m.iloc[3] == 0.0 and np.isnan(r.length_m.iloc[0]) and np.isnan(r.length_m.iloc[2]), "planar length of lines only"
    assert r.area_m2.iloc[2] == 96.0 and np.isnan(r.area_m2.iloc[1]), "a hole is subtracted"
    assert r.loc[6, ["x_min", "y_min", "x_max", "y_max", "n_points"]].tolist() == [0.0, 0.0, 3.0, 10.0, 3] and grid.parse_geom(pd.Series(dtype=object), context=M12).empty
    assert grid.parse_geom(pd.Series(["LINESTRING (1.5e3 -2.25, 1501.5 -2.25)"]), context=M12).length_m.iloc[0] == 1.5, "decimals, signs and exponents"
    for bad in ("LINESTRING (0 0, 1)", "MULTIPOINT (1 1)", "POINT EMPTY", None, "POLYGON ()"):
        with pytest.raises(FrameError):
            grid.parse_geom(pd.Series([bad]), context=M12)
    with pytest.raises(FrameError, match="Series"):
        grid.parse_geom(["POINT (1 1)"], context=M12)


def _gv(rows):
    return pd.DataFrame(rows, columns=["net_key", "valid_from", "valid_to", "is_current", "geom"])


def test_geometry_as_of_inclusive_end_open_end_and_one_row_per_element():
    gv = _gv([("N1", "2020-01-01", "2025-11-30", False, "old"), ("N1", "2025-12-01", None, True, "new"), ("N2", "2026-02-01", None, True, "future"), ("N3", "2019-01-01", None, True, "only")])
    on = lambda d: grid.geometry_as_of(gv, d, context=M12).set_index("net_key").geom.to_dict()
    assert on("2025-11-30") == {"N1": "old", "N3": "only"}, "valid_to is inclusive, N2 is not built yet"
    assert on("2025-12-01") == {"N1": "new", "N3": "only"} and on("2026-02-01") == {"N1": "new", "N2": "future", "N3": "only"}
    assert on("2018-12-31") == {} and on(pd.Timestamp("2030-01-01")) == {"N1": "new", "N2": "future", "N3": "only"}
    assert grid.geometry_as_of(gv, context=M12).net_key.tolist() == ["N1", "N2", "N3"], "the date defaults to world.now (2026-11-30)"
    with pytest.raises(FrameError, match="more than one version"):
        grid.geometry_as_of(gv.assign(valid_to=[None, None, None, None]), "2026-01-01", context=M12)
    for bad in (2025, "garbage"):
        with pytest.raises(FrameError):
            grid.geometry_as_of(gv, bad, context=M12)


def test_validate_versions_finds_gaps_overlaps_and_current_problems():
    ok = _gv([("N1", "2020-01-01", "2025-11-30", False, "a"), ("N1", "2025-12-01", None, True, "b"), ("N2", "2019-01-01", None, True, "c")])
    ge = pd.DataFrame({"net_key": ["N1", "N2"], "current_geometry_valid_from": ["2025-12-01", "2019-01-01"]})
    assert grid.validate_versions(ok, ge, context=M12).empty
    rules = lambda gv, g=None: sorted(set(grid.validate_versions(gv, g, context=M12).rule))
    assert rules(_gv([("N1", "2020-01-01", "2025-11-29", False, "a"), ("N1", "2025-12-01", None, True, "b")])) == ["gap"], "a day is missing"
    assert rules(_gv([("N1", "2020-01-01", "2025-12-01", False, "a"), ("N1", "2025-12-01", None, True, "b")])) == ["overlap"]
    assert rules(_gv([("N1", "2020-01-01", None, False, "a"), ("N1", "2025-12-01", None, True, "b")])) == ["open_not_last"]
    assert rules(_gv([("N1", "2020-01-01", "2019-01-01", True, "a")])) == ["current_not_open", "reversed"]
    assert rules(_gv([("N1", "2020-01-01", None, False, "a")])) == ["no_current"] and rules(_gv([("N1", "2020-01-01", "2020-12-31", True, "a"), ("N1", "2021-01-01", None, True, "b")])) == ["several_current"]
    assert rules(ok, ge.assign(current_geometry_valid_from=["2025-12-02", "2019-01-01"])) == ["current_start_mismatch"]
    assert rules(ok, pd.concat([ge, ge.iloc[:1].assign(net_key="N9")])) == ["element_without_version"]
    with pytest.raises(FrameError, match="null net_key"):
        grid.validate_versions(ok.assign(net_key=[None, "N1", "N2"]), context=M12)


def _pa():
    c = ["prj_key", "kind", "version", "valid_from", "valid_to", "length_m"]
    return pd.DataFrame([("P1", "work_area", 1, "2025-04-01", None, np.nan), ("P1", "planned_route", 2, "2025-01-24", "2025-11-30", 5200.2), ("P1", "as_built_route", 3, "2025-12-01", None, 6100.5),
                         ("P2", "planned_route", 2, "2025-01-01", None, 1000.0), ("P3", "planned_route", 2, "2025-01-01", None, 800.0), ("P3", "as_built_route", 3, "2025-06-01", None, 800.3)], columns=c)


def test_route_change_for_the_delivery_frame():
    r = grid.route_change(_pa(), context=M12).set_index("prj_key")
    assert r.loc["P1", ["planned_length_m", "as_built_length_m", "delta_m", "delta_percent", "changed"]].tolist() == [5200.2, 6100.5, 900.3, 17.313, True]
    assert str(r.loc["P1", "planned_valid_to"].date()) == "2025-11-30" and str(r.loc["P1", "as_built_valid_from"].date()) == "2025-12-01"
    assert np.isnan(r.loc["P2", "as_built_length_m"]) and not r.loc["P2", "changed"], "a project without an as-built route has no change"
    assert not r.loc["P3", "changed"] and grid.route_change(_pa(), tolerance_m=0.1, context=M12).set_index("prj_key").loc["P3", "changed"], "0.3 m is inside the default tolerance"
    assert "as_built_length_m" in r.columns and "planned_length_m" in r.columns
    for bad, msg in ((pd.concat([_pa(), _pa().iloc[[1]]]), "more than one planned"), (pd.concat([_pa(), _pa().iloc[[2]]]), "more than one as-built"), (_pa().assign(length_m=[np.nan] * 6), "without a length_m")):
        with pytest.raises(FrameError, match=msg):
            grid.route_change(bad, context=M12)
    with pytest.raises(FrameError, match="tolerance_m"):
        grid.route_change(_pa(), tolerance_m=-1, context=M12)
    assert grid.route_change(_pa().iloc[:0], context=M12).empty


def test_element_age_and_condition_class():
    ge = pd.DataFrame({"install_year": [2000, 2020, np.nan, 2010, 2030], "status": ["in_service", "in_service", "in_service", "planned", "in_service"],
                       "commissioned_date": ["2000-07-01", None, None, None, "2030-01-01"]})
    a = grid.element_age(ge, "2026-07-01", context=M12)
    assert a.name == "age_years" and a.tolist()[0] == 26.0 and a.iloc[1] == round((pd.Timestamp("2026-07-01") - pd.Timestamp("2020-01-01")).days / 365.25, 2) and a.isna().tolist()[2:] == [True, True, True], \
        "commissioning date first, else 1 January of the install year; null when not in service, without a year or commissioned later"
    assert grid.element_age(ge, context=M12).iloc[0] == round((pd.Timestamp("2026-11-30") - pd.Timestamp("2000-07-01")).days / 365.25, 2), "the date defaults to world.now"
    with pytest.raises(FrameError, match="on must be a date|not a"):
        grid.element_age(ge, "garbage", context=M12)
    sc = pd.Series([100.0, 80.0, 79.9, 60.0, 40.0, 39.9, 20.0, 19.9, 3.0, np.nan], index=list("abcdefghij"))
    c = grid.condition_class_from_score(sc, context=M12)
    assert c.tolist() == ["A", "A", "B", "B", "C", "D", "D", "E", "E", None] and c.index.tolist() == list(sc.index), "the class starts at its lower bound"
    assert grid.condition_class_from_score(sc, bands=((90.0, "X"), (50.0, "Y")), context=M12).tolist()[:4] == ["X", "Y", "Y", "Y"]
    for bad in (((50.0, "A"), (80.0, "B")), (), ((1,),)):
        with pytest.raises(FrameError, match="bands"):
            grid.condition_class_from_score(sc, bands=bad, context=M12)
    with pytest.raises(FrameError, match="Series"):
        grid.condition_class_from_score([1, 2], context=M12)


def test_parse_geom_accepts_case_z_m_signs_and_rejects_malformed_counts_and_rings():
    P = lambda t: grid.parse_geom(pd.Series([t]), context=M12).iloc[0]
    assert P("linestring(0 0,3 4)").length_m == 5.0 and P("LineString Z (0 0 9, 3 4 9)").length_m == 5.0 and P("POINT ZM (1 2 3 4)").n_points == 1
    assert P("LINESTRING (+0 .5, 3 4.5)").length_m == 5.0 and P("LINESTRING (0 0, 3. 4)").length_m == 5.0, "plus sign, leading and trailing dot"
    big = P("POLYGON ((500000 6100000, 500001.1 6100000, 500001.1 6100001.1, 500000 6100001.1, 500000 6100000))")
    assert abs(big.area_m2 - 1.21) < 1e-6, "area from the first vertex, not from the UTM origin"
    for bad in ("POINT (1 2, 3 4)", "LINESTRING (0 0)", "POLYGON ((0 0, 1 1))", "POLYGON ((0 0, 4 0, 4 4, 0 4))", "POLYGON ((0 0,1 0,1 1,0 0) junk (5 5,6 5,6 6,5 5))", "POLYGON (((0 0,1 0,1 1,0 0)))",
                "POLYGON ((0 0,1 0,1 1,0 1,0 0)))", "POLYGON ((0 0,10 0,10 10,0 10,0 0),(20 20,21 20,21 21,20 20))", "LINESTRING (0 0 1, 3 4)", "POINT Z (1 2)", "LINESTRING ((0 0, 1 1))", "POINT (a b)"):
        with pytest.raises(FrameError):
            P(bad)


def test_validate_versions_new_rules_and_strict_flags():
    base = [("N1", "2020-01-01", "2025-11-30", False, "a"), ("N1", "2025-12-01", None, True, "b")]
    ge = pd.DataFrame({"net_key": ["N1"], "current_geometry_valid_from": ["2025-12-01"]})
    rules = lambda gv, g=None: sorted(set(grid.validate_versions(gv, g, context=M12).rule))
    assert rules(_gv(base + [("ZZ", "2020-01-01", None, True, "x")]), ge) == ["version_without_element"], "an orphan version"
    assert rules(_gv(base), pd.concat([ge, ge])) == ["duplicate_element"]
    assert rules(_gv([("N1", None, "2025-11-30", False, "a"), ("N1", "2025-12-01", None, True, "b")])) == ["null_valid_from"]
    assert rules(_gv([("N1", None, None, True, "a")])) == ["null_valid_from"]
    d = grid.validate_versions(_gv([("N1", "2020-01-01", None, False, "a")]), pd.DataFrame({"net_key": ["N1", "N2"], "current_geometry_valid_from": [None, None]}), context=M12)
    assert sorted(zip(d.key, d.rule)) == [("N1", "element_without_version"), ("N1", "no_current"), ("N2", "element_without_version")] and "no geometry version" in d.detail.iloc[2]
    d = grid.validate_versions(_gv([("N1", "2020-01-01", None, False, "a")]), pd.DataFrame({"net_key": ["N1"], "current_geometry_valid_from": [None]}), context=M12)
    assert "none is current" in d.detail.iloc[0]
    for bad in ([True, None], [True, "true"], [True, 1], [True, np.nan]):
        with pytest.raises(FrameError, match="is_current"):
            grid.validate_versions(_gv([("N1", "2020-01-01", "2020-12-31", bad[0], "a"), ("N1", "2021-01-01", None, bad[1], "b")]), context=M12)
    with pytest.raises(FrameError, match="is_current"):
        grid.validate_versions(_gv([("N1", "2020-01-01", None, True, "a")]).assign(is_current=pd.array([pd.NA], dtype="boolean")), context=M12)
    assert grid.validate_versions(_gv([("N1", "2020-01-01", None, True, "a")]).assign(is_current=pd.array([True], dtype="boolean")), context=M12).empty
    assert "reversed" in rules(_gv([("N1", "2020-01-02", "2020-01-01", False, "a")])), "a version ending one day before it starts"


def test_geometry_as_of_time_of_day_null_start_and_null_key():
    gv = _gv([("N1", "2020-01-01", "2025-11-30", False, "old"), ("N1", "2025-12-01", None, True, "new")])
    assert grid.geometry_as_of(gv, "2025-11-30 12:00", context=M12).geom.tolist() == ["old"], "the end day counts whatever the time"
    assert grid.geometry_as_of(gv, "2025-11-30 23:59:59", context=M12).geom.tolist() == ["old"] and grid.geometry_as_of(gv, "2025-12-01 00:00:00", context=M12).geom.tolist() == ["new"]
    with pytest.raises(FrameError, match="valid_from"):
        grid.geometry_as_of(gv.assign(valid_from=[None, "2025-12-01"]), "2024-01-01", context=M12)
    with pytest.raises(FrameError, match="null net_key"):
        grid.geometry_as_of(gv.assign(net_key=[None, "N1"]), "2024-01-01", context=M12)


def test_route_change_boundary_inputs_and_element_age_edges():
    pa = lambda *rows: pd.DataFrame(rows, columns=["prj_key", "kind", "version", "valid_from", "valid_to", "length_m"])
    r = grid.route_change(pa(("P1", "planned_route", 1, "2025-01-01", "2025-11-30", 100.0), ("P1", "as_built_route", 2, "2025-12-01", None, 100.5)), tolerance_m=0.5, context=M12)
    assert r.delta_m.iloc[0] == 0.5 and not r.changed.iloc[0], "a difference equal to the tolerance is not a change"
    assert grid.route_change(pa(("P1", "planned_route", 1, "2025-01-01", None, 100.0), ("P1", "as_built_route", 2, "2025-12-01", None, 100.6)), tolerance_m=0.5, context=M12).changed.iloc[0]
    only = grid.route_change(pa(("P2", "as_built_route", 2, "2025-12-01", None, 10.0)), context=M12).iloc[0]
    assert np.isnan(only.planned_length_m) and not only.changed
    zero = grid.route_change(pa(("P3", "planned_route", 1, "2025-01-01", None, 0.0), ("P3", "as_built_route", 2, "2025-12-01", None, 5.0)), context=M12).iloc[0]
    assert zero.changed and np.isnan(zero.delta_percent)
    with pytest.raises(FrameError, match="not a number"):
        grid.route_change(pa(("P1", "planned_route", 1, "2025-01-01", None, "abc")), context=M12)
    with pytest.raises(FrameError, match="null prj_key"):
        grid.route_change(pa((None, "planned_route", 1, "2025-01-01", None, 1.0)), context=M12)
    ge = lambda **kw: pd.DataFrame({"install_year": [2000], "status": ["in_service"], "commissioned_date": [None], **kw})
    assert grid.element_age(ge(commissioned_date=["2024-02-29"]), "2024-02-29", context=M12).iloc[0] == 0.0, "an element commissioned on the date is age 0"
    assert np.isnan(grid.element_age(ge(commissioned_date=["2024-03-01"]), "2024-02-29", context=M12).iloc[0]), "commissioned after the date"
    assert grid.element_age(ge(), "2001-01-01", context=M12).iloc[0] == round(366 / 365.25, 2)
    for y in (2000.5, 20, 1, -5, np.inf, 2300):
        with pytest.raises(FrameError, match="install_year"):
            grid.element_age(ge(install_year=[y]), "2024-01-01", context=M12)
    assert np.isnan(grid.element_age(ge(install_year=[None]), "2024-01-01", context=M12).iloc[0])


def test_condition_class_checks_range_numbers_and_bands():
    s = pd.Series([100, 80, 79.9999999999999, 60, 40, 20, 0, None])
    assert grid.condition_class_from_score(s, context=M12).tolist() == ["A", "A", "B", "B", "C", "D", "E", None]
    for bad in (pd.Series(["abc"]), pd.Series([101]), pd.Series([-1]), pd.Series([np.inf])):
        with pytest.raises(FrameError):
            grid.condition_class_from_score(bad, context=M12)
    for bands in (None, ((80, "A"), (90, "B")), (("80", "A"),), ((float("nan"), "A"),), ((80, 1),), "AB"):
        with pytest.raises(FrameError, match="bands"):
            grid.condition_class_from_score(s, bands=bands, context=M12)
    assert grid.condition_class_from_score(pd.Series([50]), bands=[(50, "X")], context=M12).tolist() == ["X"], "a list of pairs is fine"


def test_round2_validate_versions_nesting_order_one_day_and_current_edges():
    rules = lambda gv, g=None: sorted(set(grid.validate_versions(gv, g, context=M12).rule))
    shuffled = _gv([("N1", "2025-12-01", None, True, "b"), ("N1", "2020-01-01", "2025-11-30", False, "a")])
    assert rules(shuffled) == [], "rows in any order"
    assert rules(_gv([("N1", "2020-01-01", "2020-01-01", False, "a"), ("N1", "2020-01-02", None, True, "b")])) == [], "a one-day version ends on the day it starts: not reversed"
    nested = _gv([("N1", "2020-01-01", "2020-12-31", False, "a"), ("N1", "2020-02-01", "2020-02-10", False, "b"), ("N1", "2021-01-01", None, True, "c")])
    d = grid.validate_versions(nested, context=M12)
    assert d.rule.tolist() == ["overlap"], "a nested version is one overlap and the next version is not a gap"
    assert rules(_gv([("N1", "2020-01-01", "2020-12-31", False, "a"), ("N1", "2021-01-05", None, True, "b")])) == ["gap"]
    ge = pd.DataFrame({"net_key": ["N1"], "current_geometry_valid_from": ["2025-12-01 13:00"]})
    ok = _gv([("N1", "2020-01-01", "2025-11-30", False, "a"), ("N1", "2025-12-01", None, True, "b")])
    assert rules(ok, ge) == [], "a time of day in the element date is cut off"
    assert rules(ok, ge.assign(current_geometry_valid_from="2025-11-30")) == ["current_start_mismatch"] and rules(ok, ge.assign(current_geometry_valid_from="2025-12-02")) == ["current_start_mismatch"]
    assert "null_valid_from" in rules(_gv([("N1", None, None, True, "a"), ("N1", "2020-01-01", None, False, "b")]))
    assert "no_current" in rules(_gv([("N1", None, None, True, "a"), ("N1", "2020-01-01", None, False, "b")])), "a current version without a start does not count as current"
    assert rules(_gv([("N1", "2020-01-01", "2020-12-31", True, "a"), ("N1", "2021-01-01", None, True, "b")])) == ["several_current"]


def test_round2_wkt_exponent_ordinates_rings_unicode_and_backtracking():
    P = lambda t: grid.parse_geom(pd.Series([t]), context=M12).iloc[0]
    assert P("LINESTRING (0 0, 1E3 0)").length_m == 1000.0 and P("LINESTRING (0 0, 3 4)").length_m == 5.0
    with pytest.raises(FrameError):
        P("POINT (1 2 3 4 5)")
    with pytest.raises(FrameError):
        P("POLYGON ((0 0, 1 0, 0 0))")
    assert P("POLYGON ((0 0,4 0,4 4,0 0))").area_m2 == 8.0
    for bad in ("POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 12,3 12,3 13,2 13,2 12))", "POINT (" + chr(0x661) + " " + chr(0x662) + ")", "POINT" + chr(0xa0) + "(1 2)", "POINT (1" + chr(0xa0) + "2)"):
        with pytest.raises(FrameError):
            P(bad)
    import time
    t0 = time.time()
    with pytest.raises(FrameError):
        P("POINT (" + "1" * 20000 + "e)")
    assert time.time() - t0 < 1.0, "no quadratic backtracking on long digit runs"


def test_round2_route_change_unrounded_difference_and_length_checks_and_class_inputs():
    pa = lambda pl, ab: pd.DataFrame([("P", "planned_route", 1, "2025-01-01", "2025-11-30", pl), ("P", "as_built_route", 2, "2025-12-01", None, ab)], columns=["prj_key", "kind", "version", "valid_from", "valid_to", "length_m"])
    assert grid.route_change(pa(100.0, 100.0004), tolerance_m=0.0, context=M12).changed.iloc[0], "the difference is compared before rounding"
    assert grid.route_change(pa(100.0, 100.5004), context=M12).changed.iloc[0]
    for bad in (True, "12.5", np.inf, -5.0):
        with pytest.raises(FrameError, match="length_m"):
            grid.route_change(pa(bad, 100.0), context=M12)
    for bad in (pd.Series([True, False]), pd.Series(["85"]), pd.Series([1 + 2j])):
        with pytest.raises(FrameError, match="not a number"):
            grid.condition_class_from_score(bad, context=M12)
    ge = lambda y: pd.DataFrame({"install_year": [y], "status": ["in_service"], "commissioned_date": [None]})
    assert grid.element_age(ge(1800), "1900-01-01", context=M12).iloc[0] == round(36524 / 365.25, 2)
    assert not np.isnan(grid.element_age(ge(2200), "2201-01-01", context=M12).iloc[0]) and not np.isnan(grid.element_age(ge(1800), "1801-01-01", context=M12).iloc[0])
    with pytest.raises(FrameError, match="install_year"):
        grid.element_age(ge(2201), "2202-01-01", context=M12)
