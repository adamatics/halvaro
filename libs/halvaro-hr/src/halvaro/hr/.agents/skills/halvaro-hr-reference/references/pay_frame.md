# pay_frame

```python
pay_frame(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, as_of: dt.date, *, context: Context, bands_year: int = 2026) -> pd.DataFrame
```

Use this when you need the person frame on a date with the monthly full-time rate, tenure and position in the pay band; it is the input of every pay difference function.

Rule: the terms valid on the date, with rate_local = base_salary over fte; rate_dkk is rate_local for a DKK term and rate_local times the fixed EUR to DKK rate (a fact) for an EUR term. tenure_years is the days from hire_date to as_of over 365.25; compa is rate_local over the band midpoint in the currency of the term. base_salary itself is not returned. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning in attrs["warnings"] says that compa is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

employee: Employee frame with emp_key, gender, hire_date and legal_entity_key.
term: Employment term frame with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency and base_salary.
team: Team frame with team_key and dep_key.
grade: Grade frame with gra_key, level and the DKK and EUR band minimum and maximum.
as_of: The date the frame describes.
context: The caller; the role must be allowed to read pay (required keyword).
bands_year: The year the grade bands are set at. Default 2026 (proposed).

## Returns

pandas.DataFrame: one row per valid term with the employee, team and grade columns, rate_local, rate_dkk, tenure_years and compa, and warnings in attrs.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the term frame has no base_salary.
FrameError: a column is missing, a valid term has fte not above zero, a missing or infinite salary or a currency other than DKK and EUR, or a valid term has no employee, team or grade.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import pay_frame
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "hire_date": [dt.date(2020, 1, 1)], "legal_entity_key": ["LE-01"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": [dt.date(2020, 1, 1)], "valid_to": [None], "team_key": ["TEAM-1"], "grade_key": ["GRA-1"], "fte": [1.0],
...                       "currency": ["DKK"], "base_salary": [50000.0]})
>>> team = pd.DataFrame({"team_key": ["TEAM-1"], "dep_key": ["DEP-01"]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-1"], "level": [3], "band_min_dkk": [40000.0], "band_max_dkk": [60000.0], "band_min_eur": [5000.0], "band_max_eur": [8000.0]})
>>> frame = pay_frame(employee, term, team, grade, dt.date(2026, 6, 1), context=access)
>>> frame[["rate_dkk", "compa"]].values.tolist()
[[50000.0, 1.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.
