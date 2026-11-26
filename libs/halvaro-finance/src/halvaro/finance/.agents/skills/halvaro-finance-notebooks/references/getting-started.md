# Getting started with halvaro-finance

Finance library of the Halvaro Infra estate: ledger, subledgers, project view, exposure, payroll tie-out, statements (0.1: ledger)

## First steps

- Import from the package: `from halvaro.finance import bank_reconciliation, cash_forecast_checks, cost_centre_team_map`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [A cash forecast against the bank and the floor](cash-forecast-and-floor.md): Does a weekly cash forecast tie to the bank and chain from week to week, and in which week does its low case fall below the minimum cash floor?
- [Payroll tie-out: the pay HR implies against the pay the ledger booked](payroll-tie-out.md): Does the gross pay in the ledger equal the gross pay that the employment terms of HR imply, per cost centre and month, and what do the employer pension and social contributions come to on that pay?
- [From VAT in the ledger to the payment in the bank](vat-payment-and-bank.md): Is the VAT of a month, as the ledger lines say it, the VAT that was paid the month after, and does the bank balance after the payment agree with the payments?

## Reference pages of the functions

- `halvaro-finance-reference/references/cost_centre_team_map.md`
- `halvaro-finance-reference/references/employer_oncosts.md`
- `halvaro-finance-reference/references/ledger_gross_pay.md`
- `halvaro-finance-reference/references/tie_out.md`
- `halvaro-finance/references/bank_reconciliation.md`
- `halvaro-finance/references/cash_forecast_checks.md`
- `halvaro-finance/references/liquidity_headroom.md`
- `halvaro-finance/references/vat_return_from_ledger.md`
- `halvaro-finance/references/vat_settlement.md`
