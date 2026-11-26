# zone_design_capacity

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import zone_design_capacity`.

```python
zone_design_capacity(supply_zone: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the design capacity of each zone with its unit, as stored in the supply zone table.

One row per zone with the design capacity and its unit as stored (MW_th for heat, MVA for electric).

Args:
    supply_zone: The gis.supply_zone table, with the columns zone_key, design_capacity and design_capacity_unit.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, design_capacity, design_capacity_unit, sorted by zone_key, one row per zone.

Raises:
    FrameError: supply_zone is not a DataFrame or lacks zone_key, design_capacity or design_capacity_unit; a zone_key appears in more than one row; a zone has a null design_capacity or unit, or a design_capacity that is not above zero.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import zone_design_capacity
    >>> ctx = Context(stage="month12", role="analyst")
    >>> zones = pd.DataFrame({"zone_key": ["ZONE-0002", "ZONE-0001"], "design_capacity": [40.0, 25.0], "design_capacity_unit": ["MW_th", "MVA"]})
    >>> zone_design_capacity(zones, context=ctx)["zone_key"].tolist()
    ['ZONE-0001', 'ZONE-0002']
    >>> zone_design_capacity(zones, context=ctx)["design_capacity"].tolist()
    [25.0, 40.0]

## Source columns

- `gis.supply_zone.zone_key`
- `gis.supply_zone.design_capacity`
- `gis.supply_zone.design_capacity_unit`
