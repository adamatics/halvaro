"""Project view: percent of completion, revenue, loss provision, contract position, margins and the write-down journal, from finance.project_financials.

Completion comes from the caller (`actual_end` per project, the delivery status of a project is not recomputed here); the cap before completion is a required keyword because it is a config value
without a fact id yet (`cfg:finance.yaml#projects.poc_cap_before_completion`). Amounts are in the contract currency of the row, never summed across currencies.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, violations

from ._guard import staged
from ._util import _cents, _days, _need

_PF = ["prj_key", "period", "contract_value", "eac", "actual_cost", "billed", "revenue_recognised", "loss_provision"]


def _actual_end(actual_end: Any) -> pd.Series:
    """prj_key to end date from a Series, a dict or a frame with prj_key and actual_end; missing or null means not completed."""
    if isinstance(actual_end, pd.DataFrame):
        _need(actual_end, ["prj_key", "actual_end"], "projects.project")
        actual_end = actual_end.set_index("prj_key")["actual_end"]
    s = pd.Series(actual_end) if not isinstance(actual_end, pd.Series) else actual_end
    if s.index.duplicated().any():
        raise FrameError(f"actual_end names {', '.join(sorted(set(map(str, s.index[s.index.duplicated()]))))} more than once")
    return _days(pd.DataFrame({"d": s}), ["d"], "actual_end")["d"]


_PERIOD = r"\d{4}-\d{2}"


def _check_periods(period: pd.Series, what: str) -> None:
    if period.isna().any() or not period.astype(str).str.fullmatch(_PERIOD).all():
        raise FrameError(f"{what}.period must be text like 2025-03 for every row")


def _fraction(pf: pd.DataFrame, actual_end: Any, cap: float) -> np.ndarray:
    """Cost to cost fraction: 1 when the project ended on or before the end of the period, else cost over EAC capped. A cap outside (0, 1] or an EAC of zero raises."""
    _need(pf, ["prj_key", "period", "actual_cost", "eac"], "finance.project_financials")
    if not isinstance(cap, (int, float, np.number)) or isinstance(cap, bool) or not 0 < cap <= 1:
        raise FrameError(f"cap must be a number in (0, 1], for example the config value projects.poc_cap_before_completion; got {cap!r}")
    _check_periods(pf["period"], "finance.project_financials")
    ends = _actual_end(actual_end)
    if len(ends) and len(pf) and not pf["prj_key"].isin(ends.index).any():
        raise FrameError("none of the keys of actual_end is a prj_key of the frame; pass a Series indexed by prj_key")
    end = pf["prj_key"].map(ends)
    month_end = pd.to_datetime(pf["period"] + "-01") + pd.offsets.MonthEnd(0)
    done = (end.notna() & (end <= month_end)).to_numpy()
    eac = pf["eac"].to_numpy(dtype=float)
    if (~done & ~(eac > 0)).any():
        raise FrameError(f"{int((~done & ~(eac > 0)).sum())} rows of projects still running have an EAC of zero or null")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(done, 1.0, np.minimum(pf["actual_cost"].to_numpy(dtype=float) / eac, cap))


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.actual_cost", "finance.project_financials.eac"),
        oracle="py:tests/tieout_c.py::t17_project_revenue")
def percent_complete(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float) -> pd.Series:
    """Use this when you need the percent of completion of each project row by cost to cost: actual cost over the estimate at completion.

    Rule: a running project has the actual cost over the EAC, limited by cap; a project that ended on or before the end of the period has 100. The result is in percent with two decimals.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, one row per project and period.
        actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
        cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.Series named percent_complete, on the index of the frame, from 0 to 100.

    Raises:
        FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import percent_complete
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "actual_cost": [400.0, 780.0, 800.0], "eac": [800.0, 800.0, 800.0]})
        >>> percent_complete(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
        [50.0, 95.0, 100.0]
        >>> percent_complete(pf, {}, cap=1.5, context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: cap must be a number in (0, 1], ...
    """
    return pd.Series(np.round(_fraction(project_financials, actual_end, cap) * 100, 2), index=project_financials.index, name="percent_complete")


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.actual_cost", "finance.project_financials.eac",
                 "finance.project_financials.contract_value"), oracle="py:tests/tieout_c.py::t17_project_revenue")
def revenue_recognised(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float) -> pd.Series:
    """Use this when you need the revenue recognised to date on each project row: the contract value times the cost to cost fraction.

    Rule: the contract value in cents times the fraction of percent_complete (actual cost over EAC, limited by cap), rounded to the cent; the full contract value when the project has ended on or before the end of the period.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value, one row per project and period.
        actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
        cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.Series named revenue_recognised, on the index of the frame, in the contract currency of the row.

    Raises:
        FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import revenue_recognised
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-3"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "actual_cost": [400.0, 800.0], "eac": [800.0, 800.0]})
        >>> revenue_recognised(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
        [500.0, 1000.0]
    """
    _need(project_financials, ["contract_value"], "finance.project_financials")
    f = _fraction(project_financials, actual_end, cap)
    return pd.Series(np.rint(np.rint(project_financials["contract_value"].to_numpy(dtype=float) * 100) * f) / 100, index=project_financials.index, name="revenue_recognised")


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.actual_cost", "finance.project_financials.eac",
                 "finance.project_financials.contract_value"), oracle="py:tests/tieout_c.py::t17_project_revenue")
def loss_provision(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float) -> pd.Series:
    """Use this when you need the provision for the loss that a project is expected to make: the part of the expected loss not yet recognised.

    Rule: the expected loss is the EAC above the contract value (zero when the EAC is not above it). The provision is the expected loss times one less the cost to cost fraction, rounded to two decimals; none when the project has ended.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value, one row per project and period.
        actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
        cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.Series named loss_provision, on the index of the frame, in the contract currency of the row; zero where no loss is expected.

    Raises:
        FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import loss_provision
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "contract_value": [1000.0] * 3,
        ...                    "actual_cost": [400.0, 600.0, 1200.0], "eac": [800.0, 1200.0, 1200.0]})
        >>> loss_provision(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
        [0.0, 100.0, 0.0]
    """
    _need(project_financials, ["contract_value"], "finance.project_financials")
    f = _fraction(project_financials, actual_end, cap)
    loss = np.clip(project_financials["eac"].to_numpy(dtype=float) - project_financials["contract_value"].to_numpy(dtype=float), 0, None)
    return pd.Series(np.where(f >= 1.0, 0.0, np.round(loss * (1 - f), 2)), index=project_financials.index, name="loss_provision")


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.actual_cost", "finance.project_financials.eac",
                 "finance.project_financials.contract_value", "finance.project_financials.billed"), oracle="py:tests/tieout_c.py::t17_project_revenue")
def contract_position(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float) -> pd.DataFrame:
    """Use this when you need revenue recognised less billed on each project row, split into the contract asset and the contract liability.

    Rule: the position is revenue_recognised less billed. A positive position is the contract asset (wip, GL-2100), a negative one the contract liability (GL-4500, shown as a positive amount).

    Args:
        project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value and billed, one row per project and period.
        actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
        cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, period, revenue_recognised, billed, contract_position (asset positive, liability negative), wip and contract_liability, on the index of the frame.

    Raises:
        FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import contract_position
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "billed": [300.0, 700.0],
        ...                    "actual_cost": [400.0, 400.0], "eac": [800.0, 800.0]})
        >>> contract_position(pf, {}, cap=0.95, context=ctx)[["prj_key", "contract_position", "wip", "contract_liability"]].to_dict("records")
        [{'prj_key': 'PRJ-1', 'contract_position': 200.0, 'wip': 200.0, 'contract_liability': 0.0}, {'prj_key': 'PRJ-2', 'contract_position': -200.0, 'wip': 0.0, 'contract_liability': 200.0}]
    """
    _need(project_financials, ["billed"], "finance.project_financials")
    rev = cast(Any, revenue_recognised).__wrapped__(project_financials, actual_end, cap=cap)
    pos = (rev - project_financials["billed"]).round(2)
    return pd.DataFrame({"prj_key": project_financials["prj_key"], "period": project_financials["period"], "revenue_recognised": rev, "billed": project_financials["billed"],
                         "contract_position": pos, "wip": pos.clip(lower=0), "contract_liability": (-pos).clip(lower=0)})


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.contract_value", "finance.project_financials.eac",
                 "finance.project_financials.actual_cost", "finance.project_financials.revenue_recognised", "finance.project_financials.loss_provision"))
def project_margin(project_financials: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the two named margins of a project and period in percent: the margin to date and the margin forecast at completion. Never one "margin". To follow one project period by period together with its write-down, use margin_trail.

    Rule: margin_pct is (revenue recognised less actual cost less loss provision) over revenue recognised, empty without revenue. forecast_margin_pct is (contract value less EAC) over contract value, empty without a contract value. Both are rounded to two decimals.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, period, margin_pct and forecast_margin_pct, on the index of the frame.

    Raises:
        FrameError: a column is missing.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import project_margin
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "eac": [800.0, 1200.0],
        ...                    "actual_cost": [400.0, 600.0], "revenue_recognised": [500.0, 500.0], "loss_provision": [0.0, 100.0]})
        >>> project_margin(pf, context=ctx)[["prj_key", "margin_pct", "forecast_margin_pct"]].to_dict("records")
        [{'prj_key': 'PRJ-1', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0}, {'prj_key': 'PRJ-2', 'margin_pct': -40.0, 'forecast_margin_pct': -20.0}]
    """
    _need(project_financials, _PF[:2] + ["contract_value", "eac", "actual_cost", "revenue_recognised", "loss_provision"], "finance.project_financials")
    pf = project_financials
    rev, cv = pf["revenue_recognised"].to_numpy(dtype=float), pf["contract_value"].to_numpy(dtype=float)
    margin = rev - pf["actual_cost"].to_numpy(dtype=float) - pf["loss_provision"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        to_date = np.where(rev > 0, np.round(margin / np.maximum(rev, 1e-9) * 100, 2), np.nan)
        at_completion = np.where(cv > 0, np.round((cv - pf["eac"].to_numpy(dtype=float)) / np.maximum(cv, 1e-9) * 100, 2), np.nan)
    return pd.DataFrame({"prj_key": pf["prj_key"].to_numpy(), "period": pf["period"].to_numpy(), "margin_pct": to_date, "forecast_margin_pct": at_completion}, index=pf.index)


@staged(sources=("finance.journal_header.source", "finance.journal_header.posting_date", "finance.journal_line.prj_key", "finance.journal_line.gl_key", "finance.journal_line.amount",
                 "finance.journal_line.amount_dkk"), oracle="py:halvaro_gen/world/finance/facts.py::build_truth")
def write_down_journal(manual: pd.DataFrame, prj_key: str, *, gl_key: str = "GL-5190") -> pd.DataFrame:
    """Use this when you need the write-down lines booked on one project, from the manual journals.

    Rule: the rows of the manual journals on the project and on the write-down account, in the order of posting date and journal number. There is no guess from a change of margin: a project without such a row gives an empty frame.

    Args:
        manual: The manual journals, the output of ledger.manual_journals, with le_key, journal_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk.
        prj_key: The project key.
        gl_key: The write-down account. PROPOSED default GL-5190, until the fact fin.project_accounting.write_down_gl_key exists.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with le_key, journal_no, posting_date, description, currency, amount and amount_dkk; empty when the project has no write-down.

    Raises:
        FrameError: a column is missing or a posting date is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import write_down_journal
        >>> ctx = Context(stage="month3", role="analyst")
        >>> manual = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": ["J-2", "J-1"], "posting_date": ["2026-03-31", "2026-02-28"], "description": ["write down"] * 2,
        ...                        "gl_key": ["GL-5190"] * 2, "prj_key": ["PRJ-2"] * 2, "currency": ["DKK"] * 2, "amount": [50.0, 25.0], "amount_dkk": [50.0, 25.0]})
        >>> write_down_journal(manual, "PRJ-2", context=ctx)[["journal_no", "posting_date", "amount_dkk"]].to_dict("records")
        [{'journal_no': 'J-1', 'posting_date': '2026-02-28', 'amount_dkk': 25.0}, {'journal_no': 'J-2', 'posting_date': '2026-03-31', 'amount_dkk': 50.0}]
        >>> write_down_journal(manual, "PRJ-9", context=ctx).empty
        True
    """
    _need(manual, ["le_key", "journal_no", "posting_date", "description", "gl_key", "prj_key", "currency", "amount", "amount_dkk"], "manual_journals output")
    out = manual[(manual["prj_key"] == prj_key) & (manual["gl_key"] == gl_key)]
    out = out[["le_key", "journal_no", "posting_date", "description", "currency", "amount", "amount_dkk"]]
    when = _days(out, ["posting_date"], "manual_journals output")["posting_date"]
    return out.iloc[np.lexsort((out["journal_no"].to_numpy(), when.to_numpy()))].reset_index(drop=True)


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.contract_value", "finance.project_financials.eac",
                 "finance.project_financials.actual_cost", "finance.project_financials.revenue_recognised", "finance.project_financials.loss_provision"))
def margin_trail(project_financials: pd.DataFrame, prj_key: str, write_down: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you follow the margin of one project period by period, with the period and amount of its write-down. For the margins alone, of all projects at once, project_margin is enough.

    Rule: the rows of the project in period order, with margin_pct and forecast_margin_pct as in project_margin. Each write-down journal line is put on the period of its posting month: write_down_period is true there, and write_down_amount (entity currency) and write_down_amount_dkk add up the lines of that month to two decimals; elsewhere they are empty. The amounts stay in the currency of the rows and are never summed across currencies.

    Args:
        project_financials: Frame finance.project_financials with prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
        prj_key: The project key.
        write_down: The output of write_down_journal with posting_date, amount and amount_dkk (and currency if present). Default None, no write-down.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with period, currency, margin_pct, forecast_margin_pct, write_down_period, write_down_amount and write_down_amount_dkk, one row per period of the project.

    Raises:
        FrameError: prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised or loss_provision is missing, the project has no row, a posting date is missing or not a date, an amount is null, a period is repeated for the project (checked only when write_down is given), the write-down is in another currency than the rows, or the write-down is posted in a month without a row of the project.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import margin_trail
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "period": ["2026-02", "2026-03"], "currency": ["EUR", "EUR"], "contract_value": [1000.0, 1000.0], "eac": [800.0, 800.0],
        ...                    "actual_cost": [300.0, 400.0], "revenue_recognised": [400.0, 500.0], "loss_provision": [0.0, 0.0]})
        >>> wd = pd.DataFrame({"posting_date": ["2026-03-15"], "amount": [40.0], "amount_dkk": [300.0]})
        >>> margin_trail(pf, "PRJ-1", wd, context=ctx)[["period", "margin_pct", "forecast_margin_pct", "write_down_period", "write_down_amount_dkk"]].to_dict("records")
        [{'period': '2026-02', 'margin_pct': 25.0, 'forecast_margin_pct': 20.0, 'write_down_period': False, 'write_down_amount_dkk': nan}, {'period': '2026-03', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0, 'write_down_period': True, 'write_down_amount_dkk': 300.0}]
    """
    _need(project_financials, ["currency"], "finance.project_financials")
    _need(project_financials, ["prj_key", "period"], "finance.project_financials")
    x = project_financials[project_financials["prj_key"] == prj_key].sort_values("period")
    if x.empty:
        raise FrameError(f"{prj_key} has no rows in finance.project_financials")
    m: pd.DataFrame = cast(Any, project_margin).__wrapped__(x)
    out = m[["period", "margin_pct", "forecast_margin_pct"]].assign(currency=x["currency"].to_numpy())[["period", "currency", "margin_pct", "forecast_margin_pct"]].reset_index(drop=True)
    out["write_down_period"], out["write_down_amount"], out["write_down_amount_dkk"] = False, np.nan, np.nan
    if write_down is not None and len(write_down):
        _need(write_down, ["posting_date", "amount", "amount_dkk"], "write_down_journal output")
        wd = _days(write_down, ["posting_date"], "write_down_journal output")
        if wd["posting_date"].isna().any():
            raise FrameError("a write-down journal has no posting date")
        if write_down[["amount", "amount_dkk"]].isna().any().any():
            raise FrameError("a write-down journal has a null amount; a null would be dropped or kept depending on the row order")
        if out["period"].duplicated().any():
            raise FrameError(f"finance.project_financials has more than one row of {prj_key} in a period")
        if "currency" in write_down.columns and (write_down["currency"].nunique() > 1 or (write_down["currency"] != out["currency"].iloc[0]).any()):
            raise FrameError("the write-down journals are not in the currency of the project rows; amounts are never summed across currencies")
        outside = sorted(set(wd["posting_date"].dt.strftime("%Y-%m")) - set(out["period"]))
        if outside:
            raise FrameError(f"the write-down is posted in {outside[0]}, a month without a finance.project_financials row of {prj_key}")
        r: Any
        for r in wd.itertuples():
            hit = out["period"] == r.posting_date.strftime("%Y-%m")
            out.loc[hit, "write_down_period"] = True
            out.loc[hit, "write_down_amount"] = (out.loc[hit, "write_down_amount"].fillna(0) + r.amount).round(2)
            out.loc[hit, "write_down_amount_dkk"] = (out.loc[hit, "write_down_amount_dkk"].fillna(0) + r.amount_dkk).round(2)
    return out


@staged(sources=("finance.project_financials.prj_key", "finance.project_financials.period", "finance.project_financials.eac", "finance.project_financials.actual_cost",
                 "finance.project_financials.committed_cost", "finance.project_financials.currency"))
def cost_to_completion(project_financials: pd.DataFrame, prj_keys: str | Sequence[str], period: str) -> pd.DataFrame:
    """Use this when you need the cost still to come on a list of projects in one period: EAC less actual cost, with the committed cost shown apart.

    Rule: cost_to_completion is EAC less actual cost and uncommitted is that less the committed cost, both to two decimals. Amounts stay in the currency of the row and are never summed across currencies. A project without a row in the period is listed with the reason "no finance row".

    Args:
        project_financials: Frame finance.project_financials with prj_key, period, currency, eac, actual_cost and committed_cost, one row per project and period.
        prj_keys: The projects, one key or a list of keys, each at most once.
        period: The period, text like 2026-03.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, period, currency, eac, actual_cost, cost_to_completion, committed_cost, uncommitted and reason, one row per key in the order given.

    Raises:
        FrameError: a column is missing, a period is not text like 2026-03, a key is repeated, or the frame has two rows for a project in the period.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import cost_to_completion
        >>> ctx = Context(stage="month3", role="analyst")
        >>> pf = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["DKK"], "eac": [800.0], "actual_cost": [400.0], "committed_cost": [100.0]})
        >>> r = cost_to_completion(pf, ["PRJ-1", "PRJ-9"], "2026-03", context=ctx).set_index("prj_key")
        >>> r[["cost_to_completion", "uncommitted"]].loc["PRJ-1"].to_dict(), r.loc["PRJ-9", "reason"]
        ({'cost_to_completion': 400.0, 'uncommitted': 300.0}, 'no finance row')
        >>> cost_to_completion(pf, ["PRJ-1"], "2026-3", context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: period must be text like 2025-11, not '2026-3'
    """
    _need(project_financials, ["prj_key", "period", "currency", "eac", "actual_cost", "committed_cost"], "finance.project_financials")
    _check_periods(project_financials["period"], "finance.project_financials")
    if not isinstance(period, str) or not re.fullmatch(_PERIOD, period):
        raise FrameError(f"period must be text like 2025-11, not {period!r}")
    keys = [prj_keys] if isinstance(prj_keys, str) else list(prj_keys)
    if len(set(keys)) != len(keys):
        raise FrameError("prj_keys has repeated keys")
    x = project_financials[(project_financials["period"] == period) & project_financials["prj_key"].isin(keys)]
    if x["prj_key"].duplicated().any():
        raise FrameError(f"finance.project_financials has more than one row for a project in {period}")
    out = pd.DataFrame({"prj_key": pd.Series(keys, dtype=object)}).merge(x[["prj_key", "currency", "eac", "actual_cost", "committed_cost"]].assign(_row=True), on="prj_key", how="left")
    out["period"] = period
    out["cost_to_completion"] = (out["eac"] - out["actual_cost"]).round(2)
    out["uncommitted"] = (out["cost_to_completion"] - out["committed_cost"]).round(2)
    out["reason"] = np.where(out["_row"].isna(), "no finance row", None)
    return out[["prj_key", "period", "currency", "eac", "actual_cost", "cost_to_completion", "committed_cost", "uncommitted", "reason"]]


@staged(sources=("finance.order_intake_backlog.le_key", "finance.order_intake_backlog.project_type", "finance.order_intake_backlog.period", "finance.order_intake_backlog.backlog_opening",
                 "finance.order_intake_backlog.order_intake_total", "finance.order_intake_backlog.revenue_recognised", "finance.order_intake_backlog.backlog_closing"),
        oracle="py:halvaro_gen/world/finance/checks.py::order_book_identity")
def order_book_check(order_intake_backlog: pd.DataFrame, *, tolerance: float = 0.05) -> pd.DataFrame:
    """Use this when you check the order book of each entity and project type: the closing backlog is the opening plus order intake less revenue recognised, and the opening is the previous closing.

    Rule: roll_forward when the closing differs from opening plus intake less revenue by more than tolerance (default 0.05, proposed); opening_not_previous_closing when the opening differs from the closing of the month before by more than the same tolerance. Book to bill is not tied.

    Args:
        order_intake_backlog: Frame finance.order_intake_backlog with le_key, project_type, period, backlog_opening, order_intake_total, revenue_recognised and backlog_closing, no missing months.
        tolerance: Largest accepted difference, zero or more, in the unit of the backlog columns. Default 0.05 (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail; empty when the order book is clean.

    Raises:
        FrameError: a column is missing, tolerance is not a number of zero or more, a value is null, a key and period is repeated, or a month is skipped within an entity and project type.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import order_book_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> book = pd.DataFrame({"le_key": ["LE-01"] * 2, "project_type": ["dh_network"] * 2, "period": ["2026-01", "2026-02"], "backlog_opening": [100.0, 150.0],
        ...                      "order_intake_total": [80.0, 40.0], "revenue_recognised": [30.0, 40.0], "backlog_closing": [150.0, 160.0]})
        >>> order_book_check(book, context=ctx)[["key", "rule"]].values.tolist()
        [['LE-01 dh_network 2026-02', 'roll_forward']]
    """
    cols = ["le_key", "project_type", "period", "backlog_opening", "order_intake_total", "revenue_recognised", "backlog_closing"]
    _need(order_intake_backlog, cols, "finance.order_intake_backlog")
    if not isinstance(tolerance, (int, float)) or not tolerance >= 0:
        raise FrameError(f"tolerance must be a number of at least 0, not {tolerance!r}")
    ob = order_intake_backlog
    if ob[cols].isna().any().any():
        raise FrameError(f"finance.order_intake_backlog has {int(ob[cols].isna().sum().sum())} null values in {', '.join(c for c in cols if ob[c].isna().any())}")
    _check_periods(ob["period"], "finance.order_intake_backlog")
    if ob.duplicated(["le_key", "project_type", "period"]).any():
        raise FrameError("finance.order_intake_backlog has more than one row for the same le_key, project_type and period")
    o = ob.sort_values(["le_key", "project_type", "period"], kind="stable")
    month = o["period"].str[:4].astype(int) * 12 + o["period"].str[5:7].astype(int)
    if (month.groupby([o["le_key"], o["project_type"]]).diff().dropna() != 1).any():
        raise FrameError("finance.order_intake_backlog skips a month within a le_key and project_type; the opening cannot be tied to the previous closing")
    key = o["le_key"] + " " + o["project_type"] + " " + o["period"]
    roll = (o["backlog_closing"] - (o["backlog_opening"] + o["order_intake_total"] - o["revenue_recognised"])).abs() > tolerance + 1e-9
    prev = o.groupby(["le_key", "project_type"])["backlog_closing"].shift()
    gap = prev.notna() & ((o["backlog_opening"] - prev).abs() > tolerance + 1e-9)
    rows = [("finance.order_intake_backlog", k, "roll_forward", "closing differs from opening + intake - revenue") for k in key[roll]]
    rows += [("finance.order_intake_backlog", k, "opening_not_previous_closing", "opening differs from the previous closing") for k in key[gap]]
    return violations.frame(rows)
