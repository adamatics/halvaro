# committed_cost

```python
committed_cost(open_po_lines: pd.DataFrame, po_line: pd.DataFrame, purchase_order: pd.DataFrame, *, spot_orders: pd.DataFrame | None = None, delivery_type: str = 'project_site', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the value of the purchase orders that are still open, by project and cost code, in the order currency and in DKK.

Rule: the open quantity of each line (from open_po_lines and spot_orders; a line in both is counted once and flagged spot) times the unit price of its order line. Only orders of the given delivery type count (proposed "project_site"; orders for stock have no project and are dropped). DKK is converted at the booking rates.

## Args

open_po_lines: Frame from the delivery open_po_lines with po_key, line_no, prj_key and qty_open (the name remaining is also accepted).
po_line: Frame procurement.po_line with po_key, line_no, unit_price, currency and cst_key, one row per order line.
purchase_order: Frame procurement.purchase_order with po_key and delivery_type, one row per order.
spot_orders: Frame from the delivery spot_orders with the same columns as open_po_lines. Optional.
delivery_type: The delivery type of the orders that count. Default "project_site" (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, cst_key, currency, spot, n_lines, committed and committed_dkk, sorted by project, cost code, currency and spot.

## Raises

FrameError: a column is missing, po_line or purchase_order repeats a key, an order line is listed twice, a quantity is null or negative, an open line has no order line or no price or currency, a quantity or a price is infinite, belongs to an order without a delivery type, or (of the counted type) has no project, or qty_open and remaining disagree.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import committed_cost
>>> ctx = Context(stage="month12", role="analyst")
>>> open_lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "prj_key": ["PRJ-1"], "qty_open": [4.0]})
>>> lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "unit_price": [25.0], "currency": ["DKK"], "cst_key": ["CST-1"]})
>>> orders = pd.DataFrame({"po_key": ["PO-1"], "delivery_type": ["project_site"]})
>>> committed_cost(open_lines, lines, orders, context=ctx)[["prj_key", "cst_key", "spot", "committed_dkk"]].values.tolist()
[['PRJ-1', 'CST-1', False, 100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `procurement.po_line.po_key`, `procurement.po_line.line_no`, `procurement.po_line.unit_price`, `procurement.po_line.currency`, `procurement.po_line.cst_key`, `procurement.purchase_order.po_key`, `procurement.purchase_order.delivery_type`.
