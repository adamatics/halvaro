# liquidity_headroom

```python
liquidity_headroom(cash_forecast: pd.DataFrame, *, tolerance: float = 0.011, context: Context) -> pd.DataFrame
```

Use this when you need the headroom of a cash forecast to the minimum cash floor and the first week in which the low case falls below it.

Rule: per week, headroom = closing cash less the floor and headroom_p10 = the 10th percentile closing cash less the floor; the facility still available = rcf_limit less rcf_drawn; a week is
a breach week when the 10th percentile closing cash is below the floor. The result has one row per entity and forecast date. The floor and the limit are one value per forecast, taken from the
forecast rows. The tolerance is a PROPOSED keyword.

## Args

cash_forecast: Frame finance.cash_forecast with the closing cash lines, the floor, the facility columns and the stored headroom columns.
tolerance: Largest accepted difference between a recomputed and a stored column, in currency units (default 0.011).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with le_key, forecast_date, weeks (number of weeks), first_breach_week (empty when no week breaches), lowest_headroom_p10 (currency units), lowest_headroom_week,
rcf_available_at_lowest (currency units), breach_weeks (number of weeks) and agrees (the recomputed headroom, facility and breach flag equal the stored columns).
Typed form: HeadroomRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a column is missing, the tolerance is negative or not a number, a week appears twice for an entity and forecast date, or a forecast has more than one floor or facility limit.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import liquidity_headroom
>>> ctx = Context(stage="month3", role="analyst")
>>> rows = [{"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": w, "closing_cash": c, "closing_cash_p10": c - 30.0, "minimum_cash_floor": 100.0,
...          "rcf_limit": 500.0, "rcf_drawn": 100.0, "rcf_available": 400.0, "headroom_to_floor": c - 100.0, "headroom_to_floor_p10": c - 130.0,
...          "floor_breach_risk": c - 30.0 < 100.0} for w, c in ((1, 700.0), (2, 110.0))]
>>> r = liquidity_headroom(pd.DataFrame(rows), context=ctx)
>>> r.loc[0, ["weeks", "first_breach_week", "lowest_headroom_p10", "breach_weeks", "agrees"]].tolist() == [2, 2, -20.0, 1, True]
True
```

## Typed result

`HeadroomRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.cash_forecast.le_key`, `finance.cash_forecast.forecast_date`, `finance.cash_forecast.week_no`, `finance.cash_forecast.closing_cash`, `finance.cash_forecast.closing_cash_p10`, `finance.cash_forecast.minimum_cash_floor`, `finance.cash_forecast.rcf_limit`, `finance.cash_forecast.rcf_drawn`, `finance.cash_forecast.rcf_available`, `finance.cash_forecast.headroom_to_floor`, `finance.cash_forecast.headroom_to_floor_p10`, `finance.cash_forecast.floor_breach_risk`.
