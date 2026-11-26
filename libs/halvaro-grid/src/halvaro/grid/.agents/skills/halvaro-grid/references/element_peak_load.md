# element_peak_load

Module `halvaro.grid.assets`. Import: `from halvaro.grid import element_peak_load`.

```python
element_peak_load(sensor: pd.DataFrame, measurement_daily: pd.DataFrame, *, window: Window | None = None, min_completeness: float = 0.9, sensor_type: str = 'load_percent', context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the peak load in percent of each element that has its own load sensor, with the completeness that says whether the peak can be trusted.

Peak load in percent for each element with its own load sensor (`sensor_type`, default load_percent: sensors whose value is already a percent of their rated value), from the daily
maxima of the ok samples; elements without such a sensor are not listed (null in a join). Other sensor types (kW, A, kV, m3/h) are in their own units and are not converted.

Args:
    sensor: The telemetry.sensor table; it needs the columns sns_key, net_key, rated_value, install_date and sensor_type.
    measurement_daily: The telemetry.measurement_daily table; it needs the columns sns_key, date, max and availability_pct.
    window: An optional (first, last) pair of days that limits the daily rows; the first day must not be after the last. Without it the window runs from the first to the last day of the rows passed in, and a day without a row counts as zero availability, so completeness depends on the rows passed: pass the window when the share matters.
    min_completeness: The share from 0 to 1 of the days with data that makes a peak valid, PROPOSED 0.9, policy.grid.min_peak_completeness.
    sensor_type: The sensor type that is used, default load_percent.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per net_key, sorted by net_key, with the columns net_key, sns_key, peak_percent (highest daily maximum of the ok samples as stored: for load_percent sensors that already is a percent of the rated value; with several sensors the highest, valid or not), peak_date, days (days with data
    in the window), completeness (mean of the daily availability_pct over the days from the later of the window start and the sensor install date to the window end, as a share) and valid (completeness at least
    `min_completeness`). A sensor without data has a null peak and completeness 0.

Raises:
    FrameError: a needed column is missing; min_completeness is not a share from 0 to 1; a rated_value is not above zero; telemetry.sensor has more than one row for a sns_key; telemetry.measurement_daily has more than one row for a sensor and day; a date is not readable; window is not a (first, last) pair of days in order.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import element_peak_load
    >>> ctx = Context(stage="month12", role="analyst")
    >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "net_key": ["NET-900001"], "rated_value": [100.0], "install_date": ["2019-01-01"], "sensor_type": ["load_percent"]})
    >>> md = pd.DataFrame({"sns_key": ["SNS-900001"] * 2, "date": ["2020-01-01", "2020-01-02"], "max": [55.0, 72.5], "availability_pct": [100.0, 100.0]})
    >>> out = element_peak_load(s, md, context=ctx)
    >>> out[["net_key", "peak_percent", "days", "valid"]].to_dict("records")
    [{'net_key': 'NET-900001', 'peak_percent': 72.5, 'days': 2, 'valid': True}]

## Source columns

- `telemetry.sensor.sns_key`
- `telemetry.sensor.net_key`
- `telemetry.sensor.sensor_type`
- `telemetry.sensor.install_date`
- `telemetry.measurement_daily.sns_key`
- `telemetry.measurement_daily.date`
- `telemetry.measurement_daily.max`
- `telemetry.measurement_daily.availability_pct`
