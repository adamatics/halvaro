# Strained zones and the spares for a winter plan

Notebook `notebooks/strained-zones-and-spares-for-a-winter-plan.ipynb` of halvaro-grid, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** Which zones carry strained elements, how many critical spares did the last winter use, and does the stock on the planning day, with the lead time of the supplier, carry the spares through a similar winter?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `element_peak_load` | you need the peak load in percent of each element that has its own load sensor, with the completeness that says whether the peak can be trusted. | [element_peak_load](../../halvaro-grid/references/element_peak_load.md) |
| `strained_elements` | you need to know which in service elements are strained by load or by age or condition class, with the reasons. | [strained_elements](../../halvaro-grid/references/strained_elements.md) |
| `zone_strain_summary` | you need the counts of in service and strained elements by zone and customer, with the zone area. | [zone_strain_summary](../../halvaro-grid/references/zone_strain_summary.md) |
| `critical_spares_issued` | you need the issues of the critical spare items on tickets, with the units used and the first and last day of use. | [critical_spares_issued](../../halvaro-grid/references/critical_spares_issued.md) |

## Also uses (other libraries)

| Library | Functions |
|---|---|
| halvaro-delivery | `stock_on`, `lead_time_on` |

## Steps

A winter plan needs a view of the grid and a view of the warehouse, side by side. The grid half is in halvaro-grid: `element_peak_load` gives the peak load of every element with a load sensor, `strained_elements` marks the elements strained by load or by age, `zone_strain_summary` counts them by zone and `critical_spares_issued` says how many units of the critical spares the tickets used. The warehouse half is in halvaro-delivery: `stock_on` gives the stock of a day and `lead_time_on` the lead time of the supplier on that day. The two halves meet in a few lines of pandas at the end. The notebook builds its own small frames with invented values, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.delivery import lead_time_on, stock_on
from halvaro.grid import critical_spares_issued, element_peak_load, strained_elements, zone_strain_summary

ctx = Context(stage="month12", role="analyst")
winter = ("2025-12-02", "2026-03-01")  # the last winter
planning_day = "2026-09-01"
min_completeness = 0.9  # the share of the days with data that makes a peak valid (proposed)
load_limit = 90.0  # the peak percent that counts as strained by load (proposed)
next_winter = "2026-12-01"
days = pd.date_range(winter[0], winter[1]).strftime("%Y-%m-%d")
grid_element = pd.DataFrame({
    "net_key": [f"NET-90000{i}" for i in range(1, 7)], "element_type": ["transformer_station"] * 4 + ["cable"] * 2, "status": ["in_service"] * 6,
    "install_year": [2012, 2015, 1975, 2010, 2016, 2018], "condition_class": ["B", "B", "C", "D", "B", "B"], "cus_key": [None] * 6,
    "zone_key": ["ZONE-0001", "ZONE-0001", "ZONE-0002", "ZONE-0002", "ZONE-0002", "ZONE-0003"], "commissioned_date": [None] * 6})
supply_zone = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0002", "ZONE-0003"], "area_km2": [4.0, 10.0, 2.6]})
# four elements have a load sensor; the daily maximum cycles over five values from the base value up
sensor = pd.DataFrame({"sns_key": [f"SNS-90000{i}" for i in range(1, 5)], "net_key": [f"NET-90000{i}" for i in (1, 2, 4, 6)], "rated_value": [100.0] * 4,
                       "install_date": ["2019-01-01"] * 4, "sensor_type": ["load_percent"] * 4})
base = {"SNS-900001": 70.0, "SNS-900002": 88.0, "SNS-900003": 60.0, "SNS-900004": 91.0}
daily = pd.DataFrame([(s, d, base[s] + i % 5, 100.0 if s != "SNS-900004" else 50.0) for s in base for i, d in enumerate(days)], columns=["sns_key", "date", "max", "availability_pct"])
grid_element
```

Step 1. The peak load of each element with a sensor, in the window of the winter. The sensor of NET-900006 delivered half of its samples, so its peak is listed but is not valid; the elements NET-900003 and NET-900005 have no sensor and are not listed at all.

```python
peaks = element_peak_load(sensor, daily, window=winter, min_completeness=min_completeness, context=ctx)
peaks[["net_key", "peak_percent", "days", "completeness", "valid"]]
```

Step 2. Which elements are strained on the planning day. An element is strained by load when its valid peak reaches the load limit (a parameter of the function, 90 percent proposed), and by age when its condition class is a bad one or it is old enough. An element with no valid peak and no age strain is neither strained nor not strained: the answer is unknown, and the count keeps it apart.

```python
strained = strained_elements(peaks, grid_element, as_of=planning_day, load_percent=load_limit, context=ctx)
strained[["net_key", "zone_key", "peak_percent", "load_strained", "age_strained", "strained", "reasons"]]
```

```python
by_zone = zone_strain_summary(strained, supply_zone, context=ctx)
by_zone[["zone_key", "n_elements", "n_strained", "n_strained_unknown", "n_load_strained", "n_age_strained", "strained_per_km2"]]
```

Step 3. The spares side. Three items are on the tickets of last winter: two critical ones and one that is not critical and is left out. A critical item that no ticket used (ITM-900003) is listed with zero units. A line from before the winter is left out by the window.

```python
ticket_item_use = pd.DataFrame({
    "tkt_key": [f"TKT-90000{i}" for i in range(1, 8)], "itm_key": ["ITM-900001", "ITM-900001", "ITM-900002", "ITM-900001", "ITM-900004", "ITM-900002", "ITM-900001"],
    "qty": [2.0, 1.0, 4.0, 3.0, 9.0, 2.0, 5.0], "used_on": ["2025-12-12", "2026-01-08", "2026-01-27", "2026-02-03", "2026-02-10", "2026-02-19", "2025-10-04"], "uom": ["pcs"] * 7})
item = pd.DataFrame({"itm_key": [f"ITM-90000{i}" for i in range(1, 5)], "critical": [True, True, True, False]})
spares = critical_spares_issued(ticket_item_use, item, window=winter, context=ctx)
spares[["itm_key", "uom", "units", "n_tickets", "first_used", "last_used"]]
```

Step 4. The warehouse side on the planning day: what is on hand, what is reserved by open reservations, and the lead time of the supplier. The next winter starts on 1 December, so the weeks from the planning day to that day are what a new order can use.

```python
stock_movement = pd.DataFrame({"site_key": ["SIT-900001"] * 6, "itm_key": ["ITM-900001", "ITM-900001", "ITM-900002", "ITM-900002", "ITM-900003", "ITM-900003"],
                               "movement_date": ["2026-03-02", "2026-06-16", "2026-03-02", "2026-07-02", "2026-04-02", "2026-12-16"], "qty": [8.0, -2.0, 6.0, -1.0, 3.0, 4.0]})
open_reservations = pd.DataFrame({"site_key": ["SIT-900001"], "itm_key": ["ITM-900001"], "qty_open": [1.0]})
on_the_day = stock_on(stock_movement, planning_day, reservation_open=open_reservations, context=ctx)
lead_time = pd.DataFrame({"sup_key": ["SUP-900001"] * 3, "itm_key": ["ITM-900001", "ITM-900002", "ITM-900002"], "valid_from": ["2025-01-01"] * 2 + ["2026-05-07"],
                          "valid_to": [None, "2026-05-06", None], "lead_time_weeks": [6.0, 10.0, 16.0]})
lead = lead_time_on(lead_time, planning_day, context=ctx)
weeks_to_winter = (pd.Timestamp(next_winter) - pd.Timestamp(planning_day)).days / 7
on_the_day[["itm_key", "on_hand", "reserved", "available", "source"]], lead[["itm_key", "lead_time_weeks", "previous_weeks", "change_weeks"]], weeks_to_winter
```

Step 5. The two halves meet. The plan assumes that a similar winter needs the units of the last one; that is the assumption of this notebook, not a rule of the library. One site and one supplier here, so the items join on the item key. For each critical item: the units of last winter against what is available, the shortfall, and whether an order placed on the planning day would come too late for the winter. The strained zones above say where the crews will be needed; they do not change the arithmetic of the spares.

```python
plan = (spares[["itm_key", "units"]].rename(columns={"units": "last_winter_units"})
        .merge(on_the_day[["itm_key", "available"]], on="itm_key", how="left").merge(lead[["itm_key", "lead_time_weeks"]], on="itm_key", how="left"))
plan["available"] = plan["available"].fillna(0.0)
plan["shortfall"] = (plan["last_winter_units"] - plan["available"]).clip(lower=0)
plan["too_late"] = (plan["shortfall"] > 0) & (plan["lead_time_weeks"] > weeks_to_winter)  # a shortfall that an order today cannot close in time
plan
```

Check. Each half is recomputed another way from the frames above: the peak as the highest daily maximum of the sensor, the strained flag from the two flags, the zone counts with a group by, the units of the spares with a filter on the window, the stock as the sum of the movements to the day less the reservations, and the lead time from the row that is valid on the day.

```python
top = daily.groupby("sns_key")["max"].max()
assert (peaks.set_index("sns_key")["peak_percent"] == top).all()
share = daily.groupby("sns_key")["availability_pct"].mean() / 100
assert (peaks.set_index("sns_key")["valid"] == (share >= min_completeness)).all()
by_net = peaks.set_index("net_key")
known = strained["load_strained"].notna()
by_strain = strained.set_index("net_key")
valid_nets = by_net.index[by_net["valid"]]
assert (by_strain.loc[valid_nets, "load_strained"].astype(bool) == (by_net.loc[valid_nets, "peak_percent"] >= load_limit)).all()
assert by_strain.loc[by_net.index[~by_net["valid"]], "load_strained"].isna().all()  # no valid peak: unknown, not "not strained"
assert (strained.loc[known, "strained"] == (strained.loc[known, "load_strained"].astype(bool) | strained.loc[known, "age_strained"].astype(bool))).all()
assert (strained["age_strained"] == (strained["condition_class"].isin(["D", "E"]) | (strained["age_years"] >= 40.0))).all()
counts = strained.groupby("zone_key")["strained"].apply(lambda s: int((s == True).sum()))  # noqa: E712
assert (by_zone.set_index("zone_key")["n_strained"] == counts).all()
assert (by_zone.groupby("zone_key")["n_elements"].sum() == grid_element.groupby("zone_key").size()).all()
critical = set(item.loc[item["critical"], "itm_key"])
used = ticket_item_use[ticket_item_use["itm_key"].isin(critical) & ticket_item_use["used_on"].between(*winter)].groupby("itm_key")["qty"].sum()
assert (spares.set_index("itm_key")["units"] == used.reindex(spares["itm_key"]).fillna(0.0).to_numpy()).all()
moved = stock_movement[stock_movement["movement_date"] <= planning_day].groupby("itm_key")["qty"].sum()
reserved = open_reservations.set_index("itm_key")["qty_open"].reindex(moved.index).fillna(0.0)
assert (on_the_day.set_index("itm_key")["available"] == moved - reserved).all()
valid_row = lead_time[(lead_time["valid_from"] <= planning_day) & (lead_time["valid_to"].isna() | (lead_time["valid_to"] >= planning_day))]
assert (lead.set_index("itm_key")["lead_time_weeks"] == valid_row.set_index("itm_key")["lead_time_weeks"]).all()
assert (plan["shortfall"] == plan["last_winter_units"].where(plan["last_winter_units"] > plan["available"], plan["available"]) - plan["available"]).all()
late_by_dates = (pd.Timestamp(next_winter) - pd.Timestamp(planning_day)) < pd.to_timedelta(plan["lead_time_weeks"] * 7, unit="D")
assert (plan["too_late"] == ((plan["shortfall"] > 0) & late_by_dates)).all()
```
