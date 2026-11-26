# labour_absorption_check

```python
labour_absorption_check(journal_line: pd.DataFrame, *, project_labour: str = 'GL-6100', project_absorbed: str = 'GL-7900', service_absorbed: str = 'GL-7910', service_accounts: tuple[str, ...] = ('GL-6610', 'GL-6620'), max_warranty_share: float = 0.2, tolerance: float = 0.005, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that labour booked on projects and on service is absorbed in the ledger, per entity and month for projects and over the whole window for service.

Rule: for each entity and month, the lines on project_labour and project_absorbed must net to zero within tolerance, else the violation project_labour_not_absorbed. Over the whole window and all entities, the service labour (the lines on service_accounts) must be covered by the credit on service_absorbed, and the absorbed amount may exceed it by at most max_warranty_share of itself (the rest is the warranty ticket charge), else the violation service_labour_not_absorbed. The service sums use amount_dkk when the frame has it, otherwise amount. Amounts are in currency units and summed in whole cents; the tolerance is cut down to whole cents. All keyword defaults are proposed business choices (accounts, share and tolerance).

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, period and amount, and optionally amount_dkk and currency, one row per line.
project_labour: Account of project labour at standard rate. Default GL-6100 (proposed).
project_absorbed: Account of labour absorbed to projects. Default GL-7900 (proposed).
service_absorbed: Account of labour absorbed to service. Default GL-7910 (proposed).
service_accounts: Accounts of service labour, as a tuple. Default GL-6610 and GL-6620 (proposed).
max_warranty_share: Largest share of the absorbed service amount that may exceed the service labour, from 0 to below 1. Default 0.2 (proposed).
tolerance: Largest accepted difference in currency units, zero or more. Default 0.005 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail: project_labour_not_absorbed (key is the entity and month; the net amount is written in the detail text, not in a column) and service_labour_not_absorbed (key is "window"); empty when the labour is absorbed.

## Raises

FrameError: a column is missing, an amount is null, an le_key is null, an amount is text that is not a number, max_warranty_share is not a number from 0 to below 1, tolerance is not a number of zero or more, service_accounts is a string, or the service lines are in more than one currency while the frame has no amount_dkk.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import labour_absorption_check
>>> ctx = Context(stage="month12", role="analyst")
>>> jl = pd.DataFrame({"le_key": ["LE-A"] * 4, "period": ["2026-01"] * 4, "gl_key": ["GL-6100", "GL-7900", "GL-6610", "GL-7910"], "amount": [1000.0, -900.0, 100.0, -100.0]})
>>> labour_absorption_check(jl, context=ctx)[["key", "rule", "detail"]].values.tolist()
[['LE-A 2026-01', 'project_labour_not_absorbed', 'GL-6100 and GL-7900 net to 100.00, not zero']]
>>> labour_absorption_check(jl.assign(amount=[1000.0, -1000.0, 100.0, -100.0]), context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`.
