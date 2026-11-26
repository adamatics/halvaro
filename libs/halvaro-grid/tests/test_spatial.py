"""Spatial (plan 5.6): hand computed geometry."""

import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry
from halvaro.grid.spatial import _ON_SITE as ON_SITE

M12 = Context(stage="month12", role="r")


def _ge(rows):
    return pd.DataFrame(rows, columns=["net_key", "element_type", "zone_key", "lon", "lat", "commissioned_date", "status", "install_year"])


def _fe(rows):
    return pd.DataFrame(rows, columns=["net_key", "fault_ts"])


# 0.0027 degrees of latitude are about 300 m
GE = _ge([("A", "cable_section", "Z1", 10.0, 55.0, "2000-01-01", "in_service", 1975), ("B", "cable_section", "Z1", 10.0, 55.0020, "2000-01-01", "in_service", 1976), ("C", "cable_section", "Z1", 10.0, 55.0040, "2000-01-01", "in_service", 1977),
          ("D", "cable_section", "Z1", 10.0, 55.0600, "2000-01-01", "in_service", 1999), ("E", "valve", "Z1", 10.0, 55.0010, "2000-01-01", "in_service", 1980), ("F", "cable_section", "Z1", 10.0, 55.0020, "2000-01-01", "out_of_service", 1975),
          ("G", "cable_section", "Z1", 10.0, 55.0, "2027-01-01", "in_service", 2026)])


def test_fault_density_window_commissioning_cells_and_unknown_elements():
    fe = _fe([("A", "2025-12-01 00:00"), ("A", "2026-02-28 23:59"), ("B", "2026-03-01 00:00"), ("B", "2025-11-30 23:59"), ("C", "2026-01-10 00:00")])
    d = grid.fault_density(fe, GE, "2025-12-01", "2026-02-28", context=M12).set_index("net_key")
    assert d.loc["A", "n_faults"] == 2 and d.loc["B", "n_faults"] == 0 and d.loc["C", "n_faults"] == 1, "both window days are inclusive; one second outside does not count"
    assert "G" not in d.index and "F" not in d.index, "G is commissioned after the window, F is out of service (T18)"
    assert "F" in grid.fault_density(fe, GE, "2025-12-01", "2026-02-28", in_service=None, context=M12).net_key.tolist()
    assert d.loc["A", "months"] == pytest.approx(90 / 30.4375, abs=1e-3) and d.loc["A", "faults_per_month"] == pytest.approx(2 / (90 / 30.4375), abs=1e-3)
    assert d.loc["A", "cell_x"] == d.loc["B", "cell_x"] and d.loc["A", "cell_faults"] == 2 + 0 + 0 and d.loc["D", "cell_faults"] == 0
    late = GE.assign(commissioned_date=GE.commissioned_date.where(GE.net_key != "A", "2026-01-15"))
    assert grid.fault_density(fe, late, "2025-12-01", "2026-02-28", context=M12).set_index("net_key").loc["A", "months"] == pytest.approx(45 / 30.4375, abs=1e-3), "an element exists from its commissioning date"
    for bad, msg in ((_fe([("Z", "2026-01-01")]), "not in gis.grid_element"),):
        with pytest.raises(FrameError, match=msg):
            grid.fault_density(bad, GE, "2025-12-01", "2026-02-28", context=M12)
    with pytest.raises(FrameError, match="in order"):
        grid.fault_density(fe, GE, "2026-02-28", "2025-12-01", context=M12)
    with pytest.raises(FrameError, match="cell_m"):
        grid.fault_density(fe, GE, "2025-12-01", "2026-02-28", cell_m=0, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.fault_density(fe, pd.concat([GE, GE.iloc[:1]]), "2025-12-01", "2026-02-28", context=M12)


def test_fault_clusters_link_distance_threshold_members_and_hull_buffer():
    fe = _fe([("A", "2026-01-01")] * 3 + [("B", "2026-01-02")] * 3 + [("C", "2026-01-03")] * 3 + [("D", "2026-01-04")] * 2)
    d = grid.fault_density(fe, GE, "2025-12-01", "2026-02-28", context=M12)
    cl = grid.fault_clusters(d, GE, context=M12)
    assert len(cl) == 1 and cl[0].n_faulted == 3 and cl[0].n_faults == 9 and cl[0].cluster_id == 1, "A, B, C are 222 m apart, D is far away and has too few faults"
    assert cl[0].members == ("A", "B", "C"), "E is a valve (not a faulted type), F is out of service, G does not exist yet"
    assert grid.fault_clusters(d, GE, link_m=100, context=M12) == [] and len(grid.fault_clusters(d, GE, min_faults=2, context=M12)) == 2
    assert grid.fault_clusters(d, GE, min_faults=10, context=M12) == [] and grid.fault_clusters(d.assign(n_faults=0), GE, context=M12) == []
    one = grid.fault_clusters(d, GE, min_element_faults=3, link_m=300, min_faults=3, context=M12)
    assert [c.n_faulted for c in one] == [3] and cl[0].radius_m == pytest.approx(222.0, abs=3.0) and len(cl[0].hull) == 2
    ge2 = GE.assign(lat=GE.lat.where(GE.net_key != "F", 55.0030), status=GE.status.where(GE.net_key != "F", "in_service"))
    d2 = grid.fault_density(fe, ge2, "2025-12-01", "2026-02-28", context=M12)
    assert "F" in grid.fault_clusters(d2, ge2, context=M12)[0].members, "an in service element of a faulted type at 222 m from the hull centre line... inside the buffered hull"
    far = GE.assign(lat=GE.lat.where(GE.net_key != "F", 55.0100), status=GE.status.where(GE.net_key != "F", "in_service"))
    assert "F" not in grid.fault_clusters(grid.fault_density(fe, far, "2025-12-01", "2026-02-28", context=M12), far, context=M12)[0].members, "F at 55.0100 is more than 150 m from the hull of A to C"
    with pytest.raises(FrameError, match="min_faults"):
        grid.fault_clusters(d, GE, min_faults=0, context=M12)
    with pytest.raises(FrameError, match="min_element_faults"):
        grid.fault_clusters(d, GE, min_element_faults=0, context=M12)


def test_age_group_clusters_find_a_decade_without_fault_data():
    rows = [(f"K{i}", "cable_section", "Z1", 10.0, 55.0 + 0.001 * i, "1990-01-01", "in_service", 1970 + i % 10) for i in range(25)]
    rows += [(f"O{i}", "cable_section", "Z1", 10.2 + 0.05 * i, 55.5, "1990-01-01", "in_service", 1990) for i in range(30)] + [("V1", "valve", "Z1", 10.0, 55.0, "1990-01-01", "in_service", 1975)]
    ge = _ge(rows)
    r = grid.age_group_clusters(ge, decade=1970, element_type="cable_section", context=M12)
    assert len(r) == 1 and r.n_elements.iloc[0] == 25 and r.share_of_group.iloc[0] == 1.0 and r.zone_key.iloc[0] == "Z1" and r.density_ratio.iloc[0] > 1
    assert grid.age_group_clusters(ge, decade=1970, element_type="cable_section", min_size=26, context=M12).empty and grid.age_group_clusters(ge, decade=1980, element_type="cable_section", context=M12).empty
    with pytest.raises(FrameError, match="decade"):
        grid.age_group_clusters(ge, decade=1975, element_type="cable_section", context=M12)


def _gc(rows):
    return pd.DataFrame(rows, columns=["area_id", "geom", "soil_class", "groundwater", "bearing_capacity", "survey_kind"])


SQ = "POLYGON ((0 -10, 100 -10, 100 10, 0 10, 0 -10))"
HOLE = "POLYGON ((200 -10, 400 -10, 400 10, 200 10, 200 -10), (250 -5, 350 -5, 350 5, 250 5, 250 -5))"


def test_route_ground_intersection_lengths_holes_shares_and_conditions():
    pa = pd.DataFrame({"prj_key": ["P1", "P1", "P2"], "version": [1, 2, 1], "kind": ["planned_route", "as_built_route", "planned_route"], "geom": ["LINESTRING (-50 0, 450 0)", "LINESTRING (-50 50, 450 50)", "LINESTRING (0 0, 0 0.5, 80 0.5)"]})
    gc = _gc([("G1", SQ, "clay", "normal", "good", "borehole_survey"), ("G2", HOLE, "peat", "high", "poor", ON_SITE)])
    r = grid.route_ground_intersection(pa, gc, context=M12).set_index(["prj_key", "area_id"])
    assert r.loc[("P1", "G1"), "metres"] == pytest.approx(100.0) and r.loc[("P1", "G2"), "metres"] == pytest.approx(100.0), "the hole (100 m wide, 250 to 350) is not ground"
    assert r.loc[("P1", "G1"), "covered_m"] == pytest.approx(200.0) and r.loc[("P1", "G1"), "share_of_covered"] == pytest.approx(0.5) and r.loc[("P1", "G1"), "share_of_route"] == pytest.approx(0.2) and r.loc[("P1", "G1"), "route_length_m"] == pytest.approx(500.0)
    assert r.loc[("P2", "G1"), "metres"] == pytest.approx(80.5, abs=0.01), "a route that starts on the polygon edge: 0.5 m up along x = 0 and 80 m along y = 0.5"
    assert grid.route_ground_intersection(pa, gc, kind="as_built_route", context=M12).empty, "the as-built route at y 50 touches nothing"
    ms = grid.majority_soil(grid.route_ground_intersection(pa, gc, context=M12), context=M12).set_index("prj_key")
    assert ms.loc["P2", "soil_class"] == "clay" and ms.loc["P2", "share"] == 1.0 and ms.loc["P1", "soil_class"] == "clay" and ms.loc["P1", "share"] == pytest.approx(0.5), "a tie goes to the class that sorts first"
    cs = grid.route_conditions_summary(grid.route_ground_intersection(pa, gc, context=M12), context=M12).set_index("prj_key")
    assert bool(cs.loc["P1", "crosses_poor_bearing"]) and bool(cs.loc["P1", "crosses_high_groundwater"]) and bool(cs.loc["P1", "crosses_site_observation"]) and cs.loc["P1", "poor_bearing_share"] == pytest.approx(0.2)
    assert not bool(cs.loc["P2", "crosses_poor_bearing"]) and cs.loc["P2", "high_groundwater_m"] == 0.0
    assert grid.route_conditions_summary(grid.route_ground_intersection(pa, gc, context=M12), poor_bearing=("good",), context=M12).set_index("prj_key").loc["P2", "crosses_poor_bearing"]
    for bad, msg in ((gc.assign(geom=["LINESTRING (0 0, 1 1)", HOLE]), "not a POLYGON"), (gc.assign(area_id="G1"), "more than one row")):
        with pytest.raises(FrameError, match=msg):
            grid.route_ground_intersection(pa, bad, context=M12)
    with pytest.raises(FrameError, match="LINESTRING"):
        grid.route_ground_intersection(pa.assign(geom="POINT (0 0)"), gc, context=M12)
    with pytest.raises(FrameError, match="kind"):
        grid.route_ground_intersection(pa, gc, kind="work_area", context=M12)
    assert grid.majority_soil(grid.route_ground_intersection(pa.iloc[:0], gc, context=M12), context=M12).empty


def test_stage_registry_and_facade_for_spatial():
    reg = registry.registered()
    for n in ("fault_density", "fault_clusters", "age_group_clusters", "route_ground_intersection", "majority_soil", "route_conditions_summary"):
        assert f"halvaro.grid.spatial.{n}" in reg and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.fault_density(pd.DataFrame(), pd.DataFrame(), "2025-12-01", "2026-02-28", context=Context(stage="month3", role="r"))





def test_route_sliver_touch_is_no_crossing_and_age_group_arguments_are_checked():
    pa = pd.DataFrame({"prj_key": ["P1"], "version": [2], "kind": ["planned_route"], "geom": ["LINESTRING(0 0, 100 0)"]})
    poly = lambda x0, x1: f"POLYGON(({x0} -10, {x1} -10, {x1} 10, {x0} 10, {x0} -10))"
    gc = pd.DataFrame({"area_id": ["G1", "G2"], "geom": [poly(0, 50), poly(100, 150)], "soil_class": ["peat", "clay"], "groundwater": ["high", "low"], "bearing_capacity": ["poor", "good"], "survey_kind": ["survey", "survey"]})
    r = grid.route_ground_intersection(pa, gc, context=M12)
    assert r.area_id.tolist() == ["G1"] and r.metres.tolist() == [50.0], "G2 only touches the end of the route"
    thin = gc.assign(geom=[poly(0, 50), poly(99.995, 150)])
    assert grid.route_ground_intersection(pa, thin, context=M12).area_id.tolist() == ["G1"], "5 mm inside is a sliver"
    assert grid.route_ground_intersection(pa, thin, min_metres=0.001, context=M12).area_id.tolist() == ["G1", "G2"]
    cs = grid.route_conditions_summary(r, context=M12).iloc[0]
    assert cs.poor_bearing_share == 0.5 and bool(cs.crosses_poor_bearing) and not bool(cs.crosses_site_observation)
    with pytest.raises(FrameError, match="min_metres"):
        grid.route_ground_intersection(pa, gc, min_metres=-1, context=M12)
    with pytest.raises(FrameError, match="poor_bearing"):
        grid.route_conditions_summary(r, poor_bearing="poor", context=M12)
    for kw, msg in ((dict(link_m=0), "link_m"), (dict(min_size=0), "min_size"), (dict(buffer_m=-5), "buffer_m"), (dict(link_m="x"), "link_m")):
        with pytest.raises(FrameError, match=msg):
            grid.age_group_clusters(GE, decade=1970, element_type="cable_section", context=M12, **kw)
    with pytest.raises(FrameError, match="numeric"):
        grid.age_group_clusters(GE.assign(install_year=GE.install_year.astype(str)), decade=1970, element_type="cable_section", context=M12)
    assert grid.age_group_clusters(GE.assign(zone_key=None), decade=1970, element_type="cable_section", min_size=2, context=M12).zone_key.isna().all()
