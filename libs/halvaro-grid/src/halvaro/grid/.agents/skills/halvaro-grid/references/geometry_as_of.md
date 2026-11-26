# geometry_as_of

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import geometry_as_of`.

```python
geometry_as_of(geometry_version: pd.DataFrame, on: DateLike | None = None, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the geometry version of each element that was valid on a date.

A version is valid when valid_from <= date <= valid_to, an open end (null valid_to) valid. The date defaults to world.now. One row per element; an element with no version valid on the date (not yet built,
or planned from later) is not listed.

Args:
    geometry_version: The gis.geometry_version table; it needs the columns net_key, valid_from and valid_to.
    on: The date to look at; defaults to world.now.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The rows of geometry_version that are valid on the date (all its columns), sorted by net_key, with a fresh index.

Raises:
    FrameError: geometry_version lacks a needed column; a net_key or a valid_from is null; a date cannot be read or on is not a date; two versions of an element are valid on the same date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import geometry_as_of
    >>> ctx = Context(stage="month12", role="analyst")
    >>> gv = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "valid_from": ["2000-01-01", "2010-01-01"], "valid_to": ["2009-12-31", None], "geom": ["POINT (1 1)", "POINT (2 2)"]})
    >>> geometry_as_of(gv, "2005-06-01", context=ctx)["geom"].tolist()
    ['POINT (1 1)']

## Source columns

- `gis.geometry_version.net_key`
- `gis.geometry_version.valid_from`
- `gis.geometry_version.valid_to`
- `gis.geometry_version.geom`
- `gis.geometry_version.source`
- `gis.geometry_version.is_current`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
