# tax_provision

```python
tax_provision(provision: pd.DataFrame, *, tolerance: float = 0.011, context: Context) -> Envelope
```

Use this when you need the corporate tax provision of each entity and fiscal year recomputed from its inputs and compared with the stored rows.

Rule, per entity in fiscal year order: taxable income before losses = profit before tax + non deductible expenses - exempt income - temporary difference movement. A negative result is added
to the loss carried forward; a positive one is reduced by the loss utilised, at most the share of the fact frep.corporate_tax.tax_losses.utilisation_cap_share_of_taxable_income of the income
and at most the loss carried in. taxable income = income before losses - loss utilised. current tax = rate x taxable income. total tax expense = current tax + the stored deferred movement.
The rate of the row is compared with the fact frep.corporate_tax.<country>.rate (status VERIFY). The deferred movement is taken as stored: its inputs are not in the row. The function
refuses when the fact fin.corporate_tax.posted_in_ledger is true, because the provision would then be counted twice.

## Args

provision: Frame finance-reporting.tax_provision with the inputs and the stored results, one row per entity and fiscal year.
tolerance: Largest accepted difference between a recomputed and a stored figure, in currency units (default 0.011).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, fiscal_year, tax_rate (a share), profit_before_tax, taxable_income_before_losses, tax_loss_utilised, tax_loss_added,
tax_loss_carried_forward, taxable_income, current_tax, deferred_tax_movement, total_tax_expense (currency units), rate_is_the_fact and agrees (yes or no).
Typed form: TaxProvisionRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, a row has no entity or fiscal year, an entity and year appear twice, an input is null, or fin.corporate_tax.posted_in_ledger is true.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context, fact
>>> from halvaro.finance import tax_provision
>>> from halvaro.finance.vat_tax import _TAX_COLS
>>> ctx = Context(stage="month12", role="analyst")
>>> rate = fact("frep.corporate_tax.DK.rate").value
>>> row = dict.fromkeys(_TAX_COLS, 0.0)
>>> row.update(le_key="LE-01", fiscal_year=2025, tax_rate=rate, profit_before_tax=1000.0, taxable_income_before_losses=1000.0, taxable_income=1000.0,
...            current_tax=round(1000.0 * rate, 2), total_tax_expense=round(1000.0 * rate, 2))
>>> r = tax_provision(pd.DataFrame([row]), context=ctx).value
>>> r.loc[0, ["taxable_income", "current_tax", "rate_is_the_fact", "agrees"]].tolist() == [1000.0, round(1000.0 * rate, 2), True, True]
True
```

## Typed result

`TaxProvisionRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `frep.corporate_tax.DK.rate`, `frep.corporate_tax.DE.rate`, `frep.corporate_tax.tax_losses.utilisation_cap_share_of_taxable_income`.

Source columns: `finance-reporting.tax_provision.fiscal_year`, `finance-reporting.tax_provision.tax_rate`, `finance-reporting.tax_provision.profit_before_tax`, `finance-reporting.tax_provision.non_deductible_expenses`, `finance-reporting.tax_provision.exempt_income`, `finance-reporting.tax_provision.temporary_difference_movement`, `finance-reporting.tax_provision.taxable_income_before_losses`, `finance-reporting.tax_provision.tax_loss_utilised`, `finance-reporting.tax_provision.tax_loss_added`, `finance-reporting.tax_provision.tax_loss_carried_forward`, `finance-reporting.tax_provision.taxable_income`, `finance-reporting.tax_provision.current_tax`, `finance-reporting.tax_provision.deferred_tax_movement`, `finance-reporting.tax_provision.total_tax_expense`, `finance-reporting.tax_provision.le_key`.
