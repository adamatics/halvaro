# Getting started with halvaro-hr

HR library of the Halvaro Infra estate: organisation, holiday, pay, crosswalk, staffing and certificates (0.1: organisation)

## First steps

- Import from the package: `from halvaro.hr import accrual_expected, carry_over_position, carry_over_projection`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [Holiday balance and accrual end to end](holiday-balance-and-accrual.md): What is the holiday balance of one person at the end of a month, and does the accrual in the ledger match what the rule says it should be?
- [Holiday carry-over into the next year](holiday-carry-over.md): How many holiday days should a person carry into the next holiday year, does the carry-in stored for the next year agree, and how far is it from the cap?
- [The HR API and the libraries in one app](hr-api-client.md): How does an app use the HR API and the libraries together: read the leave records of a person from the API, count the leave days inside one month with the calendar of halvaro-core, and read the holiday balance that the API computed as a typed model of halvaro-hr?
- [Who has holiday left, who carries a lot, and do the records agree?](who-has-holiday-left.md): As HR, which people are in the red on their holiday balance, who carries many days into the new holiday year, and do the leave records match the days that the ledger says were taken?

## Reference pages of the functions

- `halvaro-hr-holiday/references/accrual_expected.md`
- `halvaro-hr-holiday/references/carry_over_position.md`
- `halvaro-hr-holiday/references/carry_over_projection.md`
- `halvaro-hr-holiday/references/high_carry_over.md`
- `halvaro-hr-holiday/references/holiday_balance.md`
- `halvaro-hr-holiday/references/holiday_ledger.md`
- `halvaro-hr-holiday/references/holiday_year_label.md`
- `halvaro-hr-holiday/references/leave_vs_ledger.md`
