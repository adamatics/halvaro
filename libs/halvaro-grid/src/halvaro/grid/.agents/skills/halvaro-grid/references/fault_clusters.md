# fault_clusters

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import fault_clusters`.

```python
fault_clusters(density: pd.DataFrame, grid_element: pd.DataFrame, *, link_m: float = 300.0, min_faults: int = 8, buffer_m: float = 150.0, min_element_faults: int = 1, context: halvaro.core.access.Context) -> list[FaultCluster]
```

Use this when you need the spatial clusters of faulted elements found from the output of fault_density.

Elements with a fault in the window are linked when their midpoints are at most `link_m` apart (single linkage, PROPOSED 300 m); a component with at least `min_faults` faults (PROPOSED 8) is a cluster. Its
hull (convex, buffered by `buffer_m`, PROPOSED 150 m) selects the members: in service elements of the faulted types of the cluster that exist in the window (they are in the density frame). Only elements
with at least `min_element_faults` faults in the window (PROPOSED 1) are linked. The rule is policy.grid.fault_cluster (needed, LOW) and the distances are not calibrated by the data: with dense faults
single linkage can chain a whole zone into one component that is much larger than a cluster; a smaller link_m with a higher min_element_faults keeps the components small (the measurement is in
the notes of the closed generator repository). The age route (age_group_clusters) groups elements by install year instead.

Args:
    density: The output of fault_density; it needs the columns net_key, element_type, lon, lat and n_faults.
    grid_element: The gis.grid_element table; it needs the columns net_key, element_type, status, lon and lat.
    link_m: Linking distance in metres (PROPOSED 300); above zero.
    min_faults: Smallest number of faults of a cluster (PROPOSED 8); a whole number, one or more.
    buffer_m: Distance in metres by which the hull is buffered to select members (PROPOSED 150); zero or more.
    min_element_faults: Smallest number of faults for an element to be linked (PROPOSED 1); a whole number, one or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A list of FaultCluster, sorted by size (faults, then first net_key), with cluster_id (from 1), centre_lon and centre_lat (the mean of the faulted members), n_faulted (elements with a fault in the
    window), n_faults, n_members (in service elements of the faulted types inside the buffered hull), members (their net_keys, sorted), hull (longitude and latitude corners) and radius_m (largest
    distance of a faulted element to the centre). The list is empty when no element reaches min_element_faults.

Raises:
    FrameError: a table lacks a needed column; link_m or buffer_m is not a number of metres (or link_m is zero); min_faults or min_element_faults is not a whole number of one or more; lon or lat is not
        a finite number.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import fault_clusters
    >>> ctx = Context(stage="month12", role="analyst")
    >>> dens = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "element_type": ["cable"] * 3, "lon": [9.5000, 9.5005, 9.6000],
    ...                      "lat": [53.5, 53.5, 53.6], "n_faults": [3, 2, 1]})
    >>> ge = dens.assign(status="in_service")
    >>> cl = fault_clusters(dens, ge, min_faults=4, context=ctx)
    >>> len(cl), cl[0].n_faults, list(cl[0].members)
    (1, 5, ['NET-900001', 'NET-900002'])

## Source columns

- `service.fault_event.net_key`
- `gis.grid_element.net_key`
- `gis.grid_element.element_type`
- `gis.grid_element.status`
- `gis.grid_element.lon`
- `gis.grid_element.lat`
