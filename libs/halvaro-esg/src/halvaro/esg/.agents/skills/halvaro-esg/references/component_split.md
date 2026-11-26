# component_split

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import component_split`.

```python
component_split(PF: pd.DataFrame, P: pd.DataFrame, cs: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the median kg CO2e per route metre of each footprint component over a comparable set of projects.

Each project's component over all periods is divided by its route length, then the median is taken over the projects with a length. Projects without a route length are left out.

Args:
    PF: The energy-esg.project_footprint table, with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e and subcontractor_kgco2e.
    P: The projects.project table, with the columns prj_key and route_length_m.
    cs: A delivery comparable_set frame, with the column prj_key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns component (materials, transport, site, subcontractor), median_kgco2e_per_m (three decimals; null when no project has a length) and n (projects used).

Raises:
    FrameError: PF, P or cs lacks a needed column; a prj_key of cs or PF is null; cs or P has two rows for a project; PF has two rows for a project and period.
    FrameError: a component of PF is null or not a number; a footprint project of the set is not in projects.project; route_length_m is zero or less or not a number.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import component_split
    >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "period": ["2025-01", "2025-01"], "materials_kgco2e": [100.0, 300.0],
    ...                    "transport_kgco2e": [10.0, 30.0], "site_kgco2e": [50.0, 150.0], "subcontractor_kgco2e": [0.0, 0.0]})
    >>> P = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "route_length_m": [100.0, 100.0]})
    >>> cs = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
    >>> out = component_split(PF, P, cs, context=ctx)
    >>> out[["component", "median_kgco2e_per_m", "n"]].values.tolist()[:2]
    [['materials', 2.0, 2], ['transport', 0.2, 2]]

## Source columns

- `energy-esg.project_footprint.prj_key`
- `energy-esg.project_footprint.period`
- `energy-esg.project_footprint.materials_kgco2e`
- `energy-esg.project_footprint.transport_kgco2e`
- `energy-esg.project_footprint.site_kgco2e`
- `energy-esg.project_footprint.subcontractor_kgco2e`
- `energy-esg.project_footprint.total_kgco2e`
- `projects.project.prj_key`
- `projects.project.route_length_m`
- `projects.project.start`
- `projects.project.status`
