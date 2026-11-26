# Money in cents, one currency per sum, one status per result

Notebook `notebooks/money-sums-and-status.ipynb` of halvaro-core, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How do you split an amount between cost centres without losing a cent, sum money without mixing currencies, and report one status for a result that rests on several facts?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `to_cents` | you need an amount as whole cents, so that sums and comparisons are exact. | [to_cents](../../halvaro-core/references/to_cents.md) |
| `from_cents` | you have whole cents and need the amount, with a missing value kept as missing. | [from_cents](../../halvaro-core/references/from_cents.md) |
| `rdiv` | you divide whole cents by a whole number and the result must be whole cents too. | [rdiv](../../halvaro-core/references/rdiv.md) |
| `guarded_sum` | you need the sum of an amount or quantity column and must be sure that no two currencies or units are added together. | [guarded_sum](../../halvaro-core/references/guarded_sum.md) |
| `combine_status` | a result rests on several facts and needs one status for its envelope. | [combine_status](../../halvaro-core/references/combine_status.md) |

## Steps

Money in the Halvaro libraries is counted in whole cents, a sum never adds two currencies, and a result that rests on several legal facts carries one combined status. The notebook uses `to_cents`, `from_cents`, `rdiv`, `guarded_sum` and `combine_status` of halvaro-core, and the result of `holiday_balance` of halvaro-hr, which uses them. It builds its own small frames.

```python
import datetime as dt

import pandas as pd

from halvaro.core import SumGuardError, combine_status, fact
from halvaro.core.money import from_cents, guarded_sum, rdiv, to_cents

total = to_cents(1000.00)
total
```

Step 1. An amount becomes integer cents. A tie, half a cent exactly, goes to the even cent, so the rounding has no drift. The three amounts here are exact ties.

```python
ties = (0.125, 0.375, 0.625)
[to_cents(x) for x in ties]
```

Step 2. Split the total over three cost centres by weight. Each share is an integer division rounded half away from zero, so the shares can differ from the total by a cent. The last share takes the difference.

```python
weights = [1, 1, 1]
shares = [rdiv(total * w, sum(weights)) for w in weights]
shares[-1] += total - sum(shares)
[from_cents(s) for s in shares]
```

Step 3. A sum never adds two currencies. Group by the currency and each currency has its own sum.

```python
rows = pd.DataFrame({"cc_key": ["CC-0001", "CC-0001", "CC-0002"], "currency": ["DKK", "EUR", "DKK"], "amount": [100.0, 20.0, 5.5]})
per_currency = guarded_sum(rows, "amount", by=["currency"])
per_currency
```

Step 4. A sum of one cost centre that holds two currencies is refused, with a message that names the guard.

```python
try:
    guarded_sum(rows, "amount", by=["cc_key"], guard="currency")
except SumGuardError as error:
    refusal = str(error)
refusal
```

Step 5. A result that rests on several facts gets one status: VERIFY beats verified. The balance of halvaro-hr reports the status that core combines from the facts behind it.

```python
ids = ["legal.DK.holiday.accrual_days_per_month", "legal.DK.holiday.annual_days"]
status = combine_status([fact(i).status for i in ids])
status
```

Check. The ties round to the even cent, as the built in round of Python does, the shares add up to the total, the sums per currency equal a plain pandas group by, the guard refused the mixed group, and the combined status is VERIFY exactly when one of the facts is.

```python
assert [int(to_cents(x)) for x in ties] == [round(x * 100) for x in ties]
assert sum(shares) == total
assert dict(zip(per_currency["currency"], per_currency["amount"])) == rows.groupby("currency")["amount"].sum().to_dict()
assert "currency" in refusal
assert (status == "VERIFY") == any(fact(i).status in ("VERIFY", "proposed") for i in ids)
```
