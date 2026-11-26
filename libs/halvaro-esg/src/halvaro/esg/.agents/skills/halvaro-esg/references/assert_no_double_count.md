# assert_no_double_count

Module `halvaro.esg.lines`. Import: `from halvaro.esg import assert_no_double_count`.

```python
assert_no_double_count(L: pd.DataFrame, *, context: halvaro.core.access.Context) -> bool
```

Use this when you need to confirm that a frame of emission lines holds no original together with the restated line that replaces it, before you total it.

Raises FrameError when the frame holds both an original line and the restated line that replaces it (a total over it counts the change twice, T1). Returns True otherwise. Frames that are the current basis, the lines as first booked or an as-of view pass; the unfiltered table does not.

Args:
    L: The energy-esg.emission_line table, or a basis taken from it, with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    True when no original is in the frame together with the restated line that replaces it.

Raises:
    FrameError: an original line is in the frame together with the restated line that replaces it (the message names the years).
    FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
    FrameError: a restated line has no supersedes_line_no.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import assert_no_double_count
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> assert_no_double_count(L[L["line_no"] == 2], context=ctx)
    True

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
