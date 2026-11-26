# From the open tenders to the price per metre

Notebook `notebooks/tender-pipeline-and-price-per-metre.ipynb` of halvaro-delivery, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** Which tenders are open on a day, how often were decided tenders won, and what does the estimate of a project cost per route metre once the contingency has been advised from the delay record?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `open_tenders` | you need the open opportunities in a tender stage on a day, with their profile, bid deadline and days to the deadline. | [open_tenders](../../halvaro-delivery/references/open_tenders.md) |
| `win_rate` | you need the win rate (won over decided) by period of the decision date and, if wanted, by customer tier. | [win_rate](../../halvaro-delivery/references/win_rate.md) |
| `estimate_amount_per_metre` | you need the estimate amount per route metre by cost code and category for each project, from the lines of estimate_bridge. | [estimate_amount_per_metre](../../halvaro-delivery/references/estimate_amount_per_metre.md) |
| `contingency_advice` | you need advice on the contingency percentage of a set of projects from the ground share of delay days and the schedule overrun, net of the contingency the tender estimates already carry. | [contingency_advice](../../halvaro-delivery/references/contingency_advice.md) |

## Steps

A tender pipeline starts with the open opportunities. `open_tenders` lists those in a tender stage on a day, `win_rate` says how many decided ones were won, `estimate_amount_per_metre` turns the lines of an estimate into an amount per route metre, and `contingency_advice` advises the contingency percentage from the ground share of the delay days and the schedule overrun, net of what the estimate already carries. The notebook builds its own small frames, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.delivery import contingency_advice, estimate_amount_per_metre, open_tenders, win_rate

ctx = Context(stage="month12", role="analyst")
opportunity = pd.DataFrame({
    "opp_key": ["OPP-900001", "OPP-900002", "OPP-900003", "OPP-900004"], "name": ["Tender A", "Tender B", "Tender C", "Tender D"], "cus_key": ["CUS-900001"] * 4,
    "stage": ["tender", "won", "lost", "withdrawn"], "is_open": [True, False, False, False], "project_type": ["district_heating"] * 4, "country": ["DK"] * 4,
    "soil_class": ["clay"] * 4, "route_length_m": [1200.0, 800.0, 500.0, 300.0], "zone_key": ["ZONE-0001"] * 4,
    "bid_deadline": ["2025-06-30", "2025-03-01", "2025-02-01", "2025-01-15"], "requirements": [None] * 4, "carbon_limit_kgco2e_per_m": [None] * 4,
    "created_date": ["2025-01-15", "2025-01-10", "2025-01-05", "2025-01-02"], "decision_date": [None, "2025-03-01", "2025-04-02", "2025-05-01"]})
opportunity[["opp_key", "stage", "is_open", "bid_deadline"]]
```

Step 1. The tenders that are open on 1 June 2025, with the days left to the bid deadline.

```python
pipeline = open_tenders(opportunity, "2025-06-01", context=ctx)
pipeline[["opp_key", "bid_deadline", "days_to_deadline"]]
```

Step 2. The win rate is won over decided. A withdrawn tender is counted separately and is not decided.

```python
customer = pd.DataFrame({"cus_key": ["CUS-900001"], "tier": ["key"]})
rates = win_rate(opportunity, customer, by_tier=False, context=ctx)
rates
```

Step 3. The lines of the estimate of a project, as an amount per route metre by cost code.

```python
lines = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "type": ["tender"] * 3, "cst_key": ["CST-100", "CST-200", "CST-830"], "category": ["civil", "electrical", "contingency"],
                      "amount": [95.0, 50.0, 5.0], "currency": ["DKK"] * 3})
project = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [1000.0]})
per_metre = estimate_amount_per_metre(lines, project, context=ctx)
per_metre[["cst_key", "amount", "per_metre"]]
```

Step 4. The contingency advice from the delay record. The ground share of the delay days and the schedule overrun give a gross percent; the percent already in the estimate comes off.

```python
overrun = pd.DataFrame({"measure": ["schedule"], "n": [4], "n_legacy": [1], "q75": [0.2]})
shares = pd.DataFrame({"view": ["all_events", "all_events"], "cause_code": ["ground_conditions", "weather"], "days": [30, 10]})
advice = contingency_advice(overrun, shares, lines, context=ctx)
advice.rows
```

Check. The open tenders are exactly the opportunities with an open flag, the win rate is won over won plus lost, the amounts per metre add up to the estimate divided by the length, and the net percent is the gross percent less the percent already in the estimate (the library rounds percents to three decimals).

```python
assert set(pipeline["opp_key"]) == set(opportunity.loc[opportunity["is_open"], "opp_key"])
count = opportunity["stage"].value_counts()
assert rates.loc[0, "win_rate"] == count["won"] / (count["won"] + count["lost"])
assert abs(per_metre["per_metre"].sum() - lines["amount"].sum() / project["route_length_m"].iloc[0]) < 1e-9
value = advice.rows.set_index("measure")["value"]
assert abs(value["net_percent"] - (value["gross_percent"] - value["existing_percent"])) < 0.002
assert abs(value["existing_percent"] - 100 * lines.loc[lines["cst_key"] == "CST-830", "amount"].sum() / lines["amount"].sum()) < 0.002
```
