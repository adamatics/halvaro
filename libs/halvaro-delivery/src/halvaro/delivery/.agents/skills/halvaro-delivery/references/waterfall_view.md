# waterfall_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import waterfall_view`.

```python
waterfall_view(lines: pd.DataFrame, *, from_type: str = 'tender', to_type: str = 'final', as_of: DateLike | None = None, legacy: int | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need the step from one estimate type to another by cost category, per currency, for a waterfall chart.

The frame has the columns currency, category, from_amount, to_amount and delta, plus a 'total' row per currency. Only projects that have both types in the same currency are included in that currency; n_projects (in extra) says how many. A null category is shown as '(none)'. `lines` is the lines frame of estimate_bridge (prj_key, type, category, amount, currency). Currencies are never added. from_type and to_type must differ.

Args:
    lines: The lines frame of estimate_bridge; it needs prj_key, type, category, amount and currency.
    from_type: The estimate type to start from (default 'tender').
    to_type: The estimate type to end at (default 'final'); it must differ from from_type.
    as_of: Optional as-of date, shown in the caption.
    legacy: Optional number of legacy projects, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'waterfall': `frame` (currency, category, from_amount, to_amount, delta; sorted by currency, then category with the total row last), x category, y delta, group currency, n the number of line rows used, extra['n_projects'] the number of projects with both types.

Raises:
    FrameError: lines is not a DataFrame or lacks a needed column; from_type equals to_type; a line has a null currency.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import waterfall_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001"] * 4, "type": ["tender", "final", "tender", "final"], "category": ["labour", "labour", "plant", "plant"],
    ...                       "amount": [100.0, 130.0, 50.0, 40.0], "currency": ["EUR"] * 4})
    >>> spec = waterfall_view(lines, context=ctx)
    >>> spec.frame["category"].tolist()
    ['labour', 'plant', 'total']
    >>> spec.frame["delta"].tolist()
    [30.0, -10.0, 20.0]
    >>> spec.extra["n_projects"]
    1

## Source columns

- `projects.estimate_line.prj_key`
- `projects.estimate_line.amount`
- `projects.cost_code.category`
