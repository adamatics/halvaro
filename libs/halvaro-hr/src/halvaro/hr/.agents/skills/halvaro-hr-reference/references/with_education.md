# with_education

```python
with_education(frame: pd.DataFrame, education: pd.DataFrame, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you want the education level of each person next to the pay frame, so that it can be used as a control in the adjusted gap.

Rule: education_rank is the highest level_rank of the person's education records and 0 without a record; has_education_record says which. People without a record are kept, so the control treats no record as rank 0. The input is not changed.

## Args

frame: A pay frame (the output of pay_frame) with emp_key.
education: Education record frame (competence.education_record) with emp_key and level_rank.
context: The caller. Optional keyword.

## Returns

pandas.DataFrame: the frame plus education_rank and has_education_record.

## Raises

RestrictedColumnRefusal: a context is given and its role may not read pay.
StageRefusal: a context is given and its stage does not hold the pay and education sources.
FrameError: a column is missing, the pay frame already has one of the new columns, or level_rank is not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import with_education
>>> people = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
>>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "level_rank": [2, 3]})
>>> with_education(people, education, context=access)[["emp_key", "education_rank", "has_education_record"]].values.tolist()
[['EMP-000001', 3, True], ['EMP-000002', 0, False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `competence.education_record.emp_key`, `competence.education_record.level_rank`.
