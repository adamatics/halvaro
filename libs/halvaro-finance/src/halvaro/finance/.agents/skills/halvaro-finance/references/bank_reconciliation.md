# bank_reconciliation

```python
bank_reconciliation(bank_balance: pd.DataFrame, payment: pd.DataFrame, bank_account: pd.DataFrame, opening_balance_item: pd.DataFrame, *, context: Context) -> pd.DataFrame
```

Use this when you need the ledger balance of every bank account rebuilt from the opening balance and the payments, compared with the stored daily balance.

Rule: computed_balance on a date = the opening balance of the ledger account of the bank account + the signed payments of the account up to and including that date (incoming positive,
outgoing negative). difference = computed less the stored closing balance, to the cent. Dates without a payment carry the balance of the date before.

## Args

bank_balance: Frame finance.bank_balance with le_key, bank_account, balance_date, closing_balance and currency, one row per account and date.
payment: Frame finance.payment with bank_account, payment_date, direction (incoming or outgoing) and amount.
bank_account: Frame finance.bank_account with le_key, bank_account and gl_key, one row per account.
opening_balance_item: Frame finance.opening_balance_item with le_key, gl_key and amount (the opening balance of the ledger accounts).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with le_key, bank_account, balance_date, computed_balance, closing_balance, difference (currency units to the cent) and currency; empty when there are no bank accounts.
Typed form: BankReconRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a column is missing, a payment direction is neither incoming nor outgoing, or a date cannot be read.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import bank_reconciliation
>>> ctx = Context(stage="month3", role="analyst")
>>> bb = pd.DataFrame({"le_key": "LE-01", "bank_account": "BA-1", "balance_date": ["2025-01-02", "2025-01-03"], "closing_balance": [1100.0, 1000.0], "currency": "DKK"})
>>> pay = pd.DataFrame({"bank_account": ["BA-1", "BA-1"], "payment_date": ["2025-01-02", "2025-01-03"], "direction": ["incoming", "outgoing"], "amount": [100.0, 100.0]})
>>> ba = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["BA-1"], "gl_key": ["GL-1200"]})
>>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1200"], "amount": [1000.0]})
>>> bank_reconciliation(bb, pay, ba, ob, context=ctx)[["computed_balance", "difference"]].values.tolist()
[[1100.0, 0.0], [1000.0, 0.0]]
```

## Typed result

`BankReconRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.bank_balance.bank_account`, `finance.bank_balance.balance_date`, `finance.bank_balance.closing_balance`, `finance.payment.bank_account`, `finance.payment.payment_date`, `finance.payment.direction`, `finance.payment.amount`, `finance.bank_account.gl_key`, `finance.opening_balance_item.amount`.
