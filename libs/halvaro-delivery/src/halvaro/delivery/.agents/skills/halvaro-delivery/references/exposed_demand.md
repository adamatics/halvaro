# exposed_demand

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import exposed_demand`.

```python
exposed_demand(open_lines: pd.DataFrame, reservations_open: pd.DataFrame, price_list: pd.DataFrame, project: pd.DataFrame, sup_key: str, effective_from: DateLike, *, active: Sequence[str], context: halvaro.core.access.Context) -> ExposedDemand
```

Use this when you need the quantity exposed to one supplier's price step: its open order lines and the free reservations on active projects, and the projects they define.

The lines are the open order lines of the supplier (open_po_lines output) on the active projects, with remaining quantity and after_effective_date (placed on or after `effective_from`, the lines the price step reaches). The reservations are the free ones (po_key null, quantity open) on active projects for items in the supplier's price list. `active` is the list of active project keys the app passes (from active_on). projects: every project with either, with price_type, n_lines, n_reservations and the remaining quantities. Every project in `projects` must be in the project frame; an active project that has no demand of the supplier need not be. The supplier and the date are the caller's. Quantities only: money is multiplied by finance. The remaining quantities add up quantities of items with different units (metres, sets, units), as the generator's own exposure test does; they are not unit safe. `.combined` gives lines and reservations as the single frame of plan section 6.

Args:
    open_lines: Output of open_po_lines; it needs po_key, line_no, prj_key, itm_key, sup_key, order_date and remaining (numeric), one row per po_key and line_no.
    reservations_open: Output of reserved_demand; it needs prj_key, itm_key, qty_open (numeric) and po_key.
    price_list: The procurement.price_list frame; it needs sup_key and itm_key and gives the items of the supplier.
    project: The projects.project frame, one row per prj_key; it needs prj_key and price_type.
    sup_key: The supplier the price step belongs to.
    effective_from: The day the price step starts (a date, a Timestamp or a text).
    active: The active project keys, a list or a single key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An ExposedDemand tuple: `lines` (the supplier's open lines on active projects with after_effective_date, sorted by prj_key, po_key, line_no), `reservations` (the free reservations, sorted by prj_key, itm_key), `projects` (prj_key, n_lines, remaining_lines, n_reservations, remaining_reserved, price_type, sorted by prj_key) and `sup_key`; its `.combined` property is the single frame.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the project frame repeats a prj_key; remaining or qty_open is not numeric or has nulls; a key column is null; the open lines repeat an order line or have a row without order_date; active is a frame, a mapping or None; effective_from or an order_date is not a date; a project with demand is not in the project frame.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import exposed_demand
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lines = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"],
    ...                       "sup_key": ["SUP-900001"], "order_date": ["2025-03-01"], "remaining": [8.0]})
    >>> res = pd.DataFrame({"prj_key": ["PRJ-900001"], "itm_key": ["ITM-900001"], "qty_open": [3.0], "po_key": [None]})
    >>> pl = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"]})
    >>> pj = pd.DataFrame({"prj_key": ["PRJ-900001"], "price_type": ["fixed"]})
    >>> r = exposed_demand(lines, res, pl, pj, "SUP-900001", "2025-02-01", active=["PRJ-900001"], context=ctx)
    >>> r.lines["after_effective_date"].tolist()
    [True]
    >>> r.projects[["prj_key", "remaining_lines", "remaining_reserved"]].to_dict("records")
    [{'prj_key': 'PRJ-900001', 'remaining_lines': 8.0, 'remaining_reserved': 3.0}]

## Source columns

- `procurement.po_line.po_key`
- `procurement.po_line.line_no`
- `procurement.po_line.itm_key`
- `procurement.po_line.qty`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.order_date`
- `procurement.goods_receipt.qty_accepted`
- `procurement.price_list.sup_key`
- `procurement.price_list.itm_key`
- `projects.project.prj_key`
- `projects.project.price_type`
- `inventory.reservation.prj_key`
- `inventory.reservation.itm_key`
- `inventory.reservation.reservation_no`
- `inventory.reservation.qty`
- `inventory.reservation.po_key`
