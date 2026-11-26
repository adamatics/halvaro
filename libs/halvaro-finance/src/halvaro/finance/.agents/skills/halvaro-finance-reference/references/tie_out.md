# tie_out

```python
tie_out(ledger_gross: pd.DataFrame, hr_aggregate: pd.DataFrame, *, tolerance: float | None = None, band_floor_factor: float = 0.97, band_ceiling_factor: float = 1.02, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you check the gross pay of the ledger against the aggregate of the hr side, per group of cost centres and month.

Rule: the ledger gross pay of all cost centres of a group of the aggregate is compared with its hr gross pay; they are tied when the difference (ledger less hr) is within tolerance. The ledger must also sit between the band minimum total times band_floor_factor and the band maximum total times band_ceiling_factor. Status is tied, difference, outside_band, suppressed (the aggregate hides the row) or ledger_only (the ledger has a cost centre that no group holds). This is an internal consistency check, not an audit, and no pay per person is accepted.

## Args

ledger_gross: The result of ledger_gross_pay, with le_key, cc_key, period and ledger_gross_pay, one row per entity, cost centre and month.
hr_aggregate: The result of halvaro.hr.payroll_aggregate with le_key, cc_key, period, currency, hr_gross_pay, band_minimum_total, band_maximum_total, cost_centres (comma separated) and suppressed.
tolerance: Largest accepted difference per group and month. None takes the fact policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk (proposed). Optional.
band_floor_factor: Factor on the band minimum total. Default 0.97 (proposed).
band_ceiling_factor: Factor on the band maximum total. Default 1.02 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, cc_key, period, cost_centres, currency, ledger_gross_pay, hr_gross_pay, difference, band_minimum_total, band_maximum_total, within_tolerance, within_band_envelope and status.

## Raises

FrameError: a column is missing, a frame has a column that names a person or a base salary, tolerance or a factor is not a valid number, a ledger or aggregate row is repeated, suppressed or cost_centres is null or not valid, an unsuppressed row has a null pay or band total, or a cost centre is in two groups of the same month.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import tie_out
>>> ctx = Context(stage="month12", role="analyst")
>>> ledger = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "ledger_gross_pay": [1000.0]})
>>> hr = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "currency": ["DKK"], "hr_gross_pay": [1000.0], "band_minimum_total": [900.0],
...                    "band_maximum_total": [1100.0], "cost_centres": ["CC-1"], "suppressed": [False]})
>>> tie_out(ledger, hr, context=ctx).value[["cc_key", "difference", "status"]].values.tolist()
[['CC-1', 0.0, 'tied']]
>>> tie_out(ledger, hr.assign(hr_gross_pay=900.0), context=ctx).value["status"].tolist()
['difference']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.cc_key`, `finance.payroll_hr_reconciliation.difference`, `finance.payroll_hr_reconciliation.within_tolerance`, `finance.payroll_hr_reconciliation.within_band_envelope`.
