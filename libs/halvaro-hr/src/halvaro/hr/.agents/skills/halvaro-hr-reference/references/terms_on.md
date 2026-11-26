# terms_on

```python
terms_on(term: pd.DataFrame, as_of: dt.date) -> pd.DataFrame
```

Use this when you need the one employment term that is valid on a date for each person, without the restricted pay column.

Rule: a term is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. The org layer never returns a restricted column, so the pay column is dropped from the result.

## Args

term: The employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
as_of: The date.

## Returns

pandas.DataFrame: one row per person with a term valid on the date, the columns of the frame except the restricted ones.

## Raises

FrameError: the frame lacks emp_key, valid_from or valid_to.
AmbiguousKey: one person has two terms valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import terms_on
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2025-01-01", "2026-01-01"],
...                      "valid_to": ["2025-12-31", None], "team_key": ["TEAM-01", "TEAM-02"]})
>>> terms_on(term, dt.date(2026, 6, 1))[["emp_key", "team_key"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'team_key': 'TEAM-02'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`.
