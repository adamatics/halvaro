"""Controlled work (rule 15): hours and allocation days of work that needs a certificate, checked against the certificates valid on the date.

The rules (which role, entity, project type and cost code need which qualification) are the controlled_tasks of config/competence.yaml. They are passed in, not read here, because HR keeps no policy
store for them: PROPOSED, the owner of the rule list is the Head of HR and People with the HSE manager. Validity is read from issued and expires only, never from the stored status."""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError
from halvaro.core.registry import function

from ._guard import staged
from .certs import _day
from .org import _need

_KINDS = ("time_entry", "allocation_start", "allocation_end", "allocation_planned")
_VIOLATION_COLS = ["kind", "rule_id", "emp_key", "prj_key", "work_date", "cst_key", "qual_key", "planned"]


class ControlledAudit(NamedTuple):
    """violations: one row per checked day without a valid certificate, sorted by kind (in the order time_entry, allocation_start, allocation_end, allocation_planned), rule_id, emp_key, work_date,
    prj_key. checked: per kind and rule the number of (row, rule) pairs checked and the violations among them (a row that two rules control counts twice). unchecked: per kind the rows no rule could
    judge: `unchecked` (no employment term on the date, so no role) and, among the rows that have a role a rule names, `no_project_type` (the project has no type, for a rule with project_types),
    `no_cst_key` (a time entry without cost code, for a rule with cst) and `no_entity` (the person has no legal entity, or no hr.employee row, for a rule with an entity). A row counts once per
    column, however many rules it escapes. An audit with no violations is clean only when all four counts are zero too."""

    violations: pd.DataFrame
    checked: pd.DataFrame
    unchecked: pd.DataFrame


def _isnull(x: Any) -> bool:
    return x is None or x is pd.NA or (isinstance(x, float) and np.isnan(x))


def _cst_name(x: Any, rule_id: Any = None) -> str:
    """'CST-430' for 430, 430.0, '430' and 'CST-430'; anything else (a fraction, a bool, text) raises FrameError."""
    if isinstance(x, str):
        t = x.strip()
        if t.startswith("CST-") and t[4:].isdigit():
            return t
        if t.isdigit():
            return f"CST-{int(t)}"
    elif isinstance(x, (int, np.integer)) and not isinstance(x, (bool, np.bool_)):
        return f"CST-{int(x)}"
    elif isinstance(x, (float, np.floating)) and np.isfinite(x) and float(x).is_integer():
        return f"CST-{int(x)}"
    raise FrameError(f"rule {rule_id} has a cost code {x!r} that is not a whole number or 'CST-n'")


def _cst_entry(x: Any) -> Any:
    """The cost code of a time entry as 'CST-n'; null stays null, a value that is no cost code number is kept as it is (it matches no rule)."""
    if _isnull(x) or x is pd.NaT:
        return None
    try:
        return _cst_name(x)
    except FrameError:
        return x


def _number(x: Any) -> bool:
    return isinstance(x, (bool, int, float, np.number, np.bool_)) and not _isnull(x)


def _flag(x: Any, rule_id: Any) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer, float, np.floating)) and x in (0, 1):
        return bool(x)
    raise FrameError(f"rule {rule_id} has an allocation flag that is not true or false: {x!r}")


def _rules(rules: pd.DataFrame, role_groups: Mapping[str, Sequence[str]] | None, all_roles: set[str]) -> list[tuple[Any, Any, set[str], Any, set[str] | None, set[str] | None, bool]]:
    _need(rules, ["rule_id", "qual_key", "roles", "entity", "project_types", "cst", "allocation"], "controlled rules")
    if rules["rule_id"].duplicated().any():
        raise FrameError("controlled rules has more than one row for a rule_id")
    if role_groups is not None and not isinstance(role_groups, Mapping):
        raise FrameError(f"role_groups must be None or a mapping from a group name to a list of role names, not {role_groups!r}")
    for k, v in (role_groups or {}).items():
        if not isinstance(v, (str, Iterable)):
            raise FrameError(f"role_groups must map each group name to a role name or a list of role names; group {k!r} has {v!r}")
    groups = {k: ([v] if isinstance(v, str) else list(v)) for k, v in (role_groups or {}).items()}
    out = []
    r: Any
    for r in rules.itertuples(index=False):
        if _isnull(r.roles):
            raise FrameError(f"rule {r.rule_id} has no roles")
        names: set[str] = set()
        for x in ([r.roles] if isinstance(r.roles, str) else list(r.roles)):
            names.update(all_roles if x == "*" else groups.get(x, [x]))
        if not names:
            raise FrameError(f"rule {r.rule_id} has no roles")
        unknown = sorted(names - all_roles)
        if unknown:
            raise FrameError(f"rule {r.rule_id} names roles that hr.role does not have: {unknown[:3]}")
        types: set[str] | None = None if _isnull(r.project_types) else ({r.project_types} if isinstance(r.project_types, str) else set(r.project_types))
        if types is not None and "any" in types:
            types = None
        cst: set[str] | None
        if _isnull(r.cst):
            cst = None
        else:
            items = [r.cst] if isinstance(r.cst, (int, np.integer, str, float, np.floating)) else list(r.cst)
            if any(isinstance(x, str) and x == "any" for x in items):
                cst = None
            else:
                cst = {_cst_name(x, r.rule_id) for x in items}
        ent = None if _isnull(r.entity) or r.entity == "" else r.entity
        if _isnull(r.allocation):
            raise FrameError(f"rule {r.rule_id} has no allocation flag")
        out.append((r.rule_id, r.qual_key, names, ent, types, cst, _flag(r.allocation, r.rule_id)))
    return out


def _keys(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    return frame.assign(**{c: frame[c].astype(object) for c in columns})


def _dates(frame: pd.DataFrame, column: str, what: str, *, null_ok: bool = False) -> pd.Series:
    col = frame[column]
    if (pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_datetime64_any_dtype(col) and col.notna().any()) or (col.dtype == object and col.map(_number).any()):
        raise FrameError(f"{what}.{column} holds numbers, not dates")
    try:
        out = pd.to_datetime(col)
    except (ValueError, TypeError, OverflowError) as exc:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {exc}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    if not null_ok and out.isna().any():
        raise FrameError(f"the date {what}.{column} has nulls")
    return out.dt.normalize()


@staged(sources=("projects.time_entry.emp_key", "projects.time_entry.work_date", "projects.time_entry.prj_key", "projects.time_entry.cst_key", "hr.allocation.emp_key", "hr.allocation.prj_key",
                   "hr.allocation.start", "hr.allocation.end", "hr.employment_term.role_key", "hr.role.name", "hr.employee.legal_entity_key", "hr.employee.hire_date", "projects.project.type",
                   "competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::_rule15")
def controlled_work_audit(time_entry: pd.DataFrame, allocation: pd.DataFrame, project: pd.DataFrame, employment_term: pd.DataFrame, role: pd.DataFrame, employee: pd.DataFrame,
                          cert: pd.DataFrame, rules: pd.DataFrame, as_of: dt.date | str | pd.Timestamp, *, role_groups: Mapping[str, Sequence[str]] | None = None, first_term_from_hire: bool = True,
                          time_entries_until_as_of: bool = False) -> ControlledAudit:
    """Use this when you need the time entries and allocation days of controlled work that have no valid certificate on the day.

    Rule: a row is controlled by a rule when the person's role (the employment term valid on the row's date, role name from hr.role) is in the rule's roles (role names, keys of role_groups, or '*' for every role; an unknown name raises), the person's legal entity equals the rule's entity (empty: any), the project type is in the rule's project_types (empty or 'any': every type) and, for time entries, the cost code is in the rule's cst (numbers such as 430 or 'CST-430'; empty or 'any': every code). A certificate is valid from issued to expires, both inclusive, an empty expires is open; a time of day in a date is dropped.
    Kinds: time_entry (audited whatever its date, also after as_of, unless time_entries_until_as_of is true); allocation_start (the start day of a stint that starts on or before as_of); allocation_end (the end day, never later than as_of; an open stint counts as ending on as_of, so one that starts after it has only its planned start); allocation_planned (the start day of a stint that starts after as_of and the end day of one that ends after it: planned days, so a certificate that expires before them is a forward warning, not a breach that has happened). Allocations use only rules with allocation true, whatever the cost code, and take the role at the stint's start for every check of the stint.
    first_term_from_hire (proposed default, MEDIUM): the first employment term of a person counts from the hire date (a later hire date never moves the start later); with false, rows before the first term are unchecked. Keys of any dtype are read as keys, so an empty frame is simply empty; an integer cost code such as 430 is read as 'CST-430'. An audit with no violations is clean only when the unchecked counts are zero too.

    Args:
        time_entry: Time entries (projects.time_entry) with emp_key, work_date, prj_key and cst_key.
        allocation: Allocation stints (hr.allocation) with emp_key, prj_key, start and end; an empty end is open.
        project: Projects (projects.project) with prj_key and type, one row per project.
        employment_term: Employment terms (hr.employment_term) with emp_key, valid_from, valid_to and role_key; an empty valid_to is open.
        role: Roles (hr.role) with role_key and name, one row per role.
        employee: Employees (hr.employee) with emp_key, legal_entity_key and hire_date, one row per person.
        cert: Certificates (competence.certification_held) with emp_key, qual_key, issued and expires.
        rules: The controlled rules with rule_id, qual_key, roles, entity, project_types, cst and allocation (true: the rule also applies to allocations; 0 and 1 are read as false and true).
        as_of: The audit date (a date, a timestamp or an ISO date text); dates must be dates, not numbers such as 20250601.
        role_groups: Names that stand for several roles in the rules' roles; None means no groups.
        first_term_from_hire: Whether the first term of a person counts from the hire date (see the Rule).
        time_entries_until_as_of: True leaves out the time entries dated after as_of.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        ControlledAudit, a named tuple of three pandas.DataFrame. violations: kind, rule_id, emp_key, prj_key, work_date, cst_key (null for allocations), qual_key and planned (true for allocation_planned), one row per checked day without a valid certificate, sorted by kind (time_entry, allocation_start, allocation_end, allocation_planned), rule_id, emp_key, work_date and prj_key. checked: kind, rule_id, checked (the (row, rule) pairs checked; a row that two rules control counts twice) and violations among them. unchecked: kind, unchecked (no employment term on the date, so no role), no_project_type, no_cst_key and no_entity (rows with a role a rule names that lack the project type, cost code or legal entity that rule needs; a person with no hr.employee row counts under no_entity); a row counts once per column however many rules it escapes.

    Raises:
        FrameError: a frame lacks a column, role_groups is not a mapping or a group is not a role name or a list of them, a key is not unique in project, role or employee, a time entry or allocation names a project that is not in project, a term has an unknown role_key, two terms are valid on the same day for a person, a term, stint or certificate ends before it starts or expires before it was issued, a rule has no roles, an unknown role, a duplicate rule_id, a cost code that is not a whole number or 'CST-n' or an allocation flag that is not true or false, or a date column holds numbers, a time zone, nulls where a date is needed or text that is not a date.
        PeriodError: as_of is not a date.
        StageRefusal: a context is given and its stage does not hold the projects or competence source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import controlled_work_audit
        >>> time_entry = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "work_date": ["2026-03-10", "2026-06-10"], "prj_key": ["PRJ-001"] * 2, "cst_key": [430, 430]})
        >>> allocation = pd.DataFrame({"emp_key": ["EMP-000001"], "prj_key": ["PRJ-001"], "start": ["2026-02-01"], "end": [None]})
        >>> project = pd.DataFrame({"prj_key": ["PRJ-001"], "type": ["install"]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2025-01-01"], "valid_to": [None], "role_key": ["ROLE-01"]})
        >>> role = pd.DataFrame({"role_key": ["ROLE-01"], "name": ["technician"]})
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "legal_entity_key": ["LE-01"], "hire_date": ["2025-01-01"]})
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "issued": ["2026-01-01"], "expires": ["2026-05-31"]})
        >>> rules = pd.DataFrame({"rule_id": ["R1"], "qual_key": ["QUAL-01"], "roles": [["technician"]], "entity": [None], "project_types": ["any"], "cst": [430], "allocation": [True]})
        >>> audit = controlled_work_audit(time_entry, allocation, project, term, role, employee, cert, rules, "2026-06-30")
        >>> audit.violations[["kind", "rule_id", "emp_key", "work_date"]].astype(str).to_dict("records")
        [{'kind': 'time_entry', 'rule_id': 'R1', 'emp_key': 'EMP-000001', 'work_date': '2026-06-10'}, {'kind': 'allocation_end', 'rule_id': 'R1', 'emp_key': 'EMP-000001', 'work_date': '2026-06-30'}]
        >>> audit.checked.to_dict("records")[0]
        {'kind': 'time_entry', 'rule_id': 'R1', 'checked': 2, 'violations': 1}
    
    """
    _need(time_entry, ["emp_key", "work_date", "prj_key", "cst_key"], "projects.time_entry")
    _need(allocation, ["emp_key", "prj_key", "start", "end"], "hr.allocation")
    _need(project, ["prj_key", "type"], "projects.project")
    _need(employment_term, ["emp_key", "valid_from", "valid_to", "role_key"], "hr.employment_term")
    _need(role, ["role_key", "name"], "hr.role")
    _need(employee, ["emp_key", "legal_entity_key", "hire_date"], "hr.employee")
    _need(cert, ["emp_key", "qual_key", "issued", "expires"], "competence.certification_held")
    time_entry = _keys(time_entry, ["emp_key", "prj_key"]).assign(cst_key=time_entry["cst_key"].map(_cst_entry).astype(object))
    allocation, employment_term, cert = _keys(allocation, ["emp_key", "prj_key"]), _keys(employment_term, ["emp_key", "role_key"]), _keys(cert, ["emp_key", "qual_key"])
    for frame, key, what in ((project, "prj_key", "projects.project"), (role, "role_key", "hr.role"), (employee, "emp_key", "hr.employee")):
        if frame[key].duplicated().any():
            raise FrameError(f"{what} has more than one row for a {key}")
    day = _day(as_of)
    rl = _rules(rules, role_groups, set(role["name"]))
    for what, frame in (("projects.time_entry", time_entry), ("hr.allocation", allocation)):
        unknown = sorted(set(frame["prj_key"]) - set(project["prj_key"]))
        if unknown:
            raise FrameError(f"{what} has projects that projects.project does not have: {unknown[:3]}")
    terms = employment_term.merge(role[["role_key", "name"]], on="role_key", how="left")
    if terms["name"].isna().any():
        raise FrameError("hr.employment_term has a role_key that hr.role does not have")
    terms = terms.assign(valid_from=_dates(terms, "valid_from", "hr.employment_term"), valid_to=_dates(terms, "valid_to", "hr.employment_term", null_ok=True))[["emp_key", "valid_from", "valid_to", "name"]]
    if (terms["valid_to"] < terms["valid_from"]).any():
        raise FrameError("hr.employment_term has a term that ends before it starts")
    terms = terms.rename(columns={"name": "role_name"})
    if first_term_from_hire:
        hire = _dates(employee, "hire_date", "hr.employee")
        hire = pd.Series(hire.to_numpy(), index=employee["emp_key"].to_numpy())
        first = terms.groupby("emp_key")["valid_from"].transform("min")
        early = (terms["valid_from"] == first) & terms["emp_key"].map(hire).notna()
        terms.loc[early, "valid_from"] = np.minimum(terms.loc[early, "valid_from"], terms.loc[early, "emp_key"].map(hire))
    ent = employee.set_index("emp_key")["legal_entity_key"]
    ptype = project.set_index("prj_key")["type"]
    c = cert[["emp_key", "qual_key"]].assign(issued=_dates(cert, "issued", "competence.certification_held", null_ok=True), expires=_dates(cert, "expires", "competence.certification_held", null_ok=True).fillna(pd.Timestamp.max))
    if (c["expires"] < c["issued"]).any():
        raise FrameError("competence.certification_held has a certificate that expires before it was issued")

    def rows(kind: str) -> pd.DataFrame:
        if kind == "time_entry":
            x = time_entry[["emp_key", "prj_key", "cst_key"]].assign(work_date=_dates(time_entry, "work_date", "projects.time_entry"), role_date=lambda f: f["work_date"])
            if time_entries_until_as_of:
                x = x[x["work_date"] <= day]
        else:
            st, en_raw = _dates(allocation, "start", "hr.allocation"), _dates(allocation, "end", "hr.allocation", null_ok=True)
            if (en_raw < st).any():
                raise FrameError("hr.allocation has a stint that ends before it starts")
            en = en_raw.fillna(day)   # an open stint counts to `as_of`: no end row for one that starts after it, only its planned start
            base = allocation[["emp_key", "prj_key"]].assign(cst_key=None, role_date=st)
            if kind == "allocation_start":
                x = base.assign(work_date=st)[st <= day]
            elif kind == "allocation_end":
                x = base.assign(work_date=en.clip(upper=cast(Any, day)))[st <= day]
            else:
                a = base.assign(work_date=st)[st > day]
                b = base.assign(work_date=en)[en > day]
                x = pd.concat([a, b], ignore_index=True)
        x = x.assign(entity=x["emp_key"].map(ent), project_type=x["prj_key"].map(ptype)).reset_index(drop=True)
        x["rid"] = x.index
        m = x[["rid", "emp_key", "role_date"]].merge(terms, on="emp_key", how="left")
        m = m[(m["valid_from"] <= m["role_date"]) & (m["valid_to"].isna() | (m["valid_to"] >= m["role_date"]))]
        if m.duplicated("rid").any():
            raise FrameError("hr.employment_term has two terms valid on the same day for a person")
        return x.merge(m[["rid", "role_name"]], on="rid", how="left")

    viol, chk, unchk = [], [], []
    for kind in _KINDS:
        x = rows(kind)
        n_role = int(x["role_name"].isna().sum())
        x = x[x["role_name"].notna()]
        miss = {k: pd.Series(False, index=x.index) for k in ("project_type", "cst_key", "entity")}
        for rid_, qual, names, entity, types, cst, alloc in rl:
            if kind != "time_entry" and not alloc:
                continue
            s = x[x["role_name"].isin(names)]
            for col, wanted in (("project_type", types is not None), ("cst_key", cst is not None and kind == "time_entry"), ("entity", entity is not None)):
                if wanted:
                    miss[col] = miss[col] | x.index.isin(s.index[s[col].isna()])
            if entity is not None:
                s = s[s["entity"] == entity]
            if types is not None:
                s = s[s["project_type"].isin(types)]
            if kind == "time_entry" and cst is not None:
                s = s[s["cst_key"].isin(cst)]
            m = s[["rid", "emp_key", "work_date"]].merge(c[c["qual_key"] == qual][["emp_key", "issued", "expires"]], on="emp_key", how="left")
            m["ok"] = (m["issued"] <= m["work_date"]) & (m["expires"] >= m["work_date"])
            ok = m.groupby("rid")["ok"].any().reindex(s["rid"]).fillna(False).to_numpy(bool)
            bad = s[~ok]
            viol.append(bad.assign(kind=kind, rule_id=rid_, qual_key=qual, planned=(kind == "allocation_planned"))[_VIOLATION_COLS])
            chk.append((kind, rid_, len(s), len(bad)))
        unchk.append((kind, n_role, int(miss["project_type"].sum()), int(miss["cst_key"].sum()), int(miss["entity"].sum())))
    v = pd.concat(viol, ignore_index=True) if viol else pd.DataFrame(columns=_VIOLATION_COLS)
    v = v.assign(_k=v["kind"].map({k: i for i, k in enumerate(_KINDS)})).sort_values(["_k", "rule_id", "emp_key", "work_date", "prj_key"], kind="stable").drop(columns="_k").reset_index(drop=True)
    return ControlledAudit(v, pd.DataFrame(chk, columns=["kind", "rule_id", "checked", "violations"]),
                           pd.DataFrame(unchk, columns=["kind", "unchecked", "no_project_type", "no_cst_key", "no_entity"]))
