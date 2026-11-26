# assert_aggregate

```python
assert_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> None
```

Use this when a frame holds an aggregate of a restricted measure (pay, birth date) and you must check that it names no person and has no group that is too small.

Rule: the frame is refused when any column or index level holds an EMP key in at least one value (text columns are read as text; numbers, dates and durations are skipped). When min_group is given, every row of count_column must be at least min_group, and a row with no count is refused as well. group_columns is not read by the check; it is only carried by mark_aggregate.

## Args

frame: The aggregate, one row per group.
restricted_column: The column that holds the restricted measure; it must be a column of the frame.
group_columns: The columns the aggregate is grouped by. Optional; not used by the check itself.
min_group: The smallest number of people a group may have. Optional; without it the group sizes are not checked.
count_column: The column with the number of people per group. Needed when min_group is given.

## Returns

None: nothing happens when the frame passes the guard.

## Raises

FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import assert_aggregate
>>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 1]})
>>> assert_aggregate(frame, "measure", ["grade"], min_group=1, count_column="people")
>>> assert_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
Traceback (most recent call last):
...
halvaro.core.errors.AggregateRefusal: 1 groups have fewer than 2 people or no count; suppress them or widen the grouping.
>>> by_person = pd.DataFrame({"emp_key": ["EMP-000001"], "measure": [10.0]})
>>> assert_aggregate(by_person, "measure")
Traceback (most recent call last):
...
halvaro.core.errors.AggregateRefusal: measure sits next to person keys in column(s) emp_key. Group by department, grade or similar and drop the person key.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
