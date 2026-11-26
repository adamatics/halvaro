# grid_strain_answer

Module `halvaro.grid.recipes`. Import: `from halvaro.grid import grid_strain_answer`.

```python
grid_strain_answer(strained: pd.DataFrame, zone_summary: pd.DataFrame, part_use: pd.DataFrame, critical_issued: pd.DataFrame, *, context: halvaro.core.access.Context) -> GridStrainAnswer
```

Use this when you need the grid side of the supply strain answer (strained elements, zone summary, part use) with the two key lists for the delivery answer.

Assemble the grid side of the supply strain answer: the strained elements (`strained_elements`), the zone summary (`zone_strain_summary`), the part use (`part_usage`), and the two key lists for the supply answer of halvaro-delivery: the critical items
that were issued (`itm_key` of `critical_spares_issued` with units above zero, sorted) and the zones of the summary (`zone_key`, sorted). The lists hold keys only. A critical item that was never issued is
not asked about. Elements whose strain is unknown stay unknown in `strained`. Nothing new is computed; the label 'synthetic data' is part of the answer.

Args:
    strained: The output of strained_elements; it needs the columns net_key, strained and load_strained.
    zone_summary: The output of zone_strain_summary; it needs the columns zone_key, n_elements and n_strained.
    part_use: The output of part_usage; it needs the columns itm_key and units.
    critical_issued: The output of critical_spares_issued; it needs the columns itm_key and units.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An GridStrainAnswer with the fields strained, zone_summary, part_use (frames with a fresh index), item_keys (sorted tuple of itm_key of the critical items with units above zero), zone_keys (sorted tuple of the zones of the summary) and labels (the tuple holding 'synthetic data').

Raises:
    FrameError: a piece is not a frame or lacks a needed column; a column name of the four frames contains the word stock, po, order, orders, price, cost, amount, money, credit or intent (split at underscores), so the delivery side never receives it from here; a null itm_key or zone_key.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import grid_strain_answer
    >>> ctx = Context(stage="month12", role="analyst")
    >>> st = pd.DataFrame({"net_key": ["NET-900001"], "strained": [True], "load_strained": [True]})
    >>> zs = pd.DataFrame({"zone_key": ["ZONE-0002", "ZONE-0001"], "n_elements": [3, 2], "n_strained": [1, 0]})
    >>> pu = pd.DataFrame({"itm_key": ["ITM-900001"], "units": [4]})
    >>> ci = pd.DataFrame({"itm_key": ["ITM-900002", "ITM-900001", "ITM-900003"], "units": [2, 5, 0]})
    >>> a = grid_strain_answer(st, zs, pu, ci, context=ctx)
    >>> a.item_keys, a.zone_keys
    (('ITM-900001', 'ITM-900002'), ('ZONE-0001', 'ZONE-0002'))

## Source columns

- `gis.grid_element.net_key`
- `gis.supply_zone.zone_key`
- `service.ticket_item_use.itm_key`
- `inventory.item.critical`
