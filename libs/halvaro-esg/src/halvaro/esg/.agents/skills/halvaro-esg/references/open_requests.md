# open_requests

Module `halvaro.esg.data_requests`. Import: `from halvaro.esg import open_requests`.

```python
open_requests(R: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the status of every customer sustainability request on a given day, worked out from its dates.

The status of every request on a day, from its dates and not from the snapshot `status`: not_received (received after the day), answered (answered on or before the day), overdue (due before
the day and not answered), open (received, due on or after the day, not answered). The stored status is informative only: the snapshot is as of the release; a stored 'open' for a request that is overdue as of the day is a difference, not hidden.

Args:
    R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due and answered_date, and optionally request_type and status.
    as_of: The day (a date, Timestamp, ISO text or YYYY-MM) as of which the status is derived.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns cus_key, request_no, request_type, received, due, answered_date (as of the day: null when answered later), status_as_of, days_to_due (due less the day; negative when overdue), and, when R has a status column, stored_status and status_agrees (the derived status against the snapshot), sorted by cus_key and request_no.

Raises:
    FrameError: R is not a frame or lacks a needed column; R has two rows for a customer and request number.
    FrameError: received, due or answered_date holds numbers or a value that is not a date; a row has no received or due date; a request is due before it was received.
    FrameError: as_of is a number, not a date, or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import open_requests
    >>> ctx = Context(stage="month12", role="analyst")
    >>> R = pd.DataFrame({
    ...     "cus_key": ["CUS-900001", "CUS-900001", "CUS-900002"], "request_no": [1, 2, 1],
    ...     "received": ["2031-03-01", "2031-03-10", "2031-04-20"], "due": ["2031-03-31", "2031-04-10", "2031-05-20"],
    ...     "answered_date": ["2031-03-20", None, None], "status": ["answered", "open", "open"]})
    >>> out = open_requests(R, "2031-04-15", context=ctx)
    >>> out[["cus_key", "request_no", "status_as_of", "days_to_due", "status_agrees"]].values.tolist()
    [['CUS-900001', 1, 'answered', -15, True], ['CUS-900001', 2, 'overdue', -5, False], ['CUS-900002', 1, 'not_received', 35, False]]

## Source columns

- `energy-esg.esg_data_request.cus_key`
- `energy-esg.esg_data_request.request_no`
- `energy-esg.esg_data_request.received`
- `energy-esg.esg_data_request.due`
- `energy-esg.esg_data_request.answered_date`
- `energy-esg.esg_data_request.status`
- `energy-esg.esg_data_request.request_type`
- `energy-esg.esg_data_request.opp_key`
- `energy-esg.esg_data_request.limit_kgco2e_per_m`
