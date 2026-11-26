# A restated year, counted once

Notebook `notebooks/restated-emission-lines.ipynb` of halvaro-esg, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** When emission lines of a year were restated with a new factor, how do the lines pass the rule checks, why does a plain total count a restated line together with its original, what is the total on the current basis, and how much did the restatement move it?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `validate_lines` | you need the rule violations of the emission lines, such as a wrong kg value, an unknown or invalid factor or a wrong method. | [validate_lines](../../halvaro-esg/references/validate_lines.md) |
| `assert_no_double_count` | you need to confirm that a frame of emission lines holds no original together with the restated line that replaces it, before you total it. | [assert_no_double_count](../../halvaro-esg/references/assert_no_double_count.md) |
| `current_basis` | you need the emission lines without the superseded originals, so that a total counts every restatement once. | [current_basis](../../halvaro-esg/references/current_basis.md) |
| `restatement_pairs` | you need each restated emission line next to the original it replaces, with the change in kg. | [restatement_pairs](../../halvaro-esg/references/restatement_pairs.md) |
| `restatement_bridge` | you need the change from first booked to restated emissions of one year, by scope, category and factor family. | [restatement_bridge](../../halvaro-esg/references/restatement_bridge.md) |

## Steps

A restated line does not overwrite its original: both stay in the table, the original flagged as superseded. That keeps the history, and it makes a careless total wrong. `validate_lines` checks the rules of every line, `assert_no_double_count` refuses a frame that holds an original together with its restatement, `current_basis` leaves the superseded originals out, `restatement_pairs` sets each restated line next to its original and `restatement_bridge` sums the change by scope, category and factor family. The notebook builds its own small frames with invented values, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context, FrameError
from halvaro.esg import assert_no_double_count, current_basis, restatement_bridge, restatement_pairs, validate_lines

ctx = Context(stage="month12", role="analyst")
# two factor sets: the first valid through 2025, the second published for 2026 and used to restate the lines of 2025
factor = pd.DataFrame({
    "efac_key": ["EF-900001", "EF-900002", "EF-900003", "EF-900004"], "category": ["gas", "gas", "diesel", "diesel"], "carrier": ["natural_gas", "natural_gas", "diesel", "diesel"],
    "region": ["DE"] * 4, "method": [None] * 4, "kgco2e_per_unit": [0.2, 0.19, 2.68, 2.47], "valid_from": ["2024-01-01", "2026-01-01", "2024-01-01", "2026-01-01"],
    "valid_to": ["2025-12-31", None, "2025-12-31", None], "factor_set": ["FS-A", "FS-B", "FS-A", "FS-B"], "synthetic": [True] * 4, "verify_note": ["VERIFY first", "VERIFY second"] * 2})
lines = pd.DataFrame({
    "le_key": ["LE-900001"] * 7, "period": ["2025-01", "2025-01", "2025-02", "2025-02", "2025-02", "2025-03", "2025-03"], "scope": [1] * 7,
    "category": ["gas", "gas", "gas", "diesel", "diesel", "gas", "gas"], "line_no": [1, 2, 1, 1, 2, 1, 2],
    "quantity": [1000.0, 1000.0, 1200.0, 500.0, 500.0, 900.0, 900.0], "efac_key": ["EF-900001", "EF-900002", "EF-900001", "EF-900003", "EF-900004", "EF-900001", "EF-900002"],
    "method": [None] * 7, "ghg_category": ["1"] * 7, "restated_from_period": [None, "2026-01", None, None, "2026-01", None, "2026-01"],
    "supersedes_line_no": [None, 1, None, None, 1, None, 1], "is_superseded": [True, False, False, True, False, True, False],
    "ref_type": ["SITE"] * 7, "ref_key": ["SITE-900001"] * 7})
per_unit = lines["efac_key"].map(factor.set_index("efac_key")["kgco2e_per_unit"])
lines["kgco2e"] = (lines["quantity"] * per_unit).round(3)
lines[["period", "category", "line_no", "quantity", "efac_key", "kgco2e", "restated_from_period", "is_superseded"]]
```

Step 1. The rules. Each kg value must equal quantity times factor, a restated line must name its original, and a restated line must use a factor that was not valid in its period (otherwise nothing was restated). An empty frame means no violation.

```python
violations = validate_lines(lines, factor, context=ctx)
violations
```

Step 2. The trap. The table holds the originals and the restatements, so a plain sum counts the same line twice (the original and the restated one), and the guard refuses the table for that reason.

```python
plain_total = float(lines["kgco2e"].sum())
try:
    assert_no_double_count(lines, context=ctx)
except FrameError as refused:
    print("refused:", refused)
plain_total
```

Step 3. The current basis keeps the restated lines and drops the originals they replace. It passes the guard, and its total counts every change once.

```python
basis = current_basis(lines, context=ctx)
passes = assert_no_double_count(basis, context=ctx)
basis_total = float(basis["kgco2e"].sum())
passes, len(lines), len(basis), basis_total
```

Step 4. What the restatement moved. The pairs put each restated line next to its original; the bridge sums the change per scope, category and factor family and gives it in percent of the first booked kg.

```python
pairs = restatement_pairs(lines, context=ctx)
bridge = restatement_bridge(lines, factor, 2025, context=ctx)
pairs[["period", "category", "efac_original", "efac_restated", "kg_original", "kg_restated", "delta_kg"]], bridge[["category", "family", "n_lines", "kg_first_booked", "kg_restated", "delta_kg", "delta_percent"]]
```

Check. The totals are recomputed from the flags and from quantity times factor: the current basis is the lines that are not superseded, the first booked total is the lines that are not restatements, and the bridge moves one into the other. The plain total exceeds the current basis by exactly the superseded kg.

```python
first_booked = lines.loc[lines["restated_from_period"].isna(), "kgco2e"].sum()
superseded = lines.loc[lines["is_superseded"], "kgco2e"].sum()
assert abs(basis_total - lines.loc[~lines["is_superseded"], "kgco2e"].sum()) < 0.001
assert abs(plain_total - basis_total - superseded) < 0.001
assert abs(bridge["kg_first_booked"].sum() - superseded) < 0.001
assert abs(bridge["delta_kg"].sum() - pairs["delta_kg"].sum()) < 0.001
assert abs(basis_total - first_booked - pairs["delta_kg"].sum()) < 0.001
assert len(violations) == 0
by_category = pairs.groupby("category")[["kg_original", "kg_restated"]].sum()
assert ((bridge.set_index("category")["delta_percent"] - (by_category["kg_restated"] - by_category["kg_original"]) / by_category["kg_original"] * 100).abs() < 0.01).all()
```
