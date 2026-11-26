# invoice_tie_out

Module `halvaro.esg.activity`. Import: `from halvaro.esg import invoice_tie_out`.

```python
invoice_tie_out(c: pd.DataFrame, si: pd.DataFrame, *, tolerance: float = 0.02, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to tie the cost of the consumption rows to the net amount of the energy invoice they come from.

The cost of the consumption rows per source_sinv_key is compared with the net amount of the energy invoice. Rows without a source_sinv_key (null or empty), such as purchase order fuel and the month after the last invoices (T19), are not an error and are not listed.
PROPOSED: tolerance 0.02 as in the plan.

Args:
    c: The energy-esg.energy_consumption table, with the columns source_sinv_key and cost_amount.
    si: The finance.supplier_invoice table, with the columns sinv_key, net_amount and document_kind.
    tolerance: The largest absolute difference that still counts as within (PROPOSED default 0.02); a finite number of zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns source_sinv_key, cost_sum, net_amount, difference, within (|difference| <= tolerance) and status (ok, outside_tolerance, invoice_missing, not_energy), sorted by source_sinv_key.

Raises:
    FrameError: c lacks source_sinv_key or cost_amount; si lacks sinv_key, net_amount or document_kind.
    FrameError: tolerance is not a finite number of zero or more; finance.supplier_invoice has two rows for a sinv_key; cost_amount or net_amount is not numeric; a row with a source_sinv_key has a null cost_amount.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import invoice_tie_out
    >>> c = pd.DataFrame({"source_sinv_key": ["SINV-900001", "SINV-900001", "SINV-900002"], "cost_amount": [60.0, 40.0, 10.0]})
    >>> si = pd.DataFrame({"sinv_key": ["SINV-900001", "SINV-900002"], "net_amount": [100.0, 12.0], "document_kind": ["energy", "energy"]})
    >>> out = invoice_tie_out(c, si, context=ctx)
    >>> out[["source_sinv_key", "difference", "status"]].values.tolist()
    [['SINV-900001', 0.0, 'ok'], ['SINV-900002', -2.0, 'outside_tolerance']]

## Source columns

- `energy-esg.energy_consumption.source_sinv_key`
- `energy-esg.energy_consumption.cost_amount`
- `finance.supplier_invoice.sinv_key`
- `finance.supplier_invoice.net_amount`
- `finance.supplier_invoice.document_kind`
