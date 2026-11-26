# overrun_distribution

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import overrun_distribution`.

```python
overrun_distribution(overrun: pd.DataFrame, project: pd.DataFrame, totals: pd.DataFrame | None = None, *, projects: Sequence[str] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the spread of the schedule overrun, and with estimate totals of the cost overrun, over a set of completed projects.

The measures are the minimum, quartiles, median, maximum and mean of the schedule overrun (the `overrun` column of schedule_overrun for completed projects, basis actual) and, with `totals` (estimate_bridge totals), of the cost overrun: final_cost over the tender total minus one, full projects with both numbers, contract currency, no conversion. `projects` limits the set (a comparable set). PROPOSED: the definitions of policy.delivery.overrun_definition (needed): schedule fraction as in the generator test, cost overrun a separate measure.

Args:
    overrun: The output of schedule_overrun; it needs prj_key and a numeric overrun, and may carry basis (only the rows of basis actual count; without a basis column every row is taken as actual).
    project: The projects.project frame, one row per prj_key; it needs prj_key, final_cost, legacy and currency.
    totals: Optional totals output of estimate_bridge (prj_key, type, total_cost, currency); the tender rows give the cost overrun measure. Without it only the schedule measure is returned.
    projects: Optional prj_key values (a key as text or a list) that limit the set.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per measure (schedule, then cost when totals is given) and the columns measure, n, n_legacy, min, q25, median, q75, max, mean. The statistics are null when n is zero.

Raises:
    FrameError: overrun, project or totals is not a DataFrame, lacks a needed column or (project) repeats a prj_key; overrun is not numeric; the overrun frame has more than one actual row for a project; a project of the overrun frame is not in the project frame; with totals: final_cost is not numeric, a project has more than one tender row, or a tender is in another currency than the project.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import overrun_distribution
    >>> ctx = Context(stage="month12", role="analyst")
    >>> overrun = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "overrun": [0.1, 0.3], "basis": ["actual", "actual"]})
    >>> project = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "final_cost": [120.0, 200.0], "legacy": [False, False], "currency": ["DKK", "DKK"]})
    >>> totals = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "type": ["tender", "tender"], "total_cost": [100.0, 100.0], "currency": ["DKK", "DKK"]})
    >>> r = overrun_distribution(overrun, project, totals, context=ctx)
    >>> r["measure"].tolist()
    ['schedule', 'cost']
    >>> [round(x, 3) for x in r["median"]]
    [0.2, 0.6]

## Source columns

- `projects.project.prj_key`
- `projects.project.final_cost`
- `projects.project.legacy`
- `projects.project.currency`
- `projects.estimate_version.total_cost`
