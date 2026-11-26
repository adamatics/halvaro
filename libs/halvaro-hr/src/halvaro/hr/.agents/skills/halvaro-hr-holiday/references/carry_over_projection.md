# carry_over_projection

```python
carry_over_projection(ledger: LedgerRows | pd.DataFrame, ent: pd.DataFrame, *, tolerance: float = 0.05) -> CarryOverProjectionRows
```

Use this when you need the carry-in that the next holiday year should start with, and whether the carry-in stored for it agrees.

Rule: projected_carry_in = min(max(year_end_balance, 0), cap). year_end_balance is the balance of the last ledger period of the person and holiday year (the frame of holiday_ledger).
cap is the cap of the closing year: the agreement cap for a DK person whose carry_over_agreement flag is set in that year, otherwise the default cap; a closing year without an entitlement
row has the default. stored_carry_in is carried_in_days of the next holiday year (null when that year has no row). difference = projected_carry_in - stored_carry_in. matches is True when
the difference is within `tolerance` days (null without a stored value). The tolerance of 0.05 days is a proposed policy value.

## Args

ledger: The result of holiday_ledger (LedgerRows), or a frame with emp_key, holiday_year, period, balance (for example its to_frame()).
ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement.
tolerance: Largest difference in days that still counts as a match. A number of zero or more, not a bool.

## Returns

CarryOverProjectionRows: an immutable sequence of CarryOverProjectionRow, one per person and closing holiday year, sorted by emp_key and holiday_year. Fields of a row: emp_key,
holiday_year, year_end_balance (days), country, next_holiday_year, basis, cap (days), projected_carry_in (days), stored_carry_in (days, None without a next year), difference (days, None
without a stored value), matches (flag, None without a stored value), legal_status (status of the facts). Every field carries a description and a unit
(CarryOverProjectionRow.columns()). result.to_frame() gives the DataFrame.

## Raises

FrameError: a frame lacks a required column, the entitlement frame has several rows for one person and holiday year, tolerance is not a number of zero or more, or a holiday year
    label matches no label format.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import fact
>>> from halvaro.hr import carry_over_projection, holiday_ledger
>>> cap = fact("legal.DK.holiday.carryover.default_max_days").value
>>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2027/28"], "carried_in_days": [0.0, cap],
...                     "carry_over_agreement": [False, False], "opening_balance": [False, False]})
>>> acc = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "period": ["2027-08"], "accrued_days": [cap + 3.0], "taken_days": [0.0]})
>>> projection = carry_over_projection(holiday_ledger(ent, acc), ent)
>>> projection[0].projected_carry_in == cap, projection[0].matches
(True, True)
```

## Typed result

`CarryOverProjectionRows`, a sequence of `CarryOverProjectionRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.carryover.default_max_days`, `legal.DE.holiday.carryover.default_max_days`, `legal.DK.holiday.carryover.agreement_max_days`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: `hr.holiday_entitlement.emp_key`, `hr.holiday_entitlement.holiday_year`, `hr.holiday_entitlement.carried_in_days`, `hr.holiday_entitlement.carry_over_agreement`, `hr.holiday_entitlement.opening_balance`, `hr.holiday_accrual.emp_key`, `hr.holiday_accrual.holiday_year`, `hr.holiday_accrual.period`, `hr.holiday_accrual.accrued_days`, `hr.holiday_accrual.taken_days`.
