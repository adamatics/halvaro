"""Availability and utilisation (the hr side of staffing): hours a person can work in a period, project hours over that availability, and the hours an allocation stint stands for.

PROPOSED values are keyword parameters with the plan's recommended default: world.staffing.hours_per_day (7.4 hours per full-time day) and policy.staffing.utilisation_basis (project hours over
availability net of leave and public holidays, population limited to the project roles passed in). The calendar comes from halvaro.core by the region of the site of the person's team."""
from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, PeriodError
from halvaro.core.calendar import is_working_day, region_of
from halvaro.core.registry import function

from ._guard import staged
from .org import _need

HOURS_PER_DAY = 7.4                                                                                  # PROPOSED, world.staffing.hours_per_day

_PERIOD_COLS = ["emp_key", "period_start", "period_end", "region", "working_days", "leave_days", "net_days", "hours"]


class _DateError(FrameError, PeriodError):
    """A date argument (as_of, a period end, before) that is not a calendar day: a FrameError for this module's contract and a PeriodError like the other halvaro.hr date arguments (halvaro.hr.certs)."""


_BOOL = (bool, np.bool_)
_NUMBER = (int, float, np.number) + _BOOL


def _ts(value: Any, name: str) -> pd.Timestamp:
    """A calendar day from a date, Timestamp or ISO text. A number (it would be read as nanoseconds since 1970), an unreadable text and a time zone raise."""
    if isinstance(value, _NUMBER):
        raise _DateError(f"{name} is a number, not a date: {value!r}")
    try:
        t = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _DateError(f"{name} is not a date: {value!r}") from exc
    if pd.isna(t):
        raise _DateError(f"{name} is not a date: {value!r}")
    if t.tzinfo is not None:
        raise _DateError(f"{name} is not a date without a time zone: {value!r}")
    return t.normalize()


def _numbers(series: pd.Series, what: str, lo: float, hi: float = np.inf) -> np.ndarray:
    """The column as floats. Strings, booleans, nulls, infinities and values outside lo to hi (both inclusive) raise FrameError."""
    bad = FrameError(f"{what} must be a number{'' if lo == -np.inf else f' from {lo:g}'}{'' if hi == np.inf else f' to {hi:g}'}, finite, without nulls, text or booleans")
    if pd.api.types.is_bool_dtype(series):
        raise bad
    if not pd.api.types.is_numeric_dtype(series):
        if not series.map(lambda x: isinstance(x, _NUMBER) and not isinstance(x, _BOOL)).all():
            raise bad
    try:
        v = series.to_numpy(dtype=float, na_value=np.nan)
    except (ValueError, TypeError):
        raise bad from None
    if not np.isfinite(v).all() or (v < lo).any() or (v > hi).any():
        raise bad
    return v


def _keys(frame: pd.DataFrame, what: str, *, null_ok: bool = False) -> None:
    """emp_key (or another key column) of one kind, text or numbers: a mix cannot be sorted or compared. Nulls raise unless null_ok."""
    col = frame["emp_key"]
    if not null_ok and col.isna().any():
        raise FrameError(f"{what}.emp_key has nulls")
    kinds = col.dropna().map(lambda x: "text" if isinstance(x, str) else "number" if isinstance(x, _NUMBER) else type(x).__name__)
    if kinds.nunique() > 1:
        raise FrameError(f"{what}.emp_key mixes {sorted(kinds.unique())}: one kind of key per column")


def _hpd(hours_per_day: Any) -> float:
    if isinstance(hours_per_day, bool) or not isinstance(hours_per_day, (int, float, np.integer, np.floating)) or not 0 < hours_per_day <= 24:
        raise FrameError(f"hours_per_day is a number of hours above zero and at most 24, not {hours_per_day!r}")
    return float(hours_per_day)


def _periods(periods: Any) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out = []
    for p in periods:
        if not isinstance(p, (tuple, list)) or len(p) != 2:
            raise FrameError(f"a period is a (start, end) pair, not {p!r}")
        a, b = _ts(p[0], "period start"), _ts(p[1], "period end")
        if b < a:
            raise FrameError(f"the period {a.date()} to {b.date()} ends before it starts")
        out.append((a, b))
    return out


_MAX_DAYS = 40000                                                                                    # about 110 years: the day arrays are persons times days


def _holds_numbers(col: pd.Series) -> bool:
    if pd.api.types.is_bool_dtype(col) or pd.api.types.is_numeric_dtype(col):
        return bool(col.notna().any())
    return bool(col.dtype == object and col.map(lambda x: isinstance(x, _NUMBER) and not pd.isna(cast(Any, x))).any())


def _dates(frame: pd.DataFrame, column: str, what: str, *, null_ok: bool) -> pd.Series:
    """The column as calendar days (time of day removed). Nulls raise unless null_ok; numbers (read as nanoseconds since 1970 by pandas), text that is not a date and time zones raise FrameError."""
    col = frame[column]
    if _holds_numbers(col):
        raise FrameError(f"{what}.{column} holds numbers, not dates")
    try:
        out = pd.to_datetime(col)
    except (ValueError, TypeError, OverflowError) as exc:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {exc}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    if not null_ok and out.isna().any():
        raise FrameError(f"{what}.{column} has nulls")
    return out.dt.normalize()


class _Daily(NamedTuple):
    first: pd.Timestamp
    emp: list[str]
    work: np.ndarray        # employed, regional working day (leave not removed): E x N bool
    net: np.ndarray         # employed, working day, no leave: E x N bool
    fte: np.ndarray         # E x N float, zero where no term
    gap: np.ndarray         # employed but no term row valid that day: E x N bool
    region: np.ndarray      # E x N int8 index into `names`, -1 where no term
    names: list[str]


def _no_overlap(terms: pd.DataFrame) -> None:
    """No two terms of one person share a day, checked over the whole table (not only the days asked for). valid_to null is open ended."""
    t = terms.sort_values(["emp_key", "valid_from"], kind="stable")
    end = t["valid_to"].fillna(pd.Timestamp("2262-04-01"))
    prev = end.groupby(t["emp_key"]).shift()                                                  # sorted by start, ends rise unless a pair overlaps, so the previous row is enough
    bad = prev.notna() & (t["valid_from"] <= prev)
    if bad.any():
        raise FrameError(f"hr.employment_term of {t.loc[bad, 'emp_key'].iloc[0]} overlaps")


def _daily(employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, first: pd.Timestamp, last: pd.Timestamp, leave_types: Any) -> _Daily:
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _need(employment_term, ["emp_key", "valid_from", "valid_to", "team_key", "fte"], "hr.employment_term")
    _need(leave_record, ["emp_key", "start", "end"] + (["leave_type"] if leave_types is not None else []), "hr.leave_record")
    _need(team, ["team_key", "site_key"], "hr.team")
    _keys(employee, "hr.employee")
    _keys(employment_term, "hr.employment_term")
    _keys(leave_record, "hr.leave_record")
    if employee["emp_key"].duplicated().any():
        raise FrameError("hr.employee has more than one row for an emp_key")
    if team["team_key"].duplicated().any():
        raise FrameError("hr.team has more than one row for a team_key")
    n = (last - first).days + 1
    if n > _MAX_DAYS:
        raise FrameError(f"the span from {first.date()} to {last.date()} is {n} days; at most {_MAX_DAYS} are supported")
    days = pd.date_range(first, last)
    site = team.set_index("team_key")["site_key"]
    terms = employment_term.assign(valid_from=_dates(employment_term, "valid_from", "hr.employment_term", null_ok=False), valid_to=_dates(employment_term, "valid_to", "hr.employment_term", null_ok=True))
    terms["fte"] = _numbers(terms["fte"], "hr.employment_term fte", 0.0, 1.0)
    if (terms["valid_to"] < terms["valid_from"]).any():
        raise FrameError("hr.employment_term has a term that ends before it starts")
    _no_overlap(terms)
    unknown = sorted(set(terms["team_key"]) - set(site.index))
    if unknown:
        raise FrameError(f"hr.employment_term has teams that hr.team does not have: {unknown[:3]}")
    sites = sorted(set(site.loc[terms["team_key"].unique()]))
    names = sorted({region_of(x) for x in sites})
    rix = {x: names.index(region_of(x)) for x in sites}
    wd = np.stack([np.array([is_working_day(d.date(), r) for d in days]) for r in names]) if names else np.zeros((0, n), bool)
    lv = leave_record if leave_types is None else leave_record[leave_record["leave_type"].isin(list(leave_types))]
    lv = lv.assign(start=_dates(lv, "start", "hr.leave_record", null_ok=False), end=_dates(lv, "end", "hr.leave_record", null_ok=True))
    if (lv["end"] < lv["start"]).any():
        raise FrameError("hr.leave_record has a leave that ends before it starts")
    lv["end"] = lv["end"].fillna(last)                                                               # a leave with no end is open (as org.status_on reads it): it lasts to the end of the window
    hire_all = _dates(employee, "hire_date", "hr.employee", null_ok=False)
    left_all = _dates(employee, "leave_date", "hr.employee", null_ok=True)
    off = lambda t: int((t - first).days)
    spans = {k: g for k, g in lv.groupby("emp_key")}
    tspans = {k: g for k, g in terms.groupby("emp_key")}
    order = employee.assign(hire0=hire_all, left0=left_all).sort_values("emp_key")
    keys = order["emp_key"].tolist()
    E = len(keys)
    work, net, fte, gap = np.zeros((E, n), bool), np.zeros((E, n), bool), np.zeros((E, n)), np.zeros((E, n), bool)
    region = np.full((E, n), -1, dtype=np.int8)
    for i, r in enumerate(order.itertuples(index=False)):
        key = r.emp_key
        employed = np.zeros(n, bool)
        employed[max(off(r.hire0), 0):] = True
        if pd.notna(r.left0):
            employed[max(off(r.left0) + 1, 0):] = False
        cover = np.zeros(n, bool)
        for t in (tspans[key].itertuples(index=False) if key in tspans else []):
            a = max(off(t.valid_from), 0)
            z = n if pd.isna(t.valid_to) else min(off(t.valid_to) + 1, n)
            if z <= a:
                continue
            cover[a:z] = True
            fte[i, a:z] = t.fte
            region[i, a:z] = rix[site[t.team_key]]
        for ri in range(len(names)):
            work[i] |= (region[i] == ri) & wd[ri]
        work[i] &= employed
        m = np.zeros(n, bool)
        for s_, e_ in (zip(spans[key]["start"], spans[key]["end"]) if key in spans else []):
            lo, hi = max(off(s_), 0), min(off(e_) + 1, n)
            if hi > lo:
                m[lo:hi] = True
        net[i] = work[i] & ~m
        fte[i, ~employed] = 0.0
        gap[i] = employed & ~cover
    return _Daily(first, keys, work, net, fte, gap, region, names)


@function(sources=("hr.employee.hire_date", "hr.employee.leave_date", "hr.employment_term.fte", "hr.employment_term.team_key", "hr.employment_term.valid_from", "hr.employment_term.valid_to",
                   "hr.leave_record.start", "hr.leave_record.end", "hr.leave_record.leave_type", "hr.team.site_key"), oracle="py:tests/test_staffing.py::test_utilisation")
def availability_hours(employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, periods: Sequence[tuple[dt.date | str, dt.date | str]], *,
                       hours_per_day: float = HOURS_PER_DAY, leave_types: Sequence[str] | None = None) -> pd.DataFrame:
    """Use this when you need the hours each person can work in each period: employed working days of the region, less leave, times the fte, times the hours of a day.

    Rule: per period (a pair of dates, both included) the days on which the person is employed and which are working days of the region of the team's site; leave days are taken off; the rest times the fte of the term valid that day and times hours_per_day (PROPOSED default, world.staffing.hours_per_day). A person with no term on a day gives no hours there.

    Args:
        employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
        employment_term: Employment term frame (hr.employment_term) with emp_key, valid_from, valid_to, team_key and fte.
        leave_record: Leave frame (hr.leave_record) with emp_key, start, end and leave_type; an empty end is open.
        team: Team frame (hr.team) with team_key and site_key.
        periods: A list of (start, end) date pairs, both days included.
        hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
        leave_types: The leave types that count as leave; None means all.

    Returns:
        pandas.DataFrame with emp_key, period_start, period_end, region, working_days, leave_days, net_days and hours, sorted by person and period; a person with no employed working day in a period has no row.

    Raises:
        FrameError: a frame lacks a column, a date is not a date, hours_per_day is not above zero and at most 24, or a period is not a pair of dates.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import availability_hours
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
        >>> week = [(dt.date(2026, 3, 2), dt.date(2026, 3, 6))]
        >>> availability_hours(employee, term, leave, team, week)[["working_days", "leave_days", "net_days", "hours"]].to_dict("records")
        [{'working_days': 5, 'leave_days': 1, 'net_days': 4, 'hours': 29.6}]
    """
    h = _hpd(hours_per_day)
    ps = _periods(periods)
    if not ps:
        return pd.DataFrame(columns=_PERIOD_COLS)
    first, last = min(p[0] for p in ps), max(p[1] for p in ps)
    if len(set(ps)) != len(ps):
        raise FrameError("periods has the same period twice")
    d = _daily(employee, employment_term, leave_record, team, first, last, leave_types)
    rows = []
    for i, k in enumerate(d.emp):
        for a, b in ps:
            ia, ib = (a - d.first).days, (b - d.first).days + 1
            wk = int(d.work[i, ia:ib].sum())
            if wk == 0:
                continue
            nt = d.net[i, ia:ib]
            reg = d.region[i, ia:ib][d.work[i, ia:ib]][0]
            rows.append((k, a, b, d.names[reg], wk, wk - int(nt.sum()), int(nt.sum()), round(float((nt * d.fte[i, ia:ib]).sum() * h), 9)))
    out = pd.DataFrame(rows, columns=_PERIOD_COLS)
    return out.sort_values(["emp_key", "period_start", "period_end"]).reset_index(drop=True)


@staged(sources=("projects.time_entry.emp_key", "projects.time_entry.work_date", "projects.time_entry.hours", "hr.employment_term.team_key", "hr.employment_term.role_key", "hr.team.dep_key",
                   "hr.department.dep_code"), oracle="py:tests/test_staffing.py::test_utilisation")
def utilisation(time_entry: pd.DataFrame, availability: pd.DataFrame, employment_term: pd.DataFrame, team: pd.DataFrame, department: pd.DataFrame, *, project_roles: Sequence[str],
                before: dt.date | str | pd.Timestamp | None = None) -> pd.DataFrame:
    """Use this when you need project hours over availability by team and by department, for the people who hold a project role.

    Rule: the basis is proposed (policy.staffing.utilisation_basis): project hours over availability net of leave and public holidays, limited to the project roles. Per person and period of an availability_hours frame, the team and role are those of the employment term valid at the middle of the period (start plus half the span, the time of day dropped). The person counts when the role key is in project_roles. Project hours are the time entries of the person with work_date inside the period, both ends included; negative hours are corrections and are summed. With before only periods that start before that date count. Hours of persons or periods outside the availability frame are not counted.

    Args:
        time_entry: Time entry frame (projects.time_entry) with emp_key, work_date and hours.
        availability: The output of availability_hours: emp_key, period_start, period_end and hours (availability).
        employment_term: Employment term frame (hr.employment_term) with emp_key, valid_from, valid_to, team_key and role_key.
        team: Team frame (hr.team) with team_key and dep_key.
        department: Department frame (hr.department) with dep_key and dep_code.
        project_roles: The role keys that count as project roles.
        before: Optional date; only periods that start before it count.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: level (team or department), key (team_key or dep_code), availability_hours, project_hours, utilisation (empty when availability is zero) and n_persons.

    Raises:
        FrameError: a frame lacks a column, project_roles is empty, a team or department key is duplicated, availability has a reversed, duplicate or overlapping period, two terms are valid at the middle of a period, or a team or department is missing.
        StageRefusal: a context is given and its stage does not hold the projects source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import utilisation
        >>> entries = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "work_date": ["2026-03-02", "2026-03-03"], "hours": [7.5, 6.0]})
        >>> availability = pd.DataFrame({"emp_key": ["EMP-000001"], "period_start": ["2026-03-01"], "period_end": ["2026-03-31"], "hours": [150.0]})
        >>> terms = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2025-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"]})
        >>> teams = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"]})
        >>> departments = pd.DataFrame({"dep_key": ["DEP-1"], "dep_code": ["ENG"]})
        >>> result = utilisation(entries, availability, terms, teams, departments, project_roles=["ROLE-1"])
        >>> result[["level", "key", "project_hours", "n_persons"]].to_dict("records")
        [{'level': 'team', 'key': 'TEAM-01', 'project_hours': 13.5, 'n_persons': 1}, {'level': 'department', 'key': 'ENG', 'project_hours': 13.5, 'n_persons': 1}]
    """
    _need(time_entry, ["emp_key", "work_date", "hours"], "projects.time_entry")
    _need(availability, ["emp_key", "period_start", "period_end", "hours"], "availability_hours output")
    _need(employment_term, ["emp_key", "valid_from", "valid_to", "team_key", "role_key"], "hr.employment_term")
    _need(team, ["team_key", "dep_key"], "hr.team")
    _need(department, ["dep_key", "dep_code"], "hr.department")
    roles = {project_roles} if isinstance(project_roles, str) else set(project_roles)
    if not roles:
        raise FrameError("project_roles is empty: the utilisation population would be nobody")
    for frame, key, what in ((team, "team_key", "hr.team"), (department, "dep_key", "hr.department")):
        if frame[key].duplicated().any():
            raise FrameError(f"{what} has more than one row for a {key}")
    _keys(availability, "availability")
    _keys(time_entry, "projects.time_entry")
    _keys(employment_term, "hr.employment_term")
    av = availability.copy()
    av["period_start"], av["period_end"] = _dates(av, "period_start", "availability", null_ok=False), _dates(av, "period_end", "availability", null_ok=False)
    av["hours"] = _numbers(av["hours"], "availability hours", 0.0)
    if (av["period_end"] < av["period_start"]).any():
        raise FrameError("availability has a period that ends before it starts")
    if av.duplicated(["emp_key", "period_start", "period_end"]).any():
        raise FrameError("availability has more than one row for a person and period")
    av = av.sort_values(["emp_key", "period_start", "period_end"], kind="stable")
    prev_end = av["period_end"].groupby(av["emp_key"]).shift()
    if (prev_end.notna() & (av["period_start"] <= prev_end)).any():
        raise FrameError("availability has overlapping periods for a person: their hours would be counted twice")
    if before is not None:
        av = av[av["period_start"] < _ts(before, "before")]
    av["mid"] = (av["period_start"] + (av["period_end"] - av["period_start"]) / 2).dt.normalize()
    terms = employment_term.assign(valid_from=_dates(employment_term, "valid_from", "hr.employment_term", null_ok=False), valid_to=_dates(employment_term, "valid_to", "hr.employment_term", null_ok=True))
    m = av.merge(terms[["emp_key", "valid_from", "valid_to", "team_key", "role_key"]], on="emp_key", how="left")
    m = m[(m["valid_from"] <= m["mid"]) & (m["valid_to"].isna() | (m["valid_to"] >= m["mid"]))]
    if m.duplicated(["emp_key", "period_start", "period_end"]).any():
        raise FrameError("hr.employment_term has two terms valid at the middle of a period")
    m = m[m["role_key"].isin(roles)]
    te = time_entry.assign(work_date=_dates(time_entry, "work_date", "projects.time_entry", null_ok=False))
    te["hours"] = _numbers(te["hours"], "projects.time_entry.hours", -np.inf)                                    # negative hours are corrections, kept as in staffing.planned_vs_actual_hours
    m = m.reset_index(drop=True)
    try:
        codes = {k: i for i, k in enumerate(sorted(set(te["emp_key"]) | set(m["emp_key"])))}
    except TypeError:
        raise FrameError("projects.time_entry.emp_key and the availability emp_key are not of one kind (text and numbers)") from None
    day0 = pd.Timestamp("1970-01-01")
    scale = 1 << 20                                                                                  # days per person slot, far above any span
    tk = te["emp_key"].map(codes).to_numpy(np.int64) * scale + ((te["work_date"] - day0).dt.days.to_numpy(np.int64) + (1 << 19))
    order = np.argsort(tk, kind="stable")
    keys, cum = tk[order], np.concatenate([[0.0], np.cumsum(te["hours"].to_numpy(float)[order])])
    mc = m["emp_key"].map(codes).to_numpy(np.int64) * scale
    lo = np.searchsorted(keys, mc + (m["period_start"] - day0).dt.days.to_numpy(np.int64) + (1 << 19), side="left")
    hi = np.searchsorted(keys, mc + (m["period_end"] - day0).dt.days.to_numpy(np.int64) + (1 << 19), side="right")
    hrs = cum[hi] - cum[lo]
    m = m.assign(project_hours=hrs, availability_hours=m["hours"])
    dep = team.merge(department[["dep_key", "dep_code"]], on="dep_key", how="left").set_index("team_key")["dep_code"]
    unknown = sorted(set(m["team_key"]) - set(dep.index))
    if unknown:
        raise FrameError(f"hr.employment_term has teams that hr.team does not have: {unknown[:3]}")
    if dep.loc[sorted(set(m["team_key"]))].isna().any():
        raise FrameError("hr.team has a team whose department hr.department does not have")
    m["dep_code"] = m["team_key"].map(dep)
    def agg(col: str, level: str) -> pd.DataFrame:
        g = m.groupby(col).agg(availability_hours=("availability_hours", "sum"), project_hours=("project_hours", "sum"), n_persons=("emp_key", "nunique")).reset_index()
        g.insert(0, "level", level)
        return g.rename(columns={col: "key"})
    out = pd.concat([agg("team_key", "team"), agg("dep_code", "department")], ignore_index=True)
    out["utilisation"] = np.where(out["availability_hours"] > 0, out["project_hours"] / out["availability_hours"].where(out["availability_hours"] > 0), np.nan)
    out = out[["level", "key", "availability_hours", "project_hours", "utilisation", "n_persons"]].sort_values(["level", "key"], ascending=[False, True]).reset_index(drop=True)
    return out


@function(sources=("hr.allocation.emp_key", "hr.allocation.prj_key", "hr.allocation.start", "hr.allocation.end", "hr.allocation.percent", "hr.employee.hire_date", "hr.employee.leave_date",
                   "hr.employment_term.fte", "hr.leave_record.start", "hr.leave_record.end"), oracle="py:tests/test_staffing.py::test_allocation_capacity")
def allocation_hours(allocation: pd.DataFrame, employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, as_of: dt.date | str | pd.Timestamp, *,
                     hours_per_day: float = HOURS_PER_DAY, leave_types: Sequence[str] | None = None) -> pd.DataFrame:
    """Use this when you need the hours that each allocation stint stands for, split into the hours up to a date and the hours after it.

    Rule: the percent of the stint divided by 100 times the availability hours of the person inside the stint (the rules of availability_hours). hours_before counts stint days up to and including the date, hours_after the days after it; after_now says that the stint has days after the date.

    Args:
        allocation: Allocation frame (hr.allocation) with emp_key, prj_key, start, end and percent; start and end must be dates.
        employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
        employment_term: Employment term frame (hr.employment_term).
        leave_record: Leave frame (hr.leave_record).
        team: Team frame (hr.team) with team_key and site_key.
        as_of: The date that splits realised from planned hours.
        hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
        leave_types: The leave types that count as leave; None means all.

    Returns:
        pandas.DataFrame: the columns of the allocation frame plus availability_hours, hours, hours_before, hours_after, no_term_days and after_now.

    Raises:
        FrameError: a frame lacks a column, a stint has no start or end, a person of the allocations is not in hr.employee, or hours_per_day is not above zero and at most 24.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import allocation_hours
        >>> allocation = pd.DataFrame({"emp_key": ["EMP-000001"], "prj_key": ["PRJ-1"], "start": ["2026-03-02"], "end": ["2026-03-06"], "percent": [50]})
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
        >>> result = allocation_hours(allocation, employee, term, leave, team, dt.date(2026, 3, 4))
        >>> result[["availability_hours", "hours", "hours_before", "hours_after", "after_now"]].to_dict("records")
        [{'availability_hours': 29.6, 'hours': 14.8, 'hours_before': 7.4, 'hours_after': 7.4, 'after_now': True}]
    """
    _need(allocation, ["emp_key", "start", "end", "percent"], "hr.allocation")
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _keys(allocation, "hr.allocation")
    _keys(employee, "hr.employee")
    h = _hpd(hours_per_day)
    day = _ts(as_of, "as_of")
    al = allocation.copy()
    al["s0"], al["end0"] = _dates(al, "start", "hr.allocation", null_ok=True), _dates(al, "end", "hr.allocation", null_ok=True)
    if al["s0"].isna().any() or al["end0"].isna().any():
        raise FrameError("hr.allocation start and end must be dates: an open allocation needs an end before its hours can be counted")
    if (al["end0"] < al["s0"]).any():
        raise FrameError("hr.allocation has a stint that ends before it starts")
    al["percent"] = _numbers(al["percent"], "hr.allocation percent", 0.0, 100.0)
    missing = sorted(set(al["emp_key"]) - set(employee["emp_key"]))
    if missing:
        raise FrameError(f"hr.allocation has persons that hr.employee does not have: {missing[:3]}")
    if al.empty:
        return allocation.assign(availability_hours=pd.Series(dtype=float), hours=pd.Series(dtype=float), hours_before=pd.Series(dtype=float), hours_after=pd.Series(dtype=float),
                                 no_term_days=pd.Series(dtype=int), after_now=pd.Series(dtype=bool))
    d = _daily(employee[employee["emp_key"].isin(set(al["emp_key"]))], employment_term, leave_record, team, al["s0"].min(), al["end0"].max(), leave_types)
    idx = {k: i for i, k in enumerate(d.emp)}
    hours_day = d.net * d.fte * h
    cum = np.concatenate([np.zeros((len(d.emp), 1)), np.cumsum(hours_day, axis=1)], axis=1)
    def span(i: Any, a: Any, b: Any) -> float:
        ia, ib = (a - d.first).days, (b - d.first).days + 1
        return float(cum[i, ib] - cum[i, ia]) if ib > ia else 0.0
    tot, before, after, nogap = [], [], [], []
    r: Any
    for r in al.itertuples():
        i = idx[r.emp_key]
        cut = min(max(day, r.s0 - pd.DateOffset(days=1)), r.end0)
        tot.append(span(i, r.s0, r.end0))
        nogap.append(int(d.gap[i, (r.s0 - d.first).days:(r.end0 - d.first).days + 1].sum()))
        before.append(span(i, r.s0, cut))
        after.append(span(i, cut + pd.DateOffset(days=1), r.end0))
    out = allocation.copy()
    p = al["percent"].to_numpy(float) / 100.0
    out["availability_hours"] = np.round(tot, 9)
    out["hours"] = np.round(np.array(tot) * p, 9)
    out["hours_before"] = np.round(np.array(before) * p, 9)
    out["hours_after"] = np.round(np.array(after) * p, 9)
    out["no_term_days"] = nogap
    out["after_now"] = (al["end0"] > day).to_numpy()
    return out
