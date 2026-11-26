# route_facts

Module `halvaro.grid.recipes`. Import: `from halvaro.grid import route_facts`.

```python
route_facts(route_change: pd.DataFrame, soil: pd.DataFrame, conditions: pd.DataFrame, projects: pd.DataFrame | None = None, *, planned_version: int = 2, context: halvaro.core.access.Context) -> RouteFacts
```

Use this when you need the route length, versions, soil and crossing flags of each project, with the projects that have no route version listed as summary.

Route length, versions, soil and flags per project, from `route_change` (planned and as-built length, changed), `majority_soil` and `route_conditions_summary` (both per project and version).
Columns of `routes`: the route_change columns plus, for the planned version, soil_class, soil_share, crosses_poor_bearing, crosses_high_groundwater, crosses_site_observation (when the conditions frame has it). With the projects frame
(`prj_key`) a project without a route version is listed in `summary_projects` (legacy projects marked summary), never given invented values. Only the soil and condition rows of `planned_version` are used; other versions are not.

Args:
    route_change: The output of route_change; it needs the columns prj_key, planned_length_m, as_built_length_m, delta_m and changed, one row per project.
    soil: The output of majority_soil; it needs the columns prj_key, version, soil_class and share.
    conditions: The output of route_conditions_summary; it needs the columns prj_key, version, crosses_poor_bearing and crosses_high_groundwater.
    projects: The projects.project table with the column prj_key, or None to list no summary projects.
    planned_version: The version of gis.project_area whose soil and condition rows are used, default 2 (the planned route).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An RouteFacts with the fields routes (one row per project, sorted by prj_key), soil (the soil frame as given, fresh index), summary_projects (sorted tuple of prj_key of the projects without a route version) and labels (the tuple holding 'synthetic data').

Raises:
    FrameError: a piece lacks a needed column; route_change has more than one row for a project; majority_soil or route_conditions_summary has more than one row for a project and version; soil or conditions rows for a project that route_change does not hold.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import route_facts
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rc = pd.DataFrame({"prj_key": ["PRJ-900001"], "planned_length_m": [100.0], "as_built_length_m": [104.0], "delta_m": [4.0], "changed": [True]})
    >>> so = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [2], "soil_class": ["clay"], "share": [0.6]})
    >>> co = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [2], "crosses_poor_bearing": [False], "crosses_high_groundwater": [True]})
    >>> pr = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
    >>> f = route_facts(rc, so, co, pr, context=ctx)
    >>> f.routes[["prj_key", "soil_class", "soil_share"]].to_dict("records"), f.summary_projects
    ([{'prj_key': 'PRJ-900001', 'soil_class': 'clay', 'soil_share': 0.6}], ('PRJ-900002',))

## Source columns

- `gis.project_area.prj_key`
- `gis.project_area.length_m`
- `gis.ground_condition.soil_class`
- `projects.project.prj_key`
