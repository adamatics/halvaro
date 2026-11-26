# condition_trend

Module `halvaro.grid.assets`. Import: `from halvaro.grid import condition_trend`.

```python
condition_trend(condition_assessment: pd.DataFrame, grid_element: pd.DataFrame, group: Iterable[Any], before: DateLike, after: DateLike, *, context: halvaro.core.access.Context) -> ConditionTrend
```

Use this when you need the change of the condition score of a group of elements between two dates, checked against the gis score.

Score change of a group over two dates: the mean of each group element's last assessment strictly before `before`, the mean of the group's assessments on or after `after` (one value per
element: its first assessment from that date), the change (after less before), and for all assessed elements the mean and standard deviation of the last assessment less the gis condition score.
Elements without an assessment in a period are not in that mean (n_before, n_after count the elements). `before` must not be after `after`. An element twice on one date raises FrameError.

Args:
    condition_assessment: The service.condition_assessment table; it needs the columns net_key, assessed_on and score.
    grid_element: The gis.grid_element table; it needs the columns net_key and condition_score.
    group: One net_key or an iterable of net_keys, the elements of the group.
    before: The first date; the last assessment strictly before it counts as the earlier state.
    after: The second date; the first assessment on or after it counts as the later state; not before `before`.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ConditionTrend with the fields n_before, mean_before, n_after, mean_after, change (after less before), n_assessed, last_vs_gis_mean and last_vs_gis_sd, all rounded to three decimals. A mean or the change is NaN when its period has no assessed element; the standard deviation is NaN with fewer than two assessed elements.

Raises:
    FrameError: a needed column is missing; the group has no element; before or after is not a date or before is after after; an element has two assessments on one date; a score is null.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import condition_trend
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ca = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900002"], "assessed_on": ["2020-01-01", "2022-01-01", "2020-06-01"], "score": [80.0, 60.0, 70.0]})
    >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "condition_score": [58.0, 72.0]})
    >>> t = condition_trend(ca, ge, ["NET-900001", "NET-900002"], "2021-01-01", "2021-06-01", context=ctx)
    >>> (t.n_before, t.mean_before, t.n_after, t.change)
    (2, 75.0, 1, -15.0)

## Source columns

- `service.condition_assessment.net_key`
- `service.condition_assessment.assessed_on`
- `service.condition_assessment.score`
- `gis.grid_element.net_key`
- `gis.grid_element.condition_score`
