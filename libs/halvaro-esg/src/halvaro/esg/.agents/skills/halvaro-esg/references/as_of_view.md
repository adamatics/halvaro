# as_of_view

Module `halvaro.esg.lines`. Import: `from halvaro.esg import as_of_view`.

```python
as_of_view(L: pd.DataFrame, as_of: str, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the emission lines that were visible at a booking period, whatever is_superseded says today.

The lines visible at a booking period (text 'YYYY-MM'), from restated_from_period and the replacement links, ignoring is_superseded: lines of periods up to as_of, restated lines booked up to as_of, and originals that no restated line booked up to as_of has replaced. is_superseded is state as of now (T3) and is not used.

Args:
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
    as_of: The booking period as text 'YYYY-MM', for example 2025-12.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The visible lines of L with all columns of L, in the order of L and a fresh index.

Raises:
    FrameError: as_of is not a period text like 2025-12.
    FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
    FrameError: a line restated up to as_of has no supersedes_line_no.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import as_of_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> as_of_view(L, "2025-12", context=ctx)["line_no"].tolist()
    [1]
    >>> as_of_view(L, "2026-01", context=ctx)["line_no"].tolist()
    [2]

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
