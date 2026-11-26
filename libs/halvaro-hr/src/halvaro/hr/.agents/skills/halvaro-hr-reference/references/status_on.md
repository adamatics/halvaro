# status_on

```python
status_on(employee: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, unavailable_leave_types: Sequence[str] | PolicyDefault = policy:policy.staffing.unavailable_leave_types) -> pd.DataFrame
```

Use this when you need to know, for each person, whether they have left, are on leave, are not yet hired or are available on a date.

Rule: left when leave_date is before the date, not_hired when hire_date is after it, on_leave when a leave of an unavailable type covers it (a leave with no end is open), otherwise available. The leave types default to the fact policy.staffing.unavailable_leave_types (status proposed: the owner has not decided); when the default is used the frame carries attrs["policy_status"] with the fact status.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
leave_record: Leave frame (hr.leave_record) with emp_key, leave_type, start and end.
as_of: The date.
unavailable_leave_types: Leave types that make a person unavailable, as a list, or the default fact.

## Returns

pandas.DataFrame: one row per employee with emp_key, as_of and status (left, on_leave, not_hired or available).

## Raises

FrameError: a frame lacks a column, employee has duplicate emp_key values, or a person has no hire_date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import status_on
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"],
...                          "hire_date": ["2020-01-01", "2021-01-01", "2027-01-01", "2019-01-01"],
...                          "leave_date": [None, None, None, "2025-06-30"]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["parental"], "start": ["2026-03-01"], "end": [None]})
>>> status_on(employee, leave, dt.date(2026, 6, 1), unavailable_leave_types=["parental"])["status"].tolist()
['available', 'on_leave', 'not_hired', 'left']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.unavailable_leave_types`.

Source columns: `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.leave_record.emp_key`, `hr.leave_record.leave_type`, `hr.leave_record.start`, `hr.leave_record.end`.
