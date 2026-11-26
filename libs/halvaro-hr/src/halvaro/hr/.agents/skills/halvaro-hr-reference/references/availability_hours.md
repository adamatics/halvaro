# availability_hours

```python
availability_hours(employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, periods: Sequence[tuple[dt.date | str, dt.date | str]], *, hours_per_day: float = 7.4, leave_types: Sequence[str] | None = None) -> pd.DataFrame
```

Use this when you need the hours each person can work in each period: employed working days of the region, less leave, times the fte, times the hours of a day.

Rule: per period (a pair of dates, both included) the days on which the person is employed and which are working days of the region of the team's site; leave days are taken off; the rest times the fte of the term valid that day and times hours_per_day (PROPOSED default, world.staffing.hours_per_day). A person with no term on a day gives no hours there.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
employment_term: Employment term frame (hr.employment_term) with emp_key, valid_from, valid_to, team_key and fte.
leave_record: Leave frame (hr.leave_record) with emp_key, start, end and leave_type; an empty end is open.
team: Team frame (hr.team) with team_key and site_key.
periods: A list of (start, end) date pairs, both days included.
hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
leave_types: The leave types that count as leave; None means all.

## Returns

pandas.DataFrame with emp_key, period_start, period_end, region, working_days, leave_days, net_days and hours, sorted by person and period; a person with no employed working day in a period has no row.

## Raises

FrameError: a frame lacks a column, a date is not a date, hours_per_day is not above zero and at most 24, or a period is not a pair of dates.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import availability_hours
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
>>> week = [(dt.date(2026, 3, 2), dt.date(2026, 3, 6))]
>>> availability_hours(employee, term, leave, team, week)[["working_days", "leave_days", "net_days", "hours"]].to_dict("records")
[{'working_days': 5, 'leave_days': 1, 'net_days': 4, 'hours': 29.6}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.employment_term.team_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.leave_record.start`, `hr.leave_record.end`, `hr.leave_record.leave_type`, `hr.team.site_key`.
