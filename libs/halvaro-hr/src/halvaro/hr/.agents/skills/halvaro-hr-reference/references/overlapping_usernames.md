# overlapping_usernames

```python
overlapping_usernames(index: pd.DataFrame) -> list[str]
```

Use this when you want to check that no username was held by two holders on overlapping dates.

Rule: a username is never reused, so the list is expected to be empty.

## Args

index: The output of build_username_index.

## Returns

list: the usernames that map to different holders on overlapping dates, sorted; empty when the index is clean.

## Raises

FrameError: the index lacks a column or a date is not a date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, overlapping_usernames
>>> history = pd.DataFrame({"username": ["ab", "ab"], "emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2024-01-01", "2024-06-01"], "valid_to": [None, None]})
>>> pool = pd.DataFrame(columns=["account_name", "team_key", "valid_from", "valid_to"])
>>> overlapping_usernames(build_username_index(history, pool))
['ab']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.emp_key`, `hr.username_history.username`, `hr.username_history.valid_from`, `hr.username_history.valid_to`.
