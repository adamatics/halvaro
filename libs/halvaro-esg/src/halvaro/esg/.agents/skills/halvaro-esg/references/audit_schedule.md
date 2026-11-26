# audit_schedule

Module `halvaro.esg.audit_targets`. Import: `from halvaro.esg import audit_schedule`.

```python
audit_schedule(A: pd.DataFrame, as_of: DateLike, *, cycle_years: int = 4, completed: str = 'completed', ignored: tuple[str, ...] = ('cancelled',), context: halvaro.core.access.Context) -> Provenance
```

Use this when you need, per site, the last completed energy audit, the next due date and whether the site is overdue on a given day.

Per site: the last completed audit on or before the day, the next due date, whether an audit is open and whether the site is overdue. The due date of a completed row is ignored. A site with no completed audit has a null last date and is overdue only through an open row. The cycle (4 years, VERIFY) is a keyword; the legal duty is not stated, so the result has the status VERIFY and `overdue` rests on the cycle. Statuses are compared without case and spaces. Rows with a status in `ignored` (cancelled) are left out; any other status than `completed` is an open audit and needs a due date.

Args:
    A: The energy-esg.energy_audit table with the columns site_key, audit_date, due_date and status (year, when present, is not used).
    as_of: The day of the schedule (a date, a Timestamp or ISO text); audits after it do not count as done.
    cycle_years: The audit cycle in whole years, from 1 to 100 (default 4, VERIFY).
    completed: The status text of a completed audit (default "completed").
    ignored: The statuses that are left out (default ("cancelled",)); a tuple, not a single text.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns site_key, last_audit_date, open_audit (a row that is not completed), open_due_date, next_due (the open row's due date when there is one, else the last audit plus `cycle_years`), days_to_due (negative when past), overdue and cycle_years, one row per site sorted by site_key.

Raises:
    FrameError: A lacks site_key, audit_date, due_date or status, or a row has no status or no site_key.
    FrameError: cycle_years is not a whole number from 1 to 100, `ignored` is a single text, or as_of is not a date without a time zone.
    FrameError: audit_date or due_date holds numbers, a value that is not a date, or a time zone.
    FrameError: a completed audit has no audit date, an open audit has no due date, or a site has more than one open audit.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import audit_schedule
    >>> ctx = Context(stage="month12", role="analyst")
    >>> A = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900002"], "audit_date": ["2021-05-10", None],
    ...                   "due_date": [None, "2026-02-01"], "status": ["completed", "planned"]})
    >>> r = audit_schedule(A, "2026-03-01", context=ctx)
    >>> r.value["site_key"].tolist()
    ['SIT-900001', 'SIT-900002']
    >>> r.value["next_due"].dt.strftime("%Y-%m-%d").tolist()
    ['2025-05-10', '2026-02-01']
    >>> r.value["overdue"].tolist()
    [True, True]

## Source columns

- `energy-esg.energy_audit.site_key`
- `energy-esg.energy_audit.year`
- `energy-esg.energy_audit.audit_date`
- `energy-esg.energy_audit.due_date`
- `energy-esg.energy_audit.status`
