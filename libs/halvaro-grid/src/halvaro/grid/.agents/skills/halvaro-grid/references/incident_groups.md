# incident_groups

Module `halvaro.grid.alarms`. Import: `from halvaro.grid import incident_groups`.

```python
incident_groups(alarm: pd.DataFrame, *, merge_gap_hours: Mapping[str, float] = {'load_high': 60.0, 'default': 8.0}, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the incident number of each alarm, grouping alarms of one element and type that follow each other closely.

Alarms of one element (net_key) and type are one incident while each starts at most the merge gap after the cleared time of the incident so far; the gap is in hours, by type, else the 'default' entry. A null
cleared_ts counts as the raised time. Numbers run from 1 in order of net_key, alarm_type and time.
PROPOSED: merge_gap_hours is cfg:service.yaml#alarm_tickets.merge_gap_hours (load_high 60, default 8); no fact id.

Args:
    alarm: The telemetry.alarm frame, columns raised_ts, cleared_ts, net_key and alarm_type.
    merge_gap_hours: PROPOSED mapping of alarm type to merge gap in hours, with a required 'default' entry used for types not listed.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An int64 Series named incident with the index of the alarm frame (empty when the frame is empty).

Raises:
    FrameError: a column of alarm is missing, merge_gap_hours has no 'default' entry, or raised_ts or cleared_ts holds numbers, unreadable text or a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import incident_groups
    >>> ctx = Context(stage="month12", role="analyst")
    >>> a = pd.DataFrame({"net_key": "NET-900001", "alarm_type": "load_high", "raised_ts": ["2025-03-01 00:00", "2025-03-01 12:00", "2025-03-10 00:00"],
    ...                   "cleared_ts": ["2025-03-01 02:00", "2025-03-01 13:00", None]})
    >>> incident_groups(a, context=ctx).tolist()
    [1, 1, 2]

## Source columns

- `telemetry.alarm.raised_ts`
- `telemetry.alarm.cleared_ts`
- `telemetry.alarm.net_key`
- `telemetry.alarm.alarm_type`
