# overdue_plans

Module `halvaro.grid.maintenance`. Import: `from halvaro.grid import overdue_plans`.

```python
overdue_plans(maintenance_plan: pd.DataFrame, as_of: DateLike, *, grace_days: int = 14, active_status: tuple[str, ...] = ('active',), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the active maintenance plans that are overdue beyond the grace period, with the days overdue.

Active plans whose next due date is more than `grace_days` (PROPOSED 14, config planned.grace_days) before the as-of date, with the days overdue beyond the grace. A plan without a next due date is not overdue.

Args:
    maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, next_due, last_done, team_key and status.
    as_of: The as-of date.
    grace_days: Days after the next due date that are still tolerated (PROPOSED 14); a whole number of zero or more.
    active_status: The statuses that count as active (default only "active"); a tuple or list.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns net_key, plan_no, plan_type, team_key, next_due, last_done and days_overdue (beyond the grace), sorted by days_overdue (largest first), net_key and plan_no.

Raises:
    FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; next_due or last_done is not a time; as_of is not a date; grace_days is not a whole number of zero or more; active_status is a single text or not iterable.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import overdue_plans
    >>> ctx = Context(stage="month12", role="analyst")
    >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "plan_no": [1, 1], "plan_type": "condition_inspection", "next_due": ["2025-03-01", "2025-05-30"],
    ...                   "last_done": ["2024-03-01", "2024-05-30"], "team_key": "TEAM-900001", "status": "active"})
    >>> out = overdue_plans(p, "2025-04-01", context=ctx)
    >>> out[["net_key", "days_overdue"]].to_dict("records")
    [{'net_key': 'NET-900001', 'days_overdue': 17}]

## Source columns

- `service.maintenance_plan.net_key`
- `service.maintenance_plan.plan_no`
- `service.maintenance_plan.plan_type`
- `service.maintenance_plan.next_due`
- `service.maintenance_plan.last_done`
- `service.maintenance_plan.team_key`
- `service.maintenance_plan.status`
