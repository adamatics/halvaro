# accrual_expected

```python
accrual_expected(employee: pd.DataFrame, leave_record: pd.DataFrame, acc: pd.DataFrame, now: dt.date, *, tolerance: float = 0.01, non_accruing_types: tuple[str, ...] = ('extended_leave',)) -> AccrualRows
```

Use this when you need the holiday accrual a person should have per month, to compare with the ledger and find months that are missing or differ.

Rule: expected_days = monthly rate of the country of the holiday year (legal fact) x employed days of the month / days of the month, rounded to 2 decimals. Employed days run from the hire
date to the leave date or `now`, whichever comes first, minus the days inside leave records of `non_accruing_types`. The result is not scaled by fte. Months that should exist (from the
start of the holiday year, the hire date or the window start, to the end of the holiday year, the leave date or `now`) and are missing in `acc` come back as rows with accrued_days null
and missing_month True. `tolerance` and `non_accruing_types` are proposed policy values. Simplification: only extended_leave is non-accruing by default; the ledger of the data accrues
during parental leave too, so pass non_accruing_types=("extended_leave", "parental") to test the rule that it does not (known-defects.md D11).

## Args

employee: Frame hr.employee with emp_key, hire_date, leave_date (null while employed).
leave_record: Frame hr.leave_record with emp_key, leave_type, start, end.
acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days.
now: Last day that counts as employed (the data date).
tolerance: Largest difference in days between stored and expected accrual that counts as within tolerance.
non_accruing_types: leave_type values whose days do not accrue.

## Returns

AccrualRows: an immutable sequence of AccrualRow sorted by emp_key, holiday_year, period. Fields of a row: emp_key, holiday_year, period (YYYY-MM), accrued_days (days, None on a missing
month), expected_days (days), missing_month (flag), difference (days, accrued minus expected, None on a missing month), within_tolerance (flag), legal_status (status of the facts).
Every field carries a description and a unit (AccrualRow.columns()). result.to_frame() gives the DataFrame.

## Raises

FrameError: a frame lacks a required column, a person of `acc` is not in `employee`, or a holiday year label matches no label format.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import fact
>>> from halvaro.hr import accrual_expected
>>> rate = fact("legal.DK.holiday.accrual_days_per_month").value
>>> employee = pd.DataFrame({"emp_key": ["EMP-1"], "hire_date": [dt.date(2020, 1, 1)], "leave_date": [None]})
>>> leave_record = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
>>> acc = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "period": ["2026-10"], "accrued_days": [rate]})
>>> out = accrual_expected(employee, leave_record, acc, dt.date(2026, 10, 31))
>>> [r.period for r in out], [r.missing_month for r in out], [r.within_tolerance for r in out]
(['2026-09', '2026-10'], [True, False], [False, True])
>>> all(r.expected_days == round(rate, 2) for r in out)
True
```

## Typed result

`AccrualRows`, a sequence of `AccrualRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.accrual_days_per_month`, `legal.DE.holiday.accrual_days_per_month`, `world.window_start`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`, `legal.DK.holiday.holiday_year_start.month`, `legal.DE.holiday.holiday_year_start.month`, `legal.DK.holiday.holiday_year_start.day`, `legal.DE.holiday.holiday_year_start.day`.

Source columns: `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.leave_record.emp_key`, `hr.leave_record.leave_type`, `hr.leave_record.start`, `hr.leave_record.end`, `hr.holiday_accrual.emp_key`, `hr.holiday_accrual.holiday_year`, `hr.holiday_accrual.period`, `hr.holiday_accrual.accrued_days`, `hr.holiday_accrual.taken_days`.
