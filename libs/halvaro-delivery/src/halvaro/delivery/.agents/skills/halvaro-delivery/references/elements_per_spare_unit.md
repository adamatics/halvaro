# elements_per_spare_unit

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import elements_per_spare_unit`.

```python
elements_per_spare_unit(stock: pd.DataFrame, grid_element: pd.DataFrame, *, items: Sequence[str], site: str, element_types: Sequence[str] = ('transformer_station', 'substation'), status: str = 'in_service', zone_keys: Sequence[str] | None = None, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how many installed grid elements share one spare switchgear unit in stock.

Installed grid elements that house the switchgear divided by the spare units of the items at the site (stock_on output, each balance counted from zero up, so a negative balance does not cancel a positive one). A higher elements_per_spare_unit is thinner cover; it is null when no spare unit is left. Element types and status are the parameter thin_cover of inventory.yaml (passed in, the grid frame is not read for config). Every zone counts unless `zone_keys` is passed: one row per zone key passed, or one row for all zones. The date is `as_of`, or the one `as_of` of the stock frame when it has one (a frame of several dates, or of another date than `as_of`, is refused); with a date, only elements with commissioned_date on or before it are installed (a null commissioned_date counts as not yet commissioned; `as_of` given and no commissioned_date column is refused). Without a date at all every element of the grid frame counts, as at the date of that frame.

Args:
    stock: Output of stock_on; it needs site_key, itm_key and on_hand (numeric without nulls), one row per site and item.
    grid_element: The gis.grid_element frame; it needs element_type, status and zone_key, and commissioned_date when a date is used.
    items: The item keys of the switchgear, a list or a single key.
    site: The site key as text whose stock is counted.
    element_types: The element types that house the switchgear (default transformer_station and substation).
    status: The status an element must have to count (default in_service).
    zone_keys: Optional zone keys as text; one row per zone. Without it one row covers all zones.
    as_of: Optional day to count elements on, a date, a Timestamp or an ISO text YYYY-MM-DD.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns zone_key (null for all zones), installed_elements, spare_units and elements_per_spare_unit (rounded to one decimal), one row per zone key passed or a single row.

Raises:
    FrameError: stock or grid_element is not a DataFrame, has duplicate column names or lacks a needed column; the stock frame is for another date than as_of, holds more than one date or has more than one row for a site and item; as_of is not an ISO date, is a number or has a time zone; site or status is not text; on_hand is not numeric or has nulls; as_of is given and grid_element lacks commissioned_date or holds a value there that is not a date; items, element_types or zone_keys is a frame, a mapping or None; a zone key is not text.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import elements_per_spare_unit
    >>> ctx = Context(stage="month12", role="analyst")
    >>> stock = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900001"], "itm_key": ["ITM-900001", "ITM-900002"], "on_hand": [2.0, -1.0]})
    >>> grid = pd.DataFrame({"element_type": ["substation", "substation", "substation", "cable"], "status": ["in_service"] * 4,
    ...                      "zone_key": ["ZONE-0001", "ZONE-0001", "ZONE-0002", "ZONE-0001"]})
    >>> r = elements_per_spare_unit(stock, grid, items=["ITM-900001", "ITM-900002"], site="SIT-900001", zone_keys=["ZONE-0001"], context=ctx)
    >>> r.to_dict("records")
    [{'zone_key': 'ZONE-0001', 'installed_elements': 2, 'spare_units': 2.0, 'elements_per_spare_unit': 1.0}]

## Source columns

- `inventory.stock_level.on_hand`
- `gis.grid_element.element_type`
- `gis.grid_element.status`
- `gis.grid_element.zone_key`
- `gis.grid_element.commissioned_date`
