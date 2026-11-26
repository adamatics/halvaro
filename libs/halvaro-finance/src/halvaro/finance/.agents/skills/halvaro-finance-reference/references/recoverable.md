# recoverable

```python
recoverable(open_exposure_result: pd.DataFrame, terms: pd.DataFrame, contracts: pd.DataFrame, *, apply_threshold: bool = False, on: dt.date | str | pd.Timestamp | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the part of the price exposure that the customer contract passes on to the customer, per project.

Rule: exposure times the pass-through percent of the customer contract of the project, to the cent; a fixed price contract passes nothing on. The rest is absorbed. With apply_threshold (proposed False) nothing is passed on when the largest step of the project does not exceed the threshold percent of the terms; the default passes the percent on whatever the size of the step. Only the contracts of `contracts` are read from `terms`. A contract with more than one clause row needs `on`; then every used contract is read on that date and of the clauses in force the one with the latest start counts (never two).

## Args

open_exposure_result: The result of open_exposure, with prj_key, exposure_dkk and step_percent_max.
terms: Frame from price_adjustment_terms with con_key, pass_through_percent and threshold_percent (null when none), and valid_from and valid_to when a contract has several clauses.
contracts: Frame from contracts_for_project with prj_key, con_key and price_type, one row per project.
apply_threshold: True passes nothing on when step_percent_max does not exceed threshold_percent. Default False (proposed).
on: The date to read the clauses on (no time zone), needed when a contract has more than one clause row. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, con_key, price_type, exposure_dkk, pass_through_percent, threshold_percent, recoverable_dkk and absorbed_dkk, sorted by project.

## Raises

FrameError: a column is missing, contracts has more than one row for a project, a contract has several clause rows and on is missing or terms lacks valid_from and valid_to, on has a time zone, a clause has no valid_from or ends before it starts, no clause or two clauses with the same start are in force on the date, a project has no contract, a contract that is not fixed price has no terms, or a pass-through percent is outside 0 to 100.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import recoverable
>>> ctx = Context(stage="month12", role="analyst")
>>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_dkk": [1000.0], "step_percent_max": [10.0]})
>>> terms = pd.DataFrame({"con_key": ["CON-1"], "pass_through_percent": [50.0], "threshold_percent": [None]})
>>> contracts = pd.DataFrame({"prj_key": ["PRJ-1"], "con_key": ["CON-1"], "price_type": ["indexed"]})
>>> recoverable(opened, terms, contracts, context=ctx)[["prj_key", "recoverable_dkk", "absorbed_dkk"]].values.tolist()
[['PRJ-1', 500.0, 500.0]]
>>> recoverable(opened, terms, contracts.assign(price_type="fixed_price"), context=ctx)["recoverable_dkk"].tolist()
[0.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `contracts.contract.price_type`, `contracts.clause.param_value`, `contracts.clause.param2_value`.
