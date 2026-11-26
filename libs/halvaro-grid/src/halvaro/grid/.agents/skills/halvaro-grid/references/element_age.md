# element_age

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import element_age`.

```python
element_age(grid_element: pd.DataFrame, on: DateLike | None = None, *, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the age in years of each grid element on a date.

The age is in years (days over 365.25) from the commissioning date, else 1 January of the install year; it is null when the element is not in service (status in_service is matched exactly), has no install
year or is commissioned after the date. The date defaults to world.now. The age has two decimals, so a threshold on the age sees an element one day short of a whole year as that year.

Args:
    grid_element: The gis.grid_element table; it needs the columns install_year, status and commissioned_date.
    on: The date to measure the age on; defaults to world.now.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Series named age_years with the index of grid_element.

Raises:
    FrameError: grid_element lacks a needed column; on is not a date; a date cannot be read; install_year is not a number or not a whole year from 1800 to 2200.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import element_age
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ge = pd.DataFrame({"install_year": [2000, 2010, None], "status": ["in_service", "planned", "in_service"], "commissioned_date": ["2000-01-01", None, None]})
    >>> element_age(ge, "2020-01-01", context=ctx).round(1).tolist()
    [20.0, nan, nan]

## Source columns

- `gis.grid_element.install_year`
- `gis.grid_element.status`
- `gis.grid_element.commissioned_date`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
