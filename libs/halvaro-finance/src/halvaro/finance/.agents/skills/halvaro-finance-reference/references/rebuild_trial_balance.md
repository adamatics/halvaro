# rebuild_trial_balance

```python
rebuild_trial_balance(journal_line: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, *, carry_results: bool = True, retained_earnings_gl: str = 'GL-3300', context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the trial balance per entity, period and account rebuilt from the journal lines and the opening items.

Rule: amounts are summed in cents. The opening journals are not movements. Balance sheet accounts run from the opening items and income statement accounts restart at each fiscal year start (there are no closing journals). With carry_results the results of earlier fiscal years sit in the retained earnings account, as in the stored table; with carry_results False they are left out (the input of roll_retained_earnings). A row exists for a non-zero opening or closing balance (also in DKK) or a non-zero movement.

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, amount, amount_dkk, currency, period (text like 2026-01) and source.
opening_balance_item: Frame finance.opening_balance_item with le_key, gl_key, amount and amount_dkk, balance sheet accounts only.
gl_account: Frame finance.gl_account with gl_key and statement (IS or BS), one row per account.
carry_results: True puts the results of earlier fiscal years in the retained earnings account. Default True.
retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame in the shape of finance.trial_balance: le_key, period, gl_key, opening_balance, debit, credit, closing_balance, currency and closing_balance_dkk.

## Raises

FrameError: a column is missing, journal_line is empty or has a line without le_key, gl_key or period, a period is not text like 2026-01, gl_account repeats an account or has a statement other than IS or BS, the retained earnings account is not a balance sheet account, an opening item is on a result account or belongs to an entity without lines, an account is not in gl_account, or an entity has more than one currency.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import rebuild_trial_balance
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 2, "gl_key": ["GL-1000", "GL-5100"], "amount": [100.0, -100.0], "amount_dkk": [100.0, -100.0], "currency": ["DKK"] * 2,
...                       "period": ["2026-01"] * 2, "source": ["manual"] * 2})
>>> opening = pd.DataFrame({"le_key": [], "gl_key": [], "amount": [], "amount_dkk": []})
>>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
>>> rebuild_trial_balance(lines, opening, accounts, context=ctx).value[["gl_key", "closing_balance"]].values.tolist()
[['GL-1000', 100.0], ['GL-5100', -100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.bookkeeping.fiscal_year_start_month`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`, `finance.journal_line.currency`, `finance.journal_line.period`, `finance.journal_line.source`, `finance.opening_balance_item.le_key`, `finance.opening_balance_item.gl_key`, `finance.opening_balance_item.amount`, `finance.opening_balance_item.amount_dkk`, `finance.gl_account.gl_key`, `finance.gl_account.statement`.
