# at_risk_items

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import at_risk_items`.

```python
at_risk_items(items: Sequence[str], stock: pd.DataFrame, open_lines: pd.DataFrame, alerts: pd.DataFrame, window_performance: pd.DataFrame, *, site: str, sup_key: str, as_of: DateLike, min_on_time_percent: float = 75.0, min_lines: int | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to flag which items of one supplier are at risk from stock, slipping order lines, lead time alerts or poor on time delivery.

Per item of a supplier: stock_zero (on hand at the site zero or less), n_slipping_lines (open lines of the supplier promised later than requested or already past their promise, from an open_po_lines frame built for the same date as `as_of`), lead_time_alert (the item is in the alerts), on_time_percent (supplier_performance_window row of the supplier) and low_on_time (below min_on_time_percent, PROPOSED 75). lines_due is the supplier's line count of the window (null when the window frame has no lines_due column): OP.STD.002 flags a supplier with few lines only with the count shown, so read low_on_time with it; min_lines (None) adds thin_window, true when lines_due is below it or unknown (the supplier has no row in the window frame, no line in the window being the thinnest window, or the frame has no lines_due column), and does not change low_on_time or at_risk. no_stock_row is true for an item with no row in the stock frame at the site: it counts as zero stock (stock_zero true, as in blocked_projects), so a mistyped or unstocked item shows up as at risk with this flag set. The stock frame, when it has an `as_of` column (stock_on output), must be for `as_of`; open_lines carries no date, build it with open_po_lines for the same date. at_risk is true when any of the four holds.

Args:
    items: The item keys of the supplier to judge, a list or a single key.
    stock: Output of stock_on; it needs site_key, itm_key and on_hand, one row per site and item, and when it has an as_of column that is one date equal to `as_of`.
    open_lines: Output of open_po_lines for the same date; it needs sup_key, itm_key, slip_days and days_overdue.
    alerts: Output of lead_time_alerts; it needs sup_key and itm_key.
    window_performance: Output of supplier_performance_window; it needs sup_key and on_time_percent, and lines_due for the line count, at most one row for the supplier.
    site: The site key whose stock is judged.
    sup_key: The supplier key as text.
    as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
    min_on_time_percent: Below this on time percent the supplier counts as low (default 75.0, PROPOSED).
    min_lines: Optional whole number of zero or more; a window with fewer lines than this, or an unknown line count, sets thin_window.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per item and the columns itm_key, stock_zero, n_slipping_lines, lead_time_alert, on_time_percent, lines_due, low_on_time, thin_window, no_stock_row and at_risk, sorted by itm_key.

Raises:
    FrameError: as_of is not an ISO date, is a number or has a time zone; sup_key is not one key as text; a frame is not a DataFrame, has duplicate column names or lacks a needed column; the stock frame is for another date than as_of, holds more than one date or has more than one row for a site and item; min_lines is not a whole number of zero or more or None; items is a frame, a mapping or None; window_performance has more than one row for the supplier or a non-numeric on_time_percent.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import at_risk_items
    >>> ctx = Context(stage="month12", role="analyst")
    >>> stock = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900001"], "itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [0.0, 5.0]})
    >>> lines = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900002"], "slip_days": [0], "days_overdue": [0]})
    >>> alerts = pd.DataFrame({"sup_key": [], "itm_key": []})
    >>> perf = pd.DataFrame({"sup_key": ["SUP-900001"], "lines_due": [40], "on_time_percent": [90.0]})
    >>> r = at_risk_items(["ITM-900001", "ITM-900002"], stock, lines, alerts, perf, site="SIT-900001", sup_key="SUP-900001", as_of="2031-04-01", context=ctx)
    >>> r[["itm_key", "stock_zero", "at_risk"]].to_dict("records")
    [{'itm_key': 'ITM-900001', 'stock_zero': True, 'at_risk': True}, {'itm_key': 'ITM-900002', 'stock_zero': False, 'at_risk': False}]

## Source columns

- `inventory.stock_level.on_hand`
- `procurement.po_line.promised_date`
- `procurement.po_line.requested_date`
- `inventory.lead_time.lead_time_weeks`
- `procurement.supplier_performance.on_time_percent`
