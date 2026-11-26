# A cash forecast against the bank and the floor

Notebook `notebooks/cash-forecast-and-floor.ipynb` of halvaro-finance, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** Does a weekly cash forecast tie to the bank and chain from week to week, and in which week does its low case fall below the minimum cash floor?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `cash_forecast_checks` | you need to check that a weekly cash forecast ties to the bank, chains from week to week and keeps its band. | [cash_forecast_checks](../../halvaro-finance/references/cash_forecast_checks.md) |
| `liquidity_headroom` | you need the headroom of a cash forecast to the minimum cash floor and the first week in which the low case falls below it. | [liquidity_headroom](../../halvaro-finance/references/liquidity_headroom.md) |

## Steps

A weekly cash forecast is only worth reading when it starts at the bank balance and each week starts where the week before ended. `cash_forecast_checks` lists every place where it does not, and `liquidity_headroom` gives the headroom to the minimum cash floor and the first week in which the low case (the 10th percentile) falls below it. The notebook builds its own small forecast, four weeks of one entity, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.finance import cash_forecast_checks, liquidity_headroom

ctx = Context(stage="month3", role="analyst")
parts = ["receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new",
         "payments_net_wages", "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest"]
weeks = pd.DataFrame({"week_no": [1, 2, 3, 4], "receipts_customers": [200.0, 150.0, 100.0, 100.0], "payments_suppliers_open": [-250.0, -250.0, -300.0, -250.0],
                      "payments_vat": [0.0, 0.0, -200.0, 0.0]})
for name in parts:
    if name not in weeks:
        weeks[name] = 0.0
weeks["net_cash_flow"] = weeks[parts].sum(axis=1)
bank_balance = 1000.0
weeks["closing_cash"] = bank_balance + weeks["net_cash_flow"].cumsum()
weeks["opening_cash"] = weeks["closing_cash"].shift(fill_value=bank_balance)
weeks["closing_cash_p10"] = weeks["closing_cash"] - 60.0
weeks["closing_cash_p90"] = weeks["closing_cash"] + 60.0
weeks["minimum_cash_floor"] = 300.0
weeks["rcf_limit"], weeks["rcf_drawn"] = 500.0, 100.0
weeks["rcf_available"] = weeks["rcf_limit"] - weeks["rcf_drawn"]
weeks["headroom_to_floor"] = weeks["closing_cash"] - weeks["minimum_cash_floor"]
weeks["headroom_to_floor_p10"] = weeks["closing_cash_p10"] - weeks["minimum_cash_floor"]
weeks["floor_breach_risk"] = weeks["closing_cash_p10"] < weeks["minimum_cash_floor"]
forecast = weeks.assign(le_key="LE-01", forecast_date="2025-01-31")
bank = pd.DataFrame({"le_key": ["LE-01"], "balance_date": ["2025-01-31"], "closing_balance": [bank_balance]})
forecast[["week_no", "opening_cash", "net_cash_flow", "closing_cash", "closing_cash_p10"]]
```

Step 1. The forecast against the bank. The first week opens at the bank balance, each week opens where the one before closed, the components add up to the net flow, and every closing balance lies inside its band. A clean forecast gives an empty list.

```python
clean = cash_forecast_checks(forecast, bank, context=ctx)
clean
```

Step 2. Break the chain on purpose: week 3 opens 10 below where week 2 closed. Every violation is listed, not only the first.

```python
broken = forecast.copy()
broken.loc[broken["week_no"] == 3, "opening_cash"] -= 10.0
found = cash_forecast_checks(broken, bank, context=ctx)
found["rule"].tolist()
```

Step 3. The headroom to the floor. The low case falls below the floor in the last week; the facility that is still available is shown next to it.

```python
headroom = liquidity_headroom(forecast, context=ctx)
headroom[["weeks", "first_breach_week", "lowest_headroom_p10", "lowest_headroom_week", "rcf_available_at_lowest", "breach_weeks", "agrees"]]
```

Check. A clean forecast has no violation and the broken one is flagged for its chain. The first breach week and the lowest headroom equal what pandas reads from the forecast.

```python
assert clean.empty
assert "weekly_chain_broken" in found["rule"].tolist()
below = forecast[forecast["closing_cash_p10"] < forecast["minimum_cash_floor"]]
assert headroom.loc[0, "first_breach_week"] == below["week_no"].min()
assert headroom.loc[0, "lowest_headroom_p10"] == (forecast["closing_cash_p10"] - forecast["minimum_cash_floor"]).min()
assert headroom.loc[0, "breach_weeks"] == len(below)
assert bool(headroom.loc[0, "agrees"])
```
