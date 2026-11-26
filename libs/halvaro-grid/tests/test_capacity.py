"""Capacity and load (plan 5.3): hand computed zones and series (the release checks are in repo_tests of the closed repository)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")
T0 = pd.Timestamp("2026-01-19 00:00")


def _sensor():
    rows = [("R-LOAD", "ZONE-1", "load_percent", 900, "root_pump", 50.0, "WST-1"), ("R-POWER", "ZONE-1", "heat_power", 900, "root_pump", 50.0, "WST-1"), ("R-SUPPLY", "ZONE-1", "supply_temp", 900, "root_pump", np.nan, "WST-1"),
            ("H-LOAD", "ZONE-2", "load_percent", 3600, "root_pump", 100.0, "WST-2"), ("E-ST1", "ZONE-4", "load_percent", 3600, "largest_load", 315.0, "WST-4"),
            ("E-ST2", "ZONE-4", "load_percent", 3600, None, 630.0, "WST-4"), ("OTHER", "ZONE-1", "flow", 900, None, 1500.0, "WST-1")]
    return pd.DataFrame(rows, columns=["sns_key", "zone_key", "sensor_type", "interval_s", "critical_role", "rated_value", "station_key"])


def _meas(key, values, flags=None, step="15min", start=T0):
    n = len(values)
    return pd.DataFrame({"sns_key": key, "ts": pd.date_range(start, periods=n, freq=step), "value": values, "quality_flag": flags or ["ok"] * n})


def _series():
    load = [50.0, 80.0, 120.0, 130.0, 90.0, 99.0, 100.0, 101.0]
    flags = ["ok", "ok", "ok", "suspect", "ok", "missing", "ok", "ok"]
    power = [25.0, 40.0, 60.0, 65.0, 45.0, 49.5, 50.0, 50.5]
    m = pd.concat([_meas("R-LOAD", load, flags), _meas("R-POWER", power, flags), _meas("H-LOAD", [10.0, 20.0, 30.0], step="h"), _meas("E-ST1", [70.0, 110.0, 90.0], step="h"), _meas("E-ST2", [105.0, 60.0, 50.0], step="h")])
    m.loc[(m.quality_flag == "missing"), "value"] = np.nan
    return m


def test_design_capacity_as_stored_and_recomputed_from_the_elements_in_service():
    z = pd.DataFrame({"zone_key": ["ZONE-2", "ZONE-1"], "design_capacity": [65.4, 46.1], "design_capacity_unit": ["MW_th", "MW_th"], "extra": 1})
    assert grid.zone_design_capacity(z, context=M12).values.tolist() == [["ZONE-1", 46.1, "MW_th"], ["ZONE-2", 65.4, "MW_th"]]
    for bad in (z.assign(design_capacity=[0.0, 1.0]), z.assign(design_capacity_unit=[None, "MW_th"]), pd.concat([z, z.iloc[:1]])):
        with pytest.raises(FrameError):
            grid.zone_design_capacity(bad, context=M12)
    g = pd.DataFrame({"zone_key": ["ZONE-1"] * 3 + ["ZONE-4"] * 3, "element_type": ["heat_exchanger_station"] * 3 + ["transformer_station"] * 2 + ["substation"],
                      "status": ["in_service", "in_service", "planned", "in_service", "under_construction", "in_service"], "rated_capacity": [1000.0, 500.0, 9000.0, 630.0, 800.0, 40.0],
                      "capacity_unit": ["kW"] * 3 + ["kVA"] * 2 + ["MVA"]})
    r = grid.recompute_design_capacity(g, context=M12).set_index("zone_key")
    assert r.loc["ZONE-1", ["network_type", "design_capacity", "design_capacity_unit", "n_elements"]].tolist() == ["heat", 0.9, "MW_th", 2], "1,500 kW in service times 0.6"
    assert r.loc["ZONE-4", ["network_type", "design_capacity", "design_capacity_unit"]].tolist() == ["electric", 0.284, "MVA"] and r.loc["ZONE-4", "n_elements"] == 1
    assert grid.recompute_design_capacity(g, heat_diversity=1.0, electric_diversity=1.0, context=M12).set_index("zone_key").loc["ZONE-1", "design_capacity"] == 1.5
    for kw in (dict(heat_diversity=0), dict(electric_diversity=1.5), dict(heat_diversity=True)):
        with pytest.raises(FrameError, match="diversity"):
            grid.recompute_design_capacity(g, context=M12, **kw)
    with pytest.raises(FrameError, match="rated in kW"):
        grid.recompute_design_capacity(g.assign(capacity_unit="MVA"), context=M12)
    with pytest.raises(FrameError, match="zero or more"):
        grid.recompute_design_capacity(g.assign(rated_capacity=np.nan), context=M12)


def test_zone_load_percent_reads_the_root_and_keeps_stations_apart():
    z = grid.zone_load_percent(_series(), _sensor(), context=M12)
    root = z[z.sns_key == "R-LOAD"]
    assert root.level.eq("zone").all() and root.basis.eq("load_percent").all() and root.load_percent.tolist()[:3] == [50.0, 80.0, 120.0] and root.ok.tolist() == [True, True, True, False, True, False, True, True]
    assert root.load_percent.isna().tolist() == [not o for o in root.ok], "only ok samples carry a percent"
    p = grid.zone_load_percent(_series(), _sensor(), basis="heat_power", context=M12)
    assert p[p.sns_key == "R-POWER"].load_percent.tolist()[:3] == [50.0, 80.0, 120.0]and set(p.sns_key) == {"R-POWER", "E-ST1", "E-ST2"}
    st = z[z.level == "station"]
    assert set(st.zone_key) == {"ZONE-4"} and set(st.basis) == {"station"} and set(st.sns_key) == {"E-ST1", "E-ST2"}, "the electric zone has stations, no zone value"
    assert "OTHER" not in set(z.sns_key) and z.ts.is_monotonic_increasing is False
    with pytest.raises(FrameError, match="basis must be"):
        grid.zone_load_percent(_series(), _sensor(), basis="flow", context=M12)
    with pytest.raises(FrameError, match="positive rated_value"):
        grid.zone_load_percent(_series(), _sensor().assign(rated_value=np.nan), basis="heat_power", context=M12)
    two = pd.concat([_sensor(), _sensor().iloc[[0]].assign(sns_key="R-LOAD2")])
    with pytest.raises(FrameError, match="more than one root"):
        grid.zone_load_percent(_series(), two, context=M12)
    assert grid.zone_load_percent(_series().iloc[:0], _sensor(), context=M12).empty


def _weather():
    return pd.DataFrame({"station_key": "WST-1", "ts": pd.date_range("2026-01-18 22:00", periods=6, freq="h"), "temp_c": [-5.0, -6.0, -7.0, -8.0, -9.0, -10.0]})


def test_peak_load_is_the_first_ok_maximum_with_its_context():
    z = grid.zone_load_percent(_series(), _sensor(), context=M12)
    supply = _meas("R-SUPPLY", [80.0, 81.0, 95.0, 99.0, 90.0, 85.0, 84.0, 83.0])
    p = grid.peak_load(z, _sensor(), _weather(), supply, context=M12).set_index("sns_key")
    r = p.loc["R-LOAD"]
    assert (r.peak_percent, r.peak_ts_utc, r.ok_samples, r.rows) == (120.0, T0 + pd.Timedelta(minutes=30), 6, 8), "the suspect 130 never counts"
    assert str(r.peak_ts_local) == "2026-01-19 01:30:00+01:00" and r.completeness == 0.75 and not r.valid, "0.75 of the samples are ok: below the default 0.9"
    assert r.outdoor_c == -7.0, "last hourly observation at or before 00:30 is the one of 00:00"
    assert r.supply_temp_c == 95.0 and r.level == "zone" and r.basis == "load_percent"
    assert p.loc["H-LOAD", "peak_percent"] == 30.0 and np.isnan(p.loc["H-LOAD", "supply_temp_c"]) and p.loc["H-LOAD", "valid"]
    assert p.loc["E-ST1", ["peak_percent", "level"]].tolist() == [110.0, "station"]
    assert grid.peak_load(z, _sensor(), _weather(), min_completeness=0.7, context=M12).set_index("sns_key").loc["R-LOAD", "valid"], "the minimum completeness is a keyword"
    tie = grid.peak_load(grid.zone_load_percent(pd.concat([_meas("H-LOAD", [50.0, 50.0], step="h")]), _sensor(), context=M12), _sensor(), _weather(), context=M12).iloc[0]
    assert tie.peak_ts_utc == T0, "ties take the first sample"
    far = grid.peak_load(z, _sensor(), _weather().assign(ts=_weather().ts + pd.Timedelta(days=3)), context=M12).set_index("sns_key")
    assert np.isnan(far.loc["R-LOAD", "outdoor_c"]), "an observation older than 1.5 hours is no outdoor temperature"
    allbad = grid.zone_load_percent(_meas("H-LOAD", [1.0, 2.0], flags=["suspect", "missing"], step="h"), _sensor(), context=M12)
    e = grid.peak_load(allbad, _sensor(), _weather(), context=M12).iloc[0]
    assert np.isnan(e.peak_percent) and pd.isna(e.peak_ts_utc) and not e.valid and e.completeness == 0.0
    for bad in (-0.1, 1.5, True, "0.9"):
        with pytest.raises(FrameError, match="min_completeness"):
            grid.peak_load(z, _sensor(), _weather(), min_completeness=bad, context=M12)


def test_hours_above_use_the_interval_and_ok_samples_only():
    z = grid.zone_load_percent(_series(), _sensor(), context=M12)
    h = grid.hours_above(z, _sensor(), bands=(100.0, 90.0), context=M12)
    r = h[h.sns_key == "R-LOAD"].set_index("band")
    assert r.loc[100.0, "hours_above"] == 0.5 and r.loc[90.0, "hours_above"] == 0.75, "above 100: 120 and 101 (100 itself is not), 0.5 h; above 90: 120, 100 and 101 (90 itself is not), 0.75 h"
    assert r.loc[100.0, "ok_samples"] == 6 and r.loc[100.0, "rows"] == 8 and r.loc[100.0, "coverage"] == 0.75
    s = h[h.sns_key == "E-ST1"].set_index("band")
    assert s.loc[100.0, "hours_above"] == 1.0, "an hourly station sample is one hour"
    assert grid.hours_above(z, _sensor(), context=M12).band.unique().tolist() == [90.0, 100.0, 105.0]
    for bands in ([], ["x"], [np.nan], [True]):
        with pytest.raises(FrameError, match="bands"):
            grid.hours_above(z, _sensor(), bands=bands, context=M12)


def test_winter_label_and_the_load_duration_curve():
    assert grid.winter_label(pd.Timestamp("2026-01-17"), context=M12) == "2025/26" and grid.winter_label(pd.Timestamp("2025-11-01"), context=M12) == "2025/26"
    assert grid.winter_label(pd.Timestamp("2026-04-30"), context=M12) is None and grid.winter_label(pd.Timestamp("2026-10-31"), context=M12) is None and grid.winter_label("2026-03-31", context=M12) == "2025/26"
    s = grid.winter_label(pd.Series(pd.to_datetime(["2026-01-17", "2026-07-01", "2026-12-01"]), index=[5, 6, 7]), context=M12)
    assert s.to_dict() == {5: "2025/26", 6: None, 7: "2026/27"}
    assert grid.winter_label(pd.Timestamp("2026-10-31"), months=(10, 11), context=M12) == "2026/27"
    with pytest.raises(FrameError, match="month numbers"):
        grid.winter_label(pd.Timestamp("2026-01-01"), months=[13], context=M12)
    z = grid.zone_load_percent(_series(), _sensor(), context=M12)
    c = grid.load_duration_curve(z, _sensor(), context=M12)
    r = c[c.sns_key == "R-LOAD"]
    assert r.load_percent.tolist() == [120.0, 101.0, 100.0, 90.0, 80.0, 50.0] and r["rank"].tolist() == [1, 2, 3, 4, 5, 6] and r.hours.tolist() == [0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
    summer = z.assign(ts=z.ts + pd.Timedelta(days=170))
    assert grid.load_duration_curve(summer, _sensor(), winter_only=True, context=M12).empty and len(grid.load_duration_curve(z, _sensor(), winter_only=True, context=M12)) == len(c)
    assert len(grid.load_duration_curve(summer, _sensor(), winter_only=True, months=(6, 7), context=M12)) == len(c)


def test_rank_zones_lists_heat_by_peak_and_stations_apart():
    s = pd.DataFrame({"zone_key": ["Z1", "Z2", "Z3", "Z4", "Z4"], "sns_key": ["a", "b", "c", "d", "e"], "level": ["zone"] * 3 + ["station"] * 2, "basis": ["load_percent"] * 3 + ["station"] * 2,
                      "peak_percent": [97.0, 118.0, 130.0, 110.0, 70.0], "valid": [True, True, False, True, True]})
    r = grid.rank_zones(s, context=M12)
    assert r[["rank", "zone_key"]].values.tolist()[:2] == [[1.0, "Z2"], [2.0, "Z1"]] and r["rank"].isna().tolist() == [False, False, True, True, True]
    assert r.zone_key.tolist() == ["Z2", "Z1", "Z3", "Z4", "Z4"] and r[r.zone_key == "Z4"].basis.eq("station").all(), "the station percent has no rank among the zones"
    assert grid.rank_zones(s.iloc[:0], context=M12).empty


def _daily(values, zone="Z1", start="2026-01-10"):
    return pd.DataFrame({"zone_key": zone, "date": pd.date_range(start, periods=len(values)), "t_min": values})


def test_cold_snaps_core_extension_and_gaps():
    t = [-2.0, -5.0, -9.0, -12.0, -10.0, -6.0, -4.0, -3.0, -1.0]                    # core: three days of -9 to -10, extended over -5 and -6 and -4 (<= -4)
    s = grid.cold_snaps(_daily(t), context=M12).iloc[0]
    assert (s.zone_key, str(s.start.date()), str(s.end.date()), s.days, s.core_days, s.t_min, str(s.t_min_date.date())) == ("Z1", "2026-01-11", "2026-01-16", 6, 3, -12.0, "2026-01-13")
    assert len(grid.cold_snaps(_daily([-9.0, -9.0, -1.0, -9.0, -9.0, -1.0]), context=M12)) == 2, "two core days are a snap: the default reads the proposed fact (2), owner decision 2026-11-13"
    assert len(grid.cold_snaps(_daily([-9.0, -9.0, -1.0, -9.0, -9.0, -1.0]), min_core_days=2, context=M12)) == 2
    assert len(grid.cold_snaps(pd.concat([_daily(t), _daily(t, zone="Z2")]), context=M12)) == 2
    gap = _daily(t).drop(index=3)
    assert grid.cold_snaps(gap, context=M12).empty or grid.cold_snaps(gap, context=M12).core_days.iloc[0] < 3, "a missing day ends a run"
    assert grid.cold_snaps(_daily([-9.0, np.nan, -9.0, -9.0, -9.0]), context=M12).iloc[0].start == pd.Timestamp("2026-01-12"), "a null day is no cold day"
    assert grid.cold_snaps(_daily([-20.0, -20.0, -20.0]), core_c=-30.0, context=M12).empty and grid.cold_snaps(_daily([]), context=M12).empty
    for kw in (dict(core_c=np.nan), dict(edge_c=-20.0), dict(min_core_days=0), dict(min_core_days=True)):
        with pytest.raises(FrameError):
            grid.cold_snaps(_daily(t), context=M12, **kw)
    with pytest.raises(FrameError, match="more than one row"):
        grid.cold_snaps(pd.concat([_daily(t), _daily(t)]), context=M12)


def test_review_cases_nulls_order_flags_boundaries_and_winters():
    # design capacity: decimal half up, negative capacity
    g = pd.DataFrame({"zone_key": ["Z4"], "element_type": ["transformer_station"], "status": ["in_service"], "rated_capacity": [1050.0], "capacity_unit": ["kVA"]})
    assert grid.recompute_design_capacity(g, context=M12).design_capacity.tolist() == [0.473], "1,050 kVA times 0.45 is 0.4725: half up"
    with pytest.raises(FrameError, match="zero or more"):
        grid.recompute_design_capacity(g.assign(rated_capacity=-1.0), context=M12)
    with pytest.raises(FrameError, match="without a zone_key"):
        grid.recompute_design_capacity(g.assign(zone_key=None), context=M12)
    z = grid.zone_load_percent(_series(), _sensor(), context=M12)
    # estimated and infinite values are no samples
    est = _series().assign(quality_flag=lambda d: d.quality_flag.where(d.index != 0, "estimated"))
    assert not grid.zone_load_percent(est, _sensor(), context=M12).query("sns_key == 'R-LOAD'").ok.iloc[0]
    inf = _series().assign(value=lambda d: d.value.where(~((d.sns_key == "R-LOAD") & (d.ts == T0 + pd.Timedelta(minutes=30))), np.inf))
    assert not grid.zone_load_percent(inf, _sensor(), context=M12).query("sns_key == 'R-LOAD'").ok.iloc[2], "an infinite value is no sample"
    # peak: first sample whatever the row order, equality of the completeness limit, age limits
    tie = grid.zone_load_percent(_meas("H-LOAD", [50.0, 50.0, 50.0], step="h"), _sensor(), context=M12).iloc[::-1]
    assert grid.peak_load(tie, _sensor(), _weather(), context=M12).iloc[0].peak_ts_utc == T0, "the first sample in time, not in row order"
    r = grid.peak_load(z, _sensor(), _weather(), min_completeness=0.75, context=M12).set_index("sns_key").loc["R-LOAD"]
    assert r.valid and r.completeness == 0.75, "completeness equal to the minimum is valid"
    w1 = pd.DataFrame({"station_key": "WST-1", "ts": [T0 - pd.Timedelta(hours=1, minutes=30)], "temp_c": [-3.0]})
    p = grid.peak_load(z, _sensor(), _weather().assign(ts=_weather().ts + pd.Timedelta(minutes=30)), context=M12).set_index("sns_key").loc["R-LOAD"]
    assert p.peak_ts_utc == T0 + pd.Timedelta(minutes=30) and p.outdoor_c == -7.0, "an observation at the peak time itself counts"
    w2 = pd.DataFrame({"station_key": "WST-1", "ts": [T0 + pd.Timedelta(minutes=30) - pd.Timedelta(hours=1, minutes=30)], "temp_c": [-3.0]})
    w3 = w2.assign(ts=w2.ts - pd.Timedelta(minutes=1))
    assert grid.peak_load(z, _sensor(), w2, context=M12).set_index("sns_key").loc["R-LOAD", "outdoor_c"] == -3.0 and np.isnan(grid.peak_load(z, _sensor(), w3, context=M12).set_index("sns_key").loc["R-LOAD", "outdoor_c"]), "exactly 1.5 hours old counts, one minute more does not"
    sel = lambda w, **kw: grid.peak_load(z, _sensor(), w, context=M12, **kw).set_index("sns_key").loc["R-LOAD", "outdoor_c"]
    assert np.isnan(sel(w2, max_age_hours=1.0)) and sel(w3, max_age_hours=1.6) == -3.0, "the age limit is a keyword (proposed 1.5 hours)"
    for bad in (-1, np.nan, True, "1.5"):
        with pytest.raises(FrameError, match="max_age_hours"):
            grid.peak_load(z, _sensor(), w2, max_age_hours=bad, context=M12)
    with pytest.raises(FrameError, match="not a date|timestamp|time zone"):
        grid.peak_load(z.assign(ts=pd.to_datetime(z.ts).dt.tz_localize("UTC")), _sensor(), _weather(), context=M12)
    with pytest.raises(FrameError, match="null zone_key or sns_key"):
        grid.peak_load(z.assign(zone_key=None), _sensor(), _weather(), context=M12)
    # supply maximum and outdoor minimum over the span of the series
    supply = _meas("R-SUPPLY", [80.0, 81.0, 95.0, 99.0, 90.0, 85.0, 84.0, 83.0], flags=["ok", "ok", "ok", "suspect", "ok", "ok", "ok", "ok"])
    ex = grid.peak_load(z, _sensor(), _weather(), supply, context=M12).set_index("sns_key").loc["R-LOAD"]
    assert ex.supply_temp_max_c == 95.0, "the suspect 99 never counts"
    assert ex.outdoor_min_c == -8.0, "lowest observation of the station within the span of the series (00:00 to 01:45)"
    # hours: sensors must be known, ldc by winter
    with pytest.raises(FrameError, match="not in telemetry.sensor"):
        grid.hours_above(z, _sensor().iloc[2:], context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.hours_above(z, pd.concat([_sensor(), _sensor().iloc[:1]]), context=M12)
    h = grid.load_duration_curve(z, _sensor(), context=M12)
    assert h[h.sns_key == "H-LOAD"].hours.tolist() == [1.0, 2.0, 3.0], "an hourly sensor counts one hour a sample"
    two = pd.concat([z, z.assign(ts=z.ts + pd.Timedelta(days=365))], ignore_index=True)
    bw = grid.load_duration_curve(two, _sensor(), by_winter=True, context=M12)
    assert set(bw.winter) == {"2025/26", "2026/27"} and bw.groupby(["sns_key", "winter"])["rank"].min().eq(1).all()
    # winter label with a missing timestamp, months at the boundaries
    lab = grid.winter_label(pd.Series(pd.to_datetime(["2026-01-17", None, "2026-12-01"])), context=M12)
    assert lab.tolist() == ["2025/26", None, "2026/27"]
    for m, month in ((11, "2025-11-30"), (3, "2026-03-31")):
        assert grid.winter_label(pd.Timestamp(month), context=M12) == "2025/26"
    assert grid.winter_label(pd.Timestamp("2026-06-30"), months=(6, 7), context=M12) == "2025/26" and grid.winter_label(pd.Timestamp("2026-07-01"), months=(6, 7), context=M12) == "2026/27", "the season starts in July"
    # rank zones with a repeated index
    a = pd.DataFrame({"zone_key": ["Z1", "Z2"], "sns_key": ["a", "b"], "level": "zone", "basis": "load_percent", "peak_percent": [97.0, 118.0], "valid": [True, False]})
    b = pd.DataFrame({"zone_key": ["Z3", "Z4"], "sns_key": ["c", "d"], "level": "zone", "basis": "load_percent", "peak_percent": [91.0, 120.0], "valid": [False, True]})
    rr = grid.rank_zones(pd.concat([a, b]), context=M12)
    assert rr.zone_key.tolist()[:2] == ["Z4", "Z1"] and sorted(rr.zone_key) == ["Z1", "Z2", "Z3", "Z4"] and rr["rank"].isna().sum() == 2, "invalid zones stay listed without a rank"
    # cold snaps: the core limit is inclusive, the order of the rows does not matter
    t = _daily([-8.0, -8.0, -8.0, -5.0]).sample(frac=1, random_state=3)
    assert grid.cold_snaps(t, context=M12).iloc[0].core_days == 3
    assert grid.cold_snaps(_daily([-7.9, -8.0, -8.0, -8.0]), context=M12).iloc[0].core_days == 3 and grid.cold_snaps(_daily([-7.9, -8.0, -8.0, -8.0]), context=M12).iloc[0].days == 4 and grid.cold_snaps(_daily([-8.0, -8.0, -8.0, -4.0, -4.0]), context=M12).iloc[0].days == 5, "the edge limit is inclusive"
    gap = pd.concat([_daily([-9.0, -9.0, -9.0]), _daily([-9.0, -9.0, -9.0], start="2026-01-14")])
    assert len(grid.cold_snaps(gap, context=M12)) == 2, "a missing day separates two snaps"
    assert grid.cold_snaps(_daily([-9.0, -9.0, -9.0]).assign(date=lambda d: d.date + pd.Timedelta(hours=5)), context=M12).iloc[0].start == pd.Timestamp("2026-01-10")
