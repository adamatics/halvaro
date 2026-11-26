# load_duration_curve

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import load_duration_curve`.

```python
load_duration_curve(zone_series: pd.DataFrame, sensor: pd.DataFrame, *, winter_only: bool = False, by_winter: bool = False, months: Sequence[int] = (11, 12, 1, 2, 3), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the load duration curve of each zone or station: the ok load, highest first, against the hours it is reached or exceeded.

Rank k has hours k times the interval of the sensor. With winter_only only the samples of the winter months count. Ties keep their time order. With by_winter one curve per winter (a winter column, the months of the winter only).
The hours count ok samples, so a gap in the series shortens the curve (the coverage is in hours_above).

Args:
    zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
    sensor: The telemetry.sensor table, with the columns sns_key and interval_s; it must hold every sensor of the series.
    winter_only: Count only the samples of the winter months; default False.
    by_winter: Give one curve per winter with a winter column (this also keeps only the winter months); default False.
    months: The month numbers 1 to 12 that count as winter; default (11, 12, 1, 2, 3) (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, sns_key, [winter,] rank, hours, load_percent, sorted by zone_key and sns_key (and winter) with the highest load first; empty when no sample is ok.

Raises:
    FrameError: zone_series or sensor lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; telemetry.sensor has more than one row for a sns_key or an interval_s that is not positive; a sensor of the series is not in telemetry.sensor.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import load_duration_curve
    >>> ctx = Context(stage="month12", role="analyst")
    >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "sns_key": ["SNS-900001"] * 3, "level": ["zone"] * 3, "basis": ["load_percent"] * 3,
    ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00", "2026-01-10 02:00"], "quality_flag": ["ok"] * 3, "ok": [True] * 3, "load_percent": [85.0, 95.0, 90.0]})
    >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [3600]})
    >>> out = load_duration_curve(series, sensor, context=ctx)
    >>> out["load_percent"].tolist()
    [95.0, 90.0, 85.0]
    >>> out["hours"].tolist()
    [1.0, 2.0, 3.0]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.interval_s`
