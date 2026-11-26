# forecast_accuracy

```python
forecast_accuracy(cash_forecast: pd.DataFrame, *, context: Context) -> pd.DataFrame
```

Use this when you need to know how well a cash forecast covered the actual closing cash, by entity and forecast horizon.

Rule: over the forecast weeks that have an actual closing cash (without the facility), coverage = the share of weeks whose actual is inside the 10th to 90th percentile band, and the error is
actual less forecast closing cash. Weeks without an actual are left out; an entity without any actual has no rows. Rows with week_no 0 hold all horizons of the entity.

## Args

cash_forecast: Frame finance.cash_forecast with le_key, week_no, closing_cash, the two band columns and actual_closing_cash_ex_rcf.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with le_key, week_no (0 for all horizons), n (number of weeks), coverage (share between 0 and 1), mean_abs_error and median_abs_error and mean_error (currency units; mean_error is
positive when the forecast was too low).
Typed form: AccuracyRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a column is missing.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import forecast_accuracy
>>> ctx = Context(stage="month3", role="analyst")
>>> cf = pd.DataFrame({"le_key": "LE-01", "week_no": [1, 2], "closing_cash": [700.0, 650.0], "closing_cash_p10": [670.0, 600.0], "closing_cash_p90": [730.0, 700.0],
...                    "actual_closing_cash_ex_rcf": [710.0, 720.0]})
>>> r = forecast_accuracy(cf, context=ctx).set_index("week_no")
>>> r.loc[0, ["n", "coverage", "mean_error"]].tolist() == [2, 0.5, 40.0]
True
```

## Typed result

`AccuracyRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.cash_forecast.le_key`, `finance.cash_forecast.week_no`, `finance.cash_forecast.closing_cash`, `finance.cash_forecast.closing_cash_p10`, `finance.cash_forecast.closing_cash_p90`, `finance.cash_forecast.actual_closing_cash_ex_rcf`.
