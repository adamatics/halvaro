# supplier_performance_recompute

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import supplier_performance_recompute`.

```python
supplier_performance_recompute(po_line: pd.DataFrame, purchase_order: pd.DataFrame, goods_receipt: pd.DataFrame, as_of: DateLike, *, grace_days: int = 2, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the lines due and on time per supplier and month rebuilt from the order lines and goods receipts up to a date.

Lines due and on time per supplier and month of requested_date (the original due date), like procurement.supplier_performance. A line is due when requested_date is on or before the date, on time when the cumulative accepted quantity reached the ordered quantity (receipts up to the date) on or before requested_date plus grace_days (PROPOSED policy.delivery.supplier_on_time_rule, 2 days). Cancelled orders are left out. goods_receipt is one row per (po_key, line_no, receipt_no); a repeated key, or without a receipt_no an identical row, is refused.

Args:
    po_line: The procurement.po_line frame; it needs po_key, line_no, qty (numeric without nulls) and requested_date, one row per po_key and line_no.
    purchase_order: The procurement.purchase_order frame; it needs po_key, sup_key (no nulls) and status, one row per po_key.
    goods_receipt: The procurement.goods_receipt frame; it needs po_key, line_no, receipt_date and qty_accepted (numeric, not negative, no nulls), and receipt_no when several receipts may look alike.
    as_of: The day to count up to, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
    grace_days: Whole days after requested_date that still count as on time, zero or more (default 2, PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns sup_key, period (YYYY-MM of requested_date), po_count, lines_due, lines_on_time and on_time_percent (rounded to 1 decimal), sorted by sup_key and period.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line or purchase_order has more than one row for a key; goods_receipt repeats a key or, without receipt_no, has identical rows; grace_days is not a whole number of zero or more; qty or qty_accepted is not numeric or has nulls; qty_accepted is negative; as_of is not an ISO date, is a number or has a time zone; an order has no sup_key; line_no has different types in po_line and goods_receipt; requested_date or receipt_date has nulls, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import supplier_performance_recompute
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lines = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "qty": [5.0, 3.0], "requested_date": ["2031-03-10", "2031-03-20"]})
    >>> orders = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"], "status": ["received"]})
    >>> gr = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "receipt_no": [1, 1],
    ...                    "receipt_date": ["2031-03-11", "2031-03-25"], "qty_accepted": [5.0, 3.0]})
    >>> r = supplier_performance_recompute(lines, orders, gr, "2031-04-01", context=ctx)
    >>> r[["sup_key", "period", "lines_due", "lines_on_time", "on_time_percent"]].to_dict("records")
    [{'sup_key': 'SUP-900001', 'period': '2031-03', 'lines_due': 2, 'lines_on_time': 1, 'on_time_percent': 50.0}]

## Source columns

- `procurement.po_line.po_key`
- `procurement.po_line.line_no`
- `procurement.po_line.qty`
- `procurement.po_line.requested_date`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.status`
- `procurement.goods_receipt.receipt_no`
- `procurement.goods_receipt.receipt_date`
- `procurement.goods_receipt.qty_accepted`
