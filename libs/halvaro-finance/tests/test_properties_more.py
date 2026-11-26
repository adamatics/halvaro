"""Property style tests of the finance modules vat_tax and project_costs that the standard check found none for (standard 3.2.3, lane W1, issue #504).

Seeded random inputs, no extra package; the rules are written from the documented behaviour of the functions, which are called in the tests themselves.
"""
import random

import numpy as np
import pandas as pd

from halvaro.core import Context
from halvaro.finance import cost_per_metre_by_cost_code, vat_return_from_ledger

CTX = Context(stage="month12", role="analyst")


def rng(seed: int) -> random.Random:
    return random.Random(20261120 + seed)


def test_vat_return_from_ledger_sum_of_the_parts_vat_payable_is_output_less_input_and_the_total_is_the_sum_of_the_lines():
    r = rng(1)
    for _ in range(30):
        n = 40
        lines = pd.DataFrame({"le_key": "LE-01", "gl_key": [r.choice(["GL-4710", "GL-4720", "GL-2510", "GL-2520"]) for _ in range(n)], "period": [f"2026-0{r.randint(1, 4)}" for _ in range(n)],
                              "vat_code": "DK25", "vat_base": [round(r.uniform(100, 9000), 2) for _ in range(n)], "currency": "DKK"})
        lines["amount"] = [round(-b * 0.25, 2) if g in ("GL-4710", "GL-4720") else round(b * 0.25, 2) for b, g in zip(lines["vat_base"], lines["gl_key"])]
        before = lines.copy()
        out = vat_return_from_ledger(lines, context=CTX).value
        assert lines.equals(before)
        assert np.allclose(out["vat_payable"], out["total_output_vat"] - out["total_input_vat"], atol=0.011)
        out_lines = lines[lines["gl_key"].isin(["GL-4710", "GL-4720"])]
        assert abs(out["total_output_vat"].sum() - (-out_lines["amount"].sum())) < 0.011
        assert out["period"].is_monotonic_increasing and out.equals(vat_return_from_ledger(lines.sample(frac=1, random_state=r.randint(0, 99)), context=CTX).value)


def test_cost_per_metre_by_cost_code_invariant_under_the_order_of_the_rows_and_the_median_is_within_the_values():
    r = rng(2)
    for _ in range(20):
        n = 7
        comp = pd.DataFrame({"prj_key": [f"P{i}" for i in range(n)], "legacy": False, "data_depth": "full"})
        project = pd.DataFrame({"prj_key": comp["prj_key"], "route_length_m": [r.choice([500.0, 1000.0, 2000.0]) for _ in range(n)]})
        cb = pd.DataFrame([(p, "2025-02", "CST-110", "EUR", round(r.uniform(100, 5000), 2), 0.0, 0.0) for p in comp["prj_key"]],
                          columns=["prj_key", "period", "cst_key", "currency", "actual_amount", "incurred_in_period", "estimate_amount"])
        out = cost_per_metre_by_cost_code(comp, cb, project, context=CTX)
        values = (cb.set_index("prj_key")["actual_amount"] / project.set_index("prj_key")["route_length_m"])
        m = float(out.by_code["median_per_metre"].iloc[0])
        assert values.min() - 0.011 <= m <= values.max() + 0.011
        shuffled = cost_per_metre_by_cost_code(comp.sample(frac=1, random_state=r.randint(0, 99)), cb.sample(frac=1, random_state=r.randint(0, 99)), project, context=CTX)
        assert shuffled.by_code.reset_index(drop=True).equals(out.by_code.reset_index(drop=True))
