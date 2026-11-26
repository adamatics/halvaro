# einvoice_format_share

```python
einvoice_format_share(customer_invoice: pd.DataFrame, *, le_key: str = 'LE-02', structured: tuple[str, ...] = ('xrechnung', 'zugferd', 'peppol_bis'), invoice_types: tuple[str, ...] | None = None, context: Context) -> pd.DataFrame
```

Use this when you need the share of structured e-invoices among the third party invoices of one entity, by month.

Rule: share = invoices whose format is structured / all invoices of the month, four decimals. Structured formats are every format except pdf (default xrechnung, zugferd and peppol_bis,
PROPOSED). Intercompany invoices (counterpart_le_key set) are left out. By default every document counts, credit notes included; invoice_types restricts the rows to those types when the
frame has invoice_type, for example ("invoice",) leaves credit notes out.

## Args

customer_invoice: Frame finance.customer_invoice with le_key, invoice_date, invoice_format and counterpart_le_key (and invoice_type to filter).
le_key: Entity to count (default LE-02, the German company).
structured: Tuple of the invoice formats that count as structured.
invoice_types: Tuple of invoice types to count, or None for every type (default None).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with period (text like 2025-02), n_invoices and n_structured (counts) and share (between 0 and 1, four decimals), one row per month with invoices.
Typed form: EinvoiceShareRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a column is missing, an invoice has no date or no format, or structured or invoice_types is a single text instead of a tuple.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import einvoice_format_share
>>> ctx = Context(stage="month3", role="analyst")
>>> inv = pd.DataFrame({"le_key": "LE-02", "invoice_date": ["2025-03-03", "2025-03-10", "2025-03-20"], "invoice_format": ["pdf", "xrechnung", "xrechnung"],
...                     "counterpart_le_key": [None, None, None]})
>>> einvoice_format_share(inv, context=ctx).loc[0, ["period", "n_invoices", "n_structured", "share"]].tolist() == ['2025-03', 3, 2, 0.6667]
True
```

## Typed result

`EinvoiceShareRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.customer_invoice.le_key`, `finance.customer_invoice.invoice_date`, `finance.customer_invoice.invoice_format`, `finance.customer_invoice.counterpart_le_key`, `finance.customer_invoice.invoice_type`.
