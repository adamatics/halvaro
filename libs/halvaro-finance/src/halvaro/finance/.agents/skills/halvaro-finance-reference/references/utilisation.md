# utilisation

```python
utilisation(mgmt_pl_department: pd.DataFrame, *, by: str = 'period', tolerance: float = 0.01, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need booked hours over available hours in percent, per department and period or per department over all periods.

Rule: utilisation is (project hours plus service hours) over available hours times 100. by="period" gives each row of the entity, department and period with the recomputed value, the stored utilisation_pct and whether they agree within tolerance (PROPOSED 0.01); rows without available hours have a null utilisation. by="department" adds the hours of all periods per entity and department first, so the result is a ratio of sums and not a mean of percents.

## Args

mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, utilisation_pct, project_hours, service_hours and available_hours, one row per entity, department and period.
by: "period" or "department" (default "period").
tolerance: Largest accepted difference between the recomputed and the stored utilisation_pct, in percentage points (default 0.01, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame. With by="period": le_key, dep_key, period, project_hours, service_hours, available_hours, utilisation_pct, stored_utilisation_pct and agrees. With by="department": le_key, dep_key, the three hour columns summed and utilisation_pct to two decimals.

## Raises

FrameError: a column is missing, by is not "period" or "department", tolerance is negative or not a number, a row is repeated for an entity, department and period, or an hour value is negative.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import utilisation
>>> ctx = Context(stage="month3", role="analyst")
>>> hours = pd.DataFrame({"le_key": ["LE-01"] * 2, "dep_key": ["DEP-1"] * 2, "period": ["2026-01", "2026-02"], "utilisation_pct": [75.0, 80.0],
...                      "project_hours": [100.0, 120.0], "service_hours": [20.0, 20.0], "available_hours": [160.0, 175.0]})
>>> utilisation(hours, context=ctx)[["period", "utilisation_pct", "agrees"]].to_dict("records")
[{'period': '2026-01', 'utilisation_pct': 75.0, 'agrees': True}, {'period': '2026-02', 'utilisation_pct': 80.0, 'agrees': True}]
>>> utilisation(hours, by="department", context=ctx)["utilisation_pct"].tolist()
[77.61]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.mgmt_pl_department.le_key`, `finance.mgmt_pl_department.dep_key`, `finance.mgmt_pl_department.period`, `finance.mgmt_pl_department.utilisation_pct`, `finance.mgmt_pl_department.project_hours`, `finance.mgmt_pl_department.service_hours`, `finance.mgmt_pl_department.available_hours`.
