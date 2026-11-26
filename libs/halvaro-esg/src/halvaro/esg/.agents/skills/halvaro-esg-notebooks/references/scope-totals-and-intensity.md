# From emission lines to scope totals and intensity

Notebook `notebooks/scope-totals-and-intensity.ipynb` of halvaro-esg, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How do emission lines of a year become totals per scope, tonnes per employee and per revenue, and a list of the scope 3 categories that have no lines?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `scope_totals` | you need the scope 1, scope 2 and scope 3 totals of one year on one basis, per entity, for one entity or for all. | [scope_totals](../../halvaro-esg/references/scope_totals.md) |
| `intensity` | you need the emissions in tonnes CO2e per employee and per DKK million of revenue, per legal entity and for the company. | [intensity](../../halvaro-esg/references/intensity.md) |
| `scope3_coverage` | you need to see which of the 15 scope 3 categories have lines and the reason for each absent one. | [scope3_coverage](../../halvaro-esg/references/scope3_coverage.md) |

## Steps

The ledger of emissions has one line per entity, month, scope and category. `scope_totals` rolls the lines up to totals per scope, `intensity` divides the total by employees and revenue, and `scope3_coverage` shows which of the 15 scope 3 categories have lines and the reason for each one without. Scope 2 is reported on two bases, location and market, and the notebook shows both. It builds its own small frames, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.esg import intensity, scope3_coverage, scope_totals

ctx = Context(stage="month12", role="analyst")
cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
lines = pd.DataFrame([
    ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100000.0, False, None),
    ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50000.0, False, None),
    ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 20000.0, False, None),
    ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.11", 30000.0, False, None)], columns=cols)
lines
```

Step 1. The totals of 2025 per entity and for all entities, one column per scope, in kg CO2e.

```python
totals = scope_totals(lines, 2025, context=ctx)
totals.value[["le_key", "scope1", "scope2_location", "scope2_market", "scope3", "total_location_based", "total_market_based"]]
```

Step 2. The intensity, in tonnes: tonnes per employee and per DKK million of revenue, from the totals and a small table of the reporting basis.

```python
basis = pd.DataFrame({"le_key": ["LE-900001", "GROUP-900001"], "scope": ["entity", "group"], "fiscal_year": [2025, 2025],
                      "revenue": [50000000.0, 50000000.0], "average_employees": [100, 100], "currency": ["DKK", "DKK"]})
ratios = intensity(lines, basis, 2025, context=ctx)
ratios.value[["le_key", "employees", "revenue_dkk_m", "total_location_t", "t_per_employee_location", "t_per_dkk_m_location"]]
```

Step 3. The scope 3 categories with and without lines. A category without lines needs a reason: a screening decision, or a note that a decision is needed.

```python
coverage = scope3_coverage(lines, {"3.12": "screened out: not relevant in this example"}, 2025, context=ctx)
coverage.value.loc[coverage.value["ghg_category"].isin(["3.11", "3.12", "3.13"]), ["ghg_category", "present", "reason"]]
```

Check. The totals equal a plain pandas sum of the lines, the intensity equals the total divided by the employees and by the revenue, and the number of categories present equals the categories that have lines.

```python
kg = lines.groupby("scope")["kgco2e"].sum()
row = totals.value.iloc[0]
assert float(row["scope1"]) == kg[1] and float(row["scope3"]) == kg[3]
assert float(row["total_location_based"]) == float(row["scope1"]) + float(row["scope2_location"]) + float(row["scope3"])
entity = ratios.value.iloc[0]
assert float(entity["total_location_t"]) == float(row["total_location_based"]) / 1000
assert abs(float(entity["t_per_employee_location"]) - float(entity["total_location_t"]) / float(entity["employees"])) < 1e-9
assert abs(float(entity["t_per_dkk_m_location"]) - float(entity["total_location_t"]) / float(entity["revenue_dkk_m"])) < 1e-9
assert int(coverage.value["present"].sum()) == lines["ghg_category"].nunique()
```
