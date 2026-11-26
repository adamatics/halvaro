---
name: halvaro-hr-holiday
description: Use when a task needs a holiday balance, a month by month holiday ledger, a carry-over position or projection, the expected holiday accrual of a month, a check of holiday leave records against the ledger, or a list of high carry-over. Calls the nine holiday functions of the halvaro-hr library. Check these functions before you write your own version.
---
# Holiday functions of halvaro-hr

Fictional company, synthetic data. This skill belongs to the installed version of the package and was generated from its docstrings.

## When to use

A task asks for the holiday balance of a person, the running ledger of a holiday year, how many days were carried into a year and against which cap, what a month of accrual should be, whether leave records and the ledger agree, or which people carry in many days. Look here first. If the function you need is not in the table, say so and ask for it to be added; do not write a private copy of the rule.

## How to call

- Import from the package: `from halvaro.hr import holiday_balance, holiday_ledger` (names in the table below).
- The library never reads data, files, credentials or the environment. Your app loads the tables (`hr.holiday_entitlement`, `hr.holiday_accrual`, `hr.employee`, `hr.leave_record`) and passes them in as DataFrames with the source column names.
- Legal values (accrual rate, caps, start of the holiday year) are facts read with `halvaro.core.fact(id)`. Never type one. Every result carries `legal_status`: VERIFY means the value is provisional and not verified, and you say so when you report a number that depends on it.
- A policy value (a tolerance or a threshold) is a parameter with a proposed default. Name the value you used.
- Errors are `FrameError` and name the column, key or label that is wrong. Fix the input, do not catch and ignore the error.
- Typed results (from halvaro-hr 1.0): `holiday_balance` returns one `HolidayBalance`; the six functions with a table as result return an immutable sequence of row models (`LedgerRows`, `CarryOverRows`, `CarryOverProjectionRows`, `AccrualRows`, `LeaveLedgerRows`, `HighCarryOverRows`) that you read like a tuple. Use `result.to_frame()` when you need a DataFrame and `result.to_dict()` (`HolidayBalance`) for a dict. Every field of a model has a description and a unit (`LedgerRow.columns()`).

## Functions

| Function | Use this when | Returns |
|---|---|---|
| [`holiday_year_label`](references/holiday_year_label.md) | Use this when you need the label of the holiday year that contains a date, for DK or DE. | `str` |
| [`holiday_year_bounds`](references/holiday_year_bounds.md) | Use this when you have the label of a holiday year and need its first and last day. | `tuple[dt.date, dt.date]` |
| [`holiday_balance`](references/holiday_balance.md) | Use this when you need the holiday balance of one person in one holiday year at the end of a month. | `HolidayBalance` |
| [`holiday_ledger`](references/holiday_ledger.md) | Use this when you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance. | `LedgerRows` |
| [`carry_over_position`](references/carry_over_position.md) | Use this when you need to compare the days carried into each holiday year with the cap that applies to the person, and see the headroom that is left. | `CarryOverRows` |
| [`carry_over_projection`](references/carry_over_projection.md) | Use this when you need the carry-in that the next holiday year should start with, and whether the carry-in stored for it agrees. | `CarryOverProjectionRows` |
| [`accrual_expected`](references/accrual_expected.md) | Use this when you need the holiday accrual a person should have per month, to compare with the ledger and find months that are missing or differ. | `AccrualRows` |
| [`leave_vs_ledger`](references/leave_vs_ledger.md) | Use this when you need to check that the holiday leave records agree with the days taken in the ledger, per person and holiday year. | `LeaveLedgerRows` |
| [`high_carry_over`](references/high_carry_over.md) | Use this when you need the people who carry more holiday days into a holiday year than a threshold, so that a person can look at each of them. | `HighCarryOverRows` |

## Reference pages

- One page per function in `references/` (signature, rule, arguments, returns, errors, example, facts).
- `references/results.md`: the result models with the description and unit of every field.
