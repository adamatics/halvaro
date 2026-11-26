# product_basis_share

Module `halvaro.esg.factors`. Import: `from halvaro.esg import product_basis_share`.

```python
product_basis_share(factors: pd.DataFrame, *, context: halvaro.core.access.Context) -> float
```

Use this when you need the counted share of the product footprints for purchased goods.

The counted share of the product footprints: kgco2e_per_unit of the one purchased_goods_product_footprint row of the table. The share is read from the table only, never from the yaml: the table is the truth. It is computed, and it must lie in (0, 1].

Args:
    factors: The energy-esg.emission_factor table with the columns category and kgco2e_per_unit.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The share as a float in (0, 1].

Raises:
    FrameError: factors lacks category or kgco2e_per_unit, has zero or several purchased_goods_product_footprint rows, or the share is outside (0, 1].
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import product_basis_share
    >>> ctx = Context(stage="month12", role="analyst")
    >>> F = pd.DataFrame({"category": ["gas", "purchased_goods_product_footprint"], "kgco2e_per_unit": [0.2, 0.25]})
    >>> product_basis_share(F, context=ctx)
    0.25

## Source columns

- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.kgco2e_per_unit`
