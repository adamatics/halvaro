# price_list_on

Module `halvaro.delivery.pricing`. Import: `from halvaro.delivery import price_list_on`.

```python
price_list_on(price_list: pd.DataFrame, as_of: DateLike, *, sup_key: str | None = None, itm_key: str | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the price per supplier and item that is valid on a date, optionally for one supplier and one item.

A price row is valid when valid_from is on or before the date and valid_to is null or on or after it (DA.REF.007, inclusive). Prices stay in the currency of the row. Two valid rows for one supplier and item on the date raise AmbiguousKey (the generator test forbids it). A valid row without a unit_price raises FrameError (no price is never passed on as a missing number).

Args:
    price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason.
    as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
    sup_key: Optional keyword, one supplier key as text; only its prices are returned.
    itm_key: Optional keyword, one item key as text; only its prices are returned.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason, sorted by sup_key and itm_key, index reset.

Raises:
    FrameError: price_list is not a DataFrame, lacks a needed column, has duplicate column names, has a row without sup_key, itm_key or valid_from, has a unit_price that is not numeric, or holds a valid_from or valid_to that is not a date; sup_key or itm_key is not text; as_of is a number, has a time zone or is not a date; a valid row has no unit_price.
    AmbiguousKey: two rows of one supplier and item are valid on the date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import price_list_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pl = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
    ...                    "valid_from": ["2025-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None],
    ...                    "unit_price": [10.0, 12.5], "currency": ["EUR", "EUR"], "con_key": [None, None], "change_reason": [None, "indexation"]})
    >>> price_list_on(pl, "2026-03-01", context=ctx)["unit_price"].tolist()
    [12.5]
    >>> price_list_on(pl, "2025-03-01", sup_key="SUP-900001", itm_key="ITM-900001", context=ctx)["unit_price"].tolist()
    [10.0]

## Source columns

- `procurement.price_list.sup_key`
- `procurement.price_list.itm_key`
- `procurement.price_list.valid_from`
- `procurement.price_list.valid_to`
- `procurement.price_list.unit_price`
- `procurement.price_list.currency`
- `procurement.price_list.con_key`
- `procurement.price_list.change_reason`
