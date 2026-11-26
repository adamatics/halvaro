"""Staffing: daily allocation load, handover around a long leave, experience from the project roster, ranked staffing candidates and plan hours against booked hours (plan 5.5).

Allocation is a plan, not hours worked (DA.REF.211). The roster frame comes from halvaro-delivery (soft dependency): hr ranks people and keeps no copy of the roster rule.
PROPOSED values are keyword parameters with the plan's recommended default: policy.staffing.max_allocation_percent, policy.staffing.unavailable_leave_types, policy.staffing.experience_ranking.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact
from halvaro.core.registry import function

from ._guard import staged
from .certs import _day, _days
from .org import UNAVAILABLE_LEAVE_TYPES, PolicyDefault, _need, policy_number, unavailable_types

LEAD_ROLES = ("project manager", "lead engineer", "lead designer", "site manager", "foreman")      # PROPOSED, py:halvaro_gen/truth/staffing.py::LEADS (fact needed: world.staffing.lead_roles)
LONG_LEAVE = ("extended_leave", "parental")                                                          # PROPOSED, policy.staffing.unavailable_leave_types
_FAR = pd.Timestamp("2200-01-01")        # an open allocation runs to here
MAX_LOAD_PERCENT = PolicyDefault("policy.staffing.max_allocation_percent")                          # proposed policy fact (100)
LABOUR_COST_CODES = (110, 120, 130, 140, 430, 440, 540, 610, 620, 630)                              # PROPOSED, fact needed: world.staffing.labour_cost_codes


def _plus_days(days: pd.Series, n: int) -> pd.Series:
    """The dates of a Series moved by n days, with an explicit numpy unit (a bare pandas Timedelta triggers a numpy deprecation warning)."""
    return pd.Series((days.to_numpy("datetime64[ns]").astype("datetime64[D]") + np.timedelta64(n, "D")).astype("datetime64[ns]"), index=days.index)


@function(sources=("hr.allocation.emp_key", "hr.allocation.start", "hr.allocation.end", "hr.allocation.percent"), oracle="py:tests/test_staffing.py::test_allocation_capacity", facts=("policy.staffing.max_allocation_percent",))
def allocation_load(allocation: pd.DataFrame, limit: float | PolicyDefault = MAX_LOAD_PERCENT) -> pd.DataFrame:
    """Use this when you need to see how loaded each person is over time: the allocation percents of all projects added up per day, as segments of constant load.

    Rule: the percents of the allocations that cover a day are summed per person; neighbouring days with the same sum form one segment; days with no load are not listed. A load above the limit is flagged. The default limit is the fact policy.staffing.max_allocation_percent (status proposed); the frame then carries attrs["policy_status"]. An allocation with no end is open: its segment has an empty end.

    Args:
        allocation: Allocation frame (hr.allocation) with emp_key, start, end and percent (numbers of zero or more, no nulls).
        limit: The largest accepted load in percent per person per day. Default the fact.

    Returns:
        pandas.DataFrame with emp_key, start, end (included), load and over_limit, sorted by person and start.

    Raises:
        FrameError: limit is not a number, an allocation has no emp_key or start, percent is not numeric and zero or more, an allocation ends before it starts, or an end date is in the year 2200 or later.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import allocation_load
        >>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "prj_key": ["PRJ-1", "PRJ-2"], "start": ["2026-01-01", "2026-01-01"],
        ...                            "end": ["2026-01-31", "2026-01-15"], "percent": [60, 50]})
        >>> allocation_load(allocation, limit=100)[["start", "end", "load", "over_limit"]].astype(str).values.tolist()
        [['2026-01-01', '2026-01-15', '110.0', 'True'], ['2026-01-16', '2026-01-31', '60.0', 'False']]
    """
    _need(allocation, ["emp_key", "start", "end", "percent"], "hr.allocation")
    used: dict[str, Any] = {}
    limit = policy_number(limit, used)
    if isinstance(limit, bool) or not isinstance(limit, (int, float, np.integer, np.floating)):
        raise FrameError(f"limit must be a number of percent, not {limit!r}")
    if len(allocation):
        if allocation["emp_key"].isna().any():
            raise FrameError("hr.allocation has rows without emp_key")
        pc = allocation["percent"]
        if not pd.api.types.is_numeric_dtype(pc) or pd.api.types.is_bool_dtype(pc) or pc.isna().any() or (pc < 0).any():
            raise FrameError("hr.allocation.percent must be numeric, zero or more, without nulls")
    a = _days(allocation[["emp_key", "start", "end", "percent"]], ["start", "end"], "hr.allocation")
    if a["start"].isna().any():
        raise FrameError("hr.allocation has rows without a start date")
    if (a["end"] < a["start"]).any():
        raise FrameError(f"{int((a['end'] < a['start']).sum())} allocations end before they start")
    if (a["end"] >= _FAR).any():
        raise FrameError("hr.allocation has an end date in the year 2200 or later")
    ev = pd.concat([pd.DataFrame({"emp_key": a["emp_key"], "day": a["start"], "delta": a["percent"].astype(float)}),
                    pd.DataFrame({"emp_key": a["emp_key"], "day": _plus_days(a["end"].fillna(_FAR), 1), "delta": -a["percent"].astype(float)})])
    ev = cast(pd.DataFrame, ev.groupby(["emp_key", "day"], as_index=False)["delta"].sum()).sort_values(["emp_key", "day"])
    ev["load"] = ev.groupby("emp_key")["delta"].cumsum().round(9)
    ev["next_day"] = ev.groupby("emp_key")["day"].shift(-1)
    seg = ev[(ev["load"] > 0) & ev["next_day"].notna()].copy()
    seg["end"] = _plus_days(seg["next_day"], -1)
    seg.loc[seg["end"] >= _FAR, "end"] = pd.NaT
    out = seg.rename(columns={"day": "start"})[["emp_key", "start", "end", "load"]].reset_index(drop=True)
    if len(out):          # merge neighbours with the same load (a stint that ends where another of the same size starts)
        prev_end = _plus_days(out["end"].fillna(_FAR), 1).groupby(out["emp_key"]).shift(1)
        new = ~((out["start"] == prev_end) & (out["load"] == out["load"].groupby(out["emp_key"]).shift(1))) | out["end"].isna().shift(1, fill_value=False)
        last = new.shift(-1, fill_value=True)          # the last segment of a run; an open segment is always the last of its person
        out = out[new].reset_index(drop=True).assign(end=out.loc[last, "end"].to_numpy())[["emp_key", "start", "end", "load"]]
    out["over_limit"] = out["load"] > limit
    if used:
        out.attrs["policy_status"] = used
    return out


@function(sources=("hr.allocation.emp_key", "hr.allocation.prj_key", "hr.allocation.start", "hr.allocation.end", "hr.allocation.percent", "hr.leave_record.emp_key", "hr.leave_record.leave_type",
                   "hr.leave_record.start", "hr.leave_record.end"), facts=("policy.staffing.unavailable_leave_types",))
def handover_report(allocation: pd.DataFrame, leave_record: pd.DataFrame, *, leave_types: Sequence[str] | str | PolicyDefault = UNAVAILABLE_LEAVE_TYPES, lookback_days: int = 7, replacement_days: int = 7,
                    crew_plan: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need, around each long leave, the allocations that ended or still run at its start, the people who replace the absent person on the project, and where the person returns.

    Rule: long leaves are the rows of leave_types (default the fact policy.staffing.unavailable_leave_types, status proposed; the frame then carries attrs["policy_status"]); duplicate leave rows are reported once. Per person and leave the kinds are: ends_before_leave (own allocations that end in the lookback_days before the leave starts); overlaps_leave (own allocations running on the leave start day: they end on or after it or are open); replacement (allocations of other people on the projects where the person has an ends_before_leave or overlaps_leave allocation, and only those projects, that start from the leave start to replacement_days later, so the first working day after a weekend leave start is covered); planned_return (per project the first own allocation that starts after the leave ended and before the person's next long leave; none while the leave has no end). Lookback and replacement days default to 7 (proposed).
    crew_plan (optional, not a registered source, so the function stays day 1): its rows of the person that start after the leave ended (and before the next long leave) are planned_return candidates too, with start and end from planned_start and planned_end (a null planned_end is open); per project the earliest start wins and an allocation wins a tie. Plan rows that start inside the leave (from the leave start to the leave end, both inclusive; any day from the start when the leave has no end) are reported as plan_during_leave, last per leave: the plan seats a person who is on leave, a conflict hr.allocation cannot show. Without crew_plan there are no plan_during_leave rows and no source column.

    Args:
        allocation: Allocation rows (hr.allocation) with emp_key, prj_key, start, end and percent; an empty end is open.
        leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
        leave_types: The leave types that count as long leave (a list or one type).
        lookback_days: How many days before the leave start an ending allocation still counts (proposed 7).
        replacement_days: How many days after the leave start a replacing allocation may start (proposed 7).
        crew_plan: Optional crew plan (competence.crew_plan) with emp_key, prj_key, planned_start, planned_end and percent; None leaves it out.

    Returns:
        pandas.DataFrame with leave_emp_key, leave_type, leave_start, leave_end, kind, prj_key, emp_key, percent, start and end (and source, allocation or crew_plan, when crew_plan is given), ordered by leave, kind (in the order above), project, start and emp_key.

    Raises:
        FrameError: a frame lacks a column, lookback_days or replacement_days is not a whole number of zero or more, leave_types is None or the default lists no type, a long leave has no start or ends before it starts, an allocation or plan row has no start, ends before it starts or is a duplicate (a repeated alc_key, or all columns identical), or a date column is not a date.
        FactNotFound: the default leave types are used and the fact is not in the snapshot.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import handover_report
        >>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000001"], "prj_key": ["PRJ-001", "PRJ-001", "PRJ-002"],
        ...                            "start": ["2026-01-01", "2026-03-03", "2026-05-04"], "end": [None, None, None], "percent": [100, 100, 100]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_type": ["extended_leave"], "start": ["2026-03-02"], "end": ["2026-04-30"]})
        >>> out = handover_report(allocation, leave, leave_types=["extended_leave"])
        >>> out[["leave_emp_key", "kind", "prj_key", "emp_key"]].to_dict("records")
        [{'leave_emp_key': 'EMP-000001', 'kind': 'overlaps_leave', 'prj_key': 'PRJ-001', 'emp_key': 'EMP-000001'}, {'leave_emp_key': 'EMP-000001', 'kind': 'replacement', 'prj_key': 'PRJ-001', 'emp_key': 'EMP-000002'}, {'leave_emp_key': 'EMP-000001', 'kind': 'planned_return', 'prj_key': 'PRJ-002', 'emp_key': 'EMP-000001'}]
    
    """
    _need(allocation, ["emp_key", "prj_key", "start", "end", "percent"], "hr.allocation")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    for name, v in (("lookback_days", lookback_days), ("replacement_days", replacement_days)):
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0:
            raise FrameError(f"{name} must be a whole number of days, zero or more, not {v!r}")
    if leave_types is None:
        raise FrameError("leave_types is a leave type or a list of them")
    types = unavailable_types(leave_types)
    used = {leave_types.fact_id: fact(leave_types.fact_id).status} if isinstance(leave_types, PolicyDefault) else {}
    lv = _days(leave_record[leave_record["leave_type"].isin(types)][["emp_key", "leave_type", "start", "end"]], ["start", "end"], "hr.leave_record").drop_duplicates()
    if lv["start"].isna().any():
        raise FrameError("hr.leave_record has long leave rows without a start date")
    if (lv["end"] < lv["start"]).any():
        raise FrameError(f"{int((lv['end'] < lv['start']).sum())} leave records end before they start")
    al = _days(allocation[["emp_key", "prj_key", "start", "end", "percent"]], ["start", "end"], "hr.allocation")
    if al["start"].isna().any():
        raise FrameError(f"{int(al['start'].isna().sum())} allocations have no start date")
    if (al["end"] < al["start"]).any():
        raise FrameError(f"{int((al['end'] < al['start']).sum())} allocations end before they start")
    if al.duplicated().any() or ("alc_key" in allocation.columns and allocation["alc_key"].duplicated().any()):
        raise FrameError(f"hr.allocation has {int(al.duplicated().sum())} duplicate rows (identical rows or a repeated alc_key); a repeated row would be reported twice")
    al["source"] = "allocation"
    plan = None
    if crew_plan is not None:
        _need(crew_plan, ["emp_key", "prj_key", "planned_start", "planned_end", "percent"], "competence.crew_plan")
        plan = _days(crew_plan[["emp_key", "prj_key", "planned_start", "planned_end", "percent"]], ["planned_start", "planned_end"], "competence.crew_plan")
        if plan["planned_start"].isna().any():
            raise FrameError(f"{int(plan['planned_start'].isna().sum())} crew plan rows have no planned_start")
        if (plan["planned_end"] < plan["planned_start"]).any():
            raise FrameError(f"{int((plan['planned_end'] < plan['planned_start']).sum())} crew plan rows end before they start")
        if plan.duplicated().any():
            raise FrameError(f"competence.crew_plan has {int(plan.duplicated().sum())} duplicate rows; a repeated row would be reported twice")
        plan = plan.rename(columns={"planned_start": "start", "planned_end": "end"})
        plan["source"] = "crew_plan"
    lv = lv.sort_values(["emp_key", "start", "leave_type"]).reset_index(drop=True)
    lv["_next"] = lv.groupby("emp_key")["start"].shift(-1)
    lv = lv.rename(columns={"emp_key": "leave_emp_key", "start": "leave_start", "end": "leave_end"})
    lv["_l"] = np.arange(len(lv))
    head = ["_l", "leave_emp_key", "leave_type", "leave_start", "leave_end"]
    cols = ["leave_emp_key", "leave_type", "leave_start", "leave_end", "kind", "prj_key", "emp_key", "percent", "start", "end"]
    own = lv.merge(al, left_on="leave_emp_key", right_on="emp_key", how="inner")
    before = own[(own["end"] >= _plus_days(own["leave_start"], -lookback_days)) & (own["end"] < own["leave_start"])]
    over = own[(own["start"] <= own["leave_start"]) & (own["end"].isna() | (own["end"] >= own["leave_start"]))]
    cand = pd.concat([before[["_l", "prj_key"]], over[["_l", "prj_key"]]]).drop_duplicates()
    cand = cand[cand["prj_key"].notna()].merge(lv[head], on="_l").merge(al, on="prj_key")
    rep = cand[(cand["emp_key"] != cand["leave_emp_key"]) & (cand["start"] >= cand["leave_start"]) & (cand["start"] <= _plus_days(cand["leave_start"], replacement_days))]
    pools = [own] if plan is None else [own, lv.merge(plan, left_on="leave_emp_key", right_on="emp_key", how="inner")]
    back = pd.concat([p[p["leave_end"].notna() & (p["start"] > p["leave_end"]) & (p["_next"].isna() | (p["start"] < p["_next"]))] for p in pools])
    back = back.sort_values(["_l", "start"], kind="stable").drop_duplicates(["_l", "prj_key"], keep="first")
    kinds = [("ends_before_leave", before), ("overlaps_leave", over), ("replacement", rep), ("planned_return", back)]
    if plan is not None:
        pl = pools[1]
        kinds.append(("plan_during_leave", pl[(pl["start"] >= pl["leave_start"]) & (pl["leave_end"].isna() | (pl["start"] <= pl["leave_end"]))]))
    parts = [f.assign(kind=k, _k=i) for i, (k, f) in enumerate(kinds)]
    shown = cols + (["source"] if plan is not None else [])
    parts = [p[head + ["kind", "_k", "prj_key", "emp_key", "percent", "start", "end", "source"]] for p in parts if len(p)]
    if not parts:
        out = pd.DataFrame(columns=shown)
    else:
        out = pd.concat(parts).sort_values(["_l", "_k", "prj_key", "start", "emp_key"], kind="stable").reset_index(drop=True)[shown]
    if used:
        out.attrs["policy_status"] = used
    return out


@staged(sources=("projects.project_role.emp_key", "projects.project_role.prj_key", "projects.project_role.project_role", "projects.project_role.hours_total", "projects.project_role.basis",
                   "hr.employee.leave_date"), oracle="py:halvaro_gen/truth/staffing.py::staffing_truth")
def experience_summary(roster: pd.DataFrame, employee: pd.DataFrame | None = None, *, lead_roles: Sequence[str] = LEAD_ROLES, as_of: dt.date | str | pd.Timestamp | None = None) -> pd.DataFrame:
    """Use this when you need the hours, projects, roles and lead flag of each person over a roster, ranked by hours.

    Rule: hours are the total over both bases (time_entries and roster) as the generator truth sums them, kept apart in hours_time_entries and hours_roster (legacy roster hours are estimates). Ranked by hours, high first, then emp_key (hours equal to six decimals tie); the lead roles are proposed. With as_of a leaver is a person whose leave_date is before it, strictly: on the leave date itself the person is still there. Without as_of a leaver is any person with a leave date, also a future one, so a staffing decision must use the date specific status of org.status_on and never this flag. A person missing from the employee frame has leaver false and no leave date.

    Args:
        roster: Roster frame with prj_key, emp_key, project_role, hours_total and basis (time_entries or roster), and optional legacy.
        employee: Optional employee frame (hr.employee) with emp_key and leave_date; adds leave_date and leaver.
        lead_roles: Project roles that make a person a lead. Default LEAD_ROLES (proposed).
        as_of: Optional date for the leaver flag.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: rank, emp_key, hours, hours_time_entries, hours_roster, n_projects, projects, roles, lead_roles, is_lead, legacy_projects (when the roster has legacy), and leave_date and leaver (with an employee frame).

    Raises:
        FrameError: a column is missing, hours_total is not numeric or has nulls, a key or role is null, basis is neither time_entries nor roster, legacy is not True or False, or employee has duplicate emp_key values.
        StageRefusal: a context is given and its stage does not hold the projects source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import experience_summary
        >>> roster = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-1"], "emp_key": ["EMP-000001", "EMP-000001", "EMP-000002"],
        ...                        "project_role": ["project manager", "electrician", "electrician"],
        ...                        "hours_total": [100.0, 50.0, 80.0], "basis": ["time_entries", "roster", "time_entries"]})
        >>> experience_summary(roster)[["rank", "emp_key", "hours", "n_projects", "is_lead"]].to_dict("records")
        [{'rank': 1, 'emp_key': 'EMP-000001', 'hours': 150.0, 'n_projects': 2, 'is_lead': True}, {'rank': 2, 'emp_key': 'EMP-000002', 'hours': 80.0, 'n_projects': 1, 'is_lead': False}]
    """
    _need(roster, ["prj_key", "emp_key", "project_role", "hours_total", "basis"], "projects.project_role roster")
    if len(roster):
        if roster["hours_total"].isna().any() or not pd.api.types.is_numeric_dtype(roster["hours_total"]) or pd.api.types.is_bool_dtype(roster["hours_total"]):
            raise FrameError("roster hours_total must be numeric without nulls")
        nulls = [c for c in ("emp_key", "prj_key", "project_role") if roster[c].isna().any()]
        if nulls:
            raise FrameError(f"the roster has rows with a null {', '.join(nulls)}")
        other = sorted(set(roster["basis"].dropna().astype(str)) - {"time_entries", "roster"})
        if roster["basis"].isna().any() or other:
            raise FrameError(f"roster basis must be time_entries or roster, not {other or 'null'}")
        if "legacy" in roster.columns and not pd.api.types.is_bool_dtype(roster["legacy"]) and not roster["legacy"].isin([True, False]).all():
            raise FrameError("roster legacy must be True or False on every row")
    leads = set([lead_roles] if isinstance(lead_roles, str) else lead_roles)
    rows = []
    for emp, g in roster.groupby("emp_key", sort=True):
        row = {"emp_key": emp, "hours": float(g["hours_total"].sum()), "hours_time_entries": float(g.loc[g["basis"] == "time_entries", "hours_total"].sum()),
               "hours_roster": float(g.loc[g["basis"] == "roster", "hours_total"].sum()), "n_projects": int(g["prj_key"].nunique()), "projects": sorted(set(g["prj_key"])),
               "roles": sorted(set(g["project_role"])), "lead_roles": sorted(set(g["project_role"]) & leads)}
        row["is_lead"] = bool(row["lead_roles"])
        if "legacy" in g.columns:
            row["legacy_projects"] = int(g.loc[g["legacy"] == True, "prj_key"].nunique())      # noqa: E712
        rows.append(row)
    cols = ["rank", "emp_key", "hours", "hours_time_entries", "hours_roster", "n_projects", "projects", "roles", "lead_roles", "is_lead"] + (["legacy_projects"] if "legacy" in roster.columns else [])
    if employee is not None:
        cols += ["leave_date", "leaver"]
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=cols)
    out = out.assign(_h=out["hours"].round(6)).sort_values(["_h", "emp_key"], ascending=[False, True]).drop(columns="_h").reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    if employee is not None:
        _need(employee, ["emp_key", "leave_date"], "hr.employee")
        if employee["emp_key"].duplicated().any():
            raise FrameError("hr.employee has duplicate emp_key values; one row per person is required")
        ld = _days(employee[["emp_key", "leave_date"]], ["leave_date"], "hr.employee").set_index("emp_key")["leave_date"]
        out["leave_date"] = out["emp_key"].map(ld)
        out["leaver"] = out["leave_date"].notna() if as_of is None else (out["leave_date"] < _day(as_of)).fillna(False)
    return out


@function(sources=("hr.employee.leave_date", "hr.leave_record.leave_type"), oracle="py:tests/test_staffing.py::test_available_experienced_leads")
def staffing_candidates(experience: pd.DataFrame, status: Mapping[str, pd.DataFrame], *, valid: Mapping[str, pd.DataFrame] | None = None, qual_keys: Sequence[str] = ()) -> pd.DataFrame:
    """Use this when you want the experience ranking with the staffing status of each person on one or more dates.

    Rule: for each label of status the status on that date (available, on_leave, left, not_hired) goes in status_<label> and staffable_<label> is true when it is available. Leavers are shown and never staffable. With valid and qual_keys, certs_<label> is true when the person holds every qualification on that date. The order of the experience frame is kept.

    Args:
        experience: The output of experience_summary.
        status: A mapping of label to the status_on output of that date.
        valid: A mapping of label to the valid_on output of that date. Optional; needs qual_keys.
        qual_keys: The qualifications to check with valid. Default none.

    Returns:
        pandas.DataFrame: the experience frame with status_<label>, staffable_<label> and, when valid is given, certs_<label>. A person missing from a status frame gets a null status and is not staffable.

    Raises:
        FrameError: a status frame has more than one row for a person, or valid is given without qual_keys.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import staffing_candidates
        >>> experience = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "rank": [1, 2], "hours": [100.0, 50.0]})
        >>> status = {"mar": pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "status": ["available", "on_leave"]})}
        >>> staffing_candidates(experience, status)[["emp_key", "status_mar", "staffable_mar"]].values.tolist()
        [['EMP-000001', 'available', True], ['EMP-000002', 'on_leave', False]]
    """
    _need(experience, ["emp_key", "rank"], "experience_summary output")
    out = experience.copy()
    for label, frame in status.items():
        _need(frame, ["emp_key", "status"], f"status_on output for {label}")
        if frame["emp_key"].duplicated().any():
            raise FrameError(f"status frame {label} has more than one row for a person")
        out[f"status_{label}"] = out["emp_key"].map(frame.set_index("emp_key")["status"])
        out[f"staffable_{label}"] = out[f"status_{label}"].eq("available")
    if valid is not None:
        quals = [qual_keys] if isinstance(qual_keys, str) else list(qual_keys)
        if not quals:
            raise FrameError("valid needs qual_keys, the qualifications to check")
        for label, frame in valid.items():
            _need(frame, ["emp_key", "qual_key"], f"valid_on output for {label}")
            held = frame[frame["qual_key"].isin(quals)].groupby("emp_key")["qual_key"].nunique()
            out[f"certs_{label}"] = out["emp_key"].map(held).fillna(0).eq(len(set(quals)))
    return out


@staged(sources=("projects.estimate_version.prj_key", "projects.estimate_version.estimate_version", "projects.estimate_version.type", "projects.estimate_line.cst_key",
                   "projects.estimate_line.quantity", "projects.time_entry.prj_key", "projects.time_entry.hours"), oracle="py:tests/test_staffing.py::test_story_hours_over_plan")
def planned_vs_actual_hours(estimate_version: pd.DataFrame, estimate_line: pd.DataFrame, time_entry: pd.DataFrame, *, version_type: str = "budget",
                            labour_cost_codes: Sequence[int] = LABOUR_COST_CODES) -> pd.DataFrame:
    """Use this when you need the plan hours of each project against the hours booked in time entries.

    Rule: plan hours are the quantity of the lines of the labour cost codes in the estimate version of version_type (default budget), one version per project and type. actual_hours are the booked hours of the project; negative booked hours are kept as corrections. ratio is actual over plan and empty without plan hours. The labour cost codes are proposed (a fact is needed). Bad input raises instead of giving a quiet zero.

    Args:
        estimate_version: Estimate version frame (projects.estimate_version) with prj_key, estimate_version and type.
        estimate_line: Estimate line frame (projects.estimate_line) with prj_key, estimate_version, cst_key (CST-<digits>) and quantity.
        time_entry: Time entry frame (projects.time_entry) with prj_key and hours.
        version_type: The estimate type to read. Default "budget".
        labour_cost_codes: Whole cost code numbers that count as labour. Default LABOUR_COST_CODES (proposed).
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: prj_key, plan_hours, actual_hours and ratio, sorted by prj_key.

    Raises:
        FrameError: a column is missing, a cost key is not CST-<digits>, quantity or hours is not numeric without nulls, no version of version_type exists in a non-empty frame, a project has two versions of that type, a labour line has negative plan hours, a time entry has no prj_key, or labour_cost_codes is not a list of whole numbers.
        StageRefusal: a context is given and its stage does not hold the projects source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import planned_vs_actual_hours
        >>> version = pd.DataFrame({"prj_key": ["PRJ-1"], "estimate_version": [1], "type": ["budget"]})
        >>> line = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "estimate_version": [1, 1], "cst_key": ["CST-110", "CST-500"], "quantity": [100.0, 9.0]})
        >>> entry = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "hours": [60.0, 45.0]})
        >>> planned_vs_actual_hours(version, line, entry).to_dict("records")
        [{'prj_key': 'PRJ-1', 'plan_hours': 100.0, 'actual_hours': 105.0, 'ratio': 1.05}]
    """
    _need(estimate_version, ["prj_key", "estimate_version", "type"], "projects.estimate_version")
    _need(estimate_line, ["prj_key", "estimate_version", "cst_key", "quantity"], "projects.estimate_line")
    _need(time_entry, ["prj_key", "hours"], "projects.time_entry")
    if isinstance(labour_cost_codes, (str, bytes)) or not all(isinstance(c, (int, np.integer)) and not isinstance(c, bool) for c in labour_cost_codes):
        raise FrameError("labour_cost_codes is a list of whole cost code numbers such as 110")
    if len(time_entry) and (not pd.api.types.is_numeric_dtype(time_entry["hours"]) or time_entry["hours"].isna().any()):
        raise FrameError("projects.time_entry.hours must be numeric without nulls")
    if len(estimate_line) and not estimate_line["cst_key"].astype(str).str.fullmatch(r"CST-\d+").all():
        bad = estimate_line.loc[~estimate_line["cst_key"].astype(str).str.fullmatch(r"CST-\d+"), "cst_key"].iloc[0]
        raise FrameError(f"projects.estimate_line.cst_key {bad!r} is not of the form CST-<digits>")
    if len(estimate_version) and len(estimate_line) and estimate_version["estimate_version"].dtype != estimate_line["estimate_version"].dtype:
        raise FrameError("estimate_version differs in type between projects.estimate_version and projects.estimate_line")
    if len(time_entry) and time_entry["prj_key"].isna().any():
        raise FrameError(f"{int(time_entry['prj_key'].isna().sum())} projects.time_entry rows have no prj_key; their hours belong to no project")
    if len(estimate_line) and (not pd.api.types.is_numeric_dtype(estimate_line["quantity"]) or pd.api.types.is_bool_dtype(estimate_line["quantity"]) or estimate_line["quantity"].isna().any()):
        raise FrameError("projects.estimate_line.quantity must be numeric without nulls")
    ev = estimate_version[estimate_version["type"] == version_type]
    if ev.empty and len(estimate_version):
        raise FrameError(f"no estimate version of type {version_type!r} (the data has {sorted(estimate_version['type'].dropna().astype(str).unique())})")
    if ev.duplicated("prj_key").any():
        raise FrameError(f"more than one {version_type} estimate version for a project (for example {ev.loc[ev.duplicated('prj_key'), 'prj_key'].iloc[0]})")
    codes = {int(c) for c in labour_cost_codes}
    ln = estimate_line.merge(ev[["prj_key", "estimate_version"]], on=["prj_key", "estimate_version"], how="inner")
    ln = ln[ln["cst_key"].astype(str).str[4:].astype(int).isin(codes)]
    if (ln["quantity"] < 0).any():
        raise FrameError(f"{int((ln['quantity'] < 0).sum())} labour lines of the {version_type} versions have negative plan hours (for example {ln.loc[ln['quantity'] < 0, 'prj_key'].iloc[0]})")
    plan = cast(pd.DataFrame, ln.groupby("prj_key", as_index=False)["quantity"].sum()).rename(columns={"quantity": "plan_hours"})
    act = cast(pd.DataFrame, time_entry.groupby("prj_key", as_index=False)["hours"].sum()).rename(columns={"hours": "actual_hours"})
    out = plan.merge(act, on="prj_key", how="outer").fillna({"plan_hours": 0.0, "actual_hours": 0.0})
    out["ratio"] = np.where(out["plan_hours"] > 0, out["actual_hours"] / out["plan_hours"].replace(0, np.nan), np.nan)
    return out.sort_values("prj_key").reset_index(drop=True)
