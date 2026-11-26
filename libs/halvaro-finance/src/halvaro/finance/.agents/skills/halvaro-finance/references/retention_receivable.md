# retention_receivable

```python
retention_receivable(open_items: pd.DataFrame, *, context: Context) -> pd.DataFrame
```

Use this when you need the retention held on receivables per item and in total per entity.

Rule: the items are the rows of the open items of receivables whose retention_held is not zero; the total row of an entity and currency is the sum of retention_held over all its open items.
The retention account of the ledger holds exactly the total. The release date is the release date of the invoice, or the due date of an opening item.

## Args

open_items: The frame returned by open_items_ar.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with item_key (empty on a total row), source (invoice, opening or total), le_key, cus_key, document_date, release_date, currency and retention_held (entity currency), items first and
the total row of each entity last.
Typed form: RetentionRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: the frame lacks a required column.
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
>>> from halvaro.finance import open_items_ar, retention_receivable
>>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
>>> retention_receivable(items, context=ctx)[["source", "retention_held"]].values.tolist()
[['invoice', 100.0], ['total', 100.0]]
```

## Typed result

`RetentionRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.customer_invoice.inv_key`, `finance.customer_invoice.le_key`, `finance.customer_invoice.cus_key`, `finance.customer_invoice.retention_amount_le`, `finance.customer_invoice.retention_release_date`, `finance.opening_balance_item.due_date`.
