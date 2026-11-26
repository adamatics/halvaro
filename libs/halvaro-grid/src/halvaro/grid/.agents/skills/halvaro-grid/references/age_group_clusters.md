# age_group_clusters

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import age_group_clusters`.

```python
age_group_clusters(grid_element: pd.DataFrame, *, decade: int, element_type: str, link_m: float = 300.0, min_size: int = 20, buffer_m: float = 150.0, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the spatial concentrations of one install decade and element type found without fault data.

The elements of `element_type` installed in the decade (for example 1960 for 1960 to 1969) are linked at `link_m` metres (PROPOSED 300, policy.grid.fault_cluster); a component of at least `min_size`
elements (PROPOSED 20) is a candidate. density_ratio is the elements of the same type per square kilometre of the hull buffered by `buffer_m` (150 m PROPOSED), over the same for all other elements of the
type in the cluster's most common zone, in or out of the decade, over the bounding box of the zone's elements of that type; it is null when the hull has no area.

Args:
    grid_element: The gis.grid_element table; it needs the columns net_key, install_year (numeric, null for elements not in service), element_type, zone_key, lon and lat.
    decade: First year of the decade, a whole number divisible by ten (for example 1960).
    element_type: The element type to look at.
    link_m: Linking distance in metres (PROPOSED 300); above zero.
    min_size: Smallest number of elements of a candidate (PROPOSED 20); a whole number, two or more.
    buffer_m: Distance in metres by which the hull is buffered (PROPOSED 150); above zero.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns cluster_id, zone_key (most common), n_elements, share_of_group, centre_lon, centre_lat, radius_m (largest distance to the centre) and density_ratio, sorted by n_elements
    (largest first) and cluster_id. It is empty when no element of the type was installed in the decade.

Raises:
    FrameError: grid_element lacks a needed column; decade is not a whole number divisible by ten; link_m or buffer_m is not a positive number; min_size is not a whole number of two or more; install_year is
        not numeric; lon or lat is not a finite number.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import age_group_clusters
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "install_year": [1961, 1965, 1998], "element_type": ["cable"] * 3,
    ...                    "zone_key": ["ZONE-0001"] * 3, "lon": [9.5000, 9.5005, 9.7], "lat": [53.5, 53.5, 53.7]})
    >>> out = age_group_clusters(ge, decade=1960, element_type="cable", min_size=2, context=ctx)
    >>> out["n_elements"].tolist(), out["zone_key"].tolist()
    ([2], ['ZONE-0001'])

## Source columns

- `gis.grid_element.net_key`
- `gis.grid_element.install_year`
- `gis.grid_element.element_type`
- `gis.grid_element.zone_key`
- `gis.grid_element.lon`
- `gis.grid_element.lat`
