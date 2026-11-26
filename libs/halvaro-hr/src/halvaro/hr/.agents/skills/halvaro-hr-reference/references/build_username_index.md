# build_username_index

```python
build_username_index(username_history: pd.DataFrame, shared_account: pd.DataFrame) -> pd.DataFrame
```

Use this when you need one effective dated list of usernames and pool accounts with their holders.

Rule: usernames of employees (kind employee) and pool accounts of teams (kind pool) are put in one frame; a null valid_to is open. The result is sorted by username and start date.

## Args

username_history: Frame hr.username_history with username, emp_key, valid_from and valid_to.
shared_account: Frame hr.shared_account with account_name, team_key, valid_from and valid_to.

## Returns

pandas.DataFrame with username, kind, holder, emp_key, team_key, valid_from and valid_to.

## Raises

FrameError: a column is missing, a row has no username, holder or start date, or a row ends before it starts.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import build_username_index
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> build_username_index(history, pool)[["username", "kind", "holder"]].to_dict("records")
[{'username': 'ab', 'kind': 'employee', 'holder': 'EMP-000001'}, {'username': 'ops-pool', 'kind': 'pool', 'holder': 'TEAM-01'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.username`, `hr.username_history.emp_key`, `hr.username_history.valid_from`, `hr.username_history.valid_to`, `hr.shared_account.account_name`, `hr.shared_account.team_key`, `hr.shared_account.valid_from`, `hr.shared_account.valid_to`.
