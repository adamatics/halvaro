# winter_ratio

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import winter_ratio`.

```python
winter_ratio(L: pd.DataFrame, prev: Sequence[str] = ('2024-12', '2025-02'), now: Sequence[str] = ('2025-12', '2026-02'), *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need Scope 1 of a winter window against the same window a year earlier, on the current and the first booked basis.

Scope 1 of a winter window over the same window a year earlier, on both bases. Windows are (first, last) periods, inclusive; the defaults are December to February. The two bases differ because
a restatement changes the earlier window only, so the ratio on the current basis can differ from the ratio as first booked. A longer window (November to March) gives another ratio.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    prev: The (first, last) periods of the earlier window, inclusive (default ('2024-12', '2025-02')).
    now: The (first, last) periods of the later window, inclusive, with as many months as prev (default ('2025-12', '2026-02')).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with basis, scope1_prev_kg, scope1_now_kg and ratio (three decimals; null without scope 1 in the earlier window), one row for current and one for first_booked.

Raises:
    FrameError: a window is not a (first, last) pair of period text in order, the two windows have a different number of months, L lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, a restated line has no supersedes_line_no or its original is not flagged is_superseded, or a window has scope 1 lines for fewer months than it spans.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import winter_ratio
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2024-12", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
    ...     ("LE-900001", "2025-12", 1, "stationary_combustion", 1, None, None, 120.0, False, None)], columns=cols)
    >>> r = winter_ratio(L, prev=("2024-12", "2024-12"), now=("2025-12", "2025-12"), context=ctx)
    >>> r.value[["basis", "scope1_prev_kg", "scope1_now_kg", "ratio"]].values.tolist()
    [['current', 100.0, 120.0, 1.2], ['first_booked', 100.0, 120.0, 1.2]]

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
