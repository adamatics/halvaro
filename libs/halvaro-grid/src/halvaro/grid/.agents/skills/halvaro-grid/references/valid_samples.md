# valid_samples

Module `halvaro.grid.quality`. Import: `from halvaro.grid import valid_samples`.

```python
valid_samples(measurement: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need only the samples that count, those flagged ok with a value, sorted by sensor and time.

Estimated, suspect and missing samples are dropped, never filled or zeroed. An unknown flag, a duplicated slot or a time zone raises FrameError.

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns of the input, only the ok samples with a value, sorted by sns_key and ts, with a fresh index.

Raises:
    FrameError: a column of measurement is missing, ts holds numbers, unreadable text or a time zone, a row has no sns_key or ts, quality_flag is null or not one of the known flags, or a sensor has two rows for the same ts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import valid_samples
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
    ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
    >>> valid_samples(m, context=ctx)["value"].tolist()
    [1.0, 4.0]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
