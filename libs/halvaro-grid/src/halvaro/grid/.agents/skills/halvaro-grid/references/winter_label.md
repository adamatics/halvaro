# winter_label

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import winter_label`.

```python
winter_label(ts: TimesLike, *, months: Sequence[int] = (11, 12, 1, 2, 3), context: halvaro.core.access.Context) -> str | None | pd.Series
```

Use this when you need the winter season of a timestamp or a series of timestamps as a label such as 2025/26.

The label is like '2025/26' (the season starts in July, so January 2026 is 2025/26) and null outside the winter months. A timestamp gives text or None, a Series gives a Series.
PROPOSED: the months November to March (policy.grid.winter_window is needed).

Args:
    ts: A timestamp, or a list, tuple, array, Index or Series of timestamps (UTC without time zone).
    months: The month numbers 1 to 12 that count as winter; default (11, 12, 1, 2, 3) (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    The label as text, or None outside the winter months, for one timestamp; a Series of labels (None outside the winter months) for several, with the index of ts when it is a Series.

Raises:
    FrameError: months is empty or holds something that is not a month number 1 to 12; ts holds numbers, a time zone or a value that is not a timestamp.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> from halvaro.core import Context
    >>> from halvaro.grid import winter_label
    >>> ctx = Context(stage="month12", role="analyst")
    >>> winter_label("2026-01-15 12:00", context=ctx)
    '2025/26'
    >>> winter_label("2026-06-15 12:00", context=ctx) is None
    True
    >>> winter_label(["2025-12-01", "2026-07-01"], context=ctx).tolist()
    ['2025/26', None]

## Source columns

- `telemetry.measurement.ts`
