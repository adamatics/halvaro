# majority_soil

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import majority_soil`.

```python
majority_soil(route_shares: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the soil class with the most metres on each route version, from the output of route_ground_intersection.

The soil class with most metres per route version and its share of the covered metres (the generator's rule: ties go to the class name that sorts first).

Args:
    route_shares: The output of route_ground_intersection; it needs the columns prj_key, version, soil_class, metres and route_length_m.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with one row per route version and the columns prj_key, version, soil_class, share (of covered metres), share_of_route and covered_share_of_route (covered metres over the route length). It is
    empty when route_shares is empty.

Raises:
    FrameError: route_shares lacks a needed column.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import majority_soil
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rs = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "version": [1, 1], "soil_class": ["clay", "sand"], "metres": [30.0, 10.0], "route_length_m": [100.0, 100.0]})
    >>> out = majority_soil(rs, context=ctx)
    >>> out[["soil_class", "share", "share_of_route", "covered_share_of_route"]].to_dict("records")
    [{'soil_class': 'clay', 'share': 0.75, 'share_of_route': 0.3, 'covered_share_of_route': 0.4}]

## Source columns

- `gis.project_area.prj_key`
- `gis.ground_condition.soil_class`
