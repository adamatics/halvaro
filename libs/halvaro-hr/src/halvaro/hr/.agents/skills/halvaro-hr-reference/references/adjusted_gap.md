# adjusted_gap

```python
adjusted_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None, extra_controls: str | Sequence[str] = ()) -> dict[str, Any]
```

Use this when you need the pay difference between women and men after taking tenure, legal entity and grade into account, with its standard error.

Rule: an OLS of ln(rate_dkk) on a dummy for women, tenure, one indicator per legal entity and one per grade; the gap is (1 minus exp(b)) times 100 in percent, positive when women are paid less. The result is suppressed (NaN, suppressed True) below minimum_group people per gender (proposed 8), when the sample is too small for the model, and for nothing else. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key and level.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.
extra_controls: Names of numeric columns added to the model, for instance education_rank from with_education. Default none.

## Returns

dict: n_women, n_men, adjusted_gap_pct and adjusted_gap_se_pct (percent, NaN when suppressed), suppressed (bool) and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, an extra control is not numeric, infinite, missing, repeated or already in the model, or the rate, entity, grade or tenure values are missing or not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import adjusted_gap
>>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6})
>>> result = adjusted_gap(people, minimum_group=3, context=access)
>>> result["n_women"], result["n_men"], result["suppressed"], round(result["adjusted_gap_pct"], 1)
(3, 3, False, 9.1)
>>> adjusted_gap(people, context=access)["suppressed"]
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.
