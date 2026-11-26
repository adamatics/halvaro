# interval_join

```python
interval_join(points: pd.DataFrame, intervals: pd.DataFrame, *, point_ts: str = 'ts', start: str = 'from_ts', end: str = 'to_ts', key: str | Sequence[str] | None = None, inclusive_end: bool = True, how: str = 'left') -> pd.DataFrame
```

Use this when you need to attach to each point in time the interval that contains it, such as a sample and the quality event that covers it.

Rule: a point matches an interval when start <= ts and either end is empty (an open interval) or ts <= end (ts < end without inclusive_end). With key the key columns must also be equal. A point inside two intervals appears twice. With how "left" a point without an interval is kept with empty interval columns, with "inner" it is dropped. The join runs as one merge on the key (a cross join without key), so pass a chunk of points when there are millions.

## Args

points: The points, one row per point, with the timestamp column and the key columns.
intervals: The intervals, one row per interval, with the start and end columns and the key columns.
point_ts: Name of the timestamp column of points. Default "ts".
start: Name of the start column of intervals. Default "from_ts".
end: Name of the end column of intervals; empty means open. Default "to_ts".
key: Column name, or list of column names, present in both frames that must match as well. Optional.
inclusive_end: Whether a point at the end moment is inside. Default True.
how: "left" or "inner". Default "left".

## Returns

pandas.DataFrame: the columns of points, then the other columns of intervals (a name that is also a point column gets the suffix _iv), ordered by the position of the point and then the interval start, with a fresh index.

## Raises

FrameError: how is neither left nor inner, or a frame lacks a needed column.
TypeError: the timestamps cannot be compared, for example one side is time zone aware and the other is not.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import interval_join
>>> points = pd.DataFrame({"ts": [5, 12]})
>>> intervals = pd.DataFrame({"from_ts": [0], "to_ts": [5], "label": ["X"]})
>>> interval_join(points, intervals)["label"].tolist()
['X', nan]
>>> interval_join(points, intervals, inclusive_end=False, how="inner").shape[0]
0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
