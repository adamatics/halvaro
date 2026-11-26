# suppress_small_cells

```python
suppress_small_cells(table: pd.DataFrame, value_columns: str | Sequence[str], *, count_columns: Sequence[str] = ('n_women', 'n_men'), minimum_group: int = 8) -> pd.DataFrame
```

Use this when you publish a gap table and must hide the values of groups that are too small.

Rule: in a row where any count is under minimum_group (proposed 8) or missing, the value columns are set to null; the flag becomes suppressed, the rank empty and the standard error null where those columns exist. The column suppressed only turns on, so suppressing twice gives the same table.

## Args

table: The gap table with the value columns and the count columns.
value_columns: One column name or a list of names whose values are hidden for a small group.
count_columns: The columns with the group sizes. Default n_women and n_men.
minimum_group: The smallest group size that may be shown. Default 8 (proposed).

## Returns

pandas.DataFrame: a copy of the table with the small groups hidden and a boolean column suppressed.

## Raises

FrameError: the table lacks a value column or a count column.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import suppress_small_cells
>>> table = pd.DataFrame({"group": ["a", "b"], "n_women": [10, 3], "n_men": [12, 9], "gap_pct": [1.5, 2.5]})
>>> suppress_small_cells(table, ["gap_pct"])[["group", "gap_pct", "suppressed"]].astype(str).values.tolist()
[['a', '1.5', 'False'], ['b', 'nan', 'True']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
