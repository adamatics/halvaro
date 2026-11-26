# alarm_summary

Module `halvaro.grid.alarms`. Import: `from halvaro.grid import alarm_summary`.

```python
alarm_summary(alarm: pd.DataFrame, *, first_month: str | None = None, last_month: str | None = None, context: halvaro.core.access.Context) -> AlarmSummary
```

Use this when you need counts of alarms by zone, type, severity and month, and the background alarm rate per zone and year.

Counts are by UTC month of raised_ts. The background rate is the alarms per month over the months of the year inside first_month..last_month. first_month and last_month default to the first and last month of the
alarm frame; pass the data window as months ('YYYY-MM') for a rate that counts months without alarms, as a year with few alarms is otherwise rated on the months it happens to have. An empty alarm frame without
both months gives an empty background.

Args:
    alarm: The telemetry.alarm frame, columns zone_key, alarm_type, severity, raised_ts and sns_key.
    first_month: First month of the background window ('YYYY-MM'); None takes the first month of the alarm frame.
    last_month: Last month of the background window ('YYYY-MM'); None takes the last month of the alarm frame.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An AlarmSummary named tuple: counts (zone_key, alarm_type, severity, month, n_alarms, sorted by these keys) and background (zone_key, year, n_alarms, months, per_month; per_month is rounded to 4 decimals, sorted by zone_key and year).

Raises:
    FrameError: a column of alarm is missing, zone_key, alarm_type, severity or raised_ts is null, raised_ts is not a readable timestamp or has a time zone, first_month or last_month is not a month, or first_month is after last_month.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import alarm_summary
    >>> ctx = Context(stage="month12", role="analyst")
    >>> a = pd.DataFrame({"zone_key": "ZONE-0001", "alarm_type": "load_high", "severity": ["warning", "warning", "critical"], "sns_key": "SNS-900001",
    ...                   "raised_ts": ["2025-03-01 10:00", "2025-03-02 10:00", "2025-04-01 10:00"]})
    >>> out = alarm_summary(a, first_month="2025-01", last_month="2025-12", context=ctx)
    >>> out.counts[["severity", "month", "n_alarms"]].to_dict("records")
    [{'severity': 'critical', 'month': '2025-04', 'n_alarms': 1}, {'severity': 'warning', 'month': '2025-03', 'n_alarms': 2}]
    >>> out.background[["year", "n_alarms", "months", "per_month"]].to_dict("records")
    [{'year': 2025, 'n_alarms': 3, 'months': 12, 'per_month': 0.25}]

## Source columns

- `telemetry.alarm.zone_key`
- `telemetry.alarm.alarm_type`
- `telemetry.alarm.severity`
- `telemetry.alarm.raised_ts`
- `telemetry.alarm.sns_key`
