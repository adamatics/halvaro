# cause_bars_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import cause_bars_view`.

```python
cause_bars_view(cause_shares: pd.DataFrame, *, view: str = 'all_events', as_of: DateLike | None = None, legacy: int | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need delay days by cause code for one view of the cause shares, ready for a bar chart.

The bars are the delay days by cause code for one view of `cause_shares`: cause_code, days, events and share (days over the days of the view, recomputed from the summed rows) with responsible parties summed. A null cause code is shown as '(unknown)'. Sorted by days, largest first, then cause code.

Args:
    cause_shares: The cause shares frame; it needs view, cause_code, days and events.
    view: The view of the frame to draw (default 'all_events').
    as_of: Optional as-of date, shown in the caption.
    legacy: Optional number of legacy projects, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'bars': `frame` (cause_code, days, events, share rounded to 4 places; sorted by days descending, then cause_code), x cause_code, y days, n the number of events of the view.

Raises:
    FrameError: cause_shares is not a DataFrame or lacks a needed column; cause_shares has no rows for the view.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import cause_bars_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cs = pd.DataFrame({"view": ["all_events"] * 3, "cause_code": ["WTR", "WTR", "SUP"], "days": [3.0, 1.0, 4.0], "events": [1, 1, 2]})
    >>> spec = cause_bars_view(cs, context=ctx)
    >>> spec.frame["cause_code"].tolist()
    ['SUP', 'WTR']
    >>> spec.frame["share"].tolist()
    [0.5, 0.5]
    >>> spec.n
    4

## Source columns

- `projects.delay_event.cause_code`
- `projects.delay_event.days`
