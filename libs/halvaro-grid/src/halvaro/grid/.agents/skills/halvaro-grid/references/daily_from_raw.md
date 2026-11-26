# daily_from_raw

Module `halvaro.grid.quality`. Import: `from halvaro.grid import daily_from_raw`.

```python
daily_from_raw(measurement: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the daily min, max, avg, count and availability per sensor recomputed from the raw samples.

The result has the shape and dtypes of telemetry.measurement_daily. Only ok samples with a value enter the aggregates. A day exists when at least one slot is present (a row of any flag, so nothing before the install date);
the aggregates are null when no sample is ok; availability_pct is 100 times ok over the present slots to two decimals. The date is a Python date like the stored column.

Args:
    measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns sns_key, date (UTC), min, max, avg, count and availability_pct (float32, count int32), sorted by sns_key and date.

Raises:
    FrameError: a column of measurement is missing, ts holds numbers, unreadable text or a time zone, a row has no sns_key or ts, quality_flag is null or unknown, or a sensor has two rows for the same ts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import daily_from_raw
    >>> ctx = Context(stage="month12", role="analyst")
    >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
    ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
    >>> out = daily_from_raw(m, context=ctx)
    >>> out[["min", "max", "avg", "count", "availability_pct"]].to_dict("records")
    [{'min': 1.0, 'max': 4.0, 'avg': 2.5, 'count': 2, 'availability_pct': 50.0}]
    >>> str(out["date"].iloc[0])
    '2025-03-01'

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
