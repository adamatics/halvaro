"""Estimating: the estimate versions by type and cost code, amount per route metre, the distribution of schedule and cost overrun over a set, delay cause shares and the risks and lessons that match them (plan 5.3).

Money stays in the contract currency of the row. Nothing here sums across currencies: a result that would is split by currency.
"""
from __future__ import annotations

from typing import Any, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from ._types import DateLike

_KB = ("DA.REF.212",)
_TYPES = ("tender", "budget", "forecast", "final")        # the estimate version types (plan 3.4); several forecast versions may exist, the latest one counts
_EST = ("projects.estimate_version.prj_key", "projects.estimate_version.estimate_version", "projects.estimate_version.type", "projects.estimate_version.date",
        "projects.estimate_version.currency", "projects.estimate_version.total_cost", "projects.estimate_line.prj_key", "projects.estimate_line.estimate_version",
        "projects.estimate_line.cst_key", "projects.estimate_line.amount", "projects.cost_code.cst_key", "projects.cost_code.category")


def _frame_need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    if frame.columns.duplicated().any():
        raise FrameError(f"{what} has duplicate column names ({', '.join(map(str, frame.columns[frame.columns.duplicated()]))})")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys:
        if frame[list(keys)].isna().any().any():
            raise FrameError(f"{what} has rows with a null in {', '.join(keys)}")
        dup = frame[frame.duplicated(list(keys), keep=False)]
        if len(dup):
            raise FrameError(f"{what} has {len(dup)} rows sharing {', '.join(keys)} (for example {dup.iloc[0][keys[0]]}); one row per key is required")


_STATUSES = ("planned", "active", "completed")
_NOT_DUE = {"planned": ("forecast", "final"), "active": ("forecast", "final"), "completed": ("forecast",)}      # by status the versions that need not exist; forecast is never tied to status (see estimate_bridge)


def _as_of_day(as_of: Any) -> pd.Timestamp:
    """as_of as a calendar day; numbers, time zones and unreadable values are refused (FrameError, as for the frame dates)."""
    if isinstance(as_of, (bool, int, float, np.number)):
        raise FrameError(f"as_of {as_of!r} is a number, not a date; pass a date, a Timestamp or an ISO text such as 2026-11-30")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d):
        raise FrameError(f"as_of {as_of!r} is not a date")
    if d.tzinfo is not None:
        raise FrameError(f"as_of {as_of!r} has a time zone; dates here are calendar days, pass it without one")
    return d.normalize()


def _version_days(column: pd.Series) -> pd.Series:
    try:
        try:
            out = pd.to_datetime(column)
        except ValueError:
            out = pd.to_datetime(column, format="mixed")      # dates with and without a time of day in one column
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"projects.estimate_version.date holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError("projects.estimate_version.date has a time zone; dates here are calendar days")
    if out.isna().any():
        raise FrameError("projects.estimate_version.date has nulls; the versions valid on as_of cannot be told")
    return out.dt.normalize()


class EstimateBridge(NamedTuple):
    """Result of estimate_bridge: amounts by cost code, one total per project and type, and the versions missing for a project."""

    lines: pd.DataFrame
    totals: pd.DataFrame
    missing: pd.DataFrame


@staged(sources=_EST, kb=_KB, oracle="py:tests/test_projects.py::test_estimates")
def estimate_bridge(estimate_version: pd.DataFrame, estimate_line: pd.DataFrame, cost_code: pd.DataFrame, *, full_projects: Sequence[str] | None = None, as_of: DateLike | None = None, status: pd.Series | None = None) -> EstimateBridge:
    """Use this when you need the amounts by cost code of the tender, budget, forecast and final estimate of each project, with the stored totals and the versions that are missing.

    Per project and type the latest version counts (highest estimate_version); a project may have several forecast versions. With `as_of` only versions dated on or before it exist, so the forecasts quoted at an earlier date are the earlier versions; as_of is a calendar day, inclusive (a version dated that day, at any time of day, counts), and a number, a time zone or an unreadable date is refused with FrameError. Money stays in the currency of the version; nothing is converted. Several estimate lines of one cost code are kept as separate lines.

    Result fields: lines has prj_key, type, estimate_version, cst_key, category, amount, currency. totals has one row per project and type with the line sum, the stored total_cost and their difference (the generator asserts it within 40). missing lists the (prj_key, type) pairs without a version, for `full_projects` when given (legacy summary projects have no estimates and are not listed).

    Which absences are expected: the baseline data (full projects) has tender and budget for every project, final for every completed project and for no other, and forecast for all active projects but only for part of the completed ones and for no planned one, so a forecast is NOT tied to status (it is optional) while tender, budget and final are. Pass `status` (a Series prj_key -> planned, active or completed, for example from projects.project_status) and missing gains a boolean column `expected`: True where the absence is by design (planned: tender and budget only, so forecast and final are expected; active: final expected; completed: nothing but forecast; forecast is always expected), False where the version should exist or the status of the project is not given. Without `status` missing has the two columns only.

    Args:
        estimate_version: The projects.estimate_version frame, one row per prj_key and estimate_version; it needs prj_key, estimate_version, type (tender, budget, forecast or final), date, currency and total_cost.
        estimate_line: The projects.estimate_line frame; it needs prj_key, estimate_version, cst_key and amount, and may carry currency.
        cost_code: The projects.cost_code frame, one row per cst_key; it needs cst_key and category.
        full_projects: The prj_key values of the full projects for which missing versions are listed (a key as text or a list); without it missing is empty.
        as_of: The day on which only versions dated on or before it exist (a date, a Timestamp or an ISO text); without it every version counts.
        status: A Series prj_key -> planned, active or completed that adds the column `expected` to missing; without it missing has the two columns only.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An EstimateBridge (named tuple) of three DataFrames. lines is sorted by prj_key, type and cst_key; totals by prj_key and type (columns prj_key, type, estimate_version, currency, total_cost, line_sum, difference); missing by project in the order of the types tender, budget, forecast, final (columns prj_key, type and, with status, expected).

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names, lacks a needed column, has a null in or repeats a key (estimate_version by prj_key and estimate_version, cost_code by cst_key); type is not text, is null or is not one of tender, budget, forecast, final; amount or total_cost is not numeric or has nulls; category has nulls; as_of is a number, has a time zone or is not a date; a version date is not a date, has a time zone or is null; an estimate line belongs to a version that is not in estimate_version or points at a cst_key that is not in cost_code; a line currency differs from the currency of its version; status is not a Series, repeats a project or holds an unknown value.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import estimate_bridge
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ver = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "estimate_version": [1, 2], "type": ["tender", "budget"],
        ...                     "date": ["2025-01-10", "2025-02-01"], "currency": ["DKK", "DKK"], "total_cost": [150.0, 140.0]})
        >>> line = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "estimate_version": [1, 1, 2], "cst_key": ["CST-100", "CST-200", "CST-100"], "amount": [100.0, 50.0, 140.0]})
        >>> codes = pd.DataFrame({"cst_key": ["CST-100", "CST-200"], "category": ["civil", "electrical"]})
        >>> r = estimate_bridge(ver, line, codes, full_projects=["PRJ-900001"], status=pd.Series({"PRJ-900001": "planned"}), context=ctx)
        >>> r.totals["type"].tolist()
        ['budget', 'tender']
        >>> r.missing[["type", "expected"]].values.tolist()
        [['forecast', True], ['final', True]]"""
    _frame_need(estimate_version, ["prj_key", "estimate_version", "type", "date", "currency", "total_cost"], "projects.estimate_version", keys=("prj_key", "estimate_version"))
    _frame_need(estimate_line, ["prj_key", "estimate_version", "cst_key", "amount"], "projects.estimate_line")
    _frame_need(cost_code, ["cst_key", "category"], "projects.cost_code", keys=("cst_key",))
    if estimate_version["type"].isna().any() or not estimate_version["type"].map(lambda t: isinstance(t, str)).all():
        raise FrameError("projects.estimate_version.type must be text without nulls")
    bad = sorted(set(estimate_version["type"]) - set(_TYPES))
    if bad:
        raise FrameError(f"projects.estimate_version.type has unknown value(s) {', '.join(bad)}; known: {', '.join(_TYPES)}")
    if len(estimate_line) and (not pd.api.types.is_numeric_dtype(estimate_line["amount"]) or estimate_line["amount"].isna().any()):
        raise FrameError("projects.estimate_line.amount must be numeric without nulls")
    if not pd.api.types.is_numeric_dtype(estimate_version["total_cost"]) or estimate_version["total_cost"].isna().any():
        raise FrameError("projects.estimate_version.total_cost must be numeric without nulls")
    if cost_code["category"].isna().any():
        raise FrameError("projects.cost_code.category has nulls")
    versions = estimate_version
    if as_of is not None:
        day = _as_of_day(as_of)
        versions = versions[_version_days(versions["date"]) <= day]
    if len(estimate_line):
        known = set(zip(estimate_version["prj_key"], estimate_version["estimate_version"]))
        orphan = [k for k in zip(estimate_line["prj_key"], estimate_line["estimate_version"]) if k not in known]
        if orphan:
            raise FrameError(f"{len(orphan)} estimate lines belong to a version that is not in projects.estimate_version (for example {orphan[0][0]} version {orphan[0][1]})")
        if "currency" in estimate_line.columns:
            cur = estimate_line.merge(estimate_version[["prj_key", "estimate_version", "currency"]], on=["prj_key", "estimate_version"], suffixes=("", "_version"))
            if (cur["currency"] != cur["currency_version"]).any():
                r = cur[cur["currency"] != cur["currency_version"]].iloc[0]
                raise FrameError(f"an estimate line of {r['prj_key']} is in {r['currency']}, its version in {r['currency_version']}; no conversion is made")
    v = versions.sort_values(["prj_key", "type", "estimate_version"]).drop_duplicates(["prj_key", "type"], keep="last")
    ln = estimate_line[["prj_key", "estimate_version", "cst_key", "amount"]].merge(v[["prj_key", "estimate_version", "type", "currency"]], on=["prj_key", "estimate_version"], how="inner").merge(cost_code[["cst_key", "category"]], on="cst_key", how="left")
    if ln["category"].isna().any():
        raise FrameError(f"{int(ln['category'].isna().sum())} estimate lines point at a cst_key that is not in projects.cost_code (for example {ln.loc[ln['category'].isna(), 'cst_key'].iloc[0]})")
    lines = ln[["prj_key", "type", "estimate_version", "cst_key", "category", "amount", "currency"]].sort_values(["prj_key", "type", "cst_key"]).reset_index(drop=True)
    sums = cast(pd.DataFrame, ln.groupby(["prj_key", "type"], as_index=False)["amount"].sum()).rename(columns={"amount": "line_sum"})
    totals = v[["prj_key", "type", "estimate_version", "currency", "total_cost"]].merge(sums, on=["prj_key", "type"], how="left")
    totals["line_sum"] = totals["line_sum"].fillna(0.0)
    totals["difference"] = totals["line_sum"] - totals["total_cost"]
    totals = totals.sort_values(["prj_key", "type"]).reset_index(drop=True)
    if full_projects is None:
        missing = pd.DataFrame(columns=["prj_key", "type"])
    else:
        full_projects = [full_projects] if isinstance(full_projects, str) else full_projects
        have = set(zip(v["prj_key"], v["type"]))
        missing = pd.DataFrame([(p, t) for p in sorted(set(full_projects)) for t in _TYPES if (p, t) not in have], columns=["prj_key", "type"])
    if status is not None:
        if not isinstance(status, pd.Series):
            raise FrameError(f"status must be a Series of prj_key -> status, not {type(status).__name__}")
        if status.index.duplicated().any():
            raise FrameError(f"status has more than one value for {status.index[status.index.duplicated()][0]}")
        badst = sorted(set(status.dropna().astype(str)) - set(_STATUSES))
        if badst:
            raise FrameError(f"status has unknown value(s) {', '.join(badst)}; known: {', '.join(_STATUSES)}")
        st = missing["prj_key"].map(status)
        missing["expected"] = [t == "forecast" or (s in _NOT_DUE and t in _NOT_DUE[s]) for t, s in zip(missing["type"], st)]
        missing["expected"] = missing["expected"].astype(bool)
    return EstimateBridge(lines, totals, missing)


@staged(sources=("projects.project.prj_key", "projects.project.route_length_m", "projects.estimate_line.amount", "projects.cost_code.category"), kb=_KB,
        oracle="py:tests/test_projects.py::test_estimates")
def estimate_amount_per_metre(lines: pd.DataFrame, project: pd.DataFrame, *, route_length: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need the estimate amount per route metre by cost code and category for each project, from the lines of estimate_bridge.

    Rows follow the `lines` frame of estimate_bridge. per_metre is null when the length is null or not positive (the project is kept, nothing is dropped silently). `route_length` (prj_key, route_length_m) replaces the planned length, for example the as-built length from the route change of the grid library; where its value is null the planned length is used. length_source says which: 'as_built' (the length of `route_length`) or 'planned' (the project frame). The estimate side only: actual cost per metre is a finance function. Amounts of different currencies are never added; each row keeps its currency.

    Args:
        lines: The lines output of estimate_bridge; it needs prj_key, type, cst_key, category, amount (numeric, no nulls) and currency.
        project: The projects.project frame, one row per prj_key; it needs prj_key and route_length_m (the planned length, numeric).
        route_length: Optional frame with prj_key (one row each) and route_length_m that replaces the planned length where its value is not null.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame in the order of the lines with the columns prj_key, type, cst_key, category, currency, amount, route_length_m, length_source and per_metre (amount over the length, null where the length is null or not positive).

    Raises:
        FrameError: lines, project or route_length is not a DataFrame, lacks a needed column or (project, route_length) repeats a prj_key; a project of the lines is not in the project frame; amount is not numeric or has nulls; route_length_m is not numeric.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import estimate_amount_per_metre
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "type": ["tender", "tender"], "cst_key": ["CST-100", "CST-200"],
        ...                       "category": ["civil", "electrical"], "amount": [100.0, 50.0], "currency": ["DKK", "DKK"]})
        >>> project = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [1000.0]})
        >>> r = estimate_amount_per_metre(lines, project, context=ctx)
        >>> [round(x, 3) for x in r["per_metre"]]
        [0.1, 0.05]
        >>> built = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [500.0]})
        >>> r = estimate_amount_per_metre(lines, project, route_length=built, context=ctx)
        >>> r["length_source"].unique().tolist()
        ['as_built']"""
    _frame_need(lines, ["prj_key", "type", "cst_key", "category", "amount", "currency"], "estimate_bridge lines")
    _frame_need(project, ["prj_key", "route_length_m"], "projects.project", keys=("prj_key",))
    length = project.set_index("prj_key")["route_length_m"]
    unknown = sorted(set(lines["prj_key"]) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the lines are not in the project frame (for example {unknown[0]})")
    if len(lines) and (not pd.api.types.is_numeric_dtype(lines["amount"]) or lines["amount"].isna().any()):
        raise FrameError("the amount of the lines must be numeric without nulls")
    built = None
    if route_length is not None:
        _frame_need(route_length, ["prj_key", "route_length_m"], "route_length", keys=("prj_key",))
        built = route_length.set_index("prj_key")["route_length_m"]
        length = built.combine_first(length)
    if not pd.api.types.is_numeric_dtype(length):
        raise FrameError("route_length_m must be numeric")
    out = lines[["prj_key", "type", "cst_key", "category", "currency", "amount"]].copy()
    out["route_length_m"] = out["prj_key"].map(length)
    out["length_source"] = np.where(out["prj_key"].map(built).notna(), "as_built", "planned") if built is not None else "planned"
    ok = (out["route_length_m"] > 0) & np.isfinite(out["route_length_m"])
    out["per_metre"] = np.where(ok, out["amount"] / out["route_length_m"].where(ok), np.nan)
    return out.reset_index(drop=True)


@staged(sources=("projects.project.prj_key", "projects.project.final_cost", "projects.project.legacy", "projects.project.currency", "projects.estimate_version.total_cost"), kb=_KB,
        oracle="py:tests/test_projects.py::test_cell_calibration")
def overrun_distribution(overrun: pd.DataFrame, project: pd.DataFrame, totals: pd.DataFrame | None = None, *, projects: Sequence[str] | None = None) -> pd.DataFrame:
    """Use this when you need the spread of the schedule overrun, and with estimate totals of the cost overrun, over a set of completed projects.

    The measures are the minimum, quartiles, median, maximum and mean of the schedule overrun (the `overrun` column of schedule_overrun for completed projects, basis actual) and, with `totals` (estimate_bridge totals), of the cost overrun: final_cost over the tender total minus one, full projects with both numbers, contract currency, no conversion. `projects` limits the set (a comparable set). PROPOSED: the definitions of policy.delivery.overrun_definition (needed): schedule fraction as in the generator test, cost overrun a separate measure.

    Args:
        overrun: The output of schedule_overrun; it needs prj_key and a numeric overrun, and may carry basis (only the rows of basis actual count; without a basis column every row is taken as actual).
        project: The projects.project frame, one row per prj_key; it needs prj_key, final_cost, legacy and currency.
        totals: Optional totals output of estimate_bridge (prj_key, type, total_cost, currency); the tender rows give the cost overrun measure. Without it only the schedule measure is returned.
        projects: Optional prj_key values (a key as text or a list) that limit the set.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per measure (schedule, then cost when totals is given) and the columns measure, n, n_legacy, min, q25, median, q75, max, mean. The statistics are null when n is zero.

    Raises:
        FrameError: overrun, project or totals is not a DataFrame, lacks a needed column or (project) repeats a prj_key; overrun is not numeric; the overrun frame has more than one actual row for a project; a project of the overrun frame is not in the project frame; with totals: final_cost is not numeric, a project has more than one tender row, or a tender is in another currency than the project.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import overrun_distribution
        >>> ctx = Context(stage="month12", role="analyst")
        >>> overrun = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "overrun": [0.1, 0.3], "basis": ["actual", "actual"]})
        >>> project = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "final_cost": [120.0, 200.0], "legacy": [False, False], "currency": ["DKK", "DKK"]})
        >>> totals = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "type": ["tender", "tender"], "total_cost": [100.0, 100.0], "currency": ["DKK", "DKK"]})
        >>> r = overrun_distribution(overrun, project, totals, context=ctx)
        >>> r["measure"].tolist()
        ['schedule', 'cost']
        >>> [round(x, 3) for x in r["median"]]
        [0.2, 0.6]"""
    _frame_need(overrun, ["prj_key", "overrun"], "schedule_overrun output")
    _frame_need(project, ["prj_key", "final_cost", "legacy", "currency"], "projects.project", keys=("prj_key",))
    keep = None if projects is None else set([projects] if isinstance(projects, str) else projects)
    legacy = project.set_index("prj_key")["legacy"]
    if not pd.api.types.is_numeric_dtype(overrun["overrun"]):
        raise FrameError("the overrun column must be numeric")
    s = overrun[overrun["basis"] == "actual"] if "basis" in overrun.columns else overrun      # without a basis column every row is taken as actual
    if s["prj_key"].duplicated().any():
        raise FrameError(f"the overrun frame has more than one actual row for {s.loc[s['prj_key'].duplicated(), 'prj_key'].iloc[0]}")
    if keep is not None:
        s = s[s["prj_key"].isin(keep)]
    unknown = sorted(set(s["prj_key"]) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the overrun frame are not in the project frame (for example {unknown[0]})")
    rows = [_describe("schedule", s["prj_key"], s["overrun"], legacy)]
    if totals is not None:
        _frame_need(totals, ["prj_key", "type", "total_cost", "currency"], "estimate_bridge totals")
        if not pd.api.types.is_numeric_dtype(project["final_cost"]):
            raise FrameError("projects.project.final_cost must be numeric")
        tt = totals[totals["type"] == "tender"]
        if tt["prj_key"].duplicated().any():
            raise FrameError(f"the totals have more than one tender row for {tt.loc[tt['prj_key'].duplicated(), 'prj_key'].iloc[0]}")
        t = tt.set_index("prj_key")
        p = project.set_index("prj_key")
        both = p[p["final_cost"].notna()].join(t[["total_cost", "currency"]].rename(columns={"currency": "tender_currency"}), how="inner")
        if keep is not None:
            both = both[both.index.isin(keep)]
        clash = both[(both["tender_currency"] != both["currency"]) & both["currency"].notna()]
        if len(clash):
            raise FrameError(f"{len(clash)} projects have a tender in another currency than the project (for example {clash.index[0]}); no conversion is made")
        cost = both[both["total_cost"] > 0]
        rows.append(_describe("cost", pd.Series(cost.index), pd.Series((cost["final_cost"] / cost["total_cost"] - 1).to_numpy()), legacy))
    return pd.DataFrame(rows)


def _describe(measure: str, keys: pd.Series, values: pd.Series, legacy: pd.Series) -> dict[str, Any]:
    v = pd.Series(values.to_numpy(dtype=float))
    n = int(v.notna().sum())
    q = v.quantile([0, 0.25, 0.5, 0.75, 1.0]).tolist() if n else [np.nan] * 5
    return {"measure": measure, "n": n, "n_legacy": int(((pd.Series(keys.to_numpy()).map(legacy) == True) & v.notna()).sum()),      # noqa: E712
            "min": q[0], "q25": q[1], "median": q[2], "q75": q[3], "max": q[4], "mean": float(v.mean()) if n else np.nan}


@staged(sources=("projects.delay_event.prj_key", "projects.delay_event.cause_code", "projects.delay_event.responsible_party", "projects.delay_event.days", "projects.delay_event.mtg_key",
                 "projects.project.prj_key", "projects.project.data_depth"), kb=_KB, oracle="py:tests/test_project_history.py::test_ground_conditions_dominate_german_dh_on_clay")
def cause_shares(delay_event: pd.DataFrame, project: pd.DataFrame, *, projects: Sequence[str] | None = None) -> pd.DataFrame:
    """Use this when you need the delay days by cause code and responsible party, with their shares, for all events and for the events linked to a meeting.

    Two views: all_events (every delay event of the projects) and full_linked (full projects, events linked to a meeting through mtg_key). Columns: view, cause_code, responsible_party, events, days, share (of the days of the view) and cause_share (the days of the whole cause_code over the days of the view). `projects` limits the set (a comparable set).

    Args:
        delay_event: The projects.delay_event frame; it needs prj_key, cause_code, responsible_party, days and mtg_key.
        project: The projects.project frame, one row per prj_key; it needs prj_key and data_depth (full or not).
        projects: Optional prj_key values (a key as text or a list) that limit the set.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns view, cause_code, responsible_party, events, days, share and cause_share, sorted by view and days (high first), then cause_code and responsible_party.

    Raises:
        FrameError: delay_event or project is not a DataFrame, lacks a needed column or (project) repeats a prj_key; days is not numeric or has nulls; a row has a null prj_key, cause_code or responsible_party; a project of the delay events is not in the project frame.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import cause_shares
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ev = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "cause_code": ["ground_conditions", "ground_conditions", "weather"],
        ...                    "responsible_party": ["client", "client", "nature"], "days": [10, 20, 10], "mtg_key": ["MTG-900001", None, "MTG-900002"]})
        >>> project = pd.DataFrame({"prj_key": ["PRJ-900001"], "data_depth": ["full"]})
        >>> r = cause_shares(ev, project, context=ctx)
        >>> r[r["view"] == "all_events"]["days"].tolist()
        [30, 10]
        >>> [round(x, 2) for x in r[r["view"] == "all_events"]["share"]]
        [0.75, 0.25]"""
    _frame_need(delay_event, ["prj_key", "cause_code", "responsible_party", "days", "mtg_key"], "projects.delay_event")
    _frame_need(project, ["prj_key", "data_depth"], "projects.project", keys=("prj_key",))
    if not pd.api.types.is_numeric_dtype(delay_event["days"]) or delay_event["days"].isna().any():
        raise FrameError("projects.delay_event.days must be numeric without nulls")
    nulls = [c for c in ("prj_key", "cause_code", "responsible_party") if delay_event[c].isna().any()]
    if nulls:
        raise FrameError(f"projects.delay_event has rows with a null {', '.join(nulls)}; they would drop out of the shares")
    ev = delay_event if projects is None else delay_event[delay_event["prj_key"].isin(set([projects] if isinstance(projects, str) else projects))]
    unknown = set(ev["prj_key"]) - set(project["prj_key"])
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the delay events are not in the project frame (for example {sorted(unknown)[0]})")
    full = set(project.loc[project["data_depth"] == "full", "prj_key"])
    views = {"all_events": ev, "full_linked": ev[ev["prj_key"].isin(full) & ev["mtg_key"].notna()]}
    parts = []
    for name, x in views.items():
        g = x.groupby(["cause_code", "responsible_party"], as_index=False).agg(events=("days", "size"), days=("days", "sum"))
        g.insert(0, "view", name)
        g["share"] = g["days"] / g["days"].sum() if len(g) else pd.Series(dtype=float)
        g["cause_share"] = g.groupby("cause_code")["days"].transform("sum") / g["days"].sum() if len(g) else pd.Series(dtype=float)
        parts.append(g.sort_values(["days", "cause_code", "responsible_party"], ascending=[False, True, True]))
    return pd.concat(parts, ignore_index=True)


class RiskLessons(NamedTuple):
    """Result of risk_lessons_summary: counts by risk cause and lesson category, the occurred risks matched to their delay event and the lessons matched to theirs."""

    risk_causes: pd.DataFrame
    lesson_categories: pd.DataFrame
    occurred: pd.DataFrame
    lessons: pd.DataFrame


@staged(sources=("projects.risk.prj_key", "projects.risk.cause_code", "projects.risk.status", "projects.risk.delay_seq", "projects.lesson_learned.prj_key", "projects.lesson_learned.category",
                 "projects.lesson_learned.delay_seq", "projects.delay_event.prj_key", "projects.delay_event.seq", "projects.delay_event.cause_code"), kb=_KB,
        oracle="py:tests/test_project_history.py::test_ground_conditions_dominate_german_dh_on_clay")
def risk_lessons_summary(risk: pd.DataFrame, lesson_learned: pd.DataFrame, delay_event: pd.DataFrame, *, projects: Sequence[str] | None = None) -> RiskLessons:
    """Use this when you need the most frequent risk causes and lesson categories of a set of projects and whether occurred risks and lessons match the cause of their delay event.

    The top cause codes of risks and the lesson categories of a set (counts, high first), and the occurred risks (status occurred) matched to their delay event by prj_key and delay_seq. Lessons count only when linked to a delay event (delay_seq set); `lessons` matches each of them to the cause of its event the same way (a delay_seq without an event does not match).

    Args:
        risk: The projects.risk frame; it needs prj_key, risk_no, cause_code (no nulls), status and delay_seq (whole numbers or null).
        lesson_learned: The projects.lesson_learned frame; it needs prj_key, category and delay_seq (whole numbers or null).
        delay_event: The projects.delay_event frame, one row per prj_key and seq; it needs prj_key, seq and cause_code.
        projects: Optional prj_key values (a key as text or a list) that limit the risks and lessons to a set.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A RiskLessons (named tuple) of four DataFrames. risk_causes: cause_code and risks, high first. lesson_categories: category and lessons, high first. occurred: prj_key, risk_no, delay_seq, risk_cause, event_cause and matches (the causes agree; false also when the event is missing), sorted by prj_key and risk_no. lessons: prj_key, category, delay_seq, event_cause and matches, sorted by prj_key, delay_seq and category.

    Raises:
        FrameError: a frame is not a DataFrame, lacks a needed column or (delay_event) has a null in or repeats prj_key and seq; a risk has a null cause_code; delay_seq of the risks or lessons is not numeric or holds a value that is not a whole number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import risk_lessons_summary
        >>> ctx = Context(stage="month12", role="analyst")
        >>> risk = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "risk_no": [1, 2], "cause_code": ["ground_conditions", "weather"],
        ...                      "status": ["occurred", "open"], "delay_seq": [1.0, None]})
        >>> lesson = pd.DataFrame({"prj_key": ["PRJ-900001"], "category": ["ground_conditions"], "delay_seq": [1.0]})
        >>> event = pd.DataFrame({"prj_key": ["PRJ-900001"], "seq": [1], "cause_code": ["ground_conditions"]})
        >>> r = risk_lessons_summary(risk, lesson, event, context=ctx)
        >>> r.risk_causes["risks"].tolist()
        [1, 1]
        >>> r.occurred["matches"].tolist()
        [True]
        >>> r.lessons["matches"].tolist()
        [True]"""
    _frame_need(risk, ["prj_key", "risk_no", "cause_code", "status", "delay_seq"], "projects.risk")
    _frame_need(lesson_learned, ["prj_key", "category", "delay_seq"], "projects.lesson_learned")
    _frame_need(delay_event, ["prj_key", "seq", "cause_code"], "projects.delay_event", keys=("prj_key", "seq"))
    keep = None if projects is None else set([projects] if isinstance(projects, str) else projects)
    if risk["cause_code"].isna().any():
        raise FrameError("projects.risk.cause_code has nulls")
    for name, f in (("projects.risk", risk), ("projects.lesson_learned", lesson_learned)):
        ds = f["delay_seq"].dropna()
        if not pd.api.types.is_numeric_dtype(f["delay_seq"]) or (ds % 1 != 0).any():
            raise FrameError(f"{name}.delay_seq must hold whole numbers")
    rk = risk if keep is None else risk[risk["prj_key"].isin(keep)]
    ls = lesson_learned if keep is None else lesson_learned[lesson_learned["prj_key"].isin(keep)]
    ls = ls[ls["delay_seq"].notna()]
    causes = rk.groupby("cause_code", as_index=False).size().rename(columns={"size": "risks"}).sort_values(["risks", "cause_code"], ascending=[False, True]).reset_index(drop=True)
    cats = ls.groupby("category", as_index=False).size().rename(columns={"size": "lessons"}).sort_values(["lessons", "category"], ascending=[False, True]).reset_index(drop=True)
    occ = rk[rk["status"] == "occurred"][["prj_key", "risk_no", "delay_seq", "cause_code"]].rename(columns={"cause_code": "risk_cause"})
    ev = delay_event[["prj_key", "seq", "cause_code"]].rename(columns={"seq": "delay_seq", "cause_code": "event_cause"})
    occ = occ.assign(delay_seq=occ["delay_seq"].astype("Int64")).merge(ev.assign(delay_seq=ev["delay_seq"].astype("Int64")), on=["prj_key", "delay_seq"], how="left")
    occ["matches"] = occ["risk_cause"] == occ["event_cause"]
    les = ls[["prj_key", "category", "delay_seq"]].assign(delay_seq=ls["delay_seq"].astype("Int64")).merge(ev.assign(delay_seq=ev["delay_seq"].astype("Int64")), on=["prj_key", "delay_seq"], how="left")
    les["matches"] = les["category"] == les["event_cause"]
    return RiskLessons(causes, cats, occ.sort_values(["prj_key", "risk_no"]).reset_index(drop=True), les.sort_values(["prj_key", "delay_seq", "category"]).reset_index(drop=True))


class ContingencyAdvice(NamedTuple):
    """Advice rows (measure, value, unit, note), the number of projects behind the schedule overrun, how many of them are legacy summary projects, the method text and the caveats. Advice only."""
    rows: pd.DataFrame
    n: int
    n_legacy: int
    method: str
    caveats: tuple[Any, ...]


@staged(sources=("projects.delay_event.cause_code", "projects.delay_event.days", "projects.estimate_line.cst_key", "projects.estimate_line.amount", "projects.estimate_version.type"), kb=_KB, facts=("policy.delivery.contingency_method",), oracle="py:tests/test_oracle_estimating.py::test_oracle_contingency_advice_net_of_the_allowance_line")
def contingency_advice(overrun_dist: pd.DataFrame, shares: pd.DataFrame, lines: pd.DataFrame, *, quantile: str = "q75", ground_causes: Sequence[str] = ("ground_conditions",),
                       view: str = "all_events", contingency_code: str = "CST-830", schedule_measure: str = "schedule", projects: Sequence[str] | None = None) -> ContingencyAdvice:
    """Use this when you need advice on the contingency percentage of a set of projects from the ground share of delay days and the schedule overrun, net of the contingency the tender estimates already carry.

    The method is the fact policy.delivery.contingency_method (the method text and its status come from the fact; the parameters below are PROPOSED): the share of delay days with a ground cause (`cause_shares`, view `all_events`, cause codes `ground_causes`) times a quantile of the schedule overrun (`overrun_distribution`, measure 'schedule', quantile q25, median or q75, PROPOSED q75), as a percentage of the contract, less the contingency the tender estimates already carry. Rows: ground_share (of delay days), schedule_overrun_<quantile> (percent), gross_percent (their product), existing_percent (median over the projects with a tender estimate of the tender line `contingency_code` over the tender total, from the `lines` of estimate_bridge with type tender; a project without the line counts as zero; 0 when no project has the line), net_percent (gross less existing, not below zero). The result states n and the number of legacy projects, and says: advice only, no percentage is hard coded, a legacy summary project has no estimate lines. Amounts of different currencies are never added: the existing share is a ratio per project. `projects` limits the lines to a set (a comparable set); without it every project of the lines frame counts.

    Args:
        overrun_dist: The output of overrun_distribution; it needs measure, n, n_legacy and the column of `quantile`, with exactly one row of `schedule_measure`.
        shares: The output of cause_shares; it needs view, cause_code and days.
        lines: The lines output of estimate_bridge; it needs prj_key, type, cst_key and amount.
        quantile: The column of the overrun distribution to use: q25, median or q75 (default q75, PROPOSED).
        ground_causes: The cause codes that count as ground causes (a tuple or list, not a text; default ground_conditions).
        view: The view of cause_shares to take the delay days from (default all_events).
        contingency_code: The cost code of the contingency line of the tender estimate (default CST-830).
        schedule_measure: The measure name of the schedule row in overrun_dist (default schedule).
        projects: Optional prj_key values (a list) that limit the lines to a set.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ContingencyAdvice (named tuple): rows (a DataFrame with measure, value, unit and note for ground_share, schedule_overrun_<quantile>, gross_percent, existing_percent and net_percent), n (projects behind the schedule overrun), n_legacy (how many of them are legacy summary projects), method (text, PROPOSED) and caveats (a tuple of texts; advice only).

    Raises:
        FrameError: quantile is not q25, median or q75; a frame is not a DataFrame or lacks a needed column; ground_causes is a text instead of a list; overrun_dist does not have exactly one row of schedule_measure; shares has no rows for the view; the delay days of the view are zero; the schedule overrun quantile is null; projects is a text instead of a list.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import contingency_advice
        >>> ctx = Context(stage="month12", role="analyst")
        >>> dist = pd.DataFrame({"measure": ["schedule"], "n": [4], "n_legacy": [1], "q75": [0.2]})
        >>> shares = pd.DataFrame({"view": ["all_events", "all_events"], "cause_code": ["ground_conditions", "weather"], "days": [30, 10]})
        >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "type": ["tender", "tender"], "cst_key": ["CST-830", "CST-100"], "amount": [5.0, 95.0]})
        >>> r = contingency_advice(dist, shares, lines, context=ctx)
        >>> r.rows.set_index("measure")["value"].to_dict()
        {'ground_share': 0.75, 'schedule_overrun_q75': 20.0, 'gross_percent': 15.0, 'existing_percent': 5.0, 'net_percent': 10.0}
        >>> (r.n, r.n_legacy)
        (4, 1)"""
    if quantile not in ("q25", "median", "q75"):
        raise FrameError("quantile is q25, median or q75")
    rule = fact("policy.delivery.contingency_method")
    _frame_need(overrun_dist, ["measure", "n", "n_legacy", quantile], "overrun_distribution")
    _frame_need(shares, ["view", "cause_code", "days"], "cause_shares")
    _frame_need(lines, ["prj_key", "type", "cst_key", "amount"], "estimate lines")
    if quantile not in ("q25", "median", "q75"):
        raise FrameError("quantile is q25, median or q75")
    if isinstance(ground_causes, (str, bytes)):
        raise FrameError("ground_causes must be a list of cause codes")
    sch = overrun_dist[overrun_dist["measure"] == schedule_measure]
    if len(sch) != 1:
        raise FrameError(f"overrun_distribution needs exactly one '{schedule_measure}' row")
    v = shares[shares["view"] == view]
    if v.empty:
        raise FrameError(f"cause_shares has no rows for the view {view}")
    total_days = float(v["days"].sum())
    if not total_days > 0:
        raise FrameError("the delay days of the view are zero")
    ground = float(v.loc[v["cause_code"].isin(list(ground_causes)), "days"].sum()) / total_days
    q = float(sch[quantile].iloc[0])
    if np.isnan(q):
        raise FrameError("the schedule overrun quantile is null")
    gross = ground * q * 100.0
    t = lines[lines["type"] == "tender"]
    if projects is not None:
        if isinstance(projects, (str, bytes)):
            raise FrameError("projects must be a list of prj_key values")
        t = t[t["prj_key"].isin(list(projects))]
    per = t.groupby("prj_key")["amount"].sum()
    ct = t[t["cst_key"] == contingency_code].groupby("prj_key")["amount"].sum().reindex(per.index).fillna(0.0)
    ratio = (ct / per.where(per > 0)).dropna()                                  # a project without the line counts as zero, not as missing
    n_with = int((ct > 0).sum())
    existing = float(ratio.median() * 100.0) if len(ratio) else 0.0
    net = max(gross - existing, 0.0)
    rows = pd.DataFrame([
        ("ground_share", round(ground, 4), "share of delay days", f"cause codes {list(ground_causes)}, view {view}"),
        (f"schedule_overrun_{quantile}", round(q * 100.0, 3), "percent of planned days", f"{int(sch['n'].iloc[0])} projects"),
        ("gross_percent", round(gross, 3), "percent", "ground share times the overrun quantile"),
        ("existing_percent", round(existing, 3), "percent", f"median over {len(ratio)} projects with a tender estimate of {contingency_code} over the tender total (zero where the line is missing); {n_with} carry the line"),
        ("net_percent", round(net, 3), "percent", "gross less existing, not below zero")], columns=["measure", "value", "unit", "note"])
    n, nl = int(sch["n"].iloc[0]), int(sch["n_legacy"].iloc[0])
    cav = [f"advice only: policy.delivery.contingency_method is {rule.status} and no percentage is decided here",
           f"{nl} of the {n} projects behind the overrun are legacy summary projects; they have no estimate lines, so the existing contingency rests on the {len(ratio)} projects with a tender estimate"]
    if n_with == 0:
        cav.append(f"no tender estimate carries a {contingency_code} line")
    return ContingencyAdvice(rows, n, nl, rule.value, tuple(cav))
