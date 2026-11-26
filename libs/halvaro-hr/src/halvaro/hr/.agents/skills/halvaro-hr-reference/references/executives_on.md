# executives_on

```python
executives_on(org: pd.DataFrame, role: pd.DataFrame, roles: Sequence[str]) -> Executives
```

Use this when you need the holders of named executive roles on the date of an org_on frame, and the roles that nobody holds.

Rule: the roles are named by the caller (hr keeps no list of executive roles). A holder is a person who is active in the org frame with one of the roles. Leave status is not applied. A vacant role is listed, an unknown role raises.

## Args

org: An org_on frame for one date, with emp_key, as_of, active, role_name, dep_code and team_key.
role: The role frame (hr.role) with the column name.
roles: One role name or a list of distinct role names.

## Returns

Executives: .frame has emp_key, role_name, dep_code and team_key sorted by role and person; .vacant lists the named roles that nobody holds.

## Raises

FrameError: a frame lacks a column or has duplicate column names, no role is named, the roles are not distinct text, a role is not in hr.role, or the org frame is not for exactly one date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import executives_on
>>> org = pd.DataFrame({"emp_key": ["EMP-000001"], "as_of": [pd.Timestamp("2026-06-01")], "active": [True],
...                     "role_name": ["Chief Financial Officer"], "dep_code": ["FIN"], "team_key": ["TEAM-01"]})
>>> role = pd.DataFrame({"name": ["Chief Financial Officer", "Director Service"]})
>>> result = executives_on(org, role, ["Chief Financial Officer", "Director Service"])
>>> result.frame["emp_key"].tolist(), result.vacant
(['EMP-000001'], ('Director Service',))
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.role.name`, `hr.department.dep_code`, `hr.employment_term.team_key`.
