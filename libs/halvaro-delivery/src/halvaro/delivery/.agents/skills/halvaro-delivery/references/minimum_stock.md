# minimum_stock

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import minimum_stock`.

```python
minimum_stock(stock_movement: pd.DataFrame, lead_time: pd.DataFrame, item: pd.DataFrame, as_of: DateLike, *, window_weeks: float = 52.0, usage_types: Sequence[str] = ('issue_project', 'issue_ticket'), min_floor: float = 1.0, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need a suggested minimum and order up to level of stock per stocked site and item from recent usage and lead time.

Minimum, order up to level and cover weeks per stocked (site, item) pair from the usage in the last `window_weeks` weeks before the date (PROPOSED 52, the issues of `usage_types`) and the lead time of the item's preferred supplier on the date. PROPOSED rule (policy.delivery.minimum_stock_rule is needed; LOW confidence): rate = units issued per week over the window, or over the weeks since the first movement when the data starts inside it (`history_weeks`); min = max(`min_floor`, ceil(rate x (lead time weeks + cover_weeks_min)), ceil(event_cover x average issue quantity)); order up to = max(min + 1, ceil(min + rate x cover_weeks_order), min + ceil(event_cover x average issue quantity)); the cover parameters are the generator values procurement.yaml#stock (cover_weeks_min 2, cover_weeks_order 6, event_cover 1.5, synthetic). Pack sizes and fixed levels set in the generator config are not applied. Pairs without usage in the window and items that are not stocked are not listed. The result is a suggestion: compare it with `stock_level.min_level` in the measured notes, it is not that table.

Args:
    stock_movement: The inventory.stock_movement frame; it needs site_key, itm_key, movement_date, movement_type and qty (no nulls; issues are negative).
    lead_time: The inventory.lead_time frame; it needs sup_key, itm_key, valid_from, valid_to and lead_time_weeks, as lead_time_on reads it.
    item: The inventory.item frame; it needs itm_key (one row per item), stocked and preferred_sup_key, and critical when the flag should be carried.
    as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
    window_weeks: Length of the usage window in weeks, a number above zero (default 52.0, PROPOSED).
    usage_types: The movement types that count as usage, a tuple of text (default issue_project and issue_ticket).
    min_floor: The lowest minimum quantity (default 1.0).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns site_key, itm_key, sup_key, lead_time_weeks, rate_per_week, avg_issue_qty, n_issues, history_weeks, min_qty, order_up_to_qty, cover_weeks (min over rate; null without usage) and critical (only when the item frame has the flag), sorted by site_key and itm_key.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; inventory.item has more than one row for an item; usage_types is a text instead of a tuple; window_weeks is not a positive number; as_of is not an ISO date, is a number or has a time zone; qty has nulls; the movements of an item that inventory.item does not hold; a usage movement has a positive quantity; a listed item has no lead time row on the date for its preferred supplier; inventory.item.critical has nulls; lead_time has a value that lead_time_on refuses.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import minimum_stock
    >>> ctx = Context(stage="month12", role="analyst")
    >>> mv = pd.DataFrame({"site_key": ["SIT-900001"] * 3, "itm_key": ["ITM-900001"] * 3, "movement_type": ["issue_project"] * 3,
    ...                    "movement_date": ["2031-05-01", "2031-05-08", "2031-05-15"], "qty": [-2.0, -2.0, -2.0]})
    >>> lt = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"], "valid_from": ["2031-01-01"], "valid_to": [None], "lead_time_weeks": [4.0]})
    >>> item = pd.DataFrame({"itm_key": ["ITM-900001"], "stocked": [True], "preferred_sup_key": ["SUP-900001"]})
    >>> r = minimum_stock(mv, lt, item, "2031-05-21", context=ctx)
    >>> r[["itm_key", "n_issues", "min_qty", "order_up_to_qty"]].to_dict("records")
    [{'itm_key': 'ITM-900001', 'n_issues': 3, 'min_qty': 12.0, 'order_up_to_qty': 24.0}]

## Source columns

- `inventory.stock_movement.site_key`
- `inventory.stock_movement.itm_key`
- `inventory.stock_movement.movement_date`
- `inventory.stock_movement.movement_type`
- `inventory.stock_movement.qty`
- `inventory.lead_time.sup_key`
- `inventory.lead_time.itm_key`
- `inventory.lead_time.valid_from`
- `inventory.lead_time.valid_to`
- `inventory.lead_time.lead_time_weeks`
- `inventory.item.itm_key`
- `inventory.item.stocked`
- `inventory.item.preferred_sup_key`
