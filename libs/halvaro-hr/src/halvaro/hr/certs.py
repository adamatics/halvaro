"""Certificates: validity from the dates, status on a date, renewal chains, booked renewals, expiring certificates and the expiry report (reads competence, Month 12)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, PeriodError, fact
from halvaro.core.registry import function

from ._guard import staged
from .org import UNAVAILABLE_LEAVE_TYPES, PolicyDefault, _need, data_now, leave_types_given, unavailable_types

_CERT = ["emp_key", "qual_key", "issued", "expires"]
_WARNING_DAYS = PolicyDefault("policy.certificates.expiry_warning_days")      # proposed policy fact


def _days(frame: pd.DataFrame, columns: Sequence[str], what: str) -> pd.DataFrame:
    """The columns as naive calendar days; an unreadable value or a time zone raises FrameError."""
    out = frame.copy()
    for c in columns:
        if pd.api.types.is_numeric_dtype(out[c]) and not pd.api.types.is_datetime64_any_dtype(out[c]) and out[c].notna().any():
            raise FrameError(f"{what}.{c} holds numbers, not dates")
        try:
            x = pd.to_datetime(out[c], format="mixed") if (out[c].dtype == object or pd.api.types.is_string_dtype(out[c])) else pd.to_datetime(out[c])
        except (ValueError, TypeError, OverflowError) as e:
            raise FrameError(f"{what}.{c} holds a value that is not a date: {e}") from None
        if getattr(x.dt, "tz", None) is not None:
            raise FrameError(f"{what}.{c} has a time zone; dates here are calendar days")
        out[c] = x.dt.normalize().astype("datetime64[ns]")
    return out


def _day(as_of: Any, name: str = "as_of") -> pd.Timestamp:
    if isinstance(as_of, (bool, int, float, np.number)):
        raise PeriodError(f"{name} {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise PeriodError(f"{name} {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise PeriodError(f"{name} {as_of!r} is not a date without a time zone")
    return d.normalize()


def _certs(cert: pd.DataFrame, extra: Sequence[str] = ()) -> pd.DataFrame:
    _need(cert, [*_CERT, *extra], "competence.certification_held")
    if cert.columns.duplicated().any():
        raise FrameError("competence.certification_held has duplicate column names")
    out = _days(cert, ["issued", "expires"], "competence.certification_held").reset_index(drop=True)
    if out["issued"].isna().any() or out["emp_key"].isna().any() or out["qual_key"].isna().any():
        raise FrameError("competence.certification_held rows need emp_key, qual_key and issued")
    rev = out["expires"].notna() & (out["expires"] < out["issued"])
    if rev.any():
        raise FrameError(f"{int(rev.sum())} certificates expire before they are issued (for example {out.loc[rev, 'emp_key'].iloc[0]})")
    return out


def _order(c: pd.DataFrame) -> pd.DataFrame:
    """Certificates in a fixed order: by person, qualification, issue, then expiry (open last), then event_no, so that ties never depend on the input order."""
    keys = c.assign(_open=c["expires"].isna(), _ev=c["event_no"] if "event_no" in c.columns else 0)
    return keys.sort_values(["emp_key", "qual_key", "issued", "_open", "expires", "_ev"], kind="stable", na_position="last").drop(columns=["_open", "_ev"])


def _superseded(c: pd.DataFrame, d: pd.Timestamp) -> pd.Series:
    """True for a certificate when a strictly later issue of the same person and qualification is already issued and still in force on the date."""
    keyed = c[["emp_key", "qual_key", "issued"]].assign(_i=np.arange(len(c)))
    later = c[["emp_key", "qual_key", "issued", "expires"]].rename(columns={"issued": "issued_later", "expires": "expires_later"})
    later = later[(later["issued_later"] <= d) & (later["expires_later"].isna() | (later["expires_later"] >= d))]
    m = keyed.merge(later, on=["emp_key", "qual_key"], how="inner")
    hit = set(m.loc[m["issued_later"] > m["issued"], "_i"])
    return pd.Series(np.isin(np.arange(len(c)), list(hit)), index=c.index)


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::valid_on_record")
def valid_on(cert: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the certificates that are valid on a date, one row per person and qualification.

    Rule: a certificate is valid when issued is on or before the date and expires is empty (no expiry) or on or after the date, both ends included. The status column is never read. Per person and qualification the latest issue is kept.

    Args:
        cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
        as_of: The date.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: emp_key, qual_key, issued, expires and as_of, sorted by person and qualification.

    Raises:
        FrameError: a column is missing or duplicated, a row has no emp_key, qual_key or issued, or a certificate expires before it is issued.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import valid_on
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "qual_key": ["QUAL-01", "QUAL-01"],
        ...                      "issued": ["2023-01-10", "2025-01-10"], "expires": ["2025-01-09", "2027-01-09"]})
        >>> valid = valid_on(cert, dt.date(2026, 11, 30))
        >>> valid["qual_key"].tolist(), valid["expires"].dt.strftime("%Y-%m-%d").tolist()
        (['QUAL-01'], ['2027-01-09'])
    """
    c = _certs(cert)
    d = _day(as_of)
    v = c[(c["issued"] <= d) & (c["expires"].isna() | (c["expires"] >= d))]
    v = _order(v).drop_duplicates(["emp_key", "qual_key"], keep="last")
    out = v[["emp_key", "qual_key", "issued", "expires"]].assign(as_of=d.to_datetime64().astype("datetime64[ns]"))
    return out.sort_values(["emp_key", "qual_key"]).reset_index(drop=True)


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires",
                   "competence.certification_held.status"), oracle="py:tests/test_competence.py::test_status_logic")
def cert_status_on(cert: pd.DataFrame, as_of: dt.date, stored_at: dt.date | None = None) -> pd.DataFrame:
    """Use this when you need the status of every certificate on a date, worked out from the dates and not read from the stored status.

    Rule: not_yet_valid before issued, expired after expires, superseded when a strictly later issue of the same person and qualification is issued and still in force, otherwise valid. matches_stored is set only when as_of equals stored_at, the date the stored status was computed for.

    Args:
        cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires and status.
        as_of: The date.
        stored_at: The date the stored status was computed for (the release date). Optional.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: one row per certificate with emp_key, qual_key, issued, expires, as_of, status_on, stored_status and matches_stored (null unless stored_at equals as_of).

    Raises:
        FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import cert_status_on
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2024-01-01"],
        ...                      "expires": ["2023-12-31", "2026-12-31"], "status": ["expired", "valid"]})
        >>> cert_status_on(cert, dt.date(2025, 6, 1))["status_on"].tolist()
        ['expired', 'valid']
    """
    c = _certs(cert, ["status"])
    d = _day(as_of)
    sup = _superseded(c, d)
    status = np.where(c["issued"] > d, "not_yet_valid", np.where(c["expires"].notna() & (c["expires"] < d), "expired", np.where(sup, "superseded", "valid")))
    out = c[["emp_key", "qual_key", "issued", "expires"]].assign(as_of=d, status_on=status, stored_status=c["status"].to_numpy())
    same = pd.Series(pd.NA, index=out.index, dtype="boolean")
    if stored_at is not None and _day(stored_at) == d:
        same = pd.Series(out["status_on"].to_numpy() == out["stored_status"].to_numpy(), index=out.index, dtype="boolean")
    out["matches_stored"] = same
    return out.reset_index(drop=True)


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires",
                   "competence.certification_held.origin", "competence.certification_held.event_no", "competence.certification_held.renews_issued"),
          oracle="py:halvaro_gen/world/competence/certs.py::ChainBuilder")
def renewal_chains(cert: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need to see how certificates follow each other for a person and qualification: the chains of renewals, with lapses and overlaps.

    Rule: a certificate with no renews_issued starts a chain; a renewal names the issue date of the one it renews. link_ok says that renews_issued is the previous issue. lapse_days are the days without a valid certificate before this one, overlap_days the days both are valid; both are given only for a renewal whose link is ok.

    Args:
        cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires, origin, event_no and renews_issued.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: the certificate rows with chain, position, previous issue and expiry, link_ok, covered_until, lapse_days and overlap_days.

    Raises:
        FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import renewal_chains
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2023-12-01"], "expires": ["2023-12-31", "2025-12-31"],
        ...                      "origin": ["initial", "renewal"], "event_no": [1, 2], "renews_issued": [None, "2022-01-01"]})
        >>> renewal_chains(cert)[["position", "link_ok", "lapse_days", "overlap_days"]].fillna(-1).values.tolist()
        [[1, True, -1.0, -1.0], [2, True, 0.0, 31.0]]
    """
    c = _certs(cert, ["origin", "event_no", "renews_issued"])
    c = _days(c, ["renews_issued"], "competence.certification_held")
    c = _order(c).reset_index(drop=True)
    g = c.groupby(["emp_key", "qual_key"], sort=False)
    c["prev_issued"], c["prev_expires"] = g["issued"].shift(), g["expires"].shift()
    c["chain"] = c["renews_issued"].isna().groupby([c["emp_key"], c["qual_key"]], sort=False).cumsum()
    c["position"] = c.groupby(["emp_key", "qual_key", "chain"], sort=False).cumcount() + 1
    renewal = c["renews_issued"].notna()
    c["link_ok"] = (~renewal) | (c["prev_issued"].notna() & (c["renews_issued"] == c["prev_issued"]))
    far = pd.Timestamp("2262-04-11")
    earlier = c["expires"].fillna(far).groupby([c["emp_key"], c["qual_key"]], sort=False).cummax().groupby([c["emp_key"], c["qual_key"]], sort=False).shift()
    c["covered_until"] = earlier.where(earlier < far)
    gap = (c["issued"] - earlier).dt.days
    ok = c["prev_issued"].notna() & renewal & c["link_ok"]
    c["lapse_days"] = (gap - 1).clip(lower=0).where(ok).astype("float64")
    c["overlap_days"] = (1 - gap).clip(lower=0).where(ok & (earlier < far)).astype("float64")
    return c[["emp_key", "qual_key", "chain", "position", "origin", "event_no", "issued", "expires", "renews_issued", "prev_issued", "prev_expires", "covered_until", "link_ok", "lapse_days", "overlap_days"]]


@staged(sources=("competence.training_attendance.status", "competence.training_attendance.event_no", "competence.training_attendance.emp_key", "competence.training_event.date",
                   "competence.training_event.end_date", "competence.training_event.qual_key", "competence.training_event.capacity", "competence.training_event.seats_taken",
                   "competence.training_event.country", "competence.training_event.location_site_key", "competence.data_release.now"),
          oracle="py:halvaro_gen/world/competence/truthcalc.py::valid_with_booked")
def booked_renewals(attendance: pd.DataFrame, event: pd.DataFrame, as_of: dt.date, data_releases: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Use this when you need the seats booked on training courses that start after the release date, to see who will renew a certificate in time.

    Rule: bookings carry no booking date, so the function only answers for the release date itself (data_now of the passed data_release frames); another date is refused. Only attendance with the status booked counts; any other status (for example cancelled) does not.

    Args:
        attendance: Attendance frame (competence.training_attendance) with event_no, emp_key and status.
        event: Training event frame (competence.training_event) with event_no, qual_key, date, end_date, capacity, seats_taken, country and location_site_key.
        as_of: The date; it must be the release date.
        data_releases: A mapping of source name to its data_release frame, for example {"competence": frame}.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame with emp_key, qual_key, event_no, course_date, course_end, capacity, seats_taken, free_seats, country and location_site_key.

    Raises:
        FrameError: data_releases is not a mapping, a frame lacks a column, event_no is duplicated, a booked seat is listed twice or names an event that is missing, or a booked course does not start after the date.
        PeriodError: as_of is not the release date.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import booked_renewals
        >>> release = pd.DataFrame({"release": ["r1"], "now": ["2026-03-31"], "generated_at": ["2026-04-01"], "base_seed": [1], "increment": [0]})
        >>> attendance = pd.DataFrame({"event_no": [7, 7], "emp_key": ["EMP-000001", "EMP-000002"], "status": ["booked", "cancelled"]})
        >>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-05-10"], "end_date": ["2026-05-11"], "capacity": [10], "seats_taken": [4], "country": ["DK"], "location_site_key": ["SITE-01"]})
        >>> booked_renewals(attendance, event, dt.date(2026, 3, 31), {"competence": release})[["emp_key", "qual_key", "free_seats"]].to_dict("records")
        [{'emp_key': 'EMP-000001', 'qual_key': 'QUAL-01', 'free_seats': 6}]
        >>> booked_renewals(attendance, event, dt.date(2026, 3, 1), {"competence": release})
        Traceback (most recent call last):
        ...
        halvaro.core.errors.PeriodError: booked renewals are only known at the release date 2026-03-31: bookings have no booking date, so 2026-03-01 cannot be rebuilt
    """
    if not isinstance(data_releases, Mapping):
        raise FrameError("data_releases is a mapping of source name to its data_release frame, for example {'competence': frame}")
    now = data_now(data_releases)
    d = _day(as_of)
    if d != pd.Timestamp(now):
        raise PeriodError(f"booked renewals are only known at the release date {now}: bookings have no booking date, so {d.date()} cannot be rebuilt")
    _need(attendance, ["event_no", "emp_key", "status"], "competence.training_attendance")
    _need(event, ["event_no", "qual_key", "date", "end_date", "capacity", "seats_taken", "country", "location_site_key"], "competence.training_event")
    if event["event_no"].duplicated().any():
        raise FrameError("competence.training_event has duplicate event_no values")
    ev = _days(event[["event_no", "qual_key", "date", "end_date", "capacity", "seats_taken", "country", "location_site_key"]], ["date", "end_date"], "competence.training_event")
    b = attendance.loc[attendance["status"] == "booked", ["event_no", "emp_key"]]
    if b.duplicated().any():
        raise FrameError(f"{int(b.duplicated().sum())} booked seats appear twice (for example {b[b.duplicated()].iloc[0].tolist()})")
    try:
        m = b.merge(ev, on="event_no", how="left", validate="many_to_one")
    except (ValueError, TypeError) as e:
        raise FrameError(f"event_no in the attendance and event frames do not match in type or are not unique: {e}") from None
    if m["date"].isna().any():
        raise FrameError(f"{int(m['date'].isna().sum())} booked seats name an event_no that is not in competence.training_event (for example {m.loc[m['date'].isna(), 'event_no'].iloc[0]})")
    if (m["date"] <= d).any():
        raise FrameError(f"{int((m['date'] <= d).sum())} seats are still 'booked' on a course that is not after {d.date()}: the cache is stale")
    m["free_seats"] = m["capacity"] - m["seats_taken"]
    if (m["free_seats"] < 0).any():
        raise FrameError("a course has more seats taken than capacity")
    out = m.rename(columns={"date": "course_date", "end_date": "course_end"})[["emp_key", "qual_key", "event_no", "course_date", "course_end", "capacity", "seats_taken", "free_seats", "country", "location_site_key"]]
    return out.sort_values(["emp_key", "qual_key", "course_date"]).reset_index(drop=True)


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.expires"), facts=("policy.certificates.expiry_warning_days",))
def expiring(valid: pd.DataFrame, booked: pd.DataFrame, as_of: dt.date, window_days: int | PolicyDefault = _WARNING_DAYS) -> pd.DataFrame:
    """Use this when you need the valid certificates that expire soon, with the first booked renewal course after the date and the days a person would be without a valid certificate.

    Rule: window_days defaults to the fact policy.certificates.expiry_warning_days (status proposed: the owner has not decided); when the default is used the frame carries attrs["policy_status"] with the fact status. A certificate is listed when it expires on the date or within window_days after it. gap_days is the number of days between the expiry and the first booked course without a valid certificate, 0 when the course is on or before the expiry day, empty when nothing is booked.

    Args:
        valid: The output of valid_on for the same date.
        booked: The output of booked_renewals.
        as_of: The date. It must be the date of the valid frame.
        window_days: Whole number of days, zero or more, or the default fact.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: emp_key, qual_key, as_of, expires, booked, course_date, event_no, free_seats and gap_days, sorted by expiry, person and qualification.

    Raises:
        FrameError: a frame lacks a column, window_days is not a whole number of days of zero or more, the valid frame is for another date or has two rows for a person and qualification, or the default fact is not a whole number.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import expiring, valid_on
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01", "QUAL-02"],
        ...                      "issued": ["2025-01-10", "2024-05-01"], "expires": ["2027-01-09", "2026-12-31"]})
        >>> booked = pd.DataFrame({"emp_key": ["EMP-000002"], "qual_key": ["QUAL-02"], "course_date": [pd.Timestamp("2027-01-20")], "event_no": [7], "free_seats": [3]})
        >>> soon = expiring(valid_on(cert, dt.date(2026, 11, 30)), booked, dt.date(2026, 11, 30), window_days=60)
        >>> soon[["emp_key", "booked", "gap_days"]].to_dict("records")
        [{'emp_key': 'EMP-000002', 'booked': True, 'gap_days': 19.0}, {'emp_key': 'EMP-000001', 'booked': False, 'gap_days': nan}]
    """
    _need(valid, ["emp_key", "qual_key", "expires"], "valid_on output")
    _need(booked, ["emp_key", "qual_key", "course_date", "event_no", "free_seats"], "booked_renewals output")
    used = None
    if isinstance(window_days, PolicyDefault):
        used = {window_days.fact_id: fact(window_days.fact_id).status}
        value = fact(window_days.fact_id).value
        if isinstance(value, bool) or not isinstance(value, int):
            raise FrameError(f"{window_days.fact_id} must be a whole number of days, it is {value!r}")
        window_days = value
    if isinstance(window_days, bool) or not isinstance(window_days, (int, np.integer)) or window_days < 0:
        raise FrameError(f"window_days must be a whole number of days, zero or more, not {window_days!r}")
    d = _day(as_of)
    v = _days(valid[["emp_key", "qual_key", "expires"] + (["as_of"] if "as_of" in valid.columns else [])], ["expires"] + (["as_of"] if "as_of" in valid.columns else []), "valid_on output")
    if "as_of" in v.columns and (v["as_of"] != d).any():
        raise FrameError(f"the valid frame is for {v['as_of'].iloc[0].date()}, not {d.date()}; call valid_on with the same date")
    if v.duplicated(["emp_key", "qual_key"]).any():
        raise FrameError("the valid frame has more than one row for a person and qualification; pass the output of valid_on")
    soon = v[v["expires"].notna() & (v["expires"] >= d) & (v["expires"] <= d + pd.DateOffset(days=int(window_days)))][["emp_key", "qual_key", "expires"]]
    bk = _days(booked[["emp_key", "qual_key", "course_date", "event_no", "free_seats"]], ["course_date"], "booked_renewals output")
    first = bk[bk["course_date"] > d].sort_values(["emp_key", "qual_key", "course_date"], kind="stable").drop_duplicates(["emp_key", "qual_key"])
    out = soon.merge(first, on=["emp_key", "qual_key"], how="left", validate="one_to_one")
    out["booked"] = out["course_date"].notna()
    out["gap_days"] = np.where(out["booked"], (out["course_date"] - out["expires"]).dt.days.sub(1).clip(lower=0), np.nan)
    out["as_of"] = d.to_datetime64().astype("datetime64[ns]")
    out = out[["emp_key", "qual_key", "as_of", "expires", "booked", "course_date", "event_no", "free_seats", "gap_days"]].sort_values(["expires", "emp_key", "qual_key"]).reset_index(drop=True)
    if used:
        out.attrs["policy_status"] = used
    return out


class ExpiryReport(NamedTuple):
    """Result of expiry_report: one row per current holder, the counts, the courses after the date and the holders of the second qualification."""

    frame: pd.DataFrame
    counts: dict[str, Any]
    events: pd.DataFrame
    holders: tuple[str, ...]


@staged(sources=("competence.certification_held.emp_key", "competence.certification_held.qual_key", "competence.certification_held.issued", "competence.certification_held.expires",
                   "competence.training_event.date", "competence.training_event.qual_key", "competence.training_event.capacity", "competence.training_event.seats_taken",
                   "hr.employee.leave_date", "hr.leave_record.leave_type", "hr.leave_record.start", "hr.leave_record.end"),
          parameters=("cert", "booked", "event", "employee", "leave_record", "as_of", "expiry_date", "qual_key", "holder_qual_key", "unavailable_leave_types"), facts=("policy.staffing.unavailable_leave_types",))
def expiry_report(cert: pd.DataFrame, booked: pd.DataFrame, event: pd.DataFrame, employee: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, *, expiry_date: dt.date, qual_key: str,
                 holder_qual_key: str | None = None, unavailable_leave_types: Sequence[str] | PolicyDefault = UNAVAILABLE_LEAVE_TYPES) -> ExpiryReport:
    """Use this when you need the people whose certificate for a qualification runs out on a given date: whether each has a renewal course booked, the free seats, and who is on leave during the course.

    Rule: the report covers people who hold qual_key on as_of (valid_on rule, issued to expires inclusive) with a certificate expiring on expiry_date and who have not left (a missing leave_date, or one on or after as_of, counts as current; a person with no hr.employee row is treated as left: not in the frame and counted in former_employees). Only the latest issue per person and qualification counts (valid_on), so a person who holds a later certificate is dropped from the frame and counted in superseded. Per person it takes the earliest booked course of qual_key (from booked_renewals) that starts after as_of, with its free seats; gap_days is 0 for a course starting on the expiry day or the day after, otherwise the course date minus the expiry date minus 1, and empty when nothing is booked; on_leave_at_course is true when a leave of an unavailable type overlaps any day of the course. Courses of the qualification after as_of are listed separately, and the holders of holder_qual_key are listed when it is given. expiry_date and qual_key are supplied by the caller. The unavailable leave types default to the fact policy.staffing.unavailable_leave_types (proposed).

    Args:
        cert: Certificate frame (competence.certification_held) with emp_key, qual_key, issued and expires; an empty expires is open.
        booked: Output of booked_renewals with emp_key, qual_key, course_date, course_end, event_no and free_seats.
        event: Training events (competence.training_event) with event_no, qual_key, date, capacity, seats_taken, country and location_site_key.
        employee: Employee frame (hr.employee) with emp_key, leave_date and legal_entity_key, one row per person.
        leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
        as_of: The date on which certificates are read; also the lower bound (exclusive) of the courses that count.
        expiry_date: The expiry date the report covers.
        qual_key: The qualification the report covers.
        holder_qual_key: A second qualification whose current valid holders are listed; None lists none.
        unavailable_leave_types: The leave types that count as absence (a list or one type); the default reads the fact policy.staffing.unavailable_leave_types.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        ExpiryReport, a named tuple of frame, counts, events and holders. frame is a pandas.DataFrame with emp_key, legal_entity_key, expires, booked, course_date, event_no, free_seats, gap_days and on_leave_at_course, one row per person sorted by emp_key. counts is a dict with the keys expiry_date, qual_key, n_expiring, n_booked, n_not_booked, rows_expiring_on_date, former_employees, superseded, n_holders and booked_on_leave_at_course. former_employees counts the certificate rows of qual_key expiring on expiry_date whose holder has left or has no hr.employee row; superseded counts such rows, still unexpired on as_of, whose holder has a later issue in force on as_of; rows_expiring_on_date counts all raw certificate rows of qual_key expiring on expiry_date, of any issue date. events is a pandas.DataFrame with event_no, date, country, location_site_key, capacity, seats_taken and free_seats. holders is a sorted tuple of emp_key.

    Raises:
        FrameError: a frame lacks a column, hr.employee has a duplicate emp_key, the certificate frame has duplicate columns, a missing key or issued date or an expiry before its issue, a date column holds numbers or text that is not a date, capacity or seats_taken of the training events is not a number, unavailable_leave_types is not a leave type name or a list of them (None, a number), or the leave type default lists no type.
        PeriodError: as_of or expiry_date is not a date without a time zone (the message names the argument).
        FactNotFound: the default leave types are used and the fact is not in the snapshot.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import expiry_report
        >>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01"] * 2, "issued": ["2023-01-01"] * 2, "expires": ["2026-12-31"] * 2})
        >>> booked = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "course_date": ["2026-10-10"], "course_end": ["2026-10-11"], "event_no": [7], "free_seats": [6]})
        >>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-10-10"], "capacity": [10], "seats_taken": [4], "country": ["DK"], "location_site_key": ["SITE-01"]})
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "leave_date": [None, None], "legal_entity_key": ["LE-01", "LE-01"]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["extended_leave"], "start": ["2026-09-01"], "end": [None]})
        >>> r = expiry_report(cert, booked, event, employee, leave, dt.date(2026, 6, 30), expiry_date=dt.date(2026, 12, 31), qual_key="QUAL-01", unavailable_leave_types=["extended_leave"])
        >>> r.frame[["emp_key", "booked", "free_seats"]].to_dict("records")
        [{'emp_key': 'EMP-000001', 'booked': True, 'free_seats': 6.0}, {'emp_key': 'EMP-000002', 'booked': False, 'free_seats': nan}]
        >>> r.counts["n_expiring"], r.counts["n_booked"], r.counts["n_not_booked"]
        (2, 1, 1)
    
    """
    _need(booked, ["emp_key", "qual_key", "course_date", "course_end", "event_no", "free_seats"], "booked_renewals output")
    _need(event, ["event_no", "qual_key", "date", "capacity", "seats_taken", "country", "location_site_key"], "competence.training_event")
    _need(employee, ["emp_key", "leave_date", "legal_entity_key"], "hr.employee")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    if employee["emp_key"].duplicated().any():
        raise FrameError("hr.employee has duplicate emp_key values; one row per person is required")
    leave_types_given(unavailable_leave_types, "unavailable_leave_types")
    d, expiry = _day(as_of), _day(expiry_date, "expiry_date")
    c = _certs(cert)
    types = unavailable_types(unavailable_leave_types)
    emp = _days(employee[["emp_key", "leave_date", "legal_entity_key"]], ["leave_date"], "hr.employee").set_index("emp_key")
    leave = emp["leave_date"]
    current = lambda keys: keys.map(lambda k: k in leave.index and (pd.isna(leave[k]) or leave[k] >= d)).astype(bool)
    on_expiry = c[(c["qual_key"] == qual_key) & (c["expires"] == expiry)]
    valid = valid_on(cert, d)
    holders_now = valid[(valid["qual_key"] == qual_key) & (valid["expires"] == expiry)]
    people = holders_now[current(holders_now["emp_key"]).to_numpy()]
    bk = _days(booked[booked["qual_key"] == qual_key], ["course_date", "course_end"], "booked_renewals output")
    bk = bk[bk["course_date"] > d].sort_values(["emp_key", "course_date"], kind="stable").drop_duplicates("emp_key")
    out = people[["emp_key", "expires"]].merge(bk[["emp_key", "course_date", "course_end", "event_no", "free_seats"]], on="emp_key", how="left", validate="one_to_one")
    out["booked"] = out["course_date"].notna()
    lr = _days(leave_record, ["start", "end"], "hr.leave_record")
    lr = lr[lr["leave_type"].isin(types)][["emp_key", "start", "end"]]
    hit = out.loc[out["booked"], ["emp_key", "course_date", "course_end"]].merge(lr, on="emp_key", how="inner")
    hit = hit[(hit["start"] <= hit["course_end"]) & (hit["end"].isna() | (hit["end"] >= hit["course_date"]))]
    out["on_leave_at_course"] = out["emp_key"].isin(set(hit["emp_key"])).astype(bool)
    out["gap_days"] = ((out["course_date"] - out["expires"]).dt.days - 1).clip(lower=0).astype("float64")
    out["legal_entity_key"] = out["emp_key"].map(emp["legal_entity_key"])
    out = out[["emp_key", "legal_entity_key", "expires", "booked", "course_date", "event_no", "free_seats", "gap_days", "on_leave_at_course"]].sort_values("emp_key").reset_index(drop=True)
    ev = _days(event, ["date"], "competence.training_event")
    ev = ev[(ev["qual_key"] == qual_key) & (ev["date"] > d)].sort_values(["date", "event_no"])
    try:
        free = ev["capacity"] - ev["seats_taken"]
    except TypeError:
        raise FrameError("competence.training_event capacity and seats_taken must be numbers") from None
    events = ev.assign(free_seats=free)[["event_no", "date", "country", "location_site_key", "capacity", "seats_taken", "free_seats"]].reset_index(drop=True)
    holders = ()
    if holder_qual_key is not None:
        h = valid[(valid["qual_key"] == holder_qual_key) & current(valid["emp_key"]).to_numpy()]
        holders = tuple(sorted(h["emp_key"]))
    gone = ~current(on_expiry["emp_key"]).to_numpy()
    sup = on_expiry[_superseded(c, d)[on_expiry.index].to_numpy() & (on_expiry["expires"] >= d).to_numpy()]
    counts = {"expiry_date": expiry.date(), "qual_key": qual_key, "n_expiring": len(out), "n_booked": int(out["booked"].sum()), "n_not_booked": int((~out["booked"]).sum()),
              "rows_expiring_on_date": len(on_expiry), "former_employees": int(gone.sum()), "superseded": len(sup), "n_holders": len(holders),
              "booked_on_leave_at_course": int(out["on_leave_at_course"].sum())}
    return ExpiryReport(out, counts, events, holders)


def _check_education(education: pd.DataFrame) -> None:
    """The one rule for competence.education_record, shared by education_level and pay.with_education: emp_key and level_rank present, no null emp_key, level_rank whole numbers, zero or more, no nulls."""
    _need(education, ("emp_key", "level_rank"), "competence.education_record")
    lr = education["level_rank"]
    if len(lr) and (lr.isna().any() or not pd.api.types.is_numeric_dtype(lr) or (lr % 1 != 0).any() or (lr < 0).any()):
        raise FrameError("competence.education_record.level_rank must be whole numbers, zero or more, without nulls")
    if education["emp_key"].isna().any():
        raise FrameError("competence.education_record has a null emp_key")


@staged(sources=("competence.education_record.emp_key", "competence.education_record.level_rank"))
def education_level(education: pd.DataFrame) -> pd.Series:
    """Use this when you need the highest education level of each person from the education records.

    Rule: the highest level_rank per person; people without a record are not in the result. The rank scale is in the competence config.

    Args:
        education: Education record frame (competence.education_record) with emp_key and level_rank (whole numbers, zero or more, no nulls).
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.Series named education_rank, indexed by emp_key and sorted by it.

    Raises:
        FrameError: a column is missing, a key is null, or level_rank is not a whole number of zero or more.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import education_level
        >>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001", "EMP-000002"], "level_rank": [2, 3, 1]})
        >>> education_level(education).to_dict()
        {'EMP-000001': 3, 'EMP-000002': 1}
    """
    _check_education(education)
    return education.groupby("emp_key")["level_rank"].max().astype("int64").rename("education_rank").sort_index()


@staged(sources=("competence.skill_rating.emp_key", "competence.skill_rating.skl_key", "competence.skill_rating.level", "competence.skill_rating.assessed_on", "competence.skill.name"),
          oracle="py:tests/test_competence.py::test_candidates_by_skill_are_findable")
def skill_latest(skill_rating: pd.DataFrame, skill: pd.DataFrame, as_of: dt.date | None = None) -> pd.DataFrame:
    """Use this when you need the latest rating of each person and skill, with the name of the skill.

    Rule: the latest rating is the one with the highest assessed_on. On the same day the higher round_no wins when the column exists (a null round_no loses to any number), then the higher level. With as_of only ratings assessed on or before that date count.

    Args:
        skill_rating: Rating frame (competence.skill_rating) with emp_key, skl_key, level and assessed_on.
        skill: Skill frame (competence.skill) with skl_key and name, one row per skill.
        as_of: Optional date; later ratings are ignored.
        context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

    Returns:
        pandas.DataFrame: emp_key, skl_key, name, level and assessed_on, sorted by emp_key and skl_key.

    Raises:
        FrameError: a frame lacks a column, skl_key is duplicated in the skill frame, a rating has a null emp_key, skl_key, level or assessed_on, or a rating points at a skill that is not in the skill frame.
        StageRefusal: a context is given and its stage does not hold the competence source.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import skill_latest
        >>> rating = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "skl_key": ["SKL-1", "SKL-1"], "level": [2, 3], "assessed_on": ["2025-01-01", "2026-01-01"]})
        >>> skill = pd.DataFrame({"skl_key": ["SKL-1"], "name": ["Welding"]})
        >>> skill_latest(rating, skill, dt.date(2025, 12, 31))[["name", "level"]].to_dict("records")
        [{'name': 'Welding', 'level': 2}]
    """
    _need(skill_rating, ("emp_key", "skl_key", "level", "assessed_on"), "competence.skill_rating")
    _need(skill, ("skl_key", "name"), "competence.skill")
    if skill["skl_key"].duplicated().any():
        raise FrameError("competence.skill has duplicate skl_key values")
    r = _days(skill_rating, ["assessed_on"], "competence.skill_rating")
    if r["assessed_on"].isna().any() or r["level"].isna().any() or r["emp_key"].isna().any() or r["skl_key"].isna().any():
        raise FrameError("competence.skill_rating has rows with a null emp_key, skl_key, level or assessed_on")
    if as_of is not None:
        r = r[r["assessed_on"] <= _day(as_of)]
    order = ["emp_key", "skl_key", "assessed_on"] + (["round_no"] if "round_no" in r.columns else []) + ["level"]
    last = r.sort_values(order, kind="stable", na_position="first").drop_duplicates(["emp_key", "skl_key"], keep="last")
    out = last.merge(skill[["skl_key", "name"]], on="skl_key", how="left", validate="many_to_one")
    if out["name"].isna().any():
        raise FrameError(f"{int(out['name'].isna().sum())} ratings point at a skl_key that is not in competence.skill (for example {out.loc[out['name'].isna(), 'skl_key'].iloc[0]})")
    return out[["emp_key", "skl_key", "name", "level", "assessed_on"]].sort_values(["emp_key", "skl_key"]).reset_index(drop=True)
