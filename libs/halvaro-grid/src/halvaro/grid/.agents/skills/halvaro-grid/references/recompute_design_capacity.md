# recompute_design_capacity

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import recompute_design_capacity`.

```python
recompute_design_capacity(grid_element: pd.DataFrame, *, heat_diversity: float = 0.6, electric_diversity: float = 0.45, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to recompute the design capacity of each zone from the grid elements in service, with the heat and electric diversity applied.

Heat exchanger stations (kW) times the heat diversity give MW_th, transformer stations (kVA) times the electric diversity give MVA. Elements that are not in service count for nothing. The stored value is rounded to 0.1.
PROPOSED: the diversities 0.6 and 0.45 (cfg:gis.yaml#defaults, no fact id).

Args:
    grid_element: The gis.grid_element table, with the columns zone_key, element_type, status, rated_capacity and capacity_unit.
    heat_diversity: Diversity factor of the heat zones, a number in (0, 1]; default 0.6 (PROPOSED).
    electric_diversity: Diversity factor of the electric zones, a number in (0, 1]; default 0.45 (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns zone_key, network_type, design_capacity (three decimals), design_capacity_unit, n_elements, sorted by zone_key.

Raises:
    FrameError: grid_element is not a DataFrame or lacks one of its columns; a diversity is not a number in (0, 1]; an element in service has no zone_key; a heat exchanger station is not rated in kW or a transformer station not in kVA; an element in service has a null or negative rated_capacity.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import recompute_design_capacity
    >>> ctx = Context(stage="month12", role="analyst")
    >>> elements = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "element_type": ["heat_exchanger_station"] * 3,
    ...                          "status": ["in_service", "in_service", "planned"], "rated_capacity": [1000.0, 500.0, 9000.0], "capacity_unit": ["kW"] * 3})
    >>> recompute_design_capacity(elements, context=ctx).to_dict("records")
    [{'zone_key': 'ZONE-0001', 'network_type': 'heat', 'design_capacity': 0.9, 'design_capacity_unit': 'MW_th', 'n_elements': 2}]

## Source columns

- `gis.grid_element.zone_key`
- `gis.grid_element.element_type`
- `gis.grid_element.status`
- `gis.grid_element.rated_capacity`
- `gis.grid_element.capacity_unit`
