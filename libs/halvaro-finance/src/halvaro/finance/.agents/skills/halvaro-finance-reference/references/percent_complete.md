# percent_complete

```python
percent_complete(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need the percent of completion of each project row by cost to cost: actual cost over the estimate at completion.

Rule: a running project has the actual cost over the EAC, limited by cap; a project that ended on or before the end of the period has 100. The result is in percent with two decimals.

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named percent_complete, on the index of the frame, from 0 to 100.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import percent_complete
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "actual_cost": [400.0, 780.0, 800.0], "eac": [800.0, 800.0, 800.0]})
>>> percent_complete(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
[50.0, 95.0, 100.0]
>>> percent_complete(pf, {}, cap=1.5, context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: cap must be a number in (0, 1], ...
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`.
