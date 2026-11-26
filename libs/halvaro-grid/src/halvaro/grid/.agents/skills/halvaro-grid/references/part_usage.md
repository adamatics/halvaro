# part_usage

Module `halvaro.grid.parts`. Import: `from halvaro.grid import part_usage`.

```python
part_usage(ticket_item_use: pd.DataFrame, service_ticket: pd.DataFrame, grid_element: pd.DataFrame | None = None, *, no_element: str = 'none', context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the units of parts used on tickets by item, unit of measure, element type and month.

The month is the month of `used_on`. The element type comes from the ticket's element (`service.service_ticket.net_key`) and `gis.grid_element`; a ticket without an element (off-grid work) gets `no_element` ('none').
Without `grid_element` every row gets 'unknown'. Quantities of different units are never added: the unit of measure is a key column.

Args:
    ticket_item_use: The service.ticket_item_use frame, columns tkt_key, itm_key, qty, used_on and uom.
    service_ticket: The service.service_ticket frame, columns tkt_key and net_key.
    grid_element: Optional gis.grid_element frame, columns net_key and element_type; without it the element type is 'unknown'.
    no_element: The element type given to a ticket without an element (default 'none').
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns itm_key, uom, element_type, period (YYYY-MM), units, n_lines and n_tickets, sorted by itm_key, uom, element_type and period.

Raises:
    FrameError: a column of ticket_item_use, service_ticket or grid_element is missing; ticket_item_use has rows without a ticket or an item, more than one row for a ticket, item and day, a qty that is not a number of zero or more, or a used_on that is not a date;
        service_ticket or grid_element repeats a key; a use row's ticket is not in service_ticket; a ticket names an element that grid_element does not hold.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import part_usage
    >>> ctx = Context(stage="month12", role="analyst")
    >>> u = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "itm_key": "ITM-900001", "qty": [2.0, 3.0], "used_on": ["2025-03-03", "2025-03-20"], "uom": "pcs"})
    >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "net_key": ["NET-900001", None]})
    >>> g = pd.DataFrame({"net_key": ["NET-900001"], "element_type": ["valve"]})
    >>> out = part_usage(u, t, g, context=ctx)
    >>> out[["element_type", "period", "units", "n_tickets"]].to_dict("records")
    [{'element_type': 'none', 'period': '2025-03', 'units': 3.0, 'n_tickets': 1}, {'element_type': 'valve', 'period': '2025-03', 'units': 2.0, 'n_tickets': 1}]

## Source columns

- `service.ticket_item_use.itm_key`
- `service.ticket_item_use.qty`
- `service.ticket_item_use.uom`
- `service.ticket_item_use.used_on`
- `service.ticket_item_use.tkt_key`
- `service.service_ticket.tkt_key`
- `service.service_ticket.net_key`
- `gis.grid_element.net_key`
- `gis.grid_element.element_type`
