# mgmt_pl_check

```python
mgmt_pl_check(mgmt_pl_department: pd.DataFrame, trial_balance: pd.DataFrame, *, result_accounts: tuple[int, int] = (5100, 8999), revenue_accounts: tuple[int, int] = (5100, 5499), tolerance: float = 1.0, line_tolerance: float = 0.05, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that the management P&L agrees with the ledger and adds up within each department row.

Rule: per entity and month, the operating result of the management P&L must equal the ledger result (credit less debit on the result accounts) and the total revenue must equal the ledger revenue (the revenue accounts), each within tolerance. Per department row, the cost lines must add up to total_cost and revenue less cost must equal the operating result, each within line_tolerance. The account ranges and tolerances are business choices (proposed).

## Args

mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, total_revenue, total_cost, operating_result and the ten cost line columns, one row per entity, department and period.
trial_balance: Frame finance.trial_balance with le_key, period, gl_key (like GL-5100), debit and credit.
result_accounts: First and last account number of the result accounts. Default (5100, 8999) (proposed).
revenue_accounts: First and last account number of the revenue accounts. Default (5100, 5499) (proposed).
tolerance: Largest accepted gap per entity and month. Default 1.0 (proposed).
line_tolerance: Largest accepted gap per department row. Default 0.05 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; the rules are result_differs_from_ledger, revenue_differs_from_ledger, cost_lines_do_not_add_up and result_not_revenue_less_cost. Empty when everything agrees.

## Raises

FrameError: a column is missing, a tolerance is negative or not a number, an account range is not a (first, last) pair, or a row is repeated for an entity, department and period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import mgmt_pl_check
>>> ctx = Context(stage="month12", role="analyst")
>>> costs = ["project_labour_cost", "project_other_direct_cost", "service_direct_cost", "stock_and_inventory_cost", "staff_cost", "labour_absorbed", "overhead_cost", "overhead_allocated", "depreciation_and_amortisation", "other_operating_cost"]
>>> pl = pd.DataFrame({"le_key": ["LE-01"], "dep_key": ["DEP-1"], "period": ["2026-01"], "total_revenue": [100.0], "total_cost": [60.0], "operating_result": [40.0], **{c: [0.0] for c in costs}})
>>> pl["project_labour_cost"] = 60.0
>>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-01"] * 2, "gl_key": ["GL-5100", "GL-6000"], "debit": [0.0, 60.0], "credit": [100.0, 0.0]})
>>> mgmt_pl_check(pl, tb, context=ctx).empty
True
>>> mgmt_pl_check(pl.assign(operating_result=30.0), tb, context=ctx)["rule"].tolist()
['result_differs_from_ledger', 'result_not_revenue_less_cost']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.mgmt_pl_department.le_key`, `finance.mgmt_pl_department.dep_key`, `finance.mgmt_pl_department.period`, `finance.mgmt_pl_department.total_revenue`, `finance.mgmt_pl_department.total_cost`, `finance.mgmt_pl_department.operating_result`, `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.debit`, `finance.trial_balance.credit`.
