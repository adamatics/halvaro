# How late a project was: plan versions, milestones and delay days

Notebook `notebooks/plan-versions-and-overrun.ipynb` of halvaro-delivery, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How far did the plan of a project move over its versions, which milestones were done late or are overdue on a day, how large was the overrun of a finished project, and do the logged delay days add up to the difference between planned and actual end?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `plan_slip` | you need how far each plan version moved planned_end against the baseline (version 1) and against the version before it. | [plan_slip](../../halvaro-delivery/references/plan_slip.md) |
| `milestone_slippage` | you need the state of each milestone on a date: done with its slip, or open with its overdue days. | [milestone_slippage](../../halvaro-delivery/references/milestone_slippage.md) |
| `schedule_overrun` | you need the schedule overrun of each project on a date, in days and as a fraction of the planned days. | [schedule_overrun](../../halvaro-delivery/references/schedule_overrun.md) |
| `delay_days` | you need the delay event days of each project by cause and responsible party, and how they tie to the date difference between actual and planned end. | [delay_days](../../halvaro-delivery/references/delay_days.md) |

## Steps

Lateness has four views. `plan_slip` follows the planned end across the plan versions, `milestone_slippage` gives the state of each milestone on a day, `schedule_overrun` measures a finished project against its planned days (the overrun is the days late over the planned days, a proposed definition), and `delay_days` sums the logged delay events and sets them against the date difference. The notebook builds its own small frames with invented dates, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.delivery import delay_days, milestone_slippage, plan_slip, schedule_overrun

ctx = Context(stage="month12", role="analyst")
project = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "start": ["2028-02-01", "2028-03-01"], "planned_end": ["2028-09-30", "2028-08-31"],
                        "actual_end": ["2028-10-14", "2028-08-24"], "forecast_end": [None, None]})
plan_version = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3 + ["PRJ-900002"], "plan_version": [1, 2, 3, 1], "created": ["2028-01-10", "2028-05-02", "2028-07-20", "2028-02-15"],
                             "reason": ["baseline", "ground conditions", "late delivery", "baseline"], "planned_end": ["2028-09-30", "2028-10-07", "2028-10-14", "2028-08-31"]})
milestone = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "milestone_no": [1, 2, 3], "planned_date": ["2028-04-01", "2028-07-01", "2028-10-01"],
                          "actual_date": ["2028-04-06", "2028-07-01", "2028-10-14"]})
delay_event = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "seq": [1, 2], "cause_code": ["ground_conditions", "late_delivery"], "responsible_party": ["customer", "supplier"], "days": [7, 7]})
plan_version
```

Step 1. The plan versions. Each version is set against the baseline (version 1) and against the version before it, so a project that slipped in two steps shows both numbers.

```python
slip = plan_slip(plan_version, context=ctx)
slip[["prj_key", "plan_version", "reason", "planned_end", "slip_days", "step_days"]]
```

Step 2. The milestones on two days. On 10 October 2028 the last milestone of the first project is open and overdue; on 1 November it is done, with its slip. A date after the day counts as not yet known.

```python
before = milestone_slippage(milestone, "2028-10-10", context=ctx)
after = milestone_slippage(milestone, "2028-11-01", context=ctx)
before[["milestone_no", "state", "slip_days", "overdue_days"]], after[["milestone_no", "state", "slip_days", "overdue_days"]]
```

Step 3. The overrun of the finished projects on 1 November: the days between actual and planned end, over the planned days of the project. A project that finished early has a negative overrun.

```python
overrun = schedule_overrun(project, "2028-11-01", context=ctx)
overrun[["prj_key", "basis", "planned_days", "overrun_days", "overrun"]]
```

Step 4. The delay events, by cause and responsible party, and the tie: the event days of a project against the date difference of its actual and planned end. A project without events is listed too, with zero event days, and does not tie by design.

```python
delays = delay_days(delay_event, project, context=ctx)
delays.by_cause, delays.tie[["prj_key", "event_days", "date_diff", "diff", "ties"]]
```

Check. Every figure is recomputed from the dates with pandas: the slip against the baseline and against the previous version, the state and slip of each milestone on each day, the overrun as days over planned days, and the event days against the date difference.

```python
ends = pd.to_datetime(plan_version["planned_end"])
baseline = ends.groupby(plan_version["prj_key"]).transform("first")
assert ((slip["slip_days"]) == (ends - baseline).dt.days.to_numpy()).all()
assert (slip["step_days"].fillna(0).to_numpy() == ends.groupby(plan_version["prj_key"]).diff().dt.days.fillna(0).to_numpy()).all()
planned, actual = pd.to_datetime(milestone["planned_date"]), pd.to_datetime(milestone["actual_date"])
def state_on(day):
    return pd.Series(["done" if a <= pd.Timestamp(day) else ("open_overdue" if p < pd.Timestamp(day) else "open") for p, a in zip(planned, actual)])
assert (before["state"].reset_index(drop=True) == state_on("2028-10-10")).all()
assert (after["state"].reset_index(drop=True) == state_on("2028-11-01")).all()
assert (after["slip_days"].to_numpy() == (actual - planned).dt.days.to_numpy()).all()
assert (before["overdue_days"].iloc[2] == (pd.Timestamp("2028-10-10") - planned.iloc[2]).days)
span = pd.to_datetime(project["planned_end"]) - pd.to_datetime(project["start"])
late = pd.to_datetime(project["actual_end"]) - pd.to_datetime(project["planned_end"])
assert (overrun["planned_days"].to_numpy() == (span.dt.days + 1).to_numpy()).all()
assert ((overrun["overrun"] - late.dt.days / (span.dt.days + 1)).abs() < 1e-9).all()
events = delay_event.groupby("prj_key")["days"].sum()
first = delays.tie.set_index("prj_key")
assert first.loc["PRJ-900001", "event_days"] == events["PRJ-900001"] == late.dt.days.iloc[0]
assert first.loc[events.index, "ties"].all()  # a project without events is listed and does not tie by design: nothing was logged
```
