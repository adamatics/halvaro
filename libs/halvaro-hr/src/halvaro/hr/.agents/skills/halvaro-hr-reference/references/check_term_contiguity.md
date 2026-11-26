# check_term_contiguity

```python
check_term_contiguity(term: pd.DataFrame, employee: pd.DataFrame) -> pd.DataFrame
```

Use this when you check the employment term history of every person for gaps, overlaps and other breaks in the dating.

Rule: per person the terms are ordered by valid_from. The rules are reversed, gap, overlap, two_open, open_not_last, null_key, no_employee, hire_missing, leave_before_hire, no_terms, first_row (the first term does not start on the expected day: the hire date, or the start of the data window when the person was hired before it and still works), open_row and last_row_not_leave_date.

## Args

term: Employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; empty when the history is clean.

## Raises

FrameError: a frame lacks a column.
FactNotFound: the fact for the start of the data window is not known.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import check_term_contiguity
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "valid_from": ["2024-01-01", "2025-03-01"], "valid_to": ["2024-12-31", None]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2024-01-01"], "leave_date": [None]})
>>> check_term_contiguity(term, employee)["rule"].tolist()
['gap']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.window_start`.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.employee.hire_date`, `hr.employee.leave_date`.
