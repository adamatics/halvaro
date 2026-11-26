"""Time series helpers of the telemetry: local time, sample interval, peaks per bucket and the outdoor temperature at a time."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import _checked_measurement, _need, _utc
from ._types import TimesLike

_TIMEZONES = {"DK": "Europe/Copenhagen", "DE": "Europe/Berlin"}      # PROPOSED: cfg:telemetry.yaml#timezones has no fact id
_FREQ = {"hour": "h", "day": "D", "week": "W-MON"}


@staged(sources=("telemetry.measurement.ts", "gis.supply_zone.country"), oracle="py:tests/test_oracle_series.py::test_oracle_to_local_two_years_hour_by_hour_against_zoneinfo")
def to_local(ts: TimesLike, country: str, *, timezones: Mapping[str, str] = _TIMEZONES) -> pd.Series[Any]:
    """Use this when you need stored UTC timestamps as local time of the country of a zone.

    UTC timestamps (naive, as stored) as time zone aware local time of the country of the zone (DK Europe/Copenhagen, DE Europe/Berlin).
    PROPOSED: the zone names are the config values cfg:telemetry.yaml#timezones.DK and .DE; a fact id is needed.

    Args:
        ts: The UTC timestamps as stored (telemetry.measurement.ts), without a time zone.
        country: The country of the zone (gis.supply_zone.country), a key of `timezones`.
        timezones: The mapping from country to time zone name; defaults to DK Europe/Copenhagen and DE Europe/Berlin (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series of time zone aware local timestamps, in the order of ts.

    Raises:
        FrameError: the country is not a string or has no time zone in `timezones`; a timestamp cannot be read, holds numbers or has a time zone; the time zone name is not known.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> from halvaro.core import Context
        >>> from halvaro.grid import to_local
        >>> ctx = Context(stage="month12", role="analyst")
        >>> to_local(["2020-01-15 12:00", "2020-07-15 12:00"], "DK", context=ctx).dt.hour.tolist()
        [13, 14]
"""
    if not isinstance(country, str) or country not in timezones:
        raise FrameError(f"no time zone for the country {country!r}; known: {sorted(timezones)}")
    s = _utc(ts, "ts")
    return cast("pd.Series[Any]", s.dt.tz_localize("UTC").dt.tz_convert(_zone(timezones[country])))


@staged(sources=("telemetry.sensor.sns_key", "telemetry.sensor.interval_s"), oracle="py:tests/test_telemetry.py::test_values_look_physical")
def interval_hours(sensor: pd.DataFrame) -> pd.Series:
    """Use this when you need the sampling interval of each sensor in hours, to turn a count of samples into hours.

    The sampling interval of each sensor in hours (900 s is 0.25, 3,600 s is 1.0), indexed by sns_key. Hours above a limit are samples times this, never a fixed 0.25.

    Args:
        sensor: The telemetry.sensor table; it needs the columns sns_key and interval_s.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series named interval_hours, indexed by sns_key, in the order of the sensor rows.

    Raises:
        FrameError: a needed column is missing; telemetry.sensor has more than one row for a sns_key; interval_s is not positive for every sensor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import interval_hours
        >>> ctx = Context(stage="month12", role="analyst")
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001", "SNS-900002"], "interval_s": [900, 3600]})
        >>> interval_hours(s, context=ctx).to_dict()
        {'SNS-900001': 0.25, 'SNS-900002': 1.0}
"""
    _need(sensor, ["sns_key", "interval_s"], "telemetry.sensor")
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    iv = pd.to_numeric(sensor["interval_s"], errors="coerce")
    if not (iv > 0).all():
        raise FrameError("telemetry.sensor.interval_s must be positive for every sensor")
    return pd.Series((iv / 3600.0).to_numpy(), index=pd.Index(sensor["sns_key"].to_numpy(), name="sns_key"), name="interval_hours")


def _zone(name: str) -> str:
    try:
        pd.Timestamp("2025-01-01", tz=name)
    except Exception as e:                                                       # pytz and zoneinfo raise their own unknown zone errors
        raise FrameError(f"{name!r} is not a time zone name: {e}") from None
    return name


def _bucket(ts: pd.Series, freq: str, tz: str | None) -> pd.Series:
    """Start of the hour, day or Monday week of each UTC timestamp, naive UTC or (with tz) local and time zone aware."""
    t = ts.dt.tz_localize("UTC")
    if tz:
        t = t.dt.tz_convert(_zone(tz))
    if freq == "hour":
        b = t.dt.tz_convert("UTC").dt.floor("h").dt.tz_convert(tz) if tz else t.dt.floor("h")             # floor in UTC: the repeated hour of the autumn change is two buckets
    else:
        naive = t.dt.tz_localize(None)
        day = naive.dt.normalize()
        if freq == "week":
            day = day - pd.to_timedelta(naive.dt.dayofweek, unit="D")
        b = day.dt.tz_localize(tz, ambiguous=True, nonexistent="shift_forward") if tz else day
    return cast("pd.Series[Any]", b.dt.tz_localize(None) if (not tz and freq == "hour") else b)


@staged(sources=("telemetry.measurement.sns_key", "telemetry.measurement.ts", "telemetry.measurement.value", "telemetry.measurement.quality_flag", "telemetry.sensor.sns_key", "telemetry.sensor.interval_s"),
        oracle="py:tests/test_telemetry.py::test_truth_keys")
def bucket_peak(measurement: pd.DataFrame, sensor: pd.DataFrame, freq: str = "day", *, tz: str | None = None) -> pd.DataFrame:
    """Use this when you need the maximum of the ok samples of each sensor per hour, day or week, with the number of ok samples and their hours.

    Maximum of the ok samples per sensor and hour, day or week (weeks start on Monday), with the number of ok samples, their hours and the time of the first sample at the maximum.
    Buckets are UTC unless tz names a time zone (then the bucket start is local time). A bucket
    without an ok sample is not listed; estimated, suspect and missing samples never count (a suspect spike would be the peak).

    Args:
        measurement: The telemetry.measurement table; it needs the columns sns_key, ts, value and quality_flag.
        sensor: The telemetry.sensor table; it needs the columns sns_key and interval_s.
        freq: The bucket size: hour, day (default) or week.
        tz: The name of a time zone for local buckets, or None for UTC buckets.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by sns_key and bucket with the columns sns_key, bucket, peak, peak_ts (UTC), ok_count, ok_hours (ok_count times interval_hours). It is empty when there is no ok sample.

    Raises:
        FrameError: tz is not a time zone name or None; freq is not hour, day or week; a needed column is missing; a timestamp cannot be read; a flag is not one of ok, estimated, suspect, missing; a sensor has two samples at one timestamp; interval_s is not positive; a sensor of the measurements is not in telemetry.sensor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import bucket_peak
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": ["SNS-900001"] * 3, "ts": ["2020-03-02 00:00", "2020-03-02 00:15", "2020-03-02 00:30"],
        ...                   "value": [10.0, 30.0, 99.0], "quality_flag": ["ok", "ok", "suspect"]})
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [900]})
        >>> bucket_peak(m, s, "day", context=ctx)[["peak", "ok_count", "ok_hours"]].to_dict("records")
        [{'peak': 30.0, 'ok_count': 2, 'ok_hours': 0.5}]
"""
    if tz is not None and (not isinstance(tz, str) or not tz):
        raise FrameError(f"tz must be a time zone name or None, not {tz!r}")
    if freq not in _FREQ:
        raise FrameError(f"freq must be one of {sorted(_FREQ)}, not {freq!r}")
    m = _checked_measurement(measurement)
    hours = unwrapped(interval_hours)(sensor)
    unknown = sorted(set(m["sns_key"]) - set(hours.index))
    if unknown:
        raise FrameError(f"{len(unknown)} sensors of the measurements are not in telemetry.sensor (for example {unknown[0]})")
    ok = m[(m["quality_flag"] == "ok") & m["value"].notna()]
    cols = ["sns_key", "bucket", "peak", "peak_ts", "ok_count", "ok_hours"]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    x = ok.assign(bucket=_bucket(ok["ts"], freq, tz))
    idx = x.groupby(["sns_key", "bucket"])["value"].idxmax()
    first = x.loc[idx.to_numpy(), ["sns_key", "bucket", "value", "ts"]].rename(columns={"value": "peak", "ts": "peak_ts"})
    cnt = x.groupby(["sns_key", "bucket"]).size().rename("ok_count").reset_index()
    out = first.merge(cnt, on=["sns_key", "bucket"])
    out["ok_hours"] = out["ok_count"] * out["sns_key"].map(hours)
    return out[cols].sort_values(["sns_key", "bucket"]).reset_index(drop=True)


@staged(sources=("telemetry.weather_observation.station_key", "telemetry.weather_observation.ts", "telemetry.weather_observation.temp_c", "telemetry.sensor.station_key"), oracle="py:repo_tests/test_oracle_series_release.py::test_oracle_outdoor_at_baseline_with_gaps_per_timestamp")
def outdoor_at(weather_observation: pd.DataFrame, ts: TimesLike, station_key: str | Sequence[str] | pd.Series | pd.Index | np.ndarray, *, max_age_hours: float | None = 1.5) -> pd.Series:
    """Use this when you need the outdoor temperature at given times from the last observation of a weather station.

    Outdoor temperature at each timestamp: the last observation of the station at or before it (hourly observations; no interpolation), null before the first observation and when the last
    observation is older than max_age_hours (PROPOSED 1.5, so a gap in the observations or a time after the last observation is null, not a stale value; None switches the limit off).

    Args:
        weather_observation: The telemetry.weather_observation table; it needs the columns station_key, ts and temp_c.
        ts: The timestamps to look up (UTC, without a time zone); a list or a Series.
        station_key: One station for all timestamps or a sequence of the same length (the station of each sensor, telemetry.sensor.station_key).
        max_age_hours: The oldest an observation may be, in hours, PROPOSED 1.5; zero or more, or None for no limit.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series named temp_c with one value per timestamp, in order; it has the index of `ts` when it is a Series.

    Raises:
        FrameError: a needed column is missing; max_age_hours is not zero or more or None; station_key is not a station key or a sequence; station_key has another length than ts or has null stations; a station is not in the observations; the observations have more than one row for a station and time; a timestamp cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import outdoor_at
        >>> ctx = Context(stage="month12", role="analyst")
        >>> w = pd.DataFrame({"station_key": ["STN-900001"] * 2, "ts": ["2020-03-02 00:00", "2020-03-02 01:00"], "temp_c": [1.5, 2.5]})
        >>> outdoor_at(w, ["2020-03-02 01:20", "2020-03-02 05:00"], "STN-900001", context=ctx).tolist()
        [2.5, nan]
"""
    _need(weather_observation, ["station_key", "ts", "temp_c"], "telemetry.weather_observation")
    if max_age_hours is not None and (not isinstance(max_age_hours, (int, float, np.number)) or isinstance(max_age_hours, bool) or not max_age_hours >= 0):
        raise FrameError(f"max_age_hours must be zero or more or None, not {max_age_hours!r}")
    index = ts.index if isinstance(ts, pd.Series) else None
    t = _utc(ts, "ts").reset_index(drop=True)
    if not isinstance(station_key, (str, list, tuple, pd.Series, np.ndarray, pd.Index)):
        raise FrameError(f"station_key must be a station key or one per timestamp, not {type(station_key).__name__}")
    st = pd.Series([station_key] * len(t) if isinstance(station_key, str) else list(station_key), dtype=object)
    if len(st) != len(t):
        raise FrameError(f"station_key must be one station or one per timestamp (got {len(st)} stations for {len(t)} timestamps)")
    obs = weather_observation.assign(ts=_utc(weather_observation["ts"], "telemetry.weather_observation.ts").to_numpy())
    if st.isna().any():
        raise FrameError(f"station_key has null stations ({int(st.isna().sum())} of {len(st)})")
    missing = sorted(set(st) - set(obs["station_key"]))
    if missing:
        raise FrameError(f"station {missing[0]} is not in telemetry.weather_observation")
    if obs.duplicated(["station_key", "ts"]).any():
        raise FrameError("telemetry.weather_observation has more than one row for a station and time")
    left = pd.DataFrame({"ts": t, "station_key": st, "pos": np.arange(len(t))}).sort_values("ts")
    right = obs.assign(station_key=obs["station_key"].astype(object), obs_ts=obs["ts"])[["station_key", "ts", "obs_ts", "temp_c"]].sort_values("ts")
    got = pd.merge_asof(left, right, on="ts", by="station_key", direction="backward").sort_values("pos")
    temp = got["temp_c"].to_numpy(dtype=float)
    if max_age_hours is not None:
        stale = ((got["ts"] - got["obs_ts"]) > pd.Timedelta(hours=float(max_age_hours))).to_numpy()
        temp = np.where(stale, np.nan, temp)
    return pd.Series(temp, index=index, name="temp_c")
