# rebuild_subledger_reconciliation

```python
rebuild_subledger_reconciliation(customer_invoice: pd.DataFrame, supplier_invoice: pd.DataFrame, payment: pd.DataFrame, payment_allocation: pd.DataFrame, opening_balance_item: pd.DataFrame, fixed_asset: pd.DataFrame, fixed_asset_schedule: pd.DataFrame, inventory_valuation: pd.DataFrame, intercompany: pd.DataFrame, bank_balance: pd.DataFrame, bank_account: pd.DataFrame, trial_balance: pd.DataFrame, gl_account: pd.DataFrame, *, allowance_gl: str = 'GL-2015', intercompany_accounts: Mapping[Any, Any] = {'intercompany_trade': (('management_fee', 'it_recharge'), 'GL-2300', 'GL-4800'), 'intercompany_interest': (('loan_interest',), 'GL-2320', 'GL-4820'), 'intercompany_dividend': (('dividend',), 'GL-2310', 'GL-4810'), 'intercompany_loan': (('loan_principal',), 'GL-1510', 'GL-4120')}, context: Context) -> pd.DataFrame
```

Use this when you need every subledger compared with its control account in the ledger at each month end.

Rule: for each entity and month end the balance of a subledger is rebuilt from the published tables and compared with the closing balance of its control account in the trial balance:
receivables and retention receivable (customer invoices and credit notes, payments allocated, write offs, opening items), payables, fixed assets cost and accumulated depreciation per
asset class, inventory and its allowance, intercompany trade, and every bank account (last daily balance of the month). reconciled = the difference is zero to the cent. An event in a
month that is not a period counts from the next period; events before the first period are the opening balance and events after the last period are ignored. The ledger account of the
allowance and the intercompany accounts are PROPOSED keywords.

## Args

customer_invoice: Frame finance.customer_invoice (invoices and credit notes, retention, write off date, counterpart entity).
supplier_invoice: Frame finance.supplier_invoice with le_key, invoice_type, invoice_date and payable_amount_le.
payment: Frame finance.payment with the allocation key columns and payment_date.
payment_allocation: Frame finance.payment_allocation, the allocation of payments to documents.
opening_balance_item: Frame finance.opening_balance_item, open items at the start of the window.
fixed_asset: Frame finance.fixed_asset with asset_class and its cost and accumulated depreciation accounts.
fixed_asset_schedule: Frame finance.fixed_asset_schedule with cost_closing and accumulated_closing per entity, asset class and period.
inventory_valuation: Frame finance.inventory_valuation with stock_value and allowance per entity, period and account.
intercompany: Frame finance.intercompany with creditor and debtor entity, amounts and dates.
bank_balance: Frame finance.bank_balance, one row per bank account and date.
bank_account: Frame finance.bank_account with le_key, bank_account and gl_key, one row per account.
trial_balance: Frame finance.trial_balance with closing_balance per entity, account and period, one row each.
gl_account: Frame finance.gl_account with control_type per account.
allowance_gl: Ledger account of the inventory allowance (default GL-2015, PROPOSED).
intercompany_accounts: Map of the intercompany control accounts (default the proposed map).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with le_key, period, subledger, detail, gl_key, subledger_balance, ledger_balance, difference (currency units), currency and reconciled (yes or no), in the shape of
finance.subledger_reconciliation.
Typed form: SubledgerReconciliationRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a frame lacks a required column, the trial balance, the asset schedule, the bank accounts or the bank balances have duplicate keys, a date cannot be read, or the trial
    balance has no rows.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import rebuild_subledger_reconciliation
>>> ctx = Context(stage="month3", role="analyst")
>>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
>>> tb = pd.DataFrame({"le_key": "LE-01", "period": ["2023-01"] * 3, "gl_key": ["GL-1100", "GL-1190", "GL-2100"], "closing_balance": [900.0, 100.0, 0.0]})
>>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "invoice_type": "invoice", "invoice_date": ["2023-01-15"], "gross_amount_le": 1000.0, "retention_amount_le": 100.0,
...                    "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
>>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
>>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2022-12-01"], "due_date": [None], "amount": [0.0],
...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
>>> empty = lambda *cols: pd.DataFrame(columns=list(cols))
>>> r = rebuild_subledger_reconciliation(
...     ci, empty("le_key", "invoice_type", "invoice_date", "payable_amount_le"), empty("le_key", "bank_account", "payment_no", "payment_date"), alloc, ob,
...     empty("asset_class", "gl_cost_key", "gl_accumulated_key"), empty("le_key", "asset_class", "period", "cost_closing", "accumulated_closing"),
...     empty("le_key", "period", "gl_key", "stock_value", "allowance"),
...     empty("ic_type", "creditor_le_key", "debtor_le_key", "document_date", "settlement_date", "creditor_amount", "debtor_amount"),
...     empty("bank_account", "balance_date", "closing_balance"), empty("le_key", "bank_account", "gl_key"), tb, gl, context=ctx)
>>> rec = r[r["subledger"] == "receivables"]
>>> rec[["subledger_balance", "ledger_balance", "reconciled"]].iloc[0].tolist() == [900.0, 900.0, True]
True
```

## Typed result

`SubledgerReconciliationRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.customer_invoice.inv_key`, `finance.customer_invoice.le_key`, `finance.customer_invoice.invoice_type`, `finance.customer_invoice.invoice_date`, `finance.customer_invoice.gross_amount_le`, `finance.customer_invoice.retention_amount_le`, `finance.customer_invoice.retention_release_date`, `finance.customer_invoice.written_off_date`, `finance.customer_invoice.counterpart_le_key`, `finance.supplier_invoice.le_key`, `finance.supplier_invoice.invoice_type`, `finance.supplier_invoice.invoice_date`, `finance.supplier_invoice.payable_amount_le`, `finance.payment.le_key`, `finance.payment.bank_account`, `finance.payment.payment_no`, `finance.payment.payment_date`, `finance.payment_allocation.le_key`, `finance.payment_allocation.bank_account`, `finance.payment_allocation.payment_no`, `finance.payment_allocation.allocation_kind`, `finance.payment_allocation.document_type`, `finance.payment_allocation.booked_amount`, `finance.payment_allocation.inv_key`, `finance.payment_allocation.sinv_key`, `finance.payment_allocation.opening_item_ref`, `finance.opening_balance_item.le_key`, `finance.opening_balance_item.gl_key`, `finance.opening_balance_item.item_ref`, `finance.opening_balance_item.document_date`, `finance.opening_balance_item.due_date`, `finance.opening_balance_item.amount`, `finance.opening_balance_item.currency`, `finance.opening_balance_item.cus_key`, `finance.opening_balance_item.sup_key`, `finance.fixed_asset.asset_class`, `finance.fixed_asset.gl_cost_key`, `finance.fixed_asset.gl_accumulated_key`, `finance.fixed_asset_schedule.le_key`, `finance.fixed_asset_schedule.asset_class`, `finance.fixed_asset_schedule.period`, `finance.fixed_asset_schedule.cost_closing`, `finance.fixed_asset_schedule.accumulated_closing`, `finance.inventory_valuation.le_key`, `finance.inventory_valuation.period`, `finance.inventory_valuation.gl_key`, `finance.inventory_valuation.stock_value`, `finance.inventory_valuation.allowance`, `finance.intercompany.ic_type`, `finance.intercompany.creditor_le_key`, `finance.intercompany.debtor_le_key`, `finance.intercompany.document_date`, `finance.intercompany.settlement_date`, `finance.intercompany.creditor_amount`, `finance.intercompany.debtor_amount`, `finance.bank_balance.bank_account`, `finance.bank_balance.balance_date`, `finance.bank_balance.closing_balance`, `finance.bank_account.le_key`, `finance.bank_account.bank_account`, `finance.bank_account.gl_key`, `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.closing_balance`, `finance.gl_account.gl_key`, `finance.gl_account.control_type`.
