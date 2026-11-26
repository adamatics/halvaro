# supplier_spend

```python
supplier_spend(supplier_invoice: pd.DataFrame, supplier: pd.DataFrame, start: dt.date | str, end: dt.date | str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need what was spent per supplier and category in DKK over a range of invoice dates.

Rule: invoices dated from start to end, both days included; credit notes count negative.

## Args

supplier_invoice: Frame finance.supplier_invoice with sup_key, invoice_type, invoice_date and net_amount_dkk.
supplier: Frame procurement.supplier with sup_key and category, one row per supplier.
start: First day.
end: Last day.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, category, n_invoices and spend_dkk, sorted by supplier.

## Raises

FrameError: a column is missing, a supplier or an invoice key is duplicated, start is after end, or an invoice is from a supplier that is not in the supplier frame.
PeriodError: start or end is a number, not a date, an unreadable text or has a time zone.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import supplier_spend
>>> ctx = Context(stage="month12", role="analyst")
>>> import datetime as dt
>>> invoices = pd.DataFrame({"sup_key": ["SUP-1"] * 2, "invoice_type": ["invoice", "credit_note"], "invoice_date": ["2026-01-05", "2026-01-20"], "net_amount_dkk": [100.0, 30.0]})
>>> suppliers = pd.DataFrame({"sup_key": ["SUP-1"], "category": ["steel"]})
>>> supplier_spend(invoices, suppliers, dt.date(2026, 1, 1), dt.date(2026, 1, 31), context=ctx).values.tolist()
[['SUP-1', 'steel', 2, 70.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice.sup_key`, `finance.supplier_invoice.invoice_type`, `finance.supplier_invoice.invoice_date`, `finance.supplier_invoice.net_amount_dkk`, `procurement.supplier.sup_key`, `procurement.supplier.category`.
