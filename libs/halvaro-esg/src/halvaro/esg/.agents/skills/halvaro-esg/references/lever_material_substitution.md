# lever_material_substitution

Module `halvaro.esg.levers`. Import: `from halvaro.esg import lever_material_substitution`.

```python
lever_material_substitution(G: pd.DataFrame, item: pd.DataFrame, epd: pd.DataFrame, cand: pd.DataFrame | dict[str, Any], factors: pd.DataFrame, *, context: halvaro.core.access.Context) -> object
```

Use this when you need the kilograms CO2e saved by replacing bought items with candidate items of a lower footprint.

Kilograms CO2e saved when the bought quantities `G` (itm_key, quantity in the unit of the item) are replaced by the candidate items `cand` (a dict or frame itm_key -> cand_itm_key), times the counted share of the product footprints (the one row of the factor table, product_basis_share). The candidate must be an item of the same category and unit, else FrameError. The same item gives zero. A candidate with a higher footprint gives a negative saving and `worse` true. Quantities of the same item are summed; items of G without a candidate are left out. The estimate has the status VERIFY+synthetic and warns that the counted share is one row of the factor table and that equivalence of the candidate is not verified.

Args:
    G: The bought quantities with the columns itm_key and quantity (in the unit of the item).
    item: The inventory.item table with the columns itm_key, category, unit and footprint_kgco2e_per_unit.
    epd: The energy-esg.item_epd table with the columns itm_key, source and verification (valid_from, when present, orders the rows of an item).
    cand: The candidate map, a dict itm_key -> cand_itm_key or a frame with the columns itm_key and cand_itm_key.
    factors: The energy-esg.emission_factor table with category and kgco2e_per_unit, from which product_basis_share reads the counted share.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns itm_key, cand_itm_key, quantity, unit, category, footprint_per_unit, cand_footprint_per_unit, counted_share, saved_kgco2e (three decimals), worse, cand_epd_verified (the latest EPD row of the candidate carries a verification text; the text itself is not judged) and equivalence ('unverified': whether the candidate does the same job is not in the data), sorted by itm_key.

Raises:
    FrameError: G, item, epd or a candidate frame lacks a column, or item has more than one row for an item, or the candidate map names an item twice.
    FrameError: the bought quantities are not finite numbers of zero or more, or a row has no itm_key.
    FrameError: item does not hold an item or a candidate of the map, a candidate differs in category or unit from the item it replaces, or an item or its candidate has no footprint per unit.
    FrameError: the factor table has no usable counted share (see product_basis_share).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import lever_material_substitution
    >>> ctx = Context(stage="month12", role="analyst")
    >>> G = pd.DataFrame({"itm_key": ["ITM-900001"], "quantity": [10.0]})
    >>> item = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "category": ["steel", "steel"], "unit": ["kg", "kg"], "footprint_kgco2e_per_unit": [2.0, 1.0]})
    >>> epd = pd.DataFrame({"itm_key": ["ITM-900002"], "source": ["EPD"], "verification": ["checked"]})
    >>> factors = pd.DataFrame({"category": ["purchased_goods_product_footprint"], "kgco2e_per_unit": [0.5]})
    >>> r = lever_material_substitution(G, item, epd, {"ITM-900001": "ITM-900002"}, factors, context=ctx)
    >>> r.value[["itm_key", "cand_itm_key", "saved_kgco2e", "worse", "cand_epd_verified"]].to_dict("records")
    [{'itm_key': 'ITM-900001', 'cand_itm_key': 'ITM-900002', 'saved_kgco2e': 5.0, 'worse': False, 'cand_epd_verified': True}]

## Source columns

- `inventory.item.itm_key`
- `inventory.item.category`
- `inventory.item.unit`
- `inventory.item.footprint_kgco2e_per_unit`
- `energy-esg.item_epd.itm_key`
- `energy-esg.item_epd.source`
- `energy-esg.item_epd.verification`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.kgco2e_per_unit`
