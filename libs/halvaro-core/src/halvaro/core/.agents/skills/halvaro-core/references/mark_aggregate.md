# mark_aggregate

```python
mark_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> RestrictedAggregate
```

Use this when you have checked an aggregate of a restricted measure and want to hand it on marked as safe to show.

Rule: the frame is first checked with assert_aggregate (same arguments, same refusals); when it passes, it is wrapped unchanged together with the column name, the group columns as a tuple and min_group.

## Args

frame: The aggregate, one row per group.
restricted_column: The column that holds the restricted measure; it must be a column of the frame.
group_columns: The columns the aggregate is grouped by. Optional; kept as a tuple in the result.
min_group: The smallest number of people a group may have. Optional; kept in the result.
count_column: The column with the number of people per group. Needed when min_group is given.

## Returns

RestrictedAggregate: a record with the fields frame, restricted_column, group_columns (a tuple) and min_group.

## Raises

FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import mark_aggregate
>>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 2]})
>>> marked = mark_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
>>> marked.restricted_column, marked.group_columns, marked.min_group, len(marked.frame)
('measure', ('grade',), 2, 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
