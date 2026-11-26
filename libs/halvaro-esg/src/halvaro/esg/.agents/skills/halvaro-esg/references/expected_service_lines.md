# expected_service_lines

Module `halvaro.esg.recompute`. Import: `from halvaro.esg import expected_service_lines`.

```python
expected_service_lines(po_line: pd.DataFrame, item: pd.DataFrame, purchase_order: pd.DataFrame, f: pd.DataFrame, *, category_factor: Mapping[str, Any] | None = None, country_of_le: Mapping[str, Any] | None = None, received_status: tuple[str, ...] = ('received', 'partially_received'), periods: Iterable[str] | None = None, restate: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the scope 3.1 spend based emission lines that the received share of service orders should produce per project and month.

Scope 3.1 spend based service lines: the value of the received share of each service order line (`line_value_dkk` times the received share, at most 1, lines with a received quantity and a last receipt
date) in DKK, per project (or legal entity without a project) and month of the last receipt, times the spend factor of the item category in the country of the legal entity, valid on the first of the month.
`category_factor` (item category -> factor category) and `country_of_le` are PROPOSED keywords (the plan says fact needed): defaults map the civil and electrical services to their own spend families and the
rest to spend_subcontractor_other. Same columns as expected_lines_s123: ref_key is the project or the entity, subcategory is null, unit DKK. An item category without a mapping, or a legal entity without a
country, raises FrameError. `restate` ({'year': 2025, 'factor_date': '2026-01-01'}) takes the factor of that date for the months of the year, as expected_lines_s123 does for the restated lines.

Args:
    po_line: The procurement.po_line table with the columns po_key, line_no, itm_key, qty, line_value_dkk, received_qty, last_receipt_date and line_status.
    item: The inventory.item table with the columns itm_key (one row per item), category and item_type (only 'service' items count).
    purchase_order: The procurement.purchase_order table with the columns po_key (one row per order), prj_key and legal_entity_key.
    f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
    category_factor: PROPOSED mapping from item category to factor category; None for the built in defaults.
    country_of_le: PROPOSED mapping from legal entity key to country; None for the built in defaults.
    received_status: The line_status values that count as received (default received and partially_received).
    periods: A collection of YYYY-MM months to keep, or None for every month.
    restate: None for the factors of the first day of each month, or a mapping with exactly the keys year and factor_date for the restated basis of that year.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), one row per project or entity, month and factor family, sorted by ref_key, period and subcategory; quantity is the value in DKK; empty with these columns when no line counts.

Raises:
    FrameError: a table is not a frame or lacks a needed column; po_line, purchase_order or item has two rows for a key.
    FrameError: a counted service line has a quantity of zero or less or a null quantity, value or received quantity; an order is not in purchase_order.
    FrameError: an item category has no factor category (or is null) in category_factor; a legal entity has no country in country_of_le.
    FrameError: restate is not a mapping with exactly the keys year and factor_date, the restate year has no period in the data, or a period is not text YYYY-MM.
    FrameError: a month has no valid factor or more than one valid factor on its date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import expected_service_lines
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
    >>> F = pd.DataFrame([("EF-900005", "spend_subcontractor_civil", None, "DK", None, 0.1, "2031-01-01", None, "FS-A")], columns=cols)
    >>> PL = pd.DataFrame({"po_key": ["PO-900002"], "line_no": [1], "itm_key": ["ITM-900002"], "qty": [4.0], "line_value_dkk": [1000.0],
    ...                    "received_qty": [2.0], "last_receipt_date": ["2031-03-20"], "line_status": ["partially_received"]})
    >>> PO = pd.DataFrame({"po_key": ["PO-900002"], "prj_key": ["PRJ-900001"], "legal_entity_key": ["LE-900001"]})
    >>> IT = pd.DataFrame({"itm_key": ["ITM-900002"], "category": ["service_civil"], "item_type": ["service"]})
    >>> out = expected_service_lines(PL, IT, PO, F, country_of_le={"LE-900001": "DK"}, context=ctx)
    >>> out[["ref_key", "period", "quantity", "unit", "expected_kg"]].to_dict("records")
    [{'ref_key': 'PRJ-900001', 'period': '2031-03', 'quantity': 500.0, 'unit': 'DKK', 'expected_kg': 50.0}]

## Source columns

- `procurement.po_line.po_key`
- `procurement.po_line.itm_key`
- `procurement.po_line.qty`
- `procurement.po_line.line_value_dkk`
- `procurement.po_line.received_qty`
- `procurement.po_line.last_receipt_date`
- `procurement.po_line.line_status`
- `procurement.purchase_order.po_key`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.legal_entity_key`
- `inventory.item.itm_key`
- `inventory.item.category`
- `inventory.item.footprint_kgco2e_per_unit`
- `inventory.item.item_type`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
- `energy-esg.emission_factor.factor_set`
