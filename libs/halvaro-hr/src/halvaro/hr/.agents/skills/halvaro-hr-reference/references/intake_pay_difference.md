# intake_pay_difference

```python
intake_pay_difference(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8, context: Context | None = None) -> dict[str, Any]
```

Use this when you want to know whether the women hired from an intake date are paid differently from the men and from the other women of the same department.

Rule: the by-grade frame of intake_compa_by_grade, and an OLS of ln(rate_dkk) on a dummy for women hired from the intake date, a dummy for the other women, tenure, entity and grade, over the whole department. The estimates are 100 times (exp(b) minus 1): negative when the women earn less (the sign of a pay level, not of adjusted_gap). The intake estimate is NaN with suppressed True when fewer than minimum_group women (proposed 8) were hired from the intake date or fewer men are in the department; the estimate of the other women is NaN when they number fewer than minimum_group. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level, compa, rate_dkk, tenure_years and legal_entity_key.
dep: The department key (required).
hired_from: The first hire date of the intake (required: the caller decides which intake it asks about).
grades: The grade levels of the by-grade frame (required).
minimum_group: The smallest number of people per group. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

dict: by_grade (the intake_compa_by_grade frame), n_intake_women, n_other_women, n_men, intake_women_pct and its se, other_women_pct and its se (percent), suppressed (bool) and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, or the rate, entity, grade or tenure values are missing or not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import intake_pay_difference
>>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0],
...                         "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"]})
>>> result = intake_pay_difference(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), context=access)
>>> result["suppressed"], result["n_intake_women"], result["n_men"]
(True, 1, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.department.dep_code`.
