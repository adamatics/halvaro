# Holiday balance and accrual end to end

Notebook `notebooks/holiday-balance-and-accrual.ipynb` of halvaro-hr, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** What is the holiday balance of one person at the end of a month, and does the accrual in the ledger match what the rule says it should be?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `holiday_ledger` | you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance. | [holiday_ledger](../../halvaro-hr-holiday/references/holiday_ledger.md) |
| `holiday_balance` | you need the holiday balance of one person in one holiday year at the end of a month. | [holiday_balance](../../halvaro-hr-holiday/references/holiday_balance.md) |
| `accrual_expected` | you need the holiday accrual a person should have per month, to compare with the ledger and find months that are missing or differ. | [accrual_expected](../../halvaro-hr-holiday/references/accrual_expected.md) |

## Steps

A holiday balance is carried-in days plus accrued days minus taken days. The ledger shows it month by month, the balance reads it at a date, and the accrual check compares the stored accrual with the rule. The notebook uses `holiday_ledger`, `holiday_balance` and `accrual_expected` of halvaro-hr and the function `fact` of halvaro-core. It builds its own small frames, so it needs no data.

```python
import datetime as dt

import pandas as pd

from halvaro.core import fact
from halvaro.hr import accrual_expected, holiday_balance, holiday_ledger

rate = fact("legal.DK.holiday.accrual_days_per_month")
rate
```

Step 1. The accrual rate is a registered fact, never a number typed in the notebook. Its status says whether the value is verified: VERIFY means provisional.

```python
ent = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "entitlement_days": [fact("legal.DK.holiday.annual_days").value],
                    "carried_in_days": [3.0], "carry_over_agreement": [False], "opening_balance": [False]})
acc = pd.DataFrame({"emp_key": ["EMP-1"] * 2, "holiday_year": ["2026/27"] * 2, "period": ["2026-09", "2026-10"],
                    "accrued_days": [rate.value] * 2, "taken_days": [0.0, 1.0]})
employee = pd.DataFrame({"emp_key": ["EMP-1"], "hire_date": [dt.date(2020, 1, 1)], "leave_date": [None]})
leave_record = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
acc
```

Step 2. The ledger gives the balance after each month. A balance below zero is flagged.

```python
ledger = holiday_ledger(ent, acc)
ledger.to_frame()[["period", "accrued_days", "taken_days", "balance", "negative"]]
```

Step 3. The balance at a date reads the same data. The date counts to the end of its month.

```python
balance = holiday_balance(ent, acc, "EMP-1", "2026/27", dt.date(2026, 10, 15))
balance.to_dict()
```

Step 4. The accrual check computes what each month should have accrued and compares it with the stored value.

```python
now = dt.date(2026, 10, 31)
expected = accrual_expected(employee, leave_record, acc, now)
expected.to_frame()[["period", "accrued_days", "expected_days", "difference", "within_tolerance"]]
```

Step 5. Take a month out of the ledger. The check lists it as missing instead of passing silently.

```python
missing = accrual_expected(employee, leave_record, acc.iloc[:1], now)
missing.to_frame()[["period", "accrued_days", "missing_month", "within_tolerance"]]
```

Check. The balance equals carried-in plus accrued minus taken, computed here with pandas and not with the library. The last ledger row agrees with the balance, every month is within tolerance, and the second month is the missing one.

```python
by_hand = ent["carried_in_days"].iloc[0] + acc["accrued_days"].sum() - acc["taken_days"].sum()
assert round(by_hand, 2) == balance.balance_days
assert ledger[-1].balance == balance.balance_days
assert all(row.within_tolerance for row in expected)
assert [row.missing_month for row in missing] == [False, True]
assert balance.legal_status == rate.status
```
