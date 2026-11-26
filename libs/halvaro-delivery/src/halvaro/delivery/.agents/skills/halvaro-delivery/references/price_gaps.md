# price_gaps

Module `halvaro.delivery.pricing`. Import: `from halvaro.delivery import price_gaps`.

```python
price_gaps(price_list: pd.DataFrame, *, window: tuple[DateLike, DateLike] | None = None, context: halvaro.core.access.Context) -> PriceGaps
```

Use this when you need to check the effective dating of the price list: the violations, the periods without a valid price per supplier and item, and the currency changes.

The result has three parts. Violations of effective dating per supplier and item (reversed, two open rows, an open row followed by another, overlap, gap; core check_contiguity, convention day_after). The periods without a valid price: sup_key, itm_key, gap_start, gap_end, days (a row starts after the latest end of the rows before it plus one day; nested or overlapping rows do not create a false gap). And currency_changes (a pair whose currency differs between consecutive rows; a price step across currencies is not comparable). The release test only forbids duplicates of the start date (3.4), so gaps can exist.

Two modes, and they do not give the same answer about the same pair:
- Without `window` only the holes between two rows of a pair are reported (internal gaps). The days before a pair's first row and the days after its last row are never reported, so a pair whose
  last row is closed (valid_to set) and ended long ago has no gap, although price_list_on of a later date returns no row for it. Use `window`, or compare with price_list_on, to find those pairs.
- With `window` (first, last day, inclusive) the result is limited to the days inside the window, and the window's days before a pair's first row (gap_start = the window's first day) and after
  the pair's last closed row (gap_end = the window's last day) are counted too; a pair with an open last row has no trailing gap. A pair that was introduced after the window starts therefore
  reports the whole stretch before its first row, for example 30 days for a pair whose first row starts 30 days after the first day of the window: that is "not priced yet", not a hole in a price list. With a window the same pairs as without it are reported, plus those leading and trailing days; how many there are is computed from the data.

`violations` comes from core check_contiguity, which costs most of the run time; the gaps and the currency changes are computed column wise and do not call it.

Args:
    price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency, con_key and change_reason.
    window: Optional keyword (first day, last day), both inclusive, as two dates; None (the default) reports only the internal gaps.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A PriceGaps named tuple. `violations` is the core check_contiguity frame (table, key, rule, detail). `gaps` has sup_key, itm_key, gap_start, gap_end and days, sorted by sup_key, itm_key and gap_start. `currency_changes` has sup_key, itm_key, valid_from, currency_before and currency_after.

Raises:
    FrameError: price_list is not a DataFrame, lacks a needed column, has duplicate column names, has a row without sup_key, itm_key or valid_from, has a unit_price that is not numeric, or holds a valid_from or valid_to that is not a date; window is not two dates, holds a number, a time zone or a null, or ends before it starts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import price_gaps
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pl = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
    ...                    "valid_from": ["2025-01-01", "2025-02-01"], "valid_to": ["2025-01-10", None],
    ...                    "unit_price": [10.0, 11.0], "currency": ["EUR", "DKK"], "con_key": [None, None], "change_reason": [None, None]})
    >>> res = price_gaps(pl, context=ctx)
    >>> res.gaps["days"].tolist()
    [21]
    >>> res.currency_changes[["currency_before", "currency_after"]].values.tolist()
    [['EUR', 'DKK']]
    >>> price_gaps(pl, window=("2024-12-22", "2025-03-01"), context=ctx).gaps["days"].tolist()
    [10, 21]

## Source columns

- `procurement.price_list.sup_key`
- `procurement.price_list.itm_key`
- `procurement.price_list.valid_from`
- `procurement.price_list.valid_to`
- `procurement.price_list.unit_price`
- `procurement.price_list.currency`
- `procurement.price_list.con_key`
- `procurement.price_list.change_reason`
