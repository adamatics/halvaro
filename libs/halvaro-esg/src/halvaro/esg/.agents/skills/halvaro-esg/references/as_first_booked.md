# as_first_booked

Module `halvaro.esg.lines`. Import: `from halvaro.esg import as_first_booked`.

```python
as_first_booked(L: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the emission lines as they were first booked, before any restatement.

The lines without the restated lines (restated_from_period null): the figures as they were first booked, replaced originals included.

Args:
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, is_superseded and restated_from_period.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The lines of L with restated_from_period null, with all columns of L, in the order of L and a fresh index.

Raises:
    FrameError: a column is missing, is_superseded has nulls, or the line key (le_key, period, scope, category, line_no) is used twice.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import as_first_booked
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> as_first_booked(L, context=ctx)["line_no"].tolist()
    [1]

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
