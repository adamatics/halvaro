# bad_debt_candidates

```python
bad_debt_candidates(open_items: pd.DataFrame, as_of: dt.date, *, context: Context) -> Envelope
```

Use this when you need the receivables that are overdue by at least the write-off days of the fact.

Rule: a receivable is a candidate when days past due = as_of less due_date is at least the fact fin.payment.bad_debt_write_off_after_days_overdue (status VERIFY) and the receivable net of
retention (open_amount less retention_held) is above zero; retention is not collectable before its release date. The rows are ordered by entity, then longest overdue first.

## Args

open_items: The frame returned by open_items_ar.
as_of: The date the days past due are counted to (a date).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is the frame of the overdue open items: item_key, source, le_key, cus_key, inv_key, document_date, due_date, currency, invoice_amount, paid, written_off, open_amount,
retention_held, release_date as in open_items_ar, and two columns added, receivable_net (entity currency) and days_past_due (days). The envelope carries the VERIFY status of the fact.
Typed form: BadDebtRow.from_frame(envelope.value), one frozen model per row.

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
>>> from halvaro.finance import bad_debt_candidates, open_items_ar
>>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2026, 6, 30), context=ctx)
>>> r = bad_debt_candidates(items, dt.date(2026, 6, 30), context=ctx).value
>>> r[["item_key", "receivable_net", "days_past_due"]].values.tolist() == [["I1", 900.0, (dt.date(2026, 6, 30) - dt.date(2025, 2, 10)).days]]
True
```

## Typed result

`BadDebtRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.payment.bad_debt_write_off_after_days_overdue`.

Source columns: `finance.customer_invoice.due_date`, `finance.customer_invoice.le_key`.
