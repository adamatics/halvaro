# milestone_slippage

Module `halvaro.delivery.schedule`. Import: `from halvaro.delivery import milestone_slippage`.

```python
milestone_slippage(milestone: pd.DataFrame, as_of: dt.date, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the state of each milestone on a date: done with its slip, or open with its overdue days.

A milestone is done when actual_date is on or before the date, then slip_days is actual_date minus planned_date. Otherwise it is open: overdue_days is the date minus planned_date when that is positive (state open_overdue, else open).
The source columns are kept (actual_date is null if after the date).

Args:
    milestone: The projects.milestone frame, one row per prj_key and milestone_no; it needs prj_key, milestone_no, planned_date and actual_date.
    as_of: The date on which the state of each milestone is taken (a date, a Timestamp or an ISO text).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame sorted by prj_key and milestone_no with the source columns (dates as calendar days) and the added columns state (done, open_overdue or open), slip_days (null unless done) and overdue_days (null unless open and overdue).

Raises:
    FrameError: milestone is not a DataFrame, has duplicate column names or lacks a needed column; prj_key or milestone_no has a null; a prj_key and milestone_no pair is repeated; a row has no planned_date; a date column holds an unreadable value or a time zone.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import milestone_slippage
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ms = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "milestone_no": [1, 2, 3],
    ...                    "planned_date": ["2029-03-01", "2029-04-01", "2029-12-01"],
    ...                    "actual_date": ["2029-03-05", None, None]})
    >>> out = milestone_slippage(ms, "2029-05-01", context=ctx)
    >>> out["state"].tolist()
    ['done', 'open_overdue', 'open']
    >>> out["slip_days"].tolist()[0], out["overdue_days"].tolist()[1]
    (4.0, 30.0)

## Source columns

- `projects.milestone.prj_key`
- `projects.milestone.milestone_no`
- `projects.milestone.planned_date`
- `projects.milestone.actual_date`
