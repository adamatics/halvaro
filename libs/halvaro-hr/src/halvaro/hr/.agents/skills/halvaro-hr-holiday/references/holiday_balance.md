# holiday_balance

```python
holiday_balance(ent: pd.DataFrame, acc: pd.DataFrame, emp_key: str, holiday_year: str, as_of: dt.date) -> HolidayBalance
```

Use this when you need the holiday balance of one person in one holiday year at the end of a month.

Rule: balance_days = carried_in_days + accrued_days_ytd - taken_days_ytd. The sums run over the ledger periods of the person and holiday year up to the month of as_of, and as_of is
read as the end of its month. entitlement_days is the full-year entitlement: it is reported and never used as accrued. A person with no entitlement row and no accrual rows gets a zero
record (has_entitlement_row is False). legal_status is the combined status of the legal facts behind the country of the label.

## Args

ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, entitlement_days, carried_in_days, carry_over_agreement.
acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days, taken_days.
emp_key: Key of the person (EMP-).
holiday_year: Holiday year label, for example "2026/27".
as_of: A date. Its month is the last month counted.

## Returns

HolidayBalance, a frozen model whose fields carry a description and a unit (HolidayBalance.columns()): emp_key, holiday_year, as_of (ISO text), entitlement_days, carried_in_days,
carry_over_agreement, accrued_days_ytd, taken_days_ytd, balance_days (all in days, rounded to 2 decimals), has_entitlement_row and legal_status. result.to_dict() gives the fields as a dict.

## Raises

FrameError: a frame lacks a required column, the person has more than one entitlement row for the year, the person has accrual rows but no entitlement row, or the label matches no
    label format.
UserWarning: (a warning, not an error) as_of is after the last ledger period, so the balance is frozen at that month.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import fact
>>> from halvaro.hr import holiday_balance
>>> rate = fact("legal.DK.holiday.accrual_days_per_month").value
>>> ent = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "entitlement_days": [fact("legal.DK.holiday.annual_days").value],
...                     "carried_in_days": [3.0], "carry_over_agreement": [False]})
>>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"],
...                     "accrued_days": [rate, rate], "taken_days": [0.0, 1.0]})
>>> b = holiday_balance(ent, acc, "EMP-1", "2026/27", dt.date(2026, 10, 15))
>>> b.balance_days == round(3.0 + 2 * rate - 1.0, 2)
True
```

## Typed result

`HolidayBalance`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.annual_days`, `legal.DE.holiday.annual_days`, `legal.DK.holiday.accrual_days_per_month`, `legal.DE.holiday.accrual_days_per_month`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: `hr.holiday_entitlement.emp_key`, `hr.holiday_entitlement.holiday_year`, `hr.holiday_entitlement.carried_in_days`, `hr.holiday_entitlement.carry_over_agreement`, `hr.holiday_entitlement.opening_balance`, `hr.holiday_accrual.emp_key`, `hr.holiday_accrual.holiday_year`, `hr.holiday_accrual.period`, `hr.holiday_accrual.accrued_days`, `hr.holiday_accrual.taken_days`, `hr.holiday_entitlement.entitlement_days`.
