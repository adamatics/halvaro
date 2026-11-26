# reduce_chunks

```python
reduce_chunks(chunks: Iterable[pd.DataFrame], by: str | Sequence[str], aggregations: Mapping[str, tuple[str, str]]) -> pd.DataFrame
```

Use this when the rows come as an iterable of frames (chunks) and you need grouped sums, counts, minima or maxima with the same result as one frame, without holding all rows at once.

Rule: each chunk is reduced on its own per group, then the partial results are combined (sum for sum and count, min of minima, max of maxima), so memory is one chunk plus one row per group. count counts the non null values. Groups with a null key are kept. The result is sorted by the by columns. With no by columns the result has one row over all chunks. An empty chunk adds nothing; when every chunk is empty the result has no rows.

## Args

chunks: The frames to reduce, for example read one after the other. At least one frame is needed; an empty frame is fine.
by: The column or columns to group by, a name or a list. An empty list gives one row over all rows.
aggregations: A mapping from an output column to a pair (input column, function), the function being sum, count, min or max.

## Returns

pandas.DataFrame: the by columns followed by the output columns in the order of aggregations, one row per group, sorted by the by columns.

## Raises

FrameError: chunks is one frame and not an iterable of frames; an aggregation is not a (column, function) pair; a function is none of sum, count, min and max; no chunk was given; or a chunk lacks a by column or an input column (the message names the chunk number).

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import reduce_chunks
>>> first = pd.DataFrame({"g": ["x", "x", "y"], "v": [1, 2, 3], "w": [1, 2, None]})
>>> second = pd.DataFrame({"g": ["y", "z"], "v": [10, 20], "w": [None, 4]})
>>> reduce_chunks([first, second], "g", {"total": ("v", "sum"), "n": ("w", "count")})
   g  total  n
0  x      3  2
1  y     13  0
2  z     20  1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
