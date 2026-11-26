# attendance

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import attendance`.

```python
attendance(meeting: pd.DataFrame, meeting_attendance: pd.DataFrame, *, employee: pd.DataFrame | None = None, contact: pd.DataFrame | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need one row per attendee of a meeting with the meeting date and project, the resolved person and whether the person was present.

Each row carries the meeting date and project, the resolved person (person_key: emp_key for an employee, cnt_key for an external), status, present (true only for status present: apologies and absences are not attendance) and role_in_meeting. With an employee frame (hr.employee) `leaver` is true when the person had left before the meeting date; with a contact frame (crm.contact) `inactive_contact` is true when the contact was inactive since a date before the meeting. A row whose attendee_type and key column disagree raises.

Args:
    meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and meeting_type.
    meeting_attendance: The projects.meeting_attendance frame; it needs mtg_key, attendee_type (employee or external), emp_key, cnt_key, status (present, apology or absent) and role_in_meeting.
    employee: Optional hr.employee frame with emp_key (one row per key) and leave_date; adds the leaver column.
    contact: Optional crm.contact frame with cnt_key (one row per key) and inactive_since; adds the inactive_contact column.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns mtg_key, prj_key, date, meeting_type, person_key, attendee_type, emp_key, cnt_key, status, present, role_in_meeting, then leaver and inactive_contact when the matching frame is given. Sorted by mtg_key and person_key.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; meeting, employee or contact has more than one row for a key; attendee_type or status has an unknown value (or a null status); an attendee does not have exactly one of emp_key and cnt_key matching attendee_type; a person appears twice in one meeting; an attendance row names a meeting that is not in meeting; a date column holds a time zone or a value that is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import attendance
    >>> ctx = Context(stage="month12", role="analyst")
    >>> meeting = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"]})
    >>> att = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "attendee_type": ["employee", "external"], "emp_key": ["EMP-900001", None],
    ...                     "cnt_key": [None, "CNT-900001"], "status": ["present", "apology"], "role_in_meeting": ["chair", "guest"]})
    >>> out = attendance(meeting, att, context=ctx)
    >>> out["person_key"].tolist()
    ['CNT-900001', 'EMP-900001']
    >>> out["present"].tolist()
    [False, True]

## Source columns

- `projects.meeting.mtg_key`
- `projects.meeting.prj_key`
- `projects.meeting.date`
- `projects.meeting.meeting_type`
- `projects.meeting_attendance.mtg_key`
- `projects.meeting_attendance.attendee_type`
- `projects.meeting_attendance.emp_key`
- `projects.meeting_attendance.cnt_key`
- `projects.meeting_attendance.status`
- `projects.meeting_attendance.role_in_meeting`
