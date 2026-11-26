# resolve_username

```python
resolve_username(index: pd.DataFrame, username: str, on: dt.date) -> dict[str, Any] | None
```

Use this when you have a username or a pool account name and a date and need to know who held it.

Rule: the index is effective dated; the row valid on the date gives the holder. A username is never reused, so two holders on one date is an error.

## Args

index: The output of build_username_index.
username: The username or pool account name.
on: The date.

## Returns

dict | None: {'kind': 'employee' or 'pool', 'emp_key', 'team_key'} (the key that does not apply is None), or None when nobody held the name on that date.

## Raises

FrameError: the index lacks a column or a date is not a date.
AmbiguousUsername: two holders on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, resolve_username
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> index = build_username_index(history, pool)
>>> resolve_username(index, "ab", dt.date(2026, 3, 1))
{'kind': 'employee', 'emp_key': 'EMP-000001', 'team_key': None}
>>> resolve_username(index, "ops-pool", dt.date(2026, 3, 1))["kind"], resolve_username(index, "nobody", dt.date(2026, 3, 1))
('pool', None)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.username`, `hr.shared_account.account_name`.
