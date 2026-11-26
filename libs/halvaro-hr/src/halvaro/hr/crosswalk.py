"""XW-1: the username crosswalk. it-assets knows usernames only; a username is a person on a date (hr.username_history) or a pool account of a team (hr.shared_account)."""
from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple, Iterable, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import AmbiguousKey, FrameError, fact
from halvaro.core.registry import function

from ._guard import staged
from .org import PolicyDefault, _need

_INDEX_COLUMNS = ["username", "kind", "holder", "emp_key", "team_key", "valid_from", "valid_to"]
_KIND_OF_TYPE = {"named": "employee", "pool_account": "pool"}
_NEW_COLUMNS = ["resolution", "kind", "emp_key", "team_key", "kind_ok", "employed_on_start", "holds_to_end", "leave_date", "returned_after_leave_days", "open_after_leave", "late_return"]
_RETURN_DAYS = PolicyDefault("policy.offboarding.asset_return_days")      # proposed policy fact


class AmbiguousUsername(AmbiguousKey):
    """A username maps to more than one person or team on a date (must never happen in generated data)."""

    def __init__(self, username: str, on: Any, candidates: Iterable[Any]):
        self.username, self.on = username, on
        super().__init__(f"{username} on {pd.Timestamp(on).date()}", candidates)


class Resolution(NamedTuple):
    """Result of resolve_assignments: the assignment frame with the resolution columns, and the counts."""

    frame: pd.DataFrame
    diagnostics: dict[str, Any]


def _dates(frame: pd.DataFrame, columns: Sequence[str], what: str) -> pd.DataFrame:
    """The columns as naive calendar days; an unreadable value or a time zone is refused."""
    out = frame.copy()
    for c in columns:
        try:
            x = pd.to_datetime(out[c], format="mixed") if out[c].dtype == object else pd.to_datetime(out[c])
        except (ValueError, TypeError, OverflowError) as e:
            raise FrameError(f"{what}.{c} holds a value that is not a date: {e}") from None
        if getattr(x.dt, "tz", None) is not None:
            raise FrameError(f"{what}.{c} has a time zone; dates here are calendar days")
        out[c] = x.dt.normalize().astype("datetime64[ns]")
    return out


def _index(index: pd.DataFrame) -> pd.DataFrame:
    """The username index with its dates as Timestamps (a hand-built index with date objects is accepted)."""
    _need(index, _INDEX_COLUMNS, "username index")
    return _dates(index, ["valid_from", "valid_to"], "username index")


def _day(on: Any) -> pd.Timestamp:
    d: Any
    try:
        d = pd.Timestamp(on)
    except (ValueError, TypeError, OverflowError):
        d = pd.NaT
    if pd.isna(d) or isinstance(on, (bool, int, float, np.number)):
        raise FrameError(f"{on!r} is not a date; pass a date, a Timestamp or ISO text")
    if d.tzinfo is not None:
        raise FrameError(f"{on!r} has a time zone; dates here are calendar days")
    return cast("pd.Timestamp", d.normalize())


@function(sources=("hr.username_history.username", "hr.username_history.emp_key", "hr.username_history.valid_from", "hr.username_history.valid_to",
                   "hr.shared_account.account_name", "hr.shared_account.team_key", "hr.shared_account.valid_from", "hr.shared_account.valid_to"),
          oracle="py:halvaro_gen/world/it_assets/xw1.py::Resolver")
def build_username_index(username_history: pd.DataFrame, shared_account: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need one effective dated list of usernames and pool accounts with their holders.

    Rule: usernames of employees (kind employee) and pool accounts of teams (kind pool) are put in one frame; a null valid_to is open. The result is sorted by username and start date.

    Args:
        username_history: Frame hr.username_history with username, emp_key, valid_from and valid_to.
        shared_account: Frame hr.shared_account with account_name, team_key, valid_from and valid_to.

    Returns:
        pandas.DataFrame with username, kind, holder, emp_key, team_key, valid_from and valid_to.

    Raises:
        FrameError: a column is missing, a row has no username, holder or start date, or a row ends before it starts.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import build_username_index
        >>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> build_username_index(history, pool)[["username", "kind", "holder"]].to_dict("records")
        [{'username': 'ab', 'kind': 'employee', 'holder': 'EMP-000001'}, {'username': 'ops-pool', 'kind': 'pool', 'holder': 'TEAM-01'}]
    """
    _need(username_history, ["username", "emp_key", "valid_from", "valid_to"], "hr.username_history")
    _need(shared_account, ["account_name", "team_key", "valid_from", "valid_to"], "hr.shared_account")
    emp = username_history[["username", "emp_key", "valid_from", "valid_to"]].assign(kind="employee", team_key=None, holder=username_history["emp_key"])
    pool = (shared_account[["account_name", "team_key", "valid_from", "valid_to"]].rename(columns={"account_name": "username"})
            .assign(kind="pool", emp_key=None, holder=shared_account["team_key"]))
    out = _dates(pd.concat([emp.astype({"valid_to": object}), pool.astype({"valid_to": object})], ignore_index=True), ["valid_from", "valid_to"], "the username sources")
    for c in ("username", "holder", "valid_from"):
        if out[c].isna().any():
            raise FrameError(f"{int(out[c].isna().sum())} rows of the username sources have no {c}; every username needs a holder and a start date")
    rev = out["valid_to"].notna() & (out["valid_to"] < out["valid_from"])
    if rev.any():
        raise FrameError(f"{int(rev.sum())} username rows end before they start (for example {out.loc[rev, 'username'].iloc[0]})")
    return out[_INDEX_COLUMNS].sort_values(["username", "valid_from", "kind", "holder"], kind="stable").reset_index(drop=True)


def _hits(index: pd.DataFrame, username: str, on: pd.Timestamp) -> pd.DataFrame:
    rows = index[index["username"] == username]
    return rows[(rows["valid_from"] <= on) & (rows["valid_to"].isna() | (rows["valid_to"] >= on))]


@function(sources=("hr.username_history.username", "hr.shared_account.account_name"), oracle="py:halvaro_gen/world/it_assets/xw1.py::resolve_username")
def resolve_username(index: pd.DataFrame, username: str, on: dt.date) -> dict[str, Any] | None:
    """Use this when you have a username or a pool account name and a date and need to know who held it.

    Rule: the index is effective dated; the row valid on the date gives the holder. A username is never reused, so two holders on one date is an error.

    Args:
        index: The output of build_username_index.
        username: The username or pool account name.
        on: The date.

    Returns:
        dict | None: {'kind': 'employee' or 'pool', 'emp_key', 'team_key'} (the key that does not apply is None), or None when nobody held the name on that date.

    Raises:
        FrameError: the index lacks a column or a date is not a date.
        AmbiguousUsername: two holders on the date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import build_username_index, resolve_username
        >>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> index = build_username_index(history, pool)
        >>> resolve_username(index, "ab", dt.date(2026, 3, 1))
        {'kind': 'employee', 'emp_key': 'EMP-000001', 'team_key': None}
        >>> resolve_username(index, "ops-pool", dt.date(2026, 3, 1))["kind"], resolve_username(index, "nobody", dt.date(2026, 3, 1))
        ('pool', None)
    """
    index = _index(index)
    d = _day(on)
    hits = _hits(index, username, d)
    holders = hits[["kind", "holder"]].drop_duplicates()
    if len(holders) > 1:
        raise AmbiguousUsername(username, d, [f"{k} {h}" for k, h in holders.itertuples(index=False)])
    if hits.empty:
        return None
    r = hits.iloc[0]
    return {"kind": r["kind"], "emp_key": r["emp_key"] if r["kind"] == "employee" else None, "team_key": r["team_key"] if r["kind"] == "pool" else None}


@staged(sources=("it-assets.assignment.assigned_username", "it-assets.assignment.valid_from", "it-assets.assignment.valid_to", "it-assets.assignment.assignment_type",
                   "hr.employee.emp_key", "hr.employee.hire_date", "hr.employee.leave_date"),
          oracle="py:halvaro_gen/world/it_assets/xw1.py::xw1_truth", facts=("policy.offboarding.asset_return_days",))
def resolve_assignments(assignment: pd.DataFrame, index: pd.DataFrame, employee: pd.DataFrame, as_of: dt.date, asset_return_days: int | PolicyDefault = _RETURN_DAYS) -> Resolution:
    """Use this when you check who holds each asset assignment: the person or team behind each username at the start of the assignment, and whether they still hold it until the end.

    Rule: each assignment is resolved with the username index at its valid_from; unresolved and ambiguous rows are counted, not dropped. The kind follows assignment_type (named employee, pool_account pool, team no username but a pool_team_key). Further columns say whether the person was employed on the start day, held the username to the end or the leave date, and returned the asset after the leave date. asset_return_days defaults to the fact policy.offboarding.asset_return_days (status proposed); the diagnostics carry the value and its status.

    Args:
        assignment: Assignment frame (it-assets.assignment) with assignment_type, assigned_username, valid_from, valid_to and pool_team_key.
        index: The output of build_username_index.
        employee: Employee frame (hr.employee) with emp_key and leave_date.
        as_of: The date the open assignments are judged on.
        asset_return_days: Whole number of days an asset may be returned after the leave date. Default the fact.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        Resolution: .frame is the assignment frame with resolution, kind, emp_key, team_key, kind_ok, employed_on_start, leave_date, holds_to_end, returned_after_leave_days, open_after_leave and late_return; .diagnostics counts the cases.

    Raises:
        FrameError: asset_return_days is not a whole number, the assignment frame already has a column that is added, the employee frame has a person twice, assignment_type is unknown, or an assignment ends before it starts.
        StageRefusal: a context is given and its stage does not hold the it-assets and hr sources.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import build_username_index, resolve_assignments
        >>> assignment = pd.DataFrame({"assignment_type": ["named", "pool_account"], "assigned_username": ["ab", "ops-pool"], "valid_from": ["2025-01-01"] * 2, "valid_to": [None, None], "pool_team_key": [None, "TEAM-01"]})
        >>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
        >>> result = resolve_assignments(assignment, build_username_index(history, pool), employee, dt.date(2026, 3, 1))
        >>> result.frame["kind"].tolist(), result.diagnostics["resolved"], result.diagnostics["unresolved"]
        (['employee', 'pool'], 2, 0)
    """
    _need(assignment, ["assigned_username", "valid_from", "valid_to", "assignment_type", "pool_team_key"], "it-assets.assignment")
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    if isinstance(asset_return_days, PolicyDefault):
        f = fact(asset_return_days.fact_id)
        if isinstance(f.value, bool) or not isinstance(f.value, int):
            raise FrameError(f"{f.id} must be a whole number of days, it is {f.value!r}")
        asset_return_days, return_status = f.value, f.status
    else:
        return_status = "given"
    index = _index(index)
    clash = [c for c in _NEW_COLUMNS if c in assignment.columns]
    if clash:
        raise FrameError(f"the assignment frame already has column(s) {', '.join(clash)}; pass the source frame")
    if employee["emp_key"].duplicated().any():
        raise FrameError("hr.employee has duplicate emp_key values; one row per person is required")
    unknown = sorted(set(assignment["assignment_type"].dropna().unique()) - set(_KIND_OF_TYPE) - {"team"})
    if unknown or assignment["assignment_type"].isna().any():
        raise FrameError(f"unknown assignment_type {unknown or 'null'}; known: named, pool_account, team")
    now = _day(as_of)
    a = _dates(assignment, ["valid_from", "valid_to"], "it-assets.assignment")
    reversed_ = a["valid_to"].notna() & (a["valid_to"] < a["valid_from"])
    if reversed_.any():
        raise FrameError(f"{int(reversed_.sum())} assignments end before they start (for example row {a.index[reversed_][0]})")
    emp = _dates(employee[["emp_key", "hire_date", "leave_date"]], ["hire_date", "leave_date"], "hr.employee").set_index("emp_key")
    a["_row"] = np.arange(len(a))
    named = a.loc[a["assigned_username"].notna(), ["_row", "assigned_username", "valid_from"]]
    first, holders = _resolve_at(named, index, "valid_from")
    hit_count = holders.reindex(a["_row"]).fillna(0).astype(int).to_numpy()
    has_name = a["assigned_username"].notna().to_numpy()
    out = a.drop(columns="_row")
    out["resolution"] = np.where(~has_name, "no_username", np.where(hit_count == 0, "unresolved", np.where(hit_count > 1, "ambiguous", "resolved")))
    ok = out["resolution"] == "resolved"
    take = lambda col: first[col].reindex(a["_row"]).where(ok.to_numpy()).to_numpy()
    out["kind"], out["emp_key"], out["team_key"] = take("kind"), take("emp_key"), take("team_key")
    want = out["assignment_type"].map(_KIND_OF_TYPE)
    team_row = (out["resolution"] == "no_username") & (out["assignment_type"] == "team") & out["pool_team_key"].notna()
    out["kind_ok"] = np.where(ok, out["kind"] == want, team_row)
    hire, leave = out["emp_key"].map(emp["hire_date"]), out["emp_key"].map(emp["leave_date"])
    out["employed_on_start"] = (hire <= out["valid_from"]) & (leave.isna() | (leave >= out["valid_from"]))
    out["leave_date"] = leave
    # the same person holds the username to the end of the row, or to the leave date if earlier
    end = out["valid_to"].fillna(now)
    end = end.where(leave.isna() | (end <= leave), leave)
    probe = pd.DataFrame({"_row": a["_row"], "assigned_username": a["assigned_username"], "_end": end})[ok.to_numpy() & (out["kind"] == "employee").to_numpy()]
    again, again_n = _resolve_at(probe, index, "_end")
    same = again.reindex(probe["_row"])["holder"].to_numpy() == first.reindex(probe["_row"])["holder"].to_numpy()
    holds = pd.Series(True, index=out.index)
    holds.loc[out.index[probe["_row"].to_numpy()]] = same & (again_n.reindex(probe["_row"]).fillna(0).to_numpy() == 1)
    out["holds_to_end"] = holds.to_numpy()
    returned = (out["valid_to"] - leave).dt.days
    out["returned_after_leave_days"] = returned.where(out["valid_to"].notna() & leave.notna()).astype("float64")
    out["open_after_leave"] = out["valid_to"].isna() & leave.notna() & (leave < now)
    since = (now - leave).dt.days
    out["late_return"] = (out["returned_after_leave_days"] > asset_return_days) | (out["open_after_leave"] & (since > asset_return_days))
    people = out["kind"] == "employee"
    out.loc[~people, ["employed_on_start", "open_after_leave", "late_return"]] = False
    out["employed_on_start"] = out["employed_on_start"].astype(bool)
    diag = {"rows": len(out), "with_username": int(has_name.sum()), "no_username": int((~has_name).sum()), "resolved": int(ok.sum()),
            "unresolved": int((out["resolution"] == "unresolved").sum()), "ambiguous": int((out["resolution"] == "ambiguous").sum()),
            "kind_mismatch": int((~out["kind_ok"]).sum()), "not_employed_on_start": int((people & ~out["employed_on_start"]).sum()),
            "not_holding_to_end": int((people & ~out["holds_to_end"]).sum()),
            "returned_after_leave": int((out["returned_after_leave_days"] > 0).sum()), "open_after_leave": int(out["open_after_leave"].sum()),
            "late_return": int(out["late_return"].sum()), "asset_return_days": asset_return_days, "asset_return_days_status": return_status}
    return Resolution(out, diag)


def _resolve_at(rows: pd.DataFrame, index: pd.DataFrame, date_column: str) -> tuple[pd.DataFrame, pd.Series[Any]]:
    """Index rows holding each username on the date in `date_column`: the first hit per row and the number of distinct holders per row."""
    m = rows.merge(index.rename(columns={"valid_from": "_from", "valid_to": "_to"}), left_on="assigned_username", right_on="username", how="inner")
    m = m[(m["_from"] <= m[date_column]) & (m["_to"].isna() | (m["_to"] >= m[date_column]))]
    holders = (m["kind"] + "|" + m["holder"].astype(str)).groupby(m["_row"]).nunique()
    return m.drop_duplicates("_row").set_index("_row"), holders


@function(sources=("hr.username_history.emp_key", "hr.username_history.username", "hr.username_history.valid_from", "hr.username_history.valid_to"),
          oracle="py:halvaro_gen/world/it_assets/xw1.py::Resolver")
def overlapping_usernames(index: pd.DataFrame) -> list[str]:
    """Use this when you want to check that no username was held by two holders on overlapping dates.

    Rule: a username is never reused, so the list is expected to be empty.

    Args:
        index: The output of build_username_index.

    Returns:
        list: the usernames that map to different holders on overlapping dates, sorted; empty when the index is clean.

    Raises:
        FrameError: the index lacks a column or a date is not a date.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import build_username_index, overlapping_usernames
        >>> history = pd.DataFrame({"username": ["ab", "ab"], "emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2024-01-01", "2024-06-01"], "valid_to": [None, None]})
        >>> pool = pd.DataFrame(columns=["account_name", "team_key", "valid_from", "valid_to"])
        >>> overlapping_usernames(build_username_index(history, pool))
        ['ab']
    """
    index = _index(index)
    far = pd.Timestamp("2262-04-11")
    x = index.assign(_i=np.arange(len(index)), valid_to=index["valid_to"].fillna(far))
    m = x.merge(x, on="username", suffixes=("_a", "_b"))
    m = m[(m["_i_a"] < m["_i_b"]) & ((m["kind_a"] != m["kind_b"]) | (m["holder_a"] != m["holder_b"])) & (m["valid_from_a"] <= m["valid_to_b"]) & (m["valid_from_b"] <= m["valid_to_a"])]
    return sorted(set(m["username"]))
