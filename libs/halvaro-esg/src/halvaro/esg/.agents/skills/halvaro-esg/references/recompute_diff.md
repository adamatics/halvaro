# recompute_diff

Module `halvaro.esg.recompute`. Import: `from halvaro.esg import recompute_diff`.

```python
recompute_diff(lines: pd.DataFrame, expected: pd.DataFrame, *, quantity_tolerance: float = 0.01, kg_tolerance_per_line: float = 0.002, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to compare stored emission lines with the expected lines and list every key that does not tie.

Joins stored lines to expected lines by (ref_key, period, scope, ghg_category, method, category, subcategory), summing the lines of a key (scope 1 is split over projects), and reports the mismatches. Null key parts match each other (as text '-');
a null ref_key, period or scope raises. The kg tolerance is kg_tolerance_per_line times the number of lines of the key (each line is rounded to 0.001); the quantity tolerance is 0.01 (the
waste tonnes and the energy quantities are stored with two decimals at most). When both frames carry `unit` a key with another unit is reported as unit. The factor row (efac_key) is not compared: a restated
line of an unchanged factor keeps the old row, so only the kg decides. PROPOSED: the tolerances. Only mismatches are returned; the frame is empty when all keys tie.

Args:
    lines: The energy-esg.emission_line table (or any frame of stored lines) with the columns ref_key, period, scope, ghg_category, method, category, subcategory, quantity and kgco2e (and unit, when it is to be compared).
    expected: The output of one of the expected_* functions (or their concatenation) with the columns ref_key, period, scope, ghg_category, method, category, subcategory, quantity and expected_kg (and unit, when it is to be compared).
    quantity_tolerance: The largest difference in quantity of a key that still ties (PROPOSED, default 0.01); a number of zero or more.
    kg_tolerance_per_line: The difference in kg that each stored line of a key may add before the key no longer ties (PROPOSED, default 0.002); a number of zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns ref_key, period, scope, ghg_category, method, category, subcategory (the key), n_lines, quantity_lines, quantity_expected, kg_lines, kg_expected and status (missing_line, missing_expected, quantity, kg or unit; ok keys are not listed), sorted by the key; empty when all keys tie.

Raises:
    FrameError: lines or expected is not a frame or lacks a needed column (kgco2e in lines, expected_kg in expected).
    FrameError: a tolerance is not a number of zero or more (a boolean, infinite or negative value raises).
    FrameError: a ref_key, period or scope is null in either frame; scope is not a whole number.
    FrameError: quantity, kgco2e or expected_kg holds text, booleans or nulls.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import recompute_diff
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["ref_key", "period", "scope", "ghg_category", "method", "category", "subcategory", "quantity"]
    >>> L = pd.DataFrame([("PRJ-900001", "2031-03", 3, "3.1", None, "purchased_services", None, 500.0, 50.0)], columns=[*cols, "kgco2e"])
    >>> E = pd.DataFrame([("PRJ-900001", "2031-03", 3, "3.1", None, "purchased_services", None, 500.0, 55.0)], columns=[*cols, "expected_kg"])
    >>> bad = recompute_diff(L, E, context=ctx)
    >>> bad[["status", "n_lines", "kg_lines", "kg_expected"]].values.tolist()
    [['kg', 1, 50.0, 55.0]]

## Source columns

- `energy-esg.emission_line.ref_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.method`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.subcategory`
- `energy-esg.emission_line.quantity`
- `energy-esg.emission_line.kgco2e`
