# inventory_valuation_check

```python
inventory_valuation_check(inventory_valuation: pd.DataFrame, trial_balance: pd.DataFrame, *, allowance_gl: str = 'GL-2015', tolerance: float = 0.011, context: Context) -> Envelope
```

Use this when you need to check the inventory valuation for missing amounts, the allowance rule and agreement with the ledger.

Rule: net_stock: net_stock_value = stock_value less allowance. allowance_rate: allowance = the fact fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate (status VERIFY)
times slow_moving_value. allowance_over_slow_moving: the allowance is not above the slow moving value. missing_value: an amount is missing. ledger_stock and ledger_allowance: per entity and
period the valuation equals the ledger accounts of stock and of the allowance (allowance_gl) within the tolerance, and a period with stock in the ledger and no valuation row is a break.

## Args

inventory_valuation: Frame finance.inventory_valuation with le_key, site_key, item_category, period, gl_key, stock_value, slow_moving_value, allowance and net_stock_value.
trial_balance: Frame finance.trial_balance with le_key, period, gl_key and closing_balance, one row per entity, period and account.
allowance_gl: Ledger account of the allowance (default GL-2015, PROPOSED).
tolerance: Largest accepted difference in currency units (default 0.011).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame of violations (table, key, rule, detail), empty when the valuation is clean. The envelope carries the VERIFY status of the allowance rate.
Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, the tolerance is negative or not a number, or the trial balance has more than one row for an entity, period and account.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context, fact
>>> from halvaro.finance import inventory_valuation_check
>>> ctx = Context(stage="month3", role="analyst")
>>> rate = fact("fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate").value
>>> allowance = round(200.0 * rate, 2)
>>> iv = pd.DataFrame([{"le_key": "LE-01", "site_key": "SITE-01", "item_category": "cable", "period": "2023-01", "gl_key": "GL-2010", "stock_value": 1000.0,
...                     "slow_moving_value": 200.0, "allowance": allowance, "net_stock_value": 1000.0 - allowance}])
>>> tb = pd.DataFrame({"le_key": "LE-01", "period": "2023-01", "gl_key": ["GL-2010", "GL-2015"], "closing_balance": [1000.0, -allowance]})
>>> inventory_valuation_check(iv, tb, context=ctx).value.empty
True
```

## Typed result

`ViolationRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.finance_planning_and_registers.inventory_valuation.slow_moving_allowance_rate`.

Source columns: `finance.inventory_valuation.le_key`, `finance.inventory_valuation.site_key`, `finance.inventory_valuation.item_category`, `finance.inventory_valuation.period`, `finance.inventory_valuation.gl_key`, `finance.inventory_valuation.stock_value`, `finance.inventory_valuation.slow_moving_value`, `finance.inventory_valuation.allowance`, `finance.inventory_valuation.net_stock_value`, `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.closing_balance`.
