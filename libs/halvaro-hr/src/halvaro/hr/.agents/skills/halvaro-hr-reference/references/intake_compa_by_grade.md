# intake_compa_by_grade

```python
intake_compa_by_grade(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8, context: Context | None = None) -> pd.DataFrame
```

Use this when you want to compare women and men hired from a given date in one department, grade by grade, on their position in the pay band.

Rule: among people in the department, hired on or after the date and in the given grades, the gap is (mean compa of women over mean compa of men minus 1) times 100; negative means women are below men. One row per grade and one row all for the pool. A row with fewer than minimum_group people (proposed 8) of one gender has NaN and suppressed True. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level and compa.
dep: The department key (required).
hired_from: The first hire date that counts (required: the caller decides which intake it asks about).
grades: The grade levels that count (required).
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

pandas.DataFrame: one row per grade plus all, with grade_level, n_women, n_men, women_vs_men_compa_pct (percent, NaN when suppressed), suppressed and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import intake_compa_by_grade
>>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0]})
>>> by_grade = intake_compa_by_grade(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), minimum_group=1, context=access)
>>> by_grade[["grade_level", "n_women", "n_men"]].values.tolist()
[[2, 1, 1], ['all', 1, 1]]
>>> round(float(by_grade["women_vs_men_compa_pct"].iloc[0]), 6)
-10.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.department.dep_code`.
