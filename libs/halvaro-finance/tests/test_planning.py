"""Planning (plan 5.10): hand computed budget, forecast and management P&L rows, then the baseline release."""
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal, registry

M3 = Context(stage="month3", role="r")
COST = ["project_labour_cost", "project_other_direct_cost", "service_direct_cost", "stock_and_inventory_cost", "staff_cost", "labour_absorbed", "overhead_cost", "overhead_allocated",
        "depreciation_and_amortisation", "other_operating_cost"]


def _bl():
    return pd.DataFrame({"le_key": "LE-01", "budget_version": ["BUD-2025", "BUD-2025", "BUD-2025", "BUD-2024"], "cc_key": "CC-1", "gl_key": ["GL-5400", "GL-5400", "GL-6100", "GL-5400"],
                         "period": ["2025-01", "2025-02", "2025-01", "2024-01"], "amount": [-100.0, -100.0, 40.0, -1.0], "amount_dkk": [-100.0, -100.0, 40.0, -1.0]})


def _ca():
    return pd.DataFrame({"le_key": "LE-01", "cc_key": "CC-1", "gl_key": ["GL-5400", "GL-5400", "GL-7000", "GL-5400"], "period": ["2025-01", "2025-03", "2025-01", "2025-02"], "amount": [-90.0, -50.0, 7.0, -120.0],
                         "amount_dkk": [-90.0, -50.0, 7.0, -120.0]})


def test_budget_variance_actual_less_budget_for_one_version():
    v = fin.budget_variance(_bl(), _ca(), version="BUD-2025", context=M3).set_index(["gl_key", "period"])
    assert v.loc[("GL-5400", "2025-01"), ["budget", "actual", "variance", "variance_percent"]].tolist() == [-100.0, -90.0, 10.0, 10.0], "less revenue than budgeted shows as a positive (debit) variance"
    assert v.loc[("GL-5400", "2025-02"), ["budget", "actual", "variance"]].tolist() == [-100.0, -120.0, -20.0] and v.loc[("GL-6100", "2025-01"), "actual"] == 0.0 and v.loc[("GL-7000", "2025-01"), "budget"] == 0.0
    assert pd.isna(v.loc[("GL-7000", "2025-01"), "variance_percent"]) and ("GL-5400", "2025-03") not in v.index, "2025-03 is outside the periods of the version's lines"
    assert len(v) == 4
    with pytest.raises(FrameError, match="no lines"):
        fin.budget_variance(_bl(), _ca(), version="BUD-1999", context=M3)
    with pytest.raises(FrameError, match="one row per"):
        fin.budget_variance(pd.concat([_bl(), _bl().iloc[:1]]), _ca(), version="BUD-2025", context=M3)


def test_forecast_vs_budget_and_the_basis_rule():
    fv = pd.DataFrame({"forecast_version": ["FC-2025-Q1"], "actuals_through_period": ["2025-01"], "budget_version": ["BUD-2025"]})
    fl = pd.DataFrame({"le_key": "LE-01", "forecast_version": "FC-2025-Q1", "cc_key": "CC-1", "gl_key": ["GL-5400", "GL-5400", "GL-6100"], "period": ["2025-01", "2025-02", "2025-01"], "amount_dkk": [-90.0, -95.0, 41.0],
                       "basis": ["actual", "projected", "projected"]})
    r = fin.forecast_vs_budget(fl, fv, _bl(), context=M3).set_index(["gl_key", "period"])
    assert r.loc[("GL-5400", "2025-01"), ["forecast_dkk", "budget_dkk", "difference_dkk", "basis_ok"]].tolist() == [-90.0, -100.0, 10.0, True]
    assert r.loc[("GL-5400", "2025-02"), "difference_dkk"] == 5.0 and bool(r.loc[("GL-5400", "2025-02"), "basis_ok"]) and not bool(r.loc[("GL-6100", "2025-01"), "basis_ok"]), "a projected line in an actual month"
    with pytest.raises(FrameError, match="not in finance.forecast_version"):
        fin.forecast_vs_budget(fl.assign(forecast_version="FC-9"), fv, _bl(), context=M3)
    with pytest.raises(FrameError, match="one row per key"):
        fin.forecast_vs_budget(pd.concat([fl, fl.iloc[:1]]), fv, _bl(), context=M3)


def _mp(rev=(100.0, 50.0)):
    rows = []
    for dep, r in zip(("DEP-02", "DEP-03"), rev):
        c = dict.fromkeys(COST, 0.0)
        c["project_labour_cost"], c["staff_cost"] = r * 0.2, r * 0.3
        tc = sum(c.values())
        rows.append({"le_key": "LE-01", "dep_key": dep, "period": "2025-01", "total_revenue": r, "total_cost": tc, "operating_result": r - tc, "available_hours": 100.0, "project_hours": 60.0, "service_hours": 10.0,
                     "utilisation_pct": 70.0, **c})
    return pd.DataFrame(rows)


def _tb():
    return pd.DataFrame({"le_key": "LE-01", "period": "2025-01", "gl_key": ["GL-5400", "GL-6100", "GL-7000", "GL-1000"], "debit": [0.0, 60.0, 15.0, 999.0], "credit": [150.0, 0.0, 0.0, 0.0]})


def test_mgmt_pl_check_ledger_ties_and_line_sums():
    assert fin.mgmt_pl_check(_mp(), _tb(), context=M3).empty
    r = fin.mgmt_pl_check(_mp(), _tb().assign(credit=[148.0, 0.0, 0.0, 0.0]), context=M3)
    assert set(r.rule) == {"result_differs_from_ledger", "revenue_differs_from_ledger"} and fin.mgmt_pl_check(_mp(), _tb().assign(credit=[148.0, 0.0, 0.0, 0.0]), tolerance=2.5, context=M3).empty
    mp = _mp()
    assert fin.mgmt_pl_check(mp.assign(total_cost=mp.total_cost + 0.1), _tb(), context=M3).rule.tolist().count("cost_lines_do_not_add_up") == 2
    assert fin.mgmt_pl_check(mp.assign(operating_result=mp.operating_result + 0.1), _tb(), tolerance=2.0, context=M3).rule.tolist() == ["result_not_revenue_less_cost"] * 2
    with pytest.raises(FrameError, match="pair of account numbers"):
        fin.mgmt_pl_check(mp, _tb(), result_accounts=(9000, 5000), context=M3)
    with pytest.raises(FrameError, match="like GL-5100"):
        fin.mgmt_pl_check(mp, _tb().assign(gl_key="X"), context=M3)
    with pytest.raises(FrameError, match="more than one row"):
        fin.mgmt_pl_check(pd.concat([mp, mp.iloc[:1]]), _tb(), context=M3)


def test_utilisation_is_booked_hours_over_available_hours():
    mp = _mp().assign(available_hours=[100.0, 0.0], utilisation_pct=[70.0, 0.0])
    u = fin.utilisation(mp, context=M3).set_index("dep_key")
    assert u.loc["DEP-02", "utilisation_pct"] == 70.0 and bool(u.loc["DEP-02", "agrees"]) and pd.isna(u.loc["DEP-03", "utilisation_pct"]) and pd.isna(u.loc["DEP-03", "agrees"])
    assert not bool(fin.utilisation(mp.assign(utilisation_pct=[70.5, 0.0]), context=M3).set_index("dep_key").loc["DEP-02", "agrees"]) and bool(fin.utilisation(mp.assign(utilisation_pct=[70.005, 0.0]), context=M3).set_index("dep_key").loc["DEP-02", "agrees"])
    two = pd.concat([_mp().assign(available_hours=100.0, project_hours=[50.0, 0.0], service_hours=0.0), _mp().assign(period="2025-02", available_hours=300.0, project_hours=[250.0, 0.0], service_hours=0.0)])
    d = fin.utilisation(two, by="department", context=M3).set_index("dep_key")
    assert d.loc["DEP-02", "utilisation_pct"] == 75.0, "a ratio of sums: 300 of 400 hours, not the mean of 50 and 83.3"
    with pytest.raises(FrameError, match="by is"):
        fin.utilisation(mp, by="week", context=M3)
    with pytest.raises(FrameError, match="negative"):
        fin.utilisation(mp.assign(project_hours=-1.0), context=M3)


def test_stage_registry_and_facade_for_planning():
    reg = registry.registered()
    for n in ("budget_variance", "forecast_vs_budget", "mgmt_pl_check", "utilisation"):
        assert f"halvaro.finance.planning.{n}" in reg and n in fin.__all__
    with pytest.raises(StageRefusal):
        fin.utilisation(pd.DataFrame(), context=Context(stage="day1", role="r"))
