"""Labour cost against budget and cost per metre by cost code (plan 5.3): hand computed cases, then the baseline release."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")


def _codes():
    return pd.DataFrame({"cst_key": ["CST-100", "CST-110", "CST-120", "CST-720"], "category": ["labour", "labour", "labour", "material"], "is_group": [True, False, False, False]})


def _cb(rows):
    return pd.DataFrame(rows, columns=["prj_key", "period", "cst_key", "currency", "actual_amount", "incurred_in_period", "estimate_amount"])


def _pb(rows):
    return pd.DataFrame(rows, columns=["prj_key", "cst_key", "budget_version", "budget_amount", "currency"])


def _data():
    cb = _cb([("P1", "2025-01", "CST-110", "EUR", 100.0, 100.0, 400.0), ("P1", "2025-02", "CST-110", "EUR", 200.0, 100.0, 400.0), ("P1", "2025-03", "CST-110", "EUR", 300.0, 100.0, 400.0),
              ("P1", "2025-03", "CST-120", "EUR", 50.0, 50.0, 40.0), ("P1", "2025-03", "CST-720", "EUR", 900.0, 900.0, 900.0),
              ("P2", "2025-02", "CST-110", "EUR", 10.0, 10.0, 12.0), ("P3", "2024-06", "CST-110", "DKK", 77.0, 77.0, 80.0)])
    pb = _pb([("P1", "CST-110", 2, 250.0, "EUR"), ("P1", "CST-120", 2, 50.0, "EUR"), ("P1", "CST-100", 2, 999.0, "EUR"), ("P1", "CST-110", 3, 9999.0, "EUR"), ("P3", "CST-110", 1, 70.0, "DKK")])
    return cb, pb


def test_labour_overrun_uses_leaf_labour_codes_the_original_budget_and_the_window():
    cb, pb = _data()
    r = fin.labour_cost_overrun(cb, pb, _codes(), "2025-02", "2025-03", active_only=False, context=M12).set_index("prj_key")
    p1 = r.loc["P1"]
    assert (p1.labour_budget, p1.labour_estimate, p1.labour_actual_to_date, p1.labour_actual_window) == (300.0, 440.0, 350.0, 250.0), "budget version 2 only, no group code, no material"
    assert p1.overrun_vs_budget_pct == 16.67 and p1.overrun_vs_estimate_pct == -20.45 and p1.currency == "EUR" and p1.reason is None
    assert r.loc["P2"].reason == "no labour budget" and np.isnan(r.loc["P2"].overrun_vs_budget_pct) and r.loc["P2"].labour_actual_to_date == 10.0
    assert r.loc["P3"].currency == "DKK" and r.loc["P3"].labour_actual_window == 0.0 and r.loc["P3"].overrun_vs_budget_pct == 10.0, "cost before the window is still to date"
    assert fin.labour_cost_overrun(cb, pb, _codes(), "2025-02", "2025-03", active_only=False, context=M12).prj_key.tolist() == ["P1", "P3", "P2"], "largest overrun first (16.67, 10.0), null percentages last"
    act = fin.labour_cost_overrun(cb, pb, _codes(), "2025-02", "2025-03", context=M12)
    assert act.prj_key.tolist() == ["P1", "P2"], "P3 has no labour cost in the window"
    early = fin.labour_cost_overrun(cb, pb, _codes(), "2025-01", "2025-02", active_only=False, context=M12).set_index("prj_key")
    assert early.loc["P1"].labour_actual_to_date == 200.0 and early.loc["P1"].labour_actual_window == 200.0 and early.loc["P1"].overrun_vs_budget_pct == -33.33, "the end of the window cuts the cumulative"
    assert "P2" in early.index and fin.labour_cost_overrun(cb, pb, _codes(), "2023-01", "2023-02", active_only=False, context=M12).empty


def test_labour_overrun_refuses_bad_input():
    cb, pb = _data()
    f = lambda cb=cb, pb=pb, codes=_codes(), a="2025-01", b="2025-03": fin.labour_cost_overrun(cb, pb, codes, a, b, context=M12)
    with pytest.raises(FrameError, match="starts 2025-03 after it ends 2025-01"):
        f(a="2025-03", b="2025-01")
    with pytest.raises(FrameError, match="not a month"):
        f(a="garbage")
    with pytest.raises(FrameError, match="more than one row for the same"):
        f(cb=pd.concat([cb, cb.iloc[:1]]))
    with pytest.raises(FrameError, match="period must be text"):
        f(cb=cb.assign(period="2025-03-01"))
    with pytest.raises(FrameError, match="more than one currency"):
        f(cb=cb.assign(currency=["EUR", "DKK"] + ["EUR"] * 5))
    with pytest.raises(FrameError, match="another currency"):
        f(pb=pb.assign(currency="SEK"))
    with pytest.raises(FrameError, match="not in projects.cost_code"):
        f(codes=_codes().iloc[:3])
    with pytest.raises(FrameError, match="no leaf cost code"):
        f(codes=_codes().assign(category="material"))
    with pytest.raises(FrameError, match="more than one line"):
        f(pb=pd.concat([pb, pb.iloc[:1]]))
    with pytest.raises(FrameError, match="lacks column"):
        f(pb=pb.drop(columns="budget_amount"))


def test_labour_overrun_review_cases_late_codes_nulls_numbers_ties_and_order():
    cb = _cb([("P1", "2025-01", "CST-110", "EUR", 100.0, 100.0, 400.0), ("P1", "2025-02", "CST-110", "EUR", 150.0, 50.0, 400.0), ("P1", "2025-02", "CST-120", "EUR", 20.0, 20.0, 400.0)])
    pb = _pb([("P1", "CST-110", 2, 300.0, "EUR"), ("P1", "CST-120", 2, 400.0, "EUR")])
    early = fin.labour_cost_overrun(cb.sample(frac=1, random_state=4), pb, _codes(), "2025-01", "2025-01", context=M12).iloc[0]
    assert early.labour_estimate == 800.0 and early.overrun_vs_estimate_pct == -87.5, "a code that starts after the window end still has its estimate"
    shuffled = cb.sample(frac=1, random_state=1)
    assert fin.labour_cost_overrun(shuffled, pb, _codes(), "2025-01", "2025-02", context=M12).labour_actual_to_date.tolist() == [170.0], "the last row is by period, not by position"
    for col in ("actual_amount", "incurred_in_period", "estimate_amount"):
        with pytest.raises(FrameError, match="null values"):
            fin.labour_cost_overrun(cb.assign(**{col: [np.nan, 1.0, 1.0]}), pb, _codes(), "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="null budget_amount"):
        fin.labour_cost_overrun(cb, pb.assign(budget_amount=[np.nan, 1.0]), _codes(), "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="null values in cst_key"):
        fin.labour_cost_overrun(cb, pb, _codes().assign(is_group=[True, None, False, False]), "2025-01", "2025-02", context=M12)
    for bad in (2025, 5, 2025.0, True):
        with pytest.raises(FrameError, match="not a month"):
            fin.labour_cost_overrun(cb, pb, _codes(), bad, "2025-02", context=M12)
    tie_cb = _cb([(k, "2025-01", "CST-110", "EUR", 120.0, 120.0, 100.0) for k in ("P2", "P1")])
    tie_pb = _pb([(k, "CST-110", 2, 100.0, "EUR") for k in ("P2", "P1")])
    assert fin.labour_cost_overrun(tie_cb, tie_pb, _codes(), "2025-01", "2025-01", context=M12).prj_key.tolist() == ["P1", "P2"], "equal percentages are ordered by project"


def _comp(keys, legacy=None):
    return pd.DataFrame({"prj_key": keys, "legacy": legacy if legacy is not None else [False] * len(keys), "data_depth": "full"})


def _proj():
    return pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4"], "route_length_m": [1000.0, 500.0, 800.0, np.nan]})


def test_cost_per_metre_is_the_median_of_the_last_row_per_project_and_code():
    cb = _cb([("P1", "2025-01", "CST-110", "EUR", 50.0, 50.0, 0.0), ("P1", "2025-02", "CST-110", "EUR", 1000.0, 950.0, 0.0), ("P1", "2025-02", "CST-720", "EUR", 300.0, 300.0, 0.0),
              ("P2", "2025-02", "CST-110", "EUR", 1500.0, 1500.0, 0.0), ("P2", "2025-03", "CST-110", "EUR", 2000.0, 500.0, 0.0), ("P5", "2025-03", "CST-110", "EUR", 1.0, 1.0, 0.0)])
    r = fin.cost_per_metre_by_cost_code(_comp(["P1", "P2", "P3", "P4"], [False, False, True, False]), cb, _proj(), context=M12)
    assert r.by_code.cst_key.tolist() == ["CST-110", "CST-720"] and r.by_code.n_projects.tolist() == [2, 1]
    assert r.by_code.median_per_metre.tolist() == [2.5, 0.3], "CST-110: 1000/1000 = 1 and 2000/500 = 4 (last rows), median 2.5"
    assert r.dropped.values.tolist() == [["P3", "no finance rows"], ["P4", "no finance rows"]]
    assert r.per_project.legacy.tolist() == [False, False, False], "legacy is carried from the comparable set"
    assert set(r.per_project.route_source) == {"planned"} and r.per_project.cost_at_completion.tolist() == [1000.0, 300.0, 2000.0]


def test_cost_per_metre_currencies_route_changes_and_refusals():
    cb = _cb([("P1", "2025-02", "CST-110", "EUR", 1000.0, 1000.0, 0.0), ("P2", "2025-02", "CST-110", "DKK", 2000.0, 2000.0, 0.0), ("P4", "2025-02", "CST-110", "EUR", 10.0, 10.0, 0.0)])
    r = fin.cost_per_metre_by_cost_code(_comp(["P1", "P2", "P4"]), cb, _proj(), route_change=pd.DataFrame({"prj_key": ["P1"], "as_built_length_m": [2000.0]}), context=M12)
    assert r.by_code[["cst_key", "currency", "n_projects", "median_per_metre"]].values.tolist() == [["CST-110", "DKK", 1, 4.0], ["CST-110", "EUR", 1, 0.5]], "never one median across currencies"
    assert r.per_project.set_index("prj_key").route_source.to_dict() == {"P1": "as_built", "P2": "planned"} and r.dropped.values.tolist() == [["P4", "no route length"]]
    for bad, msg in ((dict(comparable_set=_comp(["P1", "P1"])), "more than once"), (dict(comparable_set=_comp(["P9"])), "not in projects.project"),
                     (dict(project=pd.concat([_proj(), _proj().iloc[:1]])), "more than one row"), (dict(route_change=pd.DataFrame({"prj_key": ["P1", "P1"], "as_built_length_m": [1.0, 2.0]})), "more than one row")):
        args = dict(comparable_set=_comp(["P1", "P2"]), project_cost_breakdown=cb, project=_proj(), route_change=None)
        args.update(bad)
        with pytest.raises(FrameError, match=msg):
            fin.cost_per_metre_by_cost_code(**args, context=M12)
    zero = fin.cost_per_metre_by_cost_code(_comp(["P1", "P2"]), cb, _proj(), route_change=pd.DataFrame({"prj_key": ["P1"], "as_built_length_m": [0.0]}), context=M12)
    assert zero.per_project.set_index("prj_key").route_source["P1"] == "planned", "an as-built length of 0 does not replace the planned one"
    cb3 = _cb([(k, "2025-02", "CST-110", "EUR", v, v, 0.0) for k, v in (("P1", 1000.0), ("P2", 500.0), ("P3", 9000.0))])
    pr3 = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "route_length_m": [1000.0, 500.0, 1000.0]})
    med = fin.cost_per_metre_by_cost_code(_comp(["P3", "P1", "P2"]), cb3.sample(frac=1, random_state=2), pr3, context=M12)
    assert med.by_code.median_per_metre.tolist() == [1.0] and med.by_code.n_projects.tolist() == [3], "median of 1, 1 and 9 is 1, not the mean"
    with pytest.raises(FrameError, match="null values"):
        fin.cost_per_metre_by_cost_code(_comp(["P1"]), cb3.assign(actual_amount=np.nan), pr3, context=M12)
    nl = fin.cost_per_metre_by_cost_code(_comp(["P1", "P2"]), cb3, _proj().assign(route_length_m=[0.0, -5.0, 1.0, 1.0]), context=M12)
    assert nl.dropped.values.tolist() == [["P1", "no route length"], ["P2", "no route length"]]
    empty = fin.cost_per_metre_by_cost_code(_comp([]), cb, _proj(), context=M12)
    assert empty.by_code.empty and empty.per_project.empty and empty.dropped.empty
