# alarm_rules_table

Module `halvaro.grid.alarms`. Import: `from halvaro.grid import alarm_rules_table`.

```python
alarm_rules_table(sensor: pd.DataFrame, *, alarm_names: Mapping[tuple[str, str], str] = {('load_percent', 'high'): 'load_high', ('breaker_state', 'low'): 'breaker_open'}, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need one row per alarm type derived from the limit columns of the sensors, in the shape of telemetry.alarm_rule.

The description text of telemetry.alarm_rule is not produced. min_duration_s is the minimum over the sensors of the type and merge_gap_s the maximum; the limits come from the sensor table, never the alarm_rule table.
PROPOSED: alarm_names, the names of the types that are not '<sensor_type>_<direction>'.

Args:
    sensor: The telemetry.sensor frame, columns sns_key, net_key, zone_key, sensor_type, interval_s, limit_high, limit_low, limit_high_crit, limit_low_crit, alarm_min_duration_s and alarm_merge_gap_s.
    alarm_names: PROPOSED mapping (sensor_type, direction) to alarm type name, for the types that are not '<sensor_type>_<direction>'; the default names load_high and breaker_open.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns rule_no (1 upward, by alarm type), alarm_type, sensor_type, direction, n_sensors, limit_min, limit_max, critical_limit_min, critical_limit_max, min_duration_s and merge_gap_s, sorted by alarm_type.

Raises:
    FrameError: a column of sensor is missing, telemetry.sensor repeats a sns_key, or a sensor with a limit has no alarm_min_duration_s or alarm_merge_gap_s.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import alarm_rules_table
    >>> ctx = Context(stage="month12", role="analyst")
    >>> s = pd.DataFrame({"sns_key": ["SNS-900001", "SNS-900002"], "net_key": ["NET-900001", "NET-900002"], "zone_key": ["ZONE-0001", "ZONE-0002"], "sensor_type": "load_percent",
    ...                   "interval_s": [900, 900], "limit_high": [90.0, 80.0], "limit_low": [None, None], "limit_high_crit": [100.0, 95.0], "limit_low_crit": [None, None],
    ...                   "alarm_min_duration_s": [900, 1800], "alarm_merge_gap_s": [900, 3600]})
    >>> out = alarm_rules_table(s, context=ctx)
    >>> out[["rule_no", "alarm_type", "direction", "n_sensors", "limit_min", "limit_max", "min_duration_s", "merge_gap_s"]].to_dict("records")
    [{'rule_no': 1, 'alarm_type': 'load_high', 'direction': 'high', 'n_sensors': 2, 'limit_min': 80.0, 'limit_max': 90.0, 'min_duration_s': 900, 'merge_gap_s': 3600}]

## Source columns

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
