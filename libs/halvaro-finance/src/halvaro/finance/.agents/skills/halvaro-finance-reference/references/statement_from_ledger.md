# statement_from_ledger

```python
statement_from_ledger(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame, le_key: str, country: str, fiscal_year: int, *, require_full_year: bool = True, context: <class 'halvaro.core.access.Context'>) -> LedgerStatement
```

Use this when you rebuild the statutory lines of one entity and fiscal year from its trial balance, in the entity currency and the natural sign.

Rule: an income statement line is the movement of the year (credit less debit over the periods of the year) of the accounts mapped to it; a balance sheet line is the closing balance of the last period of the year, with the sign of the normal side of the line (credit positive). Amounts are summed in integer cents and returned in currency units (cents divided by 100, floats). In unmapped, amount_debit_positive_for_bs is credit less debit for income statement accounts and the debit positive closing balance for balance sheet accounts. The fiscal year is the calendar year. Accounts with a balance and no statutory map are returned in unmapped, and pbt is the sum of the income statement lines other than TAX; tax lines are not in the ledger accounts, so they appear as unmapped when an account carries them.

## Args

trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-03), gl_key, debit, credit and closing_balance, one row per entity, period and account.
gl_account: Frame finance.gl_account with gl_key, statement (IS or BS) and the map column of the country (dk_statutory_map or de_statutory_map).
statutory_map_line: Frame finance.statutory_map_line with map_code, line_code, statement and normal_side (debit or credit), one row per map code.
le_key: The entity.
country: DK or DE; it selects the map column of the chart of accounts.
fiscal_year: The calendar year, a whole number.
require_full_year: True demands all twelve periods of the year in the trial balance; False accepts a part year. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

LedgerStatement, a named tuple: lines (a DataFrame with map_code, line_code, statement, amount and n_accounts), unmapped (a DataFrame with gl_key, kind and amount_debit_positive_for_bs) and pbt (a number).

## Raises

FrameError: country is not DK or DE, fiscal_year is not a whole year, a column is missing, a key is repeated, an amount is null or text that is not a number, a period is null or malformed, a normal side is not debit or credit, an account is not in the chart of accounts, a statement is not IS or BS, the entity has no rows in the year or too few periods when require_full_year is true, a balance sheet account with a balance has no row in the last period, a map code is not in the map, or an account is mapped to a line of the other statement.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import statement_from_ledger
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-A", "LE-A"], "period": ["2026-01", "2026-01"], "gl_key": ["GL-4000", "GL-1000"], "debit": [0.0, 500.0], "credit": [500.0, 0.0], "closing_balance": [-500.0, 500.0]})
>>> gl = pd.DataFrame({"gl_key": ["GL-4000", "GL-1000"], "statement": ["IS", "BS"], "dk_statutory_map": ["M-REV", "M-CASH"]})
>>> ml = pd.DataFrame({"map_code": ["M-REV", "M-CASH"], "line_code": ["REV", "CASH"], "statement": ["IS", "BS"], "normal_side": ["credit", "debit"]})
>>> res = statement_from_ledger(tb, gl, ml, "LE-A", "DK", 2026, require_full_year=False, context=ctx)
>>> res.lines[["line_code", "statement", "amount"]].values.tolist()
[['CASH', 'balance_sheet', 500.0], ['REV', 'income_statement', 500.0]]
>>> res.pbt
500.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.debit`, `finance.trial_balance.credit`, `finance.trial_balance.closing_balance`, `finance.gl_account.gl_key`, `finance.gl_account.statement`, `finance.gl_account.dk_statutory_map`, `finance.gl_account.de_statutory_map`, `finance.statutory_map_line.map_code`, `finance.statutory_map_line.line_code`, `finance.statutory_map_line.normal_side`, `finance-reporting.statement_line.amount`.
