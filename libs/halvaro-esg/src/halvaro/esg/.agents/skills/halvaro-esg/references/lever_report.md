# lever_report

Module `halvaro.esg.levers`. Import: `from halvaro.esg import lever_report`.

```python
lever_report(pm: pd.DataFrame, levers: pd.DataFrame, limit: float, *, top: int = 2, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the best levers of one project, ranked by saving per route metre, against a customer limit per metre.

The `top` (2) levers with the largest saving per route metre for one project against a customer limit. Only levers with a positive saving are ranked; ranking is on the unrounded saving. Savings of levers are not added up: two levers may act on the same kilograms.

Args:
    pm: One row of per_metre with prj_key, route_length_m and kgco2e_per_m (or per_m_exact, which is used when present).
    levers: A frame with lever (name) and saved_kgco2e.
    limit: The customer limit in kg CO2e per route metre; a positive finite number.
    top: How many levers to return, a whole number of one or more (default 2).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns rank, lever, saved_kgco2e, saved_per_m, gap_per_m (per metre footprint less limit, zero when under), share_of_gap_closed (null when there is no gap), per_m_after and below_limit_after (at or below the limit; a footprint exactly at the limit is not above it), best lever first, ties in the order of the lever name. Empty when no lever has a positive saving.

Raises:
    FrameError: pm lacks prj_key, route_length_m or the per metre column, or levers lacks lever or saved_kgco2e.
    FrameError: pm does not have exactly one row, the project has no route length above zero, or it has no finite footprint per metre.
    FrameError: limit is not a positive finite number, or top is not a whole number of one or more.
    FrameError: levers names a lever twice or has a lever without a finite saving.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import lever_report
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pm = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0], "kgco2e_per_m": [10.0]})
    >>> levers = pd.DataFrame({"lever": ["hvo", "steel", "worse"], "saved_kgco2e": [200.0, 100.0, -5.0]})
    >>> r = lever_report(pm, levers, 9.0, context=ctx)
    >>> r["lever"].tolist()
    ['hvo', 'steel']
    >>> r["saved_per_m"].tolist()
    [2.0, 1.0]
    >>> r["below_limit_after"].tolist()
    [True, True]

## Source columns

- `energy-esg.project_footprint.prj_key`
- `projects.project.route_length_m`
