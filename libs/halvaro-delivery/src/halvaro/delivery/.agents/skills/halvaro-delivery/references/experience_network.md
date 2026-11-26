# experience_network

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import experience_network`.

```python
experience_network(project_role: pd.DataFrame, project: pd.DataFrame, prj_keys: Sequence[str], employee: pd.DataFrame | None = None, *, project_types: Sequence[str] | None = None, soil_classes: Sequence[str] | None = None, countries: Sequence[str] | None = None, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> ExperienceNetwork
```

Use this when you need the person to project network of a list of projects: who worked on which project, for how long, and which people worked together.

The result is filtered by project type, soil class and country (all optional lists), with a leaver flag from the hr frame (`emp_key`, `leave_date`: a leaver has a leave date on or before `as_of`, default the release date world.now). Edges are one row per person and project: roles (sorted, joined with '; '), first start, last end, hours_total, basis (the one basis or 'mixed'), legacy. Pairs are the people of one project who worked there at the same time, from the role rows themselves (a person's stints are merged when they touch or overlap, so a gap is a gap; both days inclusive): prj_key, emp_a, emp_b (emp_a sorts first), first overlap start, last overlap end, overlap_days (the days summed over the stints). The network is as of the day: roles that start later are left out, an open role runs to the day and a role that ends later is cut at the day. Hours of a role that crosses the day are prorated by days to the day. Hours of legacy roster rows are estimates (see roster). No ranking and no score: the order is by key.

Args:
    project_role: The projects.project_role frame; it needs prj_key, emp_key, project_role, start, end, hours_total and basis.
    project: The projects.project frame, one row per prj_key; it needs prj_key, type, soil_class, country and legacy.
    prj_keys: The project keys of the network (one key as text is also accepted).
    employee: Optional hr.employee frame, one row per emp_key, with emp_key and leave_date; without it no one is a leaver.
    project_types: Optional list of project types to keep.
    soil_classes: Optional list of soil classes to keep.
    countries: Optional list of countries to keep.
    as_of: Optional day of the network; the default is the release date world.now.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An ExperienceNetwork with `nodes` (node_key, kind person or project, type, country, soil_class, leaver; sorted by kind and node_key), `edges` (prj_key, emp_key, roles, start, end, hours_total, basis, legacy; sorted by prj_key, emp_key) and `pairs` (prj_key, emp_a, emp_b, overlap_start, overlap_end, overlap_days; sorted by prj_key, emp_a, emp_b).

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; project or employee has more than one row for a key; a project of the list is not in project; project_types, soil_classes or countries is a single text; a role row has no emp_key or start; a role period ends before it starts; a date column holds a time zone or a value that is not a date.
    PeriodError: as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import experience_network
    >>> ctx = Context(stage="month12", role="analyst")
    >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900001", "EMP-900002"], "project_role": ["manager", "engineer"],
    ...                       "start": ["2026-01-01", "2026-01-06"], "end": ["2026-01-10", "2026-01-20"], "hours_total": [80.0, 100.0], "basis": ["time_entries"] * 2})
    >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tunnel"], "soil_class": ["clay"], "country": ["NL"], "legacy": [False]})
    >>> net = experience_network(roles, proj, ["PRJ-900001"], as_of="2026-02-01", context=ctx)
    >>> net.edges["emp_key"].tolist()
    ['EMP-900001', 'EMP-900002']
    >>> net.pairs["overlap_days"].tolist()
    [5]

## Source columns

- `projects.project_role.prj_key`
- `projects.project_role.emp_key`
- `projects.project_role.project_role`
- `projects.project_role.start`
- `projects.project_role.end`
- `projects.project_role.hours_total`
- `projects.project_role.basis`
- `projects.project.legacy`
- `projects.project.type`
- `projects.project.soil_class`
- `projects.project.country`
- `hr.employee.leave_date`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
