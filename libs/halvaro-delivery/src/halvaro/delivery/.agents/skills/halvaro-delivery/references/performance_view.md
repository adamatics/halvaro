# performance_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import performance_view`.

```python
performance_view(performance: pd.DataFrame, lead_on: pd.DataFrame | None = None, *, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need the on time share of suppliers as bars, with the lead time steps on the side.

The on time share comes from `supplier_performance_window` (sup_key, lines_due, lines_on_time, on_time_percent recomputed from the summed lines, never averaged) and, with `lead_on` (lead_time_on), the lead time steps are in extra['lead_times'] (sup_key, itm_key, previous_weeks, lead_time_weeks, change_weeks).

Args:
    performance: The output of supplier_performance_window; it needs sup_key, lines_due and lines_on_time (no nulls, never more on time than due).
    lead_on: Optional output of lead_time_on; it needs sup_key, itm_key and lead_time_weeks, and previous_weeks and change_weeks are carried when present.
    as_of: Optional as-of date, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'bars': `frame` (sup_key, lines_due, lines_on_time, on_time_percent rounded to 2 places and null when no line is due; sorted by sup_key), x sup_key, y on_time_percent, n the summed lines due, extra['lead_times'] the lead time frame when lead_on is given.

Raises:
    FrameError: performance or lead_on is not a DataFrame or lacks a needed column; the performance frame has nulls in lines_due or lines_on_time or more lines on time than due.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import performance_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900002"], "lines_due": [4, 4, 5], "lines_on_time": [3, 1, 5]})
    >>> spec = performance_view(perf, context=ctx)
    >>> spec.frame["sup_key"].tolist()
    ['SUP-900001', 'SUP-900002']
    >>> spec.frame["on_time_percent"].tolist()
    [50.0, 100.0]
    >>> spec.n
    13

## Source columns

- `procurement.supplier_performance.sup_key`
- `inventory.lead_time.lead_time_weeks`
