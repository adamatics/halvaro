# hours_above

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import hours_above`.

```python
hours_above(zone_series: pd.DataFrame, sensor: pd.DataFrame, bands: Sequence[float] = (90.0, 100.0, 105.0), *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the hours each zone or station spends above load bands such as 90, 100 and 105 percent, with the coverage of the series.

Hours above each band: ok samples strictly above the band times the interval of the sensor, with the coverage (ok over all samples).
PROPOSED: the bands 90, 100 and 105 percent (policy.grid.load_bands is needed).

Args:
    zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
    sensor: The telemetry.sensor table, with the columns sns_key and interval_s; it must hold every sensor of the series.
    bands: The load bands in percent; default (90.0, 100.0, 105.0) (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, sns_key, level, band, hours_above, ok_samples, rows, coverage, one row per zone, sensor, level and band.

Raises:
    FrameError: zone_series or sensor lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; bands is empty or holds something that is not a finite number; telemetry.sensor has more than one row for a sns_key or an interval_s that is not positive; a sensor of the series is not in telemetry.sensor.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import hours_above
    >>> ctx = Context(stage="month12", role="analyst")
    >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "sns_key": ["SNS-900001"] * 3, "level": ["zone"] * 3, "basis": ["load_percent"] * 3,
    ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00", "2026-01-10 02:00"], "quality_flag": ["ok"] * 3, "ok": [True] * 3, "load_percent": [85.0, 95.0, 101.0]})
    >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [3600]})
    >>> out = hours_above(series, sensor, bands=[90.0, 100.0], context=ctx)
    >>> out["hours_above"].tolist()
    [2.0, 1.0]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.interval_s`
