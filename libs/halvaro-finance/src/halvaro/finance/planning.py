"""Planning checks (plan 5.10): actual against budget, the forecast anchored on actuals against the budget, the management P&L against the ledger, utilisation.

Nothing here builds a budget or a forecast and nothing posts. Account ranges and tolerances are keywords marked PROPOSED (the ranges are the generator's: P&L accounts 5100 to 8999, revenue 5100 to 5499).
"""
from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, violations

from ._guard import staged
from ._util import _cents, _need

_COST = ("project_labour_cost", "project_other_direct_cost", "service_direct_cost", "stock_and_inventory_cost", "staff_cost", "labour_absorbed", "overhead_cost", "overhead_allocated",
         "depreciation_and_amortisation", "other_operating_cost")


def _no(gl: pd.Series) -> pd.Series:
    n = pd.to_numeric(gl.astype(str).str.extract(r"^GL-(\d+)$")[0], errors="coerce")
    if n.isna().any():
        raise FrameError("gl_key must look like GL-5100")
    return n.astype(int)


def _tol(**kw: Any) -> None:
    for name, v in kw.items():
        if isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not np.isfinite(v) or v < 0:
            raise FrameError(f"{name} must be zero or more")


@staged(sources=("finance.budget_line.le_key", "finance.budget_line.budget_version", "finance.budget_line.cc_key", "finance.budget_line.gl_key", "finance.budget_line.period", "finance.budget_line.amount",
                 "finance.budget_line.amount_dkk", "finance.cost_centre_actual.le_key", "finance.cost_centre_actual.cc_key", "finance.cost_centre_actual.gl_key", "finance.cost_centre_actual.period",
                 "finance.cost_centre_actual.amount", "finance.cost_centre_actual.amount_dkk"), oracle="py:tests/test_finance_planning.py::test_budget_version_totals_tie_to_the_lines")
def budget_variance(budget_line: pd.DataFrame, cost_centre_actual: pd.DataFrame, *, version: str) -> pd.DataFrame:
    """Use this when you compare what was booked with what was budgeted, by entity, cost centre, account and period, for one budget version.

    Rule: variance is actual less budget, in the entity currency and in DKK; amounts keep the ledger sign (debit positive), so a revenue variance above zero is less revenue. Only the periods of the version's lines are compared. A cell with an actual and no budget, or a budget and no actual, is listed with zero on the missing side. variance_percent is the variance over the absolute budget, empty without a budget. Variances are rounded to 2 decimals.

    Args:
        budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period, amount and amount_dkk.
        cost_centre_actual: Frame finance.cost_centre_actual with le_key, cc_key, gl_key, period, amount and amount_dkk.
        version: The budget version, for example BUD-2026.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with le_key, cc_key, gl_key, period, budget, actual, variance, variance_dkk, budget_dkk, actual_dkk and variance_percent.

    Raises:
        FrameError: a column is missing, the version has no lines, or a frame has more than one row for an entity, cost centre, account and period.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import budget_variance
        >>> ctx = Context(stage="month12", role="analyst")
        >>> budget = pd.DataFrame({"le_key": ["LE-01"] * 2, "budget_version": ["BUD-2026"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6100"], "period": ["2026-01"] * 2,
        ...                        "amount": [100.0, 50.0], "amount_dkk": [100.0, 50.0]})
        >>> actual = pd.DataFrame({"le_key": ["LE-01"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6200"], "period": ["2026-01"] * 2, "amount": [130.0, 20.0], "amount_dkk": [130.0, 20.0]})
        >>> budget_variance(budget, actual, version="BUD-2026", context=ctx)[["gl_key", "budget", "actual", "variance"]].values.tolist()
        [['GL-6000', 100.0, 130.0, 30.0], ['GL-6100', 50.0, 0.0, -50.0], ['GL-6200', 0.0, 20.0, 20.0]]
    """
    _need(budget_line, ["le_key", "budget_version", "cc_key", "gl_key", "period", "amount", "amount_dkk"], "finance.budget_line")
    _need(cost_centre_actual, ["le_key", "cc_key", "gl_key", "period", "amount", "amount_dkk"], "finance.cost_centre_actual")
    b = budget_line[budget_line["budget_version"] == version]
    if b.empty:
        raise FrameError(f"budget version {version!r} has no lines")
    key = ["le_key", "cc_key", "gl_key", "period"]
    if b.duplicated(key).any() or cost_centre_actual.duplicated(key).any():
        raise FrameError("budget and actual lines need one row per entity, cost centre, account and period")
    a = cost_centre_actual[cost_centre_actual["period"].isin(set(b["period"]))]
    j = b[key + ["amount", "amount_dkk"]].merge(a[key + ["amount", "amount_dkk"]], on=key, how="outer", suffixes=("_b", "_a")).fillna({"amount_b": 0.0, "amount_dkk_b": 0.0, "amount_a": 0.0, "amount_dkk_a": 0.0})
    out = pd.DataFrame({k: j[k] for k in key})
    out["budget"], out["actual"] = j["amount_b"].astype(float), j["amount_a"].astype(float)
    out["variance"] = (out["actual"] - out["budget"]).round(2)
    out["budget_dkk"], out["actual_dkk"] = j["amount_dkk_b"].astype(float), j["amount_dkk_a"].astype(float)
    out["variance_dkk"] = (out["actual_dkk"] - out["budget_dkk"]).round(2)
    out["variance_percent"] = np.where(out["budget"].abs() > 0, (out["variance"] / out["budget"].abs() * 100).round(2), np.nan)
    return out[key + ["budget", "actual", "variance", "variance_dkk", "budget_dkk", "actual_dkk", "variance_percent"]].sort_values(key).reset_index(drop=True)


@staged(sources=("finance.forecast_line.le_key", "finance.forecast_line.forecast_version", "finance.forecast_line.cc_key", "finance.forecast_line.gl_key", "finance.forecast_line.period",
                 "finance.forecast_line.amount_dkk", "finance.forecast_line.basis", "finance.forecast_version.forecast_version", "finance.forecast_version.actuals_through_period",
                 "finance.forecast_version.budget_version", "finance.budget_line.le_key", "finance.budget_line.budget_version", "finance.budget_line.cc_key", "finance.budget_line.gl_key",
                 "finance.budget_line.period", "finance.budget_line.amount_dkk"), oracle="py:tests/test_finance_planning.py::test_forecast_lines_are_anchored_on_actuals")
def forecast_vs_budget(forecast_line: pd.DataFrame, forecast_version: pd.DataFrame, budget_line: pd.DataFrame) -> pd.DataFrame:
    """Use this when you compare each forecast version with the budget it is based on, by entity, cost centre, account and period in DKK.

    Rule: difference is forecast less the budget of the version the forecast version names; a cell without a budget has budget 0; the difference is rounded to 2 decimals. basis_ok says that the line follows its version: actual up to actuals_through_period, projected after.

    Args:
        forecast_line: Frame finance.forecast_line with le_key, forecast_version, cc_key, gl_key, period, amount_dkk and basis.
        forecast_version: Frame finance.forecast_version with forecast_version, actuals_through_period and budget_version.
        budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period and amount_dkk.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with forecast_version, le_key, cc_key, gl_key, period, basis, forecast_dkk, budget_dkk, difference_dkk and basis_ok.

    Raises:
        FrameError: a column is missing, a table has more than one row for its key, or a forecast version is not in the version table.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import forecast_vs_budget
        >>> ctx = Context(stage="month12", role="analyst")
        >>> forecast = pd.DataFrame({"le_key": ["LE-01"] * 2, "forecast_version": ["FC-1"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000"] * 2, "period": ["2026-01", "2026-02"],
        ...                          "amount_dkk": [110.0, 120.0], "basis": ["actual", "projected"]})
        >>> versions = pd.DataFrame({"forecast_version": ["FC-1"], "actuals_through_period": ["2026-01"], "budget_version": ["BUD-2026"]})
        >>> budget = pd.DataFrame({"le_key": ["LE-01"], "budget_version": ["BUD-2026"], "cc_key": ["CC-1"], "gl_key": ["GL-6000"], "period": ["2026-01"], "amount_dkk": [100.0]})
        >>> forecast_vs_budget(forecast, versions, budget, context=ctx)[["period", "forecast_dkk", "budget_dkk", "difference_dkk", "basis_ok"]].values.tolist()
        [['2026-01', 110.0, 100.0, 10.0, True], ['2026-02', 120.0, 0.0, 120.0, True]]
    """
    _need(forecast_line, ["le_key", "forecast_version", "cc_key", "gl_key", "period", "amount_dkk", "basis"], "finance.forecast_line")
    _need(forecast_version, ["forecast_version", "actuals_through_period", "budget_version"], "finance.forecast_version")
    _need(budget_line, ["le_key", "budget_version", "cc_key", "gl_key", "period", "amount_dkk"], "finance.budget_line")
    key = ["le_key", "cc_key", "gl_key", "period"]
    if forecast_line.duplicated(["forecast_version", *key]).any() or budget_line.duplicated(["budget_version", *key]).any() or forecast_version["forecast_version"].duplicated().any():
        raise FrameError("forecast, budget and version tables need one row per key")
    unknown = sorted(set(forecast_line["forecast_version"]) - set(forecast_version["forecast_version"]))
    if unknown:
        raise FrameError(f"forecast version {unknown[0]!r} is not in finance.forecast_version")
    f = forecast_line.merge(forecast_version[["forecast_version", "actuals_through_period", "budget_version"]], on="forecast_version", how="left", validate="many_to_one")
    f = f.merge(budget_line[["budget_version", *key, "amount_dkk"]].rename(columns={"amount_dkk": "budget_dkk"}), on=["budget_version", *key], how="left")
    f["budget_dkk"] = f["budget_dkk"].fillna(0.0).astype(float)
    f["forecast_dkk"] = f["amount_dkk"].astype(float)
    f["difference_dkk"] = (f["forecast_dkk"] - f["budget_dkk"]).round(2)
    f["basis_ok"] = np.where(f["period"] <= f["actuals_through_period"], f["basis"] == "actual", f["basis"] == "projected")
    return f[["forecast_version", *key, "basis", "forecast_dkk", "budget_dkk", "difference_dkk", "basis_ok"]].sort_values(["forecast_version", *key]).reset_index(drop=True)


@staged(sources=("finance.mgmt_pl_department.le_key", "finance.mgmt_pl_department.dep_key", "finance.mgmt_pl_department.period", "finance.mgmt_pl_department.total_revenue", "finance.mgmt_pl_department.total_cost",
                 "finance.mgmt_pl_department.operating_result", "finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.debit",
                 "finance.trial_balance.credit"), oracle="py:tests/test_finance_planning.py::test_mgmt_pl_ties_to_the_ledger")
def mgmt_pl_check(mgmt_pl_department: pd.DataFrame, trial_balance: pd.DataFrame, *, result_accounts: tuple[int, int] = (5100, 8999), revenue_accounts: tuple[int, int] = (5100, 5499), tolerance: float = 1.0,
                  line_tolerance: float = 0.05) -> pd.DataFrame:
    """Use this when you check that the management P&L agrees with the ledger and adds up within each department row.

    Rule: per entity and month, the operating result of the management P&L must equal the ledger result (credit less debit on the result accounts) and the total revenue must equal the ledger revenue (the revenue accounts), each within tolerance. Per department row, the cost lines must add up to total_cost and revenue less cost must equal the operating result, each within line_tolerance. The account ranges and tolerances are business choices (proposed).

    Args:
        mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, total_revenue, total_cost, operating_result and the ten cost line columns, one row per entity, department and period.
        trial_balance: Frame finance.trial_balance with le_key, period, gl_key (like GL-5100), debit and credit.
        result_accounts: First and last account number of the result accounts. Default (5100, 8999) (proposed).
        revenue_accounts: First and last account number of the revenue accounts. Default (5100, 5499) (proposed).
        tolerance: Largest accepted gap per entity and month. Default 1.0 (proposed).
        line_tolerance: Largest accepted gap per department row. Default 0.05 (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail; the rules are result_differs_from_ledger, revenue_differs_from_ledger, cost_lines_do_not_add_up and result_not_revenue_less_cost. Empty when everything agrees.

    Raises:
        FrameError: a column is missing, a tolerance is negative or not a number, an account range is not a (first, last) pair, or a row is repeated for an entity, department and period.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import mgmt_pl_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> costs = ["project_labour_cost", "project_other_direct_cost", "service_direct_cost", "stock_and_inventory_cost", "staff_cost", "labour_absorbed", "overhead_cost", "overhead_allocated", "depreciation_and_amortisation", "other_operating_cost"]
        >>> pl = pd.DataFrame({"le_key": ["LE-01"], "dep_key": ["DEP-1"], "period": ["2026-01"], "total_revenue": [100.0], "total_cost": [60.0], "operating_result": [40.0], **{c: [0.0] for c in costs}})
        >>> pl["project_labour_cost"] = 60.0
        >>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-01"] * 2, "gl_key": ["GL-5100", "GL-6000"], "debit": [0.0, 60.0], "credit": [100.0, 0.0]})
        >>> mgmt_pl_check(pl, tb, context=ctx).empty
        True
        >>> mgmt_pl_check(pl.assign(operating_result=30.0), tb, context=ctx)["rule"].tolist()
        ['result_differs_from_ledger', 'result_not_revenue_less_cost']
    """
    _need(mgmt_pl_department, ["le_key", "dep_key", "period", "total_revenue", "total_cost", "operating_result", *_COST], "finance.mgmt_pl_department")
    _need(trial_balance, ["le_key", "period", "gl_key", "debit", "credit"], "finance.trial_balance")
    _tol(tolerance=tolerance, line_tolerance=line_tolerance)
    for name, rng in (("result_accounts", result_accounts), ("revenue_accounts", revenue_accounts)):
        if len(rng) != 2 or rng[0] > rng[1]:
            raise FrameError(f"{name} is a (first, last) pair of account numbers")
    m = mgmt_pl_department
    if m.duplicated(["le_key", "dep_key", "period"]).any():
        raise FrameError("finance.mgmt_pl_department has more than one row for an entity, department and period")
    no = _no(trial_balance["gl_key"])
    led = lambda lo, hi: pd.Series(_cents(trial_balance["credit"]) - _cents(trial_balance["debit"]), index=trial_balance.index)[(no >= lo) & (no <= hi)].groupby([trial_balance["le_key"], trial_balance["period"]]).sum() / 100.0
    rows = []
    r: Any
    for name, rule, col, rng in (("result", "result_differs_from_ledger", "operating_result", result_accounts), ("revenue", "revenue_differs_from_ledger", "total_revenue", revenue_accounts)):
        mp = m.groupby(["le_key", "period"])[col].sum()
        j = pd.concat([mp, led(*rng)], axis=1, keys=["m", "l"]).fillna(0.0)
        for (le, per), r in cast(Any, j[(j["m"] - j["l"]).abs() > tolerance + 1e-9]).iterrows():
            rows.append(("finance.mgmt_pl_department", f"{le} {per}", rule, f"management {name} {r['m']:.2f}, ledger {r['l']:.2f}"))
    bad = (m[list(_COST)].sum(axis=1) - m["total_cost"]).abs() > line_tolerance + 1e-9
    for r in m[bad].itertuples():
        rows.append(("finance.mgmt_pl_department", f"{r.le_key} {r.dep_key} {r.period}", "cost_lines_do_not_add_up", f"total cost {r.total_cost:.2f}"))
    bad = (m["total_revenue"] - m["total_cost"] - m["operating_result"]).abs() > line_tolerance + 1e-9
    for r in m[bad].itertuples():
        rows.append(("finance.mgmt_pl_department", f"{r.le_key} {r.dep_key} {r.period}", "result_not_revenue_less_cost", f"result {r.operating_result:.2f}"))
    return violations.frame(rows)


@staged(sources=("finance.mgmt_pl_department.le_key", "finance.mgmt_pl_department.dep_key", "finance.mgmt_pl_department.period", "finance.mgmt_pl_department.utilisation_pct",
                 "finance.mgmt_pl_department.project_hours", "finance.mgmt_pl_department.service_hours", "finance.mgmt_pl_department.available_hours"),
        oracle="py:tests/test_finance_planning.py::test_mgmt_pl_utilisation_columns")
def utilisation(mgmt_pl_department: pd.DataFrame, *, by: str = "period", tolerance: float = 0.01) -> pd.DataFrame:
    """Use this when you need booked hours over available hours in percent, per department and period or per department over all periods.

    Rule: utilisation is (project hours plus service hours) over available hours times 100. by="period" gives each row of the entity, department and period with the recomputed value, the stored utilisation_pct and whether they agree within tolerance (PROPOSED 0.01); rows without available hours have a null utilisation. by="department" adds the hours of all periods per entity and department first, so the result is a ratio of sums and not a mean of percents.

    Args:
        mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, utilisation_pct, project_hours, service_hours and available_hours, one row per entity, department and period.
        by: "period" or "department" (default "period").
        tolerance: Largest accepted difference between the recomputed and the stored utilisation_pct, in percentage points (default 0.01, PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame. With by="period": le_key, dep_key, period, project_hours, service_hours, available_hours, utilisation_pct, stored_utilisation_pct and agrees. With by="department": le_key, dep_key, the three hour columns summed and utilisation_pct to two decimals.

    Raises:
        FrameError: a column is missing, by is not "period" or "department", tolerance is negative or not a number, a row is repeated for an entity, department and period, or an hour value is negative.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import utilisation
        >>> ctx = Context(stage="month3", role="analyst")
        >>> hours = pd.DataFrame({"le_key": ["LE-01"] * 2, "dep_key": ["DEP-1"] * 2, "period": ["2026-01", "2026-02"], "utilisation_pct": [75.0, 80.0],
        ...                      "project_hours": [100.0, 120.0], "service_hours": [20.0, 20.0], "available_hours": [160.0, 175.0]})
        >>> utilisation(hours, context=ctx)[["period", "utilisation_pct", "agrees"]].to_dict("records")
        [{'period': '2026-01', 'utilisation_pct': 75.0, 'agrees': True}, {'period': '2026-02', 'utilisation_pct': 80.0, 'agrees': True}]
        >>> utilisation(hours, by="department", context=ctx)["utilisation_pct"].tolist()
        [77.61]
    """
    _need(mgmt_pl_department, ["le_key", "dep_key", "period", "utilisation_pct", "project_hours", "service_hours", "available_hours"], "finance.mgmt_pl_department")
    if by not in ("period", "department"):
        raise FrameError("by is 'period' or 'department'")
    _tol(tolerance=tolerance)
    m = mgmt_pl_department
    if m.duplicated(["le_key", "dep_key", "period"]).any():
        raise FrameError("finance.mgmt_pl_department has more than one row for an entity, department and period")
    if (m[["project_hours", "service_hours", "available_hours"]] < 0).any().any():
        raise FrameError("hours cannot be negative")
    if by == "department":
        g = m.groupby(["le_key", "dep_key"], as_index=False)[["project_hours", "service_hours", "available_hours"]].sum()
        g["utilisation_pct"] = np.where(g["available_hours"] > 0, ((g["project_hours"] + g["service_hours"]) / g["available_hours"].where(g["available_hours"] > 0) * 100).round(2), np.nan)
        return g
    out = m[["le_key", "dep_key", "period", "project_hours", "service_hours", "available_hours"]].copy()
    out["utilisation_pct"] = np.where(m["available_hours"] > 0, (m["project_hours"] + m["service_hours"]) / m["available_hours"].where(m["available_hours"] > 0) * 100, np.nan)
    out["stored_utilisation_pct"] = m["utilisation_pct"].astype(float)
    out["agrees"] = np.where(m["available_hours"] > 0, (out["utilisation_pct"] - out["stored_utilisation_pct"]).abs() <= tolerance + 1e-9, pd.NA)
    return out.sort_values(["le_key", "dep_key", "period"]).reset_index(drop=True)
