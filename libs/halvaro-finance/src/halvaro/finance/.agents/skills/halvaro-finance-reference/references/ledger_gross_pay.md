# ledger_gross_pay

```python
ledger_gross_pay(journal_line: pd.DataFrame, *, accounts: tuple[str, ...] = ('GL-7000', 'GL-7005', 'GL-7050'), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the gross salary booked in the ledger per legal entity, cost centre and month, to tie out against the payroll summary.

Rule: the sum of the journal lines on the salary accounts, in the currency of the entity, debit positive, to the cent. The default accounts GL-7000, GL-7005 and GL-7050 are PROPOSED until fin.payroll_on_costs.gross_salary_accounts is a fact.

## Args

journal_line: Frame finance.journal_line with le_key, cc_key, gl_key, period and amount.
accounts: The salary accounts (default GL-7000, GL-7005 and GL-7050, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, cc_key, period and ledger_gross_pay, sorted by those three columns.

## Raises

FrameError: a column is missing, accounts is not a non-empty tuple of account keys, or a line on these accounts has no cost centre, entity or period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import ledger_gross_pay
>>> ctx = Context(stage="month3", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 3, "cc_key": ["CC-1"] * 3, "gl_key": ["GL-7000", "GL-7005", "GL-6000"], "period": ["2026-03"] * 3, "amount": [1000.5, 200.25, 50.0]})
>>> ledger_gross_pay(lines, context=ctx).to_dict("records")
[{'le_key': 'LE-01', 'cc_key': 'CC-1', 'period': '2026-03', 'ledger_gross_pay': 1200.75}]
>>> ledger_gross_pay(lines.assign(cc_key=[None, "CC-1", "CC-1"]), context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: gross salary lines without a cost centre, entity or period; the tie-out is per cost centre
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.cc_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`.
