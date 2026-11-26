# per_metre

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import per_metre`.

```python
per_metre(PF: pd.DataFrame, P: pd.DataFrame, RC: pd.DataFrame | None = None, *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the kilograms CO2e per planned route metre of each project.

The footprint over all periods is divided by the planned route length; the value is null when the length is null. The value is a Provenance (synthetic, status VERIFY+synthetic, fact world.window_start).
PROPOSED: the RC column name is a stand-in until halvaro-grid defines the frame.

Args:
    PF: The energy-esg.project_footprint table, with the columns prj_key, period and total_kgco2e.
    P: The projects.project table, with the columns prj_key, route_length_m, start and status.
    RC: Optional grid route_change frame with prj_key and as_built_length_m; it only sets length_changed, the planned length stays the default (see the route change of the grid library).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Provenance whose value is a frame sorted by prj_key with the columns prj_key, total_kgco2e, route_length_m, kgco2e_per_m (three decimals), per_m_exact (unrounded, what limit_check compares),
    partial_history (the project started before world.window_start, because purchases are in the data from then; null for a project without a start), active_to_date (status active) and length_changed (the as-built length of RC differs from the planned one by more than half a metre; false without a planned length).

Raises:
    FrameError: PF, P or RC lacks a needed column; PF has two rows for a project and period or P two rows for a project; PF has a null prj_key or null totals; totals, route_length_m or as_built_length_m are not numbers or are infinite.
    FrameError: a project of PF is not in projects.project; route_length_m is zero or less; start is not a date or has a time zone; RC has two rows for a project or a negative as_built_length_m.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import per_metre
    >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "period": ["2025-01", "2025-02"], "total_kgco2e": [100.0, 50.0]})
    >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [1000.0], "start": ["2024-05-01"], "status": ["active"]})
    >>> out = per_metre(PF, P, context=ctx).value
    >>> out[["prj_key", "kgco2e_per_m", "partial_history", "active_to_date"]].values.tolist()
    [['PRJ-900001', 0.15, False, True]]

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

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.window_start`
