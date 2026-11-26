# resolve_assignments

```python
resolve_assignments(assignment: pd.DataFrame, index: pd.DataFrame, employee: pd.DataFrame, as_of: dt.date, asset_return_days: int | PolicyDefault = policy:policy.offboarding.asset_return_days, *, context: Context | None = None) -> Resolution
```

Use this when you check who holds each asset assignment: the person or team behind each username at the start of the assignment, and whether they still hold it until the end.

Rule: each assignment is resolved with the username index at its valid_from; unresolved and ambiguous rows are counted, not dropped. The kind follows assignment_type (named employee, pool_account pool, team no username but a pool_team_key). Further columns say whether the person was employed on the start day, held the username to the end or the leave date, and returned the asset after the leave date. asset_return_days defaults to the fact policy.offboarding.asset_return_days (status proposed); the diagnostics carry the value and its status.

## Args

assignment: Assignment frame (it-assets.assignment) with assignment_type, assigned_username, valid_from, valid_to and pool_team_key.
index: The output of build_username_index.
employee: Employee frame (hr.employee) with emp_key and leave_date.
as_of: The date the open assignments are judged on.
asset_return_days: Whole number of days an asset may be returned after the leave date. Default the fact.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

Resolution: .frame is the assignment frame with resolution, kind, emp_key, team_key, kind_ok, employed_on_start, leave_date, holds_to_end, returned_after_leave_days, open_after_leave and late_return; .diagnostics counts the cases.

## Raises

FrameError: asset_return_days is not a whole number, the assignment frame already has a column that is added, the employee frame has a person twice, assignment_type is unknown, or an assignment ends before it starts.
StageRefusal: a context is given and its stage does not hold the it-assets and hr sources.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, resolve_assignments
>>> assignment = pd.DataFrame({"assignment_type": ["named", "pool_account"], "assigned_username": ["ab", "ops-pool"], "valid_from": ["2025-01-01"] * 2, "valid_to": [None, None], "pool_team_key": [None, "TEAM-01"]})
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> result = resolve_assignments(assignment, build_username_index(history, pool), employee, dt.date(2026, 3, 1))
>>> result.frame["kind"].tolist(), result.diagnostics["resolved"], result.diagnostics["unresolved"]
(['employee', 'pool'], 2, 0)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.offboarding.asset_return_days`.

Source columns: `it-assets.assignment.assigned_username`, `it-assets.assignment.valid_from`, `it-assets.assignment.valid_to`, `it-assets.assignment.assignment_type`, `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`.
