# active_on

Module `halvaro.delivery.projects`. Import: `from halvaro.delivery import active_on`.

```python
active_on(project: pd.DataFrame, as_of: dt.date, *, context: halvaro.core.access.Context) -> list[Any]
```

Use this when you need the keys of the projects that are active on a date.

A project is active when it has started and has not ended before the date (status computed from start and actual_end, as in project_status_on).

Args:
    project: The projects.project frame; it needs prj_key, start and actual_end, one row per prj_key.
    as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A list of the prj_key values of the active projects, sorted.

Raises:
    FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a start has no date; start or actual_end holds a value that is not a date or has a time zone.
    PeriodError: as_of is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import active_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900002", "PRJ-900001", "PRJ-900003"], "start": ["2026-01-01", "2026-01-01", "2026-03-01"],
    ...                     "actual_end": [None, "2025-12-31", None]})
    >>> active_on(prj, "2026-02-01", context=ctx)
    ['PRJ-900002']

## Source columns

- `projects.project.prj_key`
- `projects.project.start`
- `projects.project.actual_end`
