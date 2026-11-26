# classify_flags

Module `halvaro.grid.quality`. Import: `from halvaro.grid import classify_flags`.

```python
classify_flags(measurement: pd.DataFrame, events: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to know which data quality event explains each sample that is not ok.

event_type is dropout for missing and estimated samples and spike, flatline or drift for suspect ones; it is null for ok samples and for a flagged sample that no event covers. Where several events of the family
cover a sample the type of the earliest listed one wins (spike, flatline, drift order).

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    events: The telemetry.data_quality_event frame, columns sns_key, from_ts, to_ts and type.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The measurements, sorted by sns_key and ts with a fresh index, with the extra column event_type.

Raises:
    FrameError: a column of measurement or events is missing, the measurement is invalid (see valid_samples), or an event has a null sns_key, from_ts, to_ts or type, an unreadable or zoned time, or ends before it starts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import classify_flags
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30"]),
    ...                   "value": [1.0, 2.0, None], "quality_flag": ["ok", "suspect", "missing"]})
    >>> e = pd.DataFrame({"sns_key": ["SNS-900001"], "from_ts": ["2025-03-01 00:10"], "to_ts": ["2025-03-01 00:20"], "type": ["spike"]})
    >>> classify_flags(m, e, context=ctx)["event_type"].fillna("none").tolist()
    ['none', 'spike', 'none']

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.data_quality_event.sns_key`
- `telemetry.data_quality_event.from_ts`
- `telemetry.data_quality_event.to_ts`
- `telemetry.data_quality_event.type`
