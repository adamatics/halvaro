# gantt_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import gantt_view`.

```python
gantt_view(plan_vs_actual: pd.DataFrame, *, as_of: DateLike | None = None, legacy: int | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need baseline, latest plan and actual bars of project activities for a Gantt chart.

The bars come from the activities of `activity_plan_vs_actual`: a long frame (activity key columns prj_key, activity_code and name where present), series (baseline, latest, actual), start, end, in_progress and critical. A bar needs both dates, except an activity that has started and not finished: with `as_of` its actual bar runs to that day and in_progress is true; without it the actual bar is left out (the caption says so). Sorted by the baseline start, then the key and series.

Args:
    plan_vs_actual: The output of activity_plan_vs_actual; it needs baseline_start, baseline_end, latest_start, latest_end, actual_start and actual_end, and at least one activity key column (prj_key, activity_code, act_no or name); a critical column is carried when present.
    as_of: Optional day; an unfinished actual bar runs to it and an actual bar that starts after it is left out.
    legacy: Optional number of legacy projects, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'gantt': `frame` (the key columns, in_progress, critical when present, series, start, end; sorted by baseline start, key, series), x start, y the last key column, group series, n the number of activities.

Raises:
    FrameError: plan_vs_actual is not a DataFrame or lacks a needed column; it has no activity key column; it has more than one row for an activity key; a bar ends before it starts.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import gantt_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> pva = pd.DataFrame({"prj_key": ["PRJ-900001"], "activity_code": ["A10"],
    ...                     "baseline_start": ["2026-01-01"], "baseline_end": ["2026-01-10"], "latest_start": ["2026-01-02"], "latest_end": ["2026-01-12"],
    ...                     "actual_start": ["2026-01-02"], "actual_end": [None]})
    >>> spec = gantt_view(pva, as_of="2026-01-20", context=ctx)
    >>> spec.frame["series"].tolist()
    ['actual', 'baseline', 'latest']
    >>> spec.frame["in_progress"].tolist()
    [True, False, False]
    >>> str(spec.frame["end"].iloc[0].date())
    '2026-01-20'

## Source columns

- `projects.plan_activity.prj_key`
- `projects.actual_activity.prj_key`
