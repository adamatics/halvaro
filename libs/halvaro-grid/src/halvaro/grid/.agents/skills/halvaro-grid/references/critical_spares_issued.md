# critical_spares_issued

Module `halvaro.grid.parts`. Import: `from halvaro.grid import critical_spares_issued`.

```python
critical_spares_issued(ticket_item_use: pd.DataFrame, item: pd.DataFrame, *, window: Window | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the issues of the critical spare items on tickets, with the units used and the first and last day of use.

The critical items are those with the flag `inventory.item.critical` (an item without the flag is never listed, and no id list is used). The optional `window` is two days, both included.
A critical item with no issue in the window is listed with zero units. The minimum stock rule (policy.delivery.minimum_stock_rule) is not applied here: it belongs to halvaro-delivery.

Args:
    ticket_item_use: The service.ticket_item_use frame, columns tkt_key, itm_key, qty, used_on and uom.
    item: The inventory.item frame, columns itm_key and critical (true or false).
    window: Optional two days (first day, last day, both included) that limit the issues by used_on.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns itm_key, uom, units, n_lines, n_tickets, first_used and last_used, sorted by itm_key and uom (a critical item without issue has a null uom, zero units and null days, last).

Raises:
    FrameError: a column of ticket_item_use or item is missing; ticket_item_use has rows without a ticket or an item, more than one row for a ticket, item and day, a qty that is not a number of zero or more, or a used_on that is not a date;
        item repeats an itm_key, or critical has nulls or holds text or numbers; an item used on a ticket is missing from inventory.item; window is not two dates or ends before it starts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import critical_spares_issued
    >>> ctx = Context(stage="month12", role="analyst")
    >>> u = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "itm_key": ["ITM-900001", "ITM-900002"], "qty": [2.0, 1.0], "used_on": ["2025-03-03", "2025-03-04"], "uom": "pcs"})
    >>> i = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002", "ITM-900003"], "critical": [True, False, True]})
    >>> out = critical_spares_issued(u, i, context=ctx)
    >>> out[["itm_key", "units", "n_tickets"]].to_dict("records")
    [{'itm_key': 'ITM-900001', 'units': 2.0, 'n_tickets': 1}, {'itm_key': 'ITM-900003', 'units': 0.0, 'n_tickets': 0}]

## Source columns

- `service.ticket_item_use.itm_key`
- `service.ticket_item_use.qty`
- `service.ticket_item_use.uom`
- `service.ticket_item_use.used_on`
- `service.ticket_item_use.tkt_key`
- `inventory.item.itm_key`
- `inventory.item.critical`
