# headcount_on

```python
headcount_on(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, as_of: dt.date, level: str = 'department') -> pd.DataFrame
```

Use this when you need the number of active people and their full time equivalents on a date, by department, team or legal entity.

Rule: a person is active on the date when the hire date is on or before it and the leave date is empty or on or after it. The team and the fte come from the employment term valid on the date.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date, leave_date and legal_entity_key, one row per person.
term: Employment term frame (hr.employment_term).
team: Team frame (hr.team) with team_key and dep_key.
as_of: The date.
level: "department", "team" or "entity". Default "department".

## Returns

pandas.DataFrame: one row per department, team or entity with headcount and fte, sorted by the key.

## Raises

FrameError: the level is not allowed, a frame lacks a column, an active person has no term on the date, or a team is missing in the team frame.
AmbiguousKey: one person has two terms valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import headcount_on
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "hire_date": ["2020-01-01", "2027-01-01"],
...                          "leave_date": [None, None], "legal_entity_key": ["LE-01", "LE-01"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2020-01-01", "2027-01-01"], "valid_to": [None, None],
...                      "team_key": ["TEAM-01", "TEAM-01"], "fte": [1.0, 0.5]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"]})
>>> headcount_on(employee, term, team, dt.date(2026, 6, 1)).to_dict("records")
[{'dep_key': 'DEP-1', 'headcount': 1, 'fte': 1.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.team.dep_key`.
