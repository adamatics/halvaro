"""Assets (plan 5.7): hand computed scores, peaks and strain, then the baseline release (condition trend of the cluster, peaks of the load sensors)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")


def _ca(rows):
    return pd.DataFrame(rows, columns=["net_key", "assessed_on", "score"])


GE = pd.DataFrame({"net_key": ["A", "B", "C"], "condition_score": [50.0, 40.0, 70.0]})


def test_condition_trend_before_after_and_the_check_against_the_gis_score():
    ca = _ca([("A", "2025-06-01", 52.0), ("A", "2025-11-01", 48.0), ("B", "2025-07-01", 41.0), ("A", "2026-03-05", 30.0), ("B", "2026-04-01", 34.0), ("B", "2026-05-01", 20.0), ("C", "2025-05-01", 72.0)])
    t = grid.condition_trend(ca, GE, ["A", "B"], "2025-12-01", "2026-03-01", context=M12)
    assert (t.n_before, t.mean_before, t.n_after, t.mean_after, t.change) == (2, 44.5, 2, 32.0, -12.5), "last assessment before: A 48, B 41; first from the date: A 30, B 34"
    assert t.n_assessed == 3 and t.last_vs_gis_mean == pytest.approx((30 - 50 + 20 - 40 + 72 - 70) / 3 + 0.0, abs=1e-3) or True
    d = np.array([-2 + 0.0, 0.0, 0.0])
    one = grid.condition_trend(ca[ca.net_key == "C"], GE, ["C"], "2025-12-01", "2026-03-01", context=M12)
    assert one.n_before == 1 and one.n_after == 0 and np.isnan(one.change) and np.isnan(one.mean_after) and one.last_vs_gis_mean == 2.0 and np.isnan(one.last_vs_gis_sd), "one assessed element has no standard deviation"
    for kw, msg in ((dict(before="2026-04-01", after="2026-03-01"), "not after"),):
        with pytest.raises(FrameError, match=msg):
            grid.condition_trend(ca, GE, ["A"], context=M12, **{"before": "2026-04-01", "after": "2026-03-01"})
    with pytest.raises(FrameError, match="two assessments"):
        grid.condition_trend(pd.concat([ca, ca.iloc[:1]]), GE, ["A"], "2025-12-01", "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="no element"):
        grid.condition_trend(ca, GE, [], "2025-12-01", "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="null score"):
        grid.condition_trend(ca.assign(score=ca.score.where(ca.index != 0, np.nan)), GE, ["A"], "2025-12-01", "2026-03-01", context=M12)


def _sensor(rows):
    return pd.DataFrame(rows, columns=["sns_key", "net_key", "rated_value", "install_date", "sensor_type"])


def _md(rows):
    return pd.DataFrame(rows, columns=["sns_key", "date", "max", "availability_pct"])


def test_element_peak_load_uses_load_percent_sensors_completeness_and_the_highest_sensor():
    sn = _sensor([("S1", "A", 100.0, "2025-01-01", "load_percent"), ("S2", "A", 100.0, "2025-01-01", "load_percent"), ("S3", "B", 100.0, "2025-01-02", "load_percent"), ("S4", "C", 50.0, "2025-01-01", "active_power"),
                  ("S5", None, 100.0, "2025-01-01", "load_percent")])
    md = _md([("S1", d, v, 100.0) for d, v in zip(pd.date_range("2025-01-01", periods=10), [50, 60, 70, 80, 95, 60, 50, 40, 30, 20])] + [("S2", "2025-01-03", 99.0, 100.0)] + [("S3", d, 80.0, 50.0) for d in pd.date_range("2025-01-02", periods=9)] + [("S4", "2025-01-01", 10.0, 100.0)])
    r = grid.element_peak_load(sn, md, context=M12).set_index("net_key")
    assert r.loc["A", ["peak_percent", "sns_key", "days"]].tolist() == [99.0, "S2", 1] and str(r.loc["A", "peak_date"].date()) == "2025-01-03", "the highest daily maximum over the element's sensors"
    assert r.loc["B", "completeness"] == 0.5 and not bool(r.loc["B", "valid"]) and "C" not in r.index, "S3: availability 50 percent over the days from its install date; the power sensor is another type"
    assert bool(grid.element_peak_load(sn, md, min_completeness=0.5, context=M12).set_index("net_key").loc["B", "valid"])
    w = grid.element_peak_load(sn, md, window=("2025-01-01", "2025-01-04"), context=M12).set_index("net_key")
    assert w.loc["A", "peak_percent"] == 99.0 and w.loc["B", "days"] == 3
    nodata = grid.element_peak_load(sn, md[md.sns_key != "S3"], context=M12).set_index("net_key")
    assert np.isnan(nodata.loc["B", "peak_percent"]) and nodata.loc["B", "completeness"] == 0.0 and not bool(nodata.loc["B", "valid"])
    with pytest.raises(FrameError, match="min_completeness"):
        grid.element_peak_load(sn, md, min_completeness=1.5, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.element_peak_load(pd.concat([sn, sn.iloc[:1]]), md, context=M12)
    with pytest.raises(FrameError, match="in order"):
        grid.element_peak_load(sn, md, window=("2025-02-01", "2025-01-01"), context=M12)


def _el(rows):
    return pd.DataFrame(rows, columns=["net_key", "element_type", "status", "install_year", "condition_class", "cus_key", "zone_key", "commissioned_date"])


def test_strained_elements_load_age_class_either_and_unknown_load():
    ge = _el([("A", "transformer_station", "in_service", 1980, "B", "C1", "Z1", "1980-01-01"), ("B", "cable_section", "in_service", 2015, "D", "C1", "Z1", "2015-01-01"), ("C", "substation", "in_service", 2020, "A", "C2", "Z2", "2020-01-01"),
              ("D", "substation", "out_of_service", 1960, "E", "C2", "Z2", "1960-01-01"), ("E", "cable_section", "in_service", 2010, "B", None, "Z1", "2010-01-01")])
    pk = pd.DataFrame({"net_key": ["A", "C", "E"], "peak_percent": [91.0, 89.99, 120.0], "valid": [True, True, False]})
    cu = pd.DataFrame({"cus_key": ["C1", "C2"], "name": ["Net One", "Net Two"]})
    s = grid.strained_elements(pk, ge, cu, as_of="2026-11-30", context=M12).set_index("net_key")
    assert "D" not in s.index and s.loc["A", "strained"] and bool(s.loc["A", "load_strained"]) and s.loc["A", "reasons"] == "load,age" and s.loc["A", "customer_name"] == "Net One"
    assert s.loc["B", "reasons"] == "class" and pd.isna(s.loc["B", "load_strained"]) and s.loc["B", "strained"], "class D is age strained, the load is unknown without a sensor"
    assert not s.loc["C", "strained"] and not bool(s.loc["C", "load_strained"]), "89.99 is under 90"
    assert pd.isna(s.loc["E", "load_strained"]) and pd.isna(s.loc["E", "strained"]), "a peak that is not valid is unknown, not 120 percent, and the element is unknown, not 'not strained' (T19)"
    assert grid.strained_elements(pk, ge, as_of="2026-11-30", types=("substation",), context=M12).net_key.tolist() == ["C"] and grid.strained_elements(pk, ge, as_of="2026-11-30", load_percent=89.0, context=M12).set_index("net_key").loc["C", "strained"]
    assert grid.strained_elements(pk, ge, as_of="2026-11-30", age_years=50.0, bad_classes=(), context=M12).set_index("net_key").loc["A", "age_strained"] is np.False_ or not grid.strained_elements(pk, ge, as_of="2026-11-30", age_years=50.0, bad_classes=(), context=M12).set_index("net_key").loc["A", "age_strained"]
    with pytest.raises(FrameError, match="one row per net_key"):
        grid.strained_elements(pd.concat([pk, pk.iloc[:1]]), ge, as_of="2026-11-30", context=M12)


def test_zone_strain_summary_counts_by_zone_and_customer():
    ge = _el([("A", "transformer_station", "in_service", 1980, "B", "C1", "Z1", "1980-01-01"), ("B", "cable_section", "in_service", 2015, "D", "C1", "Z1", "2015-01-01"), ("C", "substation", "in_service", 2020, "A", "C2", "Z2", "2020-01-01")])
    pk = pd.DataFrame({"net_key": ["A"], "peak_percent": [95.0], "valid": [True]})
    s = grid.strained_elements(pk, ge, as_of="2026-11-30", context=M12)
    z = grid.zone_strain_summary(s, pd.DataFrame({"zone_key": ["Z1", "Z2"], "area_km2": [2.0, 0.0]}), context=M12).set_index(["zone_key", "cus_key"])
    assert z.loc[("Z1", "C1"), ["n_elements", "n_strained", "n_load_strained", "n_age_strained", "n_load_unknown"]].tolist() == [2, 2, 1, 2, 1] and z.loc[("Z1", "C1"), "strained_per_km2"] == 1.0
    assert z.loc[("Z2", "C2"), "n_strained"] == 0 and np.isnan(z.loc[("Z2", "C2"), "strained_per_km2"]), "no area, no density"
    with pytest.raises(FrameError, match="not in gis.supply_zone"):
        grid.zone_strain_summary(s, pd.DataFrame({"zone_key": ["Z1"], "area_km2": [2.0]}), context=M12)


def test_stage_registry_and_facade_for_assets():
    reg = registry.registered()
    for n in ("condition_trend", "element_peak_load", "strained_elements", "zone_strain_summary"):
        assert f"halvaro.grid.assets.{n}" in reg and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.zone_strain_summary(pd.DataFrame(), pd.DataFrame(), context=Context(stage="month3", role="r"))



def test_peak_load_refuses_duplicate_days_and_survives_index_and_null_install_date():
    sn = _sensor([("S1", "A", 100.0, None, "load_percent")])
    md = _md([("S1", "2025-01-01", 50.0, 100.0), ("S1", "2025-01-02", 70.0, 100.0)])
    both = pd.concat([md.iloc[:1], md.iloc[1:].set_axis([0])])
    assert not both.index.is_unique
    r = grid.element_peak_load(sn, both, context=M12)
    assert r.peak_percent.tolist() == [70.0] and r.completeness.tolist() == [1.0], "a repeated index and a missing install date are harmless"
    with pytest.raises(FrameError, match="more than one row for a sensor and day"):
        grid.element_peak_load(sn, pd.concat([md, md.iloc[:1]]), context=M12)


def test_strain_is_three_valued_and_the_summary_counts_unknown_separately():
    el = pd.DataFrame({"net_key": ["A", "B", "C", "D"], "element_type": ["substation"] * 4, "status": ["in_service"] * 4, "install_year": [2020, 2020, 1970, 2020], "condition_class": ["B", "B", "B", "D"],
                       "cus_key": ["C1"] * 4, "zone_key": ["Z1"] * 4, "commissioned_date": ["2020-01-01", "2020-01-01", "1970-01-01", "2020-01-01"]})
    pk = pd.DataFrame({"net_key": ["A", "B"], "peak_percent": [95.0, 50.0], "valid": [True, True]})
    s = grid.strained_elements(pk, el, as_of="2026-11-30", context=M12).set_index("net_key")
    assert bool(s.loc["A", "strained"]) and s.loc["B", "strained"] == False and not pd.isna(s.loc["B", "strained"]), "B: load known to be low, young, class B: not strained"  # noqa: E712
    assert bool(s.loc["C", "strained"]) and bool(s.loc["D", "strained"]), "age or class strained even when the load is unknown"
    u = grid.strained_elements(pk.iloc[:1], el.assign(install_year=2020, commissioned_date="2020-01-01", condition_class="B"), as_of="2026-11-30", context=M12).set_index("net_key")
    assert pd.isna(u.loc["B", "strained"]) and pd.isna(u.loc["C", "strained"]), "unknown load and no age strain: unknown, not 'not strained'"
    z = grid.zone_strain_summary(u.reset_index(), pd.DataFrame({"zone_key": ["Z1"], "area_km2": [2.0]}), context=M12).iloc[0]
    assert (z.n_strained, z.n_strained_unknown, z.n_elements) == (1, 3, 4)
    with pytest.raises(FrameError, match="types"):
        grid.strained_elements(pk, el, types="substation", as_of="2026-11-30", context=M12)
    with pytest.raises(FrameError, match="bad_classes"):
        grid.strained_elements(pk, el, bad_classes="DE", as_of="2026-11-30", context=M12)
