"""Project cost views from the cost breakdown: labour cost against budget and cost per metre by cost code.

The function ids are those of the plan (halvaro.finance.project_view.*). Amounts stay in the currency of the project, never summed across currencies. The comparable set of the cost per metre view is an argument:
finance never imports delivery.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need, _numeric

_PLAN_MODULE = "halvaro.finance.project_view"
_PERIOD = r"\d{4}-\d{2}"


def _period(value: Any, what: str) -> str:
    """'2026-11', a date or a Timestamp as a period text."""
    if isinstance(value, (bool, int, float, np.number)):
        raise FrameError(f"{what} {value!r} is a number, not a month")
    try:
        if isinstance(value, str) and len(value) == 7:
            return pd.Timestamp(value + "-01").strftime("%Y-%m")
        return pd.Timestamp(value).strftime("%Y-%m")
    except (ValueError, TypeError) as e:
        raise FrameError(f"{what} {value!r} is not a month: {e}") from None


def _breakdown(cb: pd.DataFrame) -> pd.DataFrame:
    _need(cb, ["prj_key", "period", "cst_key", "currency", "actual_amount", "incurred_in_period", "estimate_amount"], "finance.project_cost_breakdown")
    if cb["period"].isna().any() or not cb["period"].astype(str).str.fullmatch(_PERIOD).all():
        raise FrameError("finance.project_cost_breakdown.period must be text like 2025-03 for every row")
    nulls = [c for c in ("actual_amount", "incurred_in_period", "estimate_amount") if cb[c].isna().any()]
    if nulls:
        raise FrameError(f"finance.project_cost_breakdown has null values in {', '.join(nulls)}")
    if cb.duplicated(["prj_key", "period", "cst_key"]).any():
        raise FrameError("finance.project_cost_breakdown has more than one row for the same prj_key, period and cst_key")
    if cb.groupby("prj_key")["currency"].nunique().gt(1).any():
        raise FrameError("a project has cost breakdown rows in more than one currency; amounts are never summed across currencies")
    return cb


@staged(id=f"{_PLAN_MODULE}.labour_cost_overrun",
        sources=("finance.project_cost_breakdown.prj_key", "finance.project_cost_breakdown.period", "finance.project_cost_breakdown.cst_key", "finance.project_cost_breakdown.currency",
                 "finance.project_cost_breakdown.actual_amount", "finance.project_cost_breakdown.incurred_in_period", "finance.project_cost_breakdown.estimate_amount",
                 "finance.project_budget_line.prj_key", "finance.project_budget_line.cst_key", "finance.project_budget_line.budget_version", "finance.project_budget_line.budget_amount",
                 "finance.project_budget_line.currency", "projects.cost_code.cst_key", "projects.cost_code.category", "projects.cost_code.is_group"),
        oracle="py:repo_tests/test_oracle_project_costs_release.py::test_oracle_labour_cost_overrun_baseline_per_project_against_plain_loops")
def labour_cost_overrun(project_cost_breakdown: pd.DataFrame, project_budget_line: pd.DataFrame, cost_code: pd.DataFrame, window_start: dt.date | str | pd.Timestamp, window_end: dt.date | str | pd.Timestamp, *, active_only: bool = True) -> pd.DataFrame:
    """Use this when you rank projects by how far their labour cost has run over the labour budget in a window of months.

    Rule: labour is every leaf cost code (not a group) of category labour. Per project, in its own currency: labour_budget is the sum of the budget lines of the original (lowest) budget version, labour_estimate the latest estimate at completion, labour_actual_to_date the cumulative actual at the last period up to the window end, and labour_actual_window the cost incurred in the window. overrun_vs_budget_pct is actual to date over budget less 100, and overrun_vs_estimate_pct is the same against the estimate; both compare cost to date with the whole budget or estimate, so they understate a project that has only started. A project without labour budget is listed with null percentages and the reason "no labour budget". Rows are sorted by overrun_vs_budget_pct, largest first; the estimate percent is a second measure that can rank the projects differently, so say which measure a ranking uses. The definition of the overrun is a business choice (proposed).

    Args:
        project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
        project_budget_line: Frame finance.project_budget_line with prj_key, cst_key, budget_version, budget_amount and currency.
        cost_code: Frame projects.cost_code with cst_key, category and is_group, one row per cost code.
        window_start: First month of the window, a month text like 2026-01 or a date.
        window_end: Last month of the window, in the same forms.
        active_only: True keeps the projects with labour cost incurred in the window; False lists every project with cost up to the window end. Default True.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, currency, labour_budget, labour_estimate, labour_actual_to_date, labour_actual_window, overrun_vs_budget_pct, overrun_vs_estimate_pct and reason.

    Raises:
        FrameError: a column is missing, a window bound is not a month, the window starts after it ends, a period is not text like 2026-01, a value is null where one is needed, a key is repeated, a project has more than one currency, a cost code of the breakdown is not in cost_code, cost_code has no labour leaf, or a budget is in another currency than the cost rows.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import labour_cost_overrun
        >>> ctx = Context(stage="month12", role="analyst")
        >>> costs = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-01"], "cst_key": ["CST-L"], "currency": ["EUR"], "actual_amount": [120.0], "incurred_in_period": [120.0], "estimate_amount": [130.0]})
        >>> budget = pd.DataFrame({"prj_key": ["PRJ-1"], "cst_key": ["CST-L"], "budget_version": [1], "budget_amount": [100.0], "currency": ["EUR"]})
        >>> codes = pd.DataFrame({"cst_key": ["CST-L"], "category": ["labour"], "is_group": [False]})
        >>> labour_cost_overrun(costs, budget, codes, "2026-01", "2026-01", context=ctx)[["prj_key", "labour_budget", "labour_actual_to_date", "overrun_vs_budget_pct"]].values.tolist()
        [['PRJ-1', 100.0, 120.0, 20.0]]
    """
    cb = _breakdown(project_cost_breakdown)
    _need(project_budget_line, ["prj_key", "cst_key", "budget_version", "budget_amount", "currency"], "finance.project_budget_line")
    _need(cost_code, ["cst_key", "category", "is_group"], "projects.cost_code")
    w0, w1 = _period(window_start, "window_start"), _period(window_end, "window_end")
    if w0 > w1:
        raise FrameError(f"the window starts {w0} after it ends {w1}")
    if cost_code[["cst_key", "category", "is_group"]].isna().any().any():
        raise FrameError("projects.cost_code has null values in cst_key, category or is_group")
    if cost_code["cst_key"].duplicated().any():
        raise FrameError("projects.cost_code has more than one row for a cst_key")
    labour = set(cost_code.loc[(cost_code["category"] == "labour") & ~cost_code["is_group"].astype(bool), "cst_key"])
    if not labour:
        raise FrameError("projects.cost_code has no leaf cost code of category labour")
    unknown = sorted(set(cb["cst_key"]) - set(cost_code["cst_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} cost codes of the breakdown are not in projects.cost_code (for example {unknown[0]})")
    c = cb[cb["cst_key"].isin(labour) & (cb["period"] <= w1)]
    last = c.sort_values("period").groupby(["prj_key", "cst_key"], as_index=False).tail(1)
    latest = cb[cb["cst_key"].isin(labour)].sort_values("period").groupby(["prj_key", "cst_key"], as_index=False).tail(1)
    estimate = latest.groupby("prj_key")["estimate_amount"].sum().rename("labour_estimate")           # a constant per code: the latest estimate, whatever the window end
    to_date = last.groupby("prj_key").agg(currency=("currency", "first"), labour_actual_to_date=("actual_amount", "sum")).join(estimate)
    in_window = c[c["period"] >= w0].groupby("prj_key")["incurred_in_period"].sum().rename("labour_actual_window")
    if project_budget_line["budget_amount"].isna().any():
        raise FrameError("finance.project_budget_line has null budget_amount values")
    pb = project_budget_line[project_budget_line["cst_key"].isin(labour)]
    if len(pb):
        pb = pb[pb["budget_version"] == pb.groupby("prj_key")["budget_version"].transform("min")]
        if pb.duplicated(["prj_key", "cst_key"]).any():
            raise FrameError("finance.project_budget_line has more than one line for a project and cost code in its original version")
        if pb.groupby("prj_key")["currency"].nunique().gt(1).any():
            raise FrameError("a project has labour budget lines in more than one currency")
    bud = pb.groupby("prj_key").agg(labour_budget=("budget_amount", "sum"), budget_currency=("currency", "first"))
    out = to_date.join(in_window).join(bud)
    out["labour_actual_window"] = out["labour_actual_window"].fillna(0.0)
    clash = out["budget_currency"].notna() & (out["budget_currency"] != out["currency"])
    if clash.any():
        raise FrameError(f"{int(clash.sum())} projects have a labour budget in another currency than their cost rows; amounts are never summed across currencies")
    pos = out["labour_budget"] > 0
    out["overrun_vs_budget_pct"] = np.where(pos, np.round((out["labour_actual_to_date"] / out["labour_budget"].where(pos) - 1) * 100, 2), np.nan)
    out["overrun_vs_estimate_pct"] = np.where(pos & (out["labour_estimate"] > 0), np.round((out["labour_actual_to_date"] / out["labour_estimate"].where(out["labour_estimate"] > 0) - 1) * 100, 2), np.nan)
    out["reason"] = np.where(pos, None, "no labour budget")
    out = out.drop(columns="budget_currency").reset_index()
    if active_only:
        out = out[out["labour_actual_window"] > 0]
    for col in ("labour_actual_to_date", "labour_actual_window", "labour_estimate"):
        out[col] = out[col].round(2)
    out = out.sort_values(["overrun_vs_budget_pct", "prj_key"], ascending=[False, True], na_position="last").reset_index(drop=True)
    return out[["prj_key", "currency", "labour_budget", "labour_estimate", "labour_actual_to_date", "labour_actual_window", "overrun_vs_budget_pct", "overrun_vs_estimate_pct", "reason"]]


class CostPerMetre(NamedTuple):
    """by_code: cst_key, currency, n_projects, median_per_metre; per_project: prj_key, cst_key, currency, cost_at_completion, route_length_m, per_metre, route_source, legacy;
    dropped: prj_key and the reason."""
    by_code: pd.DataFrame
    per_project: pd.DataFrame
    dropped: pd.DataFrame


@staged(id=f"{_PLAN_MODULE}.cost_per_metre_by_cost_code",
        sources=("finance.project_cost_breakdown.prj_key", "finance.project_cost_breakdown.period", "finance.project_cost_breakdown.cst_key", "finance.project_cost_breakdown.currency",
                 "finance.project_cost_breakdown.actual_amount", "finance.project_cost_breakdown.incurred_in_period", "finance.project_cost_breakdown.estimate_amount",
                 "projects.project.prj_key", "projects.project.route_length_m"),
        oracle="py:repo_tests/test_oracle_project_costs_release.py::test_oracle_cost_per_metre_by_cost_code_baseline_per_project_and_code_against_plain_loops")
def cost_per_metre_by_cost_code(comparable_set: pd.DataFrame, project_cost_breakdown: pd.DataFrame, project: pd.DataFrame, route_change: pd.DataFrame | None = None) -> CostPerMetre:
    """Use this when you compare projects by actual cost per metre of route for each cost code, with the median over the projects.

    Rule: per project and cost code the last breakdown row (the latest period) gives the cost at completion, which is the cost to date for an active project; it is divided by the route length in metres and rounded to four decimals. The median per code is taken over the projects, per currency. A project with no breakdown row, or without a route length above zero, is left out and listed in dropped, never estimated; a code a project has no row for is left out of that code's median, not counted as zero. An as-built length above zero replaces the planned length and is flagged in route_source. The as-built column is a stand-in (proposed).

    Args:
        comparable_set: Frame of the projects to compare with prj_key and legacy (and data_depth if present), one row per project.
        project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
        project: Frame projects.project with prj_key and route_length_m, one row per project.
        route_change: Optional frame with prj_key and as_built_length_m, one row per project; a missing or non positive length keeps the planned one. Default None.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        CostPerMetre, a named tuple of three frames: by_code with cst_key, currency, n_projects and median_per_metre; per_project with prj_key, cst_key, currency, cost_at_completion, route_length_m, per_metre, route_source (as_built or planned) and legacy; dropped with prj_key and reason (no finance rows or no route length).

    Raises:
        FrameError: a column is missing, actual_amount, route_length_m or as_built_length_m holds text that is not a number, a period is not text like 2026-01, a breakdown value is null, a breakdown row is repeated for a project, period and cost code, a project has more than one currency, a key is repeated in the comparable set, projects or route_change, or a project of the comparable set is not in projects.project.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import cost_per_metre_by_cost_code
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cs = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "legacy": [False, False, False]})
        >>> pr = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "route_length_m": [100.0, 200.0, 50.0]})
        >>> cb = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-A", "PRJ-B"], "period": ["2026-01", "2026-02", "2026-02"], "cst_key": ["CST-1"] * 3, "currency": ["DKK"] * 3,
        ...                    "actual_amount": [500.0, 1000.0, 3000.0], "incurred_in_period": [500.0, 500.0, 3000.0], "estimate_amount": [1200.0, 1200.0, 3200.0]})
        >>> res = cost_per_metre_by_cost_code(cs, cb, pr, context=ctx)
        >>> res.per_project[["prj_key", "per_metre"]].values.tolist()
        [['PRJ-A', 10.0], ['PRJ-B', 15.0]]
        >>> res.by_code[["cst_key", "n_projects", "median_per_metre"]].values.tolist()
        [['CST-1', 2, 12.5]]
        >>> res.dropped.values.tolist()
        [['PRJ-C', 'no finance rows']]
    """
    cb = _breakdown(project_cost_breakdown)
    _need(comparable_set, ["prj_key", "legacy"], "delivery comparable_set frame")
    _need(project, ["prj_key", "route_length_m"], "projects.project")
    _numeric(cb, ["actual_amount"], "finance.project_cost_breakdown")
    _numeric(project, ["route_length_m"], "projects.project")
    if comparable_set["prj_key"].duplicated().any():
        raise FrameError("the comparable set lists a project more than once")
    if project["prj_key"].duplicated().any():
        raise FrameError("projects.project has more than one row for a prj_key")
    keys = comparable_set["prj_key"]
    unknown = sorted(set(keys) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the comparable set are not in projects.project (for example {unknown[0]})")
    length = project.set_index("prj_key")["route_length_m"].astype(float).reindex(keys)
    source: pd.Series = pd.Series("planned", index=keys.to_numpy())
    length.index = keys.to_numpy()
    if route_change is not None:
        _need(route_change, ["prj_key", "as_built_length_m"], "grid route_change frame")
        _numeric(route_change, ["as_built_length_m"], "grid route_change frame")
        if route_change["prj_key"].duplicated().any():
            raise FrameError("the route_change frame has more than one row for a prj_key")
        ab = route_change.set_index("prj_key")["as_built_length_m"].astype(float).reindex(keys).to_numpy()
        use = ab > 0                                                         # a missing or non positive as-built length leaves the planned one
        length = pd.Series(np.where(use, ab, length.to_numpy()), index=keys.to_numpy())
        source = pd.Series(np.where(use, "as_built", "planned"), index=keys.to_numpy())
    last = cb.sort_values("period").groupby(["prj_key", "cst_key"], as_index=False).tail(1)
    have = set(last["prj_key"])
    dropped = []
    for k in keys:
        if k not in have:
            dropped.append((k, "no finance rows"))
        elif not length[k] > 0:
            dropped.append((k, "no route length"))
    drop = {k for k, _ in dropped}
    x = last[last["prj_key"].isin(set(keys) - drop)].copy()
    x["route_length_m"] = x["prj_key"].map(length)
    x["route_source"] = x["prj_key"].map(source)
    x["cost_at_completion"] = x["actual_amount"]
    x["per_metre"] = (x["actual_amount"] / x["route_length_m"]).round(4)
    x["legacy"] = x["prj_key"].map(comparable_set.set_index("prj_key")["legacy"])
    per = x[["prj_key", "cst_key", "currency", "cost_at_completion", "route_length_m", "per_metre", "route_source", "legacy"]].sort_values(["prj_key", "cst_key"]).reset_index(drop=True)
    by = (per.groupby(["cst_key", "currency"]).agg(n_projects=("prj_key", "nunique"), median_per_metre=("per_metre", "median")).reset_index().sort_values(["cst_key", "currency"]).reset_index(drop=True))
    return CostPerMetre(by, per, pd.DataFrame(dropped, columns=["prj_key", "reason"]))
