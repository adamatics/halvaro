# supplier_performance_window

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import supplier_performance_window`.

```python
supplier_performance_window(performance: pd.DataFrame, first_period: str, last_period: str, *, sup_key: str | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the on time share of suppliers over a window of months, weighted by lines.

On time share over a window of months (inclusive, text YYYY-MM) by summed lines, never by averaging the monthly percentages. The input is supplier_performance_recompute or the stored table. Suppliers without lines in the window are absent. A null period is refused.

Args:
    performance: Output of supplier_performance_recompute or the procurement.supplier_performance table; it needs sup_key, period (YYYY-MM, no nulls), lines_due and lines_on_time (numeric without nulls, lines_on_time not above lines_due), one row per supplier and period.
    first_period: First month of the window as text YYYY-MM.
    last_period: Last month of the window as text YYYY-MM, not before first_period.
    sup_key: Optional supplier key as text; limits the result to that supplier.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns sup_key, lines_due, lines_on_time, on_time_percent (null when the supplier has no lines due) and n_months, one row per supplier, sorted by sup_key.

Raises:
    FrameError: performance is not a DataFrame, has duplicate column names or lacks a needed column; sup_key is not one key as text; a period is null; first_period or last_period is not a month as text YYYY-MM; lines_due or lines_on_time is not numeric or has nulls; a supplier key is null or a supplier has more than one row for a month; a row has more lines on time than lines due or negative lines; the window ends before it starts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import supplier_performance_window
    >>> ctx = Context(stage="month12", role="analyst")
    >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900001"], "period": ["2031-01", "2031-02", "2031-03"],
    ...                      "lines_due": [10, 30, 5], "lines_on_time": [10, 15, 0]})
    >>> r = supplier_performance_window(perf, "2031-01", "2031-02", context=ctx)
    >>> r.to_dict("records")
    [{'sup_key': 'SUP-900001', 'lines_due': 40, 'lines_on_time': 25, 'on_time_percent': 62.5, 'n_months': 2}]

## Source columns

- `procurement.supplier_performance.sup_key`
- `procurement.supplier_performance.period`
- `procurement.supplier_performance.lines_due`
- `procurement.supplier_performance.lines_on_time`
