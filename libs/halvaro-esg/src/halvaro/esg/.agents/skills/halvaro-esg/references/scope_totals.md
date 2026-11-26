# scope_totals

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import scope_totals`.

```python
scope_totals(L: pd.DataFrame, year: int | None = None, basis: str = 'current', le: str | None = None, *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the scope 1, scope 2 and scope 3 totals of one year on one basis, per entity, for one entity or for all.

Scope 1, scope 2 by location and by market, scope 3 (and each ghg_category) and the two totals of one year on one basis, per entity or for one entity (le) or all (le_key 'ALL'). The value
columns are le_key, year, basis, months (distinct periods with lines), scope1, scope2_location, scope2_market, scope3, scope3_<category> for each category present, total_location_based
(scope 1 + scope 2 location + scope 3) and total_market_based. kgco2e to three decimals. The year defaults to the year before the year of world.now; basis is 'current' or 'first_booked'.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    year: The whole year to total, like 2025; the year before the year of world.now when None.
    basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
    le: One le_key to report only that entity, or None or 'ALL' for every entity plus an 'ALL' row.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns above, one row per entity sorted by le_key and then the 'ALL' row, in kgco2e.

Raises:
    FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, the entity le has no lines in the year, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import scope_totals
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 20.0, False, None),
    ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
    >>> r = scope_totals(L, 2025, context=ctx)
    >>> r.value["le_key"].tolist()
    ['LE-900001', 'ALL']
    >>> r.value.loc[0, ["months", "scope1", "scope2_location", "scope2_market", "scope3"]].astype(float).tolist()
    [2.0, 100.0, 50.0, 20.0, 30.0]
    >>> r.value.loc[0, ["total_location_based", "total_market_based"]].astype(float).tolist()
    [180.0, 150.0]

## Source columns

- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.method`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
