# check_contiguity

```python
check_contiguity(frame: pd.DataFrame, key: str | Sequence[str], valid_from: str = 'valid_from', valid_to: str = 'valid_to', convention: str = 'day_after', table: str = '') -> pd.DataFrame
```

Use this when a table has effective dating (valid_from, valid_to per key) and you need the rows that break the dating rules.

Rule: per key the rows are ordered by valid_from. A row is reversed when valid_to is before valid_from, two_open when a key has more than one open row (valid_to empty), open_not_last when an open row is followed by another row, overlap when the next row starts before the previous one ends, and gap when it starts later. With convention "day_after" the next row starts the day after valid_to; with "touching" it starts on the same day.

## Args

frame: The table, one row per version.
key: Column name, or list of column names, that identify the thing the rows are versions of.
valid_from: Name of the start column. Default "valid_from".
valid_to: Name of the end column; empty means open. Default "valid_to".
convention: "day_after" or "touching". Default "day_after".
table: A label written into the table column of the result, for example "hr.employment_term".

## Returns

pandas.DataFrame: one row per violation with the columns table, key, rule and detail; empty when the dating is clean.

## Raises

FrameError: the frame has no valid_from or valid_to column (the names are the arguments).
PeriodError: the convention is neither day_after nor touching.
ValueError: a date column holds text that is not a date (the parsing error of pandas, a ValueError).

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_contiguity
>>> frame = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-02-05"], "valid_to": ["2026-01-31", None]})
>>> check_contiguity(frame, "k")[["key", "rule", "detail"]].to_dict("records")
[{'key': 'A', 'rule': 'gap', 'detail': 'next row starts 2026-02-05, previous ends 2026-01-31'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
