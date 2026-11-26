# cause_shares

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import cause_shares`.

```python
cause_shares(delay_event: pd.DataFrame, project: pd.DataFrame, *, projects: Sequence[str] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the delay days by cause code and responsible party, with their shares, for all events and for the events linked to a meeting.

Two views: all_events (every delay event of the projects) and full_linked (full projects, events linked to a meeting through mtg_key). Columns: view, cause_code, responsible_party, events, days, share (of the days of the view) and cause_share (the days of the whole cause_code over the days of the view). `projects` limits the set (a comparable set).

Args:
    delay_event: The projects.delay_event frame; it needs prj_key, cause_code, responsible_party, days and mtg_key.
    project: The projects.project frame, one row per prj_key; it needs prj_key and data_depth (full or not).
    projects: Optional prj_key values (a key as text or a list) that limit the set.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns view, cause_code, responsible_party, events, days, share and cause_share, sorted by view and days (high first), then cause_code and responsible_party.

Raises:
    FrameError: delay_event or project is not a DataFrame, lacks a needed column or (project) repeats a prj_key; days is not numeric or has nulls; a row has a null prj_key, cause_code or responsible_party; a project of the delay events is not in the project frame.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import cause_shares
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ev = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "cause_code": ["ground_conditions", "ground_conditions", "weather"],
    ...                    "responsible_party": ["client", "client", "nature"], "days": [10, 20, 10], "mtg_key": ["MTG-900001", None, "MTG-900002"]})
    >>> project = pd.DataFrame({"prj_key": ["PRJ-900001"], "data_depth": ["full"]})
    >>> r = cause_shares(ev, project, context=ctx)
    >>> r[r["view"] == "all_events"]["days"].tolist()
    [30, 10]
    >>> [round(x, 2) for x in r[r["view"] == "all_events"]["share"]]
    [0.75, 0.25]

## Source columns

- `projects.delay_event.prj_key`
- `projects.delay_event.cause_code`
- `projects.delay_event.responsible_party`
- `projects.delay_event.days`
- `projects.delay_event.mtg_key`
- `projects.project.prj_key`
- `projects.project.data_depth`
