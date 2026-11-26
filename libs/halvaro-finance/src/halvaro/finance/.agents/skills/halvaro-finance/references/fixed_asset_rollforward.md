# fixed_asset_rollforward

```python
fixed_asset_rollforward(fixed_asset: pd.DataFrame, *, context: Context) -> Envelope
```

Use this when you need the monthly cost and accumulated depreciation of the fixed asset register, per entity and asset class.

Rule: straight line depreciation of cost over useful_life_months, from the month after acquisition, accumulated amounts rounded half to even to the cent and exact at the end of the life. A
disposal month is depreciated and then derecognised. An asset acquired before the window opens opens with its accumulated depreciation. The window is the fact world.window_start to world.now.
A depreciation method other than the fact fin.fixed_assets.<country>.method (straight_line_monthly) is refused.

## Args

fixed_asset: Frame finance.fixed_asset with le_key, asset_class, acquisition_date, cost, useful_life_months, disposal_date, depreciation_method and currency.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame in the shape of finance.fixed_asset_schedule: le_key, asset_class, period (text like 2025-02), cost_opening, additions, disposals_cost,
cost_closing, accumulated_opening, depreciation, disposals_accumulated, accumulated_closing and net_book_value (all in the entity currency), and currency.
Typed form: AssetScheduleRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, an asset has no acquisition date or no positive number of months, an asset is disposed of before it was acquired, or the method is not the fact's method.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import fixed_asset_rollforward
>>> ctx = Context(stage="month3", role="analyst")
>>> fa = pd.DataFrame([{"le_key": "LE-01", "asset_class": "IT", "acquisition_date": dt.date(2023, 2, 10), "cost": 900.0, "useful_life_months": 3, "disposal_date": None,
...                     "depreciation_method": "straight_line_monthly", "currency": "DKK"}])
>>> s = fixed_asset_rollforward(fa, context=ctx).value.set_index("period")
>>> s.loc[["2023-02", "2023-03", "2023-05"], "accumulated_closing"].tolist()
[0.0, 300.0, 900.0]
```

## Typed result

`AssetScheduleRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.fixed_assets.DK.method`, `fin.fixed_assets.DE.method`, `fin.finance_planning_and_registers.fixed_asset_register.depreciation_start`, `world.window_start`, `world.now`.

Source columns: `finance.fixed_asset.le_key`, `finance.fixed_asset.asset_class`, `finance.fixed_asset.acquisition_date`, `finance.fixed_asset.cost`, `finance.fixed_asset.useful_life_months`, `finance.fixed_asset.disposal_date`, `finance.fixed_asset.depreciation_method`, `finance.fixed_asset.currency`.
