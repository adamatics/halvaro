# forecast_vs_budget

```python
forecast_vs_budget(forecast_line: pd.DataFrame, forecast_version: pd.DataFrame, budget_line: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you compare each forecast version with the budget it is based on, by entity, cost centre, account and period in DKK.

Rule: difference is forecast less the budget of the version the forecast version names; a cell without a budget has budget 0; the difference is rounded to 2 decimals. basis_ok says that the line follows its version: actual up to actuals_through_period, projected after.

## Args

forecast_line: Frame finance.forecast_line with le_key, forecast_version, cc_key, gl_key, period, amount_dkk and basis.
forecast_version: Frame finance.forecast_version with forecast_version, actuals_through_period and budget_version.
budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period and amount_dkk.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with forecast_version, le_key, cc_key, gl_key, period, basis, forecast_dkk, budget_dkk, difference_dkk and basis_ok.

## Raises

FrameError: a column is missing, a table has more than one row for its key, or a forecast version is not in the version table.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import forecast_vs_budget
>>> ctx = Context(stage="month12", role="analyst")
>>> forecast = pd.DataFrame({"le_key": ["LE-01"] * 2, "forecast_version": ["FC-1"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000"] * 2, "period": ["2026-01", "2026-02"],
...                          "amount_dkk": [110.0, 120.0], "basis": ["actual", "projected"]})
>>> versions = pd.DataFrame({"forecast_version": ["FC-1"], "actuals_through_period": ["2026-01"], "budget_version": ["BUD-2026"]})
>>> budget = pd.DataFrame({"le_key": ["LE-01"], "budget_version": ["BUD-2026"], "cc_key": ["CC-1"], "gl_key": ["GL-6000"], "period": ["2026-01"], "amount_dkk": [100.0]})
>>> forecast_vs_budget(forecast, versions, budget, context=ctx)[["period", "forecast_dkk", "budget_dkk", "difference_dkk", "basis_ok"]].values.tolist()
[['2026-01', 110.0, 100.0, 10.0, True], ['2026-02', 120.0, 0.0, 120.0, True]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.forecast_line.le_key`, `finance.forecast_line.forecast_version`, `finance.forecast_line.cc_key`, `finance.forecast_line.gl_key`, `finance.forecast_line.period`, `finance.forecast_line.amount_dkk`, `finance.forecast_line.basis`, `finance.forecast_version.forecast_version`, `finance.forecast_version.actuals_through_period`, `finance.forecast_version.budget_version`, `finance.budget_line.le_key`, `finance.budget_line.budget_version`, `finance.budget_line.cc_key`, `finance.budget_line.gl_key`, `finance.budget_line.period`, `finance.budget_line.amount_dkk`.
