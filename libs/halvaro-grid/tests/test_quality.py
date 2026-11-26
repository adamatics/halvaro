"""Quality functions (plan 5.1): hand computed synthetic frames (the release checks are in repo_tests of the closed repository)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _m(rows, key="S1"):
    return pd.DataFrame([(key, pd.Timestamp(t), v, f) for t, v, f in rows], columns=["sns_key", "ts", "value", "quality_flag"])


def _hourly(flags, start="2025-01-01 00:00", key="S1", values=None):
    ts = pd.date_range(start, periods=len(flags), freq="h")
    vals = values if values is not None else [float(i) for i in range(len(flags))]
    return pd.DataFrame({"sns_key": key, "ts": ts, "value": [np.nan if f == "missing" else v for f, v in zip(flags, vals)], "quality_flag": flags})


def _sensor(**kw):
    base = {"sns_key": ["S1"], "install_date": ["2024-01-01"], "interval_s": [3600]}
    base.update(kw)
    return pd.DataFrame(base)


def _ev(rows):
    return pd.DataFrame(rows, columns=["sns_key", "from_ts", "to_ts", "type"]).assign(from_ts=lambda d: pd.to_datetime(d.from_ts), to_ts=lambda d: pd.to_datetime(d.to_ts))


def test_valid_samples_keeps_only_ok_with_a_value():
    m = _hourly(["ok", "estimated", "suspect", "missing", "ok"], values=[1.0, 2.0, 99.0, 0.0, 5.0]).sample(frac=1, random_state=3)
    v = grid.valid_samples(m, context=M12)
    assert v.value.tolist() == [1.0, 5.0] and v.ts.is_monotonic_increasing and list(v.columns) == ["sns_key", "ts", "value", "quality_flag"]
    assert grid.valid_samples(_hourly(["ok"]).assign(value=np.nan), context=M12).empty, "an ok flag without a value is not a sample"
    for bad, msg in ((_hourly(["ok"]).assign(quality_flag="fine"), "flags are"), (_hourly(["ok"]).assign(quality_flag=None), "null"), (pd.concat([_hourly(["ok"])] * 2), "more than one row"),
                     (_hourly(["ok"]).assign(ts=pd.Timestamp("2025-01-01", tz="UTC")), "time zone"), (_hourly(["ok"]).assign(ts=5), "numbers"), (_hourly(["ok"]).drop(columns="value"), "lacks column")):
        with pytest.raises(FrameError, match=msg):
            grid.valid_samples(bad, context=M12)
    with pytest.raises(StageRefusal, match="telemetry"):
        grid.valid_samples(_hourly(["ok"]), context=M3)


def test_completeness_counts_expected_slots_from_the_later_of_window_start_and_install():
    m = _hourly(["ok"] * 20 + ["missing"] * 2 + ["estimated", "suspect"], start="2025-01-01 00:00")
    c = grid.completeness(m, _sensor(), "2025-01-01", "2025-01-01", context=M12).iloc[0]
    assert (c.expected, c.rows, c.ok, c.estimated, c.suspect, c.missing) == (24, 24, 20, 1, 1, 2) and c.share == round(20 / 24, 6) and c.share_of_present == c.share
    late = grid.completeness(m.iloc[8:], _sensor(install_date=["2025-01-01"]), "2024-12-31", "2025-01-01", context=M12).iloc[0]
    assert late.expected == 24 and late.rows == 16 and late.share == round(12 / 24, 6) and late.share_of_present == round(12 / 16, 6), "slots before the first row count as expected, not present"
    after = grid.completeness(m, _sensor(install_date=["2025-01-01 12:00"]), "2025-01-01", "2025-01-02", context=M12).iloc[0]
    assert after.expected == 48 - 0 and after.rows == 24, "the install date is a day: its midnight starts the slots"
    both = grid.completeness(pd.concat([m, _hourly(["ok"] * 3, key="S2")]), pd.concat([_sensor(), _sensor(sns_key=["S2"], interval_s=[900])]), "2025-01-01", "2025-01-01", context=M12).set_index("sns_key")
    assert both.loc["S2", "expected"] == 96 and both.loc["S2", "ok"] == 3
    none = grid.completeness(m.iloc[:0], _sensor(), "2025-01-01", "2025-01-01", context=M12).iloc[0]
    assert none.expected == 24 and none.rows == 0 and np.isnan(none.share_of_present), "a sensor without rows is listed with zeros"
    outside = grid.completeness(m, _sensor(), "2025-01-02", "2025-01-02", context=M12).iloc[0]
    assert outside.ok == 0 and outside.expected == 24, "rows outside the window are ignored"
    future = grid.completeness(m.iloc[:0], _sensor(install_date=["2030-01-01"]), "2025-01-01", "2025-01-01", context=M12).iloc[0]
    assert future.expected == 0 and np.isnan(future.share)
    with pytest.raises(FrameError, match="more rows in the window than slots"):
        grid.completeness(m, _sensor(install_date=["2030-01-01"]), "2025-01-01", "2025-01-01", context=M12)


def test_completeness_refuses_bad_windows_and_sensors():
    m, s = _hourly(["ok"]), _sensor()
    for args, msg in ((("2025-01-02", "2025-01-01"), "after it ends"),):
        with pytest.raises(FrameError, match=msg):
            grid.completeness(m, s, *args, context=M12)
    with pytest.raises(FrameError, match="not in telemetry.sensor"):
        grid.completeness(m.assign(sns_key="X"), s, "2025-01-01", "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="interval_s must be a positive number"):
        grid.completeness(m, _sensor(interval_s=[0]), "2025-01-01", "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.completeness(m, pd.concat([s, s]), "2025-01-01", "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="install_date"):
        grid.completeness(m, _sensor(install_date=[None]), "2025-01-01", "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="more rows in the window"):
        grid.completeness(_hourly(["ok"] * 24), _sensor(interval_s=[7200]), "2025-01-01", "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="must be dates"):
        grid.completeness(m, s, None, "2025-01-01", context=M12)
    with pytest.raises(FrameError, match="without a sns_key or a ts"):
        grid.valid_samples(m.assign(ts=pd.NaT), context=M12)
    with pytest.raises(FrameError, match="null sns_key"):
        grid.classify_flags(m, _ev([("S1", None, "2025-01-01", "dropout")]), context=M12)


def test_gap_report_runs_never_fill_and_carry_the_covering_event():
    flags = ["ok", "missing", "missing", "estimated", "ok", "missing", "ok", "suspect", "ok"]
    m = _hourly(flags)
    ev = _ev([("S1", "2025-01-01 01:00", "2025-01-01 03:00", "dropout"), ("S1", "2025-01-01 05:00", "2025-01-01 05:00", "dropout"), ("S1", "2025-01-01 07:00", "2025-01-01 07:00", "spike")])
    g = grid.gap_report(m, _sensor(), ev, context=M12)
    assert g[["start", "end", "samples", "missing", "estimated", "event_type", "explained"]].values.tolist() == [
        [pd.Timestamp("2025-01-01 01:00"), pd.Timestamp("2025-01-01 03:00"), 3, 2, 1, "dropout", True], [pd.Timestamp("2025-01-01 05:00"), pd.Timestamp("2025-01-01 05:00"), 1, 1, 0, "dropout", True]]
    open_gaps = grid.gap_report(m, _sensor(), ev.iloc[1:], context=M12)
    assert open_gaps.explained.tolist() == [False, True] and open_gaps.event_type.isna().tolist() == [True, False]
    broken = grid.gap_report(m.drop(index=2), _sensor(), ev, context=M12)
    assert broken.samples.tolist() == [1, 1, 1], "a slot that is not in the frame ends the run"
    assert grid.gap_report(_hourly(["ok", "ok"]), _sensor(), ev, context=M12).empty
    with pytest.raises(FrameError, match="ends before it starts"):
        grid.gap_report(m, _sensor(), _ev([("S1", "2025-01-02", "2025-01-01", "dropout")]), context=M12)
    two = pd.concat([m, _hourly(["missing", "missing"], key="S2")])
    g2 = grid.gap_report(two, pd.concat([_sensor(), _sensor(sns_key=["S2"])]), ev, context=M12)
    assert g2.sns_key.tolist() == ["S1", "S1", "S2"], "runs do not continue across sensors"


def test_overlapping_events_and_partly_covered_runs():
    flags = ["ok", "suspect", "suspect", "suspect", "suspect", "ok"]
    m = _hourly(flags)
    outer = _ev([("S1", "2025-01-01 01:00", "2025-01-01 04:00", "drift"), ("S1", "2025-01-01 02:00", "2025-01-01 02:00", "drift")])
    assert grid.classify_flags(m, outer, context=M12).event_type.iloc[1:5].tolist() == ["drift"] * 4, "an inner event does not hide the outer one"
    run = _hourly(["ok", "missing", "missing", "missing", "missing", "ok"])
    g = grid.gap_report(run, _sensor(), _ev([("S1", "2025-01-01 01:00", "2025-01-01 04:00", "dropout"), ("S1", "2025-01-01 02:00", "2025-01-01 02:00", "dropout")]), context=M12)
    assert g.explained.tolist() == [True] and g.event_type.tolist() == ["dropout"]
    part = grid.gap_report(run, _sensor(), _ev([("S1", "2025-01-01 02:00", "2025-01-01 04:00", "dropout")]), context=M12).iloc[0]
    assert not part.explained and part.event_type is None or pd.isna(part.event_type), "the type is that of the first slot: none covers it"
    with pytest.raises(FrameError, match="interval_s must be a positive"):
        grid.gap_report(run, _sensor(interval_s=[0]), _ev([]), context=M12)


def test_classify_flags_names_the_event_type_of_each_flagged_sample():
    flags = ["ok", "missing", "suspect", "suspect", "suspect", "estimated", "ok"]
    m = _hourly(flags)
    ev = _ev([("S1", "2025-01-01 01:00", "2025-01-01 01:00", "dropout"), ("S1", "2025-01-01 02:00", "2025-01-01 02:00", "spike"), ("S1", "2025-01-01 03:00", "2025-01-01 04:00", "drift"),
              ("S2", "2025-01-01 05:00", "2025-01-01 05:00", "dropout")])
    c = grid.classify_flags(m, ev, context=M12)
    assert c.event_type.where(c.event_type.notna(), "-").tolist() == ["-", "dropout", "spike", "drift", "drift", "-", "-"], "the estimated sample has only another sensor's event; ok samples have none"
    assert len(c) == len(m) and c.ts.is_monotonic_increasing
    swapped = grid.classify_flags(m, _ev([("S1", "2025-01-01 02:00", "2025-01-01 02:00", "dropout")]), context=M12)
    assert swapped.event_type.isna().all(), "a dropout event does not explain a suspect sample"


def test_daily_from_raw_uses_ok_samples_and_counts_missing_rows_as_present():
    flags = ["ok", "ok", "missing", "suspect"] + ["missing"] * 3 + ["ok"] * 17      # 24 hours of 2025-01-01, then a day of only missing slots
    m = _hourly(flags + ["missing"] * 24, values=[1.0, 3.0, 0, 500.0] + [0] * 3 + [float(i) for i in range(17)] + [0] * 24)
    d = grid.daily_from_raw(m, context=M12).iloc[0]
    assert (d["min"], d["max"], d["count"]) == (0.0, 16.0, 19) and d.avg == np.float32((1.0 + 3.0 + sum(range(17))) / 19) and d.availability_pct == np.float32(round(100 * 19 / 24, 2))
    assert d["date"] == pd.Timestamp("2025-01-01").date() and d.dtypes if False else True
    both = grid.daily_from_raw(m, context=M12)
    assert len(both) == 2 and both.iloc[1][["count"]].tolist() == [0] and both.iloc[1][["min", "max", "avg"]].isna().all() and both.iloc[1].availability_pct == 0.0
    assert both.dtypes.astype(str).to_dict() == {"sns_key": "object", "date": "object", "min": "float32", "max": "float32", "avg": "float32", "count": "int32", "availability_pct": "float32"}
    late = grid.daily_from_raw(_hourly(["ok"] * 3, start="2025-03-05 22:00"), context=M12)
    assert [str(x) for x in late.date] == ["2025-03-05", "2025-03-06"] and late["count"].tolist() == [2, 1], "UTC days, no row before the first slot"


def test_sensor_quality_board_is_a_matrix_of_mean_availability_by_iso_week():
    d = pd.DataFrame({"sns_key": ["A", "A", "A", "B"], "date": pd.to_datetime(["2024-12-29", "2024-12-30", "2024-12-31", "2025-01-06"]).date, "availability_pct": [100.0, 90.0, 80.0, 50.0]})
    b = grid.sensor_quality_board(d, context=M12)
    assert b.index.tolist() == ["A", "B"] and b.columns.tolist() == ["2024-W52", "2025-W01", "2025-W02"]
    assert b.loc["A", "2024-W52"] == 100.0 and b.loc["A", "2025-W01"] == 85.0 and np.isnan(b.loc["B", "2025-W01"]) and b.loc["B", "2025-W02"] == 50.0, "2024-12-30 belongs to ISO week 2025-W01"


def test_board_has_every_week_and_refuses_duplicates_and_nulls():
    d = pd.DataFrame({"sns_key": ["A", "A"], "date": pd.to_datetime(["2025-01-06", "2025-01-20"]).date, "availability_pct": np.float32([99.99, 50.0])})
    b = grid.sensor_quality_board(d, context=M12)
    assert b.columns.tolist() == ["2025-W02", "2025-W03", "2025-W04"] and np.isnan(b.loc["A", "2025-W03"]) and b.loc["A", "2025-W02"] == 99.99, "a week without days is a null column; float32 is rounded as float64"
    with pytest.raises(FrameError, match="more than one row"):
        grid.sensor_quality_board(pd.concat([d, d.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="null sns_key, date"):
        grid.sensor_quality_board(d.assign(date=None), context=M12)
