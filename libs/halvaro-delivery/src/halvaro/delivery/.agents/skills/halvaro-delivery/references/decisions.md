# decisions

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import decisions`.

```python
decisions(decision: pd.DataFrame, meeting: pd.DataFrame, delay_event: pd.DataFrame | None = None, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the decisions of the meetings with their project and date, impact in cost and days, linked delay cause and change order.

Cost and day impact are in the decision currency; the linked delay event cause comes from delay_seq on the same project, the change order from co_no, and write_down is true for decision_type write_down. Columns of the decision plus prj_key, date, meeting_type, write_down and, with a delay_event frame, delay_cause.

Args:
    decision: The projects.decision frame, one row per mtg_key and seq; it needs mtg_key, seq, decision_type, impact_cost, impact_days, currency, delay_seq and co_no, and must not already have prj_key, date, meeting_type, write_down or delay_cause.
    meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and meeting_type.
    delay_event: Optional projects.delay_event frame, one row per prj_key and seq; it needs prj_key, seq and cause_code and adds the delay_cause column.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns of decision plus prj_key, date, meeting_type, write_down and, with delay_event, delay_cause. Sorted by date, mtg_key, seq.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; decision, meeting or delay_event has more than one row for a key; decision already has one of the added columns; delay_seq does not hold whole numbers; a decision names a meeting that is not in meeting; the meeting date holds a time zone or a value that is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import decisions
    >>> ctx = Context(stage="month12", role="analyst")
    >>> dec = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "seq": [1, 2], "decision_type": ["write_down", "approve"], "impact_cost": [100.0, 0.0],
    ...                     "impact_days": [0, 5], "currency": ["EUR"] * 2, "delay_seq": [None, 1], "co_no": [None, None]})
    >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"]})
    >>> decisions(dec, mtg, context=ctx)["write_down"].tolist()
    [True, False]

## Source columns

- `projects.decision.mtg_key`
- `projects.decision.seq`
- `projects.decision.decision_type`
- `projects.decision.impact_cost`
- `projects.decision.impact_days`
- `projects.decision.currency`
- `projects.decision.delay_seq`
- `projects.decision.co_no`
- `projects.meeting.prj_key`
- `projects.meeting.date`
- `projects.delay_event.cause_code`
