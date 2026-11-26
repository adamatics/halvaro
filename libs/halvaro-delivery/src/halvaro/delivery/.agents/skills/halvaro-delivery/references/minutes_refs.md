# minutes_refs

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import minutes_refs`.

```python
minutes_refs(meeting: pd.DataFrame, *, context: halvaro.core.access.Context) -> MinutesRefs
```

Use this when you need the minutes path of each meeting and the share of meetings that have no minutes reference.

The share counts meetings with a null or empty minutes_ref; it is reported and not hidden.

Args:
    meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and minutes_ref.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A MinutesRefs result: `frame` with the columns mtg_key, prj_key, date, minutes_ref sorted by date and mtg_key, and `null_share`, the share of meetings with no reference (0.0 for an empty frame).

Raises:
    FrameError: meeting is not a DataFrame, has duplicate column names, lacks a needed column or has more than one row for a mtg_key; date holds a time zone or a value that is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import minutes_refs
    >>> ctx = Context(stage="month12", role="analyst")
    >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900002"], "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-10", "2026-03-03"],
    ...                     "minutes_ref": ["minutes/a.pdf", None]})
    >>> res = minutes_refs(mtg, context=ctx)
    >>> res.frame["mtg_key"].tolist(), res.null_share
    (['MTG-900002', 'MTG-900001'], 0.5)

## Source columns

- `projects.meeting.mtg_key`
- `projects.meeting.prj_key`
- `projects.meeting.date`
- `projects.meeting.minutes_ref`
