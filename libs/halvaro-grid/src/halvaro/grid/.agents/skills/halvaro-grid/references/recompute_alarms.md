# recompute_alarms

Module `halvaro.grid.alarms`. Import: `from halvaro.grid import recompute_alarms`.

```python
recompute_alarms(measurement: pd.DataFrame, sensor: pd.DataFrame, *, alarm_names: Mapping[tuple[str, str], str] = {('load_percent', 'high'): 'load_high', ('breaker_state', 'low'): 'breaker_open'}, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the alarms recomputed from the ok samples and the limit columns of each sensor, in the shape of telemetry.alarm.

Only ok samples with a value count. A sensor with a limit needs alarm_min_duration_s and alarm_merge_gap_s; a sensor without rows in the frame has no alarm. Consecutive means one interval_s apart: a slot that is not
in the frame ends a run. A series that ends inside an alarm has a null cleared_ts. The limits are columns of the sensor table, never the alarm_rule table.
PROPOSED: alarm_names, the names of the types that are not '<sensor_type>_<direction>'.

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    sensor: The telemetry.sensor frame, columns sns_key, net_key, zone_key, sensor_type, interval_s, limit_high, limit_low, limit_high_crit, limit_low_crit, alarm_min_duration_s and alarm_merge_gap_s.
    alarm_names: PROPOSED mapping (sensor_type, direction) to alarm type name, for the types that are not '<sensor_type>_<direction>'; the default names load_high and breaker_open.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns sns_key, raised_ts (first violating sample), cleared_ts (end of the last violating sample, its time plus the interval; null when the series ends inside the alarm), severity (critical when the extreme value
    reaches the critical limit, else warning), alarm_type, net_key, zone_key, peak_value, limit_value and samples (violating samples), sorted by sns_key, raised_ts and alarm_type.

Raises:
    FrameError: a column of sensor or measurement is missing, the measurement is invalid (see valid_samples), telemetry.sensor repeats a sns_key, a measured sensor is not in telemetry.sensor,
        a sensor with a limit has an interval_s that is not a whole number of seconds above 0, or has no alarm_min_duration_s or alarm_merge_gap_s.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import recompute_alarms
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45", "2025-03-01 01:00"]),
    ...                   "value": [50.0, 95.0, 96.0, 50.0, 50.0], "quality_flag": "ok"})
    >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "net_key": ["NET-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "interval_s": [900],
    ...                   "limit_high": [90.0], "limit_low": [None], "limit_high_crit": [100.0], "limit_low_crit": [None], "alarm_min_duration_s": [900], "alarm_merge_gap_s": [900]})
    >>> out = recompute_alarms(m, s, context=ctx)
    >>> out[["alarm_type", "severity", "peak_value", "limit_value", "samples"]].to_dict("records")
    [{'alarm_type': 'load_high', 'severity': 'warning', 'peak_value': 96.0, 'limit_value': 90.0, 'samples': 2}]
    >>> out["cleared_ts"].dt.strftime("%H:%M").tolist()
    ['00:45']

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.net_key`
- `telemetry.sensor.zone_key`
- `telemetry.sensor.sensor_type`
- `telemetry.sensor.interval_s`
- `telemetry.sensor.limit_high`
- `telemetry.sensor.limit_low`
- `telemetry.sensor.limit_high_crit`
- `telemetry.sensor.limit_low_crit`
- `telemetry.sensor.alarm_min_duration_s`
- `telemetry.sensor.alarm_merge_gap_s`
