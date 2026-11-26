# fault_causes

Module `halvaro.grid.faults`. Import: `from halvaro.grid import fault_causes`.

```python
fault_causes(fault_event: pd.DataFrame, group: Iterable[Any] | None = None, *, window: tuple[Any, ...] | None = None, allowed_causes: Iterable[Any] | None = None, refuse_words: tuple[str, ...] = ('intent', 'deliberate', 'blame'), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the share of each recorded cause among the faults of a group in a window of days.

The group defaults to all faults and the window (first, last, in days) to all time. `allowed_causes` (optional) is the closed list the caller accepts: a cause outside it, or a missing cause, raises
FrameError, so wording of intent or blame cannot enter a result. Faults without a cause are counted as 'unknown' when allowed_causes is not given. Without allowed_causes a recorded cause that contains
one of `refuse_words` (PROPOSED: the three words of intent and blame of the default; the plan keeps statements of intent out of results) raises FrameError.

Args:
    fault_event: The service.fault_event table; needs net_key, fault_ts and cause (the columns fault_type and detected_by are sources of the function but are not read).
    group: Optional net keys (one key as text, or an iterable); default all faults.
    window: Optional (first, last) dates, both days included, in order; default all time.
    allowed_causes: Optional closed list of accepted causes; a cause outside it, or a missing cause, raises FrameError.
    refuse_words: Words (a tuple, PROPOSED: the default of the signature) that may not occur in a recorded cause when allowed_causes is not given.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns cause, n, share (of n_total, rounded to 4 places; null when there are no faults) and n_total, sorted by n descending and then by cause.

Raises:
    FrameError: fault_event lacks a needed column; the window is not a pair of dates in order; refuse_words is a single text; allowed_causes is a single text; a cause is outside allowed_causes or missing; a cause contains a refused word.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import fault_causes
    >>> ctx = Context(stage="month12", role="analyst")
    >>> fe = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900002"], "fault_ts": ["2024-03-01", "2024-03-05", "2024-03-09"],
    ...                    "cause": ["wear", "wear", "load"]})
    >>> out = fault_causes(fe, context=ctx)
    >>> out["cause"].tolist(), out["n"].tolist(), out["share"].tolist()
    (['wear', 'load'], [2, 1], [0.6667, 0.3333])

## Source columns

- `service.fault_event.net_key`
- `service.fault_event.fault_ts`
- `service.fault_event.cause`
- `service.fault_event.fault_type`
- `service.fault_event.detected_by`
