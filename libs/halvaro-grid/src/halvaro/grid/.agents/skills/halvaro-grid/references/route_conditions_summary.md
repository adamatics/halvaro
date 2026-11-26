# route_conditions_summary

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import route_conditions_summary`.

```python
route_conditions_summary(route_shares: pd.DataFrame, *, poor_bearing: tuple[str, ...] = ('poor',), high_groundwater: tuple[str, ...] = ('high',), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to know how much of each route lies on poor bearing capacity or high groundwater and whether it crosses a polygon recorded on site.

Share of each route on poor bearing capacity and on high groundwater (of the route length) and whether it crosses either, and a polygon recorded on site. `poor_bearing` and `high_groundwater` are the PROPOSED
values of the two attributes.

Args:
    route_shares: The output of route_ground_intersection; it needs the columns prj_key, version, metres, route_length_m, bearing_capacity, groundwater and survey_kind.
    poor_bearing: The bearing_capacity values that count as poor (PROPOSED ("poor",)); a tuple or list, not a plain string.
    high_groundwater: The groundwater values that count as high (PROPOSED ("high",)); a tuple or list, not a plain string.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with one row per route version and the columns prj_key, version, poor_bearing_m, poor_bearing_share, high_groundwater_m, high_groundwater_share (both of the route length),
    crosses_poor_bearing, crosses_high_groundwater and crosses_site_observation (polygons whose survey_kind says they were recorded on site, not by a borehole survey). It is empty when route_shares is empty.

Raises:
    FrameError: route_shares lacks a needed column; poor_bearing or high_groundwater is not a tuple or list of values.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import route_conditions_summary
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rs = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "version": [1, 1], "metres": [20.0, 30.0], "route_length_m": [100.0, 100.0],
    ...                    "bearing_capacity": ["poor", "good"], "groundwater": ["low", "high"], "survey_kind": ["survey", "survey"]})
    >>> out = route_conditions_summary(rs, context=ctx)
    >>> out[["poor_bearing_share", "high_groundwater_share", "crosses_site_observation"]].to_dict("records")
    [{'poor_bearing_share': 0.2, 'high_groundwater_share': 0.3, 'crosses_site_observation': False}]

## Source columns

- `gis.ground_condition.bearing_capacity`
- `gis.ground_condition.groundwater`
- `gis.ground_condition.survey_kind`
