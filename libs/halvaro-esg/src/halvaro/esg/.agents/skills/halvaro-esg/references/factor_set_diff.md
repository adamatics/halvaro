# factor_set_diff

Module `halvaro.esg.factors`. Import: `from halvaro.esg import factor_set_diff`.

```python
factor_set_diff(factors: pd.DataFrame, old_set: str | Sequence[str], new_set: str | Sequence[str], *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need to compare the emission factors of two factor sets family by family.

Per family the old value, the new value and the percent change (two decimals) between two factor sets. A set is a name or a list of names (for example ['FS-2031', 'FS-2029-31']); a family may not appear twice in one side. change_percent is null when a side is missing or the old value is 0; side is 'both', 'old_only' or 'new_only'.

Args:
    factors: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to, factor_set, synthetic and verify_note.
    old_set: The old factor set, a name or a list of names.
    new_set: The new factor set, a name or a list of names.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Provenance whose value is a frame with the columns family, category, carrier, region, method, old_value, new_value, change_percent and side, sorted by family.

Raises:
    FrameError: factors lacks a column, a set is not a name or a list of names, or a set is not in the table.
    FrameError: one side holds more than one row for the same family.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import factor_set_diff
    >>> ctx = Context(stage="month12", role="analyst")
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
    ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
    ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
    >>> d = factor_set_diff(F, "FS-A", "FS-B", context=ctx)
    >>> d.value[["old_value", "new_value", "change_percent", "side"]].to_dict("records")
    [{'old_value': 0.2, 'new_value': 0.19, 'change_percent': -5.0, 'side': 'both'}]

## Source columns

- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
- `energy-esg.emission_factor.factor_set`
- `energy-esg.emission_factor.synthetic`
- `energy-esg.emission_factor.verify_note`
