# eliminations

```python
eliminations(consolidation_entry: pd.DataFrame, group_trial_balance: pd.DataFrame | None = None, *, tolerance: float = 0.011, period_tolerance: float = 0.5, required_types: tuple[str, ...] = ('investment', 'ic_loan', 'ic_trade_revenue'), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need to check the consolidation entries of the group: that they are positive, balanced, between two different accounts, complete by type, and zero over a period.

Rule: every violation is listed. non_positive_amount: an amount that is not above zero. entry_unbalanced: a stored difference above tolerance. same_account: an entry that debits and credits the same account of the same entity. entry_type_missing: a type of required_types without an entry (PROPOSED investment, ic_loan, ic_trade_revenue). period_not_zero: with the group trial balance, the eliminations of a period that do not sum to zero within period_tolerance. The entries are not recomputed from the books of the entities.

## Args

consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk, one row per year, period and entry number.
group_trial_balance: Optional frame with period, gl_key and elimination_dkk; when given, the eliminations of each period are checked to sum to zero.
tolerance: Largest accepted stored difference of an entry in DKK (default 0.011).
period_tolerance: Largest accepted sum of the eliminations of a period in DKK (default 0.5).
required_types: The entry types that must each have an entry (default investment, ic_loan, ic_trade_revenue, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with the columns table, key, rule and detail; empty when the entries are clean.

## Raises

FrameError: a column is missing, an entry number is repeated within a year and period, or a tolerance is negative or not a number.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import eliminations
>>> ctx = Context(stage="month12", role="analyst")
>>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
>>> eliminations(entry, context=ctx)[["key", "rule"]].to_dict("records")
[{'key': 'ic_loan', 'rule': 'entry_type_missing'}, {'key': 'ic_trade_revenue', 'rule': 'entry_type_missing'}]
>>> eliminations(entry.assign(difference_dkk=5.0), required_types=("investment",), context=ctx)[["key", "rule"]].to_dict("records")
[{'key': '2026-03 #1', 'rule': 'entry_unbalanced'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance-reporting.consolidation_entry.fiscal_year`, `finance-reporting.consolidation_entry.period`, `finance-reporting.consolidation_entry.entry_no`, `finance-reporting.consolidation_entry.entry_type`, `finance-reporting.consolidation_entry.basis`, `finance-reporting.consolidation_entry.debit_le_key`, `finance-reporting.consolidation_entry.debit_gl_key`, `finance-reporting.consolidation_entry.credit_le_key`, `finance-reporting.consolidation_entry.credit_gl_key`, `finance-reporting.consolidation_entry.amount_dkk`, `finance-reporting.consolidation_entry.difference_dkk`, `finance-reporting.group_trial_balance.period`, `finance-reporting.group_trial_balance.elimination_dkk`.
