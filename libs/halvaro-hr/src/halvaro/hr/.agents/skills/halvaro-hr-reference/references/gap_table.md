# gap_table

```python
gap_table(frame: pd.DataFrame, by: str = 'department', *, minimum_group: int = 8, watch: float = 0.03, context: Context | None = None) -> pd.DataFrame
```

Use this when you want the pay difference between women and men per department or per grade in one table, with a flag for each group and a ranking.

Rule: for each group the counts, the raw gap (raw_gap) and the adjusted gap (adjusted_gap) in percent. The flag is above_threshold at or above the legal joint assessment threshold (a fact), watch at or above watch times 100 percent (proposed 0.03), otherwise ok. A group under minimum_group people per gender (proposed 8) keeps its counts, loses the gaps, is flagged suppressed and has no rank. The rank is by adjusted gap, highest first. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key, level and the grouping column (dep_key or level).
by: Either department (groups by dep_key) or grade (groups by level). Default department.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
watch: The share at or above which a group is flagged watch. Default 0.03 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

pandas.DataFrame: one row per group with the key column, n_women, n_men, raw_gap_pct, adjusted_gap_pct, adjusted_gap_se_pct, flag, suppressed, rank and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: by is not department or grade, or a column is missing.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import gap_table
>>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6, "dep_key": ["DEP-01"] * 6})
>>> table = gap_table(people, minimum_group=3, context=access)
>>> table[["dep_key", "n_women", "n_men", "suppressed"]].values.tolist(), round(float(table["raw_gap_pct"].iloc[0]), 1)
([['DEP-01', 3, 3, False]], 9.1)
>>> gap_table(people, context=access)["flag"].tolist()
['suppressed']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.pay_transparency.joint_assessment_gap_threshold`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.
