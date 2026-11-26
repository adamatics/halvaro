# price_steps

```python
price_steps(price_before: pd.DataFrame, price_after: pd.DataFrame, *, reason: str = 'framework_amendment', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the change of the price of each supplier and item between the day before an effective date and the effective date.

Rule: the two frames are joined on supplier and item. The step is the price after less the price before, and step_percent is the step over the price before in percent (four decimals; null when there is no price before or after, or when the price before is not above zero). A price counts as amended when the price in force after has the given change reason. Side says whether the item has a price on both dates, before only or after only.

## Args

price_before: Frame from price_list_on for the day before the effective date, with sup_key, itm_key, unit_price, currency and change_reason.
price_after: Frame from price_list_on for the effective date, with the same columns.
reason: The change reason that marks an amendment. Default "framework_amendment".
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, itm_key, currency, price_before, price_after, step, step_percent, amended and side (both, before_only or after_only), sorted by supplier and item.

## Raises

FrameError: a column is missing, a frame has more than one price for a supplier and item or a null price, or the currency of a price differs between the two dates.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import price_steps
>>> ctx = Context(stage="month12", role="analyst")
>>> before = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [10.0], "currency": ["EUR"], "change_reason": ["list"]})
>>> after = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "currency": ["EUR"], "change_reason": ["framework_amendment"]})
>>> price_steps(before, after, context=ctx)[["step", "step_percent", "amended", "side"]].values.tolist()
[[1.0, 10.0, True, 'both']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.price_list.unit_price`, `procurement.price_list.change_reason`, `procurement.price_list.valid_from`, `procurement.price_list.currency`.
