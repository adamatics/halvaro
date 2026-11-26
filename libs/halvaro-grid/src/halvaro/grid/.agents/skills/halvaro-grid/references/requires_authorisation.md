# requires_authorisation

Module `halvaro.grid.callouts`. Import: `from halvaro.grid import requires_authorisation`.

```python
requires_authorisation(maintenance_plan: pd.DataFrame, *, active_status: tuple[str, ...] = ('active',), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how many active maintenance plans need electrical authorisation, per team and plan type.

The active plans with the flag `requires_electrical_authorisation` are counted. Who holds the authorisation is competence data and not read here (halvaro-hr).

Args:
    maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, requires_electrical_authorisation (true or false), team_key and status.
    active_status: The statuses that count as active (default only "active"); a tuple, not a single text.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns team_key, plan_type, n_plans, n_requiring and share_requiring (rounded to four decimals), sorted by team_key and plan_type; an empty frame with these columns when no plan is active.

Raises:
    FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; the flag has nulls or holds text or numbers; active_status is a single text.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import requires_authorisation
    >>> ctx = Context(stage="month12", role="analyst")
    >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "plan_no": [1, 1, 1], "plan_type": "condition_inspection",
    ...                   "requires_electrical_authorisation": [True, False, True], "team_key": "TEAM-900001", "status": ["active", "active", "closed"]})
    >>> out = requires_authorisation(p, context=ctx)
    >>> out[["team_key", "plan_type", "n_plans", "n_requiring", "share_requiring"]].to_dict("records")
    [{'team_key': 'TEAM-900001', 'plan_type': 'condition_inspection', 'n_plans': 2, 'n_requiring': 1, 'share_requiring': 0.5}]

## Source columns

- `service.maintenance_plan.net_key`
- `service.maintenance_plan.plan_no`
- `service.maintenance_plan.plan_type`
- `service.maintenance_plan.requires_electrical_authorisation`
- `service.maintenance_plan.team_key`
- `service.maintenance_plan.status`
