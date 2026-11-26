# timeline

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import timeline`.

```python
timeline(prj_key: str, *, site_diary: pd.DataFrame, risk: pd.DataFrame, meeting: pd.DataFrame, decision: pd.DataFrame, delay_event: pd.DataFrame, plan_version: pd.DataFrame, start: DateLike | None = None, end: DateLike | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the dated events of one project in one ordered frame, such as meetings, decisions, delay events, risks and plan versions.

Columns: date, kind (delay_event, risk, meeting, decision, plan_version, first_diary_delay), source table, source key and a short text. Diary rows are not listed one by one (they are daily): only the first row of each delay_seq appears, as first_diary_delay. `start` and `end` (inclusive) limit the dates. Sorted by date, then by kind in the order meeting, decision, delay_event, first_diary_delay, risk, plan_version (a decision follows its meeting), then as listed per kind: delay events by seq, risks by risk_no, decisions by meeting and seq, plan versions by number, first diary rows by date and then delay_seq; meetings keep the order of the meeting frame.

Args:
    prj_key: The key of the project.
    site_diary: The projects.site_diary frame; it needs prj_key, diary_date, delay_seq and notes.
    risk: The projects.risk frame; it needs prj_key, risk_no, raised, title and status.
    meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date, meeting_type and title.
    decision: The projects.decision frame; it needs mtg_key, seq, text and decision_type.
    delay_event: The projects.delay_event frame; it needs prj_key, seq, start, days and cause_code.
    plan_version: The projects.plan_version frame; it needs prj_key, plan_version, created and reason.
    start: Optional first date to keep (inclusive).
    end: Optional last date to keep (inclusive).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns date, kind, source, source_key, text, ordered as described above.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; seq or days of delay_event, risk_no of risk, seq of decision or plan_version of plan_version is not whole numbers or has nulls; meeting has more than one row for a meeting; a date column holds a time zone or a value that is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import timeline
    >>> ctx = Context(stage="month12", role="analyst")
    >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"], "title": ["Kick-off"]})
    >>> dec = pd.DataFrame({"mtg_key": ["MTG-900001"], "seq": [1], "text": ["Go"], "decision_type": ["approve"]})
    >>> diary = pd.DataFrame({"prj_key": [], "diary_date": [], "delay_seq": [], "notes": []})
    >>> risk = pd.DataFrame({"prj_key": [], "risk_no": [], "raised": [], "title": [], "status": []})
    >>> dev = pd.DataFrame({"prj_key": [], "seq": [], "start": [], "days": [], "cause_code": []})
    >>> pv = pd.DataFrame({"prj_key": [], "plan_version": [], "created": [], "reason": []})
    >>> out = timeline("PRJ-900001", site_diary=diary, risk=risk, meeting=mtg, decision=dec, delay_event=dev, plan_version=pv, context=ctx)
    >>> out[["kind", "source_key"]].to_dict("records")
    [{'kind': 'meeting', 'source_key': 'MTG-900001'}, {'kind': 'decision', 'source_key': 'MTG-900001/1'}]

## Source columns

- `projects.site_diary.prj_key`
- `projects.risk.prj_key`
- `projects.meeting.prj_key`
- `projects.decision.mtg_key`
- `projects.delay_event.prj_key`
- `projects.plan_version.prj_key`
