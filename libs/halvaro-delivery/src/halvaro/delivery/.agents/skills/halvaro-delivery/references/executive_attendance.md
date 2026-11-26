# executive_attendance

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import executive_attendance`.

```python
executive_attendance(attendance_frame: pd.DataFrame, executives: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the attendees who were present at a meeting while holding one of the named executive roles on the meeting date.

`executives` is the hr executives_on frame with an as_of column, one call per meeting date, concatenated (emp_key, role_name, as_of): a holder who changed role before the meeting is not counted for the meeting date. A present employee whose meeting date has no as_of value in the frame raises (the executive set of that date was never loaded; an attendee who is simply not an executive is fine). A date on which nobody holds an executive role (before the HR history starts, say) is declared by one row with an empty emp_key and role_name and that as_of.

Args:
    attendance_frame: The output of attendance; it needs mtg_key, prj_key, date, emp_key and status.
    executives: The hr executives_on frames with an as_of column, concatenated; it needs emp_key, role_name and as_of.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns mtg_key, prj_key, date, emp_key, role_name, sorted by date, mtg_key, emp_key.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; a date column holds a time zone or a value that is not a date; an employee appears twice in one meeting; status has an unknown value; a present employee's meeting date has no as_of row in executives; emp_key differs in type between the two frames.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import executive_attendance
    >>> ctx = Context(stage="month12", role="analyst")
    >>> att = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-10"] * 2,
    ...                     "emp_key": ["EMP-900001", "EMP-900002"], "status": ["present", "present"]})
    >>> ex = pd.DataFrame({"emp_key": ["EMP-900001"], "role_name": ["director"], "as_of": ["2026-03-10"]})
    >>> executive_attendance(att, ex, context=ctx)[["emp_key", "role_name"]].to_dict("records")
    [{'emp_key': 'EMP-900001', 'role_name': 'director'}]

## Source columns

- `projects.meeting_attendance.status`
- `projects.meeting_attendance.emp_key`
- `projects.meeting.date`
