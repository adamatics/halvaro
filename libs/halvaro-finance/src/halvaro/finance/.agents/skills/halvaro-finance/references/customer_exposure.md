# customer_exposure

```python
customer_exposure(open_items: pd.DataFrame, customer: pd.DataFrame, *, context: Context) -> pd.DataFrame
```

Use this when you need the open receivables of each customer in DKK against the credit limit of the customer.

Rule: open_dkk = the open amounts of the customer converted to DKK at the fixed booking rates (facts world.fx_eur_dkk_fixed and world.fx_sek_dkk_fixed); limit_dkk = the credit limit converted the
same way; utilisation = open_dkk / limit_dkk; over_limit = open_dkk is above limit_dkk. A customer without a credit limit has no limit_dkk and is never over the limit; a customer without open
items is listed with zero. Needs the crm source (stage month12).

## Args

open_items: The frame returned by open_items_ar, with cus_key, open_amount and currency.
customer: Frame crm.customer with cus_key, credit_limit and currency, one row per customer.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

DataFrame with cus_key, credit_limit and limit_currency (the limit as stored), limit_dkk, open_dkk (DKK), utilisation (a share, empty without a limit) and over_limit (yes or no), one row per
customer.
Typed form: CustomerExposureRow.from_frame(the frame), one frozen model per row.

## Raises

FrameError: a frame lacks a required column, crm.customer has a duplicate cus_key, or a customer with open items is not in crm.customer.
StageRefusal: a source of the function is above the stage of the context (crm is stage month12).

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import Context
>>> ctx = Context(stage="month12", role="analyst")
>>> gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
>>> alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
>>> pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
>>> ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0],
...                    "currency": ["DKK"], "cus_key": [None], "sup_key": [None]})
>>> ci = pd.DataFrame({"inv_key": ["I1"], "le_key": "LE-01", "cus_key": "CUS-1", "invoice_type": "invoice", "invoice_date": ["2025-01-10"], "due_date": ["2025-02-10"],
...                    "gross_amount_le": 1000.0, "retention_amount_le": 100.0, "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
>>> from halvaro.finance import customer_exposure, open_items_ar
>>> items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 3, 31), context=ctx)
>>> cust = pd.DataFrame({"cus_key": ["CUS-1"], "credit_limit": [500.0], "currency": ["DKK"]})
>>> r = customer_exposure(items[items["source"] == "invoice"], cust, context=ctx)
>>> r[["open_dkk", "limit_dkk", "over_limit"]].values.tolist() == [[1000.0, 500.0, True]]
True
```

## Typed result

`CustomerExposureRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `finance.customer_invoice.cus_key`, `finance.customer_invoice.le_key`, `crm.customer.cus_key`, `crm.customer.credit_limit`, `crm.customer.currency`.
