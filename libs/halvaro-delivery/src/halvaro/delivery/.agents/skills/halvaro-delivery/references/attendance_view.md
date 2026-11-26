# attendance_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import attendance_view`.

```python
attendance_view(attendance: pd.DataFrame, *, by: str = 'month', as_of: DateLike | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need meeting attendance as heatmap data: the absence rate by month or year and meeting type.

The heatmap data comes from `attendance` (one row per attendee: date, present and optionally meeting_type): period (month or year), meeting_type, n_rows, n_present, absence_rate from the summed rows (1 less present over rows), n_meetings. A frame without meeting_type uses 'all', a null meeting_type is shown as 'unknown' (rows are never dropped); a null `present` raises FrameError. x is the period, y the meeting type and `value` the absence rate.

Args:
    attendance: One row per attendee; it needs mtg_key, date and present (no nulls) and may have meeting_type.
    by: The period, 'month' or 'year' (default 'month').
    as_of: Optional as-of date, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'heatmap': `frame` (period, meeting_type, n_rows, n_present, n_meetings, absence_rate rounded to 4 places), x period, y meeting_type, value absence_rate, n the number of attendance rows.

Raises:
    FrameError: attendance is not a DataFrame or lacks a needed column; by is not month or year; attendance.present has nulls.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import attendance_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> att = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001", "MTG-900002"], "date": ["2026-01-05", "2026-01-05", "2026-02-02"], "present": [True, False, True]})
    >>> spec = attendance_view(att, context=ctx)
    >>> spec.frame["period"].tolist()
    ['2026-01', '2026-02']
    >>> spec.frame["absence_rate"].tolist()
    [0.5, 0.0]
    >>> spec.frame["meeting_type"].tolist()
    ['all', 'all']

## Source columns

- `projects.meeting_attendance.mtg_key`
- `projects.meeting.date`
