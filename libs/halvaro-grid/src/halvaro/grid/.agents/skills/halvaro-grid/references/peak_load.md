# peak_load

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import peak_load`.

```python
peak_load(zone_series: pd.DataFrame, sensor: pd.DataFrame, weather_observation: pd.DataFrame, supply: pd.DataFrame | None = None, *, min_completeness: float = 0.9, timezone: str = 'Europe/Copenhagen', max_age_hours: float = 1.5, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the peak load of each heat zone (its root) and each electric station, with its time, validity and the outdoor and supply temperature at the peak.

Per zone and sensor: the peak percent, its time in UTC and local, the completeness of the series, whether the peak is valid, the outdoor temperature at the peak and the supply temperature of the root at the peak. Over the time span of the series it also gives
the highest ok supply temperature of the root (supply_temp_max_c) and the lowest outdoor temperature of the station (outdoor_min_c): pass a series cut to a winter or a cold snap to read the maximum and minimum of that period.

Only ok samples count; the first sample at the maximum is the peak. valid is completeness (ok samples over all samples) at least min_completeness. outdoor_c is the last hourly observation of the sensor's weather station at or before the peak
(null when older than max_age_hours); supply_temp_c is the ok `supply_temp` sample of the root sensor of the zone in `supply` (a measurement frame) at that time, null without it.
PROPOSED: min_completeness 0.9 (policy.grid.min_peak_completeness is needed), max_age_hours 1.5 (the age limit of the outdoor observation, as halvaro.grid.series.outdoor_at), timezone Europe/Copenhagen (the offsets of Berlin are the same).

Args:
    zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
    sensor: The telemetry.sensor table, with the columns sns_key, zone_key, sensor_type, critical_role and station_key.
    weather_observation: The telemetry.weather_observation table, with the columns station_key, ts and temp_c.
    supply: Optional measurement frame (sns_key, ts, value, quality_flag) holding the root supply_temp samples; without it supply_temp_c and supply_temp_max_c are null. Default None.
    min_completeness: Least completeness for a valid peak, a number in [0, 1]; default 0.9 (PROPOSED).
    timezone: Time zone name of the local peak time; default Europe/Copenhagen (PROPOSED).
    max_age_hours: Oldest age in hours of the outdoor observation used for the peak, zero or more; default 1.5 (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with one row per zone and sensor, sorted by zone_key and sns_key, with the columns zone_key, sns_key, level, basis, peak_percent, peak_ts_utc, peak_ts_local, ok_samples, rows, completeness, valid, outdoor_c, supply_temp_c, supply_temp_max_c, outdoor_min_c (temperatures and percent rounded to 4 decimals).

Raises:
    FrameError: max_age_hours is not a number of zero or more; min_completeness is not a number in [0, 1]; zone_series, sensor or weather_observation lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; telemetry.sensor has more than one row for a sns_key; the weather ts is not readable; the supply frame is not a valid measurement frame or has more than one sample for a sensor and time.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import peak_load
    >>> ctx = Context(stage="month12", role="analyst")
    >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 2, "sns_key": ["SNS-900001"] * 2, "level": ["zone"] * 2, "basis": ["load_percent"] * 2,
    ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "quality_flag": ["ok", "ok"], "ok": [True, True], "load_percent": [80.0, 95.0]})
    >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "critical_role": ["root_pump"], "station_key": ["WST-900001"]})
    >>> weather = pd.DataFrame({"station_key": ["WST-900001"] * 2, "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "temp_c": [-3.0, -5.0]})
    >>> out = peak_load(series, sensor, weather, context=ctx)
    >>> out[["peak_percent", "completeness", "valid", "outdoor_c"]].to_dict("records")
    [{'peak_percent': 95.0, 'completeness': 1.0, 'valid': True, 'outdoor_c': -5.0}]

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
- `telemetry.sensor.station_key`
- `telemetry.weather_observation.station_key`
- `telemetry.weather_observation.ts`
- `telemetry.weather_observation.temp_c`
