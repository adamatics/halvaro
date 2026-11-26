# comparable_coverage

Module `halvaro.delivery.comparables`. Import: `from halvaro.delivery import comparable_coverage`.

```python
comparable_coverage(comparable: pd.DataFrame, project: pd.DataFrame, estimate_version: pd.DataFrame, project_role: pd.DataFrame, time_entry_projects: Sequence[str], *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to know which data each project of a comparable set has: estimates, final cost, route length, time entries and roster.

Returns what data each project of a comparable set has: has_estimate (an estimate version exists), has_final_estimate, has_final_cost, has_route_length, has_time_entries (its key is in time_entry_projects: a list of the distinct prj_key of
projects.time_entry, or the time_entry frame itself, whose prj_key column is used), has_roster (project_role rows) and roster_only (a roster and no time entries).

Args:
    comparable: The frame of comparable_set (or the ComparableSet itself), with prj_key, one row per project.
    project: The projects.project frame; it needs prj_key, final_cost and route_length_m.
    estimate_version: The projects.estimate_version frame; it needs prj_key and type (the value final marks a final estimate).
    project_role: The projects.project_role frame; it needs prj_key.
    time_entry_projects: A list (or set, array, Index) of the distinct prj_key of projects.time_entry, or the projects.time_entry frame itself; a Series or a groupby is refused.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per project of the set, in its order: prj_key and the booleans has_estimate, has_final_estimate, has_final_cost, has_route_length, has_time_entries, has_roster and roster_only.

Raises:
    FrameError: comparable is not a DataFrame with prj_key or has a project more than once; time_entry_projects is a frame without prj_key or is not a list of keys or a frame; project lacks a needed column or has a null or repeated prj_key; estimate_version or project_role is not a DataFrame or lacks a needed column; a project of the set is not in the project frame; a frame has an index named like one of its columns.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import comparable_coverage
    >>> ctx = Context(stage="month12", role="analyst")
    >>> comp = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "final_cost": [100.0, None], "route_length_m": [5000.0, None]})
    >>> est = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["final"]})
    >>> role = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
    >>> out = comparable_coverage(comp, prj, est, role, ["PRJ-900001"], context=ctx)
    >>> out["has_final_cost"].tolist(), out["roster_only"].tolist()
    ([True, False], [False, True])

## Source columns

- `projects.project.prj_key`
- `projects.project.final_cost`
- `projects.project.route_length_m`
- `projects.estimate_version.prj_key`
- `projects.estimate_version.type`
- `projects.project_role.prj_key`
- `projects.time_entry.prj_key`
