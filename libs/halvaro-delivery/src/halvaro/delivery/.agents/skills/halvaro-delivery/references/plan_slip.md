# plan_slip

Module `halvaro.delivery.schedule`. Import: `from halvaro.delivery import plan_slip`.

```python
plan_slip(plan_version: pd.DataFrame, as_of: dt.date | None = None, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how far each plan version moved planned_end against the baseline (version 1) and against the version before it.

Gives planned_end of each plan version against version 1 (baseline) and against the version before it: slip_days, step_days, with created and reason. A project without a version 1 has baseline_end null and slip_days null.
With as_of only versions created on or before it are kept (a plan not yet written does not exist; a version with no created date is kept). Source columns are kept.

Args:
    plan_version: The projects.plan_version frame, one row per prj_key and plan_version; it needs prj_key, plan_version (numeric), created, reason and planned_end.
    as_of: A date; only versions created on or before it are kept. None keeps all versions.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame sorted by prj_key and plan_version with the source columns (created and planned_end as calendar days) and the added columns baseline_end, slip_days (planned_end minus baseline_end) and step_days (planned_end minus the previous version's), in days.

Raises:
    FrameError: plan_version is not a DataFrame, has duplicate column names or lacks a needed column; prj_key or plan_version has a null; a prj_key and plan_version pair is repeated; plan_version is not numeric; created or planned_end holds an unreadable value or a time zone.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import plan_slip
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pv = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "plan_version": [1, 2, 3],
    ...                    "created": ["2029-01-01", "2029-02-01", "2029-03-01"], "reason": ["base", "r1", "r2"],
    ...                    "planned_end": ["2029-06-01", "2029-06-11", "2029-06-21"]})
    >>> plan_slip(pv, context=ctx)["slip_days"].tolist()
    [0.0, 10.0, 20.0]
    >>> plan_slip(pv, "2029-02-15", context=ctx)["plan_version"].tolist()
    [1, 2]

## Source columns

- `projects.plan_version.prj_key`
- `projects.plan_version.plan_version`
- `projects.plan_version.created`
- `projects.plan_version.reason`
- `projects.plan_version.planned_end`
