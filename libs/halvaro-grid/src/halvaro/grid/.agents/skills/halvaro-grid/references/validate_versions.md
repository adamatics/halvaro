# validate_versions

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import validate_versions`.

```python
validate_versions(geometry_version: pd.DataFrame, grid_element: pd.DataFrame | None = None, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to check the geometry versions of the elements for overlaps, gaps and a wrong current version.

Violations (table, key, rule, detail) of the geometry versions: null_valid_from, reversed (valid_to before valid_from), overlap, gap (the next version must start the day after the previous ends),
open_not_last (an open end before a later version), no_current and several_current (is_current), current_not_open, and with grid_element current_start_mismatch (current_geometry_valid_from is the
start of the current version), element_without_version, version_without_element (a version of an element that is not in grid_element) and duplicate_element. The key is the net_key. A version
without valid_from is reported and left out of the other checks.

Args:
    geometry_version: The gis.geometry_version table; it needs the columns net_key, valid_from, valid_to and is_current (True or False in every row).
    grid_element: Optional gis.grid_element table with net_key and current_geometry_valid_from; when given, the checks against the elements are added.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The violations frame of halvaro.core (columns table, key, rule, detail), sorted by key; empty when the versions are consistent.

Raises:
    FrameError: a table lacks a needed column; a net_key is null; is_current is not True or False in every row; a date cannot be read.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import validate_versions
    >>> ctx = Context(stage="month12", role="analyst")
    >>> gv = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "valid_from": ["2000-01-01", "2010-01-01"], "valid_to": ["2009-12-31", None], "is_current": [False, True]})
    >>> len(validate_versions(gv, context=ctx))
    0
    >>> bad = gv.assign(valid_from=["2000-01-01", "2012-01-01"])
    >>> validate_versions(bad, context=ctx)["rule"].tolist()
    ['gap']

## Source columns

- `gis.geometry_version.net_key`
- `gis.geometry_version.valid_from`
- `gis.geometry_version.valid_to`
- `gis.geometry_version.geom`
- `gis.geometry_version.source`
- `gis.geometry_version.is_current`
- `gis.grid_element.net_key`
- `gis.grid_element.current_geometry_valid_from`
