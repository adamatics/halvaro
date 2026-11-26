# intercompany_agreement

```python
intercompany_agreement(intercompany: pd.DataFrame, intercompany_balance: pd.DataFrame, *, tolerance_dkk: float = 1.0, context: Context) -> Envelope
```

Use this when you need to check that the two sides of the intercompany records agree.

Rule: both sides of a record are converted to DKK at the fixed booking rates (facts world.fx_eur_dkk_fixed and world.fx_sek_dkk_fixed) and must agree within tolerance_dkk; the stored
difference_dkk must equal the recomputed one and the stored flags matched (documents) and agrees (balances) must say the same as the recomputation. The tolerance is a PROPOSED keyword.

## Args

intercompany: Frame finance.intercompany with ic_type, document_date, creditor_amount, creditor_currency, debtor_amount, currency, difference_dkk and matched.
intercompany_balance: Frame finance.intercompany_balance with period, creditor and debtor entity, balance_type, both balances and currencies, difference_dkk and agrees.
tolerance_dkk: Largest accepted difference between the two sides, in DKK (default 1.0, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame of violations (table, key, rule, detail), empty when both sides agree. The envelope carries the VERIFY status of the exchange rate facts.
Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, the tolerance is negative or not a number, or a date cannot be read.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import intercompany_agreement
>>> ctx = Context(stage="month3", role="analyst")
>>> ic = pd.DataFrame({"ic_type": ["recharge"], "document_date": ["2025-01-31"], "creditor_amount": [100.0], "creditor_currency": ["DKK"], "debtor_amount": [100.0],
...                    "currency": ["DKK"], "difference_dkk": [0.0], "matched": [True]})
>>> icb = pd.DataFrame({"period": ["2025-01"], "creditor_le_key": ["LE-01"], "debtor_le_key": ["LE-02"], "balance_type": ["trade"], "creditor_balance": [100.0],
...                     "creditor_currency": ["DKK"], "debtor_balance": [100.0], "debtor_currency": ["DKK"], "difference_dkk": [0.0], "agrees": [True]})
>>> intercompany_agreement(ic, icb, context=ctx).value.empty
True
```

## Typed result

`ViolationRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `finance.intercompany.ic_type`, `finance.intercompany.document_date`, `finance.intercompany.creditor_amount`, `finance.intercompany.creditor_currency`, `finance.intercompany.debtor_amount`, `finance.intercompany.currency`, `finance.intercompany.difference_dkk`, `finance.intercompany.matched`, `finance.intercompany_balance.period`, `finance.intercompany_balance.balance_type`, `finance.intercompany_balance.creditor_le_key`, `finance.intercompany_balance.debtor_le_key`, `finance.intercompany_balance.creditor_balance`, `finance.intercompany_balance.creditor_currency`, `finance.intercompany_balance.debtor_balance`, `finance.intercompany_balance.debtor_currency`, `finance.intercompany_balance.difference_dkk`, `finance.intercompany_balance.agrees`.
