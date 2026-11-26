# Holiday carry-over into the next year

Notebook `notebooks/holiday-carry-over.ipynb` of halvaro-hr, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How many holiday days should a person carry into the next holiday year, does the carry-in stored for the next year agree, and how far is it from the cap?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `holiday_ledger` | you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance. | [holiday_ledger](../../halvaro-hr-holiday/references/holiday_ledger.md) |
| `carry_over_projection` | you need the carry-in that the next holiday year should start with, and whether the carry-in stored for it agrees. | [carry_over_projection](../../halvaro-hr-holiday/references/carry_over_projection.md) |
| `carry_over_position` | you need to compare the days carried into each holiday year with the cap that applies to the person, and see the headroom that is left. | [carry_over_position](../../halvaro-hr-holiday/references/carry_over_position.md) |

## Steps

The days left at the end of a holiday year are carried into the next, up to a cap. `holiday_ledger` gives the balance at the end of the year, `carry_over_projection` says what the next year should start with and whether the stored carry-in agrees, and `carry_over_position` compares the stored carry-in with the cap and shows the headroom. The cap is a registered fact, never a number typed here. The notebook builds its own small frames, so it needs no data.

```python
import pandas as pd

from halvaro.core import fact
from halvaro.hr import carry_over_position, carry_over_projection, holiday_ledger

cap = fact("legal.DK.holiday.carryover.default_max_days")
cap
```

Step 1. One person, two holiday years. The first year ends with more days than the cap, and the stored carry-in of the second year is exactly the cap.

```python
ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2027/28"], "carried_in_days": [0.0, cap.value],
                    "carry_over_agreement": [False, False], "opening_balance": [False, False]})
acc = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "period": ["2027-08"], "accrued_days": [cap.value + 3.0], "taken_days": [0.0]})
ledger = holiday_ledger(ent, acc)
ledger.to_frame()[["holiday_year", "period", "balance"]]
```

Step 2. The projection takes the balance at the end of the year, cuts it at the cap and compares it with the carry-in stored for the next year.

```python
projection = carry_over_projection(ledger, ent)
projection.to_frame()
```

Step 3. The position of every stored carry-in against the cap: the headroom that is left, and whether the person is at the cap.

```python
position = carry_over_position(ent)
position.to_frame()[["holiday_year", "carried_in_days", "headroom", "at_cap"]]
```

Check. The projected carry-in is the smaller of the balance and the cap, computed here without the library, and the stored carry-in agrees with it. The headroom of the second year is the cap less its carry-in.

```python
balance = ledger[-1].balance
assert projection[0].projected_carry_in == min(balance, cap.value)
assert projection[0].matches
second = [row for row in position if row.holiday_year == "2027/28"][0]
assert second.headroom == cap.value - ent.loc[ent["holiday_year"] == "2027/28", "carried_in_days"].iloc[0]
```
