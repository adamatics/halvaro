# group_trial_balance

```python
group_trial_balance(journal_line: pd.DataFrame, reporting_adjustment: pd.DataFrame, consolidation_entry: pd.DataFrame, *, opening_sources: tuple[str, ...] = ('opening',), context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the movement of the group per period and account in DKK: the two entities plus the reporting adjustments plus the eliminations.

Rule: the movement of an entity is the sum of the DKK amounts of its journal lines in the period, as booked (not the change of translated closing balances). Lines of the opening journals (source in opening_sources) are not movement. adjustment_dkk is debit less credit. elimination_dkk is the debit side of the entries positive and the credit side negative; entries on the opening balance basis act on opening balances and are left out. An account whose movement is eliminated to zero is listed with zero. Opening and closing balances and the year end roll are not rebuilt.

## Args

journal_line: Frame finance.journal_line with le_key, period, gl_key, amount_dkk and source.
reporting_adjustment: Frame finance-reporting.reporting_adjustment with period, gl_key, debit_dkk and credit_dkk.
consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk.
opening_sources: The journal sources that are opening balances and not movement (default "opening").
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with period, gl_key, le01_movement_dkk, le02_movement_dkk, adjustment_dkk, elimination_dkk and movement_dkk (their sum), sorted by period and account.

## Raises

FrameError: a column is missing, an amount_dkk is null, or the lines name an entity other than LE-01 and LE-02.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import group_trial_balance
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01", "LE-02"], "period": ["2026-03"] * 2, "gl_key": ["GL-8000"] * 2, "amount_dkk": [100.0, -40.0], "source": ["manual"] * 2})
>>> adjustment = pd.DataFrame({"period": ["2026-03"], "gl_key": ["GL-8000"], "debit_dkk": [10.0], "credit_dkk": [0.0]})
>>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
>>> group_trial_balance(lines, adjustment, entry, context=ctx).value[["gl_key", "adjustment_dkk", "elimination_dkk", "movement_dkk"]].to_dict("records")
[{'gl_key': 'GL-8000', 'adjustment_dkk': 10.0, 'elimination_dkk': 100.0, 'movement_dkk': 170.0}, {'gl_key': 'GL-8100', 'adjustment_dkk': 0.0, 'elimination_dkk': -100.0, 'movement_dkk': -100.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.period`, `finance.journal_line.gl_key`, `finance.journal_line.amount_dkk`, `finance.journal_line.source`, `finance-reporting.reporting_adjustment.period`, `finance-reporting.reporting_adjustment.gl_key`, `finance-reporting.reporting_adjustment.debit_dkk`, `finance-reporting.reporting_adjustment.credit_dkk`.
