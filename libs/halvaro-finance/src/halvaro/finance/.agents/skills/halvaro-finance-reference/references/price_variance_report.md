# price_variance_report

```python
price_variance_report(supplier_invoice_line: pd.DataFrame, supplier_invoice: pd.DataFrame, *, price_steps: pd.DataFrame | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need how far the invoiced prices of each supplier and item sit from the purchase order price.

Rule: credit notes and lines without a PO price are left out. The difference of a line is (invoice price less PO price) over the PO price, in percent. Per supplier, item and currency the report gives the number of lines, the summed price variance (contract currency, to the cent) and the mean, standard deviation and largest absolute difference in percent. With a price_steps frame the step is added and step_in_variance says whether the mean difference reaches half of the step (the step sits in the PO price, so it is not in the invoice variance).

## Args

supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, itm_key, unit_price, po_unit_price, price_variance, currency and invoice_type.
supplier_invoice: Frame finance.supplier_invoice with sinv_key and sup_key, one row per invoice.
price_steps: The result of price_steps, or a frame with sup_key, itm_key and step_percent, one row per supplier and item. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, itm_key, currency, n_lines, price_variance, mean_diff_percent, sd_diff_percent and max_abs_diff_percent (and step_percent and step_in_variance with price_steps), sorted by supplier, item and currency.

## Raises

FrameError: a column is missing, supplier_invoice repeats an invoice key, an invoice line belongs to an invoice that is not in supplier_invoice, a PO price is 0, a line with a PO price has no item or currency, or price_steps repeats a supplier and item.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import price_variance_report
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"sinv_key": ["INV-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "po_unit_price": [10.0], "price_variance": [10.0], "currency": ["EUR"], "invoice_type": ["invoice"]})
>>> invoices = pd.DataFrame({"sinv_key": ["INV-1"], "sup_key": ["SUP-1"]})
>>> price_variance_report(lines, invoices, context=ctx)[["sup_key", "itm_key", "n_lines", "price_variance", "mean_diff_percent"]].values.tolist()
[['SUP-1', 'ITM-1', 1, 10.0, 10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice_line.sinv_key`, `finance.supplier_invoice_line.itm_key`, `finance.supplier_invoice_line.quantity`, `finance.supplier_invoice_line.unit_price`, `finance.supplier_invoice_line.po_unit_price`, `finance.supplier_invoice_line.price_variance`, `finance.supplier_invoice_line.currency`, `finance.supplier_invoice_line.invoice_type`, `finance.supplier_invoice.sinv_key`, `finance.supplier_invoice.sup_key`.
