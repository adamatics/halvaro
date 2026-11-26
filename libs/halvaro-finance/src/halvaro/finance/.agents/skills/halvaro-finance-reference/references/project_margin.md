# project_margin

```python
project_margin(project_financials: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the two named margins of a project and period in percent: the margin to date and the margin forecast at completion. Never one "margin". To follow one project period by period together with its write-down, use margin_trail.

Rule: margin_pct is (revenue recognised less actual cost less loss provision) over revenue recognised, empty without revenue. forecast_margin_pct is (contract value less EAC) over contract value, empty without a contract value. Both are rounded to two decimals.

## Args

project_financials: Frame finance.project_financials with prj_key, period, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, margin_pct and forecast_margin_pct, on the index of the frame.

## Raises

FrameError: a column is missing.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import project_margin
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "eac": [800.0, 1200.0],
...                    "actual_cost": [400.0, 600.0], "revenue_recognised": [500.0, 500.0], "loss_provision": [0.0, 100.0]})
>>> project_margin(pf, context=ctx)[["prj_key", "margin_pct", "forecast_margin_pct"]].to_dict("records")
[{'prj_key': 'PRJ-1', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0}, {'prj_key': 'PRJ-2', 'margin_pct': -40.0, 'forecast_margin_pct': -20.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.contract_value`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.revenue_recognised`, `finance.project_financials.loss_provision`.
