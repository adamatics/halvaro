# on_call

Module `halvaro.grid.callouts`. Import: `from halvaro.grid import on_call`.

```python
on_call(on_call_rota: pd.DataFrame, on_date: DateLike, *, team_key: str | None = None, days: int = 7, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need who is primary and secondary on call on a given date, per team.

The rota row of each team that started on or before the date and ends where the next row of the team starts; the last row of a team runs `days` (7) days. A team without a row for the date is not listed. `team_key` narrows to one team or a list.

Args:
    on_call_rota: The service.on_call_rota frame, columns team_key, week_start, primary_emp_key and secondary_emp_key.
    on_date: The date to look up.
    team_key: Optional team key, or a list of team keys, to narrow the result; all teams when omitted.
    days: How many days a row runs at most, and how long the last row of a team runs (default 7); a whole number of one or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns team_key, week_start, primary_emp_key and secondary_emp_key, one row per team on call on the date, sorted by team_key.

Raises:
    FrameError: a column of on_call_rota is missing; days is not a whole number of one or more; on_date is not a date; a week_start is not a date or is missing (or has a time zone); the rota has more than one row for a team and week.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import on_call
    >>> ctx = Context(stage="month12", role="analyst")
    >>> r = pd.DataFrame({"team_key": ["TEAM-900001", "TEAM-900001"], "week_start": ["2025-03-03", "2025-03-10"],
    ...                   "primary_emp_key": ["EMP-900001", "EMP-900002"], "secondary_emp_key": ["EMP-900003", "EMP-900004"]})
    >>> out = on_call(r, "2025-03-12", context=ctx)
    >>> out[["team_key", "primary_emp_key", "secondary_emp_key"]].to_dict("records")
    [{'team_key': 'TEAM-900001', 'primary_emp_key': 'EMP-900002', 'secondary_emp_key': 'EMP-900004'}]

## Source columns

- `service.on_call_rota.team_key`
- `service.on_call_rota.week_start`
- `service.on_call_rota.primary_emp_key`
- `service.on_call_rota.secondary_emp_key`
