# due_within

Module `halvaro.grid.maintenance`. Import: `from halvaro.grid import due_within`.

```python
due_within(maintenance_plan: pd.DataFrame, as_of: DateLike, horizon_days: int, *, active_status: tuple[str, ...] = ('active',), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how many active maintenance plans fall due within a number of days from a date, per team and plan type.

Active plans with a next due date from the as-of date to `horizon_days` days later (both inclusive) are counted.

Args:
    maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, next_due, last_done, team_key and status.
    as_of: The first day of the horizon.
    horizon_days: Days after the as-of date that the horizon reaches (inclusive); a whole number of zero or more.
    active_status: The statuses that count as active (default only "active"); a tuple or list.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns team_key, plan_type, n_plans, first_due and last_due, sorted by team_key and plan_type; an empty frame with these columns when nothing falls due.

Raises:
    FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; next_due or last_done is not a time; as_of is not a date; horizon_days is not a whole number of zero or more; active_status is a single text or not iterable.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import due_within
    >>> ctx = Context(stage="month12", role="analyst")
    >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "plan_no": [1, 1, 1], "plan_type": "condition_inspection",
    ...                   "next_due": ["2025-04-05", "2025-04-20", "2025-07-01"], "last_done": ["2024-04-05", "2024-04-20", "2024-07-01"], "team_key": "TEAM-900001", "status": "active"})
    >>> out = due_within(p, "2025-04-01", 30, context=ctx)
    >>> out[["team_key", "n_plans"]].to_dict("records")
    [{'team_key': 'TEAM-900001', 'n_plans': 2}]
    >>> out["last_due"].dt.strftime("%Y-%m-%d").tolist()
    ['2025-04-20']

## Source columns

- `service.maintenance_plan.net_key`
- `service.maintenance_plan.plan_no`
- `service.maintenance_plan.plan_type`
- `service.maintenance_plan.next_due`
- `service.maintenance_plan.last_done`
- `service.maintenance_plan.team_key`
- `service.maintenance_plan.status`
