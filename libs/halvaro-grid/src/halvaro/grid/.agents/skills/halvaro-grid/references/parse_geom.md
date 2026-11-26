# parse_geom

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import parse_geom`.

```python
parse_geom(geom: pd.Series, *, to_4326: bool = False, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the kind, size and bounding box of WKT geometries as a table.

The result has one row per geometry, with the index of the series. The coordinates are EPSG:25832 metres. to_4326 reprojects the bounding box corners to longitude and latitude and needs pyproj (an optional
dependency, imported only then).

Args:
    geom: A Series of WKT text (POINT, LINESTRING or POLYGON, for example gis.geometry_version.geom or gis.project_area.geom).
    to_4326: True to add the bounding box corners as lon_min, lat_min, lon_max and lat_max (needs pyproj); default False.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the index of geom and the columns kind, n_points, length_m (planar, lines only), area_m2 (polygons only), x_min, y_min, x_max, y_max (bounding box), and with to_4326 lon_min, lat_min,
    lon_max, lat_max.

Raises:
    FrameError: geom is not a Series; a text is not WKT of a POINT, LINESTRING or POLYGON (malformed, empty, MULTI*, an unclosed ring or a hole outside the shell); to_4326 is set and pyproj is not installed.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import parse_geom
    >>> ctx = Context(stage="month12", role="analyst")
    >>> g = pd.Series(["LINESTRING (0 0, 30 40)", "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"])
    >>> out = parse_geom(g, context=ctx)
    >>> out["kind"].tolist(), out["n_points"].tolist(), out["length_m"].tolist()[0], out["area_m2"].tolist()[1]
    (['LINESTRING', 'POLYGON'], [2, 5], 50.0, 100.0)

## Source columns

- `gis.geometry_version.geom`
- `gis.project_area.geom`
