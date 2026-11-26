# convert

```python
convert(cents: Any, from_currency: str, to_currency: str, *, basis: str) -> Any
```

Use this when you move whole cents between DKK, EUR and SEK on a named basis.

Rule: the booking basis uses the fixed booking rates of core; group_pay uses the fixed EUR to DKK rate of the fact world.fx_eur_dkk_fixed and knows DKK and EUR only. The cents are multiplied by the rate of the from currency and divided by the rate of the to currency with rdiv, so the result is rounded half away from zero. There is no default basis.

## Args

cents: Whole cents, one value, an array or a Series.
from_currency: DKK, EUR or SEK.
to_currency: DKK, EUR or SEK.
basis: "booking" or "group_pay".

## Returns

The converted cents, of the shape of the input.

## Raises

BasisError: the basis is not available (the daily basis needs a rate frame), or a currency has no rate on the basis.

## Example

```python
>>> from halvaro.core import convert, fact
>>> rate = fact("world.fx_eur_dkk_fixed").value
>>> int(convert(10000, "EUR", "DKK", basis="booking")) == round(10000 * rate), int(convert(500, "DKK", "DKK", basis="booking"))
(True, 500)
>>> convert(100, "DKK", "EUR", basis="daily")
Traceback (most recent call last):
...
halvaro.core.errors.BasisError: basis 'daily' is not available; use 'booking' or 'group_pay' (the daily basis needs a rate frame and comes with core 0.2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: none (inputs are passed in).
