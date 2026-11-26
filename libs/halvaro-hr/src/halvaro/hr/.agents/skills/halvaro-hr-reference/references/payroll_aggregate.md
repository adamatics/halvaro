# payroll_aggregate

```python
payroll_aggregate(term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, first_month: str, last_month: str, *, minimum_group: int | PolicyDefault = policy:policy.pay_gap.minimum_cohort_size, on_small: str = 'pool', context: Context) -> pd.DataFrame
```

Use this when you need the gross pay of the employment terms per legal entity, cost centre, month and currency, without employee keys and without base salary, for the tie-out with finance.

Rule: pay is restricted, so the context must be allowed to read hr.employment_term.base_salary. For each month from first_month to last_month, each term in force in the month (valid_from to valid_to inclusive; an empty valid_to is open) weighs days in force over days in the month; terms are grouped by the legal entity and cost centre of their team and by currency. A group with fewer than minimum_group distinct people is small: on_small 'pool' (default) adds the small cost centres of one entity, currency and month into one row with cc_key POOLED, which is itself suppressed when it still has fewer people; 'suppress' keeps each small group with null numbers; 'refuse' raises. Suppressed rows have null numbers. Without suppression the total over all rows equals the sum over the terms. Months without a term give no row. A grade band value that is null adds 0 to the band totals (the sum skips nulls), and a term with valid_to before valid_from is accepted but has weight 0, so it is left out of the month (no row of its own, not counted in n_people).

## Args

term: Employment terms (hr.employment_term) with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency (DKK or EUR) and base_salary; fte above zero, no nulls except valid_to.
team: Teams (hr.team) with team_key, cost_centre_key and legal_entity_key, one row per team.
grade: Grades (hr.grade) with gra_key, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per grade.
first_month: The first month as text, YYYY-MM.
last_month: The last month as text, YYYY-MM; not before first_month.
minimum_group: The smallest number of people a group may show, a whole number of one or more (default the fact policy.pay_gap.minimum_cohort_size, status proposed; the status then goes into attrs["policy_status"]).
on_small: What to do with a small group: 'pool', 'suppress' or 'refuse'.
context: The caller (stage, role and whether restricted columns may be read); the role must be allowed to read pay.

## Returns

pandas.DataFrame with le_key, cc_key, period (YYYY-MM), currency, hr_gross_pay (base salary times fte times days in force over days in the month, the rule of finance.payroll_hr_reconciliation), hr_headcount_month_end (terms in force on the last day of the month), hr_fte (fte weighted by days), band_minimum_total and band_maximum_total (grade band times weighted fte, in the currency of the term), n_people (distinct people with a term in the month), n_cost_centres, cost_centres (the cost centre keys of the group, comma separated: one key, or the members of a POOLED row) and suppressed, sorted by le_key, cc_key, period and currency.

## Raises

RestrictedColumnRefusal: the context may not read base salary, or term has no base_salary column.
FrameError: context is not a Context (None, text), fte or base_salary holds text, on_small or minimum_group is invalid, a month is not YYYY-MM or first_month is after last_month, a frame lacks a column, hr.team or hr.grade has a duplicate key, term has missing values, a currency other than DKK or EUR or an fte of zero or less, a term names a team or grade that is not in hr.team or hr.grade, a date is not a date, a policy default is not a whole number, or on_small is 'refuse' and a group is small.
FactNotFound: the default minimum group is used and its fact is not in the snapshot.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.hr import payroll_aggregate
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2025-01-01", "2026-01-16"], "valid_to": [None, None], "team_key": ["TEAM-01"] * 2,
...                      "grade_key": ["GRA-01"] * 2, "fte": [1.0, 1.0], "currency": ["DKK"] * 2, "base_salary": [100.0, 100.0]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "cost_centre_key": ["CC-01"], "legal_entity_key": ["LE-01"]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-01"], "band_min_dkk": [50.0], "band_max_dkk": [150.0], "band_min_eur": [7.0], "band_max_eur": [20.0]})
>>> reader = Context(stage="month12", role="analyst", restricted_ok=True)
>>> shown = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=2, context=reader)
>>> shown[["cc_key", "period", "hr_headcount_month_end", "n_people", "suppressed"]].to_dict("records")
[{'cc_key': 'CC-01', 'period': '2026-01', 'hr_headcount_month_end': 2.0, 'n_people': 2, 'suppressed': False}]
>>> round(float(shown["hr_fte"].iloc[0]), 3)
1.516
>>> held = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=3, context=reader)
>>> held[["cc_key", "n_people", "suppressed"]].to_dict("records"), bool(held["hr_fte"].isna().all())
([{'cc_key': 'POOLED', 'n_people': 2, 'suppressed': True}], True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.pay_gap.minimum_cohort_size`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employment_term.team_key`, `hr.employment_term.grade_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.team.cost_centre_key`, `hr.team.legal_entity_key`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.
