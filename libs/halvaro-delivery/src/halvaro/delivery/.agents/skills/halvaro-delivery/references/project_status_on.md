# project_status_on

Module `halvaro.delivery.projects`. Import: `from halvaro.delivery import project_status_on`.

```python
project_status_on(project: pd.DataFrame, as_of: dt.date, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the status of each project on a date (planned, active or completed) worked out from its dates.

The status is computed from the dates, not read from the status column: planned if start is after the date, completed if actual_end is set and before it, else active. Not the leave status of halvaro.hr. Results keep the index of the input frame.

Args:
    project: The projects.project frame; it needs prj_key, start and actual_end, one row per prj_key.
    as_of: The day of the status (a date, a Timestamp or an ISO text); a time of day is dropped.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with prj_key, as_of and status (planned, active, completed), one row per project, in the index of the input.

Raises:
    FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a start has no date; start or actual_end holds a value that is not a date or has a time zone.
    PeriodError: as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import project_status_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "start": ["2026-01-01", "2026-03-01", "2025-01-01"],
    ...                     "actual_end": [None, None, "2025-12-31"]})
    >>> project_status_on(prj, "2026-02-01", context=ctx)["status"].tolist()
    ['active', 'planned', 'completed']

## Source columns

- `projects.project.prj_key`
- `projects.project.start`
- `projects.project.actual_end`
