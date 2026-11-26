# delay_days

Module `halvaro.delivery.schedule`. Import: `from halvaro.delivery import delay_days`.

```python
delay_days(delay_event: pd.DataFrame, project: pd.DataFrame | None = None, *, context: halvaro.core.access.Context) -> DelayDays
```

Use this when you need the delay event days of each project by cause and responsible party, and how they tie to the date difference between actual and planned end.

Returns delay event days per project, cause_code and responsible_party (by_cause), and per project the total event days next to the date difference actual_end minus planned_end (tie).
The tie compares the two for completed projects that have at least one event (the generator test inner joins events to projects); other projects are listed with diff and ties false or null, never dropped.
Without a project frame the tie has event_days only. The project frame may be a subset (for example one cell): events of projects not in it are left out of both results and counted in attrs['events_outside_projects'] (0 without a frame);
a frame sharing no project with the events is refused (the wrong frame). Event rows sharing prj_key and seq (when seq is loaded) and days of zero or less are refused (FrameError); they would be summed silently.

Args:
    delay_event: The projects.delay_event frame; it needs prj_key, cause_code, responsible_party and days (whole days above zero, no nulls), and may have seq.
    project: The projects.project frame with prj_key, planned_end and actual_end, or None for a tie of event days only. It may be a subset of the projects.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DelayDays tuple. by_cause has prj_key, cause_code, responsible_party, events and days, sorted by those keys. tie has prj_key, event_days and events (sorted by prj_key); with a project frame it also has date_diff, diff (event_days minus date_diff) and ties (a nullable boolean, null where date_diff is null) and holds every project of the frame.
    Both frames carry attrs['events_outside_projects'].

Raises:
    FrameError: delay_event is not a DataFrame, has duplicate column names or lacks a needed column; days is not numeric, has nulls, has a fraction or is zero or negative; prj_key, cause_code or responsible_party has a null; prj_key and seq are repeated; project lacks a needed column or has a null or repeated prj_key; no project of the events is in the project frame; a date column of project is unreadable.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import delay_days
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ev = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "cause_code": ["C-A", "C-B"],
    ...                    "responsible_party": ["P-1", "P-2"], "days": [3, 2]})
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "planned_end": ["2029-01-10"], "actual_end": ["2029-01-15"]})
    >>> res = delay_days(ev, prj, context=ctx)
    >>> res.by_cause["days"].tolist()
    [3, 2]
    >>> res.tie[["event_days", "date_diff", "ties"]].to_dict("records")
    [{'event_days': 5, 'date_diff': 5.0, 'ties': True}]

## Source columns

- `projects.delay_event.prj_key`
- `projects.delay_event.cause_code`
- `projects.delay_event.responsible_party`
- `projects.delay_event.days`
- `projects.delay_event.seq`
- `projects.project.prj_key`
- `projects.project.planned_end`
- `projects.project.actual_end`
