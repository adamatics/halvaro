# current_basis

Module `halvaro.esg.lines`. Import: `from halvaro.esg import current_basis`.

```python
current_basis(L: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the emission lines without the superseded originals, so that a total counts every restatement once.

The lines without the superseded originals (is_superseded false): restated lines stand, originals that were replaced do not. A total over this frame counts every change once. The frame is checked first: a restated line must name its original and the original must be in the frame, a line flagged is_superseded must be replaced by a restated line, and an original that a restated line replaces must be flagged is_superseded (T3).

Args:
    L: The energy-esg.emission_line table, unfiltered, with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The lines of L with is_superseded false, with all columns of L, in the order of L and a fresh index.

Raises:
    FrameError: a column is missing, is_superseded has nulls, or the line key (le_key, period, scope, category, line_no) is used twice.
    FrameError: a restated line (restated_from_period set) has no supersedes_line_no, or replaces a line that is not in the frame.
    FrameError: a line is flagged is_superseded but no restated line replaces it, or an original is replaced by a restated line but is not flagged is_superseded.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import current_basis
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> current_basis(L, context=ctx)["line_no"].tolist()
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
