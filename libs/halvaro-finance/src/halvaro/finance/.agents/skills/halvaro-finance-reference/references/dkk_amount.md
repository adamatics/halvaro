# dkk_amount

```python
dkk_amount(amount: pd.Series, currency: pd.Series, *, basis: str, fx_rate: pd.DataFrame | None = None, on: pd.Series | None = None, group: bool = False, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need amounts in DKK to the cent: on the booking basis with the fixed rates of core, or on the daily basis with the latest rate on or before each date.

Rule: rounding is half away from zero on the cent. The daily basis needs one date per amount and a rate frame without duplicate (currency, rate_date), and is refused for group statements. A currency without a rate is an error.

## Args

amount: The amounts.
currency: The currency of each amount, same length, no nulls.
basis: "booking" or "daily".
fx_rate: Frame finance.fx_rate; on the booking basis it must agree with core for the currencies used. Optional.
on: The date of each amount; required on the daily basis.
group: True for group statements, which use the booking basis only.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series of the amounts in DKK, on the index of amount.

## Raises

BasisError: the basis is neither booking nor daily, or the daily basis is asked for a group statement.
FrameError: amount and currency differ in length or have nulls, a rate frame lacks a column or disagrees with core, a currency has no rate, or the daily basis lacks its dates or rates.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import dkk_amount
>>> ctx = Context(stage="month12", role="analyst")
>>> from halvaro.core import fact
>>> rate = fact("world.fx_eur_dkk_fixed").value
>>> dkk_amount(pd.Series([10.0, 10.0]), pd.Series(["DKK", "EUR"]), basis="booking", context=ctx).tolist() == [10.0, round(10 * rate, 2)]
True
>>> dkk_amount(pd.Series([1.0]), pd.Series(["DKK"]), basis="spot", context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.BasisError: basis 'spot' is not available; use 'booking' or 'daily'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `finance.fx_rate.currency`, `finance.fx_rate.rate`, `finance.fx_rate.booking_rate`, `finance.fx_rate.rate_date`.
