# cost_to_completion

```python
cost_to_completion(project_financials: pd.DataFrame, prj_keys: str | Sequence[str], period: str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the cost still to come on a list of projects in one period: EAC less actual cost, with the committed cost shown apart.

Rule: cost_to_completion is EAC less actual cost and uncommitted is that less the committed cost, both to two decimals. Amounts stay in the currency of the row and are never summed across currencies. A project without a row in the period is listed with the reason "no finance row".

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, eac, actual_cost and committed_cost, one row per project and period.
prj_keys: The projects, one key or a list of keys, each at most once.
period: The period, text like 2026-03.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, currency, eac, actual_cost, cost_to_completion, committed_cost, uncommitted and reason, one row per key in the order given.

## Raises

FrameError: a column is missing, a period is not text like 2026-03, a key is repeated, or the frame has two rows for a project in the period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_to_completion
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["DKK"], "eac": [800.0], "actual_cost": [400.0], "committed_cost": [100.0]})
>>> r = cost_to_completion(pf, ["PRJ-1", "PRJ-9"], "2026-03", context=ctx).set_index("prj_key")
>>> r[["cost_to_completion", "uncommitted"]].loc["PRJ-1"].to_dict(), r.loc["PRJ-9", "reason"]
({'cost_to_completion': 400.0, 'uncommitted': 300.0}, 'no finance row')
>>> cost_to_completion(pf, ["PRJ-1"], "2026-3", context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: period must be text like 2025-11, not '2026-3'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.committed_cost`, `finance.project_financials.currency`.
