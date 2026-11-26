# contract_position

```python
contract_position(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need revenue recognised less billed on each project row, split into the contract asset and the contract liability.

Rule: the position is revenue_recognised less billed. A positive position is the contract asset (wip, GL-2100), a negative one the contract liability (GL-4500, shown as a positive amount).

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value and billed, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, revenue_recognised, billed, contract_position (asset positive, liability negative), wip and contract_liability, on the index of the frame.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import contract_position
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "billed": [300.0, 700.0],
...                    "actual_cost": [400.0, 400.0], "eac": [800.0, 800.0]})
>>> contract_position(pf, {}, cap=0.95, context=ctx)[["prj_key", "contract_position", "wip", "contract_liability"]].to_dict("records")
[{'prj_key': 'PRJ-1', 'contract_position': 200.0, 'wip': 200.0, 'contract_liability': 0.0}, {'prj_key': 'PRJ-2', 'contract_position': -200.0, 'wip': 0.0, 'contract_liability': 200.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`, `finance.project_financials.contract_value`, `finance.project_financials.billed`.
