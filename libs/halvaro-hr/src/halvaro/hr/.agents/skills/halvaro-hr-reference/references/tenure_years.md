# tenure_years

```python
tenure_years(employee: pd.DataFrame, as_of: dt.date, days_per_year: float = 365.25) -> pd.Series
```

Use this when you need the years of service of each person on a date.

Rule: (date minus hire_date) in days over days_per_year. A leaver is measured to the leave date. The value is NaN before the hire date and when the leave date is before the hire date.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
as_of: The date.
days_per_year: Days in a year for the division. Default 365.25. Must be positive.

## Returns

pandas.Series: years of service, named tenure_years and indexed by emp_key.

## Raises

FrameError: employee lacks a column or has duplicate emp_key values, or days_per_year is not positive.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import tenure_years
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000003"], "hire_date": ["2020-01-01", "2027-01-01"], "leave_date": [None, None]})
>>> tenure_years(employee, dt.date(2026, 1, 1)).round(2).to_dict()
{'EMP-000001': 6.0, 'EMP-000003': nan}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`.
