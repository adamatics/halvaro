# From VAT in the ledger to the payment in the bank

Notebook `notebooks/vat-payment-and-bank.ipynb` of halvaro-finance, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** Is the VAT of a month, as the ledger lines say it, the VAT that was paid the month after, and does the bank balance after the payment agree with the payments?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `vat_return_from_ledger` | you need the VAT return of each entity and month rebuilt from the VAT coded ledger lines. | [vat_return_from_ledger](../../halvaro-finance/references/vat_return_from_ledger.md) |
| `vat_settlement` | you need to compare the VAT payable of each return with the VAT payment of the following month. | [vat_settlement](../../halvaro-finance/references/vat_settlement.md) |
| `bank_reconciliation` | you need the ledger balance of every bank account rebuilt from the opening balance and the payments, compared with the stored daily balance. | [bank_reconciliation](../../halvaro-finance/references/bank_reconciliation.md) |

## Steps

Three functions of halvaro-finance in the order a month end follows. `vat_return_from_ledger` rebuilds the VAT return from the ledger lines, `vat_settlement` compares the VAT payable with the payment of the next month, and `bank_reconciliation` rebuilds the bank balance from the opening balance and the payments. The notebook builds its own small frames, so it needs no data. The VAT box layout and the payment day are provisional facts (status VERIFY); the status travels with the result.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.finance import bank_reconciliation, vat_return_from_ledger, vat_settlement

ctx = Context(stage="month12", role="analyst")
lines = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "DKK"), ("LE-01", "GL-2510", "2025-01", 100.0, "DK25", 400.0, "DKK")],
                     columns=["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency"])
lines
```

Step 1. The VAT return of January from the two ledger lines: output VAT on sales, input VAT on purchases, and the difference payable.

```python
returned = vat_return_from_ledger(lines, context=ctx)
returned.value[["le_key", "period", "total_output_vat", "total_input_vat", "vat_payable"]]
```

Step 2. The company paid in February. The settlement compares the payable with the payment of the following month and with the payment day of the country.

```python
payments = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["BA-1"], "payment_date": ["2025-02-25"], "direction": ["outgoing"], "amount": [150.0], "description": ["VAT payment"]})
vat_return = returned.value[["le_key", "period", "vat_payable"]].assign(settlement_difference=0.0)
settlement = vat_settlement(vat_return, payments, context=ctx)
settlement.value[["period", "payment_month", "vat_payable", "paid_signed", "settlement_difference", "agrees"]]
```

Step 3. The bank side. The balance of the account is rebuilt from the opening balance of the ledger account and the payments, and compared with the stored closing balance of the day.

```python
bank_balance = pd.DataFrame({"le_key": "LE-01", "bank_account": "BA-1", "balance_date": ["2025-02-25"], "closing_balance": [850.0], "currency": "DKK"})
bank_account = pd.DataFrame({"le_key": ["LE-01"], "bank_account": ["BA-1"], "gl_key": ["GL-1200"]})
opening = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1200"], "amount": [1000.0]})
recon = bank_reconciliation(bank_balance, payments, bank_account, opening, context=ctx)
recon[["bank_account", "balance_date", "computed_balance", "closing_balance", "difference"]]
```

Step 4. Both results carry the status of the facts behind them. VERIFY means the VAT box layout and the payment day are provisional, not that the arithmetic is wrong.

```python
(returned.status, settlement.status)
```

Check. The payable equals output minus input computed from the lines with pandas, the payment equals the payable, and the rebuilt bank balance equals the opening balance minus the payment.

```python
output_vat = -lines.loc[lines["gl_key"] == "GL-4710", "amount"].sum()
input_vat = lines.loc[lines["gl_key"] == "GL-2510", "amount"].sum()
assert returned.value.loc[0, "vat_payable"] == output_vat - input_vat
assert settlement.value.loc[0, "paid_signed"] == returned.value.loc[0, "vat_payable"]
assert recon.loc[0, "computed_balance"] == opening["amount"].iloc[0] - payments["amount"].iloc[0]
assert settlement.value.loc[0, "agrees"] and recon.loc[0, "difference"] == 0
```
