# allocation_hours

```python
allocation_hours(allocation: pd.DataFrame, employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, as_of: dt.date | str | pd.Timestamp, *, hours_per_day: float = 7.4, leave_types: Sequence[str] | None = None) -> pd.DataFrame
```

Use this when you need the hours that each allocation stint stands for, split into the hours up to a date and the hours after it.

Rule: the percent of the stint divided by 100 times the availability hours of the person inside the stint (the rules of availability_hours). hours_before counts stint days up to and including the date, hours_after the days after it; after_now says that the stint has days after the date.

## Args

allocation: Allocation frame (hr.allocation) with emp_key, prj_key, start, end and percent; start and end must be dates.
employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
employment_term: Employment term frame (hr.employment_term).
leave_record: Leave frame (hr.leave_record).
team: Team frame (hr.team) with team_key and site_key.
as_of: The date that splits realised from planned hours.
hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
leave_types: The leave types that count as leave; None means all.

## Returns

pandas.DataFrame: the columns of the allocation frame plus availability_hours, hours, hours_before, hours_after, no_term_days and after_now.

## Raises

FrameError: a frame lacks a column, a stint has no start or end, a person of the allocations is not in hr.employee, or hours_per_day is not above zero and at most 24.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import allocation_hours
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001"], "prj_key": ["PRJ-1"], "start": ["2026-03-02"], "end": ["2026-03-06"], "percent": [50]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
>>> result = allocation_hours(allocation, employee, term, leave, team, dt.date(2026, 3, 4))
>>> result[["availability_hours", "hours", "hours_before", "hours_after", "after_now"]].to_dict("records")
[{'availability_hours': 29.6, 'hours': 14.8, 'hours_before': 7.4, 'hours_after': 7.4, 'after_now': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.allocation.emp_key`, `hr.allocation.prj_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.leave_record.start`, `hr.leave_record.end`.
