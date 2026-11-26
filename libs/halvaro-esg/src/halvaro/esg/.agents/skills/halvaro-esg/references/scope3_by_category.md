# scope3_by_category

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import scope3_by_category`.

```python
scope3_by_category(L: pd.DataFrame, year: int | None = None, basis: str = 'current', *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need scope 3 by ghg_category and line category for one year and basis.

The sum is the scope3 of scope_totals.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    year: The whole year, like 2025; the year before the year of world.now when None.
    basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with ghg_category, category, n_lines and kgco2e (three decimals), sorted by the order of the 15 categories and then by category.

Raises:
    FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import scope3_by_category
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None),
    ...     ("LE-900001", "2025-02", 3, "purchased_goods", 2, None, "3.1", 10.0, False, None),
    ...     ("LE-900001", "2025-02", 3, "business_travel", 1, None, "3.6", 5.0, False, None)], columns=cols)
    >>> r = scope3_by_category(L, 2025, context=ctx)
    >>> r.value[["ghg_category", "category", "n_lines", "kgco2e"]].values.tolist()
    [['3.1', 'purchased_goods', 2, 40.0], ['3.6', 'business_travel', 1, 5.0]]

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
