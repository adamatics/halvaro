# condition_class_from_score

Module `halvaro.grid.geometry`. Import: `from halvaro.grid import condition_class_from_score`.

```python
condition_class_from_score(score: pd.Series, *, bands: Sequence[Any] = ((80.0, 'A'), (60.0, 'B'), (40.0, 'C'), (20.0, 'D')), context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need the condition class A to E of condition scores.

The class is the first band whose lower bound the score reaches (A at 80 and above, B 60, C 40, D 20), E below; null for a null score.

PROPOSED: the bands (policy.grid.condition_class_bands is needed; the rule is in the generator code only).

Args:
    score: A Series of condition scores from 0 to 100 (for example gis.grid_element.condition_score).
    bands: Pairs (lower bound, class) in falling order of the lower bound (PROPOSED: A at 80, B 60, C 40, D 20).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Series named condition_class with the index of score, holding the class letters (null for a null score).

Raises:
    FrameError: score is not a Series or holds a value that is not a number; a score is outside 0 to 100; bands are not (lower bound, class) pairs in falling order.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import condition_class_from_score
    >>> ctx = Context(stage="month12", role="analyst")
    >>> condition_class_from_score(pd.Series([95, 60, 10, None]), context=ctx).tolist()
    ['A', 'B', 'E', None]

## Source columns

- `gis.grid_element.condition_score`
