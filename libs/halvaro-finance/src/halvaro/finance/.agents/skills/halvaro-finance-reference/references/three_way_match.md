# three_way_match

```python
three_way_match(supplier_invoice_line: pd.DataFrame, goods_receipt: pd.DataFrame, *, price_tolerance_percent: float = 0.0, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check each supplier invoice line against the purchase order price and the quantity accepted on the receipt.

Rule (quantity first): a credit note is credit_for_rejected_goods; a line without a PO price is non_po; an invoiced quantity above the accepted quantity is quantity_variance; a price difference beyond the tolerance is price_variance; otherwise matched. price_variance is (invoice price less PO price) times quantity, to the cent. The stored status and variance are shown beside the recomputed ones.

## Args

supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, line_no, po_key, po_line_no, receipt_no, quantity, unit_price, po_unit_price, invoice_type, match_status and price_variance.
goods_receipt: Frame procurement.goods_receipt with po_key, line_no, receipt_no and qty_accepted.
price_tolerance_percent: Largest accepted price difference in percent, zero or more. Default 0 (PROPOSED; the plan recommends a policy value).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sinv_key, line_no, po_key, status, price_variance, price_diff_percent, stored_status, stored_price_variance and agrees.

## Raises

FrameError: a column is missing, the tolerance is not a finite number of zero or more, a line or a receipt key is repeated, a PO line has a null price or quantity, or a PO line has no goods receipt.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import three_way_match
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"sinv_key": ["S1", "S2"], "line_no": [1, 1], "po_key": ["PO-1"] * 2, "po_line_no": [1, 2], "receipt_no": [1, 1], "quantity": [10, 10],
...                       "unit_price": [11.0, 10.0], "po_unit_price": [10.0, 10.0], "invoice_type": ["invoice"] * 2, "match_status": ["matched"] * 2, "price_variance": [10.0, 0.0]})
>>> receipt = pd.DataFrame({"po_key": ["PO-1"] * 2, "line_no": [1, 2], "receipt_no": [1, 1], "qty_accepted": [10, 8]})
>>> three_way_match(lines, receipt, context=ctx)[["sinv_key", "status", "price_variance"]].values.tolist()
[['S1', 'price_variance', 10.0], ['S2', 'quantity_variance', 0.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice_line.sinv_key`, `finance.supplier_invoice_line.line_no`, `finance.supplier_invoice_line.po_key`, `finance.supplier_invoice_line.po_line_no`, `finance.supplier_invoice_line.receipt_no`, `finance.supplier_invoice_line.quantity`, `finance.supplier_invoice_line.unit_price`, `finance.supplier_invoice_line.po_unit_price`, `finance.supplier_invoice_line.invoice_type`, `finance.supplier_invoice_line.match_status`, `finance.supplier_invoice_line.price_variance`, `procurement.goods_receipt.po_key`, `procurement.goods_receipt.line_no`, `procurement.goods_receipt.receipt_no`, `procurement.goods_receipt.qty_accepted`.
