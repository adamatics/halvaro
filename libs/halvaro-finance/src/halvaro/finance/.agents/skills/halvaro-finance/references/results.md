# Result models

Frozen dataclasses for the rows of the results of the finance functions. Build them with `Model.from_frame(frame)` (the frame of the result, or `envelope.value`); `Model.columns()` lists the fields.

## ViolationRow (result of `cash_forecast_checks`)

One violation listed by `cash_forecast_checks`, `vat_code_check`, `inventory_valuation_check` or `intercompany_agreement`.

| Field | Type | Unit | Description |
|---|---|---|---|
| `table` | `str` | text | Table the violation is in, for example finance.journal_line. |
| `key` | `str` | key | Key of the row or group the violation is about, for example an entity and a month. |
| `rule` | `str` | label | Name of the rule that is broken, for example rate_mismatch. |
| `detail` | `str` | text | What was found, in one sentence with the figures. |

## HeadroomRow (result of `liquidity_headroom`)

One row of `liquidity_headroom`: the headroom of one forecast to the minimum cash floor.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `forecast_date` | `str` | date | Date the forecast was made. |
| `weeks` | `int` | count | Number of forecast weeks. |
| `first_breach_week` | `float` | count | First week in which the 10th percentile closing cash is below the floor; empty when no week is. |
| `lowest_headroom_p10` | `float` | currency | Lowest value of the 10th percentile closing cash less the floor. |
| `lowest_headroom_week` | `int` | count | Week of the lowest headroom. |
| `rcf_available_at_lowest` | `float` | currency | Facility limit less drawn in the week of the lowest headroom. |
| `breach_weeks` | `int` | count | Number of weeks in which the 10th percentile closing cash is below the floor. |
| `agrees` | `bool` | flag | True when the recomputed headroom, facility and breach flag equal the stored columns within the tolerance. |

## AccuracyRow (result of `forecast_accuracy`)

One row of `forecast_accuracy`: band coverage and error of a forecast horizon.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `n` | `int` | count | Number of forecast weeks that have an actual closing cash. |
| `coverage` | `float` | share | Share of those weeks whose actual is inside the 10th to 90th percentile band, between 0 and 1. |
| `mean_abs_error` | `float` | currency | Mean absolute error of the closing cash. |
| `median_abs_error` | `float` | currency | Median absolute error of the closing cash. |
| `mean_error` | `float` | currency | Mean of actual less forecast closing cash; positive when the forecast was too low. |
| `week_no` | `int` | count | Forecast horizon in weeks; 0 is all horizons of the entity. It is the last column of a frame with rows and the second column of the empty frame. |

## VatReturnRow (result of `vat_return_from_ledger`)

One row of `vat_return_from_ledger`: the VAT return of an entity and month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `period` | `str` | month | Month of the return as YYYY-MM. |
| `currency` | `str` | label | Currency of the entity; all amounts of the row are in it. |
| `output_vat_domestic` | `float` | currency | Output VAT on domestic sales. |
| `output_vat_acquisition_eu` | `float` | currency | Output VAT on acquisitions from the EU (reverse charge). |
| `output_vat_acquisition_non_eu` | `float` | currency | Output VAT on acquisitions from outside the EU (reverse charge). |
| `input_vat_domestic` | `float` | currency | Input VAT on domestic purchases. |
| `input_vat_acquisition_eu` | `float` | currency | Input VAT on acquisitions from the EU. |
| `input_vat_acquisition_non_eu` | `float` | currency | Input VAT on acquisitions from outside the EU. |
| `input_vat_import` | `float` | currency | Input VAT on imports. |
| `total_output_vat` | `float` | currency | Sum of the output boxes. |
| `total_input_vat` | `float` | currency | Sum of the input boxes. |
| `vat_payable` | `float` | currency | total_output_vat less total_input_vat; negative is a refund. |
| `taxable_base_domestic_sales` | `float` | currency | Taxable base of the domestic sales. |
| `taxable_base_acquisitions_eu` | `float` | currency | Taxable base of the acquisitions from the EU. |
| `taxable_base_acquisitions_non_eu` | `float` | currency | Taxable base of the acquisitions from outside the EU. |
| `taxable_base_domestic_purchases` | `float` | currency | Taxable base of the domestic purchases. |

## ViolationRow (result of `vat_code_check`)

One violation listed by `cash_forecast_checks`, `vat_code_check`, `inventory_valuation_check` or `intercompany_agreement`.

| Field | Type | Unit | Description |
|---|---|---|---|
| `table` | `str` | text | Table the violation is in, for example finance.journal_line. |
| `key` | `str` | key | Key of the row or group the violation is about, for example an entity and a month. |
| `rule` | `str` | label | Name of the rule that is broken, for example rate_mismatch. |
| `detail` | `str` | text | What was found, in one sentence with the figures. |

## VatSettlementRow (result of `vat_settlement`)

One row of `vat_settlement`: a return against the payment of the following month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `period` | `str` | month | Month of the return as YYYY-MM. |
| `vat_payable` | `float` | currency | VAT payable of the return. |
| `payment_month` | `str` | month | Month the payment is looked for in, the month after the period. |
| `paid_signed` | `float` | currency | Signed VAT payment of the payment month: outgoing positive, incoming negative; empty without a payment. |
| `paid_date` | `str` | date | Day of the payment; empty without a payment. |
| `settlement_difference` | `float` | currency | vat_payable less the signed payment; empty without a payment. |
| `stored_difference` | `float` | currency | The settlement difference stored with the return. |
| `agrees` | `bool` | flag | True when the recomputed and the stored difference agree within the tolerance; empty without a payment. |
| `day_agrees` | `bool` | flag | True when the payment is on the day of the fact or the next working day; empty without a payment. |

## FilingDateRow (result of `vat_filing_calendar`)

One row of `vat_filing_calendar`: the due date of a return.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `period` | `str` | month | Month of the return as YYYY-MM. |
| `due_date` | `str` | date | Filing due date by the rule of the function. |
| `stored_due_date` | `str` | date | The due date stored with the return; empty when none is stored. |
| `agrees` | `bool` | flag | True when the stored date equals the due date of the rule. |

## TaxProvisionRow (result of `tax_provision`)

One row of `tax_provision`: the recomputed corporate tax of an entity and fiscal year.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `fiscal_year` | `int` | label | Fiscal year of the provision. |
| `tax_rate` | `float` | share | Tax rate of the row, a share. |
| `profit_before_tax` | `float` | currency | Profit before tax, as stored. |
| `taxable_income_before_losses` | `float` | currency | Profit before tax plus non deductible expenses less exempt income less the temporary difference movement. |
| `tax_loss_utilised` | `float` | currency | Loss carried in that is used against the income of the year. |
| `tax_loss_added` | `float` | currency | Loss of the year that is added to the loss carried forward. |
| `tax_loss_carried_forward` | `float` | currency | Loss carried forward at the end of the year. |
| `taxable_income` | `float` | currency | Taxable income before losses less the loss utilised. |
| `current_tax` | `float` | currency | Rate times taxable income. |
| `deferred_tax_movement` | `float` | currency | Deferred tax movement, as stored. |
| `total_tax_expense` | `float` | currency | Current tax plus the deferred tax movement. |
| `rate_is_the_fact` | `bool` | flag | True when the rate of the row equals the fact of the country of the entity. |
| `agrees` | `bool` | flag | True when every recomputed figure equals the stored one within the tolerance and the rate is the fact. |

## EinvoiceShareRow (result of `einvoice_format_share`)

One row of `einvoice_format_share`: the structured share of the invoices of one month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `period` | `str` | month | Month of the invoices as YYYY-MM. |
| `n_invoices` | `int` | count | Number of third party invoices counted. |
| `n_structured` | `int` | count | Number of those invoices in a structured format. |
| `share` | `float` | share | n_structured divided by n_invoices, four decimals, between 0 and 1. |

## EinvoiceGapRow (result of `einvoice_gap`)

One row of `einvoice_gap`: a customer that still receives pdf invoices.

| Field | Type | Unit | Description |
|---|---|---|---|
| `cus_key` | `str` | key | Key of the customer. |
| `n_pdf` | `int` | count | Number of pdf invoices in the window. |
| `n_invoices` | `int` | count | Number of invoices in the window. |
| `last_invoice_date` | `str` | date | Date of the last invoice in the window. |
| `last_format` | `str` | label | Invoice format of the last invoice. |
| `days_to_mandatory` | `int` | days | Days from as_of to the mandatory date of structured invoices; negative after it. |

## SubledgerReconciliationRow (result of `rebuild_subledger_reconciliation`)

One row of `rebuild_subledger_reconciliation`: a subledger against its control account at a month end.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `period` | `str` | month | Month end as YYYY-MM. |
| `subledger` | `str` | label | Name of the subledger, for example receivables. |
| `detail` | `str` | label | Part of the subledger, for example an asset class or a bank account; empty for the whole subledger. |
| `gl_key` | `str` | key | Control account in the ledger. |
| `subledger_balance` | `float` | currency | Balance rebuilt from the subledger. |
| `ledger_balance` | `float` | currency | Closing balance of the control account in the trial balance. |
| `difference` | `float` | currency | subledger_balance less ledger_balance. |
| `currency` | `str` | label | Currency of the entity. |
| `reconciled` | `bool` | flag | True when the difference is zero to the cent. |

## AssetScheduleRow (result of `fixed_asset_rollforward`)

One row of `fixed_asset_rollforward`: cost and accumulated depreciation of an asset class and month.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `asset_class` | `str` | label | Asset class of the register. |
| `period` | `str` | month | Month as YYYY-MM. |
| `cost_opening` | `float` | currency | Cost at the start of the month. |
| `additions` | `float` | currency | Cost of the assets acquired in the month. |
| `disposals_cost` | `float` | currency | Cost of the assets disposed of in the month. |
| `cost_closing` | `float` | currency | Cost at the end of the month. |
| `accumulated_opening` | `float` | currency | Accumulated depreciation at the start of the month. |
| `depreciation` | `float` | currency | Depreciation of the month. |
| `disposals_accumulated` | `float` | currency | Accumulated depreciation of the assets disposed of in the month. |
| `accumulated_closing` | `float` | currency | Accumulated depreciation at the end of the month. |
| `net_book_value` | `float` | currency | cost_closing less accumulated_closing. |
| `currency` | `str` | label | Currency of the entity. |

## ViolationRow (result of `inventory_valuation_check`)

One violation listed by `cash_forecast_checks`, `vat_code_check`, `inventory_valuation_check` or `intercompany_agreement`.

| Field | Type | Unit | Description |
|---|---|---|---|
| `table` | `str` | text | Table the violation is in, for example finance.journal_line. |
| `key` | `str` | key | Key of the row or group the violation is about, for example an entity and a month. |
| `rule` | `str` | label | Name of the rule that is broken, for example rate_mismatch. |
| `detail` | `str` | text | What was found, in one sentence with the figures. |

## BankReconRow (result of `bank_reconciliation`)

One row of `bank_reconciliation`: the computed balance of a bank account on a date against the stored balance.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `bank_account` | `str` | key | Key of the bank account. |
| `balance_date` | `str` | date | Date of the stored balance. |
| `computed_balance` | `float` | currency | Opening balance of the ledger account plus the signed payments up to the date. |
| `closing_balance` | `float` | currency | The stored closing balance of the date. |
| `difference` | `float` | currency | computed_balance less closing_balance, to the cent. |
| `currency` | `str` | label | Currency of the bank account. |

## ViolationRow (result of `intercompany_agreement`)

One violation listed by `cash_forecast_checks`, `vat_code_check`, `inventory_valuation_check` or `intercompany_agreement`.

| Field | Type | Unit | Description |
|---|---|---|---|
| `table` | `str` | text | Table the violation is in, for example finance.journal_line. |
| `key` | `str` | key | Key of the row or group the violation is about, for example an entity and a month. |
| `rule` | `str` | label | Name of the rule that is broken, for example rate_mismatch. |
| `detail` | `str` | text | What was found, in one sentence with the figures. |

## OpenItemArRow (result of `open_items_ar`)

One row of `open_items_ar`: an open receivable, an invoice or an opening item, on a date.

| Field | Type | Unit | Description |
|---|---|---|---|
| `item_key` | `str` | key | Key of the invoice or the opening item. |
| `source` | `str` | label | invoice or opening. |
| `le_key` | `str` | key | Key of the legal entity. |
| `cus_key` | `str` | key | Key of the customer; empty for an opening item without a customer. |
| `inv_key` | `str` | key | Key of the invoice; empty for an opening item. |
| `document_date` | `str` | date | Date of the invoice or the opening item. |
| `due_date` | `str` | date | Due date; empty when none is stored. |
| `currency` | `str` | label | Currency of the entity; all amounts of the row are in it. |
| `invoice_amount` | `float` | currency | Amount including retention, a credit note negative. |
| `paid` | `float` | currency | Payments allocated up to and including the date. |
| `written_off` | `float` | currency | Amount written off up to the date. |
| `open_amount` | `float` | currency | invoice_amount less paid less written_off. |
| `retention_held` | `float` | currency | Retention billed and not yet released on the date; part of open_amount. |
| `release_date` | `str` | date | Release date of the retention: of the invoice, or the due date of an opening item. |

## OpenItemApRow (result of `open_items_ap`)

One row of `open_items_ap`: an open payable, a supplier invoice or an opening item, on a date.

| Field | Type | Unit | Description |
|---|---|---|---|
| `item_key` | `str` | key | Key of the supplier invoice or the opening item. |
| `source` | `str` | label | invoice or opening. |
| `le_key` | `str` | key | Key of the legal entity. |
| `sup_key` | `str` | key | Key of the supplier; empty for an opening item without a supplier. |
| `sinv_key` | `str` | key | Key of the supplier invoice; empty for an opening item. |
| `document_date` | `str` | date | Date of the invoice or the opening item. |
| `due_date` | `str` | date | Due date; empty when none is stored. |
| `currency` | `str` | label | Currency of the entity; all amounts of the row are in it. |
| `payable_amount_le` | `float` | currency | Amount owed, a credit note negative. |
| `paid` | `float` | currency | Payments allocated up to and including the date. |
| `open_amount` | `float` | currency | payable_amount_le less paid. |

## RetentionRow (result of `retention_receivable`)

One row of `retention_receivable`: a retention held per item, or the total of an entity.

| Field | Type | Unit | Description |
|---|---|---|---|
| `item_key` | `str` | key | Key of the invoice or opening item; empty on a total row. |
| `source` | `str` | label | invoice, opening or total. |
| `le_key` | `str` | key | Key of the legal entity. |
| `cus_key` | `str` | key | Key of the customer; empty on a total row. |
| `document_date` | `str` | date | Date of the invoice or opening item; empty on a total row. |
| `release_date` | `str` | date | Release date of the retention; empty on a total row. |
| `currency` | `str` | label | Currency of the entity. |
| `retention_held` | `float` | currency | Retention held on the item, or the sum over the entity on a total row. |

## AgeingRow (result of `ageing`)

One row of `ageing` for customers (party cus_key): the open receivable of a customer in a bucket of days past due.

| Field | Type | Unit | Description |
|---|---|---|---|
| `le_key` | `str` | key | Key of the legal entity. |
| `cus_key` | `str` | key | Key of the customer. |
| `bucket` | `str` | label | Bucket of days past due, for example 31-60, or no_due_date. |
| `n_items` | `int` | count | Number of open items in the bucket. |
| `amount` | `float` | currency | Open amount less retention held in the bucket. |

## BadDebtRow (result of `bad_debt_candidates`)

One row of `bad_debt_candidates`: an open receivable overdue by at least the write-off days of the fact.

| Field | Type | Unit | Description |
|---|---|---|---|
| `item_key` | `str` | key | Key of the invoice or the opening item. |
| `source` | `str` | label | invoice or opening. |
| `le_key` | `str` | key | Key of the legal entity. |
| `cus_key` | `str` | key | Key of the customer; empty for an opening item without a customer. |
| `inv_key` | `str` | key | Key of the invoice; empty for an opening item. |
| `document_date` | `str` | date | Date of the invoice or the opening item. |
| `due_date` | `str` | date | Due date; empty when none is stored. |
| `currency` | `str` | label | Currency of the entity; all amounts of the row are in it. |
| `invoice_amount` | `float` | currency | Amount including retention, a credit note negative. |
| `paid` | `float` | currency | Payments allocated up to and including the date. |
| `written_off` | `float` | currency | Amount written off up to the date. |
| `open_amount` | `float` | currency | invoice_amount less paid less written_off. |
| `retention_held` | `float` | currency | Retention billed and not yet released on the date; part of open_amount. |
| `release_date` | `str` | date | Release date of the retention: of the invoice, or the due date of an opening item. |
| `receivable_net` | `float` | currency | open_amount less retention_held. |
| `days_past_due` | `int` | days | Days from the due date to the date asked for. |

## CustomerExposureRow (result of `customer_exposure`)

One row of `customer_exposure`: the open receivables of a customer against its credit limit.

| Field | Type | Unit | Description |
|---|---|---|---|
| `cus_key` | `str` | key | Key of the customer. |
| `credit_limit` | `float` | currency | Credit limit as stored, in the limit currency; empty when none is set. |
| `limit_currency` | `str` | label | Currency of the credit limit. |
| `limit_dkk` | `float` | currency | Credit limit in DKK at the fixed booking rate; empty without a limit. |
| `open_dkk` | `float` | currency | Open receivables of the customer in DKK at the fixed booking rate. |
| `utilisation` | `float` | share | open_dkk divided by limit_dkk, a share; empty without a limit. |
| `over_limit` | `bool` | flag | True when open_dkk is above limit_dkk; always false without a limit. |
