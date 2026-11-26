# finance_exposure

```python
finance_exposure(project_financials: pd.DataFrame, period: str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the price exposure of the projects at a period as the finance data defines it: the cumulative exposure and the part that can be recovered.

Rule: the rows of the period with a price exposure or a recoverable amount different from zero are taken from finance.project_financials and converted to DKK at the booking rates. The open quantity definition of the exposure is a different figure.

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, price_exposure and price_recoverable, one row per project and period.
period: The period, text like 2026-03.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, currency, price_exposure, price_recoverable, price_exposure_dkk and price_recoverable_dkk; empty when no project has a non-zero row in the period.

## Raises

FrameError: a column is missing or a project has more than one row in the period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import finance_exposure
>>> ctx = Context(stage="month12", role="analyst")
>>> projects = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["EUR"], "price_exposure": [100.0], "price_recoverable": [40.0]})
>>> finance_exposure(projects, "2026-03", context=ctx)[["prj_key", "price_exposure", "price_recoverable"]].values.tolist()
[['PRJ-1', 100.0, 40.0]]
>>> finance_exposure(projects, "2026-04", context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.currency`, `finance.project_financials.price_exposure`, `finance.project_financials.price_recoverable`.
