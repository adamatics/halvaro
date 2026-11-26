# rows_on

```python
rows_on(frame: pd.DataFrame, on: dt.date, key: str | Sequence[str] | None = None, valid_from: str = 'valid_from', valid_to: str = 'valid_to') -> pd.DataFrame
```

Use this when a table has effective dating (valid_from, valid_to) and you need the rows that are valid on one date.

Rule: a row is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. With key, two valid rows of the same key are refused instead of both being returned.

## Args

frame: The table, one row per version, with the two date columns.
on: The date.
key: Column name, or list of column names, that identify the thing the rows are versions of. Optional; without it no check for two valid rows is made.
valid_from: Name of the start column. Default "valid_from".
valid_to: Name of the end column; empty means open. Default "valid_to".

## Returns

pandas.DataFrame: the rows of the frame that are valid on the date, in the order of the frame.

## Raises

FrameError: a date column is missing from the frame.
AmbiguousKey: key is given and two rows with the same key are valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import rows_on
>>> versions = pd.DataFrame({"k": ["A", "A", "B"], "valid_from": ["2026-01-01", "2026-02-01", "2026-01-01"], "valid_to": ["2026-12-31", None, None]})
>>> rows_on(versions, dt.date(2026, 1, 15))["k"].tolist()
['A', 'B']
>>> rows_on(versions, dt.date(2026, 3, 1), key="k")
Traceback (most recent call last):
...
halvaro.core.errors.AmbiguousKey: Key A matches 2 candidates: valid_from=2026-01-01, valid_from=2026-02-01. Pass a date or a more specific key.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
