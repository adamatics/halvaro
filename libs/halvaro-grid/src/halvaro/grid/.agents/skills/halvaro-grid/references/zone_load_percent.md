# zone_load_percent

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import zone_load_percent`.

```python
zone_load_percent(measurement: pd.DataFrame, sensor: pd.DataFrame, *, basis: str = 'load_percent', context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the load in percent of the design per heat zone (its root pump) and per electric station, with the quality flag of every sample.

basis load_percent takes the root `load_percent` sensor, heat_power takes the root `heat_power` sensor in MW over `rated_value` times 100. Electric stations (zones without a root pump) are listed per sensor with level 'station' and basis 'station':
they have no zone value (T9). A sensor frame without the root rows would turn the heat sensors of that zone into stations, so pass the full sensor table. The heat_power basis is a weaker oracle than the root load_percent:
peaks and hours above 100 percent can differ from the root load_percent basis, and the peak time can shift.

Args:
    measurement: The telemetry.measurement table, with the columns sns_key, ts, value and quality_flag.
    sensor: The full telemetry.sensor table, with the columns sns_key, zone_key, sensor_type, interval_s, critical_role and rated_value.
    basis: load_percent (default) or heat_power, the root sensor type the zone value is read from.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok, load_percent (null unless ok), sorted by zone_key, sns_key and ts.

Raises:
    FrameError: basis is not load_percent or heat_power; the sensor or measurement frame lacks a column or is not a DataFrame; an interval_s is not a positive number; the measurement has a timestamp that is not readable or has a time zone, a null sns_key or ts, an unknown or null quality_flag, or more than one row for a sensor and timestamp; a heat zone has more than one root sensor of the basis; with heat_power a root sensor has no positive rated_value.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import zone_load_percent
    >>> ctx = Context(stage="month12", role="analyst")
    >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "interval_s": [3600],
    ...                        "critical_role": ["root_pump"], "rated_value": [100.0]})
    >>> m = pd.DataFrame({"sns_key": ["SNS-900001"] * 2, "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "value": [80.0, 95.0], "quality_flag": ["ok", "suspect"]})
    >>> out = zone_load_percent(m, sensor, context=ctx)
    >>> out["level"].tolist()
    ['zone', 'zone']
    >>> out["load_percent"].tolist()
    [80.0, nan]

## Source columns

- `telemetry.measurement.sns_key`
- `telemetry.measurement.ts`
- `telemetry.measurement.value`
- `telemetry.measurement.quality_flag`
- `telemetry.sensor.sns_key`
- `telemetry.sensor.zone_key`
- `telemetry.sensor.sensor_type`
- `telemetry.sensor.interval_s`
- `telemetry.sensor.critical_role`
- `telemetry.sensor.rated_value`
