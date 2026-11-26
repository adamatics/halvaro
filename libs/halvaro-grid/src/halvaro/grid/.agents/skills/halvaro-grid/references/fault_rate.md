# fault_rate

Module `halvaro.grid.faults`. Import: `from halvaro.grid import fault_rate`.

```python
fault_rate(fault_event: pd.DataFrame, group: Iterable[Any], *, baseline: tuple[str, str] = ('2023-01', '2025-10'), window: tuple[str, str] = ('2025-12', '2026-02'), grid_element: pd.DataFrame | None = None, context: halvaro.core.access.Context) -> FaultRateComparison
```

Use this when you need the faults per month of a group of elements against the rest, in the baseline months and in a window, and the spike ratio.

The months are calendar months (`baseline` and `window` are first and last months). PROPOSED: the window of policy.grid.winter_window and the baseline of the months the caller passes (the policy
text would take every month before the window); the defaults of both are placeholders the caller should replace with the months it means. A month without a fault counts as zero. Ratios (window over
baseline, and spike_vs_rest as group_ratio over rest_ratio) are null when the baseline mean is zero. With grid_element the number of elements of the group and of the rest (in service or not,
commissioned or not: a count of rows) is added and the window rates per element-month are given; without it the counts are -1 and the per-element rates are null. A baseline and a window that overlap,
a month pair out of order or not a pair of months, or an empty group raises FrameError.

Args:
    fault_event: The service.fault_event table; needs net_key and fault_ts.
    group: The net keys of the group (one key as text, or an iterable of keys); must not be empty.
    baseline: The (first, last) calendar months of the baseline, like "2024-01"; replace the default with the months you mean.
    window: The (first, last) calendar months of the comparison window, like "2024-04"; replace the default with the months you mean.
    grid_element: Optional gis.grid_element table with net_key, used to count the elements of the group and of the rest.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A FaultRateComparison with group_baseline_per_month, group_window_per_month, group_ratio, rest_baseline_per_month, rest_window_per_month, rest_ratio, spike_vs_rest, n_group_elements,
    n_rest_elements, group_window_per_element_month and rest_window_per_element_month.

Raises:
    FrameError: fault_event or grid_element lacks a needed column; the group is empty; a month pair is not a (first, last) pair of months or is out of order; the baseline and the window overlap; a fault has no time.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import fault_rate
    >>> ctx = Context(stage="month12", role="analyst")
    >>> fe = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900001", "NET-900001", "NET-900002", "NET-900002"],
    ...                    "fault_ts": ["2024-01-10", "2024-02-10", "2024-04-05", "2024-04-20", "2024-01-15", "2024-04-10"]})
    >>> r = fault_rate(fe, ["NET-900001"], baseline=("2024-01", "2024-02"), window=("2024-04", "2024-04"), context=ctx)
    >>> (r.group_baseline_per_month, r.group_window_per_month, r.group_ratio, r.spike_vs_rest)
    (1.0, 2.0, 2.0, 1.0)
    >>> r.n_group_elements
    -1

## Source columns

- `service.fault_event.net_key`
- `service.fault_event.fault_ts`
- `gis.grid_element.net_key`
