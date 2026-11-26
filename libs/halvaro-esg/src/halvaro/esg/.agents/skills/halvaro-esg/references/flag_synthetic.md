# flag_synthetic

Module `halvaro.esg.factors`. Import: `from halvaro.esg import flag_synthetic`.

```python
flag_synthetic(factors: pd.DataFrame, *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need to know whether the emission factor rows are synthetic and carry a VERIFY note.

The synthetic flag and the VERIFY note of the factor rows, as the status of the result: VERIFY+synthetic when every row is synthetic and carries a VERIFY note, never 'ok'. `value` has one row per factor row (efac_key, synthetic, verify_note); a row that is not synthetic or has no VERIFY note is listed in the warnings.

Args:
    factors: The energy-esg.emission_factor table with the columns efac_key, synthetic, verify_note and factor_set.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Provenance whose value is a frame with the columns efac_key, synthetic and verify_note, one row per factor row, and whose status is VERIFY+synthetic when all rows are synthetic with a VERIFY note.

Raises:
    FrameError: factors is not a DataFrame or lacks one of efac_key, synthetic, verify_note and factor_set.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import flag_synthetic
    >>> ctx = Context(stage="month12", role="analyst")
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
    ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
    ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
    >>> s = flag_synthetic(F, context=ctx)
    >>> s.status
    'VERIFY+synthetic'
    >>> s.value["efac_key"].tolist()
    ['EF-900001', 'EF-900002']

## Source columns

- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.synthetic`
- `energy-esg.emission_factor.verify_note`
- `energy-esg.emission_factor.factor_set`
