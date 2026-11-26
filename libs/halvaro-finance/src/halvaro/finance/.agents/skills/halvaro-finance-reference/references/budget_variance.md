# budget_variance

```python
budget_variance(budget_line: pd.DataFrame, cost_centre_actual: pd.DataFrame, *, version: str, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you compare what was booked with what was budgeted, by entity, cost centre, account and period, for one budget version.

Rule: variance is actual less budget, in the entity currency and in DKK; amounts keep the ledger sign (debit positive), so a revenue variance above zero is less revenue. Only the periods of the version's lines are compared. A cell with an actual and no budget, or a budget and no actual, is listed with zero on the missing side. variance_percent is the variance over the absolute budget, empty without a budget. Variances are rounded to 2 decimals.

## Args

budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period, amount and amount_dkk.
cost_centre_actual: Frame finance.cost_centre_actual with le_key, cc_key, gl_key, period, amount and amount_dkk.
version: The budget version, for example BUD-2026.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, cc_key, gl_key, period, budget, actual, variance, variance_dkk, budget_dkk, actual_dkk and variance_percent.

## Raises

FrameError: a column is missing, the version has no lines, or a frame has more than one row for an entity, cost centre, account and period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import budget_variance
>>> ctx = Context(stage="month12", role="analyst")
>>> budget = pd.DataFrame({"le_key": ["LE-01"] * 2, "budget_version": ["BUD-2026"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6100"], "period": ["2026-01"] * 2,
...                        "amount": [100.0, 50.0], "amount_dkk": [100.0, 50.0]})
>>> actual = pd.DataFrame({"le_key": ["LE-01"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6200"], "period": ["2026-01"] * 2, "amount": [130.0, 20.0], "amount_dkk": [130.0, 20.0]})
>>> budget_variance(budget, actual, version="BUD-2026", context=ctx)[["gl_key", "budget", "actual", "variance"]].values.tolist()
[['GL-6000', 100.0, 130.0, 30.0], ['GL-6100', 50.0, 0.0, -50.0], ['GL-6200', 0.0, 20.0, 20.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.budget_line.le_key`, `finance.budget_line.budget_version`, `finance.budget_line.cc_key`, `finance.budget_line.gl_key`, `finance.budget_line.period`, `finance.budget_line.amount`, `finance.budget_line.amount_dkk`, `finance.cost_centre_actual.le_key`, `finance.cost_centre_actual.cc_key`, `finance.cost_centre_actual.gl_key`, `finance.cost_centre_actual.period`, `finance.cost_centre_actual.amount`, `finance.cost_centre_actual.amount_dkk`.
