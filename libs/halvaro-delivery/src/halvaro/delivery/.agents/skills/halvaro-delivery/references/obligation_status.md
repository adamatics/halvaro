# obligation_status

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import obligation_status`.

```python
obligation_status(obligation: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the status of each contract obligation on a date, worked out from its dates, and whether its deadline was met.

The status is completed (completed_date on or before the date), overdue (not completed and due_date before the date) or open. For obligations with a trigger and a deadline, `met_recomputed` is whether it was completed on or before triggered_on plus the deadline (hours counted as whole days rounded up: the release compares dates, not hours; null while not completed). For an obligation without a trigger that carries a stored met_deadline, `met_recomputed` is completed_date on or before due_date (null while not completed on the date); an obligation that has a trigger keeps the trigger rule above, also when its unit is not read (null). Obligations without a stored met_deadline have no recomputed result. The stored status and met_deadline stay beside as stored_status and stored_met_deadline. The stored statuses waived, breached, in_force and closed are kept (the dates cannot derive them). Deadline units hours, days and weeks are read; an obligation with another unit has no recomputed result.

Args:
    obligation: The contracts.obligation frame, one row per con_key and obligation_no; it needs con_key, obligation_no, due_date, status, completed_date, triggered_on, deadline_value, deadline_unit and met_deadline.
    as_of: The day of the status (a date, a Timestamp or an ISO text); a time of day is dropped.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns of the obligation frame except status and met_deadline, plus status_on, met_recomputed (nullable boolean), stored_status, stored_met_deadline and as_of, sorted by con_key and obligation_no, index reset.

Raises:
    FrameError: obligation is not a DataFrame, has duplicate column names, lacks a needed column or repeats a con_key and obligation_no; due_date, completed_date or triggered_on holds a value that is not a date; as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import obligation_status
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ob = pd.DataFrame({"con_key": ["CON-900001", "CON-900001", "CON-900001"], "obligation_no": [1, 2, 3],
    ...                    "due_date": ["2026-01-10", "2026-01-10", "2026-03-01"], "status": ["open", "open", "open"],
    ...                    "completed_date": ["2026-01-05", None, None], "triggered_on": [None, None, None],
    ...                    "deadline_value": [None, None, None], "deadline_unit": [None, None, None], "met_deadline": [None, None, None]})
    >>> obligation_status(ob, "2026-02-01", context=ctx)["status_on"].tolist()
    ['completed', 'overdue', 'open']

## Source columns

- `contracts.obligation.con_key`
- `contracts.obligation.obligation_no`
- `contracts.obligation.due_date`
- `contracts.obligation.status`
- `contracts.obligation.completed_date`
- `contracts.obligation.triggered_on`
- `contracts.obligation.deadline_value`
- `contracts.obligation.deadline_unit`
- `contracts.obligation.met_deadline`
