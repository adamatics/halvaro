# completeness

Module `halvaro.grid.quality`. Import: `from halvaro.grid import completeness`.

```python
completeness(measurement: pd.DataFrame, sensor: pd.DataFrame, window_start: DateLike, window_end: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the share of expected slots that hold an ok sample per sensor over a window of days.

The window runs over the days window_start to window_end inclusive (UTC). Expected slots run from the later of the window start and the install date (midnight) to the end of the last day, one per interval_s.
A sensor without rows is listed with zeros. A sensor whose first sample comes hours after the midnight of its install date has expected slots without rows, which `share` counts as lost and `share_of_present`
does not. The minimum share for a peak (policy.grid.min_peak_completeness) is not applied here.

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    sensor: The telemetry.sensor frame, columns sns_key, install_date and interval_s, one row per sensor.
    window_start: First day of the window (a date or date text, UTC).
    window_end: Last day of the window, inclusive.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns sns_key, expected, rows, ok, estimated, suspect, missing, share (ok over expected) and share_of_present (ok over the rows that exist), sorted by sns_key.
    share and share_of_present are null where there are no expected slots or no rows.

Raises:
    FrameError: a column of sensor or measurement is missing, the measurement is invalid (see valid_samples), window_start or window_end is not a date, the window ends before it starts, telemetry.sensor repeats a sns_key,
        has a missing or not positive interval_s or an empty install_date, a measured sensor is not in telemetry.sensor, or a sensor has more rows in the window than slots after its install date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import completeness
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
    ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
    >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "install_date": ["2025-03-01"], "interval_s": [900]})
    >>> out = completeness(m, s, "2025-03-01", "2025-03-01", context=ctx)
    >>> out[["sns_key", "expected", "rows", "ok"]].to_dict("records")
    [{'sns_key': 'SNS-900001', 'expected': 96, 'rows': 4, 'ok': 2}]
    >>> out["share"].tolist()
    [0.020833]
    >>> out["share_of_present"].tolist()
    [0.5]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.install_date`
- `telemetry.sensor.interval_s`
