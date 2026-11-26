# Result models

Frozen dataclasses for the results of the holiday functions. `holiday_balance` returns a `HolidayBalance`; every other function with a table as result returns a container, an immutable sequence of the row model below (`result[0]`, `for row in result`, `len(result)`) with `result.to_frame()` for the DataFrame. `Model.columns()` lists the fields.

## HolidayBalance (result of `holiday_balance`, returned as is)

Result of `holiday_balance`: the balance of one person and holiday year at the end of a month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the holiday year the balance belongs to. |
| `as_of` | `str` | date | Date asked for, as ISO text. Its month is the last month counted. |
| `entitlement_days` | `float` | days | Full-year entitlement of the person in this holiday year; 0 without an entitlement row. Reported, not part of the balance. |
| `carried_in_days` | `float` | days | Days carried into the holiday year; 0 without an entitlement row. |
| `carry_over_agreement` | `bool` | flag | True when the person has a carry-over agreement in this holiday year. |
| `accrued_days_ytd` | `float` | days | Days accrued from the start of the holiday year to the month of as_of. |
| `taken_days_ytd` | `float` | days | Days taken from the start of the holiday year to the month of as_of. |
| `balance_days` | `float` | days | carried_in_days plus accrued_days_ytd minus taken_days_ytd, rounded to 2 decimals. |
| `has_entitlement_row` | `bool` | flag | True when an entitlement row exists for the person and holiday year. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## LedgerRow (result of `holiday_ledger`, returned as `LedgerRows`)

One row of the frame of `holiday_ledger`: the running balance of a person and holiday year after one month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the holiday year. |
| `period` | `str` | month | Month of the row as YYYY-MM. |
| `accrued_days` | `float` | days | Days accrued in the month. |
| `taken_days` | `float` | days | Days taken in the month. |
| `balance` | `float` | days | carried_in_days plus the running sum of accrued_days minus taken_days up to and including this month, rounded to 2 decimals. |
| `opening_balance` | `bool` | flag | True when carried_in_days of the year is the start value of the data window, not a carry-over. |
| `missing_entitlement` | `bool` | flag | True when the person has no entitlement row for the holiday year; carried_in_days then counts as 0. |
| `negative` | `bool` | flag | True when balance is below zero. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## CarryOverRow (result of `carry_over_position`, returned as `CarryOverRows`)

One row of the frame of `carry_over_position`: the days carried into a holiday year against the cap of their basis.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the holiday year the days were carried into. |
| `carried_in_days` | `float` | days | Days carried into the holiday year. |
| `carry_over_agreement` | `bool` | flag | True when the person has a carry-over agreement in this holiday year. |
| `opening_balance` | `bool` | flag | True when carried_in_days is the start value of the data window, not a carry-over. |
| `country` | `str` | text | Country whose holiday year label the row has: DK or DE. |
| `basis` | `str` | text | Basis of the cap: agreement or default. |
| `cap` | `float | None` | days | Most days the basis lets the person carry in; None on an opening row. |
| `headroom` | `float | None` | days | cap minus carried_in_days; negative when the carry-in is above the cap; None on an opening row. |
| `at_cap` | `bool` | flag | True when headroom is zero; always False on an opening row. |
| `deadline` | `dt.date | None` | date | Date by which the carried-in days are to be used (DE rows); None for DK rows. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## CarryOverProjectionRow (result of `carry_over_projection`, returned as `CarryOverProjectionRows`)

One row of the frame of `carry_over_projection`: the carry-in the next holiday year should start with, against the stored one.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the closing holiday year. |
| `year_end_balance` | `float` | days | Balance of the last ledger period of the closing holiday year. |
| `country` | `str` | text | Country whose holiday year label the row has: DK or DE. |
| `next_holiday_year` | `str` | label | Label of the holiday year that follows. |
| `basis` | `str` | text | Basis of the cap: agreement or default. |
| `cap` | `float` | days | Most days the basis lets the person carry in. |
| `projected_carry_in` | `float` | days | year_end_balance limited to zero at the bottom and to cap at the top, rounded to 2 decimals. |
| `stored_carry_in` | `float | None` | days | carried_in_days of the next holiday year; None when the next year has no row. |
| `difference` | `float | None` | days | projected_carry_in minus stored_carry_in; None without a stored value. |
| `matches` | `bool | None` | flag | True when the size of difference is within the tolerance; None without a stored value. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## AccrualRow (result of `accrual_expected`, returned as `AccrualRows`)

One row of the frame of `accrual_expected`: stored and expected accrual of a person in a month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the holiday year. |
| `period` | `str` | month | Month of the row as YYYY-MM. |
| `accrued_days` | `float | None` | days | Days accrued in the month as stored; None on a month that is missing in the ledger. |
| `expected_days` | `float` | days | Monthly rate times the employed share of the month minus days of non-accruing leave, rounded to 2 decimals. |
| `missing_month` | `bool` | flag | True when the month should exist and is missing in the ledger. |
| `difference` | `float | None` | days | accrued_days minus expected_days; None on a missing month. |
| `within_tolerance` | `bool` | flag | True when the size of difference is within the tolerance; False on a missing month. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## LeaveLedgerRow (result of `leave_vs_ledger`, returned as `LeaveLedgerRows`)

One row of the frame of `leave_vs_ledger`: holiday leave days against taken days of a person and holiday year.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str | None` | label | Label of the holiday year; None for a leave record of a person without ledger rows. |
| `leave_days` | `float` | days | Days of the holiday leave records that ended by the data date and lie in this holiday year. |
| `taken_days` | `float` | days | Sum of taken_days of the ledger in this holiday year. |
| `difference` | `float` | days | taken_days minus leave_days, rounded to 2 decimals. |
| `total_difference_days` | `float` | days | Sum of difference over all rows; the same value on every row. |
| `within_total_tolerance` | `bool` | flag | True when the size of total_difference_days is within the tolerance. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |

## HighCarryOverRow (result of `high_carry_over`, returned as `HighCarryOverRows`)

One row of the frame of `high_carry_over`: a person whose carry-in is above the threshold.

| Field | Type | Unit | Description |
|---|---|---|---|
| `emp_key` | `str` | key | Key of the person (EMP-). |
| `holiday_year` | `str` | label | Label of the holiday year the days were carried into. |
| `carried_in_days` | `float` | days | Days carried into the holiday year. |
| `carry_over_agreement` | `bool` | flag | True when the person has a carry-over agreement in this holiday year. |
| `legal_status` | `str` | status | Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed). |
