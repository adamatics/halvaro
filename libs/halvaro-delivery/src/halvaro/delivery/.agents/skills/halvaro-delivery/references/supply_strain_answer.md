# supply_strain_answer

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import supply_strain_answer`.

```python
supply_strain_answer(items: Sequence[str], zones: Sequence[str], *, stock: pd.DataFrame, open_lines: pd.DataFrame, blocked: BlockedProjects, lead_on: pd.DataFrame, alerts: pd.DataFrame, performance: pd.DataFrame, spot: pd.DataFrame, thin_cover: pd.DataFrame, supply_zone: pd.DataFrame, customer: pd.DataFrame, context: halvaro.core.access.Context) -> SupplyAnswer
```

Use this when you need the supply side of the supply strain question assembled for the items and zones that the grid side of the answer in halvaro-grid hands over.

Composes the outputs of this module for the item list and the zone list (keys only). Each frame is cut to the items: stock_on (itm_key), open_po_lines (itm_key), blocked_projects (its `items` frame), lead_time_on and its alerts, spot_orders, the thin cover frame (as passed, one row per zone key or all), and the supplier_performance_window rows of the suppliers of those items (the suppliers in the lead time frame). The customers are those of the zones (gis.supply_zone.cus_key) with their names. An item or a zone that is not in any frame is not an error (an empty cut is honest). Nothing is computed here: no stock, order or price is calculated, the frames are only cut and joined.

Args:
    items: The item keys as a list of text, from the grid side of the answer (halvaro-grid).
    zones: The zone keys as a list of text, from the grid side of the answer (halvaro-grid); each must be in gis.supply_zone.
    stock: Output of stock_on; it needs itm_key.
    open_lines: Output of open_po_lines; it needs itm_key.
    blocked: Output of blocked_projects; its `items` frame needs itm_key.
    lead_on: Output of lead_time_on; it needs itm_key, and sup_key to pick the suppliers.
    alerts: Output of lead_time_alerts; it needs itm_key.
    performance: Output of supplier_performance_window or the stored table; it needs sup_key.
    spot: Output of spot_orders; it needs itm_key.
    thin_cover: Output of elements_per_spare_unit, passed through; when it has zone_key, rows of other zones are dropped and the row for all zones (null zone_key) is kept.
    supply_zone: The gis.supply_zone frame; it needs zone_key and cus_key.
    customer: The crm.customer frame; it needs cus_key (one row per customer) and name.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A SupplyAnswer tuple with the frames stock, open_lines, blocked_projects, lead_times, alerts, performance, spot_orders, thin_cover and customers (zone_key, cus_key, name, sorted by zone_key), and the sorted tuples items and zones.

Raises:
    FrameError: items or zones is a frame, a mapping or None, or holds a key that is not text; a frame is not a DataFrame, has duplicate column names or lacks a needed column; a zone is not in gis.supply_zone; crm.customer has more than one row for a customer.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import supply_strain_answer
    >>> from halvaro.delivery.supply import BlockedProjects
    >>> ctx = Context(stage="month12", role="analyst")
    >>> by_item = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [0.0, 5.0]})
    >>> lead = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900002"], "itm_key": ["ITM-900001", "ITM-900002"]})
    >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900002"], "on_time_percent": [60.0, 95.0]})
    >>> zone = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0002"], "cus_key": ["CUS-900001", "CUS-900002"]})
    >>> cus = pd.DataFrame({"cus_key": ["CUS-900001", "CUS-900002"], "name": ["Customer A", "Customer B"]})
    >>> empty = by_item.iloc[:0]
    >>> a = supply_strain_answer(["ITM-900001"], ["ZONE-0001"], stock=by_item, open_lines=empty, blocked=BlockedProjects(empty, empty), lead_on=lead, alerts=empty,
    ...                      performance=perf, spot=empty, thin_cover=pd.DataFrame({"zone_key": [None]}), supply_zone=zone, customer=cus, context=ctx)
    >>> a.stock["itm_key"].tolist(), a.performance["sup_key"].tolist(), a.customers["name"].tolist()
    (['ITM-900001'], ['SUP-900001'], ['Customer A'])

## Source columns

- `inventory.stock_level.on_hand`
- `procurement.po_line.itm_key`
- `inventory.lead_time.lead_time_weeks`
- `procurement.supplier_performance.sup_key`
- `gis.supply_zone.zone_key`
- `gis.supply_zone.cus_key`
- `crm.customer.cus_key`
- `crm.customer.name`
