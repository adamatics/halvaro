# repeat_faults

Module `halvaro.grid.faults`. Import: `from halvaro.grid import repeat_faults`.

```python
repeat_faults(fault_event: pd.DataFrame, *, gap_days: int = 45, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to find the repeat faults, the faults on an element that follow an earlier fault of the same element within a number of days.

A fault is a repeat when the same element had a fault at most `gap_days` days before (PROPOSED 45, as the generator's hazard rule), counted from the time of the fault before. The repeat flag is
recomputed from the times and compared with the stored repeat_of_tkt_key.

Args:
    fault_event: The service.fault_event table; needs net_key, fault_ts, tkt_key and repeat_of_tkt_key.
    gap_days: The largest number of days between a fault and the fault before it for it to count as a repeat (PROPOSED 45); a whole number, zero or more.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame sorted by element and time with the columns tkt_key, net_key, fault_ts, repeat (recomputed), chain_length (consecutive repeats up to and including this fault, 0 for a first fault),
    previous_tkt_key, gap_days, linked (the stored repeat_of_tkt_key is set) and agrees (the stored link points to the fault before when repeat, and is null otherwise).

Raises:
    FrameError: fault_event lacks a needed column; gap_days is not a whole number of zero or more; a tkt_key appears in more than one row; a fault time cannot be read.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import repeat_faults
    >>> ctx = Context(stage="month12", role="analyst")
    >>> fe = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002", "TKT-900003"], "net_key": ["NET-900001"] * 3,
    ...                    "fault_ts": ["2024-03-01", "2024-03-10", "2024-06-01"], "repeat_of_tkt_key": [None, "TKT-900001", None]})
    >>> out = repeat_faults(fe, context=ctx)
    >>> out["repeat"].tolist(), out["chain_length"].tolist(), out["agrees"].tolist()
    ([False, True, False], [0, 1, 0], [True, True, True])

## Source columns

- `service.fault_event.net_key`
- `service.fault_event.fault_ts`
- `service.fault_event.tkt_key`
- `service.fault_event.repeat_of_tkt_key`
