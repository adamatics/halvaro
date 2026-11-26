# estimate_amount_per_metre

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import estimate_amount_per_metre`.

```python
estimate_amount_per_metre(lines: pd.DataFrame, project: pd.DataFrame, *, route_length: pd.DataFrame | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the estimate amount per route metre by cost code and category for each project, from the lines of estimate_bridge.

Rows follow the `lines` frame of estimate_bridge. per_metre is null when the length is null or not positive (the project is kept, nothing is dropped silently). `route_length` (prj_key, route_length_m) replaces the planned length, for example the as-built length from the route change of the grid library; where its value is null the planned length is used. length_source says which: 'as_built' (the length of `route_length`) or 'planned' (the project frame). The estimate side only: actual cost per metre is a finance function. Amounts of different currencies are never added; each row keeps its currency.

Args:
    lines: The lines output of estimate_bridge; it needs prj_key, type, cst_key, category, amount (numeric, no nulls) and currency.
    project: The projects.project frame, one row per prj_key; it needs prj_key and route_length_m (the planned length, numeric).
    route_length: Optional frame with prj_key (one row each) and route_length_m that replaces the planned length where its value is not null.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame in the order of the lines with the columns prj_key, type, cst_key, category, currency, amount, route_length_m, length_source and per_metre (amount over the length, null where the length is null or not positive).

Raises:
    FrameError: lines, project or route_length is not a DataFrame, lacks a needed column or (project, route_length) repeats a prj_key; a project of the lines is not in the project frame; amount is not numeric or has nulls; route_length_m is not numeric.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import estimate_amount_per_metre
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "type": ["tender", "tender"], "cst_key": ["CST-100", "CST-200"],
    ...                       "category": ["civil", "electrical"], "amount": [100.0, 50.0], "currency": ["DKK", "DKK"]})
    >>> project = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [1000.0]})
    >>> r = estimate_amount_per_metre(lines, project, context=ctx)
    >>> [round(x, 3) for x in r["per_metre"]]
    [0.1, 0.05]
    >>> built = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [500.0]})
    >>> r = estimate_amount_per_metre(lines, project, route_length=built, context=ctx)
    >>> r["length_source"].unique().tolist()
    ['as_built']

## Source columns

- `projects.project.prj_key`
- `projects.project.route_length_m`
- `projects.estimate_line.amount`
- `projects.cost_code.category`
