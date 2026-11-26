# to_local

Module `halvaro.grid.series`. Import: `from halvaro.grid import to_local`.

```python
to_local(ts: TimesLike, country: str, *, timezones: Mapping[str, str] = {'DK': 'Europe/Copenhagen', 'DE': 'Europe/Berlin'}, context: halvaro.core.access.Context) -> pd.Series[Any]
```

Use this when you need stored UTC timestamps as local time of the country of a zone.

UTC timestamps (naive, as stored) as time zone aware local time of the country of the zone (DK Europe/Copenhagen, DE Europe/Berlin).
PROPOSED: the zone names are the config values cfg:telemetry.yaml#timezones.DK and .DE; a fact id is needed.

Args:
    ts: The UTC timestamps as stored (telemetry.measurement.ts), without a time zone.
    country: The country of the zone (gis.supply_zone.country), a key of `timezones`.
    timezones: The mapping from country to time zone name; defaults to DK Europe/Copenhagen and DE Europe/Berlin (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Series of time zone aware local timestamps, in the order of ts.

Raises:
    FrameError: the country is not a string or has no time zone in `timezones`; a timestamp cannot be read, holds numbers or has a time zone; the time zone name is not known.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> from halvaro.core import Context
    >>> from halvaro.grid import to_local
    >>> ctx = Context(stage="month12", role="analyst")
    >>> to_local(["2020-01-15 12:00", "2020-07-15 12:00"], "DK", context=ctx).dt.hour.tolist()
    [13, 14]

## Source columns

- `telemetry.measurement.ts`
- `gis.supply_zone.country`
