# cash_forecast_checks

```python
cash_forecast_checks(cash_forecast: pd.DataFrame, bank_balance: pd.DataFrame, *, opening_tolerance: float = 0.005, chain_tolerance: float = 0.011, component_tolerance: float = 0.02, roll_tolerance: float = 0.011, context: Context) -> pd.DataFrame
```

Use this when you need to check that a weekly cash forecast ties to the bank, chains from week to week and keeps its band.

Rule: the forecast of an entity and forecast date is checked in five ways, and every violation is listed (the generator check stops at the first). opening_differs_from_bank: opening cash of
week 1 against the sum of the bank balances of the entity on the forecast date. weekly_chain_broken: opening cash of a week against closing cash of the week before.
components_do_not_sum: net cash flow against the sum of its eleven components. closing_not_opening_plus_net: closing = opening + net cash flow. outside_band: closing cash outside the
10th to 90th percentile band. The tolerances are PROPOSED keywords.

## Args

cash_forecast: Frame finance.cash_forecast, one row per entity, forecast date and week, with the amounts in the entity currency.
bank_balance: Frame finance.bank_balance with le_key, balance_date and closing_balance, one row per bank account and date.
opening_tolerance: Largest accepted difference of opening cash and bank, in currency units (default 0.005).
chain_tolerance: Largest accepted difference between a closing and the next opening cash (default 0.011).
component_tolerance: Largest accepted difference between net cash flow and its components (default 0.02).
roll_tolerance: Largest accepted difference of closing cash and opening plus net cash flow (default 0.011).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame of violations with the columns table, key, rule, detail; empty when the forecast is clean. The key is the entity, forecast date and week.
Typed form: ViolationRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a column is missing, a tolerance is negative or not a number, or the forecast has more than one row for an entity, forecast date and week.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cash_forecast_checks
>>> ctx = Context(stage="month3", role="analyst")
>>> parts = ["receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new",
...          "payments_net_wages", "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest"]
>>> week = {"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": 1, "opening_cash": 1000.0, "net_cash_flow": -300.0, "closing_cash": 700.0,
...         "closing_cash_p10": 650.0, "closing_cash_p90": 750.0, **dict.fromkeys(parts, 0.0), "payments_vat": -300.0}
>>> bank = pd.DataFrame({"le_key": ["LE-01"], "balance_date": ["2025-01-31"], "closing_balance": [1000.0]})
>>> cash_forecast_checks(pd.DataFrame([week]), bank, context=ctx).empty
True
>>> broken = pd.DataFrame([{**week, "opening_cash": 990.0}])
>>> sorted(cash_forecast_checks(broken, bank, context=ctx)["rule"])
['closing_not_opening_plus_net', 'opening_differs_from_bank']
```

## Typed result

`ViolationRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.cash_forecast.le_key`, `finance.cash_forecast.forecast_date`, `finance.cash_forecast.week_no`, `finance.cash_forecast.opening_cash`, `finance.cash_forecast.net_cash_flow`, `finance.cash_forecast.closing_cash`, `finance.cash_forecast.closing_cash_p10`, `finance.cash_forecast.closing_cash_p90`, `finance.cash_forecast.receipts_customers`, `finance.cash_forecast.receipts_retention`, `finance.cash_forecast.receipts_new_billing`, `finance.cash_forecast.receipts_intercompany`, `finance.cash_forecast.payments_suppliers_open`, `finance.cash_forecast.payments_suppliers_new`, `finance.cash_forecast.payments_net_wages`, `finance.cash_forecast.payments_payroll_taxes_pensions`, `finance.cash_forecast.payments_vat`, `finance.cash_forecast.payments_intercompany`, `finance.cash_forecast.net_interest`, `finance.bank_balance.le_key`, `finance.bank_balance.balance_date`, `finance.bank_balance.closing_balance`.
