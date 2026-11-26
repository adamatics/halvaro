# From a month to its working days

Notebook `notebooks/month-to-working-days.ipynb` of halvaro-core, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How many working days does a month have in a region, how does that change with the region, and what does a person's leave leave of it?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `period_range` | you need every month between two periods, both included, as a list of periods. | [period_range](../../halvaro-core/references/period_range.md) |
| `month_end` | you need the last calendar day of a period written YYYY-MM. | [month_end](../../halvaro-core/references/month_end.md) |
| `public_holidays` | you need the public holidays of a year in one of the three regions. | [public_holidays](../../halvaro-core/references/public_holidays.md) |
| `working_days` | you need the number of working days between two dates in a region, both days included. | [working_days](../../halvaro-core/references/working_days.md) |
| `net_working_days` | you need, per person, the working days of a period, the leave days that fall on working days and the days left after leave. | [net_working_days](../../halvaro-core/references/net_working_days.md) |

## Steps

Many rules count days: accrual, availability, capacity. The core library holds the calendar once. `period_range` lists months, `month_end` gives the last day of a month, `public_holidays` the public holidays of a region and `working_days` the working days between two dates; `net_working_days` takes a person's leave off. The notebook builds its own small frames, so it needs no data.

```python
import datetime as dt

import numpy as np
import pandas as pd

from halvaro.core import month_end, period_range, public_holidays, working_days
from halvaro.core.calendar import net_working_days

months = period_range("2026-03", "2026-05")
months
```

Step 1. The working days of each of the three months in Denmark and in Hamburg. Easter and the other holidays fall differently in the two regions.

```python
rows = []
for month in months:
    first, last = dt.date(int(month[:4]), int(month[5:]), 1), month_end(month)
    rows.append({"month": month, "DK": working_days(first, last, "DK"), "DE-HH": working_days(first, last, "DE-HH")})
calendar = pd.DataFrame(rows)
calendar
```

Step 2. One person on leave for a week of April. The leave counts only on working days, so a holiday inside the week is not counted twice.

```python
persons = pd.DataFrame({"emp_key": ["EMP-1"], "region": ["DK"]})
leave = pd.DataFrame({"emp_key": ["EMP-1"], "leave_type": ["holiday"], "start": [dt.date(2026, 3, 30)], "end": [dt.date(2026, 4, 3)]})
net = net_working_days(persons, leave, dt.date(2026, 3, 1), dt.date(2026, 4, 30))
net
```

Check. The working days equal a plain numpy count of weekdays less the public holidays of the region. The net days are the working days less the leave days.

```python
def by_numpy(first, last, region):
    days = np.busday_count(first, last + dt.timedelta(days=1), holidays=sorted(public_holidays(first.year, region)))
    return int(days)

for month, dk in zip(calendar["month"], calendar["DK"]):
    assert dk == by_numpy(dt.date(int(month[:4]), int(month[5:]), 1), month_end(month), "DK")
row = net.iloc[0]
holidays = sorted(public_holidays(2026, "DK"))
assert row["working_days"] == int(np.busday_count(dt.date(2026, 3, 1), dt.date(2026, 5, 1), holidays=holidays))
assert row["leave_days"] == int(np.busday_count(dt.date(2026, 3, 30), dt.date(2026, 4, 4), holidays=holidays))
assert row["net_days"] == row["working_days"] - row["leave_days"]
```
