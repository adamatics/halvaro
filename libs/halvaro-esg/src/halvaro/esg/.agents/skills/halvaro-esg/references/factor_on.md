# factor_on

Module `halvaro.esg.factors`. Import: `from halvaro.esg import factor_on`.

```python
factor_on(factors: pd.DataFrame, category: str, region: str, on: DateLike, *, carrier: str | None = None, method: str | None = None, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the one emission factor row of a family that is valid on a date.

The factor row of a family valid on a date (or the first day of a 'YYYY-MM' period): valid_from <= date <= valid_to, null valid_to open (valid_to is inclusive). `value` is the row as a one row frame. The family is category, region, and carrier and method where the family has them (None matches a null). No row, or two rows, valid on the date raises FrameError: a family has no gap and no overlap. Every factor row is synthetic with a VERIFY note, so the status is VERIFY+synthetic, never verified.

Args:
    factors: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to, factor_set, synthetic and verify_note.
    category: The factor category, for example gas.
    region: The factor region.
    on: The day as a date, a Timestamp or ISO text, or a period 'YYYY-MM' (its first day); numbers and time zones are refused.
    carrier: The carrier of the family, or None for a family without carrier (matches a null).
    method: The method of the family, or None for a family without method (matches a null).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Provenance (an Envelope with factor_sets and verify_facts) whose value is the one factor row as a one row frame with all columns of factors.

Raises:
    FrameError: factors lacks a column, on is a number, not a date or has a time zone, or valid_from or valid_to holds numbers, values that are not dates or a time zone.
    FrameError: no factor of the family is valid on the date, or more than one is (the message lists their efac_key).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import factor_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
    ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
    ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
    >>> r = factor_on(F, "gas", "DE", "2025-06", carrier="natural_gas", context=ctx)
    >>> r.value[["efac_key", "kgco2e_per_unit"]].to_dict("records")
    [{'efac_key': 'EF-900001', 'kgco2e_per_unit': 0.2}]
    >>> r.status
    'VERIFY+synthetic'

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
