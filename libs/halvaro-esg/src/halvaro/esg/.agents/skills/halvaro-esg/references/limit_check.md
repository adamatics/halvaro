# limit_check

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import limit_check`.

```python
limit_check(pm: pd.DataFrame, cs: pd.DataFrame, limit: float, *, context: halvaro.core.access.Context) -> LimitCheck
```

Use this when you need to compare the kg CO2e per metre of a comparable set of projects with a customer limit.

The median, the gap, the number of projects above and below and the headroom of the kg per metre of the comparable set `cs` against the limit (kg per metre). Projects of the set without a value are not counted and their number is reported (n_null).
A project of the set that is not in pm counts as null. A value exactly at the limit (compared unrounded when pm carries per_m_exact) is neither above nor below; it is counted in n_at.

Args:
    pm: The value of per_metre, with the columns prj_key and kgco2e_per_m (and per_m_exact, used when present).
    cs: A delivery comparable_set frame, with the column prj_key.
    limit: The limit in kg per metre, a positive finite int or float (not a boolean or a float32).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A LimitCheck with n (values), n_null (projects without a value), median, limit, gap (median less limit), n_above, n_below, headroom_percent (limit less median over limit; negative when the median is above the limit) and n_at (values equal to the limit).
    A count that puts a value at the limit with the values below it is n_below + n_at here.

Raises:
    FrameError: pm lacks prj_key or kgco2e_per_m, or cs lacks prj_key; a prj_key is null or duplicated in either frame.
    FrameError: limit is not an int or float (a boolean or float32 is refused), is too large, is not finite or is zero or less; the per metre values are not numbers; no project of the comparable set has a value per metre.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import limit_check
    >>> pm = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "kgco2e_per_m": [0.5, 1.5, 3.0]})
    >>> cs = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003", "PRJ-900004"]})
    >>> r = limit_check(pm, cs, 2.0, context=ctx)
    >>> (r.n, r.n_null, r.median, r.n_above, r.n_below, r.headroom_percent)
    (3, 1, 1.5, 1, 2, 25.0)

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
