# From samples to alarms, incidents and tickets

Notebook `notebooks/samples-to-alarms-and-incidents.ipynb` of halvaro-grid, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How do the ok samples of a load sensor become alarms under the limits of the sensor, how do alarms that follow each other close become one incident, how many alarms are there per zone and month, and which of them have a service ticket?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `recompute_alarms` | you need the alarms recomputed from the ok samples and the limit columns of each sensor, in the shape of telemetry.alarm. | [recompute_alarms](../../halvaro-grid/references/recompute_alarms.md) |
| `incident_groups` | you need the incident number of each alarm, grouping alarms of one element and type that follow each other closely. | [incident_groups](../../halvaro-grid/references/incident_groups.md) |
| `alarm_summary` | you need counts of alarms by zone, type, severity and month, and the background alarm rate per zone and year. | [alarm_summary](../../halvaro-grid/references/alarm_summary.md) |
| `alarm_ticket_link` | you need to know which alarms have a service ticket, and how many tickets each incident has. | [alarm_ticket_link](../../halvaro-grid/references/alarm_ticket_link.md) |

## Steps

An alarm is not stored in a sample; it is a run of samples above a limit that lasts long enough. `recompute_alarms` finds the runs from the ok samples and the limit columns of each sensor, `incident_groups` numbers the alarms of one element and type that follow each other within a merge gap, `alarm_summary` counts them by zone, type, severity and month, and `alarm_ticket_link` says which alarms carry a service ticket. The notebook builds its own small frames with invented values, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.grid import alarm_summary, alarm_ticket_link, incident_groups, recompute_alarms

ctx = Context(stage="month12", role="analyst")
sensor = pd.DataFrame({"sns_key": ["SNS-900001", "SNS-900002"], "net_key": ["NET-900001", "NET-900002"], "zone_key": ["ZONE-0001", "ZONE-0002"], "sensor_type": ["load_percent"] * 2,
                       "interval_s": [900, 900], "limit_high": [90.0, 80.0], "limit_low": [None, None], "limit_high_crit": [100.0, 95.0], "limit_low_crit": [None, None],
                       "alarm_min_duration_s": [900, 1800], "alarm_merge_gap_s": [900, 900]})
slots = pd.date_range("2028-01-10 00:00", "2028-01-15 00:00", freq="15min")
rows = []
for key, spikes in {"SNS-900001": {4: 95.0, 5: 96.0, 7: 92.0, 40: 101.0, 41: 102.0, 400: 93.0, 401: 94.0}, "SNS-900002": {10: 85.0, 30: 82.0, 31: 83.0, 32: 84.0, 33: 81.0}}.items():
    rows += [(key, ts, spikes.get(i, 50.0), "ok") for i, ts in enumerate(slots)]
measurement = pd.DataFrame(rows, columns=["sns_key", "ts", "value", "quality_flag"])
measurement.loc[(measurement["sns_key"] == "SNS-900001") & (measurement["ts"] == "2028-01-12 12:00"), ["value", "quality_flag"]] = [99.0, "suspect"]  # a high value that does not count
measurement.head(8)
```

Step 1. The alarms. Only ok samples count, so the suspect sample of 12 January raises nothing. Two runs of high samples with one ok sample between them are one alarm, because the gap is within the merge gap of the sensor (a column of the sensor table). A single sample over 80 on the second sensor is too short for its minimum duration of half an hour; a run of four samples is long enough. A run that reaches the critical limit is critical, the others are warnings.

```python
alarm = recompute_alarms(measurement, sensor, context=ctx)
alarm[["sns_key", "net_key", "zone_key", "alarm_type", "raised_ts", "cleared_ts", "severity", "peak_value", "samples"]]
```

Step 2. The incidents. A load alarm that starts within the merge gap of the clearing of the previous one on the same element is the same incident; the gap is a parameter of the function (60 hours for load alarms, a proposed value) and is named here, so the two alarms of the first sensor on 10 January are one incident and the one on 14 January is another; the second sensor is another element and has an incident of its own.

```python
gap_hours = 60.0
alarm["incident"] = incident_groups(alarm, merge_gap_hours={"load_high": gap_hours, "default": 8.0}, context=ctx)
alarm[["net_key", "raised_ts", "incident"]]
```

Step 3. The counts by zone, type, severity and month, and the background rate of alarms per month over the window that is passed in.

```python
summary = alarm_summary(alarm, first_month="2028-01", last_month="2028-03", context=ctx)
summary.counts, summary.background
```

Step 4. The tickets. One ticket covers a whole incident, so most alarms have no ticket of their own; the incident columns show how many tickets each incident has.

```python
first = alarm.iloc[0]
ticket_alarm = pd.DataFrame({"sns_key": [first["sns_key"]], "raised_ts": [first["raised_ts"]], "link_type": ["trigger"], "tkt_key": ["TKT-900001"]})
service_ticket = pd.DataFrame({"tkt_key": ["TKT-900001"]})
linked = alarm_ticket_link(alarm.drop(columns="incident"), ticket_alarm, service_ticket, context=ctx)
linked[["sns_key", "raised_ts", "linked", "tkt_key", "incident", "incident_tickets"]]
```

Check. The alarms are recomputed another way: only ok samples are used, the whole alarm table is rebuilt with a plain run and merge loop (raise, clear, severity, peak, samples), the incidents are counted from the gaps in hours, the tickets of an incident come from the link table, and the counts add up to the number of alarms and the one link.

```python
ok = measurement[measurement["quality_flag"] == "ok"]
rows = []
for s in sensor.itertuples():
    high = ok[(ok["sns_key"] == s.sns_key) & (ok["value"] > s.limit_high)].sort_values("ts")
    run = (high["ts"].diff() != pd.Timedelta(seconds=s.interval_s)).cumsum()       # a new run when the next high sample is not one interval later
    merged: list[dict] = []
    for r in high.groupby(run).agg(raised=("ts", "first"), last=("ts", "last"), peak=("value", "max"), n=("value", "size")).itertuples():
        cleared = r.last + pd.Timedelta(seconds=s.interval_s)
        if merged and r.raised - merged[-1]["cleared"] <= pd.Timedelta(seconds=s.alarm_merge_gap_s):
            merged[-1].update(cleared=cleared, peak=max(merged[-1]["peak"], r.peak), n=merged[-1]["n"] + r.n)
        else:
            merged.append({"raised": r.raised, "cleared": cleared, "peak": r.peak, "n": r.n})
    rows += [(s.sns_key, m["raised"], m["cleared"], "critical" if m["peak"] >= s.limit_high_crit else "warning", m["peak"], m["n"])
             for m in merged if (m["cleared"] - m["raised"]).total_seconds() >= s.alarm_min_duration_s]
expected = pd.DataFrame(rows, columns=["sns_key", "raised_ts", "cleared_ts", "severity", "peak_value", "samples"]).sort_values(["sns_key", "raised_ts"]).reset_index(drop=True)
pd.testing.assert_frame_equal(alarm[expected.columns].reset_index(drop=True), expected, check_dtype=False)
by_time = alarm.sort_values(["net_key", "raised_ts"])
previous_cleared = by_time.groupby("net_key")["cleared_ts"].shift()
starts_new = previous_cleared.isna() | ((by_time["raised_ts"] - previous_cleared) > pd.Timedelta(hours=gap_hours))
assert alarm["incident"].nunique() == starts_new.sum()
assert summary.counts["n_alarms"].sum() == len(alarm)
assert linked["linked"].sum() == len(ticket_alarm)
tickets_per_incident = ticket_alarm.merge(alarm[["sns_key", "raised_ts", "incident"]], on=["sns_key", "raised_ts"]).groupby("incident")["tkt_key"].nunique()
assert (linked["incident_tickets"] == linked["incident"].map(tickets_per_incident).fillna(0)).all()
assert (summary.background["per_month"] == (summary.background["n_alarms"] / summary.background["months"]).round(4)).all()
```
