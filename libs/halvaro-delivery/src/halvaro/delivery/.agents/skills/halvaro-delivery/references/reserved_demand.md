# reserved_demand

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import reserved_demand`.

```python
reserved_demand(reservation: pd.DataFrame, stock_movement: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the reservations created by a date that still have quantity open, with what was issued against them.

A reservation counts when it was created on or before the date. Its open quantity is qty minus the issues to the project up to and including the date (movements of type issue_project with the reservation number; issues are negative stock movements, the issued quantity is their absolute sum). Only reservations with open quantity above zero are returned.

Args:
    reservation: The inventory.reservation frame, one row per prj_key, itm_key and reservation_no; it needs prj_key, itm_key, reservation_no, site_key, qty (numeric), created_date, needed_by_date, po_key and po_line_no.
    stock_movement: The inventory.stock_movement frame; it needs movement_type, movement_date, qty (numeric), prj_key, reservation_no and itm_key.
    as_of: The day to measure on (a date, a Timestamp or a text); a time of day is dropped.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns prj_key, itm_key, reservation_no, site_key, qty, issued, qty_open, needed_by_date, po_key (null for a free reservation, one that waits for no order), po_line_no, sorted by prj_key, itm_key, reservation_no.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the reservation frame repeats a prj_key, itm_key and reservation_no; qty is not numeric or has nulls; a key or created_date of a reservation is null; an issue_project movement with a reservation number has a null key or movement_date; such a movement has a positive quantity; a date is not a date or has a time zone; as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import reserved_demand
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rsv = pd.DataFrame({"prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"], "reservation_no": [1], "site_key": ["SIT-900001"], "qty": [10.0],
    ...                     "created_date": ["2025-01-10"], "needed_by_date": ["2025-03-01"], "po_key": [None], "po_line_no": [None]})
    >>> mv = pd.DataFrame({"movement_type": ["issue_project"], "movement_date": ["2025-02-01"], "qty": [-4.0], "prj_key": ["PRJ-900001"],
    ...                    "reservation_no": [1], "itm_key": ["ITM-900001"]})
    >>> r = reserved_demand(rsv, mv, "2025-02-15", context=ctx)
    >>> r[["issued", "qty_open"]].to_dict("records")
    [{'issued': 4.0, 'qty_open': 6.0}]

## Source columns

- `inventory.reservation.prj_key`
- `inventory.reservation.itm_key`
- `inventory.reservation.reservation_no`
- `inventory.reservation.site_key`
- `inventory.reservation.qty`
- `inventory.reservation.created_date`
- `inventory.reservation.needed_by_date`
- `inventory.reservation.po_key`
- `inventory.stock_movement.reservation_no`
- `inventory.stock_movement.movement_type`
- `inventory.stock_movement.movement_date`
- `inventory.stock_movement.qty`
- `inventory.stock_movement.prj_key`
- `inventory.stock_movement.itm_key`
- `inventory.reservation.po_line_no`
