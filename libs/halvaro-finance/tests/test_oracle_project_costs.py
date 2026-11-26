"""Oracle tests of project_costs.labour_cost_overrun and cost_per_metre_by_cost_code (both imported through the package): hand worked frames, then the baseline tables read with plain loops."""
import datetime as dt

import numpy as np
import pandas as pd

import halvaro.finance as fin
from halvaro.core import Context

M12 = Context(stage="month12", role="r")
OVERRUN_COLS = ["prj_key", "currency", "labour_budget", "labour_estimate", "labour_actual_to_date", "labour_actual_window", "overrun_vs_budget_pct", "overrun_vs_estimate_pct", "reason"]


def _cb(rows):
    """rows: (prj_key, period, cst_key, currency, actual_amount, incurred_in_period, estimate_amount)."""
    return pd.DataFrame(rows, columns=["prj_key", "period", "cst_key", "currency", "actual_amount", "incurred_in_period", "estimate_amount"])


def _pb(rows):
    """rows: (prj_key, cst_key, budget_version, budget_amount, currency)."""
    return pd.DataFrame(rows, columns=["prj_key", "cst_key", "budget_version", "budget_amount", "currency"])


def _codes():
    return pd.DataFrame({"cst_key": ["CST-100", "CST-110", "CST-130", "CST-500"], "category": ["labour", "labour", "labour", "material"], "is_group": [True, False, False, False]})


def _overrun_inputs():
    e = "EUR"
    cb = _cb([
        ("P1", "2025-03", "CST-110", e, 100.0, 100.0, 900.0), ("P1", "2025-04", "CST-110", e, 250.0, 150.0, 900.0), ("P1", "2025-06", "CST-110", e, 400.0, 150.0, 950.0),
        ("P1", "2025-07", "CST-110", e, 500.0, 100.0, 1000.0), ("P1", "2025-05", "CST-130", e, 60.0, 60.0, 100.0), ("P1", "2025-05", "CST-500", e, 999.0, 999.0, 999.0),
        ("P1", "2025-05", "CST-100", e, 777.0, 777.0, 777.0),
        ("P2", "2025-06", "CST-110", "DKK", 1000.0, 1000.0, 1500.0),
        ("P3", "2025-03", "CST-110", e, 80.0, 80.0, 100.0),
        ("P4", "2025-04", "CST-110", e, 50.0, 50.0, 100.0), ("P4", "2025-05", "CST-110", e, 0.0, -50.0, 100.0),
        ("P5", "2025-05", "CST-110", e, 40.0, 40.0, 60.0),
        ("P6", "2025-05", "CST-110", e, 30.0, 30.0, 50.0),
        ("P7", "2025-08", "CST-110", e, 10.0, 10.0, 10.0),
        ("P8", "2025-04", "CST-110", e, 120.0, 120.0, 120.0),
        ("P0", "2025-04", "CST-110", e, 120.0, 120.0, 120.0),
        ("P9", "2025-05", "CST-110", e, 5.0, 5.0, 0.0),
    ])
    pb = _pb([
        ("P1", "CST-110", 1, 200.0, e), ("P1", "CST-130", 1, 100.0, e), ("P1", "CST-100", 1, 5000.0, e), ("P1", "CST-500", 1, 1000.0, e), ("P1", "CST-110", 2, 9999.0, e),
        ("P2", "CST-110", 1, 1000.0, "DKK"), ("P3", "CST-110", 1, 100.0, e), ("P4", "CST-110", 1, 100.0, e), ("P6", "CST-110", 1, 0.0, e), ("P7", "CST-110", 1, 100.0, e),
        ("P8", "CST-110", 1, 100.0, e), ("P0", "CST-110", 1, 100.0, e), ("P9", "CST-110", 1, 50.0, e),
    ])
    return cb, pb, _codes()


def test_oracle_labour_cost_overrun_hand_window_original_budget_and_ranking():
    """route: hand worked projects over a window of three months, each figure written out by hand (original budget version, leaf labour codes, window and to-date cut at the window ends)."""
    cb, pb, codes = _overrun_inputs()
    kept = (cb.copy(deep=True), pb.copy(deep=True), codes.copy(deep=True))
    r = fin.labour_cost_overrun(cb, pb, codes, "2025-04", "2025-06", active_only=False, context=M12)
    assert list(r.columns) == OVERRUN_COLS
    assert r.prj_key.tolist() == ["P1", "P0", "P8", "P2", "P3", "P9", "P4", "P5", "P6"], "overrun against budget, largest first, equal values by project, no budget last by project; P7 has no cost up to the window end"
    v = r.set_index("prj_key")
    assert v.loc["P1"].tolist()[:6] == ["EUR", 300.0, 1100.0, 460.0, 360.0, 53.33], "budget 200 + 100 of version 1 (not version 2, not the group or material lines); to date 400 + 60; window 150 + 150 + 60; estimate 1000 + 100 of the latest rows"
    assert v.loc["P1", "overrun_vs_estimate_pct"] == -58.18 and v.loc["P1", "reason"] is None
    assert v.loc["P2"].tolist()[:8] == ["DKK", 1000.0, 1500.0, 1000.0, 1000.0, 0.0, -33.33, None], "the row of the last window month counts, cost equal to budget is no overrun"
    assert v.loc["P3"].tolist()[:8] == ["EUR", 100.0, 100.0, 80.0, 0.0, -20.0, -20.0, None], "cost before the window start is to date, not window"
    assert v.loc["P4"].tolist()[:8] == ["EUR", 100.0, 100.0, 0.0, 0.0, -100.0, -100.0, None], "50 and a credit of 50 inside the window net to nothing"
    for k in ("P0", "P8"):
        assert v.loc[k].tolist()[:8] == ["EUR", 100.0, 120.0, 120.0, 120.0, 20.0, 0.0, None], "a row on the first month of the window is in the window"
    assert v.loc["P9"].tolist()[:6] == ["EUR", 50.0, 0.0, 5.0, 5.0, -90.0] and np.isnan(v.loc["P9", "overrun_vs_estimate_pct"]) and v.loc["P9", "reason"] is None, "an estimate of zero gives no percentage against the estimate"
    assert np.isnan(v.loc["P5", "labour_budget"]) and v.loc["P5", ["labour_estimate", "labour_actual_to_date", "labour_actual_window"]].tolist() == [60.0, 40.0, 40.0]
    assert v.loc["P6", "labour_budget"] == 0.0 and v.loc["P6", ["labour_estimate", "labour_actual_to_date", "labour_actual_window"]].tolist() == [50.0, 30.0, 30.0]
    for k in ("P5", "P6"):
        assert v.loc[k, ["overrun_vs_budget_pct", "overrun_vs_estimate_pct"]].isna().all() and v.loc[k, "reason"] == "no labour budget", "no budget, or a budget of zero: no percentage"
    for before, after in zip(kept, (cb, pb, codes)):
        pd.testing.assert_frame_equal(before, after)


def test_oracle_labour_cost_overrun_hand_active_only_keeps_projects_with_net_cost_in_the_window():
    """route: the same hand frames, the projects with positive net labour cost inside the window written out by hand."""
    cb, pb, codes = _overrun_inputs()
    act = fin.labour_cost_overrun(cb, pb, codes, "2025-04", "2025-06", context=M12)
    assert act.prj_key.tolist() == ["P1", "P0", "P8", "P2", "P9", "P5", "P6"], "P3 has cost before the window, P4 nets to zero in it, P7 starts after it"
    one = fin.labour_cost_overrun(cb, pb, codes, dt.date(2025, 5, 1), pd.Timestamp("2025-05-31"), context=M12)
    assert one.prj_key.tolist() == ["P1", "P9", "P5", "P6"], "a one month window given as dates: P4 nets -50 in May, P2 starts in June, P8 and P0 only in April"
    p1 = one.set_index("prj_key").loc["P1"]
    assert p1.labour_actual_to_date == 310.0 and p1.labour_actual_window == 60.0 and p1.labour_estimate == 1100.0, "to date: CST-110 at its April row (250) and CST-130 (60); the estimate does not depend on the window"
    assert p1.overrun_vs_budget_pct == 3.33 and p1.overrun_vs_estimate_pct == -71.82
    assert fin.labour_cost_overrun(cb, pb, codes, "2025-09", "2025-10", active_only=False, context=M12).set_index("prj_key").loc["P7", "labour_actual_to_date"] == 10.0
    assert fin.labour_cost_overrun(cb, pb, codes, "2025-01", "2025-02", active_only=False, context=M12).empty, "no cost up to the end of the window: no rows"


def test_oracle_labour_cost_overrun_is_independent_of_the_order_of_the_rows():
    """route: the hand frames shuffled with seeds give the frame computed from the unshuffled hand frames by the hand values of the other tests."""
    cb, pb, codes = _overrun_inputs()
    r = fin.labour_cost_overrun(cb.sample(frac=1, random_state=11).reset_index(drop=True), pb.sample(frac=1, random_state=12).reset_index(drop=True), codes.sample(frac=1, random_state=13),
                                "2025-04", "2025-06", active_only=False, context=M12).set_index("prj_key")
    assert r.labour_actual_to_date.to_dict() == {"P1": 460.0, "P0": 120.0, "P8": 120.0, "P2": 1000.0, "P3": 80.0, "P9": 5.0, "P4": 0.0, "P5": 40.0, "P6": 30.0}
    assert r.labour_budget.dropna().to_dict() == {"P1": 300.0, "P0": 100.0, "P8": 100.0, "P2": 1000.0, "P3": 100.0, "P4": 100.0, "P6": 0.0, "P9": 50.0}


# ---- cost per metre by cost code


def _comp(keys, legacy=None):
    return pd.DataFrame({"prj_key": keys, "legacy": legacy if legacy is not None else [False] * len(keys)})


def test_oracle_cost_per_metre_by_cost_code_hand_last_row_median_currency_and_dropped_projects():
    """route: hand worked projects, per metre and median written out by hand: last row by period (rows out of order), median not mean, one median per currency, dropped projects with the reason."""
    e = "EUR"
    cb = _cb([
        ("P1", "2025-03", "CST-110", e, 700.0, 300.0, 0.0), ("P1", "2025-01", "CST-110", e, 100.0, 100.0, 0.0), ("P1", "2025-02", "CST-110", e, 400.0, 300.0, 0.0), ("P1", "2025-02", "CST-720", e, 90.0, 90.0, 0.0),
        ("P2", "2025-02", "CST-110", e, 300.0, 300.0, 0.0), ("P3", "2025-02", "CST-110", "DKK", 1250.0, 1250.0, 0.0), ("P8", "2025-02", "CST-110", e, 400.0, 400.0, 0.0),
        ("P9", "2025-02", "CST-900", e, 100.0, 100.0, 0.0), ("P5", "2025-02", "CST-110", e, 5.0, 5.0, 0.0), ("P6", "2025-02", "CST-110", e, 6.0, 6.0, 0.0), ("P7", "2025-02", "CST-110", e, 7.0, 7.0, 0.0),
    ])
    project = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5", "P6", "P8", "P9", "PX"], "route_length_m": [1000.0, 400.0, 500.0, 900.0, np.nan, 0.0, 100.0, 3.0, 50.0]})
    comp = _comp(["P9", "P8", "P1", "P2", "P3", "P4", "P5", "P6"], [True, False, False, False, True, False, False, False])
    kept = (cb.copy(deep=True), project.copy(deep=True), comp.copy(deep=True))
    r = fin.cost_per_metre_by_cost_code(comp, cb, project, context=M12)
    pp = r.per_project.set_index(["prj_key", "cst_key"])
    assert r.per_project[["prj_key", "cst_key"]].values.tolist() == [["P1", "CST-110"], ["P1", "CST-720"], ["P2", "CST-110"], ["P3", "CST-110"], ["P8", "CST-110"], ["P9", "CST-900"]]
    assert pp.loc[("P1", "CST-110")].tolist() == ["EUR", 700.0, 1000.0, 0.7, "planned", False], "the row of 2025-03, 700 over 1000 m"
    assert pp.loc[("P1", "CST-720")].per_metre == 0.09 and pp.loc[("P2", "CST-110")].per_metre == 0.75 and pp.loc[("P8", "CST-110")].per_metre == 4.0
    assert pp.loc[("P3", "CST-110")].tolist() == ["DKK", 1250.0, 500.0, 2.5, "planned", True], "legacy is read from the comparable set, not from the project"
    assert pp.loc[("P9", "CST-900")].per_metre == 33.3333 and bool(pp.loc[("P9", "CST-900")].legacy) is True, "100 over 3 m, four decimals"
    assert r.by_code[["cst_key", "currency", "n_projects", "median_per_metre"]].values.tolist() == [
        ["CST-110", "DKK", 1, 2.5], ["CST-110", "EUR", 3, 0.75], ["CST-720", "EUR", 1, 0.09], ["CST-900", "EUR", 1, 33.3333]], "EUR CST-110: 0.7, 0.75 and 4.0 give 0.75, not the mean"
    assert r.dropped.values.tolist() == [["P4", "no finance rows"], ["P5", "no route length"], ["P6", "no route length"]], "in the order of the comparable set; P7 and PX are not in it"
    for before, after in zip(kept, (cb, project, comp)):
        pd.testing.assert_frame_equal(before, after)


def test_oracle_cost_per_metre_by_cost_code_hand_route_change_replaces_only_a_positive_as_built_length():
    """route: hand worked as-built lengths: positive replaces, zero, negative and missing leave the planned length, a length for a project outside the set is ignored."""
    e = "EUR"
    cb = _cb([(k, "2025-02", "CST-110", e, a, a, 0.0) for k, a in (("P1", 1000.0), ("P2", 1000.0), ("P3", 1000.0), ("P4", 1000.0), ("P5", 1000.0))])
    project = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5", "P6"], "route_length_m": [1000.0, 1000.0, 1000.0, 1000.0, np.nan, 1000.0]})
    rc = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5", "P6"], "as_built_length_m": [2000.0, 0.0, -5.0, np.nan, 500.0, 10.0]})
    r = fin.cost_per_metre_by_cost_code(_comp(["P1", "P2", "P3", "P4", "P5"]), cb, project, route_change=rc, context=M12)
    pp = r.per_project.set_index("prj_key")
    assert pp.route_length_m.to_dict() == {"P1": 2000.0, "P2": 1000.0, "P3": 1000.0, "P4": 1000.0, "P5": 500.0}
    assert pp.route_source.to_dict() == {"P1": "as_built", "P2": "planned", "P3": "planned", "P4": "planned", "P5": "as_built"}
    assert pp.per_metre.to_dict() == {"P1": 0.5, "P2": 1.0, "P3": 1.0, "P4": 1.0, "P5": 2.0}, "an as-built length stands in for a missing planned length"
    assert r.by_code.median_per_metre.tolist() == [1.0] and r.by_code.n_projects.tolist() == [5] and r.dropped.empty
