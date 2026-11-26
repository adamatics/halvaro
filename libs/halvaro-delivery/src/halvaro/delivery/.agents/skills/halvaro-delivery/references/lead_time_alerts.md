# lead_time_alerts

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import lead_time_alerts`.

```python
lead_time_alerts(lead_on: pd.DataFrame, *, min_rise_weeks: float = 8.0, min_rise_percent: float = 25.0, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the supplier and item pairs whose lead time rose sharply against the previous valid row.

The pairs of a lead_time_on frame whose lead time rose by at least min_rise_weeks AND at least min_rise_percent against the previous valid row (PROPOSED policy.delivery.lead_time_alert, needed: 8 weeks and 25 percent; the threshold must exceed the normal drift of a lead time in either direction). Rows without a previous value are never alerts.

Args:
    lead_on: Output of lead_time_on; it needs sup_key, itm_key, lead_time_weeks, previous_weeks, change_weeks and change_percent.
    min_rise_weeks: The smallest rise in weeks that counts, a number of zero or more (default 8.0, PROPOSED).
    min_rise_percent: The smallest rise in percent that counts, a number of zero or more (default 25.0, PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns of the input and nothing more, only the rows that meet both thresholds, sorted by change_weeks (high first), then sup_key and itm_key.

Raises:
    FrameError: lead_on is not a DataFrame, has duplicate column names or lacks a needed column; min_rise_weeks or min_rise_percent is not a number of zero or more.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import lead_time_alerts
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lt = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900002"], "itm_key": ["ITM-900001", "ITM-900002", "ITM-900001"],
    ...                    "lead_time_weeks": [24.0, 14.0, 6.0], "previous_weeks": [12.0, 12.0, None],
    ...                    "change_weeks": [12.0, 2.0, None], "change_percent": [100.0, 16.7, None]})
    >>> lead_time_alerts(lt, context=ctx)[["sup_key", "itm_key", "change_weeks"]].to_dict("records")
    [{'sup_key': 'SUP-900001', 'itm_key': 'ITM-900001', 'change_weeks': 12.0}]

## Source columns

- `inventory.lead_time.lead_time_weeks`
