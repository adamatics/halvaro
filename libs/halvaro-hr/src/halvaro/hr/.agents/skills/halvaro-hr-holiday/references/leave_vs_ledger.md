# leave_vs_ledger

```python
leave_vs_ledger(leave_record: pd.DataFrame, acc: pd.DataFrame, now: dt.date, *, total_tolerance_days: float = 25.0) -> LeaveLedgerRows
```

Use this when you need to check that the holiday leave records agree with the days taken in the ledger, per person and holiday year.

Rule: holiday leave records (leave_type "holiday") that ended on or before `now` are placed in the holiday year of their end date, using the country of the person (read from the label of
the person in `acc`), and summed per person and holiday year as leave_days. taken_days is the sum of taken_days in `acc`. difference = taken_days - leave_days. total_difference_days is the
sum of all differences (the same value on every row) and within_total_tolerance is True when its size is at most `total_tolerance_days`. A record that straddles `now` is left out whole,
while the ledger counts its days up to `now`. `total_tolerance_days` is a proposed policy value.

## Args

leave_record: Frame hr.leave_record with emp_key, leave_type, days, end.
acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, taken_days.
now: Last day that counts (the data date).
total_tolerance_days: Largest size of the total difference, in days, that counts as within tolerance.

## Returns

LeaveLedgerRows: an immutable sequence of LeaveLedgerRow sorted by emp_key, holiday_year. Fields of a row: emp_key, holiday_year (None for a leave record of a person without ledger rows),
leave_days (days), taken_days (days), difference (days), total_difference_days (days), within_total_tolerance (flag), legal_status (status of the facts). Every field carries a
description and a unit (LeaveLedgerRow.columns()). result.to_frame() gives the DataFrame.

## Raises

FrameError: a frame lacks a required column, or a holiday year label in `acc` matches no label format.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import leave_vs_ledger
>>> leave_record = pd.DataFrame({"emp_key": ["EMP-1"], "leave_type": ["holiday"], "days": [3], "end": [dt.date(2026, 10, 9)]})
>>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"], "taken_days": [1.0, 2.0]})
>>> out = leave_vs_ledger(leave_record, acc, dt.date(2026, 11, 30))
>>> [r.holiday_year for r in out], [r.difference for r in out], [r.within_total_tolerance for r in out]
(['2026/27'], [0.0], [True])
```

## Typed result

`LeaveLedgerRows`, a sequence of `LeaveLedgerRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.holiday_year_start.month`, `legal.DE.holiday.holiday_year_start.month`, `legal.DK.holiday.holiday_year_start.day`, `legal.DE.holiday.holiday_year_start.day`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: `hr.leave_record.emp_key`, `hr.leave_record.leave_type`, `hr.leave_record.days`, `hr.leave_record.end`, `hr.holiday_accrual.emp_key`, `hr.holiday_accrual.holiday_year`, `hr.holiday_accrual.period`, `hr.holiday_accrual.accrued_days`, `hr.holiday_accrual.taken_days`.
