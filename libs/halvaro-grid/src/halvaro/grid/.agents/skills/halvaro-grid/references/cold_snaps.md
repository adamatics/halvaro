# cold_snaps

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import cold_snaps`.

```python
cold_snaps(weather_daily: pd.DataFrame, *, core_c: float = -8.0, edge_c: float = -4.0, min_core_days: int | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the cold snaps of each zone found from the daily minimum temperatures.

A cold snap has a core of at least min_core_days consecutive days with t_min at or below core_c, extended on both sides over days with t_min at or below edge_c.
PROPOSED: -8, -4 and 2 days (policy.grid.cold_snap; the rule is new, the dates of the configured snap are a test value only and never used to find one). Dates are UTC days of the weather table.
`min_core_days` None (default) reads the proposed fact policy.grid.cold_snap_min_core_days (2; owner decision of 2026-11-13, D12); pass a number to override.

Args:
    weather_daily: The telemetry.weather_daily table, with the columns zone_key, date and t_min.
    core_c: Temperature in degrees C at or below which a day belongs to the core; default -8.0 (PROPOSED).
    edge_c: Temperature in degrees C at or below which a day extends the snap around its core, not below core_c; default -4.0 (PROPOSED).
    min_core_days: Least number of consecutive core days, a whole number of at least 1; None (default) reads the fact policy.grid.cold_snap_min_core_days.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, start, end (both days inclusive), days, core_days, t_min (lowest), t_min_date, one row per cold snap, ordered by zone_key and start.

Raises:
    FrameError: weather_daily is not a DataFrame or lacks zone_key, date or t_min; core_c or edge_c is not a finite number; edge_c is below core_c or min_core_days is not a whole number of at least 1; date is not a UTC timestamp; zone_key or date is null; a zone has more than one row for a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import cold_snaps
    >>> ctx = Context(stage="month12", role="analyst")
    >>> days = pd.DataFrame({"zone_key": ["ZONE-0001"] * 5, "date": pd.date_range("2026-01-10", periods=5), "t_min": [-3.0, -9.0, -10.0, -5.0, 0.0]})
    >>> out = cold_snaps(days, min_core_days=2, context=ctx)
    >>> out["start"].dt.strftime("%Y-%m-%d").tolist(), out["end"].dt.strftime("%Y-%m-%d").tolist()
    (['2026-01-11'], ['2026-01-13'])
    >>> out[["days", "core_days", "t_min"]].to_dict("records")
    [{'days': 3, 'core_days': 2, 't_min': -10.0}]

## Source columns

- `telemetry.weather_daily.zone_key`
- `telemetry.weather_daily.date`
- `telemetry.weather_daily.t_min`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `policy.grid.cold_snap_min_core_days`
