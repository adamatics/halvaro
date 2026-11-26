# cost_per_metre_by_cost_code

```python
cost_per_metre_by_cost_code(comparable_set: pd.DataFrame, project_cost_breakdown: pd.DataFrame, project: pd.DataFrame, route_change: pd.DataFrame | None = None, *, context: <class 'halvaro.core.access.Context'>) -> CostPerMetre
```

Use this when you compare projects by actual cost per metre of route for each cost code, with the median over the projects.

Rule: per project and cost code the last breakdown row (the latest period) gives the cost at completion, which is the cost to date for an active project; it is divided by the route length in metres and rounded to four decimals. The median per code is taken over the projects, per currency. A project with no breakdown row, or without a route length above zero, is left out and listed in dropped, never estimated; a code a project has no row for is left out of that code's median, not counted as zero. An as-built length above zero replaces the planned length and is flagged in route_source. The as-built column is a stand-in (proposed).

## Args

comparable_set: Frame of the projects to compare with prj_key and legacy (and data_depth if present), one row per project.
project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
project: Frame projects.project with prj_key and route_length_m, one row per project.
route_change: Optional frame with prj_key and as_built_length_m, one row per project; a missing or non positive length keeps the planned one. Default None.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

CostPerMetre, a named tuple of three frames: by_code with cst_key, currency, n_projects and median_per_metre; per_project with prj_key, cst_key, currency, cost_at_completion, route_length_m, per_metre, route_source (as_built or planned) and legacy; dropped with prj_key and reason (no finance rows or no route length).

## Raises

FrameError: a column is missing, actual_amount, route_length_m or as_built_length_m holds text that is not a number, a period is not text like 2026-01, a breakdown value is null, a breakdown row is repeated for a project, period and cost code, a project has more than one currency, a key is repeated in the comparable set, projects or route_change, or a project of the comparable set is not in projects.project.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_per_metre_by_cost_code
>>> ctx = Context(stage="month12", role="analyst")
>>> cs = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "legacy": [False, False, False]})
>>> pr = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "route_length_m": [100.0, 200.0, 50.0]})
>>> cb = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-A", "PRJ-B"], "period": ["2026-01", "2026-02", "2026-02"], "cst_key": ["CST-1"] * 3, "currency": ["DKK"] * 3,
...                    "actual_amount": [500.0, 1000.0, 3000.0], "incurred_in_period": [500.0, 500.0, 3000.0], "estimate_amount": [1200.0, 1200.0, 3200.0]})
>>> res = cost_per_metre_by_cost_code(cs, cb, pr, context=ctx)
>>> res.per_project[["prj_key", "per_metre"]].values.tolist()
[['PRJ-A', 10.0], ['PRJ-B', 15.0]]
>>> res.by_code[["cst_key", "n_projects", "median_per_metre"]].values.tolist()
[['CST-1', 2, 12.5]]
>>> res.dropped.values.tolist()
[['PRJ-C', 'no finance rows']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_cost_breakdown.prj_key`, `finance.project_cost_breakdown.period`, `finance.project_cost_breakdown.cst_key`, `finance.project_cost_breakdown.currency`, `finance.project_cost_breakdown.actual_amount`, `finance.project_cost_breakdown.incurred_in_period`, `finance.project_cost_breakdown.estimate_amount`, `projects.project.prj_key`, `projects.project.route_length_m`.
