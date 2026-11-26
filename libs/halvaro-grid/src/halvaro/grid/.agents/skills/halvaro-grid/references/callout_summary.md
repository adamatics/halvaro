# callout_summary

Module `halvaro.grid.callouts`. Import: `from halvaro.grid import callout_summary`.

```python
callout_summary(service_ticket: pd.DataFrame, ticket_labour: pd.DataFrame, *, freq: str = 'month', window: Window | None = None, tolerance: float = 0.02, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need tickets, labour hours, overtime hours and travel hours by team, period and call-out kind.

Columns: team_key, period (the UTC month as YYYY-MM, or the Monday of the week), callout_kind, n_tickets (tickets opened in the period), labour_hours, overtime_hours, travel_hours (worked in the period, by `work_date`, by the team of the labour row
when the column exists, otherwise the ticket's team, on tickets of that kind; `hours` already holds overtime and travel, as the ticket totals do).
`window` is two days (both included): for tickets the UTC date of `opened`, for labour the local `work_date`, which are two clocks (a ticket opened late in the evening UTC belongs to the next local day); `freq` is month or week.
A labour row whose ticket is unknown, or a ticket whose labour sums differ from its own hour columns by more than `tolerance` hours (0.02, the generator test), raises FrameError when the ticket has the columns labour_hours, overtime_hours
and travel_hours. Person level rows are never returned.

Args:
    service_ticket: The service.service_ticket frame, columns tkt_key, team_key, opened and callout_kind; optionally labour_hours, overtime_hours and travel_hours, which are then checked against the labour rows.
    ticket_labour: The service.ticket_labour frame, columns tkt_key, work_date, hours, overtime_hours and travel_hours; optionally team_key.
    freq: "month" (default) or "week": the size of the period.
    window: Optional two days (first day, last day, both included) that limit tickets (by the UTC date of opened) and labour (by work_date).
    tolerance: Largest allowed difference in hours between a ticket's own hour columns and the sum of its labour rows (default 0.02); zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns team_key, period, callout_kind, n_tickets, labour_hours, overtime_hours and travel_hours (hours rounded to two decimals, zero where nothing was worked), sorted by team_key, period and callout_kind.

Raises:
    FrameError: a column of service_ticket or ticket_labour is missing; freq is not month or week; service_ticket repeats a tkt_key; tolerance is negative or not a number; window is not two dates or ends before it starts;
        opened or work_date is not a date on every row (or has a time zone, for work_date); ticket_labour has rows for tickets that service_ticket does not hold; ticket_labour has null hours; a ticket hour column has nulls or differs from the labour sum by more than tolerance.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import callout_summary
    >>> ctx = Context(stage="month12", role="analyst")
    >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "team_key": ["TEAM-900001", "TEAM-900001"],
    ...                   "opened": pd.to_datetime(["2025-03-03 08:00", "2025-03-10 09:00"]), "callout_kind": ["standby", "standby"]})
    >>> lab = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "work_date": ["2025-03-03", "2025-03-10"],
    ...                     "hours": [3.0, 2.0], "overtime_hours": [1.0, 0.0], "travel_hours": [0.5, 0.5]})
    >>> out = callout_summary(t, lab, context=ctx)
    >>> out[["period", "n_tickets", "labour_hours", "overtime_hours"]].to_dict("records")
    [{'period': '2025-03', 'n_tickets': 2, 'labour_hours': 5.0, 'overtime_hours': 1.0}]

## Source columns

- `service.service_ticket.tkt_key`
- `service.service_ticket.team_key`
- `service.service_ticket.opened`
- `service.service_ticket.callout_kind`
- `service.ticket_labour.tkt_key`
- `service.ticket_labour.work_date`
- `service.ticket_labour.hours`
- `service.ticket_labour.overtime_hours`
- `service.ticket_labour.travel_hours`
