# vat_settlement

```python
vat_settlement(vat_return: pd.DataFrame, payment: pd.DataFrame, *, description: str | tuple[str, ...] = ('VAT payment', 'VAT refund'), tolerance: float = 0.011, context: Context) -> Envelope
```

Use this when you need to compare the VAT payable of each return with the VAT payment of the following month.

Rule: the signed payment is the amount of the payments whose description is one of `description` (outgoing positive, incoming negative, so a refund is an incoming payment). The settlement
difference = vat_payable less the signed payment of the month after the period. The recomputed difference is compared with the stored one within `tolerance`. The payment day is compared with
the fact fin.vat.<country>.payment_day_of_next_month (status VERIFY): a payment on that day or on the next working day of the entity's holiday region agrees. A month with no payment has a null
payment and a null difference.

## Args

vat_return: Frame finance-reporting.vat_return with le_key, period (text like 2025-02), vat_payable and settlement_difference.
payment: Frame finance.payment with le_key, payment_date, direction (outgoing or incoming), amount and description.
description: One payment description or a tuple of them that count as VAT payments (default "VAT payment" and "VAT refund", PROPOSED).
tolerance: Largest accepted difference between the recomputed and the stored settlement difference, in currency units (default 0.011).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, period, vat_payable, payment_month, paid_signed, paid_date, settlement_difference, stored_difference (currency units), agrees and
day_agrees (yes or no, missing when there is no payment). The envelope carries the VERIFY status of the payment day facts.
Typed form: VatSettlementRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, a period is not text like 2025-02, an entity has no country, a VAT payment has no date or a direction other than outgoing or incoming, or an entity
    has more than one VAT payment in a month.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import vat_settlement
>>> ctx = Context(stage="month12", role="analyst")
>>> ret = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "vat_payable": [150.0], "settlement_difference": [0.0]})
>>> pay = pd.DataFrame({"le_key": ["LE-01"], "payment_date": ["2025-02-25"], "direction": ["outgoing"], "amount": [150.0], "description": ["VAT payment"]})
>>> r = vat_settlement(ret, pay, context=ctx).value
>>> r.loc[0, ["payment_month", "paid_signed", "settlement_difference", "agrees"]].tolist() == ['2025-02', 150.0, 0.0, True]
True
```

## Typed result

`VatSettlementRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.vat.DK.payment_day_of_next_month`, `fin.vat.DE.payment_day_of_next_month`.

Source columns: `finance-reporting.vat_return.le_key`, `finance-reporting.vat_return.period`, `finance-reporting.vat_return.vat_payable`, `finance-reporting.vat_return.settlement_difference`, `finance.payment.le_key`, `finance.payment.payment_date`, `finance.payment.direction`, `finance.payment.amount`, `finance.payment.description`.
