# open_po_lines

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import open_po_lines`.

```python
open_po_lines(po_line: pd.DataFrame, purchase_order: pd.DataFrame, goods_receipt: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the order lines still open on a date, with the quantity remaining, the slip of the promise and the days overdue.

A line is open when its order is not cancelled (no cancel date exists, so a cancelled order is left out for every date; policy.delivery.cancel_date_proxy, proposed), was placed on or before the date, and the quantity accepted in receipts up to and including the date is below the ordered quantity. remaining = qty minus accepted. slip_days = promised_date minus requested_date, the days the supplier moved the date. days_overdue = days from promised_date to the date when the promise is already past, else 0.
The promise is the one valid on the date. `po_line.promised_date` is the final promise and `promise_revised_on` the day the supplier gave it (one revision per line; `requested_date` is the original due date and the promise before the revision, generator orders.py). When the date is before the revision the original date (`requested_date`) is the promise: slip_days is then 0, days_overdue counts from it, `promised_date` shows it and `promise_is_final` is False; from the revision day on `promised_date` is the stored one and `promise_is_final` is True. A line without a revision keeps its stored promised_date (promise_is_final True). Without a `promise_revised_on` column in `po_line` no revision is known: the stored promised_date is used for every date and promise_is_final is True, which can show a later promise than the one that stood on a past date. `promise_revised_on` in the result is the revision day when it is on or before the date, else null.

Args:
    po_line: The procurement.po_line frame, one row per po_key and line_no; it needs po_key, line_no, itm_key, qty (numeric), promised_date and requested_date, and optionally promise_revised_on.
    purchase_order: The procurement.purchase_order frame, one row per po_key; it needs po_key, sup_key, prj_key, order_date and status.
    goods_receipt: The procurement.goods_receipt frame; it needs po_key, line_no, receipt_date and qty_accepted (numeric); line_no has the type of po_line.line_no.
    as_of: The day to measure on (a date, a Timestamp or a text); a time of day is dropped.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame keyed by po_key and line_no with the columns po_key, line_no, prj_key, itm_key, sup_key, order_date, qty, accepted, remaining, requested_date, promised_date, promise_revised_on, promise_is_final, slip_days, days_overdue, sorted by po_key and line_no.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line repeats a po_key and line_no or purchase_order repeats a po_key; qty or qty_accepted is not numeric or has nulls; a key, order_date or receipt_date is null; a line has no promised_date or requested_date; a date is not a date or has a time zone; line_no differs in type between po_line and goods_receipt; as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import open_po_lines
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pl = pd.DataFrame({"po_key": ["PO-900001", "PO-900001"], "line_no": [1, 2], "itm_key": ["ITM-900001", "ITM-900002"], "qty": [10.0, 5.0],
    ...                    "promised_date": ["2025-03-01", "2025-03-01"], "requested_date": ["2025-02-01", "2025-02-01"]})
    >>> po = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"], "prj_key": ["PRJ-900001"], "order_date": ["2025-01-10"], "status": ["open"]})
    >>> gr = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [2], "receipt_date": ["2025-02-20"], "qty_accepted": [5.0]})
    >>> r = open_po_lines(pl, po, gr, "2025-03-05", context=ctx)
    >>> r[["line_no", "remaining", "slip_days", "days_overdue"]].to_dict("records")
    [{'line_no': 1, 'remaining': 10.0, 'slip_days': 28, 'days_overdue': 4}]

## Source columns

- `procurement.po_line.po_key`
- `procurement.po_line.line_no`
- `procurement.po_line.itm_key`
- `procurement.po_line.qty`
- `procurement.po_line.promised_date`
- `procurement.po_line.requested_date`
- `procurement.po_line.promise_revised_on`
- `procurement.purchase_order.po_key`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.order_date`
- `procurement.purchase_order.status`
- `procurement.goods_receipt.po_key`
- `procurement.goods_receipt.line_no`
- `procurement.goods_receipt.receipt_date`
- `procurement.goods_receipt.qty_accepted`
