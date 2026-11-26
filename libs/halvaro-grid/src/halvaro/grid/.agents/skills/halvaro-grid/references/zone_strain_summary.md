# zone_strain_summary

Module `halvaro.grid.assets`. Import: `from halvaro.grid import zone_strain_summary`.

```python
zone_strain_summary(strained: pd.DataFrame, supply_zone: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the counts of in service and strained elements by zone and customer, with the zone area.

Counts of in service elements and of strained elements (load, age, either) by zone and customer, with the zone area. Elements of a zone that is not in gis.supply_zone raise FrameError.
An element without a customer is counted under the customer key "-". strained_per_km2 is null without an area above zero.

Args:
    strained: The output of strained_elements; it needs the columns net_key, zone_key, cus_key, load_strained, age_strained and strained.
    supply_zone: The gis.supply_zone table; it needs the columns zone_key and area_km2, one row per zone_key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per zone and customer and the columns zone_key, cus_key, area_km2, n_elements, n_strained (true only), n_strained_unknown, n_load_strained,
    n_age_strained, n_load_unknown, strained_per_km2 (strained elements per square kilometre, rounded to three decimals).

Raises:
    FrameError: a needed column is missing; gis.supply_zone has more than one row for a zone_key; a zone of the elements is not in gis.supply_zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import zone_strain_summary
    >>> ctx = Context(stage="month12", role="analyst")
    >>> st = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "zone_key": ["ZONE-0001"] * 2, "cus_key": [None, None],
    ...                    "load_strained": [True, False], "age_strained": [False, False], "strained": [True, False]})
    >>> z = pd.DataFrame({"zone_key": ["ZONE-0001"], "area_km2": [4.0]})
    >>> zone_strain_summary(st, z, context=ctx)[["zone_key", "cus_key", "n_elements", "n_strained", "strained_per_km2"]].to_dict("records")
    [{'zone_key': 'ZONE-0001', 'cus_key': '-', 'n_elements': 2, 'n_strained': 1, 'strained_per_km2': 0.25}]

## Source columns

- `gis.supply_zone.zone_key`
- `gis.supply_zone.area_km2`
