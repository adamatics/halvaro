# first_record

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import first_record`.

```python
first_record(site_diary: pd.DataFrame, prj_key: str, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the first site diary row of a project that records a delay, the first record of the first delay event.

The row is the one with delay_seq 1 (PROPOSED rule, policy.delivery.first_record_rule is needed); the earliest diary_date wins, and the full time stamp decides when several rows share a day. The columns are prj_key, diary_date, notes, author_emp_key, delay_seq. An empty frame (no columns lost) comes back when the project has no such row.

Args:
    site_diary: The projects.site_diary frame; it needs prj_key, diary_date, notes, author_emp_key and delay_seq.
    prj_key: The key of the project whose first record is wanted.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame of at most one row with the columns prj_key, diary_date, notes, author_emp_key, delay_seq.

Raises:
    FrameError: site_diary is not a DataFrame, has duplicate column names or lacks a needed column; delay_seq is not numeric; diary_date holds numbers, a time zone or a value that is not a date; a diary row of the project with delay_seq 1 has no diary_date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import first_record
    >>> ctx = Context(stage="month12", role="analyst")
    >>> diary = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "diary_date": ["2026-03-05", "2026-03-02", "2026-03-09"],
    ...                       "notes": ["b", "a", "c"], "author_emp_key": ["EMP-900001"] * 3, "delay_seq": [1, 1, 2]})
    >>> first_record(diary, "PRJ-900001", context=ctx).to_dict("records")
    [{'prj_key': 'PRJ-900001', 'diary_date': '2026-03-02', 'notes': 'a', 'author_emp_key': 'EMP-900001', 'delay_seq': 1}]
    >>> first_record(diary, "PRJ-900002", context=ctx).shape
    (0, 5)

## Source columns

- `projects.site_diary.prj_key`
- `projects.site_diary.diary_date`
- `projects.site_diary.notes`
- `projects.site_diary.author_emp_key`
- `projects.site_diary.delay_seq`
