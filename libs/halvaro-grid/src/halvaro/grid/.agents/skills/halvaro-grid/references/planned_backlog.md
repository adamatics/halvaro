# planned_backlog

Module `halvaro.grid.maintenance`. Import: `from halvaro.grid import planned_backlog`.

```python
planned_backlog(service_ticket: pd.DataFrame, *, sources: tuple[str, ...] = ('planned_maintenance', 'inspection'), grace_days: int = 0, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how late planned tickets were resolved against their due date, by team and month of the due date.

Planned tickets (source in `sources`, PROPOSED planned_maintenance and inspection) that were resolved after their due date plus `grace_days` (PROPOSED 0) are counted as late.
mean_lateness_days is taken over all resolved planned tickets and is negative when early: the figure of the generator test; mean_days_late is taken over the late ones (days between the due date and the resolution time, fractions of a day kept at two decimals).
Tickets without a resolution time or a due date are left out (still open).

Args:
    service_ticket: The service.service_ticket frame, columns tkt_key, source, due_date, resolved_ts and team_key.
    sources: The ticket sources that count as planned work (PROPOSED planned_maintenance and inspection); a tuple, not a single text.
    grace_days: Days after the due date (counted to its end) that are still on time (PROPOSED 0); a whole number of zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns team_key, period (YYYY-MM of the due date), n_planned (resolved planned tickets), n_late, late_share, mean_lateness_days, mean_days_late and max_days_late (both null when nothing is late), sorted by team_key and period; an empty frame with these columns when no planned ticket is resolved.

Raises:
    FrameError: a column of service_ticket is missing; it repeats a tkt_key; grace_days is not a whole number of zero or more; sources is a single text; due_date or resolved_ts is not a time; a resolved planned ticket has no team_key.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import planned_backlog
    >>> ctx = Context(stage="month12", role="analyst")
    >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "source": "planned_maintenance", "due_date": ["2025-03-10", "2025-03-20"],
    ...                   "resolved_ts": ["2025-03-12 10:00", "2025-03-19 10:00"], "team_key": "TEAM-900001"})
    >>> out = planned_backlog(t, context=ctx)
    >>> out[["team_key", "period", "n_planned", "n_late", "late_share"]].to_dict("records")
    [{'team_key': 'TEAM-900001', 'period': '2025-03', 'n_planned': 2, 'n_late': 1, 'late_share': 0.5}]

## Source columns

- `service.service_ticket.tkt_key`
- `service.service_ticket.source`
- `service.service_ticket.due_date`
- `service.service_ticket.resolved_ts`
- `service.service_ticket.team_key`
