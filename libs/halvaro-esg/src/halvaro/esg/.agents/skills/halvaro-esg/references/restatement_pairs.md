# restatement_pairs

Module `halvaro.esg.lines`. Import: `from halvaro.esg import restatement_pairs`.

```python
restatement_pairs(L: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need each restated emission line next to the original it replaces, with the change in kg.

Each restated line next to its original, one to one on (le_key, period, scope, category) and supersedes_line_no = line_no. A restated line without its original, an original replaced twice, a different quantity, key or method, or an unchanged factor raises FrameError. delta_kg is kg_restated minus kg_original, rounded to 3 decimals.

Args:
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no and is_superseded.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with one row per restated line and the columns le_key, period, scope, category, method, line_no_original, line_no_restated, restated_from_period, quantity_original, quantity_restated, efac_original, efac_restated, kg_original, kg_restated and delta_kg, sorted by le_key, period, scope, category and line_no_original.

Raises:
    FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
    FrameError: a restated line has no supersedes_line_no, or no original line.
    FrameError: an original line is replaced by more than one restated line, or a restated line replaces another restated line (chains are not supported).
    FrameError: a restated line or its original has no quantity or no efac_key, differs from its original in quantity (more than 1e-6) or method, or has the same factor as its original.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import restatement_pairs
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> pairs = restatement_pairs(L, context=ctx)
    >>> pairs[["line_no_original", "line_no_restated", "delta_kg"]].to_dict("records")
    [{'line_no_original': 1, 'line_no_restated': 2, 'delta_kg': -10.0}]

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
