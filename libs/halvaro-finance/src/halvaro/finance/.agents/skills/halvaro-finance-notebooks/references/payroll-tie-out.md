# Payroll tie-out: the pay HR implies against the pay the ledger booked

Notebook `notebooks/payroll-tie-out.ipynb` of halvaro-finance, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** Does the gross pay in the ledger equal the gross pay that the employment terms of HR imply, per cost centre and month, and what do the employer pension and social contributions come to on that pay?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `cost_centre_team_map` | you check that finance cost centres and hr teams point at each other. | [cost_centre_team_map](../../halvaro-finance-reference/references/cost_centre_team_map.md) |
| `ledger_gross_pay` | you need the gross salary booked in the ledger per legal entity, cost centre and month, to tie out against the payroll summary. | [ledger_gross_pay](../../halvaro-finance-reference/references/ledger_gross_pay.md) |
| `tie_out` | you check the gross pay of the ledger against the aggregate of the hr side, per group of cost centres and month. | [tie_out](../../halvaro-finance-reference/references/tie_out.md) |
| `employer_oncosts` | you need the employer pension and social contributions on gross pay, per entity, cost centre and month, by country. | [employer_oncosts](../../halvaro-finance-reference/references/employer_oncosts.md) |

## Also uses (other libraries)

| Library | Functions |
|---|---|
| halvaro-core | `fact` |
| halvaro-hr | `payroll_aggregate` |

## Steps

The task crosses two libraries. `payroll_aggregate` of halvaro-hr turns employment terms into the gross pay per cost centre and month, without employee keys; the pay is a restricted column, so the caller must be allowed to read it, and a group below the minimum size is pooled so that no one can read a person from a total. Three functions of halvaro-finance follow: `cost_centre_team_map` checks that cost centres and teams point at each other, `ledger_gross_pay` sums the salary lines of the ledger, and `tie_out` compares the two sides, within a tolerance and within the band of the grades. `employer_oncosts` then prices the contributions, with the shares read by `fact` of halvaro-core in the check. The notebook builds its own frames with invented amounts, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context, fact
from halvaro.finance import cost_centre_team_map, employer_oncosts, ledger_gross_pay, tie_out
from halvaro.hr import payroll_aggregate
from halvaro.hr.payroll import PAY  # the name of the pay column of the employment terms

analyst = Context(stage="month12", role="analyst")
reader = Context(stage="month12", role="analyst", restricted_ok=True)  # may read pay; a context without this is refused
people = 8  # people per cost centre; the default minimum group of the policy is 8 (proposed), so no group here is pooled
term = pd.DataFrame({"emp_key": [f"EMP-{i:03d}" for i in range(2 * people)], "valid_from": ["2024-01-01"] * (2 * people), "valid_to": [None] * (2 * people),
                     "team_key": ["TEAM-1"] * people + ["TEAM-2"] * people, "grade_key": ["GRA-1", "GRA-2"] * people, "fte": [1.0, 0.8, 1.0, 1.0] * (people // 2),
                     "currency": ["DKK"] * (2 * people), PAY: [30500.0 + 910.0 * i for i in range(2 * people)]})
team = pd.DataFrame({"team_key": ["TEAM-1", "TEAM-2"], "cost_centre_key": ["CC-1", "CC-2"], "legal_entity_key": ["LE-01", "LE-01"]})
grade = pd.DataFrame({"gra_key": ["GRA-1", "GRA-2"], "band_min_dkk": [29000.0, 39400.0], "band_max_dkk": [60000.0, 72000.0],
                      "band_min_eur": [3700.0, 5100.0], "band_max_eur": [8000.0, 9600.0]})
salary_accounts = ("GL-7000", "GL-7005")  # the function proposes three accounts; this ledger uses two
unbooked = 250.0  # a correction of the pay of CC-2 that has not been booked yet
floor_factor, ceiling_factor = 0.965, 1.025  # the margins around the band of the grades (the function proposes its own)
team
```

Step 1. The HR side for January 2026, with the default minimum group of the policy: a cost centre with fewer people would be pooled with others, so that a total never shows one person. Each cost centre here has enough people.

```python
hr_side = payroll_aggregate(term, team, grade, "2026-01", "2026-01", context=reader)
hr_side[["le_key", "cc_key", "period", "hr_gross_pay", "hr_fte", "n_people", "suppressed"]]
```

Step 2. The ledger side. Every cost centre has its salary lines on two accounts. The lines are built from the HR side here so that the example has something to tie; in the ledger of CC-2 the correction `unbooked` has not been booked yet. The salary accounts are passed on, because the default list of the function is a proposed one.

```python
rows = []
for r in hr_side.itertuples():
    booked = r.hr_gross_pay - (unbooked if r.cc_key == "CC-2" else 0.0)
    rows += [("LE-01", r.cc_key, "GL-7000", "2026-01", round(booked * 0.9, 2)), ("LE-01", r.cc_key, "GL-7005", "2026-01", round(booked - round(booked * 0.9, 2), 2)),
             ("LE-01", r.cc_key, "GL-6000", "2026-01", 1999.0)]  # an account that is not a salary account: left out
journal = pd.DataFrame(rows, columns=["le_key", "cc_key", "gl_key", "period", "amount"])
ledger_side = ledger_gross_pay(journal, accounts=salary_accounts, context=analyst)
ledger_side
```

Step 3. The tie-out. Each cost centre is a group of its own because the aggregate holds one row per cost centre. A difference within the tolerance of the policy fact (proposed) is `tied`; a ledger outside the band of the grades is `outside_band`; anything else is named. `within_band_envelope` says whether the ledger sits between the lowest and the highest pay that the grades allow, with the margins named above; the pay of CC-1 is a little under the sum of the lowest pay of its grades, and the margin keeps it inside.

```python
tied = tie_out(ledger_side, hr_side, band_floor_factor=floor_factor, band_ceiling_factor=ceiling_factor, context=analyst)
tied.value[["cc_key", "ledger_gross_pay", "hr_gross_pay", "difference", "within_band_envelope", "status"]]
```

Step 4. Before trusting a tie-out, check that finance cost centres and HR teams point at each other, and price the contributions on the pay that the ledger carries. The contribution shares are provisional facts (status VERIFY); the status travels with the result.

```python
cost_centre = pd.DataFrame({"cc_key": ["CC-1", "CC-2"], "team_key": ["TEAM-1", "TEAM-2"]})
mapping_problems = cost_centre_team_map(cost_centre, team, context=analyst)
gross = ledger_side.rename(columns={"ledger_gross_pay": "gross_salary"})
oncosts = employer_oncosts(gross, country_of={"LE-01": "DK"}, base="gross", context=analyst)
(len(mapping_problems), oncosts.status, oncosts.value[["cc_key", "base_amount", "employer_pension", "employer_social"]])
```

Check. Every figure is recomputed another way: the ledger side with a filter and a sum in pandas, the HR side from the terms (pay times fte), the difference as ledger less HR (and the correction that was left out of CC-2), the status from the tolerance of the fact, the band check from the totals and factors of the result, and the contributions from the shares of the facts on the pay the ledger carries.

```python
salary_lines = journal[journal["gl_key"].isin(salary_accounts)]
by_cc = salary_lines.groupby("cc_key")["amount"].sum().round(2)
hr_by_cc = (term[PAY] * term["fte"]).groupby(term["team_key"].map(team.set_index("team_key")["cost_centre_key"])).sum()
result = tied.value.set_index("cc_key")
tolerance = fact("policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk").value
assert (ledger_side.set_index("cc_key")["ledger_gross_pay"] == by_cc).all()
assert (result["hr_gross_pay"] == hr_by_cc).all()
assert (result["difference"].round(2) == (by_cc - hr_by_cc).round(2)).all()
assert abs(result.loc["CC-2", "difference"] + unbooked) < 0.01 and abs(result.loc["CC-1", "difference"]) < 0.01
assert (result["status"].eq("tied") == (result["difference"].abs() <= tolerance)).all()
assert (result["within_band_envelope"] == ((result["ledger_gross_pay"] >= result["band_minimum_total"] * floor_factor) & (result["ledger_gross_pay"] <= result["band_maximum_total"] * ceiling_factor))).all()
pension, social = fact("fin.payroll_on_costs.DK.employer_pension_share").value, fact("fin.payroll_on_costs.DK.employer_social_share").value
assert (oncosts.value["base_amount"].to_numpy() == ledger_side["ledger_gross_pay"].to_numpy()).all()
assert (oncosts.value["employer_pension"] - (oncosts.value["base_amount"] * pension)).abs().max() <= 0.01
assert (oncosts.value["employer_social"] - (oncosts.value["base_amount"] * social)).abs().max() <= 0.01
assert len(mapping_problems) == 0
```
