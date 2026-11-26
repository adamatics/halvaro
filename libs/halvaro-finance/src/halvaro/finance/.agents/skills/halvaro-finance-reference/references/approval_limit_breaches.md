# approval_limit_breaches

```python
approval_limit_breaches(purchase_order: pd.DataFrame, buyer_grade: pd.DataFrame, *, limits: Sequence[tuple[Any, Any]] = ((3, 50000.0), (5, 250000.0), (None, 1000000.0)), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that the buyers of purchase orders had the authority for the value, by the grade of the buyer on the order date.

Rule: the limit depends on the grade level (PROPOSED: up to level 3 DKK 50,000, up to level 5 DKK 250,000, above DKK 1,000,000; the policy value is needed). An order above the limit of its buyer is a breach. The data has no approver, so only the buyer's authority is tested.

## Args

purchase_order: Frame procurement.purchase_order with po_key, total_value, currency, buyer_emp_key and order_date.
buyer_grade: Frame with po_key and grade_level (the level of the buyer at the order date, from halvaro-hr).
limits: A list of (grade level up to, limit in DKK) with increasing levels and None for the last step. Default PROPOSED as above.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with po_key, buyer_emp_key, order_date, grade_level, total_value_dkk, limit_dkk and breach.

## Raises

FrameError: a column is missing, po_key is not unique, limits is not a list of increasing steps ending in None, or an order has no buyer grade.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import approval_limit_breaches
>>> ctx = Context(stage="month12", role="analyst")
>>> orders = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "total_value": [60000.0, 1000.0], "currency": ["DKK"] * 2, "buyer_emp_key": ["EMP-000001"] * 2, "order_date": ["2026-01-05"] * 2})
>>> grades = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "grade_level": [3, 3]})
>>> approval_limit_breaches(orders, grades, context=ctx)[["po_key", "breach"]].values.tolist()
[['PO-1', True], ['PO-2', False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.purchase_order.po_key`, `procurement.purchase_order.total_value`, `procurement.purchase_order.currency`, `procurement.purchase_order.buyer_emp_key`, `procurement.purchase_order.order_date`.
