"""Coverage of required qualifications on a project: the requirement rows of a project, its crew on a date, the gap on record and including booked renewals, and who could cover.

Reads competence (Month 12). The certificate rule is the one of certs.valid_on: valid from issued to expires inclusive, never from the stored status. A booking covers from its course date
(policy.certificates.booked_renewal_counts, proposed); the gap is reported on record and including booked, side by side.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact
from halvaro.core.registry import function

from ._guard import staged
from .certs import _certs, _day, _days
from .org import UNAVAILABLE_LEAVE_TYPES, PolicyDefault, _need, leave_types_given, policy_number, unavailable_types

_REQ = ["scope_type", "scope_key", "qual_key", "min_headcount", "requirement_level"]
_SCOPES = ("project", "contract", "project_type", "role")
# proposed policy facts (policy.certificates.candidate_*): skill level to be listed (2) and to be plausible (3), look-ahead of a long leave (90 days), seat window after the start (60 days).
_LIST_LEVEL, _PLAUSIBLE_LEVEL = PolicyDefault("policy.certificates.candidate_list_level"), PolicyDefault("policy.certificates.candidate_plausible_level")
_LEAVE_DAYS, _SEAT_DAYS = PolicyDefault("policy.certificates.candidate_leave_days"), PolicyDefault("policy.certificates.candidate_seat_days")
_LONG_LEAVE = UNAVAILABLE_LEAVE_TYPES      # proposed policy fact policy.staffing.unavailable_leave_types, the same types as org.status_on


@staged(sources=("competence.requirement.scope_type", "competence.requirement.scope_key", "competence.requirement.qual_key", "competence.requirement.min_headcount",
                   "competence.requirement.requirement_level", "projects.project.prj_key", "projects.project.type", "projects.project.contract_key"),
          oracle="py:halvaro_gen/world/competence/requirements.py::build_requirements")
def project_requirements(requirement: pd.DataFrame, project: pd.DataFrame, prj_key: str, *, role_keys: Sequence[str] = ()) -> pd.DataFrame:
    """Use this when you need the qualifications that a project must cover, from the requirements of its project, contract, project type and roles.

    Rule: the rows of each scope that match the project are kept apart (column via) and never merged. Scope project matches the project key, contract its contract_key, project_type its type and role the role keys passed in.

    Args:
        requirement: Requirement frame (competence.requirement) with scope_type, scope_key, qual_key, min_headcount and requirement_level.
        project: Project frame (projects.project) with prj_key, type and contract_key.
        prj_key: The project.
        role_keys: The role keys of the crew, for the scope role. Default none.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: the columns of the requirement frame plus via, sorted by scope and qual_key; min_headcount is null for role rows.

    Raises:
        FrameError: a column is missing, the project is not in the project frame exactly once, or a scope_type is unknown.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import project_requirements
        >>> requirement = pd.DataFrame({"scope_type": ["project", "project_type", "project_type"], "scope_key": ["PRJ-1", "dh_network", "other"], "qual_key": ["QUAL-01", "QUAL-02", "QUAL-03"],
        ...                              "min_headcount": [2, 1, 1], "requirement_level": ["must", "must", "must"]})
        >>> project = pd.DataFrame({"prj_key": ["PRJ-1"], "type": ["dh_network"], "contract_key": [None]})
        >>> project_requirements(requirement, project, "PRJ-1")[["via", "qual_key", "min_headcount"]].to_dict("records")
        [{'via': 'project', 'qual_key': 'QUAL-01', 'min_headcount': 2}, {'via': 'project_type', 'qual_key': 'QUAL-02', 'min_headcount': 1}]
    """
    _need(requirement, _REQ, "competence.requirement")
    _need(project, ["prj_key", "type", "contract_key"], "projects.project")
    p = project[project["prj_key"] == prj_key]
    if len(p) != 1:
        raise FrameError(f"project {prj_key} is not in the projects.project frame exactly once ({len(p)} rows)")
    bad = sorted(set(requirement["scope_type"].dropna()) - set(_SCOPES))
    if bad:
        raise FrameError(f"competence.requirement.scope_type has unknown value(s) {', '.join(bad)}; known: {', '.join(_SCOPES)}")
    keys = {"project": [prj_key], "contract": [p["contract_key"].iloc[0]] if pd.notna(p["contract_key"].iloc[0]) else [], "project_type": [p["type"].iloc[0]],
            "role": [role_keys] if isinstance(role_keys, str) else list(role_keys)}
    hit = pd.concat([requirement[(requirement["scope_type"] == s) & requirement["scope_key"].isin(k)].assign(via=s) for s, k in keys.items()], ignore_index=True)
    order = {s: i for i, s in enumerate(_SCOPES)}
    return hit.assign(_o=hit["via"].map(order)).sort_values(["_o", "qual_key", "scope_key"]).drop(columns="_o").reset_index(drop=True)


@staged(sources=("hr.allocation.emp_key", "hr.allocation.prj_key", "hr.allocation.start", "hr.allocation.end", "hr.allocation.percent", "competence.crew_plan.prj_key",
                   "competence.crew_plan.emp_key", "competence.crew_plan.planned_start", "competence.crew_plan.planned_end", "competence.crew_plan.percent"),
          oracle="py:halvaro_gen/world/competence/requirements.py::build_crew_plan")
def project_crew(allocation: pd.DataFrame, crew_plan: pd.DataFrame, prj_key: str, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the people on a project on a date: the allocations that cover the date, or the crew plan when the project has no allocation yet.

    Rule: allocations that cover the date (an empty end is open). When the project has no allocation row at all, the crew plan rows that cover the date are used; a project with allocations that none cover the date has an empty crew. One row per person, the larger percent when a person has several.

    Args:
        allocation: Allocation frame (hr.allocation) with emp_key, prj_key, start, end and percent.
        crew_plan: Crew plan frame (competence.crew_plan) with prj_key, emp_key, planned_start, planned_end and percent.
        prj_key: The project.
        as_of: The date.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame with emp_key, percent and source (allocation or crew_plan).

    Raises:
        FrameError: a frame lacks a column or an allocation of the project has no start.
        PeriodError: as_of is not a valid date.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import project_crew
        >>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "prj_key": ["PRJ-1", "PRJ-1"], "start": ["2026-01-01", "2026-01-01"], "end": ["2026-06-30", None], "percent": [100, 50]})
        >>> plan = pd.DataFrame({"prj_key": ["PRJ-2"], "emp_key": ["EMP-000003"], "planned_start": ["2026-01-01"], "planned_end": [None], "percent": [100]})
        >>> project_crew(allocation, plan, "PRJ-1", dt.date(2026, 3, 1))[["emp_key", "percent", "source"]].to_dict("records")
        [{'emp_key': 'EMP-000001', 'percent': 100, 'source': 'allocation'}, {'emp_key': 'EMP-000002', 'percent': 50, 'source': 'allocation'}]
        >>> project_crew(allocation, plan, "PRJ-2", dt.date(2026, 3, 1))["source"].tolist()
        ['crew_plan']
    """
    _need(allocation, ["emp_key", "prj_key", "start", "end", "percent"], "hr.allocation")
    _need(crew_plan, ["prj_key", "emp_key", "planned_start", "planned_end", "percent"], "competence.crew_plan")
    d = _day(as_of)
    a = _days(allocation[allocation["prj_key"] == prj_key][["emp_key", "start", "end", "percent"]], ["start", "end"], "hr.allocation")
    if a["start"].isna().any():
        raise FrameError(f"hr.allocation has {int(a['start'].isna().sum())} row(s) of {prj_key} with a null start (for example {a.loc[a['start'].isna(), 'emp_key'].iloc[0]})")
    if len(a):
        out = a[(a["start"] <= d) & (a["end"].isna() | (a["end"] >= d))].assign(source="allocation")[["emp_key", "percent", "source"]]
    else:
        c = _days(crew_plan[crew_plan["prj_key"] == prj_key][["emp_key", "planned_start", "planned_end", "percent"]], ["planned_start", "planned_end"], "competence.crew_plan")
        out = c[(c["planned_start"] <= d) & (c["planned_end"].isna() | (c["planned_end"] >= d))].assign(source="crew_plan")[["emp_key", "percent", "source"]]
    out = out.sort_values(["emp_key", "percent"], ascending=[True, False]).drop_duplicates("emp_key")
    return out.reset_index(drop=True)


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::_projects")
def cert_intervals(cert: pd.DataFrame) -> dict[tuple[str, str], list[tuple[Any, Any]]]:
    """Use this when you check coverage for many projects and want to build the validity intervals of the certificates once.

    Rule: every certificate is an interval from issued to expires (an empty expires is open); the intervals of one person and qualification are listed together. Pass the result to coverage_gap(..., intervals=...) to avoid building it again.

    Args:
        cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        dict: {(emp_key, qual_key): [(issued, expires), ...]} with NaT for an open end.

    Raises:
        FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import cert_intervals
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "issued": ["2024-01-01"], "expires": [None]})
        >>> intervals = cert_intervals(cert)
        >>> list(intervals), len(intervals[("EMP-000001", "QUAL-01")])
        ([('EMP-000001', 'QUAL-01')], 1)
    """
    c = _certs(cert)
    return {cast("tuple[str, str]", k): list(zip(g["issued"], g["expires"])) for k, g in c.groupby(["emp_key", "qual_key"])}


_intervals = cert_intervals


def _valid(iv: dict[tuple[str, str], list[tuple[Any, Any]]], emp: str, q: str, d: pd.Timestamp) -> bool:
    return any(a <= d and (pd.isna(b) or b >= d) for a, b in iv.get((emp, q), []))


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires",
                   "competence.requirement.qual_key", "competence.requirement.min_headcount", "hr.leave_record.emp_key", "hr.leave_record.start", "hr.leave_record.end"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::_projects")
def coverage_gap(requirements: pd.DataFrame, crew: pd.DataFrame, cert: pd.DataFrame, booked: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, *,
                 leave_types: Sequence[str] | None = None, intervals: dict[tuple[str, str], list[tuple[Any, Any]]] | None = None) -> pd.DataFrame:
    """Use this when you need, for each requirement of a minimum head count, how many people of a crew hold a valid certificate and are not on leave on a date, and when the gap closes.

    Rule: per requirement row with a min_headcount the frame has required, crew_with_cert (valid on record on the date), available (and not on leave on the date), available_incl_booked (a booking covers from its course date, so a course on or before the date counts), gap_on_record and gap_incl_booked (required minus available, at least 0), gap_closes_on (the first date from the given date on when the head count is met counting booked renewals and the end of each leave; empty if never), first_expiry and first_expiry_emp (the earliest expiry among the certificates of crew members that overlap the date; this can belong to a certificate that was renewed since, which is the generator truth kept for parity), first_expiry_renewed_aware and first_expiry_renewed_aware_emp (the earliest expiry after taking, per person and qualification, the latest expiry among the certificates valid on the date; a person with an open certificate never expires and is left out), and the emp_key lists on_leave, without_cert and booked_for_crew. leave_types None counts every leave record as leave, a one day holiday included (the generator rule; org.status_on counts long leave only): pass the unavailable types to count those only. Leave comes from hr.leave_record only.

    Args:
        requirements: Requirement rows with scope_type, scope_key, qual_key and min_headcount.
        crew: Crew frame with emp_key.
        cert: Certification frame (competence.certification_held).
        booked: The output of booked_renewals (emp_key, qual_key, course_date).
        leave_record: Leave frame (hr.leave_record) with emp_key, leave_type, start and end.
        as_of: The date.
        leave_types: Leave types that count as leave, or None for all.
        intervals: The output of cert_intervals(cert), to run it faster in a loop. Optional.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: one row per requirement with a min_headcount, columns as in the rule.

    Raises:
        FrameError: a frame lacks a column, a crew key is null, or min_headcount is not a whole number of zero or more.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import coverage_gap
        >>> requirements = pd.DataFrame({"scope_type": ["project"], "scope_key": ["PRJ-1"], "qual_key": ["QUAL-01"], "min_headcount": [2]})
        >>> crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01", "QUAL-01"], "issued": ["2025-01-01", "2025-01-01"], "expires": ["2027-12-31", "2026-12-31"]})
        >>> booked = pd.DataFrame({"emp_key": pd.Series([], dtype=str), "qual_key": pd.Series([], dtype=str), "course_date": pd.Series([], dtype="datetime64[ns]")})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_type": ["parental"], "start": ["2026-11-01"], "end": ["2027-02-28"]})
        >>> gap = coverage_gap(requirements, crew, cert, booked, leave, dt.date(2026, 11, 30), leave_types=["parental"])
        >>> gap[["required", "crew_with_cert", "available", "gap_on_record", "on_leave"]].to_dict("records")
        [{'required': 2, 'crew_with_cert': 2, 'available': 1, 'gap_on_record': 1, 'on_leave': ['EMP-000001']}]
    """
    _need(requirements, ["scope_type", "scope_key", "qual_key", "min_headcount"], "requirements (from project_requirements)")
    _need(crew, ["emp_key"], "crew (from project_crew)")
    _need(booked, ["emp_key", "qual_key", "course_date"], "booked_renewals output")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    d = _day(as_of)
    if crew["emp_key"].isna().any():
        raise FrameError("the crew frame has a null emp_key")
    hc = requirements["min_headcount"].dropna()
    if not pd.api.types.is_numeric_dtype(requirements["min_headcount"]) or (hc % 1 != 0).any() or (hc < 0).any():
        raise FrameError("min_headcount must be a whole number of people, zero or more")
    iv = cert_intervals(cert) if intervals is None else intervals
    bk = _days(booked[["emp_key", "qual_key", "course_date"]], ["course_date"], "booked_renewals output")
    bmap = {k: sorted(g["course_date"]) for k, g in bk.groupby(["emp_key", "qual_key"])}
    people = sorted(set(crew["emp_key"]))
    lr = _days(leave_record[["emp_key", "leave_type", "start", "end"]], ["start", "end"], "hr.leave_record")
    if leave_types is not None:
        lr = lr[lr["leave_type"].isin([leave_types] if isinstance(leave_types, str) else list(leave_types))]
    lr = lr[lr["emp_key"].isin(people)]
    leave = {e: list(zip(g["start"], g["end"])) for e, g in lr.groupby("emp_key")}

    def on_leave(e: str, day: pd.Timestamp) -> bool:
        return any(a <= day and (pd.isna(b) or b >= day) for a, b in leave.get(e, []))

    def covered(e: str, q: str, day: pd.Timestamp) -> bool:
        return _valid(iv, e, q, day) or any(bd <= day for bd in bmap.get((e, q), []))

    rows = []
    r: Any
    for r in requirements[requirements["min_headcount"].notna()].itertuples():
        q, n = r.qual_key, int(r.min_headcount)
        have = [e for e in people if _valid(iv, e, q, d)]
        avail = [e for e in have if not on_leave(e, d)]
        avail_b = [e for e in people if covered(e, q, d) and not on_leave(e, d)]
        cands = {d}
        for e in people:
            cands |= {bd for bd in bmap.get((e, q), []) if bd >= d}
            cands |= {b + pd.DateOffset(days=1) for a, b in leave.get(e, []) if pd.notna(b) and b >= d}      # the day after every leave that ends on or after the date, also chained leave
        closes = next((c for c in sorted(cands) if sum(1 for e in people if covered(e, q, c) and not on_leave(e, c)) >= n), pd.NaT)
        exp = sorted((b, e) for e in people for a, b in iv.get((e, q), []) if a <= d and not pd.isna(b) and b >= d)
        ra = sorted((max(b for a, b in iv.get((e, q), []) if a <= d and (not pd.isna(b)) and b >= d), e) for e in people
                    if not any(a <= d and pd.isna(b) for a, b in iv.get((e, q), [])) and any(a <= d and not pd.isna(b) and b >= d for a, b in iv.get((e, q), [])))
        rows.append({"scope_type": r.scope_type, "scope_key": r.scope_key, "qual_key": q, "as_of": d, "required": n, "crew_with_cert": len(have), "available": len(avail),
                     "available_incl_booked": len(avail_b), "gap_on_record": max(0, n - len(avail)), "gap_incl_booked": max(0, n - len(avail_b)), "gap_closes_on": closes,
                     "first_expiry": exp[0][0] if exp else pd.NaT, "first_expiry_emp": exp[0][1] if exp else None,
                     "first_expiry_renewed_aware": ra[0][0] if ra else pd.NaT, "first_expiry_renewed_aware_emp": ra[0][1] if ra else None, "on_leave": sorted(set(have) - set(avail)),
                     "without_cert": [e for e in people if e not in have], "booked_for_crew": [e for e in people if e not in have and bmap.get((e, q))]})
    cols = ["scope_type", "scope_key", "qual_key", "as_of", "required", "crew_with_cert", "available", "available_incl_booked", "gap_on_record", "gap_incl_booked", "gap_closes_on",
            "first_expiry", "first_expiry_emp", "first_expiry_renewed_aware", "first_expiry_renewed_aware_emp", "on_leave", "without_cert", "booked_for_crew"]
    return pd.DataFrame(rows, columns=cols)


@staged(sources=("competence.skill_rating.level", "competence.qualification.prerequisite_qual_key", "competence.qualification.country_scope", "competence.training_event.date",
                   "competence.training_event.capacity", "competence.training_event.seats_taken", "competence.crew_plan.percent", "hr.leave_record.start", "hr.leave_record.end"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::_candidates", facts=("policy.certificates.candidate_leave_days", "policy.certificates.candidate_list_level", "policy.certificates.candidate_plausible_level", "policy.certificates.candidate_seat_days", "policy.staffing.unavailable_leave_types"))
def cover_candidates(skill_latest: pd.DataFrame, org: pd.DataFrame, cert: pd.DataFrame, qualification: pd.DataFrame, event: pd.DataFrame, crew_plan: pd.DataFrame,
                     leave_record: pd.DataFrame, *, qual_key: str, skl_key: str, prj_key: str, crew: Sequence[str] | str | pd.DataFrame, country: str, start: dt.date, now: dt.date,
                     list_level: int | PolicyDefault = _LIST_LEVEL, plausible_level: int | PolicyDefault = _PLAUSIBLE_LEVEL, leave_days: int | PolicyDefault = _LEAVE_DAYS,
                     seat_days: int | PolicyDefault = _SEAT_DAYS, leave_types: Sequence[str] | str | PolicyDefault = _LONG_LEAVE) -> pd.DataFrame:
    """Use this when you need the people who could cover a qualification on a project that starts on a given day, with the reasons that make a candidate less plausible.

    Rule: a candidate is active in org (output of org_on on `now`), not in the crew, without a valid certificate of the qualification on the start day (issued to expires inclusive), and has a latest rating of skill skl_key (output of skill_latest) of list_level or more. `plausible` is true when no reason applies. Reasons: skill_level_below_<plausible_level>; country_scope_mismatch (the qualification is scoped to DK or DE and the person's country differs) or other_country (otherwise, the person is not in the project country); prerequisite_missing (the prerequisite qualification is not valid on the start day); long_leave (a leave of an unavailable type that starts no later than leave_days after the start day and does not end before it); planned_on_other_project (the crew plan has 100 percent or more on another project; the dates of the plan rows are not read); no_seat_before_start_plus_<seat_days>d (no course of the qualification after `now`, up to the start day plus seat_days, with a free seat in the person's country). The four numbers default to the facts policy.certificates.candidate_list_level, candidate_plausible_level, candidate_leave_days and candidate_seat_days, and the leave types to policy.staffing.unavailable_leave_types (all status proposed; the frame then carries attrs["policy_status"]). Sorted plausible first, then skill level (high first), then emp_key.

    Args:
        skill_latest: Output of skill_latest with emp_key, skl_key and level, one row per person and skill.
        org: Output of org_on with emp_key, active, country, role_name and legal_entity_key, one row per person.
        cert: Certificate frame (competence.certification_held) with emp_key, qual_key, issued and expires.
        qualification: Qualifications (competence.qualification) with qual_key, prerequisite_qual_key and country_scope; qual_key must appear exactly once.
        event: Training events (competence.training_event) with event_no, qual_key, date, capacity, seats_taken and country.
        crew_plan: Crew plan rows (competence.crew_plan) with prj_key, emp_key and percent.
        leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
        qual_key: The qualification to cover.
        skl_key: The skill whose latest rating ranks the candidates.
        prj_key: The project; its crew plan rows do not count as planned elsewhere.
        crew: The people already on the project: a list of emp_key, one emp_key, or the project_crew frame with an emp_key column.
        country: The project country.
        start: The project start day.
        now: The data date; courses must start after it.
        list_level: The lowest skill level that is listed (default the fact policy, proposed).
        plausible_level: The lowest skill level that is plausible (default the fact policy, proposed).
        leave_days: How many days after the start a leave still counts as long leave (default the fact policy, proposed).
        seat_days: How many days after the start a course seat still counts (default the fact policy, proposed).
        leave_types: The leave types that count as long leave (a list or one type; default the fact policy, proposed).
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame with emp_key, role_name, legal_entity_key, skill_level, plausible, reasons (a list of the reason texts), next_seat_event and next_seat_date (the first course with a free seat in the person's country, empty when none).

    Raises:
        FrameError: a frame lacks a column, qualification does not hold qual_key exactly once, org or skill_latest has more than one row for a key, a skill level is null or not a number, the percent of the crew plan is not a number, list_level, plausible_level, leave_days or seat_days is not a number (for example text), leave_types is not a leave type name or a list of them (None, a number), crew is not a list of emp_key, one emp_key or a frame (None, a number), a policy default is not a whole number or lists no leave type, or a date column is not a date.
        PeriodError: start or now is not a date without a time zone.
        FactNotFound: a default is used and its fact is not in the snapshot.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import cover_candidates
        >>> keys = ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"]
        >>> skill = pd.DataFrame({"emp_key": keys, "skl_key": ["SKL-01"] * 4, "level": [3, 2, 3, 3]})
        >>> org = pd.DataFrame({"emp_key": keys, "active": [True] * 4, "country": ["DK"] * 4, "role_name": ["technician"] * 4, "legal_entity_key": ["LE-01"] * 4})
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000004"], "qual_key": ["QUAL-01"], "issued": ["2025-01-01"], "expires": ["2027-12-31"]})
        >>> qualification = pd.DataFrame({"qual_key": ["QUAL-01"], "prerequisite_qual_key": [None], "country_scope": [None]})
        >>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-08-15"], "capacity": [10], "seats_taken": [4], "country": ["DK"]})
        >>> plan = pd.DataFrame({"prj_key": ["PRJ-002"], "emp_key": ["EMP-000002"], "percent": [50]})
        >>> leave = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
        >>> out = cover_candidates(skill, org, cert, qualification, event, plan, leave, qual_key="QUAL-01", skl_key="SKL-01", prj_key="PRJ-001", crew=["EMP-000003"], country="DK",
        ...                        start=dt.date(2026, 9, 1), now=dt.date(2026, 6, 30), list_level=2, plausible_level=3, leave_days=90, seat_days=60, leave_types=["extended_leave"])
        >>> out[["emp_key", "skill_level", "plausible", "reasons", "next_seat_event"]].to_dict("records")
        [{'emp_key': 'EMP-000001', 'skill_level': 3, 'plausible': True, 'reasons': [], 'next_seat_event': 7}, {'emp_key': 'EMP-000002', 'skill_level': 2, 'plausible': False, 'reasons': ['skill_level_below_3'], 'next_seat_event': 7}]
    
    """
    _need(skill_latest, ["emp_key", "skl_key", "level"], "skill_latest output")
    _need(org, ["emp_key", "active", "country", "role_name", "legal_entity_key"], "org_on output")
    _need(qualification, ["qual_key", "prerequisite_qual_key", "country_scope"], "competence.qualification")
    _need(event, ["event_no", "qual_key", "date", "capacity", "seats_taken", "country"], "competence.training_event")
    _need(crew_plan, ["prj_key", "emp_key", "percent"], "competence.crew_plan")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    used: dict[str, Any] = {}
    list_level, plausible_level = cast(int, policy_number(list_level, used, integer=True)), cast(int, policy_number(plausible_level, used, integer=True))
    leave_days, seat_days = cast(int, policy_number(leave_days, used, integer=True)), cast(int, policy_number(seat_days, used, integer=True))
    for arg, number in (("list_level", list_level), ("plausible_level", plausible_level), ("leave_days", leave_days), ("seat_days", seat_days)):
        if not isinstance(number, (int, float, np.number)):
            raise FrameError(f"{arg} must be a number, not {number!r}")
    leave_types_given(leave_types, "leave_types")
    if not isinstance(crew, (str, pd.DataFrame, Iterable)):
        raise FrameError(f"crew must be a list of emp_key, one emp_key or the project_crew frame, not {crew!r}")
    if isinstance(leave_types, PolicyDefault):
        used[leave_types.fact_id] = fact(leave_types.fact_id).status
    q = qualification[qualification["qual_key"] == qual_key]
    if len(q) != 1:
        raise FrameError(f"qualification {qual_key} is not in competence.qualification exactly once")
    pre, scope = q["prerequisite_qual_key"].iloc[0], q["country_scope"].iloc[0]
    s, n = _day(start), _day(now)
    iv = _intervals(cert)
    last = skill_latest[skill_latest["skl_key"] == skl_key].set_index("emp_key")["level"]
    if isinstance(crew, pd.DataFrame):
        _need(crew, ["emp_key"], "crew (from project_crew)")
        crew = crew["emp_key"].tolist()
    crew_set = set([crew] if isinstance(crew, str) else crew)
    if org["emp_key"].duplicated().any():
        raise FrameError("the org frame has more than one row for a person; pass the output of org_on")
    if skill_latest.duplicated(["emp_key", "skl_key"]).any():
        raise FrameError("the skill frame has more than one row for a person and skill; pass the output of skill_latest")
    if skill_latest["level"].isna().any():
        raise FrameError("the skill frame has a null level")
    for value in last:
        try:
            int(value)
        except (TypeError, ValueError, OverflowError):
            raise FrameError(f"the skill frame has a level that is not a number: {value!r}") from None
    try:
        elsewhere = set(crew_plan[(crew_plan["prj_key"] != prj_key) & (crew_plan["percent"] >= 100)]["emp_key"])
    except TypeError:
        raise FrameError("competence.crew_plan.percent must be numbers") from None
    ev = _days(event[["event_no", "qual_key", "date", "capacity", "seats_taken", "country"]], ["date"], "competence.training_event")
    seats = ev[(ev["qual_key"] == qual_key) & (ev["date"] > n) & (ev["date"] <= s + pd.DateOffset(days=seat_days)) & (ev["capacity"] - ev["seats_taken"] > 0)].sort_values(["date", "event_no"])
    lr = _days(leave_record[leave_record["leave_type"].isin(unavailable_types(leave_types))][["emp_key", "start", "end"]], ["start", "end"], "hr.leave_record")
    horizon = s + pd.DateOffset(days=leave_days)
    long_leave = set(lr[(lr["start"] <= horizon) & (lr["end"].isna() | (lr["end"] >= s))]["emp_key"])
    people = org[org["active"].astype(bool)].set_index("emp_key")
    rows = []
    emp: Any
    level: Any
    for emp, level in last.items():
        if emp not in people.index or emp in crew_set or int(level) < list_level or _valid(iv, emp, qual_key, s):
            continue
        ctry = people.loc[emp, "country"]
        reasons = []
        if int(level) < plausible_level:
            reasons.append(f"skill_level_below_{plausible_level}")
        if scope in ("DK", "DE") and ctry != scope:
            reasons.append("country_scope_mismatch")
        elif ctry != country:
            reasons.append("other_country")
        if isinstance(pre, str) and not _valid(iv, emp, pre, s):
            reasons.append("prerequisite_missing")
        if emp in long_leave:
            reasons.append("long_leave")
        if emp in elsewhere:
            reasons.append("planned_on_other_project")
        seat = seats[seats["country"] == ctry]
        if not len(seat):
            reasons.append(f"no_seat_before_start_plus_{seat_days}d")
        rows.append({"emp_key": emp, "role_name": people.loc[emp, "role_name"], "legal_entity_key": people.loc[emp, "legal_entity_key"], "skill_level": int(level),
                     "plausible": not reasons, "reasons": reasons, "next_seat_event": int(seat.iloc[0]["event_no"]) if len(seat) else None,
                     "next_seat_date": seat.iloc[0]["date"] if len(seat) else pd.NaT})
    cols = ["emp_key", "role_name", "legal_entity_key", "skill_level", "plausible", "reasons", "next_seat_event", "next_seat_date"]
    out = pd.DataFrame(rows, columns=cols)
    out = out.assign(_p=~out["plausible"].astype(bool), _l=-out["skill_level"]).sort_values(["_p", "_l", "emp_key"]).drop(columns=["_p", "_l"]).reset_index(drop=True)
    if used:
        out.attrs["policy_status"] = used
    return out
