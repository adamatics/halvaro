"""Alarms (plan 5.4): hand computed series for the rule, then the baseline release against the stored alarm, alarm_rule and service.ticket_alarm tables."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")
T0 = pd.Timestamp("2025-01-01 00:00")


def _sensor(**kw):
    base = {"sns_key": ["S1"], "net_key": "NET-1", "zone_key": "ZONE-1", "sensor_type": "load_percent", "interval_s": 3600, "limit_high": 100.0, "limit_low": np.nan, "limit_high_crit": 120.0,
            "limit_low_crit": np.nan, "alarm_min_duration_s": 7200, "alarm_merge_gap_s": 10800}
    base.update({k: [v] if not isinstance(v, list) else v for k, v in kw.items()})
    return pd.DataFrame(base)


def _m(values, flags=None, key="S1"):
    n = len(values)
    return pd.DataFrame({"sns_key": key, "ts": pd.date_range(T0, periods=n, freq="h"), "value": values, "quality_flag": flags or ["ok"] * n})


def _series():
    v = [50.0] * 12
    v[2], v[3], v[5], v[7], v[8] = 110.0, 130.0, 105.0, 102.0, 103.0
    return v


def test_runs_merge_gap_severity_and_samples_of_one_alarm():
    a = grid.recompute_alarms(_m(_series()), _sensor(), context=M12)
    assert len(a) == 1 and a.columns.tolist() == ["sns_key", "raised_ts", "cleared_ts", "severity", "alarm_type", "net_key", "zone_key", "peak_value", "limit_value", "samples"]
    r = a.iloc[0]
    assert (r.raised_ts, r.cleared_ts) == (T0 + pd.Timedelta(hours=2), T0 + pd.Timedelta(hours=9)), "cleared is the end of the last violating sample"
    assert (r.severity, r.alarm_type, r.peak_value, r.limit_value, r.samples, r.net_key, r.zone_key) == ("critical", "load_high", 130.0, 100.0, 5, "NET-1", "ZONE-1"), "the short run inside the alarm still counts as a sample"


def test_a_gap_beyond_the_merge_gap_splits_and_a_short_run_alone_is_no_alarm():
    a = grid.recompute_alarms(_m(_series()), _sensor(alarm_merge_gap_s=7200), context=M12)
    assert a[["raised_ts", "cleared_ts", "severity", "peak_value", "samples"]].values.tolist() == [[T0 + pd.Timedelta(hours=2), T0 + pd.Timedelta(hours=4), "critical", 130.0, 2], [T0 + pd.Timedelta(hours=7), T0 + pd.Timedelta(hours=9), "warning", 103.0, 2]]
    one = [50.0] * 8
    one[3] = 150.0
    assert grid.recompute_alarms(_m(one), _sensor(), context=M12).empty, "one sample is shorter than the minimum run of two"
    assert len(grid.recompute_alarms(_m(one), _sensor(alarm_min_duration_s=3600), context=M12)) == 1 and len(grid.recompute_alarms(_m(one), _sensor(alarm_min_duration_s=3601), context=M12)) == 0, "the run needs ceil(min/interval) samples"
    assert grid.recompute_alarms(_m([100.0] * 6), _sensor(alarm_min_duration_s=0), context=M12).empty, "the limit itself is not a violation"


def test_only_ok_samples_count_and_a_missing_slot_breaks_the_run():
    flags = ["ok"] * 12
    flags[3] = "suspect"
    assert grid.recompute_alarms(_m(_series(), flags), _sensor(alarm_merge_gap_s=7200), context=M12).raised_ts.tolist() == [T0 + pd.Timedelta(hours=7)], "a suspect sample ends the run: 110 alone is too short"
    est = ["ok"] * 12
    est[2] = "estimated"
    assert len(grid.recompute_alarms(_m(_series(), est), _sensor(alarm_merge_gap_s=7200), context=M12)) == 1
    missing = _m(_series()).drop(index=3).reset_index(drop=True)
    assert grid.recompute_alarms(missing, _sensor(alarm_merge_gap_s=7200), context=M12).raised_ts.tolist() == [T0 + pd.Timedelta(hours=7)], "a slot not in the frame is not a violating sample"
    nan = _m(_series()).assign(value=lambda d: d.value.where(d.index != 3))
    assert len(grid.recompute_alarms(nan, _sensor(alarm_merge_gap_s=7200), context=M12)) == 1


def test_an_alarm_that_runs_to_the_end_of_the_series_has_no_cleared_time_and_low_limits_work():
    v = [50.0] * 8 + [101.0, 103.0]
    a = grid.recompute_alarms(_m(v), _sensor(), context=M12)
    assert a.iloc[0].raised_ts == T0 + pd.Timedelta(hours=8) and pd.isna(a.iloc[0].cleared_ts) and a.cleared_ts.dtype == "datetime64[ns]"
    lo = grid.recompute_alarms(_m([50.0, 30.0, 20.0, 50.0, 50.0]), _sensor(sensor_type="voltage", limit_high=np.nan, limit_high_crit=np.nan, limit_low=40.0, limit_low_crit=25.0), context=M12).iloc[0]
    assert (lo.alarm_type, lo.peak_value, lo.limit_value, lo.severity, lo.cleared_ts) == ("voltage_low", 20.0, 40.0, "critical", T0 + pd.Timedelta(hours=3))
    nocrit = grid.recompute_alarms(_m(_series()), _sensor(limit_high_crit=np.nan), context=M12).iloc[0]
    assert nocrit.severity == "warning", "no critical limit: warning"
    named = grid.recompute_alarms(_m([1.0, 0.0, 0.0, 1.0]), _sensor(sensor_type="breaker_state", limit_high=np.nan, limit_high_crit=np.nan, limit_low=0.5, alarm_min_duration_s=0, alarm_merge_gap_s=0), context=M12)
    assert named.alarm_type.tolist() == ["breaker_open"] and named.samples.tolist() == [2]
    assert grid.recompute_alarms(_m([0.0, 0.0]), _sensor(sensor_type="breaker_state", limit_high=np.nan, limit_low=0.5, alarm_min_duration_s=0, alarm_merge_gap_s=0), alarm_names={}, context=M12).alarm_type.tolist() == ["breaker_state_low"]


def test_sensors_without_limits_and_bad_input():
    two = pd.concat([_m(_series()), _m(_series(), key="S2")])
    s = pd.concat([_sensor(), _sensor(sns_key="S2", limit_high=np.nan, limit_high_crit=np.nan)])
    assert grid.recompute_alarms(two, s, context=M12).sns_key.unique().tolist() == ["S1"]
    assert grid.recompute_alarms(_m(_series()).iloc[:0], _sensor(), context=M12).empty
    for bad, msg in ((dict(alarm_min_duration_s=pd.NA), "alarm_min_duration_s"), (dict(alarm_merge_gap_s=np.nan), "alarm_min_duration_s or alarm_merge_gap_s"), (dict(interval_s=0), "interval_s must be a whole number")):
        with pytest.raises(FrameError, match=msg):
            grid.recompute_alarms(_m(_series()), _sensor(**bad), context=M12)
    with pytest.raises(FrameError, match="not in telemetry.sensor"):
        grid.recompute_alarms(_m(_series(), key="X"), _sensor(), context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.recompute_alarms(_m(_series()), pd.concat([_sensor(), _sensor()]), context=M12)


def test_alarm_rules_table_takes_min_and_max_over_the_sensors_of_a_type():
    s = pd.concat([_sensor(), _sensor(sns_key="S2", limit_high=105.0, limit_high_crit=125.0, alarm_min_duration_s=900, alarm_merge_gap_s=86400),
                   _sensor(sns_key="S3", sensor_type="voltage", limit_high=np.nan, limit_high_crit=np.nan, limit_low=200.0, limit_low_crit=180.0)])
    r = grid.alarm_rules_table(s, context=M12).set_index("alarm_type")
    assert r.loc["load_high", ["n_sensors", "limit_min", "limit_max", "critical_limit_min", "critical_limit_max", "min_duration_s", "merge_gap_s"]].tolist() == [2, 100.0, 105.0, 120.0, 125.0, 900, 86400]
    assert r.loc["voltage_low", ["direction", "sensor_type", "limit_min"]].tolist() == ["low", "voltage", 200.0]
    assert grid.alarm_rules_table(s, context=M12).rule_no.tolist() == [1, 2], "numbered by alarm type"


def test_alarm_summary_counts_and_the_background_rate():
    al = pd.DataFrame({"zone_key": ["Z1", "Z1", "Z1", "Z2"], "alarm_type": "load_high", "severity": ["warning", "warning", "critical", "warning"], "sns_key": "S",
                       "raised_ts": pd.to_datetime(["2025-01-05", "2025-01-30 23:00", "2025-02-01", "2026-01-01"], format="mixed")})
    s = grid.alarm_summary(al, first_month="2025-01", last_month="2026-12", context=M12)
    assert s.counts[["zone_key", "severity", "month", "n_alarms"]].values.tolist() == [["Z1", "critical", "2025-02", 1], ["Z1", "warning", "2025-01", 2], ["Z2", "warning", "2026-01", 1]]
    assert s.background[["zone_key", "year", "n_alarms", "months", "per_month"]].values.tolist() == [["Z1", 2025, 3, 12, 0.25], ["Z2", 2026, 1, 12, 0.0833]]
    d = grid.alarm_summary(al, context=M12).background
    assert d.months.tolist() == [12, 1], "default window is the span of the frame, 2025-01 to 2026-01: 12 months of 2025 and 1 of 2026"
    assert grid.alarm_summary(al.iloc[:0], context=M12).counts.empty
    with pytest.raises(FrameError, match="null zone_key"):
        grid.alarm_summary(al.assign(zone_key=None), context=M12)


def test_incident_groups_merge_by_element_type_and_gap():
    al = pd.DataFrame({"net_key": ["N1", "N1", "N1", "N2", "N1"], "alarm_type": ["load_high", "load_high", "load_high", "load_high", "voltage_low"],
                       "raised_ts": pd.to_datetime(["2025-01-01 00:00", "2025-01-03 00:00", "2025-01-10 00:00", "2025-01-01 00:00", "2025-01-01 01:00"]),
                       "cleared_ts": pd.to_datetime(["2025-01-01 02:00", "2025-01-03 01:00", None, "2025-01-01 02:00", "2025-01-01 03:00"])})
    g = grid.incident_groups(al, context=M12)
    assert g.index.equals(al.index) and g.tolist() == [1, 1, 2, 4, 3], "load_high merges within 60 h (48 h later is the same incident), voltage_low is another type"
    h = grid.incident_groups(al, merge_gap_hours={"default": 8.0}, context=M12)
    assert h.tolist() == [1, 2, 3, 5, 4], "the default gap of 8 h splits them"
    inside = al.assign(cleared_ts=pd.to_datetime(["2025-01-03 02:00", "2025-01-03 01:00", None, "2025-01-01 02:00", "2025-01-01 03:00"]))
    assert grid.incident_groups(inside, merge_gap_hours={"default": 0.0}, context=M12).tolist()[:2] == [1, 1], "an alarm that starts before the cleared time of the incident joins it"
    with pytest.raises(FrameError, match="default"):
        grid.incident_groups(al, merge_gap_hours={"load_high": 60.0}, context=M12)
    assert grid.incident_groups(al.iloc[:0], context=M12).empty


def test_alarm_ticket_link_marks_alarms_with_a_ticket():
    al = pd.DataFrame({"sns_key": ["S1", "S1", "S2"], "raised_ts": pd.to_datetime(["2025-01-01 01:00", "2025-01-02 01:00", "2025-01-01 01:00"]), "alarm_type": "load_high"})
    ta = pd.DataFrame({"sns_key": ["S1"], "raised_ts": pd.to_datetime(["2025-01-02 01:00"]), "link_type": "trigger", "tkt_key": "TKT-1", "alarm_type": "load_high"})
    r = grid.alarm_ticket_link(al, ta, pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    assert r.linked.tolist() == [False, True, False] and r.tkt_key.tolist()[1] == "TKT-1" and r.link_type.tolist()[1] == "trigger" and r.tkt_key.isna().tolist() == [True, False, True]
    with pytest.raises(FrameError, match="not in service.service_ticket"):
        grid.alarm_ticket_link(al, ta, pd.DataFrame({"tkt_key": ["TKT-2"]}), context=M12)
    with pytest.raises(FrameError, match="not in the alarm frame"):
        grid.alarm_ticket_link(al.iloc[:1], ta, pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    with pytest.raises(FrameError, match="more than one link"):
        grid.alarm_ticket_link(al, pd.concat([ta, ta]), pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)


def test_review_cases_boundaries_unsorted_input_and_nulls():
    # a merge gap that is not a multiple of the interval floors: 5400 s on 3600 s is one sample
    v = [50.0] * 12
    v[2], v[3], v[5], v[6] = 110.0, 110.0, 110.0, 110.0
    one = grid.recompute_alarms(_m(v), _sensor(alarm_merge_gap_s=5400), context=M12)
    assert len(one) == 1, "a gap of one sample (1 h) is inside 5400 s floored to one sample"
    assert len(grid.recompute_alarms(_m(v), _sensor(alarm_merge_gap_s=3599), context=M12)) == 2, "a gap of 3599 s floors to 0 samples: the runs stay apart"
    # low limit is strict, critical limits are reached with >= and <=
    low = _sensor(sensor_type="voltage", limit_high=np.nan, limit_high_crit=np.nan, limit_low=40.0, limit_low_crit=20.0, alarm_min_duration_s=0)
    assert grid.recompute_alarms(_m([40.0, 40.0]), low, context=M12).empty and grid.recompute_alarms(_m([39.9, 20.0]), low, context=M12).severity.tolist() == ["critical"]
    assert grid.recompute_alarms(_m([200.0, 120.0]), _sensor(alarm_min_duration_s=0), context=M12).severity.tolist() == ["critical"], "the critical limit itself is critical"
    # non-ok samples inside the alarm window do not make the peak, rows after the last violation make a cleared time
    flags = ["ok"] * 8
    flags[3] = "suspect"
    peak = grid.recompute_alarms(_m([50.0, 110.0, 105.0, 999.0, 105.0, 50.0, 50.0, 50.0], flags), _sensor(), context=M12).iloc[0]
    assert peak.peak_value == 110.0 and peak.cleared_ts == T0 + pd.Timedelta(hours=3) and peak.samples == 2, "the suspect 999 never counts and the single sample after it is no run"
    trailing = grid.recompute_alarms(_m([50.0, 110.0, 110.0, 50.0, 50.0], ["ok", "ok", "ok", "missing", "suspect"]), _sensor(), context=M12).iloc[0]
    assert trailing.cleared_ts == T0 + pd.Timedelta(hours=3), "rows after the last violating sample, whatever their flag, mean the series did not end inside the alarm"
    with pytest.raises(FrameError, match="whole number of seconds"):
        grid.recompute_alarms(_m(_series()), _sensor(interval_s=0.5), context=M12)
    with pytest.raises(FrameError, match="whole number of seconds"):
        grid.recompute_alarms(_m(_series()), _sensor(interval_s=pd.NA), context=M12)
    # rule table: nulls and duplicates are refused
    with pytest.raises(FrameError, match="no alarm_min_duration_s"):
        grid.alarm_rules_table(_sensor(alarm_merge_gap_s=np.nan), context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.alarm_rules_table(pd.concat([_sensor(), _sensor()]), context=M12)
    r = grid.alarm_rules_table(pd.concat([_sensor(sensor_type="voltage", limit_high=np.nan, limit_high_crit=np.nan, limit_low=1.0, limit_low_crit=0.5), _sensor(sns_key="S2", sensor_type="breaker_state")]), context=M12)
    assert r.alarm_type.tolist() == ["breaker_state_high", "voltage_low"] and r.rule_no.tolist() == [1, 2], "numbered by alarm type"


def test_review_cases_incident_boundary_summary_months_and_link_order():
    al = pd.DataFrame({"net_key": "N1", "alarm_type": "load_high", "raised_ts": pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", "2025-01-06 00:00"]), "cleared_ts": pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", None])})
    exact = al.assign(raised_ts=pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", "2025-01-06 00:00"]), cleared_ts=pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", "2025-01-06 00:00"]))
    assert grid.incident_groups(exact, context=M12).tolist() == [1, 1, 1], "gaps of exactly 60.0 h merge (<=)"
    over = exact.assign(raised_ts=pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", "2025-01-06 00:01"]), cleared_ts=pd.to_datetime(["2025-01-01 00:00", "2025-01-03 12:00", "2025-01-06 00:01"]))
    assert grid.incident_groups(over, context=M12).tolist() == [1, 1, 2], "more than 60 h does not"
    nested = pd.DataFrame({"net_key": "N1", "alarm_type": "load_high", "raised_ts": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-09"]), "cleared_ts": pd.to_datetime(["2025-01-08", "2025-01-03", "2025-01-09"])})
    assert grid.incident_groups(nested, context=M12).tolist() == [1, 1, 1], "the cleared time of an incident is the latest one (the nested alarm does not shorten it)"
    sh = pd.concat([al, al]).iloc[[3, 1, 0, 4, 2, 5]]
    assert grid.incident_groups(sh, context=M12).index.tolist() == sh.index.tolist() and len(grid.incident_groups(al.iloc[:0], context=M12)) == 0
    z = pd.DataFrame({"zone_key": "Z1", "alarm_type": "load_high", "severity": "warning", "sns_key": "S", "raised_ts": pd.to_datetime(["2025-01-31 23:00"])})
    assert grid.alarm_summary(z, context=M12).counts.month.tolist() == ["2025-01"], "months are UTC months"
    assert grid.alarm_summary(z, first_month="2025-1", last_month="2025-12", context=M12).background.n_alarms.tolist() == [1], "a month is normalised"
    assert grid.alarm_summary(z.iloc[:0], first_month="2025-01", context=M12).counts.empty
    with pytest.raises(FrameError, match="null raised_ts"):
        grid.alarm_summary(z.assign(raised_ts=pd.NaT), context=M12)
    with pytest.raises(FrameError, match="after last_month"):
        grid.alarm_summary(z, first_month="2025-05", last_month="2025-01", context=M12)
    a2 = pd.DataFrame({"sns_key": ["S2", "S1", "S1"], "raised_ts": pd.to_datetime(["2025-01-01 01:00", "2025-01-02 01:00", "2025-01-01 01:00"]), "alarm_type": "load_high"}, index=[10, 20, 30])
    ta = pd.DataFrame({"sns_key": ["S1"], "raised_ts": pd.to_datetime(["2025-01-02 01:00"]), "link_type": "trigger", "tkt_key": "TKT-1"})
    r = grid.alarm_ticket_link(a2, ta, pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    assert r.index.tolist() == [10, 20, 30] and r.sns_key.tolist() == ["S2", "S1", "S1"] and r.linked.tolist() == [False, True, False], "the rows and the index of the alarm frame are kept"
    with pytest.raises(FrameError, match="already has the column"):
        grid.alarm_ticket_link(a2.assign(linked=True), ta, pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    with pytest.raises(FrameError, match="need a sns_key and a raised_ts"):
        grid.alarm_ticket_link(a2.iloc[:1].assign(raised_ts=pd.NaT), ta.assign(raised_ts=pd.NaT), pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    full = a2.assign(net_key="N1", cleared_ts=a2.raised_ts + pd.Timedelta(hours=1))
    ri = grid.alarm_ticket_link(full, ta, pd.DataFrame({"tkt_key": ["TKT-1"]}), context=M12)
    assert ri.incident.nunique() == 1 and ri.incident_tickets.tolist() == [1, 1, 1], "tickets per incident"
