# open_items_ar

```python
open_items_ar(customer_invoice: pd.DataFrame, payment_allocation: pd.DataFrame, payment: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, as_of: dt.date, *, context: Context) -> pd.DataFrame
```

Use this when you need the open receivables of every domestic invoice and opening item on a date.

Rule: open_amount = invoice amount including retention - payments allocated up to and including the date - amount written off up to the date; credit notes are negative. retention_held is the
retention billed and not yet released on the date; the receivable account holds open_amount less retention_held and the retention account holds the rest. Only payments with a date up to
the date count, never the stored paid_amount or status (values at the release date). Intercompany invoices are not receivables and are left out.

## Args

customer_invoice: Frame finance.customer_invoice with inv_key, le_key, cus_key, invoice_type, invoice_date, due_date, gross_amount_le, retention_amount_le, retention_release_date,
    written_off_date and counterpart_le_key.
payment_allocation: Frame finance.payment_allocation, the allocation of payments to documents.
payment: Frame finance.payment with the allocation key columns and payment_date.
opening_balance_item: Frame finance.opening_balance_item, open items at the start of the window; it also gives the currency of each entity.
gl_account: Frame finance.gl_account with control_type per account (ar, retention).
as_of: The date the open items are taken on (a date).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with item_key, source (invoice or opening), le_key, cus_key, inv_key, document_date, due_date, currency, invoice_amount, paid, written_off, open_amount, retention_held (all in the
entity currency) and release_date, one row per invoice and opening item.
Typed form: OpenItemArRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a frame lacks a required column, a date cannot be read, an allocation names a payment that is not in the payment frame, or the opening items are empty (the entity currencies are taken from them).
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
>>> from halvaro.finance import open_items_ar
>>> r = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
>>> r[r["source"] == "invoice"][["open_amount", "retention_held"]].values.tolist()
[[1000.0, 100.0]]
```

## Typed result

`OpenItemArRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.customer_invoice.inv_key`, `finance.customer_invoice.le_key`, `finance.customer_invoice.cus_key`, `finance.customer_invoice.invoice_type`, `finance.customer_invoice.invoice_date`, `finance.customer_invoice.due_date`, `finance.customer_invoice.gross_amount_le`, `finance.customer_invoice.retention_amount_le`, `finance.customer_invoice.retention_release_date`, `finance.customer_invoice.written_off_date`, `finance.customer_invoice.counterpart_le_key`, `finance.payment_allocation.le_key`, `finance.payment_allocation.bank_account`, `finance.payment_allocation.payment_no`, `finance.payment_allocation.allocation_kind`, `finance.payment_allocation.document_type`, `finance.payment_allocation.booked_amount`, `finance.payment_allocation.inv_key`, `finance.payment_allocation.opening_item_ref`, `finance.payment.le_key`, `finance.payment.bank_account`, `finance.payment.payment_no`, `finance.payment.payment_date`, `finance.opening_balance_item.le_key`, `finance.opening_balance_item.gl_key`, `finance.opening_balance_item.item_ref`, `finance.opening_balance_item.document_date`, `finance.opening_balance_item.due_date`, `finance.opening_balance_item.amount`, `finance.opening_balance_item.currency`, `finance.opening_balance_item.cus_key`, `finance.gl_account.gl_key`, `finance.gl_account.control_type`.
