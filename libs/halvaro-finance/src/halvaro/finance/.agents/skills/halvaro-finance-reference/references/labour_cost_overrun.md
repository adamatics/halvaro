# labour_cost_overrun

```python
labour_cost_overrun(project_cost_breakdown: pd.DataFrame, project_budget_line: pd.DataFrame, cost_code: pd.DataFrame, window_start: dt.date | str | pd.Timestamp, window_end: dt.date | str | pd.Timestamp, *, active_only: bool = True, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you rank projects by how far their labour cost has run over the labour budget in a window of months.

Rule: labour is every leaf cost code (not a group) of category labour. Per project, in its own currency: labour_budget is the sum of the budget lines of the original (lowest) budget version, labour_estimate the latest estimate at completion, labour_actual_to_date the cumulative actual at the last period up to the window end, and labour_actual_window the cost incurred in the window. overrun_vs_budget_pct is actual to date over budget less 100, and overrun_vs_estimate_pct is the same against the estimate; both compare cost to date with the whole budget or estimate, so they understate a project that has only started. A project without labour budget is listed with null percentages and the reason "no labour budget". Rows are sorted by overrun_vs_budget_pct, largest first; the estimate percent is a second measure that can rank the projects differently, so say which measure a ranking uses. The definition of the overrun is a business choice (proposed).

## Args

project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
project_budget_line: Frame finance.project_budget_line with prj_key, cst_key, budget_version, budget_amount and currency.
cost_code: Frame projects.cost_code with cst_key, category and is_group, one row per cost code.
window_start: First month of the window, a month text like 2026-01 or a date.
window_end: Last month of the window, in the same forms.
active_only: True keeps the projects with labour cost incurred in the window; False lists every project with cost up to the window end. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, currency, labour_budget, labour_estimate, labour_actual_to_date, labour_actual_window, overrun_vs_budget_pct, overrun_vs_estimate_pct and reason.

## Raises

FrameError: a column is missing, a window bound is not a month, the window starts after it ends, a period is not text like 2026-01, a value is null where one is needed, a key is repeated, a project has more than one currency, a cost code of the breakdown is not in cost_code, cost_code has no labour leaf, or a budget is in another currency than the cost rows.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import labour_cost_overrun
>>> ctx = Context(stage="month12", role="analyst")
>>> costs = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-01"], "cst_key": ["CST-L"], "currency": ["EUR"], "actual_amount": [120.0], "incurred_in_period": [120.0], "estimate_amount": [130.0]})
>>> budget = pd.DataFrame({"prj_key": ["PRJ-1"], "cst_key": ["CST-L"], "budget_version": [1], "budget_amount": [100.0], "currency": ["EUR"]})
>>> codes = pd.DataFrame({"cst_key": ["CST-L"], "category": ["labour"], "is_group": [False]})
>>> labour_cost_overrun(costs, budget, codes, "2026-01", "2026-01", context=ctx)[["prj_key", "labour_budget", "labour_actual_to_date", "overrun_vs_budget_pct"]].values.tolist()
[['PRJ-1', 100.0, 120.0, 20.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_cost_breakdown.prj_key`, `finance.project_cost_breakdown.period`, `finance.project_cost_breakdown.cst_key`, `finance.project_cost_breakdown.currency`, `finance.project_cost_breakdown.actual_amount`, `finance.project_cost_breakdown.incurred_in_period`, `finance.project_cost_breakdown.estimate_amount`, `finance.project_budget_line.prj_key`, `finance.project_budget_line.cst_key`, `finance.project_budget_line.budget_version`, `finance.project_budget_line.budget_amount`, `finance.project_budget_line.currency`, `projects.cost_code.cst_key`, `projects.cost_code.category`, `projects.cost_code.is_group`.
