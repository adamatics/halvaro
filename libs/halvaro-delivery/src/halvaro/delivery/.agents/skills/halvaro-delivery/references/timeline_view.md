# timeline_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import timeline_view`.

```python
timeline_view(timeline: pd.DataFrame, attendance: pd.DataFrame | None = None, write_down: dict[str, Any] | None = None, *, as_of: DateLike | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need the project timeline as chart lanes: meetings, decisions, delays, risks and plan versions in date order, with optional attendance and a write-down marker.

The result is the project timeline as lanes, in the order of `timeline` (it is sorted: date, then meeting before its decisions). The frame has the columns date, lane (meeting, decision, delay_event, first_diary_delay, risk, plan_version), label, source and source_key. With `attendance` (one row per attendee, columns mtg_key, present) meetings get n_present and n_invited; a null `present` raises. With `write_down` ({'date', 'amount', 'currency'} from finance) one more row on the lane 'write_down' follows the last row on or before its date, the amount kept in its currency and written without separators.

Args:
    timeline: The project timeline frame (sorted by date); it needs date, kind, source, source_key and text.
    attendance: Optional frame with one row per attendee, with mtg_key and present (no nulls); meetings get n_invited and n_present from it.
    write_down: Optional dict with date, amount and currency from finance; it adds one row on the lane 'write_down'.
    as_of: Optional as-of date, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'timeline': `frame` (date, lane, label, source, source_key and, with attendance, n_invited and n_present), x date, y and group lane, caption with the as-of date, the label 'synthetic data' and n, the number of timeline rows.

Raises:
    FrameError: timeline or attendance is not a DataFrame or lacks a needed column; attendance.present has nulls; write_down lacks date, amount or currency.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import timeline_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> tl = pd.DataFrame({"date": ["2026-01-05", "2026-01-05", "2026-01-09"], "kind": ["meeting", "decision", "delay_event"],
    ...                    "source": ["meeting", "decision", "delay_event"], "source_key": ["MTG-900001", "DEC-900001", "DLY-900001"], "text": ["Kickoff", "Go", "Late"]})
    >>> att = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001"], "present": [True, False]})
    >>> spec = timeline_view(tl, att, {"date": "2026-01-06", "amount": 1200.0, "currency": "EUR"}, context=ctx)
    >>> spec.frame["lane"].tolist()
    ['meeting', 'decision', 'write_down', 'delay_event']
    >>> int(spec.frame["n_present"].iloc[0]), int(spec.frame["n_invited"].iloc[0])
    (1, 2)
    >>> spec.n
    3

## Source columns

- `projects.meeting.mtg_key`
- `projects.decision.mtg_key`
- `projects.delay_event.prj_key`
- `projects.risk.prj_key`
