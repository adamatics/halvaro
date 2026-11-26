# outdoor_at

Module `halvaro.grid.series`. Import: `from halvaro.grid import outdoor_at`.

```python
outdoor_at(weather_observation: pd.DataFrame, ts: TimesLike, station_key: str | Sequence[str] | pd.Series | pd.Index | np.ndarray, *, max_age_hours: float | None = 1.5, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the outdoor temperature at given times from the last observation of a weather station.

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

## Source columns

- `telemetry.weather_observation.station_key`
- `telemetry.weather_observation.ts`
- `telemetry.weather_observation.temp_c`
- `telemetry.sensor.station_key`
