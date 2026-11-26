# interval_hours

Module `halvaro.grid.series`. Import: `from halvaro.grid import interval_hours`.

```python
interval_hours(sensor: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the sampling interval of each sensor in hours, to turn a count of samples into hours.

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

## Source columns

- `telemetry.sensor.sns_key`
- `telemetry.sensor.interval_s`
