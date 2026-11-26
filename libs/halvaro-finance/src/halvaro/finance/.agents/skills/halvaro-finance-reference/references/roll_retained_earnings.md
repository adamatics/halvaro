# roll_retained_earnings

```python
roll_retained_earnings(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, *, retained_earnings_gl: str = 'GL-3300', context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when a trial balance was built without carrying results and you need the results of completed fiscal years moved into the retained earnings account.

Rule: the input is the output of rebuild_trial_balance with carry_results False. The result of a fiscal year is the sum of the closing balances of the income statement accounts at its last period, and it is added to the retained earnings account from the next fiscal year on. Only the retained earnings rows differ, and that account gets a row in every period that lacks one. The table must start at the first period of the ledger. A stored finance.trial_balance already carries the roll, so a table whose retained earnings opening balance jumps at a fiscal year start is refused instead of being rolled twice.

## Args

trial_balance: Frame with le_key, period (text like 2026-12), gl_key, opening_balance, closing_balance and closing_balance_dkk.
gl_account: Frame finance.gl_account with gl_key and statement (IS or BS).
retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is the input plus rolled_opening_balance, rolled_closing_balance and rolled_closing_balance_dkk, sorted by entity, period and account.

## Raises

FrameError: a column is missing, the retained earnings account is not a balance sheet account of gl_account, or the retained earnings opening balance jumps at a fiscal year start (the table already carries the results).
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import roll_retained_earnings
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-12", "2027-01"], "gl_key": ["GL-5100", "GL-1000"], "opening_balance": [-50.0, 0.0],
...                    "closing_balance": [-100.0, 0.0], "closing_balance_dkk": [-100.0, 0.0]})
>>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
>>> out = roll_retained_earnings(tb, accounts, context=ctx).value
>>> out[out["gl_key"] == "GL-3300"][["period", "rolled_closing_balance"]].values.tolist()
[['2026-12', 0.0], ['2027-01', -100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.bookkeeping.fiscal_year_start_month`.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.opening_balance`, `finance.trial_balance.closing_balance`, `finance.trial_balance.closing_balance_dkk`, `finance.gl_account.gl_key`, `finance.gl_account.statement`.
