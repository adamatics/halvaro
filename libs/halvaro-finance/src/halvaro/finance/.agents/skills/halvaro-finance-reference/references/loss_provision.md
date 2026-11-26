# loss_provision

```python
loss_provision(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need the provision for the loss that a project is expected to make: the part of the expected loss not yet recognised.

Rule: the expected loss is the EAC above the contract value (zero when the EAC is not above it). The provision is the expected loss times one less the cost to cost fraction, rounded to two decimals; none when the project has ended.

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named loss_provision, on the index of the frame, in the contract currency of the row; zero where no loss is expected.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import loss_provision
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "contract_value": [1000.0] * 3,
...                    "actual_cost": [400.0, 600.0, 1200.0], "eac": [800.0, 1200.0, 1200.0]})
>>> loss_provision(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
[0.0, 100.0, 0.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`, `finance.project_financials.contract_value`.
