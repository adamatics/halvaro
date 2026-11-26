"""HF-01: labour_cost_overrun returns two overrun measures and sorts by the budget; the estimate measure can rank the projects the other way round (the trap)."""

import halvaro.finance as fin
from halvaro.core import Context

from test_project_costs import _cb, _codes, _pb

M12 = Context(stage="month12", role="r")


def _overrun():
    cb = _cb([("P1", "2025-03", "CST-110", "EUR", 150.0, 150.0, 400.0), ("P2", "2025-03", "CST-110", "EUR", 110.0, 110.0, 100.0)])
    pb = _pb([("P1", "CST-110", 1, 100.0, "EUR"), ("P2", "CST-110", 1, 100.0, "EUR")])
    return fin.labour_cost_overrun(cb, pb, _codes(), "2025-01", "2025-03", context=M12)


def test_both_overrun_columns_are_returned_and_the_rows_are_sorted_by_the_budget_measure():
    o = _overrun()
    assert {"overrun_vs_budget_pct", "overrun_vs_estimate_pct"} <= set(o.columns)
    assert o.prj_key.tolist() == ["P1", "P2"] and o.overrun_vs_budget_pct.is_monotonic_decreasing
    assert o.set_index("prj_key").overrun_vs_budget_pct.round(2).to_dict() == {"P1": 50.0, "P2": 10.0}


def test_the_estimate_measure_ranks_the_projects_the_other_way_round():
    o = _overrun().set_index("prj_key")
    assert o.overrun_vs_estimate_pct.round(2).to_dict() == {"P1": -62.5, "P2": 10.0}
    assert o.overrun_vs_estimate_pct.idxmax() == "P2" and o.overrun_vs_budget_pct.idxmax() == "P1", "the trap: sorting by the estimate column puts P2 first, the function ranks by the budget"
