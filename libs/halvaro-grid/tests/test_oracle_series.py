"""Oracles of to_local and outdoor_at: the expected local times come from the standard library (zoneinfo, one timestamp at a time) and from hand worked clock times; the expected temperatures come from a sorted search per timestamp."""
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")

COPENHAGEN, BERLIN = "Europe/Copenhagen", "Europe/Berlin"


def _stdlib_local(utc_values, zone):
    """One timestamp at a time: the UTC clock reading as local wall time and offset by zoneinfo."""
    zi = ZoneInfo(zone)
    out = []
    for v in utc_values:
        t = pd.Timestamp(v)
        if pd.isna(t):
            out.append(None)
            continue
        local = dt.datetime(t.year, t.month, t.day, t.hour, t.minute, t.second, tzinfo=dt.timezone.utc).astimezone(zi)
        out.append(local.strftime("%Y-%m-%d %H:%M:%S %z"))
    return out


def _as_text(series):
    return [None if pd.isna(v) else v.strftime("%Y-%m-%d %H:%M:%S %z") for v in series]


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# to_local
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def test_oracle_to_local_hand_worked_clock_times_and_switch_days():
    """route: hand worked clock times (winter plus one hour, summer plus two, the last Sundays of March and October 2026 at 01:00 UTC), each local time and offset written down."""
    utc = ["2026-01-15 12:00", "2026-07-01 12:00", "2026-03-29 00:59", "2026-03-29 01:00", "2026-10-25 00:59", "2026-10-25 01:00", "2026-10-25 01:30", "2026-12-31 23:00", "2026-06-30 22:30", None]
    t = pd.Series(pd.to_datetime(utc), index=list("abcdefghij"))
    t0 = t.copy()
    want = ["2026-01-15 13:00:00 +0100", "2026-07-01 14:00:00 +0200", "2026-03-29 01:59:00 +0100", "2026-03-29 03:00:00 +0200", "2026-10-25 02:59:00 +0200", "2026-10-25 02:00:00 +0100",
            "2026-10-25 02:30:00 +0100", "2027-01-01 00:00:00 +0100", "2026-07-01 00:30:00 +0200", None]
    for country, zone in (("DK", COPENHAGEN), ("DE", BERLIN)):
        r = grid.to_local(t, country, context=M12)
        assert _as_text(r) == want, f"{country}: the spring change at 01:00 UTC jumps from 01:59 to 03:00, the autumn change repeats the 02:00 hour"
        assert str(r.dt.tz) == zone and r.index.tolist() == list("abcdefghij") and r.dt.tz is not None, f"{country}: time zone {zone}, the index of the input"
        back = r.dt.tz_convert("UTC").dt.tz_localize(None)
        assert back.equals(t), f"{country}: converting back to UTC returns the input"
    pd.testing.assert_series_equal(t, t0)
    assert _as_text(grid.to_local(list(t[:3]), "DK", context=M12)) == want[:3], "a list is read as UTC timestamps too"
    with pytest.raises(FrameError, match="FR"):
        grid.to_local(t, "FR", context=M12)


def test_oracle_to_local_two_years_hour_by_hour_against_zoneinfo():
    """route: every hour of 2025 and 2026 and the quarter hours around the four switches, converted one by one with zoneinfo and compared with the vector result for DK and DE."""
    test_oracle_to_local_hand_worked_clock_times_and_switch_days()                              # the switch days with the local times written down
    hours = pd.date_range("2025-01-01 00:00", "2026-12-31 23:00", freq="h")
    switches = ["2025-03-30 01:00", "2025-10-26 01:00", "2026-03-29 01:00", "2026-10-25 01:00"]
    near = [pd.Timestamp(s) + pd.Timedelta(minutes=m) for s in switches for m in (-45, -30, -15, -1, 0, 1, 15, 30, 45)]
    t = pd.Series(list(hours) + near)
    for country, zone in (("DK", COPENHAGEN), ("DE", BERLIN)):
        got = _as_text(grid.to_local(t, country, context=M12))
        want = _stdlib_local(t, zone)
        bad = [(str(a), g, w) for a, g, w in zip(t, got, want) if g != w]
        assert not bad, f"{country} ({zone}): {len(bad)} timestamps differ, the first is {bad[:1]}"
    offsets = {x[-5:] for x in _stdlib_local(t, COPENHAGEN)}
    assert offsets == {"+0100", "+0200"}, "winter and summer time both occur in the two years"



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# outdoor_at
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _obs(rows):
    return pd.DataFrame(rows, columns=["station_key", "ts", "temp_c"]).assign(ts=lambda d: pd.to_datetime(d["ts"]))



def test_oracle_outdoor_at_hand_worked_age_limit():
    """route: a hand worked example, hourly observations of two stations with a gap from 03:00 to 05:00 at W1, and the answer for each query time written down, including exactly 90 minutes after an observation."""
    obs = _obs([("W1", "2026-01-01 00:00", -1.0), ("W1", "2026-01-01 01:00", -2.0), ("W1", "2026-01-01 02:00", -3.0), ("W1", "2026-01-01 05:00", -5.0),
                ("W2", "2026-01-01 00:00", 5.0), ("W2", "2026-01-01 03:00", 7.0)])
    obs0 = obs.copy()
    q = ["2025-12-31 23:59:00", "2026-01-01 00:00:00", "2026-01-01 00:59:59", "2026-01-01 01:00:00", "2026-01-01 02:00:00", "2026-01-01 03:30:00", "2026-01-01 03:30:01", "2026-01-01 04:59:00",
         "2026-01-01 05:00:00", "2026-01-01 06:30:00", "2026-01-01 06:31:00"]
    nan = np.nan
    got = grid.outdoor_at(obs.sample(frac=1, random_state=3), q, "W1", context=M12)
    np.testing.assert_array_equal(got.to_numpy(), np.array([nan, -1.0, -1.0, -2.0, -3.0, -3.0, nan, nan, -5.0, -5.0, nan]),
                                  err_msg="limit 1.5 h: nothing before the first observation, no look ahead, exactly 90 minutes old is still valid, one second more is not")
    assert got.name == "temp_c" and got.index.tolist() == list(range(len(q)))
    none = grid.outdoor_at(obs, q, "W1", max_age_hours=None, context=M12)
    np.testing.assert_array_equal(none.to_numpy(), np.array([nan, -1.0, -1.0, -2.0, -3.0, -3.0, -3.0, -3.0, -5.0, -5.0, -5.0]), err_msg="no limit: the last observation however old")
    three = grid.outdoor_at(obs, q, "W1", max_age_hours=3.0, context=M12)
    np.testing.assert_array_equal(three.to_numpy(), np.array([nan, -1.0, -1.0, -2.0, -3.0, -3.0, -3.0, -3.0, -5.0, -5.0, -5.0]), err_msg="limit 3 h: 04:59 is two hours 59 minutes after 02:00")
    zero = grid.outdoor_at(obs, ["2026-01-01 01:00:00", "2026-01-01 01:00:01"], "W1", max_age_hours=0, context=M12)
    np.testing.assert_array_equal(zero.to_numpy(), np.array([-2.0, nan]), err_msg="limit 0: only the time of an observation itself")
    two = grid.outdoor_at(obs, ["2026-01-01 03:00:00", "2026-01-01 02:59:00", "2026-01-01 03:00:00", "2026-01-01 04:30:00", "2026-01-01 04:31:00"], ["W2", "W2", "W1", "W2", "W2"], context=M12)
    np.testing.assert_array_equal(two.to_numpy(), np.array([7.0, nan, -3.0, 7.0, nan]), err_msg="the station of each timestamp: W2 at 02:59 has only its 00:00 value, 2 h 59 old, and not the 02:00 value of W1; 04:30 is exactly 90 minutes after 03:00")
    pd.testing.assert_frame_equal(obs, obs0)
    idx = pd.Series(pd.to_datetime(["2026-01-01 01:30", "2026-01-01 00:30"]), index=["late", "early"])
    keep = grid.outdoor_at(obs, idx, "W1", context=M12)
    assert keep.to_dict() == {"late": -2.0, "early": -1.0}, "the answer follows the order and the index of the timestamps"
