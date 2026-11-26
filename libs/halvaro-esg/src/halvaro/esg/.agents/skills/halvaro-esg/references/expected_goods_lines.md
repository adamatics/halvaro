# expected_goods_lines

Module `halvaro.esg.recompute`. Import: `from halvaro.esg import expected_goods_lines`.

```python
expected_goods_lines(goods_receipt: pd.DataFrame, po_line: pd.DataFrame, purchase_order: pd.DataFrame, item: pd.DataFrame, f: pd.DataFrame, *, exclude_categories: tuple[str, ...] = ('fuel_fleet',), periods: Iterable[str] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the scope 3.1 goods emission lines that the goods accepted at receipt per supplier, month and item category should produce.

Scope 3.1 goods lines: the gross product footprint accepted at goods receipt (accepted quantity times `item.footprint_kgco2e_per_unit`, items with a footprint outside `exclude_categories`,
PROPOSED fuel_fleet) per supplier, month of the receipt and item category, times the counted share (the product footprint factor row, category purchased_goods_product_footprint, region ALL, valid on the
first of the month). Same columns as expected_lines_s123: ref_key is the supplier, subcategory the item category, quantity the gross footprint in `kgCO2e gross product footprint`, expected_kg quantity times factor.
Projects are not in the key (recompute_diff sums the project lines of a key). The spend based lines of excluded fuel supplies (unit DKK) are not rebuilt here. `periods` limits the months (a set of YYYY-MM).

Args:
    goods_receipt: The procurement.goods_receipt table with the columns po_key, line_no, receipt_type (only 'goods' counts), qty_accepted and receipt_date.
    po_line: The procurement.po_line table with the columns po_key, line_no and itm_key; one row per order line.
    purchase_order: The procurement.purchase_order table with the columns po_key (one row per order) and sup_key.
    item: The inventory.item table with the columns itm_key (one row per item), category and footprint_kgco2e_per_unit.
    f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
    exclude_categories: Tuple of item categories left out (PROPOSED: fuel_fleet); a plain text raises.
    periods: A collection of YYYY-MM months to keep, or None for every month.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), one row per supplier, month and item category, sorted by ref_key, period and subcategory; empty with these columns when no receipt counts.

Raises:
    FrameError: a table is not a frame or lacks a needed column; exclude_categories is a text and not a tuple; po_line, purchase_order or item has two rows for a key.
    FrameError: qty_accepted has nulls; a receipt names an order line that po_line does not hold, or an item or order that item or purchase_order does not hold.
    FrameError: a month has no valid factor or more than one valid factor on its first day.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import expected_goods_lines
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
    >>> F = pd.DataFrame([("EF-900004", "purchased_goods_product_footprint", None, "ALL", None, 0.8, "2031-01-01", None, "FS-A")], columns=cols)
    >>> GR = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "receipt_type": ["goods"], "qty_accepted": [10.0], "receipt_date": ["2031-03-15"]})
    >>> PL = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "itm_key": ["ITM-900001"]})
    >>> PO = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"]})
    >>> IT = pd.DataFrame({"itm_key": ["ITM-900001"], "category": ["steel"], "footprint_kgco2e_per_unit": [5.0]})
    >>> out = expected_goods_lines(GR, PL, PO, IT, F, context=ctx)
    >>> out[["ref_key", "period", "subcategory", "quantity", "expected_kg"]].to_dict("records")
    [{'ref_key': 'SUP-900001', 'period': '2031-03', 'subcategory': 'steel', 'quantity': 50.0, 'expected_kg': 40.0}]

## Source columns

- `procurement.goods_receipt.po_key`
- `procurement.goods_receipt.line_no`
- `procurement.goods_receipt.receipt_type`
- `procurement.goods_receipt.qty_accepted`
- `procurement.goods_receipt.receipt_date`
- `procurement.purchase_order.po_key`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.legal_entity_key`
- `inventory.item.itm_key`
- `inventory.item.category`
- `inventory.item.footprint_kgco2e_per_unit`
- `inventory.item.item_type`
- `procurement.po_line.po_key`
- `procurement.po_line.line_no`
- `procurement.po_line.itm_key`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
- `energy-esg.emission_factor.factor_set`
