# stock_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import stock_view`.

```python
stock_view(stock: pd.DataFrame, open_lines: pd.DataFrame | None = None, *, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need on hand, reserved and available stock over dates as chart lines, with the open purchase order lines on the side.

`stock` is a stack of `stock_on` outputs (as_of, site_key, itm_key, on_hand, reserved, available). The result is a long frame as_of, site_key, itm_key, series, quantity. With `open_lines` (open_po_lines of one date) the remaining quantity per item and promised date is in extra['orders']. Quantities keep the item unit; items are never added together.

Args:
    stock: A stack of stock_on outputs; it needs as_of, site_key, itm_key, on_hand, reserved and available.
    open_lines: Optional output of open_po_lines for one date; it needs itm_key and remaining, and itm_key, po_key, line_no and promised_date are carried when present.
    as_of: Optional as-of date, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'lines': `frame` (as_of, site_key, itm_key, series one of on_hand, reserved, available, quantity; sorted by itm_key, site_key, as_of, series), x as_of, y quantity, group series, n the number of stock rows, extra['orders'] the open line frame when open_lines is given.

Raises:
    FrameError: stock or open_lines is not a DataFrame or lacks a needed column.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import stock_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> st = pd.DataFrame({"as_of": ["2026-01-05"], "site_key": ["SITE-900001"], "itm_key": ["ITM-900001"], "on_hand": [10.0], "reserved": [4.0], "available": [6.0]})
    >>> ol = pd.DataFrame({"itm_key": ["ITM-900001"], "po_key": ["PO-900001"], "remaining": [5.0]})
    >>> spec = stock_view(st, ol, context=ctx)
    >>> spec.frame["series"].tolist()
    ['available', 'on_hand', 'reserved']
    >>> spec.frame["quantity"].tolist()
    [6.0, 10.0, 4.0]
    >>> spec.extra["orders"]["remaining"].tolist()
    [5.0]

## Source columns

- `inventory.stock_level.on_hand`
- `procurement.po_line.itm_key`
