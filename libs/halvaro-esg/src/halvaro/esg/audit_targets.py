"""Energy audits and targets (plan 5.9): the audit schedule per site and the progress of a target along its glide path.

The audit cycle is a keyword marked VERIFY (config energy_audit.cycle_years 4, the legal duty and cycle are not stated in the data). The baseline of a target is compared with the lines, never changed.
"""
from __future__ import annotations

from typing import Any, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import _day, _need
from .ghg import scope_totals
from ._util import Provenance
from halvaro.core import make_envelope
from ._types import DateLike
import dataclasses


def _prov(value: Any, function: str, sources: Sequence[str], *warnings: str) -> Provenance:
    env = make_envelope(value, function, sources=sources, warnings=warnings, cls=Provenance)
    return cast(Provenance, dataclasses.replace(env, status="VERIFY+synthetic", synthetic=True))


_A = tuple(f"energy-esg.energy_audit.{c}" for c in ("site_key", "year", "audit_date", "due_date", "status"))
_NON_LINE_SCOPES = {"project_intensity"}


def _scope_mask(L: pd.DataFrame, sc: str) -> pd.Series:
    if sc == "1":
        return L["scope"] == 1
    if sc == "3":
        return L["scope"] == 3
    return (L["scope"] == 2) & (L["method"] == ("location" if sc == "2_location" else "market"))


_SCOPE_COL = {"1": "scope1", "2_location": "scope2_location", "2_market": "scope2_market", "3": "scope3"}


def _dates(col: pd.Series, name: str) -> pd.Series:
    nn = col.dropna()
    if len(nn) and (pd.api.types.is_numeric_dtype(col) or any(isinstance(v, (bool, int, float, np.number)) for v in nn)):
        raise FrameError(f"energy-esg.energy_audit.{name} holds numbers, not dates")
    try:
        out = pd.to_datetime(col)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"energy-esg.energy_audit.{name} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"energy-esg.energy_audit.{name} has a time zone")
    return out.dt.normalize()


@staged(sources=_A, oracle="py:tests/test_energy_esg.py::test_energy_audit_hannover_due")
def audit_schedule(A: pd.DataFrame, as_of: DateLike, *, cycle_years: int = 4, completed: str = "completed", ignored: tuple[str, ...] = ("cancelled",)) -> Provenance:
    """Use this when you need, per site, the last completed energy audit, the next due date and whether the site is overdue on a given day.

    Per site: the last completed audit on or before the day, the next due date, whether an audit is open and whether the site is overdue. The due date of a completed row is ignored. A site with no completed audit has a null last date and is overdue only through an open row. The cycle (4 years, VERIFY) is a keyword; the legal duty is not stated, so the result has the status VERIFY and `overdue` rests on the cycle. Statuses are compared without case and spaces. Rows with a status in `ignored` (cancelled) are left out; any other status than `completed` is an open audit and needs a due date.

    Args:
        A: The energy-esg.energy_audit table with the columns site_key, audit_date, due_date and status (year, when present, is not used).
        as_of: The day of the schedule (a date, a Timestamp or ISO text); audits after it do not count as done.
        cycle_years: The audit cycle in whole years, from 1 to 100 (default 4, VERIFY).
        completed: The status text of a completed audit (default "completed").
        ignored: The statuses that are left out (default ("cancelled",)); a tuple, not a single text.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns site_key, last_audit_date, open_audit (a row that is not completed), open_due_date, next_due (the open row's due date when there is one, else the last audit plus `cycle_years`), days_to_due (negative when past), overdue and cycle_years, one row per site sorted by site_key.

    Raises:
        FrameError: A lacks site_key, audit_date, due_date or status, or a row has no status or no site_key.
        FrameError: cycle_years is not a whole number from 1 to 100, `ignored` is a single text, or as_of is not a date without a time zone.
        FrameError: audit_date or due_date holds numbers, a value that is not a date, or a time zone.
        FrameError: a completed audit has no audit date, an open audit has no due date, or a site has more than one open audit.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import audit_schedule
        >>> ctx = Context(stage="month12", role="analyst")
        >>> A = pd.DataFrame({"site_key": ["SIT-900001", "SIT-900002"], "audit_date": ["2021-05-10", None],
        ...                   "due_date": [None, "2026-02-01"], "status": ["completed", "planned"]})
        >>> r = audit_schedule(A, "2026-03-01", context=ctx)
        >>> r.value["site_key"].tolist()
        ['SIT-900001', 'SIT-900002']
        >>> r.value["next_due"].dt.strftime("%Y-%m-%d").tolist()
        ['2025-05-10', '2026-02-01']
        >>> r.value["overdue"].tolist()
        [True, True]
    """
    _need(A, ["site_key", "audit_date", "due_date", "status"], "energy-esg.energy_audit")
    if isinstance(cycle_years, bool) or not isinstance(cycle_years, (int, np.integer)) or cycle_years < 1 or cycle_years > 100:
        raise FrameError("cycle_years must be a whole number of years, from 1 to 100")
    cycle_years = int(cycle_years)
    d = _day(as_of, "as_of")
    if isinstance(ignored, (str, bytes)):
        raise FrameError("ignored must be a tuple of statuses")
    if A["status"].isna().any() or A["site_key"].isna().any():
        raise FrameError("energy-esg.energy_audit has a row without a status or a site_key")
    norm = lambda v: str(v).strip().lower()                                                         # noqa: E731
    A = A.assign(status=A["status"].map(norm))
    completed, ignored_norm = norm(completed), [norm(v) for v in ignored]
    A = A[~A["status"].isin(ignored_norm)]
    x = A.assign(audit_date=_dates(A["audit_date"], "audit_date"), due_date=_dates(A["due_date"], "due_date"))
    if x.loc[x["status"] == completed, "audit_date"].isna().any():
        raise FrameError("a completed audit has no audit date")
    if x.loc[x["status"] != completed, "due_date"].isna().any():
        raise FrameError("an open audit has no due date")
    done = x[(x["status"] == completed) & (x["audit_date"] <= d)]
    last = done.groupby("site_key")["audit_date"].max()
    op = x[x["status"] != completed]
    if op.duplicated("site_key").any():
        raise FrameError("a site has more than one open audit")
    opd = op.set_index("site_key")["due_date"]
    sites = sorted(set(x["site_key"]))
    out = pd.DataFrame({"site_key": sites})
    out["last_audit_date"] = out["site_key"].map(last)
    out["open_audit"] = out["site_key"].isin(opd.index)
    out["open_due_date"] = out["site_key"].map(opd)
    cyc = out["last_audit_date"].map(lambda v: v + pd.DateOffset(years=cycle_years) if pd.notna(v) else pd.NaT)
    out["next_due"] = out["open_due_date"].where(out["open_audit"], cyc)
    out["days_to_due"] = (out["next_due"] - d).dt.days
    out["overdue"] = out["next_due"].notna() & (out["next_due"] < d)
    out["cycle_years"] = cycle_years
    return _prov(out, "halvaro.esg.audit_targets.audit_schedule", ("energy-esg.energy_audit",), "the audit cycle (4 years) and the legal duty are not established (VERIFY): overdue rests on the cycle keyword")


@staged(sources=("energy-esg.target.target_no", "energy-esg.target.scope", "energy-esg.target.baseline_year", "energy-esg.target.target_year", "energy-esg.target.baseline_value", "energy-esg.target.target_value",
                 *[f"energy-esg.emission_line.{c}" for c in ("le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period")]),
        oracle="py:tests/test_oracle_audit_targets.py::test_oracle_target_progress_every_route")
def target_progress(T: pd.DataFrame, L: pd.DataFrame, as_of: DateLike, *, year: int | None = None, tolerance: float = 0.005, basis: str = "current") -> Provenance:
    """Use this when you need each absolute emission target compared with its glide path and with the actual scope total of a year.

    Each absolute target against its glide path. `baseline_basis` is current, first_booked or neither: which line basis reproduces the stored baseline within `tolerance` of itself (0.5 percent PROPOSED). `actual` is the scope total of `year` (default the last full year before the day) on the current basis, `glide_value` the straight line from the stored baseline to the target value and `gap` the actual less the glide. A target whose scope is not a line scope (the per metre intensity target) is listed with null actual and glide only: it needs the per metre median, not the lines. The baseline is never changed. `basis_mismatch` is true when `baseline_basis` names a line basis other than the one of the actual; a baseline that matches both line bases is read as current, so the mismatch is then true only for the first_booked basis, and with neither match it is false. The current basis includes restatements booked after `as_of`, and the baseline year and the actual year may sit on different factor sets (T8): the result has the status VERIFY+synthetic and says so. `months` counts the periods with lines of the target's own scope and `on_track` is null when that is under 12, when the year is not over on the day, or when the scope has no lines. `actual_basis` names the line basis of the actual and `basis_mismatch` is true when the stored baseline matches the other basis.

    Args:
        T: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, baseline_value and target_value.
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        as_of: The day of the progress report (a date, a Timestamp or ISO text).
        year: The whole year of the actual; the year before the year of `as_of` when None.
        tolerance: The share of the stored baseline within which a basis reproduces it, zero or more (default 0.005, PROPOSED).
        basis: The line basis of the actual, "current" or "first_booked" (default "current").
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns target_no, scope, baseline_year, target_year, baseline_value, baseline_current, baseline_first_booked, baseline_basis, year, actual, glide_value, gap, on_track, months, actual_basis and basis_mismatch, one row per target sorted by target_no, values to three decimals.

    Raises:
        FrameError: T lacks target_no, scope, baseline_year, target_year, baseline_value or target_value, has no rows, has a repeated target_no, or has a null in a baseline or target value or year.
        FrameError: basis is not current or first_booked, year is not a whole year, tolerance is not a number of zero or more, or as_of is not a date without a time zone.
        FrameError: a target has a scope that is neither a line scope (1, 2_location, 2_market, 3) nor the intensity scope, or ends before its baseline year.
        FrameError: the line totals fail their checks (see scope_totals).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import target_progress
        >>> ctx = Context(stage="month12", role="analyst")
        >>> T = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2023], "target_year": [2027],
        ...                   "baseline_value": [1000.0], "target_value": [600.0]})
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2023-01", 1, "stationary_combustion", 1, None, None, 1000.0, False, None),
        ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 700.0, False, None)], columns=cols)
        >>> r = target_progress(T, L, "2026-03-01", context=ctx)
        >>> r.value[["target_no", "year", "baseline_basis", "actual", "glide_value", "gap", "months"]].to_dict("records")
        [{'target_no': 1, 'year': 2025, 'baseline_basis': 'current', 'actual': 700.0, 'glide_value': 800.0, 'gap': -100.0, 'months': 1}]
        >>> r.value["on_track"].isna().tolist()
        [True]
    """
    _need(T, ["target_no", "scope", "baseline_year", "target_year", "baseline_value", "target_value"], "energy-esg.target")
    if T["target_no"].duplicated().any():
        raise FrameError("energy-esg.target has more than one row for a target")
    d = _day(as_of, "as_of")
    if basis not in ("current", "first_booked"):
        raise FrameError("basis is current or first_booked")
    if T.empty:
        raise FrameError("energy-esg.target has no rows")
    if T[["baseline_value", "target_value", "baseline_year", "target_year"]].isna().any().any():
        raise FrameError("energy-esg.target has nulls in a baseline or target value or year")
    y = (d.year - 1) if year is None else year
    if isinstance(y, bool) or not isinstance(y, (int, np.integer)):
        raise FrameError("year must be a whole year")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float, np.number)) or not np.isfinite(tolerance) or tolerance < 0:
        raise FrameError("tolerance must be a number of zero or more")
    Lc = L[~L["is_superseded"].astype(bool)] if basis == "current" else L[L["restated_from_period"].isna()]
    ycut = int(y)
    late = pd.Timestamp(year=ycut, month=12, day=31) > d                                          # the year is not over on the day
    rows = []
    cache: dict[Any, Any] = {}

    def totals(yr: int, basis: str) -> Any:
        if (yr, basis) not in cache:
            tt = unwrapped(scope_totals)(L, yr, basis, "ALL")
            cache[(yr, basis)] = tt.value.iloc[0] if len(tt.value) else None
        return cache[(yr, basis)]

    r: Any
    for r in T.sort_values("target_no").itertuples():
        sc = str(int(r.scope)) if isinstance(r.scope, float) and float(r.scope).is_integer() else str(r.scope)
        col = _SCOPE_COL.get(sc)
        if col is None and sc not in _NON_LINE_SCOPES:
            raise FrameError(f"target {r.target_no} has the scope {sc!r}; known: {sorted(_SCOPE_COL) + sorted(_NON_LINE_SCOPES)}")
        row: dict[str, Any] = {"target_no": int(r.target_no), "scope": sc, "baseline_year": int(r.baseline_year), "target_year": int(r.target_year), "baseline_value": float(r.baseline_value)}
        span = int(r.target_year) - int(r.baseline_year)
        if span <= 0:
            raise FrameError(f"target {r.target_no} ends before its baseline year")
        frac = min(max((int(y) - int(r.baseline_year)) / span, 0.0), 1.0)
        row["year"] = int(y)
        row["glide_value"] = round(float(r.baseline_value) + (float(r.target_value) - float(r.baseline_value)) * frac, 3)
        if col is None:
            rows.append({**row, "baseline_current": np.nan, "baseline_first_booked": np.nan, "baseline_basis": "not a line scope", "actual": np.nan, "gap": np.nan, "on_track": None, "months": np.nan, "actual_basis": None, "basis_mismatch": False})
            continue
        bc, bf = totals(int(r.baseline_year), "current"), totals(int(r.baseline_year), "first_booked")
        vc = float(bc[col]) if bc is not None else np.nan
        vf = float(bf[col]) if bf is not None else np.nan
        tol = abs(float(r.baseline_value)) * tolerance
        bb = "current" if abs(vc - float(r.baseline_value)) <= tol else ("first_booked" if abs(vf - float(r.baseline_value)) <= tol else "neither")
        a = totals(int(y), basis)
        sel = Lc[(Lc["period"].astype(str).str[:4] == str(ycut)) & _scope_mask(Lc, sc)]
        s_months = int(sel["period"].nunique())
        if a is None or sel.empty:
            a = None
        actual = float(a[col]) if a is not None else np.nan
        rows.append({**row, "baseline_current": vc, "baseline_first_booked": vf, "baseline_basis": bb, "actual": actual, "gap": round(actual - row["glide_value"], 3) if a is not None else np.nan,
                     "on_track": bool(actual <= row["glide_value"]) if (a is not None and s_months >= 12 and not late and not np.isnan(actual)) else None, "months": s_months if a is not None else 0,
                     "actual_basis": basis, "basis_mismatch": bool(bb != basis and bb != "neither")})
    return _prov(pd.DataFrame(rows), "halvaro.esg.audit_targets.target_progress", ("energy-esg.target", "energy-esg.emission_line"),
                 f"actual on the {basis} basis; baseline year and actual year may sit on different factor sets; restatements after the day are included on the current basis")
