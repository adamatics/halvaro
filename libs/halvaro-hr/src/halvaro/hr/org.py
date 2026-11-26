"""Organisation on a date: the one term per person, the person frame, headcount and the release date."""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import PeriodError, FrameError, check_contiguity, fact, release_now, rows_on, snapshot_hash, team_context  # noqa: F401
from halvaro.core import snapshot, violations
from halvaro.core.registry import function

_LEVELS = {"department": "dep_key", "team": "team_key", "entity": "legal_entity_key"}


class PolicyDefault:
    """Default of a parameter that is a policy fact: the value is read with fact() at call time. None and any other value given by the caller keep their old meaning."""

    def __init__(self, fact_id: str):
        self.fact_id = fact_id

    def __repr__(self) -> str:
        return f"policy:{self.fact_id}"


def policy_number(value: Any, used: dict[str, Any], *, integer: bool = False) -> Any:
    """The number of a parameter whose default is a policy fact: the fact value (its status goes into `used`), or the value the caller gave unchanged."""
    if isinstance(value, PolicyDefault):
        f = fact(value.fact_id)
        v = f.value
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and not float(v).is_integer()):
            raise FrameError(f"{value.fact_id} must be {'a whole number' if integer else 'a number'}, it is {v!r}")
        used[value.fact_id] = f.status
        return int(v) if integer else v
    return value


UNAVAILABLE_LEAVE_TYPES = PolicyDefault("policy.staffing.unavailable_leave_types")      # proposed policy fact, comma separated


def unavailable_types(given: "Sequence[str] | str | PolicyDefault") -> list[str]:
    """The leave types that make someone unavailable: the argument, or the fact policy.staffing.unavailable_leave_types when it is the default."""
    if isinstance(given, PolicyDefault):
        types = [t.strip() for t in str(fact(given.fact_id).value).split(",") if t.strip()]
        if not types:
            raise FrameError(f"{given.fact_id} lists no leave type")
        return types
    return [given] if isinstance(given, str) else list(given)


def leave_types_given(given: Any, name: str) -> None:
    """Refuse a leave type argument that is neither a leave type name, a list of them nor the policy default (None, a number)."""
    if not isinstance(given, (str, PolicyDefault, Iterable)):
        raise FrameError(f"{name} must be a leave type name or a list of leave type names, not {given!r}")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}")


def _unique(employee: pd.DataFrame, what: str) -> None:
    dup = employee["emp_key"][employee["emp_key"].duplicated()]
    if len(dup):
        raise FrameError(f"{what} has {len(dup)} duplicate emp_key values (for example {dup.iloc[0]}); one row per person is required")


def _active(employee: pd.DataFrame, as_of: dt.date) -> pd.Series:
    """Employed on the date: hired on or before it and not left. `leave_date` is the last day employed (the last term ends on it)."""
    d = pd.Timestamp(as_of)
    hire, leave = pd.to_datetime(employee["hire_date"]), pd.to_datetime(employee["leave_date"])
    return (hire <= d) & (leave.isna() | (leave >= d))


def _require_terms(employee: pd.DataFrame, terms: pd.DataFrame, as_of: dt.date) -> None:
    """Every person employed on the date needs a term on it; the first terms start on the window start, so earlier dates fail loudly."""
    missing = employee.loc[_active(employee, as_of).values & ~cast("np.ndarray[Any, Any]", employee["emp_key"].isin(terms["emp_key"]).values), "emp_key"]
    if len(missing):
        raise FrameError(f"{len(missing)} people employed on {as_of} have no employment term on that date (for example {missing.iloc[0]}); "
                         f"terms start on the window start 2023-01-01, check hr.employment_term")


@function(sources=("hr.employment_term.emp_key", "hr.employment_term.valid_from", "hr.employment_term.valid_to"),
          oracle="py:halvaro_gen/truth/hr.py::terms_on")
def terms_on(term: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the one employment term that is valid on a date for each person, without the restricted pay column.

    Rule: a term is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. The org layer never returns a restricted column, so the pay column is dropped from the result.

    Args:
        term: The employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
        as_of: The date.

    Returns:
        pandas.DataFrame: one row per person with a term valid on the date, the columns of the frame except the restricted ones.

    Raises:
        FrameError: the frame lacks emp_key, valid_from or valid_to.
        AmbiguousKey: one person has two terms valid on the date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import terms_on
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2025-01-01", "2026-01-01"],
        ...                      "valid_to": ["2025-12-31", None], "team_key": ["TEAM-01", "TEAM-02"]})
        >>> terms_on(term, dt.date(2026, 6, 1))[["emp_key", "team_key"]].to_dict("records")
        [{'emp_key': 'EMP-000001', 'team_key': 'TEAM-02'}]
    """
    _need(term, ["emp_key", "valid_from", "valid_to"], "hr.employment_term")
    out = rows_on(term, as_of, key="emp_key")
    restricted = {c.split(".")[-1] for c in snapshot.load()["restricted_columns"]}      # the org layer never returns a restricted column
    return out.drop(columns=[c for c in out.columns if c in restricted]).reset_index(drop=True)


@function(sources=("hr.employee.emp_key", "hr.employee.gender", "hr.employee.hire_date", "hr.employee.leave_date", "hr.employee.legal_entity_key",
                   "hr.employment_term.team_key", "hr.employment_term.role_key", "hr.employment_term.grade_key", "hr.employment_term.fte",
                   "hr.team.dep_key", "hr.team.site_key", "hr.role.name", "hr.grade.level", "hr.department.dep_code"),
          oracle="py:tests/test_people.py::test_headcounts")
def org_on(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, role: pd.DataFrame, grade: pd.DataFrame, department: pd.DataFrame,
           site: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need one frame with each person on a date: term, employee, team, role, grade, department, country and calendar region.

    Rule: the terms valid on the date are joined to the employee, team, role, grade, department and site frames. There is no pay column. active follows the hire and leave dates.

    Args:
        employee: Employee frame (hr.employee) with emp_key, gender, hire_date, leave_date and legal_entity_key.
        term: Employment term frame (hr.employment_term).
        team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, legal_entity_key and site_key.
        role: Role frame (hr.role) with role_key and name.
        grade: Grade frame (hr.grade) with gra_key and level.
        department: Department frame (hr.department) with dep_key and dep_code.
        site: Site frame (hr.site) with site_key and country.
        as_of: The date.

    Returns:
        pandas.DataFrame with one row per person with a term on the date: emp_key, as_of, active, gender, hire_date, leave_date, legal_entity_key, team_key, role_key, role_name, grade_key, level, dep_key, dep_code, site_key, country, region, fte, valid_from and valid_to.

    Raises:
        FrameError: a frame lacks a column, the employee frame has a person twice, a person employed on the date has no term, or a term valid on the date has no row in the employee frame.
        AmbiguousKey: one person has two terms valid on the date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import org_on
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "hire_date": ["2020-01-01"], "leave_date": [None], "legal_entity_key": ["LE-01"]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "grade_key": ["GRA-1"], "fte": [1.0]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"], "cost_centre_key": ["CC-1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-05"]})
        >>> role = pd.DataFrame({"role_key": ["ROLE-1"], "name": ["Pipe fitter"]})
        >>> grade = pd.DataFrame({"gra_key": ["GRA-1"], "level": [4]})
        >>> department = pd.DataFrame({"dep_key": ["DEP-1"], "dep_code": ["ENG"]})
        >>> site = pd.DataFrame({"site_key": ["SITE-05"], "country": ["DE"]})
        >>> org_on(employee, term, team, role, grade, department, site, dt.date(2026, 3, 31))[["emp_key", "role_name", "dep_code", "country", "region"]].values.tolist()
        [['EMP-000001', 'Pipe fitter', 'ENG', 'DE', 'DE-HH']]
    """
    _need(employee, ["emp_key", "gender", "hire_date", "leave_date", "legal_entity_key"], "hr.employee")
    _need(role, ["role_key", "name"], "hr.role")
    _need(grade, ["gra_key", "level"], "hr.grade")
    _need(department, ["dep_key", "dep_code"], "hr.department")
    _unique(employee, "hr.employee")
    terms = terms_on(term, as_of)
    _require_terms(employee, terms, as_of)
    orphan = terms.loc[~terms["emp_key"].isin(employee["emp_key"]), "emp_key"]
    if len(orphan):
        raise FrameError(f"{len(orphan)} terms valid on {as_of} have no row in hr.employee (for example {orphan.iloc[0]})")
    t = terms[["emp_key", "team_key", "role_key", "grade_key", "fte", "valid_from", "valid_to"]]
    ctx = team_context(team, site)[["team_key", "dep_key", "site_key", "country", "region"]]
    e = employee[["emp_key", "gender", "hire_date", "leave_date", "legal_entity_key"]].copy()
    e["active"] = _active(e, as_of).values
    out = (t.merge(e, on="emp_key", how="left", validate="one_to_one").merge(ctx, on="team_key", how="left", validate="many_to_one")
           .merge(role[["role_key", "name"]].rename(columns={"name": "role_name"}), on="role_key", how="left", validate="many_to_one")
           .merge(grade[["gra_key", "level"]], left_on="grade_key", right_on="gra_key", how="left", validate="many_to_one").drop(columns="gra_key")
           .merge(department[["dep_key", "dep_code"]], on="dep_key", how="left", validate="many_to_one"))
    out["as_of"] = pd.Timestamp(as_of)
    cols = ["emp_key", "as_of", "active", "gender", "hire_date", "leave_date", "legal_entity_key", "team_key", "role_key", "role_name", "grade_key",
            "level", "dep_key", "dep_code", "site_key", "country", "region", "fte", "valid_from", "valid_to"]
    return out[cols].sort_values("emp_key").reset_index(drop=True)


@function(sources=("hr.employee.hire_date", "hr.employee.leave_date", "hr.employment_term.fte", "hr.team.dep_key"),
          oracle="py:tests/test_people.py::test_headcounts")
def headcount_on(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, as_of: dt.date, level: str = "department") -> pd.DataFrame:
    """Use this when you need the number of active people and their full time equivalents on a date, by department, team or legal entity.

    Rule: a person is active on the date when the hire date is on or before it and the leave date is empty or on or after it. The team and the fte come from the employment term valid on the date.

    Args:
        employee: Employee frame (hr.employee) with emp_key, hire_date, leave_date and legal_entity_key, one row per person.
        term: Employment term frame (hr.employment_term).
        team: Team frame (hr.team) with team_key and dep_key.
        as_of: The date.
        level: "department", "team" or "entity". Default "department".

    Returns:
        pandas.DataFrame: one row per department, team or entity with headcount and fte, sorted by the key.

    Raises:
        FrameError: the level is not allowed, a frame lacks a column, an active person has no term on the date, or a team is missing in the team frame.
        AmbiguousKey: one person has two terms valid on the date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import headcount_on
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "hire_date": ["2020-01-01", "2027-01-01"],
        ...                          "leave_date": [None, None], "legal_entity_key": ["LE-01", "LE-01"]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2020-01-01", "2027-01-01"], "valid_to": [None, None],
        ...                      "team_key": ["TEAM-01", "TEAM-01"], "fte": [1.0, 0.5]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"]})
        >>> headcount_on(employee, term, team, dt.date(2026, 6, 1)).to_dict("records")
        [{'dep_key': 'DEP-1', 'headcount': 1, 'fte': 1.0}]
    """
    if level not in _LEVELS:
        raise FrameError(f"level {level!r} is not one of {', '.join(_LEVELS)}")
    _need(employee, ["emp_key", "hire_date", "leave_date", "legal_entity_key"], "hr.employee")
    _need(team, ["team_key", "dep_key"], "hr.team")
    _unique(employee, "hr.employee")
    terms = terms_on(term, as_of)
    _require_terms(employee, terms, as_of)
    act = employee.loc[cast(Any, _active(employee, as_of).values), ["emp_key", "legal_entity_key"]]
    m = (act.merge(terms[["emp_key", "team_key", "fte"]], on="emp_key", how="left", validate="one_to_one")
         .merge(team[["team_key", "dep_key"]], on="team_key", how="left", validate="many_to_one"))
    if m["dep_key"].isna().any():
        raise FrameError(f"{int(m['dep_key'].isna().sum())} active people sit in a team that is not in the hr.team frame (for example {m.loc[m['dep_key'].isna(), 'team_key'].iloc[0]})")
    key = _LEVELS[level]
    out = m.groupby(key, as_index=False).agg(headcount=("emp_key", "nunique"), fte=("fte", "sum"))
    return out.sort_values(key).reset_index(drop=True)


@function(sources=("hr.data_release.release", "hr.data_release.now"), oracle="py:tests/test_release.py::test_every_source_has_one_row_data_release")
def data_now(data_releases: Mapping[str, pd.DataFrame], as_of: dt.date | None = None) -> dt.date:
    """Use this when you need the date of the data release (the "now" of the data) and want to refuse a date after it.

    Rule: all data_release frames passed must agree; the release date is their now. Ledgers and status caches end there, so a later as_of is refused.

    Args:
        data_releases: A mapping of source name to its data_release frame (one row each), for example {"hr": frame}.
        as_of: Optional date to check against the release date.

    Returns:
        datetime.date: the release date.

    Raises:
        FrameMissing: no data_release frame was passed.
        FrameError: a data_release frame does not have exactly one row.
        ReleaseMismatch: the frames name different releases.
        PeriodError: as_of is after the release date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import data_now
        >>> release = pd.DataFrame({"release": ["r1"], "now": ["2026-03-31"], "generated_at": ["2026-04-01"], "base_seed": [1], "increment": [0]})
        >>> data_now({"hr": release})
        datetime.date(2026, 3, 31)
        >>> data_now({"hr": release}, dt.date(2026, 4, 30))
        Traceback (most recent call last):
        ...
        halvaro.core.errors.PeriodError: as_of 2026-04-30 is after the data release date 2026-03-31: holiday ledgers and status caches end there. Use a date up to 2026-03-31.
    """
    now = release_now(data_releases).now
    if as_of is not None and pd.Timestamp(as_of) > pd.Timestamp(now):
        raise PeriodError(f"as_of {as_of} is after the data release date {now}: holiday ledgers and status caches end there. Use a date up to {now}.")
    return now


def _day(as_of: Any) -> pd.Timestamp:
    """A calendar day: dates, Timestamps and ISO text; a number, an unreadable text or a time zone raises PeriodError."""
    if isinstance(as_of, (bool, int, float, np.number)):
        raise PeriodError(f"as_of {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise PeriodError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise PeriodError(f"as_of {as_of!r} is not a date without a time zone")
    return d.normalize()


def _flag(column: pd.Series, name: str) -> pd.Series:
    """A boolean column as bool; a null or a value that is not True or False raises, never a cast."""
    if column.dtype == bool:
        return column
    bad = column.isna() | ~column.isin([True, False]) | column.map(lambda v: isinstance(v, str))
    if bad.any():
        raise FrameError(f"{name} must be True or False on every row; {int(bad.sum())} are not (for example {column[bad].iloc[0]!r})")
    return column.astype(bool)


class Executives(NamedTuple):
    """Result of executives_on: one row per holder, and the roles that nobody holds on the date."""

    frame: pd.DataFrame
    vacant: tuple[str, ...]


@function(sources=("hr.role.name", "hr.department.dep_code", "hr.employment_term.team_key"), oracle="py:halvaro_gen/world/people.py::Builder")
def executives_on(org: pd.DataFrame, role: pd.DataFrame, roles: Sequence[str]) -> Executives:
    """Use this when you need the holders of named executive roles on the date of an org_on frame, and the roles that nobody holds.

    Rule: the roles are named by the caller (hr keeps no list of executive roles). A holder is a person who is active in the org frame with one of the roles. Leave status is not applied. A vacant role is listed, an unknown role raises.

    Args:
        org: An org_on frame for one date, with emp_key, as_of, active, role_name, dep_code and team_key.
        role: The role frame (hr.role) with the column name.
        roles: One role name or a list of distinct role names.

    Returns:
        Executives: .frame has emp_key, role_name, dep_code and team_key sorted by role and person; .vacant lists the named roles that nobody holds.

    Raises:
        FrameError: a frame lacks a column or has duplicate column names, no role is named, the roles are not distinct text, a role is not in hr.role, or the org frame is not for exactly one date.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import executives_on
        >>> org = pd.DataFrame({"emp_key": ["EMP-000001"], "as_of": [pd.Timestamp("2026-06-01")], "active": [True],
        ...                     "role_name": ["Chief Financial Officer"], "dep_code": ["FIN"], "team_key": ["TEAM-01"]})
        >>> role = pd.DataFrame({"name": ["Chief Financial Officer", "Director Service"]})
        >>> result = executives_on(org, role, ["Chief Financial Officer", "Director Service"])
        >>> result.frame["emp_key"].tolist(), result.vacant
        (['EMP-000001'], ('Director Service',))
    """
    _need(org, ["emp_key", "as_of", "active", "role_name", "dep_code", "team_key"], "org_on")
    _need(role, ["name"], "hr.role")
    if org.columns.duplicated().any() or role.columns.duplicated().any():
        raise FrameError("the org and role frames must not have duplicate column names")
    names = [roles] if isinstance(roles, str) else list(roles)
    if not names:
        raise FrameError("name at least one role; the caller passes them (policy.delivery.executive_roles), hr keeps no list")
    if any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        raise FrameError("roles must be distinct role names (text)")
    unknown = [n for n in names if n not in set(role["name"])]
    if unknown:
        raise FrameError(f"role(s) {', '.join(map(repr, unknown))} are not in hr.role.name; known roles include {', '.join(sorted(map(str, role['name']))[:6])} ...")
    days = org["as_of"].unique()
    if len(days) != 1 or pd.isna(days[0]):
        raise FrameError(f"the org frame must be for one date, it has {len(days)} as_of values" + (" (empty or null)" if len(days) < 2 else ""))
    held = org[_flag(org["active"], "org.active") & org["role_name"].isin(names)]
    out = held[["emp_key", "role_name", "dep_code", "team_key"]].sort_values(["role_name", "emp_key"]).reset_index(drop=True)
    return Executives(out, tuple(n for n in names if n not in set(out["role_name"])))


@function(sources=("hr.employee.emp_key", "hr.employee.hire_date", "hr.employee.leave_date", "hr.leave_record.emp_key", "hr.leave_record.leave_type",
                   "hr.leave_record.start", "hr.leave_record.end"), oracle="py:halvaro_gen/truth/staffing.py::status_on", facts=("policy.staffing.unavailable_leave_types",))
def status_on(employee: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, unavailable_leave_types: Sequence[str] | PolicyDefault = UNAVAILABLE_LEAVE_TYPES) -> pd.DataFrame:
    """Use this when you need to know, for each person, whether they have left, are on leave, are not yet hired or are available on a date.

    Rule: left when leave_date is before the date, not_hired when hire_date is after it, on_leave when a leave of an unavailable type covers it (a leave with no end is open), otherwise available. The leave types default to the fact policy.staffing.unavailable_leave_types (status proposed: the owner has not decided); when the default is used the frame carries attrs["policy_status"] with the fact status.

    Args:
        employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
        leave_record: Leave frame (hr.leave_record) with emp_key, leave_type, start and end.
        as_of: The date.
        unavailable_leave_types: Leave types that make a person unavailable, as a list, or the default fact.

    Returns:
        pandas.DataFrame: one row per employee with emp_key, as_of and status (left, on_leave, not_hired or available).

    Raises:
        FrameError: a frame lacks a column, employee has duplicate emp_key values, or a person has no hire_date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import status_on
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"],
        ...                          "hire_date": ["2020-01-01", "2021-01-01", "2027-01-01", "2019-01-01"],
        ...                          "leave_date": [None, None, None, "2025-06-30"]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["parental"], "start": ["2026-03-01"], "end": [None]})
        >>> status_on(employee, leave, dt.date(2026, 6, 1), unavailable_leave_types=["parental"])["status"].tolist()
        ['available', 'on_leave', 'not_hired', 'left']
    """
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    _unique(employee, "hr.employee")
    types = unavailable_types(unavailable_leave_types)
    d = _day(as_of)
    hire, leave = pd.to_datetime(employee["hire_date"]), pd.to_datetime(employee["leave_date"])
    if hire.isna().any():
        raise FrameError(f"{int(hire.isna().sum())} people have no hire_date (for example {employee.loc[hire.isna(), 'emp_key'].iloc[0]}); a status on a date needs it")
    start, end = pd.to_datetime(leave_record["start"]), pd.to_datetime(leave_record["end"])
    away = set(leave_record.loc[leave_record["leave_type"].isin(types) & (start <= d) & (end.isna() | (end >= d)), "emp_key"])
    label = np.where(leave.notna() & (leave < d), "left", np.where(hire > d, "not_hired", np.where(employee["emp_key"].isin(away), "on_leave", "available")))
    out = pd.DataFrame({"emp_key": employee["emp_key"].to_numpy(), "as_of": d, "status": label}, index=employee.index)
    if isinstance(unavailable_leave_types, PolicyDefault):
        out.attrs["policy_status"] = {unavailable_leave_types.fact_id: fact(unavailable_leave_types.fact_id).status}
    return out


@function(sources=("hr.employee.emp_key", "hr.employee.hire_date", "hr.employee.leave_date"), oracle="py:halvaro_gen/truth/hr.py::pay_frame")
def tenure_years(employee: pd.DataFrame, as_of: dt.date, days_per_year: float = 365.25) -> pd.Series:
    """Use this when you need the years of service of each person on a date.

    Rule: (date minus hire_date) in days over days_per_year. A leaver is measured to the leave date. The value is NaN before the hire date and when the leave date is before the hire date.

    Args:
        employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
        as_of: The date.
        days_per_year: Days in a year for the division. Default 365.25. Must be positive.

    Returns:
        pandas.Series: years of service, named tenure_years and indexed by emp_key.

    Raises:
        FrameError: employee lacks a column or has duplicate emp_key values, or days_per_year is not positive.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import tenure_years
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000003"], "hire_date": ["2020-01-01", "2027-01-01"], "leave_date": [None, None]})
        >>> tenure_years(employee, dt.date(2026, 1, 1)).round(2).to_dict()
        {'EMP-000001': 6.0, 'EMP-000003': nan}
    """
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _unique(employee, "hr.employee")
    if not days_per_year > 0:
        raise FrameError(f"days_per_year must be positive, not {days_per_year!r}")
    d = _day(as_of)
    hire, leave = pd.to_datetime(employee["hire_date"]), pd.to_datetime(employee["leave_date"])
    upto = leave.where(leave.notna() & (leave < d), d)
    years = (upto - hire).dt.days / days_per_year
    years[(hire > d) | (upto < hire)] = np.nan
    return pd.Series(years.to_numpy(), index=pd.Index(employee["emp_key"].to_numpy(), name="emp_key"), name="tenure_years")


_EVENTS = ("hire", "window_start", "summary", "pay_review", "promotion", "fte_change")


@function(sources=("hr.employment_term.emp_key", "hr.employment_term.change_reason", "hr.employment_term.valid_from"), oracle="py:halvaro_gen/world/people.py::Builder")
def term_changes(term: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the events behind the employment terms: one row per name in the change reason of each term.

    Rule: a change reason such as pay_review+promotion gives two events with combined true; a single name gives one event with combined false. The known names are hire, window_start, summary, pay_review, promotion and fte_change.

    Args:
        term: Employment term frame (hr.employment_term) with emp_key, valid_from and change_reason.

    Returns:
        pandas.DataFrame with emp_key, valid_from, event and combined, sorted by person, date and event.

    Raises:
        FrameError: a column is missing, a term has no change_reason, or a name is not one of the known names.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import term_changes
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2024-01-01", "2025-01-01"], "change_reason": ["hire", "pay_review+promotion"]})
        >>> term_changes(term)[["valid_from", "event", "combined"]].to_dict("records")
        [{'valid_from': '2024-01-01', 'event': 'hire', 'combined': False}, {'valid_from': '2025-01-01', 'event': 'pay_review', 'combined': True}, {'valid_from': '2025-01-01', 'event': 'promotion', 'combined': True}]
    """
    _need(term, ["emp_key", "valid_from", "change_reason"], "hr.employment_term")
    if term["change_reason"].isna().any():
        raise FrameError(f"{int(term['change_reason'].isna().sum())} terms have no change_reason")
    parts = term["change_reason"].astype(str).str.split("+")
    events = [(name, k, f, len(p) > 1) for k, f, p in zip(term["emp_key"], term["valid_from"], parts) for name in p]
    unknown = sorted({name for name, *_ in events} - set(_EVENTS))
    if unknown:
        raise FrameError(f"unknown change_reason name(s) {', '.join(map(repr, unknown))}; known: {', '.join(_EVENTS)}")
    out = pd.DataFrame([(k, f, name, c) for name, k, f, c in events], columns=["emp_key", "valid_from", "event", "combined"])
    order = out.assign(_d=pd.to_datetime(out["valid_from"])).sort_values(["emp_key", "_d", "event"], kind="stable").index
    return out.loc[order].reset_index(drop=True)


@function(sources=("hr.employment_term.emp_key", "hr.employment_term.valid_from", "hr.employment_term.valid_to", "hr.employee.hire_date", "hr.employee.leave_date"),
          facts=("world.window_start",), oracle="py:tests/test_people.py::test_terms_are_continuous_and_within_employment")
def check_term_contiguity(term: pd.DataFrame, employee: pd.DataFrame) -> pd.DataFrame:
    """Use this when you check the employment term history of every person for gaps, overlaps and other breaks in the dating.

    Rule: per person the terms are ordered by valid_from. The rules are reversed, gap, overlap, two_open, open_not_last, null_key, no_employee, hire_missing, leave_before_hire, no_terms, first_row (the first term does not start on the expected day: the hire date, or the start of the data window when the person was hired before it and still works), open_row and last_row_not_leave_date.

    Args:
        term: Employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
        employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail; empty when the history is clean.

    Raises:
        FrameError: a frame lacks a column.
        FactNotFound: the fact for the start of the data window is not known.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import check_term_contiguity
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "valid_from": ["2024-01-01", "2025-03-01"], "valid_to": ["2024-12-31", None]})
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2024-01-01"], "leave_date": [None]})
        >>> check_term_contiguity(term, employee)["rule"].tolist()
        ['gap']
    """
    _need(term, ["emp_key", "valid_from", "valid_to"], "hr.employment_term")
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _unique(employee, "hr.employee")
    start = pd.Timestamp(fact("world.window_start").value)
    bad = [check_contiguity(term, "emp_key", table="hr.employment_term")]
    rows = []
    ordered = term.assign(_f=pd.to_datetime(term["valid_from"]), _t=pd.to_datetime(term["valid_to"])).sort_values(["emp_key", "_f"], kind="stable")
    first, last = ordered.groupby("emp_key").head(1).set_index("emp_key"), ordered.groupby("emp_key").tail(1).set_index("emp_key")
    if term["emp_key"].isna().any():
        rows.append(("hr.employment_term", "(null)", "null_key", f"{int(term['emp_key'].isna().sum())} terms have no emp_key"))
    for k in sorted(set(term["emp_key"].dropna()) - set(employee["emp_key"])):
        rows.append(("hr.employment_term", k, "no_employee", "the person has terms but no row in hr.employee"))
    e: Any
    hire: Any
    leave: Any
    for e in employee.itertuples(index=False):
        hire, leave = pd.NaT if e.hire_date is None or pd.isna(e.hire_date) else pd.Timestamp(e.hire_date), pd.NaT if e.leave_date is None or pd.isna(e.leave_date) else pd.Timestamp(e.leave_date)
        if pd.isna(hire):
            rows.append(("hr.employee", e.emp_key, "hire_missing", "the person has no hire_date"))
            continue
        if pd.notna(leave) and leave < hire:
            rows.append(("hr.employee", e.emp_key, "leave_before_hire", f"leave_date {leave.date()} is before hire_date {hire.date()}"))
        if e.emp_key not in first.index:
            rows.append(("hr.employment_term", e.emp_key, "no_terms", "the person has no term"))
            continue
        want = hire if (hire >= start or (pd.notna(leave) and leave < start)) else start
        got = first.loc[e.emp_key, "_f"]
        if got != want:
            rows.append(("hr.employment_term", e.emp_key, "first_row", f"first term starts {got.date()}, expected {want.date()}"))
        end = last.loc[e.emp_key, "_t"]
        if pd.isna(end) != pd.isna(leave):
            rows.append(("hr.employment_term", e.emp_key, "open_row", f"last term {'is open' if pd.isna(end) else 'ends ' + str(end.date())}, leave_date is {'empty' if pd.isna(leave) else str(leave.date())}"))
        elif pd.notna(end) and end != leave:
            rows.append(("hr.employment_term", e.emp_key, "last_row_not_leave_date", f"last term ends {end.date()}, leave_date is {leave.date()}"))
    return violations.frame([*(tuple(r) for r in pd.concat(bad).itertuples(index=False)), *rows])
