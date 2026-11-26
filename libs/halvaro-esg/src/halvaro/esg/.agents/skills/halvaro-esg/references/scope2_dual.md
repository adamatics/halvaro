# scope2_dual

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import scope2_dual`.

```python
scope2_dual(L: pd.DataFrame, year: int | None = None, basis: str = 'current', *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need scope 2 by carrier category with the location based and the market based result side by side.

Scope 2 by carrier category (purchased_electricity, purchased_heat) with both methods side by side and never summed.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    year: The whole year, like 2025; the year before the year of world.now when None.
    basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with le_key, year, category, location_kg, market_kg and market_vs_location_percent (market over location less 100, null without location), sorted by le_key and category.

Raises:
    FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import scope2_dual
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 20.0, False, None)], columns=cols)
    >>> scope2_dual(L, 2025, context=ctx).value.to_dict("records")
    [{'le_key': 'LE-900001', 'year': 2025, 'category': 'purchased_electricity', 'location_kg': 50.0, 'market_kg': 20.0, 'market_vs_location_percent': -60.0}]

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
