# From the estimate to the margin and the cost still to come

Notebook `notebooks/estimate-to-margin-and-cost-to-completion.ipynb` of halvaro-delivery, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** For running projects, how does the latest forecast estimate become the percent complete, the revenue and the loss provision, the two margins and the cost still to come, and what does the portfolio come to per currency?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `estimate_bridge` | you need the amounts by cost code of the tender, budget, forecast and final estimate of each project, with the stored totals and the versions that are missing. | [estimate_bridge](../../halvaro-delivery/references/estimate_bridge.md) |

## Also uses (other libraries)

| Library | Functions |
|---|---|
| halvaro-core | `guarded_sum`, `format_money` |
| halvaro-finance | `percent_complete`, `revenue_recognised`, `loss_provision`, `project_margin`, `cost_to_completion` |

## Steps

The task starts in delivery and ends in finance. `estimate_bridge` of halvaro-delivery gives the latest estimate of each project and type, checked against its lines; the forecast total is the estimate at completion (EAC). Five functions of halvaro-finance take it from there: `percent_complete`, `revenue_recognised` and `loss_provision` turn cost to date over EAC into revenue, `project_margin` names the two margins and `cost_to_completion` says what is still to be spent. Two functions of halvaro-core keep the money honest: `guarded_sum` refuses to add two currencies and `format_money` writes an amount with its currency. The notebook builds its own small frames with invented amounts, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context, SumGuardError, format_money, guarded_sum
from halvaro.delivery import estimate_bridge
from halvaro.finance import cost_to_completion, loss_provision, percent_complete, project_margin, revenue_recognised

ctx = Context(stage="month12", role="analyst")
cap = 0.95  # the largest share a running project may show; in your own work, pass the company's config value projects.poc_cap_before_completion
versions = pd.DataFrame({
    "prj_key": ["PRJ-900001", "PRJ-900001", "PRJ-900001", "PRJ-900002", "PRJ-900002", "PRJ-900003", "PRJ-900003"],
    "estimate_version": [1, 2, 3, 1, 2, 1, 2], "type": ["tender", "forecast", "forecast", "tender", "forecast", "tender", "forecast"],
    "date": ["2025-01-10", "2025-09-01", "2026-02-15", "2025-03-10", "2026-02-20", "2025-04-02", "2026-02-10"], "currency": ["DKK"] * 5 + ["EUR"] * 2})
lines = pd.DataFrame({
    "prj_key": ["PRJ-900001"] * 6 + ["PRJ-900002"] * 4 + ["PRJ-900003"] * 4,
    "estimate_version": [1, 1, 2, 2, 3, 3, 1, 1, 2, 2, 1, 1, 2, 2],
    "cst_key": ["CST-100", "CST-200"] * 7,
    "amount": [800_000.0, 400_000.0, 840_000.0, 420_000.0, 900_000.0, 450_000.0, 560_000.0, 380_000.0, 700_000.0, 500_000.0, 70_000.0, 50_000.0, 90_000.0, 60_000.0]})
versions["total_cost"] = [1_200_000.0, 1_260_000.0, 1_350_000.0, 940_000.0, 1_200_000.0, 120_000.0, 150_000.0]  # the totals stored with the versions; the bridge checks them against the lines
cost_code = pd.DataFrame({"cst_key": ["CST-100", "CST-200"], "category": ["civil", "electrical"]})
versions
```

Step 1. The bridge. Per project and type the highest version counts, so PRJ-900001 is estimated at its third version, not the second. The stored total of each version is compared with the sum of its lines; `difference` should be nothing here.

```python
bridge = estimate_bridge(versions, lines, cost_code, context=ctx)
bridge.totals[["prj_key", "type", "estimate_version", "currency", "total_cost", "line_sum", "difference"]]
```

Step 2. The finance rows of one month. The EAC of each project is its latest forecast total from the bridge; the contract values, the cost to date and the committed cost are invented. None of the three projects has ended, so each is running.

```python
eac = bridge.totals[bridge.totals["type"] == "forecast"].set_index("prj_key")["total_cost"]
pf = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "period": ["2026-03"] * 3, "currency": ["DKK", "DKK", "EUR"],
                   "contract_value": [1_500_000.0, 1_000_000.0, 200_000.0], "actual_cost": [675_000.0, 600_000.0, 148_000.0], "committed_cost": [200_000.0, 150_000.0, 0.0]})
pf["eac"] = pf["prj_key"].map(eac)
pf
```

Step 3. Percent complete is cost to date over EAC, limited by the cap; no project has an end date yet, so `actual_end` is empty. Revenue follows the percent. A project whose EAC is above its contract value carries a provision for the expected loss, scaled by how much of the work is still to do.

```python
no_end = {}
pf["percent_complete"] = percent_complete(pf, no_end, cap=cap, context=ctx)
pf["revenue_recognised"] = revenue_recognised(pf, no_end, cap=cap, context=ctx)
pf["loss_provision"] = loss_provision(pf, no_end, cap=cap, context=ctx)
pf[["prj_key", "currency", "eac", "percent_complete", "revenue_recognised", "loss_provision"]]
```

Step 4. Two margins, never one: the margin to date on the revenue so far, and the margin forecast at completion on the contract. They differ when a loss provision is booked: the margin to date takes the provision off, so PRJ-900002 shows a worse margin to date than at completion. Then the cost still to come, with the part that is already committed shown apart.

```python
margins = project_margin(pf, context=ctx)
to_come = cost_to_completion(pf, list(pf["prj_key"]), "2026-03", context=ctx)
margins.merge(to_come[["prj_key", "cost_to_completion", "committed_cost", "uncommitted"]], on="prj_key")
```

Step 5. The portfolio. A total of the cost to come over all three projects would add kroner to euro, and `guarded_sum` refuses to; grouped by currency it gives one line per currency.

```python
try:
    guarded_sum(to_come, "cost_to_completion")
except SumGuardError as refused:
    print("refused:", refused)
per_currency = guarded_sum(to_come, "cost_to_completion", by="currency")
labels = [format_money(row.cost_to_completion, row.currency) for row in per_currency.itertuples()]
per_currency, labels
```

Check. Every figure is recomputed another way: the EAC from the lines of the highest forecast version, the percent as cost over EAC limited by the cap, the revenue and the margins from their definitions, the cost to come as EAC less cost to date, the portfolio with a plain group by, and the written amounts from a format string.

```python
latest = versions[versions["type"] == "forecast"].sort_values("estimate_version").groupby("prj_key").tail(1)
eac_from_lines = lines.merge(latest[["prj_key", "estimate_version"]], on=["prj_key", "estimate_version"]).groupby("prj_key")["amount"].sum()
assert (pf.set_index("prj_key")["eac"] == eac_from_lines).all()
fraction = (pf["actual_cost"] / pf["eac"]).clip(upper=cap)
assert ((pf["percent_complete"] - fraction * 100).abs() < 0.01).all()
assert ((pf["revenue_recognised"] - pf["contract_value"] * fraction).abs() <= 0.01).all()
expected_loss = (pf["eac"] - pf["contract_value"]).clip(lower=0)
assert ((pf["loss_provision"] - expected_loss * (1 - fraction)).abs() <= 0.01).all()
assert ((margins["forecast_margin_pct"] - (pf["contract_value"] - pf["eac"]) / pf["contract_value"] * 100).abs() < 0.01).all()
assert ((margins["margin_pct"] - (pf["revenue_recognised"] - pf["actual_cost"] - pf["loss_provision"]) / pf["revenue_recognised"] * 100).abs() < 0.01).all()
assert (to_come["cost_to_completion"] == pf["eac"] - pf["actual_cost"]).all()
assert (to_come["uncommitted"] == to_come["cost_to_completion"] - pf["committed_cost"]).all()
assert (per_currency.set_index("currency")["cost_to_completion"] == to_come.groupby("currency")["cost_to_completion"].sum()).all()
assert labels == [f"{c} {v:,.0f}" for c, v in zip(per_currency["currency"], per_currency["cost_to_completion"])]
```
