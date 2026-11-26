# bucket_peak

Module `halvaro.grid.series`. Import: `from halvaro.grid import bucket_peak`.

```python
bucket_peak(measurement: pd.DataFrame, sensor: pd.DataFrame, freq: str = 'day', *, tz: str | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the maximum of the ok samples of each sensor per hour, day or week, with the number of ok samples and their hours.

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

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.interval_s`
