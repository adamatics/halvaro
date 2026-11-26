# fault_density

Module `halvaro.grid.spatial`. Import: `from halvaro.grid import fault_density`.

```python
fault_density(fault_event: pd.DataFrame, grid_element: pd.DataFrame, window_start: DateLike, window_end: DateLike, *, cell_m: float = 500.0, in_service: str | None = 'in_service', context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the faults per element and month of each element in a window, with the planar grid cell of each element.

Faults per element in a window (both days inclusive: PROPOSED policy.grid.winter_window, December to February), for the elements that were commissioned by the end of the window and, when the frame has a
`status` column, are `in_service` (planned or under construction elements do not exist yet, T18; pass in_service=None to keep every status), with a planar grid cell of `cell_m` metres (PROPOSED 500).
An element without a commissioning date counts as commissioned. Elements with no fault are listed with zero. A fault of an element that is not in grid_element raises FrameError.

Args:
    fault_event: The service.fault_event table; it needs the columns net_key and fault_ts.
    grid_element: The gis.grid_element table; it needs the columns net_key, element_type, zone_key, lon, lat and commissioned_date, and status when in_service is used.
    window_start: First day of the window (inclusive), a date or timestamp.
    window_end: Last day of the window (inclusive), a date or timestamp, not before window_start.
    cell_m: Edge of a planar grid cell in metres (PROPOSED 500); a positive number.
    in_service: The status value an element must have (default "in_service"); None keeps every status.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame sorted by net_key with the columns net_key, element_type, zone_key, lon, lat, cell_x, cell_y, n_faults, months (the part of the window the element existed, in months of 30.4375 days),
    faults_per_month (null when months is zero) and cell_faults (faults of all listed elements in the cell).

Raises:
    FrameError: a table lacks a needed column; cell_m is not a positive number; the window is not a (start, end) pair of dates in order; gis.grid_element has more than one row for a net_key; a faulted
        element is not in gis.grid_element; a timestamp or date cannot be read; lon or lat is not a finite number.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import fault_density
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ev = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "fault_ts": ["2024-01-05T10:00:00", "2024-01-20T10:00:00"]})
    >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "element_type": ["cable", "cable"], "zone_key": ["ZONE-0001", "ZONE-0001"],
    ...                    "lon": [9.50, 9.51], "lat": [53.50, 53.51], "commissioned_date": ["2000-01-01", "2001-01-01"], "status": ["in_service", "in_service"]})
    >>> out = fault_density(ev, ge, "2024-01-01", "2024-02-29", context=ctx)
    >>> out["n_faults"].tolist()
    [2, 0]
    >>> out["months"].round(1).tolist()
    [2.0, 2.0]

## Source columns

- `service.fault_event.net_key`
- `service.fault_event.fault_ts`
- `gis.grid_element.net_key`
- `gis.grid_element.element_type`
- `gis.grid_element.zone_key`
- `gis.grid_element.lon`
- `gis.grid_element.lat`
- `gis.grid_element.commissioned_date`
- `gis.grid_element.status`
