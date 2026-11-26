# strained_elements

Module `halvaro.grid.assets`. Import: `from halvaro.grid import strained_elements`.

```python
strained_elements(element_peaks: pd.DataFrame, grid_element: pd.DataFrame, customer: pd.DataFrame | None = None, *, as_of: DateLike | None = None, load_percent: float = 90.0, bad_classes: tuple[str, ...] = ('D', 'E'), age_years: float = 40.0, types: tuple[str, ...] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to know which in service elements are strained by load or by age or condition class, with the reasons.

The age is that of `element_age` (two decimals), so an element one day short of `age_years` counts as age strained.

Strain per in service element: load strained (own valid peak at or above `load_percent` of the rated value, PROPOSED 90; unknown without a valid peak), age strained (condition class in
`bad_classes`, PROPOSED D and E, or age at least `age_years`, PROPOSED 40), and strained: true when either is true, false when the load is known to be below and the age is not strained, null (unknown) when the load is unknown and the age is not strained (T19: unknown is not 'not strained'). Reported separately: load_strained (null when unknown), age_strained, reasons.
The rule is policy.grid.strained_element (needed, LOW). Customer names come from the crm customer frame (cus_key, name) when given.

Args:
    element_peaks: The output of element_peak_load; it needs the columns net_key, peak_percent and valid.
    grid_element: The gis.grid_element table; it needs the columns net_key, element_type, status, install_year, condition_class, cus_key, zone_key and commissioned_date, one row per net_key.
    customer: The crm.customer table with the columns cus_key and name, or None for no customer names.
    as_of: The date the age is measured on; defaults to world.now.
    load_percent: The peak percent at or above which the load is strained, PROPOSED 90.0.
    bad_classes: The condition classes that count as strained, PROPOSED D and E; a tuple or list, not a string.
    age_years: The age in years at or above which the element is age strained, PROPOSED 40.0.
    types: Limits the element types (for the switchgear link of the supply strain question: substation and transformer_station); None keeps all types; a tuple or list, not a string.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame sorted by net_key with the columns net_key, element_type, zone_key, cus_key, customer_name, peak_percent, load_strained, age_years, condition_class, age_strained, strained, reasons.

Raises:
    FrameError: a needed column is missing; element_peaks or gis.grid_element has more than one row for a net_key; types or bad_classes is a string; a date or an install_year cannot be read.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import strained_elements
    >>> ctx = Context(stage="month12", role="analyst")
    >>> peaks = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "peak_percent": [95.0, 40.0], "valid": [True, True]})
    >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "element_type": ["cable"] * 3, "status": ["in_service"] * 2 + ["planned"],
    ...                    "install_year": [2015, 2015, 2015], "condition_class": ["B", "B", "B"], "cus_key": [None] * 3, "zone_key": ["ZONE-0001"] * 3, "commissioned_date": [None] * 3})
    >>> out = strained_elements(peaks, ge, as_of="2020-01-01", context=ctx)
    >>> out["net_key"].tolist(), out["strained"].tolist()
    (['NET-900001', 'NET-900002'], [True, False])

## Source columns

- `gis.grid_element.net_key`
- `gis.grid_element.element_type`
- `gis.grid_element.status`
- `gis.grid_element.install_year`
- `gis.grid_element.condition_class`
- `gis.grid_element.cus_key`
- `gis.grid_element.zone_key`
- `gis.grid_element.commissioned_date`
- `crm.customer.cus_key`
- `crm.customer.name`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
