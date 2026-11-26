# schedule_overrun

Module `halvaro.delivery.schedule`. Import: `from halvaro.delivery import schedule_overrun`.

```python
schedule_overrun(project: pd.DataFrame, as_of: dt.date, *, include_forecast: bool = True, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the schedule overrun of each project on a date, in days and as a fraction of the planned days.

Overrun is (end minus planned_end) in days over (planned_end minus start plus 1) planned days, the definition of the generator test test_cell_calibration (PROPOSED, policy.delivery.overrun_definition is needed).
End is actual_end for a project completed on the date (basis actual). With include_forecast an active project with a forecast_end is listed with basis forecast and that end. The stored forecast_end is the one on the release date
(fact world.now): for an as_of before it the forecast of an active project is not the forecast that stood on that date, so its basis is "current forecast" (same end, a later view than the date); at or after the release date
the basis is "forecast". Planned projects, and active ones without a forecast, are not listed. Overrun is negative for a project that ended early.

Args:
    project: The projects.project frame, one row per prj_key; it needs prj_key, start, planned_end, actual_end and forecast_end.
    as_of: The date on which the status of each project is taken (a date, a Timestamp or an ISO text).
    include_forecast: True lists active projects with a forecast_end on the basis of that forecast; False lists only completed projects.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns prj_key, as_of, basis (actual, forecast or current forecast), planned_days, overrun_days and overrun (a fraction, negative: early), one row per listed project, in the order of the input.

Raises:
    FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a project has no start date; a date column holds an unreadable value or a time zone; a completed project has no planned_end or one before its start.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import schedule_overrun
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"],
    ...                     "start": ["2029-01-01", "2030-01-01"], "planned_end": ["2029-01-10", "2030-01-10"],
    ...                     "actual_end": ["2029-01-15", None], "forecast_end": [None, "2030-01-12"]})
    >>> out = schedule_overrun(prj, "2030-01-05", context=ctx)
    >>> out["basis"].tolist()
    ['actual', 'forecast']
    >>> out["overrun_days"].tolist()
    [5.0, 2.0]
    >>> out["overrun"].round(2).tolist()
    [0.5, 0.2]

## Source columns

- `projects.project.prj_key`
- `projects.project.start`
- `projects.project.planned_end`
- `projects.project.actual_end`
- `projects.project.forecast_end`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
