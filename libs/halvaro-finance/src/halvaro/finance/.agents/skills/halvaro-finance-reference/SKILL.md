---
name: halvaro-finance-reference
description: Use when a task needs a trial balance, a project margin or percent of completion, a consolidation check, a budget variance, a payroll tie out, a supplier spend or a statement check: the functions of halvaro-finance other than those of the finance skill.
---
# Reference of the other functions of halvaro-finance

Fictional company, synthetic data. This skill belongs to the installed version of the package and was generated from its docstrings.

## When to use

A task rebuilds a trial balance, recognises project revenue, checks the group consolidation, compares forecast and budget, ties payroll to the ledger, or checks a statement. Amounts stay in their currency; DKK conversions use the fixed booking rate of core.

## How to call

- Import from the package: `from halvaro.finance import <function>` (names in the table below).
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in as DataFrames.
- A legal value is a fact read with `halvaro.core.fact(id)`; never type one. A policy value is a parameter with a proposed default: name the value you used.
- Errors are errors of the library (`FrameError` and its relatives) and name the column, key or value that is wrong. Fix the input, do not catch and ignore the error.
- Every finance function takes a required keyword `context` (`halvaro.core.Context`): a source above its stage is refused with `StageRefusal`.

## Functions

| Function | Use this when | Returns |
|---|---|---|
| [`approval_limit_breaches`](references/approval_limit_breaches.md) | Use this when you check that the buyers of purchase orders had the authority for the value, by the grade of the buyer on the order date. | `pd.DataFrame` |
| [`budget_variance`](references/budget_variance.md) | Use this when you compare what was booked with what was budgeted, by entity, cost centre, account and period, for one budget version. | `pd.DataFrame` |
| [`committed_cost`](references/committed_cost.md) | Use this when you need the value of the purchase orders that are still open, by project and cost code, in the order currency and in DKK. | `pd.DataFrame` |
| [`contract_position`](references/contract_position.md) | Use this when you need revenue recognised less billed on each project row, split into the contract asset and the contract liability. | `pd.DataFrame` |
| [`cost_centre_team_map`](references/cost_centre_team_map.md) | Use this when you check that finance cost centres and hr teams point at each other. | `pd.DataFrame` |
| [`cost_per_metre_by_cost_code`](references/cost_per_metre_by_cost_code.md) | Use this when you compare projects by actual cost per metre of route for each cost code, with the median over the projects. | `CostPerMetre` |
| [`cost_to_completion`](references/cost_to_completion.md) | Use this when you need the cost still to come on a list of projects in one period: EAC less actual cost, with the committed cost shown apart. | `pd.DataFrame` |
| [`dkk_amount`](references/dkk_amount.md) | Use this when you need amounts in DKK to the cent: on the booking basis with the fixed rates of core, or on the daily basis with the latest rate on or before each date. | `pd.Series` |
| [`eliminations`](references/eliminations.md) | Use this when you need to check the consolidation entries of the group: that they are positive, balanced, between two different accounts, complete by type, and zero over a period. | `pd.DataFrame` |
| [`employer_oncosts`](references/employer_oncosts.md) | Use this when you need the employer pension and social contributions on gross pay, per entity, cost centre and month, by country. | `Envelope` |
| [`exposure_bridge`](references/exposure_bridge.md) | Use this when you need to explain the gap between the open quantity and the finance definitions of the price exposure, per project. | `pd.DataFrame` |
| [`filing_status`](references/filing_status.md) | Use this when you need to know whether each annual report was filed on time, from the deadline and the filed date. | `Envelope` |
| [`finance_exposure`](references/finance_exposure.md) | Use this when you need the price exposure of the projects at a period as the finance data defines it: the cumulative exposure and the part that can be recovered. | `pd.DataFrame` |
| [`forecast_vs_budget`](references/forecast_vs_budget.md) | Use this when you compare each forecast version with the budget it is based on, by entity, cost centre, account and period in DKK. | `pd.DataFrame` |
| [`group_trial_balance`](references/group_trial_balance.md) | Use this when you need the movement of the group per period and account in DKK: the two entities plus the reporting adjustments plus the eliminations. | `Envelope` |
| [`intercompany_match`](references/intercompany_match.md) | Use this when you need the intercompany pairs of the two legal entities recomputed and compared with what is stored. | `Envelope` |
| [`journal_integrity`](references/journal_integrity.md) | Use this when you check the journals of the ledger: every journal has its lines, balances to the cent and is numbered without gaps. | `Envelope` |
| [`labour_absorption_check`](references/labour_absorption_check.md) | Use this when you check that labour booked on projects and on service is absorbed in the ledger, per entity and month for projects and over the whole window for service. | `pd.DataFrame` |
| [`labour_cost_overrun`](references/labour_cost_overrun.md) | Use this when you rank projects by how far their labour cost has run over the labour budget in a window of months. | `pd.DataFrame` |
| [`ledger_gross_pay`](references/ledger_gross_pay.md) | Use this when you need the gross salary booked in the ledger per legal entity, cost centre and month, to tie out against the payroll summary. | `pd.DataFrame` |
| [`loss_provision`](references/loss_provision.md) | Use this when you need the provision for the loss that a project is expected to make: the part of the expected loss not yet recognised. | `pd.Series` |
| [`manual_journals`](references/manual_journals.md) | Use this when you need the lines of the journals that were posted by hand, optionally only those on one account or one project. | `pd.DataFrame` |
| [`margin_trail`](references/margin_trail.md) | Use this when you follow the margin of one project period by period, with the period and amount of its write-down. For the margins alone, of all projects at once, project_margin is enough. | `pd.DataFrame` |
| [`mgmt_pl_check`](references/mgmt_pl_check.md) | Use this when you check that the management P&L agrees with the ledger and adds up within each department row. | `pd.DataFrame` |
| [`open_exposure`](references/open_exposure.md) | Use this when you need the added cost of a price step on the demand that is still open, per project, in DKK. | `pd.DataFrame` |
| [`order_book_check`](references/order_book_check.md) | Use this when you check the order book of each entity and project type: the closing backlog is the opening plus order intake less revenue recognised, and the opening is the previous closing. | `pd.DataFrame` |
| [`percent_complete`](references/percent_complete.md) | Use this when you need the percent of completion of each project row by cost to cost: actual cost over the estimate at completion. | `pd.Series` |
| [`price_steps`](references/price_steps.md) | Use this when you need the change of the price of each supplier and item between the day before an effective date and the effective date. | `pd.DataFrame` |
| [`price_variance_report`](references/price_variance_report.md) | Use this when you need how far the invoiced prices of each supplier and item sit from the purchase order price. | `pd.DataFrame` |
| [`prior_year_column`](references/prior_year_column.md) | Use this when you check that the prior year column of each report equals the amount of the report of the year before. | `pd.DataFrame` |
| [`project_margin`](references/project_margin.md) | Use this when you need the two named margins of a project and period in percent: the margin to date and the margin forecast at completion. Never one "margin". To follow one project period by period together with its write-down, use margin_trail. | `pd.DataFrame` |
| [`rebuild_trial_balance`](references/rebuild_trial_balance.md) | Use this when you need the trial balance per entity, period and account rebuilt from the journal lines and the opening items. | `Envelope` |
| [`recoverable`](references/recoverable.md) | Use this when you need the part of the price exposure that the customer contract passes on to the customer, per project. | `pd.DataFrame` |
| [`revenue_recognised`](references/revenue_recognised.md) | Use this when you need the revenue recognised to date on each project row: the contract value times the cost to cost fraction. | `pd.Series` |
| [`roll_retained_earnings`](references/roll_retained_earnings.md) | Use this when a trial balance was built without carrying results and you need the results of completed fiscal years moved into the retained earnings account. | `Envelope` |
| [`size_class`](references/size_class.md) | Use this when you need how many of the three Danish size criteria a report exceeds: revenue, balance sheet total and average employees. | `Envelope` |
| [`statement_from_ledger`](references/statement_from_ledger.md) | Use this when you rebuild the statutory lines of one entity and fiscal year from its trial balance, in the entity currency and the natural sign. | `LedgerStatement` |
| [`statements_check`](references/statements_check.md) | Use this when you check a set of statutory statements for lines that do not foot and links that do not hold, per report. | `pd.DataFrame` |
| [`statutory_line_of`](references/statutory_line_of.md) | Use this when you need the statutory statement line that each ledger account belongs to, for Denmark and for Germany. | `pd.DataFrame` |
| [`supplier_spend`](references/supplier_spend.md) | Use this when you need what was spent per supplier and category in DKK over a range of invoice dates. | `pd.DataFrame` |
| [`three_way_match`](references/three_way_match.md) | Use this when you check each supplier invoice line against the purchase order price and the quantity accepted on the receipt. | `pd.DataFrame` |
| [`tie_out`](references/tie_out.md) | Use this when you check the gross pay of the ledger against the aggregate of the hr side, per group of cost centres and month. | `Envelope` |
| [`to_natural_sign`](references/to_natural_sign.md) | Use this when a ledger column is debit positive and you need it in the sign people read: revenue and liabilities positive. | `pd.Series` |
| [`translation_check`](references/translation_check.md) | Use this when you check the rounding of the line by line EUR to DKK translation of a trial balance at each fiscal year end. | `Envelope` |
| [`utilisation`](references/utilisation.md) | Use this when you need booked hours over available hours in percent, per department and period or per department over all periods. | `pd.DataFrame` |
| [`write_down_journal`](references/write_down_journal.md) | Use this when you need the write-down lines booked on one project, from the manual journals. | `pd.DataFrame` |

## Reference pages

- One page per function in `references/` (signature, rule, arguments, returns, errors, example, facts and sources).
- `references/flat.md`: every page in one file, for an agent that reads one file.
