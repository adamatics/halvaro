# family_key

Module `halvaro.esg.factors`. Import: `from halvaro.esg import family_key`.

```python
family_key(factors: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the family of each emission factor row as one text key.

The family of each factor row as text 'category|carrier|region|method' (a null part is '-'), with the index of the frame. Rows of one family differ by validity and factor set only.

Args:
    factors: The energy-esg.emission_factor table with the columns category, carrier, region and method.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Series named family_key with the text key of each row and the index of factors.

Raises:
    FrameError: factors is not a DataFrame or lacks one of category, carrier, region and method.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import family_key
    >>> ctx = Context(stage="month12", role="analyst")
    >>> F = pd.DataFrame({
    ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
    ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
    ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
    ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
    >>> family_key(F, context=ctx).tolist()
    ['gas|natural_gas|DE|-', 'gas|natural_gas|DE|-']

## Source columns

- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
