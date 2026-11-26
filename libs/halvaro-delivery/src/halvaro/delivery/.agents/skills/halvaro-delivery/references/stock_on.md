# stock_on

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import stock_on`.

```python
stock_on(stock_movement: pd.DataFrame, as_of: DateLike, *, stock_level: pd.DataFrame | None = None, reservation_open: pd.DataFrame | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need on hand, reserved and available stock per site and item on a date.

On hand is the cumulative signed movement quantity up to and including the date (the generator rebuilds on_hand the same way). When `stock_level` has a snapshot row for the date it is used (source snapshot), otherwise the movements are (source movements). `reservation_open` (output of reserved_demand: site_key, itm_key, qty_open) gives reserved, also on a snapshot row (the snapshot's own reserved column is then not used, and a pair without a reservation is reserved 0); without it reserved is the snapshot value or null. A reservation on a site and item with no stock is kept, with zero on hand. available is on_hand minus reserved and can be negative.

Args:
    stock_movement: The inventory.stock_movement frame; it needs site_key, itm_key, movement_date and qty (signed, numeric without nulls).
    as_of: The day of the stock (a date, a Timestamp or a text); a time of day is dropped.
    stock_level: Optional inventory.stock_level frame (site_key, itm_key, as_of_date, on_hand, reserved, available); a row for the date replaces the movement sum of its pair.
    reservation_open: Optional output of reserved_demand (site_key, itm_key, qty_open); it gives the reserved quantity per site and item.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns site_key, itm_key, as_of, on_hand, reserved, available, source ('snapshot' or 'movements'), sorted by site_key and itm_key.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; qty, on_hand or qty_open is not numeric or has nulls; a site or item key is null; a movement has no movement_date or a date that is not a date or has a time zone; as_of is a number, has a time zone or is not a date; the snapshot of the date has a null on_hand or reserved or more than one row for a site and item.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import stock_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> mv = pd.DataFrame({"site_key": ["SIT-900001"] * 3, "itm_key": ["ITM-900001"] * 3,
    ...                    "movement_date": ["2025-01-05", "2025-02-01", "2025-03-01"], "qty": [10.0, -4.0, 5.0]})
    >>> r = stock_on(mv, "2025-02-15", context=ctx)
    >>> r["on_hand"].tolist(), r["source"].tolist()
    ([6.0], ['movements'])
    >>> res = pd.DataFrame({"site_key": ["SIT-900001"], "itm_key": ["ITM-900001"], "qty_open": [2.0]})
    >>> stock_on(mv, "2025-02-15", reservation_open=res, context=ctx)["available"].tolist()
    [4.0]

## Source columns

- `inventory.stock_movement.site_key`
- `inventory.stock_movement.itm_key`
- `inventory.stock_movement.movement_date`
- `inventory.stock_movement.qty`
- `inventory.stock_level.site_key`
- `inventory.stock_level.itm_key`
- `inventory.stock_level.as_of_date`
- `inventory.stock_level.on_hand`
- `inventory.stock_level.reserved`
- `inventory.stock_level.available`
