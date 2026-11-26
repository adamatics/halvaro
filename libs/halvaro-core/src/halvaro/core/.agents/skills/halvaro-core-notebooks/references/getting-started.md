# Getting started with halvaro-core

Shared foundation of the Halvaro Infra libraries: keys, periods, facts, stage and access guard, org, calendar, money

## First steps

- Import from the package: `from halvaro.core import combine_status, from_cents, guarded_sum`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [Money in cents, one currency per sum, one status per result](money-sums-and-status.md): How do you split an amount between cost centres without losing a cent, sum money without mixing currencies, and report one status for a result that rests on several facts?
- [From a month to its working days](month-to-working-days.md): How many working days does a month have in a region, how does that change with the region, and what does a person's leave leave of it?

## Reference pages of the functions

- `halvaro-core/references/combine_status.md`
- `halvaro-core/references/from_cents.md`
- `halvaro-core/references/guarded_sum.md`
- `halvaro-core/references/month_end.md`
- `halvaro-core/references/net_working_days.md`
- `halvaro-core/references/period_range.md`
- `halvaro-core/references/public_holidays.md`
- `halvaro-core/references/rdiv.md`
- `halvaro-core/references/to_cents.md`
- `halvaro-core/references/working_days.md`
