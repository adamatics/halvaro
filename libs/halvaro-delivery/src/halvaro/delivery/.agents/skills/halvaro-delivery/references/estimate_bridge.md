# estimate_bridge

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import estimate_bridge`.

```python
estimate_bridge(estimate_version: pd.DataFrame, estimate_line: pd.DataFrame, cost_code: pd.DataFrame, *, full_projects: Sequence[str] | None = None, as_of: DateLike | None = None, status: pd.Series | None = None, context: halvaro.core.access.Context) -> EstimateBridge
```

Use this when you need the amounts by cost code of the tender, budget, forecast and final estimate of each project, with the stored totals and the versions that are missing.

Per project and type the latest version counts (highest estimate_version); a project may have several forecast versions. With `as_of` only versions dated on or before it exist, so the forecasts quoted at an earlier date are the earlier versions; as_of is a calendar day, inclusive (a version dated that day, at any time of day, counts), and a number, a time zone or an unreadable date is refused with FrameError. Money stays in the currency of the version; nothing is converted. Several estimate lines of one cost code are kept as separate lines.

Result fields: lines has prj_key, type, estimate_version, cst_key, category, amount, currency. totals has one row per project and type with the line sum, the stored total_cost and their difference (the generator asserts it within 40). missing lists the (prj_key, type) pairs without a version, for `full_projects` when given (legacy summary projects have no estimates and are not listed).

Which absences are expected: the baseline data (full projects) has tender and budget for every project, final for every completed project and for no other, and forecast for all active projects but only for part of the completed ones and for no planned one, so a forecast is NOT tied to status (it is optional) while tender, budget and final are. Pass `status` (a Series prj_key -> planned, active or completed, for example from projects.project_status) and missing gains a boolean column `expected`: True where the absence is by design (planned: tender and budget only, so forecast and final are expected; active: final expected; completed: nothing but forecast; forecast is always expected), False where the version should exist or the status of the project is not given. Without `status` missing has the two columns only.

Args:
    estimate_version: The projects.estimate_version frame, one row per prj_key and estimate_version; it needs prj_key, estimate_version, type (tender, budget, forecast or final), date, currency and total_cost.
    estimate_line: The projects.estimate_line frame; it needs prj_key, estimate_version, cst_key and amount, and may carry currency.
    cost_code: The projects.cost_code frame, one row per cst_key; it needs cst_key and category.
    full_projects: The prj_key values of the full projects for which missing versions are listed (a key as text or a list); without it missing is empty.
    as_of: The day on which only versions dated on or before it exist (a date, a Timestamp or an ISO text); without it every version counts.
    status: A Series prj_key -> planned, active or completed that adds the column `expected` to missing; without it missing has the two columns only.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An EstimateBridge (named tuple) of three DataFrames. lines is sorted by prj_key, type and cst_key; totals by prj_key and type (columns prj_key, type, estimate_version, currency, total_cost, line_sum, difference); missing by project in the order of the types tender, budget, forecast, final (columns prj_key, type and, with status, expected).

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names, lacks a needed column, has a null in or repeats a key (estimate_version by prj_key and estimate_version, cost_code by cst_key); type is not text, is null or is not one of tender, budget, forecast, final; amount or total_cost is not numeric or has nulls; category has nulls; as_of is a number, has a time zone or is not a date; a version date is not a date, has a time zone or is null; an estimate line belongs to a version that is not in estimate_version or points at a cst_key that is not in cost_code; a line currency differs from the currency of its version; status is not a Series, repeats a project or holds an unknown value.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import estimate_bridge
    >>> ctx = Context(stage="month12", role="analyst")
    >>> ver = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "estimate_version": [1, 2], "type": ["tender", "budget"],
    ...                     "date": ["2025-01-10", "2025-02-01"], "currency": ["DKK", "DKK"], "total_cost": [150.0, 140.0]})
    >>> line = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "estimate_version": [1, 1, 2], "cst_key": ["CST-100", "CST-200", "CST-100"], "amount": [100.0, 50.0, 140.0]})
    >>> codes = pd.DataFrame({"cst_key": ["CST-100", "CST-200"], "category": ["civil", "electrical"]})
    >>> r = estimate_bridge(ver, line, codes, full_projects=["PRJ-900001"], status=pd.Series({"PRJ-900001": "planned"}), context=ctx)
    >>> r.totals["type"].tolist()
    ['budget', 'tender']
    >>> r.missing[["type", "expected"]].values.tolist()
    [['forecast', True], ['final', True]]

## Source columns

- `projects.estimate_version.prj_key`
- `projects.estimate_version.estimate_version`
- `projects.estimate_version.type`
- `projects.estimate_version.date`
- `projects.estimate_version.currency`
- `projects.estimate_version.total_cost`
- `projects.estimate_line.prj_key`
- `projects.estimate_line.estimate_version`
- `projects.estimate_line.cst_key`
- `projects.estimate_line.amount`
- `projects.cost_code.cst_key`
- `projects.cost_code.category`
