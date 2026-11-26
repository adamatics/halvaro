# route_ground_intersection

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import route_ground_intersection`.

```python
route_ground_intersection(project_area: pd.DataFrame, ground_condition: pd.DataFrame, *, kind: str = 'planned_route', min_metres: float = 0.05, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the metres of each route that lie inside each ground polygon, with the soil class and the shares of the route.

One row per route version and polygon that it crosses (RouteSoilShare), planar in the metres of the WKT. `kind` picks planned_route (default) or as_built_route. A crossing shorter than `min_metres`
(PROPOSED 0.05 m: tiny planar float slivers appear where a route touches a polygon edge) is not a crossing. Polygons add up as the generator does: they overlap by less than 5 square metres.

Args:
    project_area: The gis.project_area table; it needs the columns prj_key, version, kind and geom (WKT LINESTRING for the routes).
    ground_condition: The gis.ground_condition table; it needs the columns area_id, geom (WKT POLYGON), soil_class, groundwater, bearing_capacity and survey_kind.
    kind: The route kind to use, planned_route (default) or as_built_route.
    min_metres: Smallest crossing length in metres that counts (PROPOSED 0.05); zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame sorted by prj_key, version and area_id with the columns prj_key, version, kind, area_id, soil_class, groundwater, bearing_capacity, survey_kind, metres, route_length_m, covered_m (metres of the
    route inside any polygon), share_of_covered (metres over covered metres, as the generator) and share_of_route (metres over the route length). It is empty when no route crosses a polygon.

Raises:
    FrameError: a table lacks a needed column; kind is not planned_route or as_built_route; min_metres is not a number of zero or more; gis.ground_condition has more than one row for an area_id;
        gis.project_area has more than one row for a project and version of this kind; a ground polygon is not a closed POLYGON or a route is not a LINESTRING; a geometry is not readable WKT.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import route_ground_intersection
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pa = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [1], "kind": ["planned_route"], "geom": ["LINESTRING (0 5, 100 5)"]})
    >>> gc = pd.DataFrame({"area_id": ["GC-900001"], "geom": ["POLYGON ((0 0, 40 0, 40 10, 0 10, 0 0))"], "soil_class": ["clay"], "groundwater": ["low"],
    ...                    "bearing_capacity": ["good"], "survey_kind": ["survey"]})
    >>> out = route_ground_intersection(pa, gc, context=ctx)
    >>> out[["metres", "route_length_m", "share_of_route"]].to_dict("records")
    [{'metres': 40.0, 'route_length_m': 100.0, 'share_of_route': 0.4}]

## Source columns

- `gis.project_area.prj_key`
- `gis.project_area.version`
- `gis.project_area.kind`
- `gis.project_area.geom`
- `gis.ground_condition.area_id`
- `gis.ground_condition.geom`
- `gis.ground_condition.soil_class`
- `gis.ground_condition.groundwater`
- `gis.ground_condition.bearing_capacity`
- `gis.ground_condition.survey_kind`
