# restatement_bridge

Module `halvaro.esg.lines`. Import: `from halvaro.esg import restatement_bridge`.

```python
restatement_bridge(L: pd.DataFrame, F: pd.DataFrame, year: int, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the change from first booked to restated emissions of one year, by scope, category and factor family.

From first booked to restated for the periods of one year, by scope, category and factor family: kg of the replaced originals, kg of the restated lines, the change and its percent. Only restated pairs count (see restatement_pairs), so a year without a restatement gives an empty frame. delta_percent is null when kg_first_booked is not above 0.

Args:
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no and is_superseded.
    F: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region and method (one row per efac_key).
    year: The year of the periods to bridge, a whole number such as 2025.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns scope, category, family, n_lines, kg_first_booked, kg_restated, delta_kg and delta_percent (two decimals), sorted by scope, category and family.

Raises:
    FrameError: year is not a whole number, or F lacks a column or has more than one row for an efac_key.
    FrameError: the lines fail the checks of restatement_pairs (missing columns, a restated line without original, chains, a changed quantity or method, an unchanged factor).
    FrameError: a factor of the lines is not in F, or a restatement changes the factor family, not only the factor.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import restatement_bridge
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None]})
    >>> bridge = restatement_bridge(L, F, 2025, context=ctx)
    >>> bridge[["family", "n_lines", "kg_first_booked", "kg_restated", "delta_kg", "delta_percent"]].to_dict("records")
    [{'family': 'gas|natural_gas|DE|-', 'n_lines': 1, 'kg_first_booked': 200.0, 'kg_restated': 190.0, 'delta_kg': -10.0, 'delta_percent': -5.0}]

## Source columns

- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
- `energy-esg.emission_line.supersedes_line_no`
- `energy-esg.emission_line.quantity`
- `energy-esg.emission_line.efac_key`
- `energy-esg.emission_line.method`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
