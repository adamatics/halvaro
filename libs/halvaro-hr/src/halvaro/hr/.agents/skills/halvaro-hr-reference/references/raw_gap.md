# raw_gap

```python
raw_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> float
```

Use this when you need the raw pay difference between women and men: how much less the women are paid on average, before any adjustment.

Rule: one minus the mean rate of women over the mean rate of men, in percent; positive means women are paid less. The result is NaN when either gender has fewer than minimum_group people (proposed 8). The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender and rate_dkk; only F and M rows count.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

float: the gap in percent, or NaN below the minimum group size.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: the frame lacks the column gender.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import raw_gap
>>> people = pd.DataFrame({"gender": ["F", "F", "M", "M"], "rate_dkk": [90.0, 110.0, 190.0, 210.0]})
>>> raw_gap(people, minimum_group=2, context=access)
50.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.
