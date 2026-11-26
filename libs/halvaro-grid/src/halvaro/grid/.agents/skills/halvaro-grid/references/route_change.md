# route_change

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import route_change`.

```python
route_change(project_area: pd.DataFrame, *, tolerance_m: float = 0.5, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the planned and as-built route length of each project with the version dates and the change, as the frame the app passes to halvaro-delivery.

Lengths are the stored length_m of the route versions (planned_route, as_built_route). A project with several planned or as-built versions raises (a re-plan needs an as-of date, which is not built).
A project with only an as-built route has a null planned length and changed False; a planned length of 0 gives a null delta_percent. PROPOSED: tolerance 0.5 m.

Args:
    project_area: The gis.project_area table; it needs the columns prj_key, kind, version, valid_from, valid_to and length_m.
    tolerance_m: Difference in metres above which the lengths count as changed (PROPOSED 0.5); a number of zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame sorted by prj_key with the columns prj_key, planned_length_m, as_built_length_m (null without an as-built route), delta_m, delta_percent, planned_valid_from, planned_valid_to,
    as_built_valid_from and changed (the lengths differ by more than tolerance_m).

Raises:
    FrameError: project_area lacks a needed column; tolerance_m is not a number of zero or more; a prj_key is null; length_m is not a number or is negative; a project has more than one planned or more
        than one as-built route version; a planned or as-built route version has no length_m; a date cannot be read.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import route_change
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pa = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "kind": ["planned_route", "as_built_route"], "version": [1, 1],
    ...                    "valid_from": ["2024-01-01", "2024-06-01"], "valid_to": [None, None], "length_m": [100.0, 110.0]})
    >>> out = route_change(pa, context=ctx)
    >>> out[["planned_length_m", "as_built_length_m", "delta_m", "delta_percent", "changed"]].to_dict("records")
    [{'planned_length_m': 100.0, 'as_built_length_m': 110.0, 'delta_m': 10.0, 'delta_percent': 10.0, 'changed': True}]

## Source columns

- `gis.project_area.prj_key`
- `gis.project_area.kind`
- `gis.project_area.version`
- `gis.project_area.valid_from`
- `gis.project_area.valid_to`
- `gis.project_area.length_m`
- `gis.project_area.geom`
