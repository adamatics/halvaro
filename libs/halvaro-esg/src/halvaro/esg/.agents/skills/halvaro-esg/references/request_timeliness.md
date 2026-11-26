# request_timeliness

Module `halvaro.esg.data_requests`. Import: `from halvaro.esg import request_timeliness`.

```python
request_timeliness(R: pd.DataFrame, *, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need how many days customer requests take to be answered and how many are answered by the due date, per request type.

Days from receipt to answer and whether the answer came by the due date, by request type. Requests not answered are counted in n and not in the shares. With `as_of`, answers after that day count as not answered.

Args:
    R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due, answered_date and request_type.
    as_of: A day (date, Timestamp or ISO text) after which answers do not count and requests received after it are left out; None to use every answer.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns request_type, n, n_answered, mean_days_to_answer, median_days_to_answer (rounded to 2 decimals), n_on_time and share_on_time (n_on_time over n_answered, rounded to 4 decimals; null when none is answered), sorted by request_type.

Raises:
    FrameError: R is not a frame or lacks a needed column; R has two rows for a customer and request number; a date column holds numbers, a value that is not a date, no received or due date, or a due date before the received date.
    FrameError: a request has no request_type; a request was answered before it was received.
    FrameError: as_of is a number, not a date, or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import request_timeliness
    >>> ctx = Context(stage="month12", role="analyst")
    >>> R = pd.DataFrame({
    ...     "cus_key": ["CUS-900001", "CUS-900001", "CUS-900002"], "request_no": [1, 2, 1],
    ...     "received": ["2031-03-01", "2031-03-10", "2031-04-20"], "due": ["2031-03-31", "2031-04-10", "2031-05-20"],
    ...     "answered_date": ["2031-03-20", "2031-04-15", None],
    ...     "request_type": ["questionnaire", "questionnaire", "tender_requirement"]})
    >>> out = request_timeliness(R, context=ctx)
    >>> out[["request_type", "n", "n_answered", "n_on_time", "share_on_time"]].values.tolist()
    [['questionnaire', 2, 2, 1, 0.5], ['tender_requirement', 1, 0, 0, nan]]

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
