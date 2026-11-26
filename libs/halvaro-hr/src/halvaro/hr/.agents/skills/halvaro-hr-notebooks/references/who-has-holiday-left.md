# Who has holiday left, who carries a lot, and do the records agree?

Notebook `notebooks/who-has-holiday-left.ipynb` of halvaro-hr, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** As HR, which people are in the red on their holiday balance, who carries many days into the new holiday year, and do the leave records match the days that the ledger says were taken?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `holiday_year_label` | you need the label of the holiday year that contains a date, for DK or DE. | [holiday_year_label](../../halvaro-hr-holiday/references/holiday_year_label.md) |
| `holiday_ledger` | you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance. | [holiday_ledger](../../halvaro-hr-holiday/references/holiday_ledger.md) |
| `high_carry_over` | you need the people who carry more holiday days into a holiday year than a threshold, so that a person can look at each of them. | [high_carry_over](../../halvaro-hr-holiday/references/high_carry_over.md) |
| `leave_vs_ledger` | you need to check that the holiday leave records agree with the days taken in the ledger, per person and holiday year. | [leave_vs_ledger](../../halvaro-hr-holiday/references/leave_vs_ledger.md) |

## Steps

Three plain questions come up every autumn. Who has taken more holiday than they have earned? Who brings a lot of days over into the new year, so that a conversation is worth having? And does what the leave records say agree with what the holiday ledger counts as taken? `holiday_year_label` says which holiday year a date is in, `holiday_ledger` gives the balance of each person month by month with a flag for a negative one, `high_carry_over` lists the people above a number of carried days (a hint for a look at one person, not a limit) and `leave_vs_ledger` sets the leave records against the ledger. The notebook builds its own small frames with invented people and days, so it needs no data.

```python
import datetime as dt

import pandas as pd

from halvaro.hr import high_carry_over, holiday_ledger, holiday_year_label, leave_vs_ledger

today = dt.date(2026, 11, 30)
year = holiday_year_label("DK", today)  # the holiday year that today is in
entitlement = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3", "EMP-4"], "holiday_year": [year] * 4, "carried_in_days": [1.0, 4.75, 11.0, 0.0],
                            "carry_over_agreement": [False, False, True, False], "opening_balance": [False] * 4})
months = ["2026-09", "2026-10", "2026-11"]
accrual = pd.DataFrame([(e, year, m, 2.0, taken) for e, taken_by_month in {"EMP-1": [0.0, 6.0, 2.0], "EMP-2": [1.0, 1.0, 1.0], "EMP-3": [0.0, 0.0, 0.0], "EMP-4": [0.0, 3.0, 1.0]}.items()
                        for m, taken in zip(months, taken_by_month)], columns=["emp_key", "holiday_year", "period", "accrued_days", "taken_days"])
year, entitlement
```

Step 1. Who is in the red? The ledger gives the balance of every person at the end of each month: the days carried in, plus what was earned, less what was taken. A balance below zero is flagged. EMP-1 took six days in October and is the one below zero.

```python
ledger = holiday_ledger(entitlement, accrual).to_frame()
latest = ledger.sort_values("period").groupby("emp_key").tail(1)
latest[["emp_key", "period", "balance", "negative"]]
```

Step 2. Who carries many days into this year? A person above the limit is listed so that someone can look at the case. The limit here is a number of the example; when it is left out the function uses a policy value that is still proposed, and the result then says so in its `policy_status`.

```python
carry_limit = 8.0  # a limit chosen for this example; without it the function uses a proposed value of the policy
carrying = high_carry_over(entitlement, holiday_year=year, threshold=carry_limit)
carrying.to_frame(), dict(carrying.policy_status)
```

Step 3. Do the records agree with the ledger? Each holiday record that ended on or before today is placed in its holiday year and summed per person; the difference is what the ledger counts as taken less what the records say. EMP-4 has a difference of one day: the ledger counts four days taken and the records show three. The total difference is compared with a tolerance of the function (25 days, a proposed value), so one day is within it.

```python
leave_record = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-2", "EMP-4"], "leave_type": ["holiday", "holiday", "holiday", "holiday"], "days": [6, 2, 3, 3],
                             "end": [dt.date(2026, 10, 23), dt.date(2026, 11, 13), dt.date(2026, 11, 6), dt.date(2026, 10, 30)]})
agreement = leave_vs_ledger(leave_record, accrual, today).to_frame()
agreement[["emp_key", "holiday_year", "leave_days", "taken_days", "difference", "within_total_tolerance"]]
```

Check. Each answer is recomputed from the frames: the balance as carried days plus earned less taken, the red flag from its sign, the list of high carriers with a filter on the limit, and the difference from a plain sum of the records and of the ledger.

```python
end_of_year = accrual.groupby("emp_key")[["accrued_days", "taken_days"]].sum()
expected = (entitlement.set_index("emp_key")["carried_in_days"] + end_of_year["accrued_days"] - end_of_year["taken_days"]).round(2)
assert (latest.set_index("emp_key")["balance"] == expected).all()
assert (latest.set_index("emp_key")["negative"] == (expected < 0)).all()
listed = set(carrying.to_frame()["emp_key"])
assert listed == set(entitlement.loc[entitlement["carried_in_days"] > carry_limit, "emp_key"])
records = leave_record.groupby("emp_key")["days"].sum()
by_person = agreement.set_index("emp_key")
assert (by_person["leave_days"] == records.reindex(by_person.index, fill_value=0)).all()
assert (by_person["taken_days"] == end_of_year["taken_days"].reindex(by_person.index)).all()
assert (by_person["difference"] == by_person["taken_days"] - by_person["leave_days"]).all()
```
