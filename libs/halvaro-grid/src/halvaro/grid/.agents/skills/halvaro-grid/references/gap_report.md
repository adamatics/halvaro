# gap_report

Module `halvaro.grid.quality`. Import: `from halvaro.grid import gap_report`.

```python
gap_report(measurement: pd.DataFrame, sensor: pd.DataFrame, events: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the runs of missing or estimated samples per sensor, never filled, with the data quality event that covers each run.

Consecutive means one interval_s apart; a slot that is not in the frame ends a run. event_type is the type of the event covering the first slot of the run, null when none does, and explained is true when every
slot of the run lies in a dropout event.

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    sensor: The telemetry.sensor frame, columns sns_key and interval_s, one row per sensor.
    events: The telemetry.data_quality_event frame, columns sns_key, from_ts, to_ts and type.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns sns_key, start, end (the last slot of the run), samples, missing, estimated, event_type and explained, sorted by sns_key and start; empty with these columns when there is no gap.

Raises:
    FrameError: a column of sensor, events or measurement is missing, the measurement is invalid (see valid_samples), interval_s is not positive for every sensor, telemetry.sensor repeats a sns_key,
        an event has a null sns_key, from_ts, to_ts or type, an unreadable or zoned time, or ends before it starts, or a measured sensor is not in telemetry.sensor.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import gap_report
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
    ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "estimated", "ok"]})
    >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [900]})
    >>> e = pd.DataFrame({"sns_key": ["SNS-900001"], "from_ts": ["2025-03-01 00:10"], "to_ts": ["2025-03-01 00:40"], "type": ["dropout"]})
    >>> out = gap_report(m, s, e, context=ctx)
    >>> out[["samples", "missing", "estimated", "event_type", "explained"]].to_dict("records")
    [{'samples': 2, 'missing': 1, 'estimated': 1, 'event_type': 'dropout', 'explained': True}]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.interval_s`
- `telemetry.data_quality_event.sns_key`
- `telemetry.data_quality_event.from_ts`
- `telemetry.data_quality_event.to_ts`
- `telemetry.data_quality_event.type`
- `telemetry.data_quality_event.samples`
