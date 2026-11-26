# spot_orders

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import spot_orders`.

```python
spot_orders(po_line: pd.DataFrame, purchase_order: pd.DataFrame, price_list: pd.DataFrame, *, framework_sup_key: str | None = None, item_type: pd.Series | None = None, rates: Mapping[str, float] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the lines of spot orders with their price, whether an expedite line is freight and the premium over the framework list price.

The lines are those of orders of order_type spot. freight is true for an expedite line of a service item (`item_type`: a Series itm_key to item_type, unique index) and is null without it (an expedite line alone does not say what it is). With `framework_sup_key` the lines of that supplier itself and of items outside its price list are left out (spot orders are for its items from other suppliers), and freight is tied to the goods: an expedite service line is freight only when a spot order of the same project and order date has a goods line (an item of the framework supplier's list, not a service, from another supplier); otherwise freight is False and `freight_unmatched` is True (an express service line with no goods order next to it); an express service line, matched or not, has no premium. freight_unmatched is False on every other row and without a framework supplier. With `framework_sup_key` and `rates` the framework list price of the failing supplier for the same item on the order date (the latest valid row that is not a spot quote; two such rows with the same valid_from are refused) is joined and premium = price in DKK over list price in DKK minus one; otherwise premium is null (prices of different currencies are never compared without a rate).

Args:
    po_line: The procurement.po_line frame, one row per po_key and line_no; it needs po_key, line_no, itm_key, unit_price (numeric), currency, price_source and expedite (True or False on every row).
    purchase_order: The procurement.purchase_order frame, one row per po_key; it needs po_key, order_type, sup_key, prj_key and order_date.
    price_list: The procurement.price_list frame; it needs sup_key, itm_key, valid_from, valid_to, unit_price, currency and change_reason, and is read only for a premium.
    framework_sup_key: The framework supplier whose list is the reference; give it together with `rates` for a premium.
    item_type: A Series from itm_key to item_type with a unique index; items of type service make expedite lines freight.
    rates: A mapping from currency to DKK per unit, positive numbers, from core; give it together with `framework_sup_key`.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns po_key, line_no, prj_key, itm_key, sup_key, order_date, unit_price, currency, price_source, expedite, freight (nullable boolean), freight_unmatched, premium (a ratio, null when not computed), sorted by po_key and line_no.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; po_line repeats a po_key and line_no or purchase_order repeats a po_key; a key, order_date or (for a premium) valid_from is null; unit_price is not numeric or has nulls; expedite is not True or False on every row; item_type is not a Series with a unique index; only one of framework_sup_key and rates is given; the framework list has two rows for an item with the same valid_from; a rate is not a positive number or a currency has no rate; a date is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import spot_orders
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pl = pd.DataFrame({"po_key": ["PO-900001", "PO-900002"], "line_no": [1, 1], "itm_key": ["ITM-900001", "ITM-900002"], "unit_price": [120.0, 50.0],
    ...                    "currency": ["DKK", "DKK"], "price_source": ["spot", "framework"], "expedite": [False, False]})
    >>> po = pd.DataFrame({"po_key": ["PO-900001", "PO-900002"], "order_type": ["spot", "standard"], "sup_key": ["SUP-900002", "SUP-900001"],
    ...                    "prj_key": ["PRJ-900001", "PRJ-900001"], "order_date": ["2025-03-01", "2025-03-01"]})
    >>> fw = pd.DataFrame({"sup_key": ["SUP-900001"], "itm_key": ["ITM-900001"], "valid_from": ["2025-01-01"], "valid_to": [None],
    ...                    "unit_price": [100.0], "currency": ["DKK"], "change_reason": ["annual"]})
    >>> r = spot_orders(pl, po, fw, framework_sup_key="SUP-900001", rates={"DKK": 1.0}, context=ctx)
    >>> r[["po_key", "premium"]].round(2).to_dict("records")
    [{'po_key': 'PO-900001', 'premium': 0.2}]

## Source columns

- `procurement.po_line.po_key`
- `procurement.po_line.line_no`
- `procurement.po_line.itm_key`
- `procurement.po_line.unit_price`
- `procurement.po_line.currency`
- `procurement.po_line.price_source`
- `procurement.po_line.expedite`
- `procurement.purchase_order.po_key`
- `procurement.purchase_order.order_type`
- `procurement.purchase_order.sup_key`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.order_date`
- `procurement.price_list.sup_key`
- `procurement.price_list.itm_key`
- `procurement.price_list.valid_from`
- `procurement.price_list.valid_to`
- `procurement.price_list.unit_price`
- `procurement.price_list.currency`
- `procurement.price_list.change_reason`
