# asof_join

```python
asof_join(left: pd.DataFrame, right: pd.DataFrame, date_column: str, key: str | Sequence[str], valid_from: str = 'valid_from', valid_to: str = 'valid_to', suffix: str = '_r') -> pd.DataFrame
```

Use this when you need to attach to each row the version of an effective dated table that was valid on the row's date.

Rule: every left row keeps its place. It gets the right row with the same key whose valid_from is the latest on or before the left date, provided its valid_to is empty or on or after that date; otherwise the right columns are empty. A left date written YYYY-MM counts as the first day of that month. The right frame must have no overlapping, reversed or doubly open rows; gaps are allowed and give empty right columns.

## Args

left: The table that needs the lookup, one row per event.
right: The effective dated table, one row per version, with the two date columns.
date_column: Name of the column in left that holds the date, a date or a YYYY-MM period text.
key: Column name, or list of column names, that exist in both frames and identify the thing.
valid_from: Name of the start column of right. Default "valid_from".
valid_to: Name of the end column of right; empty means open. Default "valid_to".
suffix: Added to the name of a right column that has the same name as a left column (the key columns excepted). Default "_r".

## Returns

pandas.DataFrame: the columns of left in their order, then the other columns of right (including its valid_from and valid_to), one row per left row in the order of left with a fresh index.

## Raises

PeriodError: the right frame has overlapping, reversed or doubly open rows.
FrameError: right lacks the valid_from or valid_to column.
KeyError: date_column or a key column is missing from left, or a key column is missing from right.
FrameError: the left date column contains a null.
ValueError: the dates of the left column or of the date columns of right are text that is not a date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import asof_join
>>> left = pd.DataFrame({"k": ["A", "A", "B"], "month": ["2026-02", "2026-04", "2026-02"]})
>>> right = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-03-01"], "valid_to": ["2026-02-28", None], "rate": [10, 20]})
>>> asof_join(left, right, "month", "k")["rate"].tolist()
[10.0, 20.0, nan]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
