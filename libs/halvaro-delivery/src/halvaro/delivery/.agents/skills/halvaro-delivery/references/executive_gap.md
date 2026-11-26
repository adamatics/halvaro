# executive_gap

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import executive_gap`.

```python
executive_gap(first: pd.DataFrame, exec_attendance: pd.DataFrame, prj_key: str, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the days from the first record of a project to the first meeting with a present executive on or after it.

Days from the first record to the first meeting of the project with a present executive on or after it. All columns but the first two are null when no executive attended (a gap that has not closed). first_executive_emp is the lowest emp_key (and its role) among the executives at that first meeting (earliest date, then lowest mtg_key); it is not picked by seniority, so the CFO of the narrative is not chosen by this function. executives_present lists every executive present at that meeting, emp_keys sorted and comma separated.

Args:
    first: The output of first_record; it needs prj_key and diary_date, with exactly one row for the project.
    exec_attendance: The output of executive_attendance; it needs mtg_key, prj_key, date, emp_key and role_name.
    prj_key: The key of the project to measure.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A one row frame with the columns prj_key, first_record, first_executive_meeting, first_executive_emp, first_executive_role, gap_days, executives_present.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the project has no first record or more than one; its first record has no diary_date; a date column holds a time zone or a value that is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import executive_gap
    >>> ctx = Context(stage="month12", role="analyst")
    >>> first = pd.DataFrame({"prj_key": ["PRJ-900001"], "diary_date": ["2026-03-01"]})
    >>> ex = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001"], "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-11"] * 2,
    ...                    "emp_key": ["EMP-900002", "EMP-900001"], "role_name": ["cfo", "director"]})
    >>> row = executive_gap(first, ex, "PRJ-900001", context=ctx).iloc[0]
    >>> float(row["gap_days"]), row["first_executive_emp"], row["executives_present"]
    (10.0, 'EMP-900001', 'EMP-900001,EMP-900002')

## Source columns

- `projects.site_diary.diary_date`
- `projects.meeting.date`
