"""History of a project: the first record of a delay, who attended which meeting, which executive was present when, decisions with their impact, minutes references, the roster and a timeline (plan 5.4).

An attendee is resolved by attendee_type: employee rows carry emp_key, external rows carry cnt_key. Only status present counts as attendance (apologies and absences do not).
"""
from __future__ import annotations

from typing import Any, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from ._types import DateLike

_KB = ("DA.REF.103",)
_KIND_ORDER = ("meeting", "decision", "delay_event", "first_diary_delay", "risk", "plan_version")
_O10 = "py:tests/test_project_history.py::test_hamburg_timeline"


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    if frame.columns.duplicated().any():
        raise FrameError(f"{what} has duplicate column names")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys and frame.duplicated(list(keys)).any():
        d = frame[frame.duplicated(list(keys), keep=False)].iloc[0]
        raise FrameError(f"{what} has more than one row for {', '.join(str(d[k]) for k in keys)}; one row per key is required")


def _day(frame: pd.DataFrame, column: str, what: str) -> pd.Series:
    try:
        out = pd.to_datetime(frame[column])
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    return out.dt.normalize()


def _stamp(frame: pd.DataFrame, column: str, what: str) -> pd.Series:
    """The column as full time stamps (the time of day is kept, so the latest/earliest of one day can be told). Numbers are refused (they would read as nanoseconds since 1970), so are time zones and
    text that is not a date; dates with and without a time of day may be mixed in one column."""
    col = frame[column]
    nonnull = col.dropna()
    if len(nonnull) and (pd.api.types.is_numeric_dtype(col) or any(isinstance(v, (bool, int, float, np.number)) for v in nonnull)):
        raise FrameError(f"{what}.{column} holds numbers, not dates")
    try:
        out = pd.to_datetime(col, format="mixed")
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    return out


@staged(sources=("projects.site_diary.prj_key", "projects.site_diary.diary_date", "projects.site_diary.notes", "projects.site_diary.author_emp_key", "projects.site_diary.delay_seq"),
        kb=_KB, oracle=_O10)
def first_record(site_diary: pd.DataFrame, prj_key: str) -> pd.DataFrame:
    """Use this when you need the first site diary row of a project that records a delay, the first record of the first delay event.

    The row is the one with delay_seq 1 (PROPOSED rule, policy.delivery.first_record_rule is needed); the earliest diary_date wins, and the full time stamp decides when several rows share a day. The columns are prj_key, diary_date, notes, author_emp_key, delay_seq. An empty frame (no columns lost) comes back when the project has no such row.

    Args:
        site_diary: The projects.site_diary frame; it needs prj_key, diary_date, notes, author_emp_key and delay_seq.
        prj_key: The key of the project whose first record is wanted.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame of at most one row with the columns prj_key, diary_date, notes, author_emp_key, delay_seq.

    Raises:
        FrameError: site_diary is not a DataFrame, has duplicate column names or lacks a needed column; delay_seq is not numeric; diary_date holds numbers, a time zone or a value that is not a date; a diary row of the project with delay_seq 1 has no diary_date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import first_record
        >>> ctx = Context(stage="month12", role="analyst")
        >>> diary = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "diary_date": ["2026-03-05", "2026-03-02", "2026-03-09"],
        ...                       "notes": ["b", "a", "c"], "author_emp_key": ["EMP-900001"] * 3, "delay_seq": [1, 1, 2]})
        >>> first_record(diary, "PRJ-900001", context=ctx).to_dict("records")
        [{'prj_key': 'PRJ-900001', 'diary_date': '2026-03-02', 'notes': 'a', 'author_emp_key': 'EMP-900001', 'delay_seq': 1}]
        >>> first_record(diary, "PRJ-900002", context=ctx).shape
        (0, 5)
    """
    _need(site_diary, ["prj_key", "diary_date", "notes", "author_emp_key", "delay_seq"], "projects.site_diary")
    if len(site_diary) and not pd.api.types.is_numeric_dtype(site_diary["delay_seq"]):
        raise FrameError("projects.site_diary.delay_seq must be numeric")
    d = site_diary.assign(_d=_stamp(site_diary, "diary_date", "projects.site_diary"))
    hit = d[(d["prj_key"] == prj_key) & (d["delay_seq"] == 1)]
    if hit["_d"].isna().any():
        raise FrameError(f"{int(hit['_d'].isna().sum())} diary rows of {prj_key} with delay_seq 1 have no diary_date")
    hit = hit.sort_values(["_d"], kind="stable")      # the full time stamp decides, then the input order
    return hit.head(1)[["prj_key", "diary_date", "notes", "author_emp_key", "delay_seq"]].reset_index(drop=True)


@staged(sources=("projects.meeting.mtg_key", "projects.meeting.prj_key", "projects.meeting.date", "projects.meeting.meeting_type", "projects.meeting_attendance.mtg_key",
                 "projects.meeting_attendance.attendee_type", "projects.meeting_attendance.emp_key", "projects.meeting_attendance.cnt_key", "projects.meeting_attendance.status",
                 "projects.meeting_attendance.role_in_meeting"), kb=_KB, oracle="py:tests/test_project_history.py::test_attendees_employed_and_not_on_leave")
def attendance(meeting: pd.DataFrame, meeting_attendance: pd.DataFrame, *, employee: pd.DataFrame | None = None, contact: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need one row per attendee of a meeting with the meeting date and project, the resolved person and whether the person was present.

    Each row carries the meeting date and project, the resolved person (person_key: emp_key for an employee, cnt_key for an external), status, present (true only for status present: apologies and absences are not attendance) and role_in_meeting. With an employee frame (hr.employee) `leaver` is true when the person had left before the meeting date; with a contact frame (crm.contact) `inactive_contact` is true when the contact was inactive since a date before the meeting. A row whose attendee_type and key column disagree raises.

    Args:
        meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and meeting_type.
        meeting_attendance: The projects.meeting_attendance frame; it needs mtg_key, attendee_type (employee or external), emp_key, cnt_key, status (present, apology or absent) and role_in_meeting.
        employee: Optional hr.employee frame with emp_key (one row per key) and leave_date; adds the leaver column.
        contact: Optional crm.contact frame with cnt_key (one row per key) and inactive_since; adds the inactive_contact column.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns mtg_key, prj_key, date, meeting_type, person_key, attendee_type, emp_key, cnt_key, status, present, role_in_meeting, then leaver and inactive_contact when the matching frame is given. Sorted by mtg_key and person_key.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; meeting, employee or contact has more than one row for a key; attendee_type or status has an unknown value (or a null status); an attendee does not have exactly one of emp_key and cnt_key matching attendee_type; a person appears twice in one meeting; an attendance row names a meeting that is not in meeting; a date column holds a time zone or a value that is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import attendance
        >>> ctx = Context(stage="month12", role="analyst")
        >>> meeting = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"]})
        >>> att = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "attendee_type": ["employee", "external"], "emp_key": ["EMP-900001", None],
        ...                     "cnt_key": [None, "CNT-900001"], "status": ["present", "apology"], "role_in_meeting": ["chair", "guest"]})
        >>> out = attendance(meeting, att, context=ctx)
        >>> out["person_key"].tolist()
        ['CNT-900001', 'EMP-900001']
        >>> out["present"].tolist()
        [False, True]
    """
    _need(meeting, ["mtg_key", "prj_key", "date", "meeting_type"], "projects.meeting", keys=("mtg_key",))
    _need(meeting_attendance, ["mtg_key", "attendee_type", "emp_key", "cnt_key", "status", "role_in_meeting"], "projects.meeting_attendance")
    a = meeting_attendance[["mtg_key", "attendee_type", "emp_key", "cnt_key", "status", "role_in_meeting"]].copy()
    bad = ~a["attendee_type"].isin(["employee", "external"])
    if bad.any():
        raise FrameError(f"projects.meeting_attendance.attendee_type has unknown value {a.loc[bad, 'attendee_type'].iloc[0]!r}; known: employee, external")
    unknown_status = sorted(set(a["status"].dropna().astype(str)) - {"present", "apology", "absent"})
    if a["status"].isna().any() or unknown_status:
        raise FrameError(f"projects.meeting_attendance.status has unknown value {unknown_status or 'null'}; known: present, apology, absent (only present counts as attendance)")
    emp_row = a["attendee_type"] == "employee"
    if (emp_row & (a["emp_key"].isna() | a["cnt_key"].notna())).any() or (~emp_row & (a["cnt_key"].isna() | a["emp_key"].notna())).any():
        raise FrameError("an attendee must have exactly one of emp_key (employee) and cnt_key (external), matching attendee_type")
    a["person_key"] = np.where(emp_row, a["emp_key"], a["cnt_key"])
    if a.duplicated(["mtg_key", "person_key"]).any():
        d = a[a.duplicated(["mtg_key", "person_key"], keep=False)].iloc[0]
        raise FrameError(f"{d['person_key']} appears more than once in meeting {d['mtg_key']}; one attendance row per person and meeting is required")
    a["present"] = a["status"] == "present"
    m = meeting[["mtg_key", "prj_key", "date", "meeting_type"]].assign(date=_day(meeting, "date", "projects.meeting"))
    out = a.merge(m, on="mtg_key", how="left", validate="many_to_one")
    if out["date"].isna().any():
        raise FrameError(f"{int(out['date'].isna().sum())} attendance rows name a meeting that is not in projects.meeting (for example {out.loc[out['date'].isna(), 'mtg_key'].iloc[0]})")
    if employee is not None:
        _need(employee, ["emp_key", "leave_date"], "hr.employee", keys=("emp_key",))
        left = employee.assign(_l=_day(employee, "leave_date", "hr.employee")).set_index("emp_key")["_l"]
        out["leaver"] = emp_row.to_numpy() & (out["emp_key"].map(left) < out["date"]).to_numpy()
    if contact is not None:
        _need(contact, ["cnt_key", "inactive_since"], "crm.contact", keys=("cnt_key",))
        inact = contact.assign(_i=_day(contact, "inactive_since", "crm.contact")).set_index("cnt_key")["_i"]
        out["inactive_contact"] = (~emp_row).to_numpy() & (out["cnt_key"].map(inact) < out["date"]).to_numpy()
    cols = ["mtg_key", "prj_key", "date", "meeting_type", "person_key", "attendee_type", "emp_key", "cnt_key", "status", "present", "role_in_meeting"] + [c for c in ("leaver", "inactive_contact") if c in out.columns]
    return out[cols].sort_values(["mtg_key", "person_key"]).reset_index(drop=True)


@staged(sources=("projects.meeting_attendance.status", "projects.meeting_attendance.emp_key", "projects.meeting.date"), kb=_KB, oracle=_O10)
def executive_attendance(attendance_frame: pd.DataFrame, executives: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the attendees who were present at a meeting while holding one of the named executive roles on the meeting date.

    `executives` is the hr executives_on frame with an as_of column, one call per meeting date, concatenated (emp_key, role_name, as_of): a holder who changed role before the meeting is not counted for the meeting date. A present employee whose meeting date has no as_of value in the frame raises (the executive set of that date was never loaded; an attendee who is simply not an executive is fine). A date on which nobody holds an executive role (before the HR history starts, say) is declared by one row with an empty emp_key and role_name and that as_of.

    Args:
        attendance_frame: The output of attendance; it needs mtg_key, prj_key, date, emp_key and status.
        executives: The hr executives_on frames with an as_of column, concatenated; it needs emp_key, role_name and as_of.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns mtg_key, prj_key, date, emp_key, role_name, sorted by date, mtg_key, emp_key.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; a date column holds a time zone or a value that is not a date; an employee appears twice in one meeting; status has an unknown value; a present employee's meeting date has no as_of row in executives; emp_key differs in type between the two frames.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import executive_attendance
        >>> ctx = Context(stage="month12", role="analyst")
        >>> att = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-10"] * 2,
        ...                     "emp_key": ["EMP-900001", "EMP-900002"], "status": ["present", "present"]})
        >>> ex = pd.DataFrame({"emp_key": ["EMP-900001"], "role_name": ["director"], "as_of": ["2026-03-10"]})
        >>> executive_attendance(att, ex, context=ctx)[["emp_key", "role_name"]].to_dict("records")
        [{'emp_key': 'EMP-900001', 'role_name': 'director'}]
    """
    _need(attendance_frame, ["mtg_key", "prj_key", "date", "emp_key", "status"], "attendance output")
    _need(executives, ["emp_key", "role_name", "as_of"], "executives_on frame with an as_of column")
    ex = executives[["emp_key", "role_name", "as_of"]].assign(as_of=_day(executives, "as_of", "executives")).drop_duplicates()
    att = attendance_frame.assign(date=_day(attendance_frame, "date", "attendance output"))
    if att.duplicated(["mtg_key", "emp_key"]).any() and att["emp_key"].notna().any():
        dup = att[att.duplicated(["mtg_key", "emp_key"], keep=False) & att["emp_key"].notna()]
        if len(dup):
            raise FrameError(f"{dup.iloc[0]['emp_key']} appears more than once in meeting {dup.iloc[0]['mtg_key']}")
    unknown = sorted(set(att["status"].dropna().astype(str)) - {"present", "apology", "absent"})
    if unknown:
        raise FrameError(f"attendance status has unknown value(s) {unknown}; known: present, apology, absent")
    present = att[(att["status"] == "present") & att["emp_key"].notna()]
    no_set = present.loc[~present["date"].isin(set(ex["as_of"])), "date"]
    if len(no_set):
        raise FrameError(f"the executives frame has no as_of row for the meeting date {no_set.min().date()} of a present attendee; load the executive set of every meeting date")
    try:
        out = present.merge(ex, left_on=["emp_key", "date"], right_on=["emp_key", "as_of"], how="inner")
    except (ValueError, TypeError) as e:
        raise FrameError(f"emp_key differs in type between the attendance and the executives frame: {e}") from None
    return out[["mtg_key", "prj_key", "date", "emp_key", "role_name"]].sort_values(["date", "mtg_key", "emp_key"]).reset_index(drop=True)


@staged(sources=("projects.site_diary.diary_date", "projects.meeting.date"), kb=_KB, oracle=_O10)
def executive_gap(first: pd.DataFrame, exec_attendance: pd.DataFrame, prj_key: str) -> pd.DataFrame:
    """Use this when you need the days from the first record of a project to the first meeting with a present executive on or after it.

    Days from the first record to the first meeting of the project with a present executive on or after it. All columns but the first two are null when no executive attended (a gap that has not closed). first_executive_emp is the lowest emp_key (and its role) among the executives at that first meeting (earliest date, then lowest mtg_key); it is not picked by seniority, so the CFO of the narrative is not chosen by this function. executives_present lists every executive present at that meeting, emp_keys sorted and comma separated.

    Args:
        first: The output of first_record; it needs prj_key and diary_date, with exactly one row for the project.
        exec_attendance: The output of executive_attendance; it needs mtg_key, prj_key, date, emp_key and role_name.
        prj_key: The key of the project to measure.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A one row frame with the columns prj_key, first_record, first_executive_meeting, first_executive_emp, first_executive_role, gap_days, executives_present.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the project has no first record or more than one; its first record has no diary_date; a date column holds a time zone or a value that is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import executive_gap
        >>> ctx = Context(stage="month12", role="analyst")
        >>> first = pd.DataFrame({"prj_key": ["PRJ-900001"], "diary_date": ["2026-03-01"]})
        >>> ex = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001"], "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-11"] * 2,
        ...                    "emp_key": ["EMP-900002", "EMP-900001"], "role_name": ["cfo", "director"]})
        >>> row = executive_gap(first, ex, "PRJ-900001", context=ctx).iloc[0]
        >>> float(row["gap_days"]), row["first_executive_emp"], row["executives_present"]
        (10.0, 'EMP-900001', 'EMP-900001,EMP-900002')
    """
    _need(first, ["prj_key", "diary_date"], "first_record output")
    _need(exec_attendance, ["mtg_key", "prj_key", "date", "emp_key", "role_name"], "executive_attendance output")
    f = first[first["prj_key"] == prj_key]
    if f.empty:
        raise FrameError(f"project {prj_key} has no first record")
    if len(f) > 1:
        raise FrameError(f"project {prj_key} has {len(f)} first records; pass the output of first_record")
    start = _day(f, "diary_date", "first_record output").iloc[0]
    if pd.isna(start):
        raise FrameError(f"the first record of {prj_key} has no diary_date")
    e = exec_attendance[(exec_attendance["prj_key"] == prj_key)]
    e = e.assign(date=_day(e, "date", "executive_attendance output")).query("date >= @start").sort_values(["date", "mtg_key", "emp_key"])
    if e.empty:
        return pd.DataFrame([{"prj_key": prj_key, "first_record": start, "first_executive_meeting": pd.NaT, "first_executive_emp": None, "first_executive_role": None, "gap_days": np.nan,
                              "executives_present": None}])
    r = e.iloc[0]
    here = ",".join(sorted({str(k) for k in e.loc[(e["mtg_key"] == r["mtg_key"]) & (e["date"] == r["date"]), "emp_key"]}))
    return pd.DataFrame([{"prj_key": prj_key, "first_record": start, "first_executive_meeting": r["date"], "first_executive_emp": r["emp_key"], "first_executive_role": r["role_name"],
                          "gap_days": float((r["date"] - start).days), "executives_present": here}])


@staged(sources=("projects.decision.mtg_key", "projects.decision.seq", "projects.decision.decision_type", "projects.decision.impact_cost", "projects.decision.impact_days",
                 "projects.decision.currency", "projects.decision.delay_seq", "projects.decision.co_no", "projects.meeting.prj_key", "projects.meeting.date", "projects.delay_event.cause_code"),
        kb=_KB, oracle=_O10)
def decisions(decision: pd.DataFrame, meeting: pd.DataFrame, delay_event: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need the decisions of the meetings with their project and date, impact in cost and days, linked delay cause and change order.

    Cost and day impact are in the decision currency; the linked delay event cause comes from delay_seq on the same project, the change order from co_no, and write_down is true for decision_type write_down. Columns of the decision plus prj_key, date, meeting_type, write_down and, with a delay_event frame, delay_cause.

    Args:
        decision: The projects.decision frame, one row per mtg_key and seq; it needs mtg_key, seq, decision_type, impact_cost, impact_days, currency, delay_seq and co_no, and must not already have prj_key, date, meeting_type, write_down or delay_cause.
        meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and meeting_type.
        delay_event: Optional projects.delay_event frame, one row per prj_key and seq; it needs prj_key, seq and cause_code and adds the delay_cause column.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns of decision plus prj_key, date, meeting_type, write_down and, with delay_event, delay_cause. Sorted by date, mtg_key, seq.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; decision, meeting or delay_event has more than one row for a key; decision already has one of the added columns; delay_seq does not hold whole numbers; a decision names a meeting that is not in meeting; the meeting date holds a time zone or a value that is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import decisions
        >>> ctx = Context(stage="month12", role="analyst")
        >>> dec = pd.DataFrame({"mtg_key": ["MTG-900001"] * 2, "seq": [1, 2], "decision_type": ["write_down", "approve"], "impact_cost": [100.0, 0.0],
        ...                     "impact_days": [0, 5], "currency": ["EUR"] * 2, "delay_seq": [None, 1], "co_no": [None, None]})
        >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"]})
        >>> decisions(dec, mtg, context=ctx)["write_down"].tolist()
        [True, False]
    """
    _need(decision, ["mtg_key", "seq", "decision_type", "impact_cost", "impact_days", "currency", "delay_seq", "co_no"], "projects.decision", keys=("mtg_key", "seq"))
    _need(meeting, ["mtg_key", "prj_key", "date", "meeting_type"], "projects.meeting", keys=("mtg_key",))
    clash = [c for c in ("prj_key", "date", "meeting_type", "write_down", "delay_cause") if c in decision.columns]
    if clash:
        raise FrameError(f"projects.decision already has column(s) {', '.join(clash)}; pass the source frame")
    ds = decision["delay_seq"].dropna()
    if len(ds) and (not pd.api.types.is_numeric_dtype(ds) or (ds % 1 != 0).any()):
        raise FrameError("projects.decision.delay_seq must hold whole numbers")
    out = decision.merge(meeting[["mtg_key", "prj_key", "date", "meeting_type"]].assign(date=_day(meeting, "date", "projects.meeting")), on="mtg_key", how="left", validate="many_to_one")
    if out["date"].isna().any():
        raise FrameError(f"{int(out['date'].isna().sum())} decisions name a meeting that is not in projects.meeting (for example {out.loc[out['date'].isna(), 'mtg_key'].iloc[0]})")
    out["write_down"] = out["decision_type"] == "write_down"
    if delay_event is not None:
        _need(delay_event, ["prj_key", "seq", "cause_code"], "projects.delay_event", keys=("prj_key", "seq"))
        ev = delay_event[["prj_key", "seq", "cause_code"]].rename(columns={"seq": "delay_seq", "cause_code": "delay_cause"})
        out = out.assign(delay_seq=out["delay_seq"].astype("Int64")).merge(ev.assign(delay_seq=ev["delay_seq"].astype("Int64")), on=["prj_key", "delay_seq"], how="left")
    return out.sort_values(["date", "mtg_key", "seq"]).reset_index(drop=True)


class MinutesRefs(NamedTuple):
    """Result of minutes_refs: meeting to minutes path, and the share of meetings without a reference."""

    frame: pd.DataFrame
    null_share: float


@staged(sources=("projects.meeting.mtg_key", "projects.meeting.prj_key", "projects.meeting.date", "projects.meeting.minutes_ref"), kb=_KB, oracle=_O10)
def minutes_refs(meeting: pd.DataFrame) -> MinutesRefs:
    """Use this when you need the minutes path of each meeting and the share of meetings that have no minutes reference.

    The share counts meetings with a null or empty minutes_ref; it is reported and not hidden.

    Args:
        meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date and minutes_ref.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A MinutesRefs result: `frame` with the columns mtg_key, prj_key, date, minutes_ref sorted by date and mtg_key, and `null_share`, the share of meetings with no reference (0.0 for an empty frame).

    Raises:
        FrameError: meeting is not a DataFrame, has duplicate column names, lacks a needed column or has more than one row for a mtg_key; date holds a time zone or a value that is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import minutes_refs
        >>> ctx = Context(stage="month12", role="analyst")
        >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900002"], "prj_key": ["PRJ-900001"] * 2, "date": ["2026-03-10", "2026-03-03"],
        ...                     "minutes_ref": ["minutes/a.pdf", None]})
        >>> res = minutes_refs(mtg, context=ctx)
        >>> res.frame["mtg_key"].tolist(), res.null_share
        (['MTG-900002', 'MTG-900001'], 0.5)
    """
    _need(meeting, ["mtg_key", "prj_key", "date", "minutes_ref"], "projects.meeting", keys=("mtg_key",))
    out = meeting[["mtg_key", "prj_key", "date", "minutes_ref"]].assign(date=_day(meeting, "date", "projects.meeting")).sort_values(["date", "mtg_key"]).reset_index(drop=True)
    missing = out["minutes_ref"].isna() | (out["minutes_ref"].astype(str).str.strip() == "")
    return MinutesRefs(out, float(missing.mean()) if len(out) else 0.0)


@staged(sources=("projects.project_role.prj_key", "projects.project_role.emp_key", "projects.project_role.project_role", "projects.project_role.start", "projects.project_role.end",
                 "projects.project_role.hours_total", "projects.project_role.basis", "projects.project.legacy"), kb=("DA.REF.103",), oracle="py:tests/test_release.py::test_rule18_project_role_hours_equal_time_entries")
def roster(project_role: pd.DataFrame, project: pd.DataFrame, prj_keys: Sequence[str]) -> pd.DataFrame:
    """Use this when you need the role rows of a list of projects as stored, with the legacy flag of each project.

    The columns are prj_key, emp_key, project_role, start, end, hours_total, basis and legacy; there is no ranking. Hours of legacy roster rows are estimates; hr experience_summary keeps the two bases apart. A project of the list without role rows is not an error; a project that is not in the project frame is.

    Args:
        project_role: The projects.project_role frame; it needs prj_key, emp_key, project_role, start, end, hours_total and basis.
        project: The projects.project frame, one row per prj_key; it needs prj_key and legacy.
        prj_keys: The project keys to list (one key as text is also accepted).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns prj_key, emp_key, project_role, start, end, hours_total, basis, legacy, sorted by prj_key, emp_key, project_role, start.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; project has more than one row for a prj_key; a project of the list is not in project.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import roster
        >>> ctx = Context(stage="month12", role="analyst")
        >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900002", "EMP-900001"], "project_role": ["engineer", "manager"],
        ...                       "start": ["2026-01-01"] * 2, "end": [None, None], "hours_total": [100.0, 50.0], "basis": ["time_entries"] * 2})
        >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "legacy": [False]})
        >>> roster(roles, proj, ["PRJ-900001"], context=ctx)["emp_key"].tolist()
        ['EMP-900001', 'EMP-900002']
    """
    _need(project_role, ["prj_key", "emp_key", "project_role", "start", "end", "hours_total", "basis"], "projects.project_role")
    _need(project, ["prj_key", "legacy"], "projects.project", keys=("prj_key",))
    keys = [prj_keys] if isinstance(prj_keys, str) else list(prj_keys)
    unknown = sorted(set(keys) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the list are not in the project frame (for example {unknown[0]})")
    out = project_role[project_role["prj_key"].isin(keys)][["prj_key", "emp_key", "project_role", "start", "end", "hours_total", "basis"]].merge(project[["prj_key", "legacy"]], on="prj_key", how="left")
    return out.sort_values(["prj_key", "emp_key", "project_role", "start"], kind="stable").reset_index(drop=True)


@staged(sources=("projects.site_diary.prj_key", "projects.risk.prj_key", "projects.meeting.prj_key", "projects.decision.mtg_key", "projects.delay_event.prj_key", "projects.plan_version.prj_key"),
        kb=_KB, oracle=_O10)
def timeline(prj_key: str, *, site_diary: pd.DataFrame, risk: pd.DataFrame, meeting: pd.DataFrame, decision: pd.DataFrame, delay_event: pd.DataFrame, plan_version: pd.DataFrame,
             start: DateLike | None = None, end: DateLike | None = None) -> pd.DataFrame:
    """Use this when you need the dated events of one project in one ordered frame, such as meetings, decisions, delay events, risks and plan versions.

    Columns: date, kind (delay_event, risk, meeting, decision, plan_version, first_diary_delay), source table, source key and a short text. Diary rows are not listed one by one (they are daily): only the first row of each delay_seq appears, as first_diary_delay. `start` and `end` (inclusive) limit the dates. Sorted by date, then by kind in the order meeting, decision, delay_event, first_diary_delay, risk, plan_version (a decision follows its meeting), then as listed per kind: delay events by seq, risks by risk_no, decisions by meeting and seq, plan versions by number, first diary rows by date and then delay_seq; meetings keep the order of the meeting frame.

    Args:
        prj_key: The key of the project.
        site_diary: The projects.site_diary frame; it needs prj_key, diary_date, delay_seq and notes.
        risk: The projects.risk frame; it needs prj_key, risk_no, raised, title and status.
        meeting: The projects.meeting frame, one row per mtg_key; it needs mtg_key, prj_key, date, meeting_type and title.
        decision: The projects.decision frame; it needs mtg_key, seq, text and decision_type.
        delay_event: The projects.delay_event frame; it needs prj_key, seq, start, days and cause_code.
        plan_version: The projects.plan_version frame; it needs prj_key, plan_version, created and reason.
        start: Optional first date to keep (inclusive).
        end: Optional last date to keep (inclusive).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns date, kind, source, source_key, text, ordered as described above.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; seq or days of delay_event, risk_no of risk, seq of decision or plan_version of plan_version is not whole numbers or has nulls; meeting has more than one row for a meeting; a date column holds a time zone or a value that is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import timeline
        >>> ctx = Context(stage="month12", role="analyst")
        >>> mtg = pd.DataFrame({"mtg_key": ["MTG-900001"], "prj_key": ["PRJ-900001"], "date": ["2026-03-10"], "meeting_type": ["site"], "title": ["Kick-off"]})
        >>> dec = pd.DataFrame({"mtg_key": ["MTG-900001"], "seq": [1], "text": ["Go"], "decision_type": ["approve"]})
        >>> diary = pd.DataFrame({"prj_key": [], "diary_date": [], "delay_seq": [], "notes": []})
        >>> risk = pd.DataFrame({"prj_key": [], "risk_no": [], "raised": [], "title": [], "status": []})
        >>> dev = pd.DataFrame({"prj_key": [], "seq": [], "start": [], "days": [], "cause_code": []})
        >>> pv = pd.DataFrame({"prj_key": [], "plan_version": [], "created": [], "reason": []})
        >>> out = timeline("PRJ-900001", site_diary=diary, risk=risk, meeting=mtg, decision=dec, delay_event=dev, plan_version=pv, context=ctx)
        >>> out[["kind", "source_key"]].to_dict("records")
        [{'kind': 'meeting', 'source_key': 'MTG-900001'}, {'kind': 'decision', 'source_key': 'MTG-900001/1'}]
    """
    _need(site_diary, ["prj_key", "diary_date", "delay_seq", "notes"], "projects.site_diary")
    _need(risk, ["prj_key", "risk_no", "raised", "title", "status"], "projects.risk")
    _need(meeting, ["mtg_key", "prj_key", "date", "meeting_type", "title"], "projects.meeting")
    _need(decision, ["mtg_key", "seq", "text", "decision_type"], "projects.decision")
    _need(delay_event, ["prj_key", "seq", "start", "days", "cause_code"], "projects.delay_event")
    _need(plan_version, ["prj_key", "plan_version", "created", "reason"], "projects.plan_version")
    for name, f, cols in (("projects.delay_event", delay_event, ["seq", "days"]), ("projects.risk", risk, ["risk_no"]), ("projects.decision", decision, ["seq"]), ("projects.plan_version", plan_version, ["plan_version"])):
        for c in cols:
            if len(f) and (not pd.api.types.is_numeric_dtype(f[c]) or f[c].isna().any() or (f[c] % 1 != 0).any()):
                raise FrameError(f"{name}.{c} must hold whole numbers without nulls")
    if meeting["mtg_key"].duplicated().any():
        raise FrameError("projects.meeting has more than one row for a meeting")
    parts = []
    d = site_diary[(site_diary["prj_key"] == prj_key) & site_diary["delay_seq"].notna()].assign(_d=lambda x: _day(x, "diary_date", "projects.site_diary")).sort_values(["_d", "delay_seq"], kind="stable")
    first = d.drop_duplicates("delay_seq", keep="first")
    parts.append(pd.DataFrame({"date": first["_d"], "kind": "first_diary_delay", "source": "projects.site_diary", "source_key": first["delay_seq"].astype(int).astype(str), "text": first["notes"].fillna("")}))
    ev = delay_event[delay_event["prj_key"] == prj_key].sort_values("seq")
    parts.append(pd.DataFrame({"date": _day(ev, "start", "projects.delay_event"), "kind": "delay_event", "source": "projects.delay_event", "source_key": ev["seq"].astype(int).astype(str),
                               "text": ev["cause_code"].astype(str) + ", " + ev["days"].astype(int).astype(str) + " days"}))
    rk = risk[risk["prj_key"] == prj_key].sort_values("risk_no")
    parts.append(pd.DataFrame({"date": _day(rk, "raised", "projects.risk"), "kind": "risk", "source": "projects.risk", "source_key": rk["risk_no"].astype(int).astype(str), "text": rk["title"].astype(str)}))
    mt = meeting[meeting["prj_key"] == prj_key]
    parts.append(pd.DataFrame({"date": _day(mt, "date", "projects.meeting"), "kind": "meeting", "source": "projects.meeting", "source_key": mt["mtg_key"].astype(str), "text": mt["title"].astype(str)}))
    dd = decision[decision["mtg_key"].isin(mt["mtg_key"])].merge(mt[["mtg_key", "date"]].assign(date=_day(mt, "date", "projects.meeting")), on="mtg_key").sort_values(["mtg_key", "seq"])
    parts.append(pd.DataFrame({"date": dd["date"], "kind": "decision", "source": "projects.decision", "source_key": dd["mtg_key"].astype(str) + "/" + dd["seq"].astype(int).astype(str),
                               "text": dd["decision_type"].astype(str) + ": " + dd["text"].astype(str)}))
    pv = plan_version[plan_version["prj_key"] == prj_key].sort_values("plan_version")
    parts.append(pd.DataFrame({"date": _day(pv, "created", "projects.plan_version"), "kind": "plan_version", "source": "projects.plan_version", "source_key": pv["plan_version"].astype(int).astype(str),
                               "text": pv["reason"].astype(str)}))
    out = pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) else pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "kind": [], "source": [], "source_key": [], "text": []})
    if start is not None:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    out = out.assign(_k=out["kind"].map({k: i for i, k in enumerate(_KIND_ORDER)}))
    return out.sort_values(["date", "_k"], kind="stable").drop(columns="_k").reset_index(drop=True)      # within one date and kind the order of each part above is kept (meetings: input order)


class ExperienceNetwork(NamedTuple):
    """People and projects as a network: `nodes` (node_key, kind person or project, label fields), `edges` (a person on a project: the roles, the period, the hours and the basis) and `pairs` (two people who
    worked on the same project at the same time and for how many days). No ranking and no score."""
    nodes: pd.DataFrame
    edges: pd.DataFrame
    pairs: pd.DataFrame


@staged(sources=("projects.project_role.prj_key", "projects.project_role.emp_key", "projects.project_role.project_role", "projects.project_role.start", "projects.project_role.end",
                 "projects.project_role.hours_total", "projects.project_role.basis", "projects.project.legacy", "projects.project.type", "projects.project.soil_class", "projects.project.country",
                 "hr.employee.leave_date"), facts=("world.now",), kb=("DA.REF.103",), oracle="py:tests/test_release.py::test_rule18_project_role_hours_equal_time_entries")
def experience_network(project_role: pd.DataFrame, project: pd.DataFrame, prj_keys: Sequence[str], employee: pd.DataFrame | None = None, *, project_types: Sequence[str] | None = None,
                       soil_classes: Sequence[str] | None = None, countries: Sequence[str] | None = None, as_of: DateLike | None = None) -> ExperienceNetwork:
    """Use this when you need the person to project network of a list of projects: who worked on which project, for how long, and which people worked together.

    The result is filtered by project type, soil class and country (all optional lists), with a leaver flag from the hr frame (`emp_key`, `leave_date`: a leaver has a leave date on or before `as_of`, default the release date world.now). Edges are one row per person and project: roles (sorted, joined with '; '), first start, last end, hours_total, basis (the one basis or 'mixed'), legacy. Pairs are the people of one project who worked there at the same time, from the role rows themselves (a person's stints are merged when they touch or overlap, so a gap is a gap; both days inclusive): prj_key, emp_a, emp_b (emp_a sorts first), first overlap start, last overlap end, overlap_days (the days summed over the stints). The network is as of the day: roles that start later are left out, an open role runs to the day and a role that ends later is cut at the day. Hours of a role that crosses the day are prorated by days to the day. Hours of legacy roster rows are estimates (see roster). No ranking and no score: the order is by key.

    Args:
        project_role: The projects.project_role frame; it needs prj_key, emp_key, project_role, start, end, hours_total and basis.
        project: The projects.project frame, one row per prj_key; it needs prj_key, type, soil_class, country and legacy.
        prj_keys: The project keys of the network (one key as text is also accepted).
        employee: Optional hr.employee frame, one row per emp_key, with emp_key and leave_date; without it no one is a leaver.
        project_types: Optional list of project types to keep.
        soil_classes: Optional list of soil classes to keep.
        countries: Optional list of countries to keep.
        as_of: Optional day of the network; the default is the release date world.now.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An ExperienceNetwork with `nodes` (node_key, kind person or project, type, country, soil_class, leaver; sorted by kind and node_key), `edges` (prj_key, emp_key, roles, start, end, hours_total, basis, legacy; sorted by prj_key, emp_key) and `pairs` (prj_key, emp_a, emp_b, overlap_start, overlap_end, overlap_days; sorted by prj_key, emp_a, emp_b).

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; project or employee has more than one row for a key; a project of the list is not in project; project_types, soil_classes or countries is a single text; a role row has no emp_key or start; a role period ends before it starts; a date column holds a time zone or a value that is not a date.
        PeriodError: as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import experience_network
        >>> ctx = Context(stage="month12", role="analyst")
        >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900001", "EMP-900002"], "project_role": ["manager", "engineer"],
        ...                       "start": ["2026-01-01", "2026-01-06"], "end": ["2026-01-10", "2026-01-20"], "hours_total": [80.0, 100.0], "basis": ["time_entries"] * 2})
        >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tunnel"], "soil_class": ["clay"], "country": ["NL"], "legacy": [False]})
        >>> net = experience_network(roles, proj, ["PRJ-900001"], as_of="2026-02-01", context=ctx)
        >>> net.edges["emp_key"].tolist()
        ['EMP-900001', 'EMP-900002']
        >>> net.pairs["overlap_days"].tolist()
        [5]
    """
    _need(project_role, ["prj_key", "emp_key", "project_role", "start", "end", "hours_total", "basis"], "projects.project_role")
    _need(project, ["prj_key", "type", "soil_class", "country", "legacy"], "projects.project", keys=("prj_key",))
    keys = [prj_keys] if isinstance(prj_keys, str) else list(prj_keys)
    unknown = sorted(set(keys) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the list are not in the project frame (for example {unknown[0]})")
    for nm, v in (("project_types", project_types), ("soil_classes", soil_classes), ("countries", countries)):
        if isinstance(v, (str, bytes)):
            raise FrameError(f"{nm} must be a list of values, not a single text")
    day = pd.Timestamp(fact("world.now").value).normalize() if as_of is None else _day_of(as_of)
    p = project[project["prj_key"].isin(keys)]
    for col, vals in (("type", project_types), ("soil_class", soil_classes), ("country", countries)):
        if vals is not None:
            p = p[p[col].isin(list(vals))]
    if employee is not None:
        _need(employee, ["emp_key", "leave_date"], "hr.employee", keys=("emp_key",))
    r = project_role[project_role["prj_key"].isin(set(p["prj_key"]))].copy()
    r["_s"], r["_e"] = _day(r, "start", "projects.project_role"), _day(r, "end", "projects.project_role")
    if r["_s"].isna().any() or r["emp_key"].isna().any():
        raise FrameError("projects.project_role has a row without emp_key or start")
    if (r["_e"].notna() & (r["_e"] < r["_s"])).any():
        raise FrameError("projects.project_role has a period that ends before it starts")
    r = r[r["_s"] <= day].copy()                                             # as of the day: a role that starts later does not exist yet
    full_days = ((r["_e"].fillna(day) - r["_s"]).dt.days + 1).astype(float)
    r["_e"] = cast(Any, r["_e"].fillna(day)).clip(upper=day)                            # an open role runs to the day, a role that ends later is cut at the day
    cut_days = ((r["_e"] - r["_s"]).dt.days + 1).astype(float)
    r["hours_total"] = r["hours_total"].astype(float) * (cut_days / full_days)        # hours of a role that crosses the day are prorated by days to the day
    r["role_txt"] = r["project_role"].fillna("(no role)").astype(str)
    g = r.groupby(["prj_key", "emp_key"], as_index=False)
    edges = g.agg(roles=("role_txt", lambda s: "; ".join(sorted(set(s)))), start=("_s", "min"), end=("_e", "max"), hours_total=("hours_total", lambda s: s.sum(min_count=1)),
                  basis=("basis", lambda s: s.iloc[0] if s.nunique() == 1 else ("mixed" if s.notna().any() else None)))
    edges = edges.merge(p[["prj_key", "legacy"]], on="prj_key", how="left").sort_values(["prj_key", "emp_key"]).reset_index(drop=True)
    stints: dict[Any, Any] = {}
    for (prj, emp), t in r.groupby(["prj_key", "emp_key"]):
        merged: list[Any] = []
        for st, en in sorted(zip(t["_s"], t["_e"])):
            if merged and st <= merged[-1][1] + pd.Timedelta(days=1):
                merged[-1][1] = max(merged[-1][1], en)
            else:
                merged.append([st, en])
        stints.setdefault(prj, {})[emp] = merged
    pair_rows: list[tuple[Any, ...]] = []
    for prj, people in stints.items():
        keys = sorted(people)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ov = [(max(a0, b0), min(a1, b1)) for a0, a1 in people[keys[i]] for b0, b1 in people[keys[j]] if max(a0, b0) <= min(a1, b1)]
                if ov:
                    pair_rows.append((prj, keys[i], keys[j], min(o[0] for o in ov), max(o[1] for o in ov), sum((o[1] - o[0]).days + 1 for o in ov)))
    pairs = pd.DataFrame(pair_rows, columns=["prj_key", "emp_a", "emp_b", "overlap_start", "overlap_end", "overlap_days"])
    leaver = pd.Series(False, index=sorted(set(edges["emp_key"])))
    if employee is not None:
        ld = _day(employee, "leave_date", "hr.employee")
        lv = pd.Series((ld <= day).to_numpy(), index=employee["emp_key"].to_numpy())
        leaver = pd.Series(leaver.index.map(lambda k: bool(lv.get(k, False))), index=leaver.index)
    people = pd.DataFrame({"node_key": leaver.index, "kind": "person", "type": None, "country": None, "soil_class": None, "leaver": leaver.to_numpy()})
    proj = p[p["prj_key"].isin(set(edges["prj_key"]))]
    projects = pd.DataFrame({"node_key": proj["prj_key"].to_numpy(), "kind": "project", "type": proj["type"].to_numpy(), "country": proj["country"].to_numpy(), "soil_class": proj["soil_class"].to_numpy(), "leaver": False})
    nodes = pd.concat([people, projects], ignore_index=True).sort_values(["kind", "node_key"]).reset_index(drop=True)
    return ExperienceNetwork(nodes, edges, pairs.sort_values(["prj_key", "emp_a", "emp_b"]).reset_index(drop=True))


def _day_of(as_of: Any) -> pd.Timestamp:
    from .projects import _day as _d
    return _d(as_of)
