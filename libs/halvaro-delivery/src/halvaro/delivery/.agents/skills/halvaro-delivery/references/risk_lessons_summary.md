# risk_lessons_summary

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import risk_lessons_summary`.

```python
risk_lessons_summary(risk: pd.DataFrame, lesson_learned: pd.DataFrame, delay_event: pd.DataFrame, *, projects: Sequence[str] | None = None, context: halvaro.core.access.Context) -> RiskLessons
```

Use this when you need the most frequent risk causes and lesson categories of a set of projects and whether occurred risks and lessons match the cause of their delay event.

The top cause codes of risks and the lesson categories of a set (counts, high first), and the occurred risks (status occurred) matched to their delay event by prj_key and delay_seq. Lessons count only when linked to a delay event (delay_seq set); `lessons` matches each of them to the cause of its event the same way (a delay_seq without an event does not match).

Args:
    risk: The projects.risk frame; it needs prj_key, risk_no, cause_code (no nulls), status and delay_seq (whole numbers or null).
    lesson_learned: The projects.lesson_learned frame; it needs prj_key, category and delay_seq (whole numbers or null).
    delay_event: The projects.delay_event frame, one row per prj_key and seq; it needs prj_key, seq and cause_code.
    projects: Optional prj_key values (a key as text or a list) that limit the risks and lessons to a set.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A RiskLessons (named tuple) of four DataFrames. risk_causes: cause_code and risks, high first. lesson_categories: category and lessons, high first. occurred: prj_key, risk_no, delay_seq, risk_cause, event_cause and matches (the causes agree; false also when the event is missing), sorted by prj_key and risk_no. lessons: prj_key, category, delay_seq, event_cause and matches, sorted by prj_key, delay_seq and category.

Raises:
    FrameError: a frame is not a DataFrame, lacks a needed column or (delay_event) has a null in or repeats prj_key and seq; a risk has a null cause_code; delay_seq of the risks or lessons is not numeric or holds a value that is not a whole number.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import risk_lessons_summary
    >>> ctx = Context(stage="month12", role="analyst")
    >>> risk = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "risk_no": [1, 2], "cause_code": ["ground_conditions", "weather"],
    ...                      "status": ["occurred", "open"], "delay_seq": [1.0, None]})
    >>> lesson = pd.DataFrame({"prj_key": ["PRJ-900001"], "category": ["ground_conditions"], "delay_seq": [1.0]})
    >>> event = pd.DataFrame({"prj_key": ["PRJ-900001"], "seq": [1], "cause_code": ["ground_conditions"]})
    >>> r = risk_lessons_summary(risk, lesson, event, context=ctx)
    >>> r.risk_causes["risks"].tolist()
    [1, 1]
    >>> r.occurred["matches"].tolist()
    [True]
    >>> r.lessons["matches"].tolist()
    [True]

## Source columns

- `projects.risk.prj_key`
- `projects.risk.cause_code`
- `projects.risk.status`
- `projects.risk.delay_seq`
- `projects.lesson_learned.prj_key`
- `projects.lesson_learned.category`
- `projects.lesson_learned.delay_seq`
- `projects.delay_event.prj_key`
- `projects.delay_event.seq`
- `projects.delay_event.cause_code`
