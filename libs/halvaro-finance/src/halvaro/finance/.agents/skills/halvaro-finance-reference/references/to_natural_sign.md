# to_natural_sign

```python
to_natural_sign(frame: pd.DataFrame, gl_account: pd.DataFrame, column: str = 'amount', gl_column: str = 'gl_key', *, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when a ledger column is debit positive and you need it in the sign people read: revenue and liabilities positive.

Rule: the amount of a line on a credit normal account is multiplied by minus one, a line on a debit normal account is kept. A zero stays zero (never minus zero).

## Args

frame: Frame with the amount column and the account column.
gl_account: Frame finance.gl_account with gl_key and normal_balance (debit or credit), one row per account.
column: Name of the amount column. Default "amount".
gl_column: Name of the account column. Default "gl_key".
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named like the amount column, on the index of the frame.

## Raises

FrameError: a column is missing, gl_account has an account twice or a normal_balance that is neither debit nor credit, or a row names an account that is not in gl_account.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import to_natural_sign
>>> ctx = Context(stage="month12", role="analyst")
>>> accounts = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "normal_balance": ["debit", "credit"]})
>>> lines = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "amount": [100.0, -40.0]})
>>> to_natural_sign(lines, accounts, context=ctx).tolist()
[100.0, 40.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.gl_account.gl_key`, `finance.gl_account.normal_balance`.
