# einvoice_gap

```python
einvoice_gap(customer_invoice: pd.DataFrame, as_of: dt.date, *, le_key: str = 'LE-02', months: int = 6, context: Context) -> Envelope
```

Use this when you need the customers of one entity that still receive pdf invoices shortly before structured invoices become mandatory.

Rule: the invoices of the entity dated after as_of less `months` months (a rolling window: the same day `months` months earlier, the day clipped to the length of that month) up to and including as_of,
without intercompany invoices. A customer is listed when at least one of those invoices is a pdf. last_invoice_date and last_format are those of the customer's latest invoice in the window; invoices of the
same day are ordered by inv_key when the frame has that column, else by position.
days_to_mandatory = the fact fin.e_invoicing.DE.mandatory_issue_from less as_of, in days (negative after the date). The fact fin.e_invoicing.DE.pdf_allowed_until is read and carried in the
envelope with its status; it does not bound the window or the list. Both facts have status VERIFY and the status is carried in the envelope.

## Args

customer_invoice: Frame finance.customer_invoice with le_key, cus_key, invoice_date, invoice_format and counterpart_le_key.
as_of: The date the window ends on (a date).
le_key: Entity to look at (default LE-02, the German company).
months: Length of the window in whole months, one or more (default 6, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with cus_key, n_pdf and n_invoices (counts), last_invoice_date, last_format and days_to_mandatory (days), the customers with most pdf invoices first.
Typed form: EinvoiceGapRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing or months is not a whole number of one or more.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import einvoice_gap
>>> ctx = Context(stage="month3", role="analyst")
>>> inv = pd.DataFrame({"le_key": "LE-02", "cus_key": ["CUS-1", "CUS-2"], "invoice_date": ["2025-03-03", "2025-03-04"], "invoice_format": ["pdf", "xrechnung"],
...                     "counterpart_le_key": [None, None]})
>>> r = einvoice_gap(inv, dt.date(2025, 3, 31), context=ctx).value
>>> r["cus_key"].tolist()
['CUS-1']
```

## Typed result

`EinvoiceGapRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.e_invoicing.DE.mandatory_issue_from`, `fin.e_invoicing.DE.pdf_allowed_until`.

Source columns: `finance.customer_invoice.le_key`, `finance.customer_invoice.cus_key`, `finance.customer_invoice.invoice_date`, `finance.customer_invoice.invoice_format`, `finance.customer_invoice.counterpart_le_key`.
