# activity_plan_vs_actual

Module `halvaro.delivery.schedule`. Import: `from halvaro.delivery import activity_plan_vs_actual`.

```python
activity_plan_vs_actual(plan_activity: pd.DataFrame, actual_activity: pd.DataFrame, as_of: dt.date | None = None, *, plan_version: pd.DataFrame | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need each activity's baseline plan, latest plan and actual dates side by side, with the start and end slip.

Per activity: baseline start and end (lowest plan_version of the activity), latest start and end (highest version, name, predecessor and critical from it), actual_start, actual_end and percent_complete,
plus start_slip_days (actual_start minus baseline start), end_slip_days (latest end minus baseline end) and plan_versions. With as_of, actual dates after it are null, and so is the percent of an activity that had not started on that date.
The stored percent is the one on the release date (fact world.now) and the final one for a finished activity: for an as_of before the release date the percent of a started, unfinished activity is null (the percent on that date is not in the data);
at or after it the stored percent of a started activity is kept. LEAK: without plan_version the plan versions are not filtered by date (the plan frame has no created date), so for a past as_of the latest version, end_slip_days and plan_versions
include re-plans that did not exist yet. Pass plan_version (the projects.plan_version frame: prj_key, plan_version, created) with as_of to drop the activity rows of versions created after the date (a version with no created date, or absent from
that frame, is kept); an activity with no version left on the date is not listed. plan_version without as_of filters nothing. Activities without actual rows stay, with nulls.

Args:
    plan_activity: The projects.plan_activity frame, one row per prj_key, plan_version and activity_code; it needs prj_key, plan_version, activity_code, name, start, end, predecessor and critical.
    actual_activity: The projects.actual_activity frame, one row per prj_key and activity_code; it needs prj_key, activity_code, actual_start, actual_end and percent_complete.
    as_of: A date; actuals after it are treated as not yet known. None uses the stored actuals as they are.
    plan_version: The projects.plan_version frame (prj_key, plan_version, created), or None; with as_of it drops plan versions created after the date.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame sorted by prj_key and activity_code with name, baseline_start, baseline_end, latest_start, latest_end, predecessor, critical, plan_versions, actual_start, actual_end, percent_complete, start_slip_days and end_slip_days (days as floats).

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; a key column has a null or a key is repeated (prj_key, plan_version and activity_code of the plan; prj_key and activity_code of the actuals; prj_key and plan_version of plan_version); a date column holds an unreadable value or a time zone; an actual activity has no plan activity.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import activity_plan_vs_actual
    >>> ctx = Context(stage="month12", role="analyst")
    >>> plan = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "plan_version": [1, 2], "activity_code": ["A10", "A10"], "name": ["Dig", "Dig"],
    ...                      "start": ["2029-01-01", "2029-01-05"], "end": ["2029-01-10", "2029-01-20"], "predecessor": [None, None], "critical": [True, True]})
    >>> act = pd.DataFrame({"prj_key": ["PRJ-900001"], "activity_code": ["A10"], "actual_start": ["2029-01-06"],
    ...                     "actual_end": ["2029-01-22"], "percent_complete": [100.0]})
    >>> out = activity_plan_vs_actual(plan, act, context=ctx)
    >>> out[["plan_versions", "start_slip_days", "end_slip_days"]].to_dict("records")
    [{'plan_versions': 2, 'start_slip_days': 5.0, 'end_slip_days': 10.0}]

## Source columns

- `projects.plan_activity.prj_key`
- `projects.plan_activity.plan_version`
- `projects.plan_activity.activity_code`
- `projects.plan_activity.name`
- `projects.plan_activity.start`
- `projects.plan_activity.end`
- `projects.plan_activity.predecessor`
- `projects.plan_activity.critical`
- `projects.actual_activity.prj_key`
- `projects.actual_activity.activity_code`
- `projects.actual_activity.actual_start`
- `projects.actual_activity.actual_end`
- `projects.actual_activity.percent_complete`
- `projects.plan_version.prj_key`
- `projects.plan_version.plan_version`
- `projects.plan_version.created`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
