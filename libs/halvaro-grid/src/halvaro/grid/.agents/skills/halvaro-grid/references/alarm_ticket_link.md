# alarm_ticket_link

Module `halvaro.grid.alarms`. Import: `from halvaro.grid import alarm_ticket_link`.

```python
alarm_ticket_link(alarm: pd.DataFrame, ticket_alarm: pd.DataFrame, service_ticket: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to know which alarms have a service ticket, and how many tickets each incident has.

The alarm frame gets linked, tkt_key and link_type (trigger or precursor) from service.ticket_alarm, matched on sns_key and raised_ts. The result keeps the rows and index of the alarm frame. Many alarms of an
incident share one ticket (T12), so most alarms are not linked. A link whose ticket is not in service.service_ticket or whose alarm is not in the frame raises.

Args:
    alarm: The telemetry.alarm frame, columns sns_key and raised_ts; with net_key, alarm_type and cleared_ts as well it also gets the incident columns.
    ticket_alarm: The service.ticket_alarm frame, columns sns_key, raised_ts, link_type and tkt_key.
    service_ticket: The service.service_ticket frame, column tkt_key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The alarm frame with the extra columns linked (bool), tkt_key and link_type (null when not linked); when net_key, alarm_type and cleared_ts are in the frame also incident (see incident_groups) and incident_tickets
    (distinct tickets of the incident, 0 when none).

Raises:
    FrameError: a column of alarm, ticket_alarm or service_ticket is missing, a ticket_alarm or alarm key pair (sns_key, raised_ts) is repeated or null, a link names a ticket that is not in service.service_ticket,
        a link names an alarm that is not in the alarm frame, the alarm frame already has a column linked, tkt_key or link_type, or a timestamp is unreadable or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import alarm_ticket_link
    >>> ctx = Context(stage="month12", role="analyst")
    >>> a = pd.DataFrame({"sns_key": "SNS-900001", "raised_ts": ["2025-03-01 00:00", "2025-03-01 12:00"]})
    >>> t = pd.DataFrame({"sns_key": ["SNS-900001"], "raised_ts": ["2025-03-01 00:00"], "link_type": ["trigger"], "tkt_key": ["TKT-900001"]})
    >>> st = pd.DataFrame({"tkt_key": ["TKT-900001"]})
    >>> out = alarm_ticket_link(a, t, st, context=ctx)
    >>> out["linked"].tolist()
    [True, False]
    >>> out["tkt_key"].tolist()
    ['TKT-900001', nan]

## Source columns

- `telemetry.alarm.sns_key`
- `telemetry.alarm.raised_ts`
- `service.ticket_alarm.sns_key`
- `service.ticket_alarm.raised_ts`
- `service.ticket_alarm.link_type`
- `service.ticket_alarm.tkt_key`
- `service.service_ticket.tkt_key`
