# validate_lines

Module `halvaro.esg.lines`. Import: `from halvaro.esg import validate_lines`.

```python
validate_lines(L: pd.DataFrame, F: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the rule violations of the emission lines, such as a wrong kg value, an unknown or invalid factor or a wrong method.

Violations (table, key, rule, detail) of the emission lines: duplicate_key, null_value, unknown_factor, value (kgco2e differs from quantity times the factor by more than 0.002 kg), period (not a month like 2025-03), link (a restated line has no supersedes_line_no), category (ghg_category does not belong to the scope: 1, 2 or 3.x), factor_validity (the factor is not valid on the first day of the period, unless the line is restated), restated_factor (a restated line has a factor that was already valid in its period, so nothing was restated), method (scope 2 has location or market, other scopes none) and ref_prefix (the reference type decides the key prefix: MTR, PRJ, SITE, SUP or LE). The key of a violation is 'le_key period scope category line_no'.

Args:
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no, is_superseded, ref_type and ref_key.
    F: The energy-esg.emission_factor table with the columns efac_key, kgco2e_per_unit, valid_from and valid_to (one row per efac_key).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns table, key, rule and detail, one row per violation; empty when the lines pass.

Raises:
    FrameError: L or F lacks a required column, or F has more than one row for an efac_key.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import validate_lines
    >>> ctx = Context(stage="month12", role="analyst")
    >>> L = pd.DataFrame({
    ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
    ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
    ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
    ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
    ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
    ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
    >>> L["ref_type"], L["ref_key"] = "SITE", "SITE-900001"
    >>> validate_lines(L, F, context=ctx).shape[0]
    0
    >>> bad = L.assign(kgco2e=[200.0, 100.0])
    >>> validate_lines(bad, F, context=ctx)[["key", "rule"]].to_dict("records")
    [{'key': 'LE-900001 2025-03 1 gas 2', 'rule': 'value'}]

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
- `energy-esg.emission_line.ref_type`
- `energy-esg.emission_line.ref_key`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
