# sla_attainment

Module `halvaro.grid.callouts`. Import: `from halvaro.grid import sla_attainment`.

```python
sla_attainment(service_ticket: pd.DataFrame, *, team_region: Mapping[str, str] | None = None, by: tuple[str, ...] = ('team_key', 'priority'), service_start: float = 7.0, service_end: float = 16.0, grace_days: int = 14, tolerance_h: float = 0.01, country_of_region: Mapping[str, str] = {'DK': 'DK', 'DE-HH': 'DE'}, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the share of tickets that met their service level, per group such as team and priority, optionally recomputed on the service-hours clock.

The share uses `sla_met` as stored, per group of `by` (default team and priority).
With `team_region` (team key to holiday region, for example {'TEAM-900001': 'DK'}) the verdict is recomputed and the columns n_recomputed, n_recomputed_met, share_recomputed_met,
n_hours_differ (response or attendance hours that differ from the stored ones by more than `tolerance_h`, 0.01) and n_verdict_differs are added. The recompute is the generator's rule:
response_h and attendance_h (rounded to two decimals, as stored) are the service hours (working days of the team's region, `service_start` 7 to `service_end` 16 local time, PROPOSED config hours) between opened and the first response or the
arrival; a corrective or enquiry ticket that is not cancelled and has a first response is met when response_h is within its target and attendance_h within its target (no arrival counts as in target);
a planned ticket (preventive, inspection) is met when resolved on or before the due date plus `grace_days` (14, PROPOSED config planned.grace_days). Credits and money are not computed here.

Args:
    service_ticket: The service.service_ticket frame, columns tkt_key, team_key, opened, ticket_type, sla_met and priority, plus the `by` columns. With `team_region` also first_response_ts, on_site_ts, resolved_ts, due_date, sla_response_target_h, sla_attendance_target_h, status, response_h and attendance_h.
    team_region: Optional mapping of team key to holiday region (DK or DE-HH by default); when given, the verdict is recomputed. Every team of the frame needs a region.
    by: The columns to group by (default team_key and priority); at least one.
    service_start: Hour of the day when service hours start (PROPOSED 7.0); with service_end it must satisfy 0 <= start < end <= 24.
    service_end: Hour of the day when service hours end (PROPOSED 16.0).
    grace_days: Days after the due date within which a planned ticket still counts as met (PROPOSED 14); a whole number of zero or more.
    tolerance_h: Largest difference in hours between recomputed and stored response or attendance hours that is not counted as differing (default 0.01).
    country_of_region: PROPOSED mapping of holiday region to the country whose time zone applies (default DK to DK, DE-HH to DE).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the `by` columns, n_tickets, n_assessed (stored sla_met not null), n_met and share_met (null when nothing is assessed); with `team_region` also n_recomputed, n_recomputed_met, share_recomputed_met, n_hours_differ and n_verdict_differs. Sorted by the `by` columns.

Raises:
    FrameError: a column of service_ticket or of `by` is missing; by is empty; sla_met holds text or numbers; service_ticket repeats a tkt_key; the service hours do not satisfy 0 <= start < end <= 24; with team_region: grace_days is not a whole number of zero or more,
        a team has no region (or a null team), opened has a null, a region has no time zone country, or a first response or an arrival lies before the ticket was opened.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import sla_attainment
    >>> ctx = Context(stage="month12", role="analyst")
    >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002", "TKT-900003"], "team_key": "TEAM-900001", "opened": pd.to_datetime(["2025-03-03 08:00"] * 3),
    ...                   "ticket_type": "corrective", "sla_met": [True, False, True], "priority": "high"})
    >>> out = sla_attainment(t, context=ctx)
    >>> out[["team_key", "priority", "n_tickets", "n_assessed", "n_met", "share_met"]].to_dict("records")
    [{'team_key': 'TEAM-900001', 'priority': 'high', 'n_tickets': 3, 'n_assessed': 3, 'n_met': 2, 'share_met': 0.6667}]

## Source columns

- `service.service_ticket.tkt_key`
- `service.service_ticket.team_key`
- `service.service_ticket.opened`
- `service.service_ticket.first_response_ts`
- `service.service_ticket.on_site_ts`
- `service.service_ticket.resolved_ts`
- `service.service_ticket.due_date`
- `service.service_ticket.ticket_type`
- `service.service_ticket.sla_met`
- `service.service_ticket.sla_response_target_h`
- `service.service_ticket.sla_attendance_target_h`
- `service.service_ticket.priority`
- `service.service_ticket.status`
