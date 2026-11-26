# project_scope_split

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import project_scope_split`.

```python
project_scope_split(L: pd.DataFrame, year: int, basis: str = 'current', *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the kgco2e of each project in one year split by scope 1, 3.1, 3.3 and 3.4.

The sum over projects of the total equals the project footprints of that year. Lines without a project are not counted.

Args:
    L: The energy-esg.emission_line table, with the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period.
    year: The whole year to split, for example 2025.
    basis: current (superseded originals left out, the default) or first_booked (restated lines left out).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns prj_key, scope1, scope3_1, scope3_3, scope3_4 and total_kgco2e (three decimals), sorted by prj_key.

Raises:
    FrameError: year is not a whole number (a boolean is refused).
    FrameError: L is not a DataFrame or lacks one of the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period; is_superseded has nulls; two lines share le_key, period, scope, category and line_no; basis is not current or first_booked.
    FrameError: a project line has a null kgco2e, scope or period; kgco2e or scope holds text, booleans or infinite values.
    FrameError: a period does not start with a year; a project line of the year is not in scope 1, 3.1, 3.3 or 3.4.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import project_scope_split
    >>> L = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "le_key": ["LE-900001"] * 3, "period": ["2025-01"] * 3, "scope": [1, 3, 3],
    ...                   "category": ["fuel", "purchased_goods", "upstream_transport"], "line_no": [1, 2, 3],
    ...                   "ghg_category": ["1", "3.1", "3.4"], "kgco2e": [10.0, 20.0, 5.0],
    ...                   "is_superseded": [False] * 3, "restated_from_period": [None] * 3})
    >>> out = project_scope_split(L, 2025, context=ctx)
    >>> out[["prj_key", "scope1", "scope3_1", "scope3_4", "total_kgco2e"]].values.tolist()
    [['PRJ-900001', 10.0, 20.0, 5.0, 35.0]]

## Source columns

- `energy-esg.emission_line.prj_key`
- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
