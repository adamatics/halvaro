# target_progress

Module `halvaro.esg.audit_targets`. Import: `from halvaro.esg import target_progress`.

```python
target_progress(T: pd.DataFrame, L: pd.DataFrame, as_of: DateLike, *, year: int | None = None, tolerance: float = 0.005, basis: str = 'current', context: halvaro.core.access.Context) -> Provenance
```

Use this when you need each absolute emission target compared with its glide path and with the actual scope total of a year.

Each absolute target against its glide path. `baseline_basis` is current, first_booked or neither: which line basis reproduces the stored baseline within `tolerance` of itself (0.5 percent PROPOSED). `actual` is the scope total of `year` (default the last full year before the day) on the current basis, `glide_value` the straight line from the stored baseline to the target value and `gap` the actual less the glide. A target whose scope is not a line scope (the per metre intensity target) is listed with null actual and glide only: it needs the per metre median, not the lines. The baseline is never changed. `basis_mismatch` is true when `baseline_basis` names a line basis other than the one of the actual; a baseline that matches both line bases is read as current, so the mismatch is then true only for the first_booked basis, and with neither match it is false. The current basis includes restatements booked after `as_of`, and the baseline year and the actual year may sit on different factor sets (T8): the result has the status VERIFY+synthetic and says so. `months` counts the periods with lines of the target's own scope and `on_track` is null when that is under 12, when the year is not over on the day, or when the scope has no lines. `actual_basis` names the line basis of the actual and `basis_mismatch` is true when the stored baseline matches the other basis.

Args:
    T: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, baseline_value and target_value.
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    as_of: The day of the progress report (a date, a Timestamp or ISO text).
    year: The whole year of the actual; the year before the year of `as_of` when None.
    tolerance: The share of the stored baseline within which a basis reproduces it, zero or more (default 0.005, PROPOSED).
    basis: The line basis of the actual, "current" or "first_booked" (default "current").
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns target_no, scope, baseline_year, target_year, baseline_value, baseline_current, baseline_first_booked, baseline_basis, year, actual, glide_value, gap, on_track, months, actual_basis and basis_mismatch, one row per target sorted by target_no, values to three decimals.

Raises:
    FrameError: T lacks target_no, scope, baseline_year, target_year, baseline_value or target_value, has no rows, has a repeated target_no, or has a null in a baseline or target value or year.
    FrameError: basis is not current or first_booked, year is not a whole year, tolerance is not a number of zero or more, or as_of is not a date without a time zone.
    FrameError: a target has a scope that is neither a line scope (1, 2_location, 2_market, 3) nor the intensity scope, or ends before its baseline year.
    FrameError: the line totals fail their checks (see scope_totals).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import target_progress
    >>> ctx = Context(stage="month12", role="analyst")
    >>> T = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2023], "target_year": [2027],
    ...                   "baseline_value": [1000.0], "target_value": [600.0]})
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2023-01", 1, "stationary_combustion", 1, None, None, 1000.0, False, None),
    ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 700.0, False, None)], columns=cols)
    >>> r = target_progress(T, L, "2026-03-01", context=ctx)
    >>> r.value[["target_no", "year", "baseline_basis", "actual", "glide_value", "gap", "months"]].to_dict("records")
    [{'target_no': 1, 'year': 2025, 'baseline_basis': 'current', 'actual': 700.0, 'glide_value': 800.0, 'gap': -100.0, 'months': 1}]
    >>> r.value["on_track"].isna().tolist()
    [True]

## Source columns

- `energy-esg.target.target_no`
- `energy-esg.target.scope`
- `energy-esg.target.baseline_year`
- `energy-esg.target.target_year`
- `energy-esg.target.baseline_value`
- `energy-esg.target.target_value`
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
