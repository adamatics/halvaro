"""Series helpers (plan 5.2): local time, interval, bucket peaks, outdoor temperature at a time."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")


def _m(rows, key="S1"):
    return pd.DataFrame([(key, pd.Timestamp(t), v, f) for t, v, f in rows], columns=["sns_key", "ts", "value", "quality_flag"])


def _s(**kw):
    return pd.DataFrame({"sns_key": ["S1"], "interval_s": [900], **kw})


def test_to_local_is_dst_aware_and_refuses_unknown_countries():
    t = pd.Series(pd.to_datetime(["2026-01-16 23:00", "2026-07-01 12:00", "2026-03-29 00:30", "2026-03-29 01:30"]))
    dk = grid.to_local(t, "DK", context=M12)
    assert dk.dt.tz is not None and dk.dt.strftime("%Y-%m-%d %H:%M %z").tolist() == ["2026-01-17 00:00 +0100", "2026-07-01 14:00 +0200", "2026-03-29 01:30 +0100", "2026-03-29 03:30 +0200"]
    assert grid.to_local(t, "DE", context=M12).dt.strftime("%Y-%m-%d %H:%M %z").tolist() == dk.dt.strftime("%Y-%m-%d %H:%M %z").tolist(), "Copenhagen and Berlin share offsets"
    assert grid.to_local(t, "SE", timezones={"SE": "Europe/Stockholm"}, context=M12).dt.tz is not None
    for bad in ("FR", None, ["DK"]):
        with pytest.raises(FrameError, match="no time zone"):
            grid.to_local(t, bad, context=M12)
    with pytest.raises(FrameError, match="time zone"):
        grid.to_local(t.dt.tz_localize("UTC"), "DK", context=M12)


def test_unknown_time_zone_names_and_the_autumn_change_in_hour_buckets():
    t = pd.Series(pd.to_datetime(["2025-10-26 00:00"]))
    with pytest.raises(FrameError, match="not a time zone name"):
        grid.to_local(t, "SE", timezones={"SE": "Mars/Olympus"}, context=M12)
    m = _m([("2025-10-26 00:00", 1.0, "ok"), ("2025-10-26 00:15", 2.0, "ok"), ("2025-10-26 01:00", 3.0, "ok"), ("2025-10-26 01:15", 4.0, "ok"), ("2025-10-26 02:00", 5.0, "ok")])
    h = grid.bucket_peak(m, _s(), "hour", tz="Europe/Copenhagen", context=M12)
    assert [str(b) for b in h.bucket] == ["2025-10-26 02:00:00+02:00", "2025-10-26 02:00:00+01:00", "2025-10-26 03:00:00+01:00"] and h.peak.tolist() == [2.0, 4.0, 5.0], "the repeated 02:00 hour is two buckets"
    d = grid.bucket_peak(m, _s(), "day", tz="Europe/Copenhagen", context=M12)
    assert d.ok_count.tolist() == [5] and d.ok_hours.tolist() == [1.25]
    for tz in ("Mars/Olympus", ""):
        with pytest.raises(FrameError, match="time zone"):
            grid.bucket_peak(m, _s(), "day", tz=tz, context=M12)
    ordered = grid.bucket_peak(pd.concat([_m([("2025-01-01 00:00", 1.0, "ok")], key="B"), _m([("2025-01-01 00:00", 2.0, "ok")], key="A")]), pd.concat([_s(sns_key=["A"]), _s(sns_key=["B"])]), "day", context=M12)
    assert ordered.sns_key.tolist() == ["A", "B"]


def test_interval_hours():
    h = grid.interval_hours(pd.DataFrame({"sns_key": ["A", "B"], "interval_s": [900, 3600]}), context=M12)
    assert h.to_dict() == {"A": 0.25, "B": 1.0} and h.name == "interval_hours"
    for bad in (pd.DataFrame({"sns_key": ["A"], "interval_s": [0]}), pd.DataFrame({"sns_key": ["A", "A"], "interval_s": [900, 900]}), pd.DataFrame({"sns_key": ["A"], "interval_s": [None]})):
        with pytest.raises(FrameError):
            grid.interval_hours(bad, context=M12)


def test_bucket_peak_uses_ok_samples_and_reports_count_hours_and_time():
    m = _m([("2025-01-01 00:00", 1.0, "ok"), ("2025-01-01 00:15", 9.0, "ok"), ("2025-01-01 00:30", 99.0, "suspect"), ("2025-01-01 00:45", 9.0, "ok"), ("2025-01-01 01:00", 5.0, "ok"),
            ("2025-01-01 01:15", np.nan, "missing"), ("2025-01-02 10:00", 2.0, "estimated"), ("2025-01-02 11:00", 3.0, "ok")])
    h = grid.bucket_peak(m, _s(), "hour", context=M12)
    assert h[["peak", "peak_ts", "ok_count", "ok_hours"]].values.tolist()[:2] == [[9.0, pd.Timestamp("2025-01-01 00:15"), 3, 0.75], [5.0, pd.Timestamp("2025-01-01 01:00"), 1, 0.25]], "ties take the first sample; the suspect 99 never counts"
    d = grid.bucket_peak(m, _s(), "day", context=M12)
    assert d.bucket.tolist() == [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-02")] and d.peak.tolist() == [9.0, 3.0] and d.ok_count.tolist() == [4, 1]
    w = grid.bucket_peak(m, _s(), "week", context=M12)
    assert w.bucket.tolist() == [pd.Timestamp("2024-12-30")] and w.peak.tolist() == [9.0] and w.ok_count.tolist() == [5], "weeks start on Monday"
    loc = grid.bucket_peak(_m([("2026-01-16 22:30", 1.0, "ok"), ("2026-01-16 23:00", 4.0, "ok")]), _s(), "day", tz="Europe/Copenhagen", context=M12)
    assert [str(b.date()) for b in loc.bucket] == ["2026-01-16", "2026-01-17"] and loc.peak.tolist() == [1.0, 4.0], "the local day starts at 23:00 UTC in winter"
    assert str(loc.bucket.dt.tz) == "Europe/Copenhagen"
    two = grid.bucket_peak(pd.concat([m, _m([("2025-01-01 00:00", 7.0, "ok")], key="S2")]), pd.concat([_s(), _s(sns_key=["S2"], interval_s=[3600])]), "day", context=M12)
    assert two[two.sns_key == "S2"].ok_hours.tolist() == [1.0], "hours use the interval of the sensor"
    assert grid.bucket_peak(m.assign(quality_flag="missing"), _s(), "day", context=M12).empty
    for kw, msg in ((dict(freq="month"), "freq must be"),):
        with pytest.raises(FrameError, match=msg):
            grid.bucket_peak(m, _s(), context=M12, **kw)
    with pytest.raises(FrameError, match="not in telemetry.sensor"):
        grid.bucket_peak(m.assign(sns_key="X"), _s(), context=M12)


def test_outdoor_at_is_the_last_observation_at_or_before():
    obs = pd.DataFrame({"station_key": ["W1", "W1", "W1", "W2"], "ts": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 02:00", "2026-01-01 00:00"]), "temp_c": [-1.0, -2.0, -3.0, 5.0]})
    ts = ["2025-12-31 23:59", "2026-01-01 00:00", "2026-01-01 01:59", "2026-01-01 02:00", "2026-01-05 00:00"]
    r = grid.outdoor_at(obs.sample(frac=1, random_state=1), ts, "W1", context=M12)
    assert r.iloc[0] != r.iloc[0] and r.tolist()[1:4] == [-1.0, -2.0, -3.0] and np.isnan(r.iloc[4]), "null before the first observation; no look ahead, no interpolation, no stale value after the last"
    assert grid.outdoor_at(obs, ts, "W1", max_age_hours=None, context=M12).tolist()[4] == -3.0, "the age limit can be switched off"
    assert grid.outdoor_at(obs, ["2026-01-01 02:30", "2026-01-01 03:30"], "W1", max_age_hours=1.0, context=M12).isna().tolist() == [False, True]
    idx = pd.Series(pd.to_datetime(["2026-01-01 00:30", "2026-01-01 01:30"]), index=[10, 11])
    assert grid.outdoor_at(obs, idx, "W1", context=M12).to_dict() == {10: -1.0, 11: -2.0}, "the result keeps the index of ts"
    assert grid.outdoor_at(obs, idx.iloc[[1, 0]], "W1", context=M12).to_dict() == {11: -2.0, 10: -1.0}, "unsorted timestamps keep their order"
    for bad in (-1.0, True, "1"):
        with pytest.raises(FrameError, match="max_age_hours"):
            grid.outdoor_at(obs, ts, "W1", max_age_hours=bad, context=M12)
    with pytest.raises(FrameError, match="null stations"):
        grid.outdoor_at(obs, ts[:2], ["W1", None], context=M12)
    with pytest.raises(FrameError, match="station_key must be"):
        grid.outdoor_at(obs, ts, 5, context=M12)
    mixed = grid.outdoor_at(obs, ["2026-01-01 00:30", "2026-01-01 00:30"], ["W1", "W2"], context=M12)
    assert mixed.tolist() == [-1.0, 5.0] and mixed.index.tolist() == [0, 1]
    for args, msg in ((("W9",), "not in telemetry.weather_observation"), ((["W1"],), "one station")):
        with pytest.raises(FrameError, match=msg):
            grid.outdoor_at(obs, ts, *args, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        grid.outdoor_at(pd.concat([obs, obs.iloc[:1]]), ts, "W1", context=M12)


def test_stage_and_registry():
    reg = registry.registered()
    for n in ("to_local", "interval_hours", "bucket_peak", "outdoor_at"):
        m = reg[f"halvaro.grid.series.{n}"]
        assert m.parameters[-1] == "context" and n in grid.__all__
    with pytest.raises(StageRefusal, match="telemetry"):
        grid.interval_hours(pd.DataFrame(), context=Context(stage="month3", role="r"))
