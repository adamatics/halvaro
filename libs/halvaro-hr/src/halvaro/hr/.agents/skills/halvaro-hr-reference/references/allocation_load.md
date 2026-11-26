# allocation_load

```python
allocation_load(allocation: pd.DataFrame, limit: float | PolicyDefault = policy:policy.staffing.max_allocation_percent) -> pd.DataFrame
```

Use this when you need to see how loaded each person is over time: the allocation percents of all projects added up per day, as segments of constant load.

Rule: the percents of the allocations that cover a day are summed per person; neighbouring days with the same sum form one segment; days with no load are not listed. A load above the limit is flagged. The default limit is the fact policy.staffing.max_allocation_percent (status proposed); the frame then carries attrs["policy_status"]. An allocation with no end is open: its segment has an empty end.

## Args

allocation: Allocation frame (hr.allocation) with emp_key, start, end and percent (numbers of zero or more, no nulls).
limit: The largest accepted load in percent per person per day. Default the fact.

## Returns

pandas.DataFrame with emp_key, start, end (included), load and over_limit, sorted by person and start.

## Raises

FrameError: limit is not a number, an allocation has no emp_key or start, percent is not numeric and zero or more, an allocation ends before it starts, or an end date is in the year 2200 or later.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import allocation_load
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "prj_key": ["PRJ-1", "PRJ-2"], "start": ["2026-01-01", "2026-01-01"],
...                            "end": ["2026-01-31", "2026-01-15"], "percent": [60, 50]})
>>> allocation_load(allocation, limit=100)[["start", "end", "load", "over_limit"]].astype(str).values.tolist()
[['2026-01-01', '2026-01-15', '110.0', 'True'], ['2026-01-16', '2026-01-31', '60.0', 'False']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.max_allocation_percent`.

Source columns: `hr.allocation.emp_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`.
