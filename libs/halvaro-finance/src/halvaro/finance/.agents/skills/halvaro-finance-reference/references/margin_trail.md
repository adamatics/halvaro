# margin_trail

```python
margin_trail(project_financials: pd.DataFrame, prj_key: str, write_down: pd.DataFrame | None = None, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you follow the margin of one project period by period, with the period and amount of its write-down. For the margins alone, of all projects at once, project_margin is enough.

Rule: the rows of the project in period order, with margin_pct and forecast_margin_pct as in project_margin. Each write-down journal line is put on the period of its posting month: write_down_period is true there, and write_down_amount (entity currency) and write_down_amount_dkk add up the lines of that month to two decimals; elsewhere they are empty. The amounts stay in the currency of the rows and are never summed across currencies.

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
prj_key: The project key.
write_down: The output of write_down_journal with posting_date, amount and amount_dkk (and currency if present). Default None, no write-down.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with period, currency, margin_pct, forecast_margin_pct, write_down_period, write_down_amount and write_down_amount_dkk, one row per period of the project.

## Raises

FrameError: prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised or loss_provision is missing, the project has no row, a posting date is missing or not a date, an amount is null, a period is repeated for the project (checked only when write_down is given), the write-down is in another currency than the rows, or the write-down is posted in a month without a row of the project.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import margin_trail
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "period": ["2026-02", "2026-03"], "currency": ["EUR", "EUR"], "contract_value": [1000.0, 1000.0], "eac": [800.0, 800.0],
...                    "actual_cost": [300.0, 400.0], "revenue_recognised": [400.0, 500.0], "loss_provision": [0.0, 0.0]})
>>> wd = pd.DataFrame({"posting_date": ["2026-03-15"], "amount": [40.0], "amount_dkk": [300.0]})
>>> margin_trail(pf, "PRJ-1", wd, context=ctx)[["period", "margin_pct", "forecast_margin_pct", "write_down_period", "write_down_amount_dkk"]].to_dict("records")
[{'period': '2026-02', 'margin_pct': 25.0, 'forecast_margin_pct': 20.0, 'write_down_period': False, 'write_down_amount_dkk': nan}, {'period': '2026-03', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0, 'write_down_period': True, 'write_down_amount_dkk': 300.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.contract_value`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.revenue_recognised`, `finance.project_financials.loss_provision`.
