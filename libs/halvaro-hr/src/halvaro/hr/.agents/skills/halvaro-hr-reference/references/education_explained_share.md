# education_explained_share

```python
education_explained_share(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> dict[str, Any]
```

Use this when you want to know how much of the adjusted pay difference goes away once education is taken into account.

Rule: adjusted_gap without and with education_rank as a further control; explained_pp is gap without minus gap with, in percentage points. Everything is NaN with suppressed True below minimum_group people per gender (proposed 8). n_without_record counts people of the two genders with no education record. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame with education (the output of with_education).
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay and education. Optional keyword.

## Returns

dict: n_women, n_men, gap_without_education_pct, gap_with_education_pct, explained_pp (percent and percentage points), n_without_record and suppressed.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
StageRefusal: the stage does not yet allow the pay and education sources.
FrameError: education_rank or has_education_record is missing, or the frame fails adjusted_gap.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import education_explained_share
>>> people = pd.DataFrame({"gender": ["F", "M"], "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"], "level": [3, 3],
...                         "education_rank": [2, 3], "has_education_record": [True, False]})
>>> result = education_explained_share(people, context=access)
>>> result["suppressed"], result["n_without_record"]
(True, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `competence.education_record.level_rank`.
