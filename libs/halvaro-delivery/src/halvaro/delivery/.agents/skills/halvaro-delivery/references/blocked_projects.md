# blocked_projects

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import blocked_projects`.

```python
blocked_projects(reservations_open: pd.DataFrame, stock: pd.DataFrame, as_of: DateLike, *, items: Sequence[str], active: Sequence[str], site: str | None = None, horizon_days: int | None = None, context: halvaro.core.access.Context) -> BlockedProjects
```

Use this when you need the active projects whose open reservations of given items cannot be met because the stock at the site is zero or less on a date.

A project is listed when it has an open reservation (qty_open above zero, reserved_demand output) of the given items, needed within `horizon_days` of the date (days already past count), where the stock of the item at the site is zero or less on the date (stock_on output). The horizon defaults to the parameter blocked_need_horizon_days of inventory.yaml (45, verified). With `site` only reservations at that site count; without it each reservation is judged at its own site. PROPOSED: policy.delivery.blocked_project_definition (needed): the generator truth selects by item and need date only, the test adds the site and the zero stock. A pair with no row in the stock frame counts as zero stock. A stock frame with an `as_of` column (stock_on output) must be for `as_of`.

Args:
    reservations_open: Output of reserved_demand; it needs prj_key, itm_key, site_key, qty_open (numeric) and needed_by_date, none of them null.
    stock: Output of stock_on; it needs site_key, itm_key and on_hand (numeric), one row per site and item, and when it has an as_of (or as_of_date) column that is one date equal to `as_of`.
    as_of: The day to judge on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
    items: The item keys to look at, a list or a single key.
    active: The active project keys, a list or a single key.
    site: Optional site key; only reservations at that site count.
    horizon_days: Optional whole number of days from zero to 36500 that a need may lie ahead; defaults to the parameter above.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A BlockedProjects tuple. `items` has one row per project and item with prj_key, itm_key, site_key, unmet_qty, n_reservations, earliest_needed_by, days_past_need (date minus earliest need, negative while the need is ahead) and on_hand, sorted by prj_key and itm_key. `projects` has prj_key, unmet_qty and n_items.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; as_of is not an ISO date, is a number or has a time zone; the stock frame is for another date than as_of, holds more than one date, has more than one row for a site and item or has nulls in site_key or itm_key; horizon_days is not a whole number from zero to 36500; qty_open or on_hand is not numeric or has nulls; a reservation has a null project, item, site or need date; items or active is a frame, a mapping or None.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import blocked_projects
    >>> ctx = Context(stage="month12", role="analyst")
    >>> res = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "itm_key": ["ITM-900001", "ITM-900001"], "site_key": ["SIT-900001", "SIT-900001"],
    ...                     "qty_open": [4.0, 2.0], "needed_by_date": ["2025-03-10", "2025-09-01"]})
    >>> stock = pd.DataFrame({"site_key": ["SIT-900001"], "itm_key": ["ITM-900001"], "on_hand": [0.0]})
    >>> r = blocked_projects(res, stock, "2025-03-01", items=["ITM-900001"], active=["PRJ-900001", "PRJ-900002"], horizon_days=45, context=ctx)
    >>> r.items[["prj_key", "unmet_qty", "days_past_need"]].to_dict("records")
    [{'prj_key': 'PRJ-900001', 'unmet_qty': 4.0, 'days_past_need': -9}]
    >>> r.projects["n_items"].tolist()
    [1]

## Source columns

- `inventory.reservation.prj_key`
- `inventory.reservation.itm_key`
- `inventory.reservation.site_key`
- `inventory.reservation.qty_open`
- `inventory.reservation.needed_by_date`
