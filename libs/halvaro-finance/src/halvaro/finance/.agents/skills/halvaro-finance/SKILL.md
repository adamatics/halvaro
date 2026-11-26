---
name: halvaro-finance
description: Use when a task needs checks or rebuilds of the finance of the Halvaro estate: a cash forecast tied to the bank, liquidity headroom, forecast accuracy, the VAT return and its coding, settlement and filing date, the corporate tax provision, the e-invoice share and gap, the month end reconciliation of subledgers, the fixed asset roll forward, the inventory valuation, the bank balance and the intercompany agreement. Fictional company, synthetic data.
---
# Finance functions of halvaro-finance (cash, VAT and tax, reconciliation)

Fictional company, synthetic data. This skill belongs to the installed version of the package and was generated from its docstrings.

## When to use

A task asks whether a forecast, a VAT return, a provision, a register or a balance agrees with the ledger or with its own rule, or asks for the rebuilt figure: cash and liquidity, VAT boxes and their coding, tax provision, e-invoice formats, subledger and bank reconciliation, fixed assets, inventory, intercompany. Do not write your own version of these checks: call the function.

## How to call

- Import from the package: `from halvaro.finance import vat_return_from_ledger, bank_reconciliation` (names in the table below).
- Every function needs `context=` a `halvaro.core.Context` (stage and role of the session). A source above the stage of the context raises `StageRefusal`.
- The library never reads data, files, credentials or the environment. Your app loads the tables (for example `finance.journal_line`) and passes them in as DataFrames.
- Legal values (VAT rates, payment and filing days, tax rates, the loss cap) are facts read with `halvaro.core.fact(id)`. Never type one. The status of the facts used is in the envelope (`status`): VERIFY means provisional.
- A policy value (a tolerance or a threshold) is a parameter with a proposed default. Name the value you used.
- Errors are `FrameError` and name the column, key or entity that is wrong. Fix the input, do not catch and ignore the error.
- Results: a function returns a DataFrame or an Envelope whose `value` is a DataFrame. For rows with a described type use the model of the result, for example `VatReturnRow.from_frame(envelope.value)`. Every field of a model has a description and a unit.

## Functions

| Function | Use this when | Returns |
|---|---|---|
| [`cash_forecast_checks`](references/cash_forecast_checks.md) | Use this when you need to check that a weekly cash forecast ties to the bank, chains from week to week and keeps its band. | `pd.DataFrame` |
| [`liquidity_headroom`](references/liquidity_headroom.md) | Use this when you need the headroom of a cash forecast to the minimum cash floor and the first week in which the low case falls below it. | `pd.DataFrame` |
| [`forecast_accuracy`](references/forecast_accuracy.md) | Use this when you need to know how well a cash forecast covered the actual closing cash, by entity and forecast horizon. | `pd.DataFrame` |
| [`vat_return_from_ledger`](references/vat_return_from_ledger.md) | Use this when you need the VAT return of each entity and month rebuilt from the VAT coded ledger lines. | `Envelope` |
| [`vat_code_check`](references/vat_code_check.md) | Use this when you need to check that the VAT codes of the ledger lines carry the right rate, sit on the right accounts and agree with the postings on the VAT accounts. | `Envelope` |
| [`vat_settlement`](references/vat_settlement.md) | Use this when you need to compare the VAT payable of each return with the VAT payment of the following month. | `Envelope` |
| [`vat_filing_calendar`](references/vat_filing_calendar.md) | Use this when you need the filing due date of each VAT return and want to compare it with the stored date. | `Envelope` |
| [`tax_provision`](references/tax_provision.md) | Use this when you need the corporate tax provision of each entity and fiscal year recomputed from its inputs and compared with the stored rows. | `Envelope` |
| [`einvoice_format_share`](references/einvoice_format_share.md) | Use this when you need the share of structured e-invoices among the third party invoices of one entity, by month. | `pd.DataFrame` |
| [`einvoice_gap`](references/einvoice_gap.md) | Use this when you need the customers of one entity that still receive pdf invoices shortly before structured invoices become mandatory. | `Envelope` |
| [`rebuild_subledger_reconciliation`](references/rebuild_subledger_reconciliation.md) | Use this when you need every subledger compared with its control account in the ledger at each month end. | `pd.DataFrame` |
| [`fixed_asset_rollforward`](references/fixed_asset_rollforward.md) | Use this when you need the monthly cost and accumulated depreciation of the fixed asset register, per entity and asset class. | `Envelope` |
| [`inventory_valuation_check`](references/inventory_valuation_check.md) | Use this when you need to check the inventory valuation for missing amounts, the allowance rule and agreement with the ledger. | `Envelope` |
| [`bank_reconciliation`](references/bank_reconciliation.md) | Use this when you need the ledger balance of every bank account rebuilt from the opening balance and the payments, compared with the stored daily balance. | `pd.DataFrame` |
| [`intercompany_agreement`](references/intercompany_agreement.md) | Use this when you need to check that the two sides of the intercompany records agree. | `Envelope` |
| [`open_items_ar`](references/open_items_ar.md) | Use this when you need the open receivables of every domestic invoice and opening item on a date. | `pd.DataFrame` |
| [`open_items_ap`](references/open_items_ap.md) | Use this when you need the open payables of every supplier invoice and opening item on a date. | `pd.DataFrame` |
| [`retention_receivable`](references/retention_receivable.md) | Use this when you need the retention held on receivables per item and in total per entity. | `pd.DataFrame` |
| [`ageing`](references/ageing.md) | Use this when you need open items grouped by party and by days past due on a date. | `pd.DataFrame` |
| [`bad_debt_candidates`](references/bad_debt_candidates.md) | Use this when you need the receivables that are overdue by at least the write-off days of the fact. | `Envelope` |
| [`customer_exposure`](references/customer_exposure.md) | Use this when you need the open receivables of each customer in DKK against the credit limit of the customer. | `pd.DataFrame` |

## Reference pages

- One page per function in `references/` (signature, rule, arguments, returns, errors, example, facts).
- `references/results.md`: the result models with the description and unit of every field.
