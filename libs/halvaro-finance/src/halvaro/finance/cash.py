"""Cash forecast checks (plan 5.9): the forecast ties to the bank, chains week to week and keeps its band; liquidity headroom to the floor; forecast accuracy by horizon.

Floors and facility limits are columns of the forecast table (the generator takes them from its configuration; a fact is needed). Tolerances are keywords marked PROPOSED.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from halvaro.core import FrameError, violations

from ._guard import staged
from ._util import _need

_COMPONENTS = ("receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new", "payments_net_wages",
               "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest")
_CF = ("le_key", "forecast_date", "week_no", "opening_cash", "net_cash_flow", "closing_cash", "closing_cash_p10", "closing_cash_p90", *_COMPONENTS)


def _tol(**kw: object) -> None:
    for name, v in kw.items():
        if isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not np.isfinite(v) or v < 0:
            raise FrameError(f"{name} must be zero or more")


@staged(sources=tuple(f"finance.cash_forecast.{c}" for c in _CF) + ("finance.bank_balance.le_key", "finance.bank_balance.balance_date", "finance.bank_balance.closing_balance"),
        oracle="py:halvaro_gen/world/finance/checks.py::cash_forecast_ties")
def cash_forecast_checks(cash_forecast: pd.DataFrame, bank_balance: pd.DataFrame, *, opening_tolerance: float = 0.005, chain_tolerance: float = 0.011, component_tolerance: float = 0.02,
                         roll_tolerance: float = 0.011) -> pd.DataFrame:
    """Use this when you need to check that a weekly cash forecast ties to the bank, chains from week to week and keeps its band.

    Rule: the forecast of an entity and forecast date is checked in five ways, and every violation is listed (the generator check stops at the first). opening_differs_from_bank: opening cash of
    week 1 against the sum of the bank balances of the entity on the forecast date. weekly_chain_broken: opening cash of a week against closing cash of the week before.
    components_do_not_sum: net cash flow against the sum of its eleven components. closing_not_opening_plus_net: closing = opening + net cash flow. outside_band: closing cash outside the
    10th to 90th percentile band. The tolerances are PROPOSED keywords.

    Args:
        cash_forecast: Frame finance.cash_forecast, one row per entity, forecast date and week, with the amounts in the entity currency.
        bank_balance: Frame finance.bank_balance with le_key, balance_date and closing_balance, one row per bank account and date.
        opening_tolerance: Largest accepted difference of opening cash and bank, in currency units (default 0.005).
        chain_tolerance: Largest accepted difference between a closing and the next opening cash (default 0.011).
        component_tolerance: Largest accepted difference between net cash flow and its components (default 0.02).
        roll_tolerance: Largest accepted difference of closing cash and opening plus net cash flow (default 0.011).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame of violations with the columns table, key, rule, detail; empty when the forecast is clean. The key is the entity, forecast date and week.
        Typed form: ViolationRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a column is missing, a tolerance is negative or not a number, or the forecast has more than one row for an entity, forecast date and week.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import cash_forecast_checks
        >>> ctx = Context(stage="month3", role="analyst")
        >>> parts = ["receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new",
        ...          "payments_net_wages", "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest"]
        >>> week = {"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": 1, "opening_cash": 1000.0, "net_cash_flow": -300.0, "closing_cash": 700.0,
        ...         "closing_cash_p10": 650.0, "closing_cash_p90": 750.0, **dict.fromkeys(parts, 0.0), "payments_vat": -300.0}
        >>> bank = pd.DataFrame({"le_key": ["LE-01"], "balance_date": ["2025-01-31"], "closing_balance": [1000.0]})
        >>> cash_forecast_checks(pd.DataFrame([week]), bank, context=ctx).empty
        True
        >>> broken = pd.DataFrame([{**week, "opening_cash": 990.0}])
        >>> sorted(cash_forecast_checks(broken, bank, context=ctx)["rule"])
        ['closing_not_opening_plus_net', 'opening_differs_from_bank']
    """
    _need(cash_forecast, list(_CF), "finance.cash_forecast")
    _need(bank_balance, ["le_key", "balance_date", "closing_balance"], "finance.bank_balance")
    _tol(opening_tolerance=opening_tolerance, chain_tolerance=chain_tolerance, component_tolerance=component_tolerance, roll_tolerance=roll_tolerance)
    if cash_forecast.duplicated(["le_key", "forecast_date", "week_no"]).any():
        raise FrameError("finance.cash_forecast has more than one row for an entity, forecast date and week")
    cf = cash_forecast.sort_values(["le_key", "forecast_date", "week_no"], kind="stable")
    rows = []
    bb = bank_balance.assign(d=pd.to_datetime(bank_balance["balance_date"]).dt.date).groupby(["le_key", "d"])["closing_balance"].sum()
    w1 = cf[cf["week_no"] == cf.groupby(["le_key", "forecast_date"])["week_no"].transform("min")]
    for r in w1.to_dict("records"):
        d = pd.Timestamp(r['forecast_date']).date()
        have = bb.get((r['le_key'], d))
        if have is None:
            rows.append(("finance.cash_forecast", f"{r['le_key']} {d}", "opening_differs_from_bank", "no bank balance on the forecast date"))
        elif abs(have - r['opening_cash']) > opening_tolerance + 1e-9:
            rows.append(("finance.cash_forecast", f"{r['le_key']} {d}", "opening_differs_from_bank", f"opening cash {r['opening_cash']:.2f}, banks {have:.2f}"))
    prev_close = cf.groupby(["le_key", "forecast_date"])["closing_cash"].shift(1)
    brk = prev_close.notna() & ((cf["opening_cash"] - prev_close).abs() > chain_tolerance + 1e-9)
    for ix, r in zip(cf[brk].index, cf[brk].to_dict("records")):
        rows.append(("finance.cash_forecast", f"{r['le_key']} {pd.Timestamp(r['forecast_date']).date()} week {r['week_no']}", "weekly_chain_broken", f"opening {r['opening_cash']:.2f}, closing of the week before {prev_close[ix]:.2f}"))
    comp = (cf[list(_COMPONENTS)].sum(axis=1) - cf["net_cash_flow"]).abs() > component_tolerance + 1e-9
    for r in cf[comp].to_dict("records"):
        rows.append(("finance.cash_forecast", f"{r['le_key']} {pd.Timestamp(r['forecast_date']).date()} week {r['week_no']}", "components_do_not_sum", f"net cash flow {r['net_cash_flow']:.2f}"))
    roll = (cf["opening_cash"] + cf["net_cash_flow"] - cf["closing_cash"]).abs() > roll_tolerance + 1e-9
    for r in cf[roll].to_dict("records"):
        rows.append(("finance.cash_forecast", f"{r['le_key']} {pd.Timestamp(r['forecast_date']).date()} week {r['week_no']}", "closing_not_opening_plus_net", f"closing {r['closing_cash']:.2f}"))
    band = (cf["closing_cash_p10"] > cf["closing_cash"]) | (cf["closing_cash_p90"] < cf["closing_cash"])
    for r in cf[band].to_dict("records"):
        rows.append(("finance.cash_forecast", f"{r['le_key']} {pd.Timestamp(r['forecast_date']).date()} week {r['week_no']}", "outside_band", f"closing {r['closing_cash']:.2f} not in {r['closing_cash_p10']:.2f} to {r['closing_cash_p90']:.2f}"))
    return violations.frame(rows)


@staged(sources=("finance.cash_forecast.le_key", "finance.cash_forecast.forecast_date", "finance.cash_forecast.week_no", "finance.cash_forecast.closing_cash", "finance.cash_forecast.closing_cash_p10",
                 "finance.cash_forecast.minimum_cash_floor", "finance.cash_forecast.rcf_limit", "finance.cash_forecast.rcf_drawn", "finance.cash_forecast.rcf_available",
                 "finance.cash_forecast.headroom_to_floor", "finance.cash_forecast.headroom_to_floor_p10", "finance.cash_forecast.floor_breach_risk"),
        oracle="py:halvaro_gen/world/finance/checks.py::cash_forecast_ties")
def liquidity_headroom(cash_forecast: pd.DataFrame, *, tolerance: float = 0.011) -> pd.DataFrame:
    """Use this when you need the headroom of a cash forecast to the minimum cash floor and the first week in which the low case falls below it.

    Rule: per week, headroom = closing cash less the floor and headroom_p10 = the 10th percentile closing cash less the floor; the facility still available = rcf_limit less rcf_drawn; a week is
    a breach week when the 10th percentile closing cash is below the floor. The result has one row per entity and forecast date. The floor and the limit are one value per forecast, taken from the
    forecast rows. The tolerance is a PROPOSED keyword.

    Args:
        cash_forecast: Frame finance.cash_forecast with the closing cash lines, the floor, the facility columns and the stored headroom columns.
        tolerance: Largest accepted difference between a recomputed and a stored column, in currency units (default 0.011).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with le_key, forecast_date, weeks (number of weeks), first_breach_week (empty when no week breaches), lowest_headroom_p10 (currency units), lowest_headroom_week,
        rcf_available_at_lowest (currency units), breach_weeks (number of weeks) and agrees (the recomputed headroom, facility and breach flag equal the stored columns).
        Typed form: HeadroomRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a column is missing, the tolerance is negative or not a number, a week appears twice for an entity and forecast date, or a forecast has more than one floor or facility limit.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import liquidity_headroom
        >>> ctx = Context(stage="month3", role="analyst")
        >>> rows = [{"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": w, "closing_cash": c, "closing_cash_p10": c - 30.0, "minimum_cash_floor": 100.0,
        ...          "rcf_limit": 500.0, "rcf_drawn": 100.0, "rcf_available": 400.0, "headroom_to_floor": c - 100.0, "headroom_to_floor_p10": c - 130.0,
        ...          "floor_breach_risk": c - 30.0 < 100.0} for w, c in ((1, 700.0), (2, 110.0))]
        >>> r = liquidity_headroom(pd.DataFrame(rows), context=ctx)
        >>> r.loc[0, ["weeks", "first_breach_week", "lowest_headroom_p10", "breach_weeks", "agrees"]].tolist() == [2, 2, -20.0, 1, True]
        True
    """
    cols = ["le_key", "forecast_date", "week_no", "closing_cash", "closing_cash_p10", "minimum_cash_floor", "rcf_limit", "rcf_drawn", "rcf_available", "headroom_to_floor", "headroom_to_floor_p10", "floor_breach_risk"]
    _need(cash_forecast, cols, "finance.cash_forecast")
    _tol(tolerance=tolerance)
    cf = cash_forecast.sort_values(["le_key", "forecast_date", "week_no"], kind="stable")
    if cf.duplicated(["le_key", "forecast_date", "week_no"]).any():
        raise FrameError("finance.cash_forecast has more than one row for an entity, forecast date and week")
    if cf.groupby(["le_key", "forecast_date"])[["minimum_cash_floor", "rcf_limit"]].nunique().gt(1).any().any():
        raise FrameError("a forecast has more than one floor or facility limit")
    f = cf["minimum_cash_floor"].astype(float)
    h, hp10 = cf["closing_cash"] - f, cf["closing_cash_p10"] - f
    avail = cf["rcf_limit"].astype(float) - cf["rcf_drawn"].astype(float)
    breach = cf["closing_cash_p10"] < f
    ok = ((h - cf["headroom_to_floor"]).abs() <= tolerance) & ((hp10 - cf["headroom_to_floor_p10"]).abs() <= tolerance) & ((avail - cf["rcf_available"]).abs() <= tolerance) & (breach == cf["floor_breach_risk"].astype(bool))
    x = pd.DataFrame({"le_key": cf["le_key"], "forecast_date": cf["forecast_date"], "week_no": cf["week_no"], "hp10": hp10, "avail": avail, "breach": breach, "ok": ok})
    rows = []
    for (le, fd), g in x.groupby(["le_key", "forecast_date"], sort=True):
        low = g.loc[g["hp10"].idxmin()]
        b = g[g["breach"]]
        rows.append({"le_key": le, "forecast_date": fd, "weeks": len(g), "first_breach_week": int(b["week_no"].min()) if len(b) else np.nan, "lowest_headroom_p10": round(float(low["hp10"]), 2),
                     "lowest_headroom_week": int(low["week_no"]), "rcf_available_at_lowest": round(float(low["avail"]), 2), "breach_weeks": int(len(b)), "agrees": bool(g["ok"].all())})
    return pd.DataFrame(rows)


@staged(sources=("finance.cash_forecast.le_key", "finance.cash_forecast.week_no", "finance.cash_forecast.closing_cash", "finance.cash_forecast.closing_cash_p10", "finance.cash_forecast.closing_cash_p90",
                 "finance.cash_forecast.actual_closing_cash_ex_rcf"), oracle="py:tests/test_finance_planning.py::test_cash_forecast_band_covers_most_actuals_but_not_all")
def forecast_accuracy(cash_forecast: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need to know how well a cash forecast covered the actual closing cash, by entity and forecast horizon.

    Rule: over the forecast weeks that have an actual closing cash (without the facility), coverage = the share of weeks whose actual is inside the 10th to 90th percentile band, and the error is
    actual less forecast closing cash. Weeks without an actual are left out; an entity without any actual has no rows. Rows with week_no 0 hold all horizons of the entity.

    Args:
        cash_forecast: Frame finance.cash_forecast with le_key, week_no, closing_cash, the two band columns and actual_closing_cash_ex_rcf.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with le_key, week_no (0 for all horizons), n (number of weeks), coverage (share between 0 and 1), mean_abs_error and median_abs_error and mean_error (currency units; mean_error is
        positive when the forecast was too low).
        Typed form: AccuracyRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a column is missing.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import forecast_accuracy
        >>> ctx = Context(stage="month3", role="analyst")
        >>> cf = pd.DataFrame({"le_key": "LE-01", "week_no": [1, 2], "closing_cash": [700.0, 650.0], "closing_cash_p10": [670.0, 600.0], "closing_cash_p90": [730.0, 700.0],
        ...                    "actual_closing_cash_ex_rcf": [710.0, 720.0]})
        >>> r = forecast_accuracy(cf, context=ctx).set_index("week_no")
        >>> r.loc[0, ["n", "coverage", "mean_error"]].tolist() == [2, 0.5, 40.0]
        True
    """
    _need(cash_forecast, ["le_key", "week_no", "closing_cash", "closing_cash_p10", "closing_cash_p90", "actual_closing_cash_ex_rcf"], "finance.cash_forecast")
    x = cash_forecast[cash_forecast["actual_closing_cash_ex_rcf"].notna()].copy()
    if x.empty:
        return pd.DataFrame(columns=["le_key", "week_no", "n", "coverage", "mean_abs_error", "median_abs_error", "mean_error"])
    x["inside"] = (x["actual_closing_cash_ex_rcf"] >= x["closing_cash_p10"]) & (x["actual_closing_cash_ex_rcf"] <= x["closing_cash_p90"])
    x["err"] = x["actual_closing_cash_ex_rcf"] - x["closing_cash"]
    agg = lambda g: pd.Series({"n": len(g), "coverage": round(float(g["inside"].mean()), 4), "mean_abs_error": round(float(g["err"].abs().mean()), 2), "median_abs_error": round(float(g["err"].abs().median()), 2),
                               "mean_error": round(float(g["err"].mean()), 2)})
    by = x.groupby(["le_key", "week_no"]).apply(agg, include_groups=False).reset_index()  # type: ignore[call-overload]  # pandas-stubs has no include_groups overload
    allw = x.groupby("le_key").apply(agg, include_groups=False).reset_index().assign(week_no=0)  # type: ignore[call-overload]  # pandas-stubs has no include_groups overload
    out = pd.concat([allw, by], ignore_index=True).sort_values(["le_key", "week_no"]).reset_index(drop=True)
    out["n"] = out["n"].astype(int)
    return pd.DataFrame(out)
