# holiday_ledger

```python
holiday_ledger(ent: pd.DataFrame, acc: pd.DataFrame) -> LedgerRows
```

Use this when you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance.

Rule: balance = carried_in_days + running sum of (accrued_days - taken_days) in period order, per person and holiday year, rounded to 2 decimals. A ledger row without an entitlement row
counts carried_in_days as 0 and is flagged missing_entitlement. negative is True when balance is below zero (bound of 1e-6 days).

## Args

ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, opening_balance.
acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days, taken_days.

## Returns

LedgerRows: an immutable sequence of LedgerRow, one per accrual row, sorted by emp_key, holiday_year, period. Fields of a row: emp_key (key), holiday_year (label), period (YYYY-MM),
accrued_days (days), taken_days (days), balance (days), opening_balance (flag: carried_in_days is the start value of the data window), missing_entitlement (flag), negative (flag),
legal_status (status of the facts). Every field carries a description and a unit (LedgerRow.columns()). result.to_frame() gives the DataFrame with these columns.

## Raises

FrameError: a frame lacks a required column, or the entitlement frame has several rows for one person and holiday year.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import holiday_ledger
>>> ent = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "carried_in_days": [1.0], "opening_balance": [False]})
>>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"],
...                     "accrued_days": [2.0, 2.0], "taken_days": [0.0, 6.0]})
>>> ledger = holiday_ledger(ent, acc)
>>> [row.balance for row in ledger], [row.negative for row in ledger]
([3.0, -1.0], [False, True])
>>> ledger.to_frame().balance.tolist()
[3.0, -1.0]
```

## Typed result

`LedgerRows`, a sequence of `LedgerRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: `hr.holiday_entitlement.emp_key`, `hr.holiday_entitlement.holiday_year`, `hr.holiday_entitlement.carried_in_days`, `hr.holiday_entitlement.carry_over_agreement`, `hr.holiday_entitlement.opening_balance`, `hr.holiday_accrual.emp_key`, `hr.holiday_accrual.holiday_year`, `hr.holiday_accrual.period`, `hr.holiday_accrual.accrued_days`, `hr.holiday_accrual.taken_days`.
