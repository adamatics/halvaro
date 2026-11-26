# ageing

```python
ageing(open_items: pd.DataFrame, as_of: dt.date, *, party: str = 'cus_key', buckets: Sequence[int] = (0, 30, 60, 90), context: Context) -> pd.DataFrame
```

Use this when you need open items grouped by party and by days past due on a date.

Rule: the amount of an item is open_amount less retention_held (retention is not aged: it falls due on its release date). days past due = as_of less due_date. The default buckets are not due (0
days or less), 1 to 30, 31 to 60, 61 to 90 and over 90 days; items without a due date are their own bucket no_due_date, and the buckets add up to the total of the open items. Items with
amount zero are left out. The bucket bounds are PROPOSED (the policy value is needed).

## Args

open_items: The frame returned by open_items_ar (party cus_key) or open_items_ap (party sup_key).
as_of: The date the days past due are counted to (a date).
party: Column of the party to group by: cus_key (default) or sup_key.
buckets: Upper bounds in days of the buckets after the not due bucket (default 0, 30, 60, 90).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with le_key, the party column (cus_key or sup_key), bucket (text such as 31-60), n_items (count) and amount (entity currency), ordered by entity, party and bucket.
Typed form: AgeingRow.from_frame(the frame) for customers and AgeingApRow.from_frame(the frame) for suppliers, one frozen model per row.

## Raises

FrameError: the frame lacks a required column or a due date cannot be read.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import Context
>>> ctx = Context(stage="month12", role="analyst")
>>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
>>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
>>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
>>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
>>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
>>> from halvaro.finance import ageing, open_items_ar
>>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
>>> ageing(items, dt.date(2025, 3, 31), context=ctx)[["cus_key", "bucket", "n_items", "amount"]].values.tolist()
[['CUS-1', '31-60', 1, 900.0]]
```

## Typed result

`AgeingRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.customer_invoice.due_date`, `finance.customer_invoice.le_key`, `finance.customer_invoice.cus_key`, `finance.supplier_invoice.due_date`, `finance.supplier_invoice.sup_key`.
