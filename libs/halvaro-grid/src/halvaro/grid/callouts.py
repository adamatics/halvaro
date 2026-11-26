"""Call-outs and service levels (plan 5.8): tickets, labour and overtime by team and period, the on-call rota, SLA attainment recomputed on the service-hours clock, work that needs electrical authorisation.

The service hours (07:00 to 16:00 on working days), the planned-work grace and the tolerance are keywords marked PROPOSED (config/service.yaml hours.start, hours.end and planned.grace_days; facts needed).
Labour is attributed to the day it was worked (`work_date`), tickets to the UTC month or week they were opened, so overtime is counted by the date it was worked.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, is_working_day

from ._guard import staged
from ._util import _need, _utc
from ._types import DateLike, Window
from .series import _TIMEZONES, _zone
from ._tail import value_text

_COUNTRY_OF_REGION = {"DK": "DK", "DE-HH": "DE"}                  # PROPOSED: time zone country of a holiday region (core calendar regions)
_PLANNED = ("preventive", "inspection")


def _day_series(values: Any, what: str) -> pd.Series[Any]:
    s = pd.Series(values)
    try:
        x = pd.to_datetime(s)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what} holds a value that is not a date: {e}") from None
    if getattr(x.dt, "tz", None) is not None:
        raise FrameError(f"{what} has a time zone; these are calendar days")
    return cast("pd.Series[Any]", x.dt.normalize())


def _flag(series: pd.Series[Any], what: str) -> pd.Series[Any]:
    """A true/false column as booleans: only real booleans are accepted. Text such as 'False' would read as true in a cast, so it raises."""
    if series.isna().any():
        raise FrameError(f"{what} has nulls")
    if not all(isinstance(v, (bool, np.bool_)) for v in series):
        raise FrameError(f"{what} must hold true or false, not text or numbers")
    return cast("pd.Series[Any]", series.astype(bool))


def _period(day: pd.Series[Any], freq: str) -> pd.Series[Any]:
    if freq == "month":
        return cast("pd.Series[Any]", day.dt.strftime("%Y-%m"))
    return cast("pd.Series[Any]", (day - pd.to_timedelta(day.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d"))


def _window(window: Any) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if window is None:
        return None
    try:
        lo, hi = pd.Timestamp(window[0]).normalize(), pd.Timestamp(window[1]).normalize()
    except (TypeError, ValueError, IndexError):
        raise FrameError(f"window must be two dates (first day, last day, both included) (got {value_text(window)})") from None
    if hi < lo:
        raise FrameError(f"window ends before it starts (got {value_text(window)})")
    return lo, hi


@staged(sources=("service.service_ticket.tkt_key", "service.service_ticket.team_key", "service.service_ticket.opened", "service.service_ticket.callout_kind",
                 "service.ticket_labour.tkt_key", "service.ticket_labour.work_date", "service.ticket_labour.hours", "service.ticket_labour.overtime_hours", "service.ticket_labour.travel_hours"),
        oracle="py:tests/test_service.py::test_labour_overtime_and_collisions")
def callout_summary(service_ticket: pd.DataFrame, ticket_labour: pd.DataFrame, *, freq: str = "month", window: Window | None = None, tolerance: float = 0.02) -> pd.DataFrame:
    """Use this when you need tickets, labour hours, overtime hours and travel hours by team, period and call-out kind.

    Columns: team_key, period (the UTC month as YYYY-MM, or the Monday of the week), callout_kind, n_tickets (tickets opened in the period), labour_hours, overtime_hours, travel_hours (worked in the period, by `work_date`, by the team of the labour row
    when the column exists, otherwise the ticket's team, on tickets of that kind; `hours` already holds overtime and travel, as the ticket totals do).
    `window` is two days (both included): for tickets the UTC date of `opened`, for labour the local `work_date`, which are two clocks (a ticket opened late in the evening UTC belongs to the next local day); `freq` is month or week.
    A labour row whose ticket is unknown, or a ticket whose labour sums differ from its own hour columns by more than `tolerance` hours (0.02, the generator test), raises FrameError when the ticket has the columns labour_hours, overtime_hours
    and travel_hours. Person level rows are never returned.

    Args:
        service_ticket: The service.service_ticket frame, columns tkt_key, team_key, opened and callout_kind; optionally labour_hours, overtime_hours and travel_hours, which are then checked against the labour rows.
        ticket_labour: The service.ticket_labour frame, columns tkt_key, work_date, hours, overtime_hours and travel_hours; optionally team_key.
        freq: "month" (default) or "week": the size of the period.
        window: Optional two days (first day, last day, both included) that limit tickets (by the UTC date of opened) and labour (by work_date).
        tolerance: Largest allowed difference in hours between a ticket's own hour columns and the sum of its labour rows (default 0.02); zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns team_key, period, callout_kind, n_tickets, labour_hours, overtime_hours and travel_hours (hours rounded to two decimals, zero where nothing was worked), sorted by team_key, period and callout_kind.

    Raises:
        FrameError: a column of service_ticket or ticket_labour is missing; freq is not month or week; service_ticket repeats a tkt_key; tolerance is negative or not a number; window is not two dates or ends before it starts;
            opened or work_date is not a date on every row (or has a time zone, for work_date); ticket_labour has rows for tickets that service_ticket does not hold; ticket_labour has null hours; a ticket hour column has nulls or differs from the labour sum by more than tolerance.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import callout_summary
        >>> ctx = Context(stage="month12", role="analyst")
        >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "team_key": ["TEAM-900001", "TEAM-900001"],
        ...                   "opened": pd.to_datetime(["2025-03-03 08:00", "2025-03-10 09:00"]), "callout_kind": ["standby", "standby"]})
        >>> lab = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "work_date": ["2025-03-03", "2025-03-10"],
        ...                     "hours": [3.0, 2.0], "overtime_hours": [1.0, 0.0], "travel_hours": [0.5, 0.5]})
        >>> out = callout_summary(t, lab, context=ctx)
        >>> out[["period", "n_tickets", "labour_hours", "overtime_hours"]].to_dict("records")
        [{'period': '2025-03', 'n_tickets': 2, 'labour_hours': 5.0, 'overtime_hours': 1.0}]
    """
    _need(service_ticket, ["tkt_key", "team_key", "opened", "callout_kind"], "service.service_ticket")
    _need(ticket_labour, ["tkt_key", "work_date", "hours", "overtime_hours", "travel_hours"], "service.ticket_labour")
    if freq not in ("month", "week"):
        raise FrameError(f"freq must be 'month' or 'week' (got {value_text(freq)})")
    if service_ticket["tkt_key"].duplicated().any():
        raise FrameError("service.service_ticket has more than one row for a ticket")
    if isinstance(tolerance, bool) or not tolerance >= 0:
        raise FrameError(f"tolerance must be zero or more (got {value_text(tolerance)})")
    win = _window(window)
    service_ticket, ticket_labour = service_ticket.reset_index(drop=True), ticket_labour.reset_index(drop=True)
    t = service_ticket.assign(day=_day_series(_utc(service_ticket["opened"], "service.service_ticket.opened").to_numpy(), "opened"))
    if t["day"].isna().any() or ticket_labour["work_date"].isna().any():
        raise FrameError("service.service_ticket.opened and service.ticket_labour.work_date must be dates on every row")
    if not set(ticket_labour["tkt_key"]).issubset(set(t["tkt_key"])):
        raise FrameError("service.ticket_labour has rows for tickets that service.service_ticket does not hold")
    lab = ticket_labour[["tkt_key", "work_date", "hours", "overtime_hours", "travel_hours"]].copy()
    if lab[["hours", "overtime_hours", "travel_hours"]].isna().any().any():
        raise FrameError("service.ticket_labour has null hours")
    sums = lab.groupby("tkt_key")[["hours", "overtime_hours", "travel_hours"]].sum().reindex(t["tkt_key"]).fillna(0.0)
    for col_t, col_l in (("labour_hours", "hours"), ("overtime_hours", "overtime_hours"), ("travel_hours", "travel_hours")):
        if col_t in t.columns:
            j = t.set_index("tkt_key")[col_t]
            if j.isna().any():
                raise FrameError(f"service.service_ticket.{col_t} has nulls")
            if ((j - sums[col_l]).abs() > tolerance + 1e-9).any():
                raise FrameError(f"labour {col_l} differs from service.service_ticket.{col_t} by more than {tolerance} h for a ticket (a ticket without labour rows counts as zero hours)")
    lab["day"] = _day_series(lab["work_date"], "service.ticket_labour.work_date")
    if "team_key" in ticket_labour.columns:
        lab["team_key"] = ticket_labour["team_key"].to_numpy()
        lab = lab.merge(t[["tkt_key", "callout_kind"]], on="tkt_key")
    else:
        lab = lab.merge(t[["tkt_key", "team_key", "callout_kind"]], on="tkt_key")
    if win is not None:
        t = t[t["day"].between(*win)]
        lab = lab[lab["day"].between(*win)]
    tk = t.assign(period=_period(t["day"], freq)).groupby(["team_key", "period", "callout_kind"], as_index=False, dropna=False, observed=True).agg(n_tickets=("tkt_key", "size"))
    lb = lab.assign(period=_period(lab["day"], freq)).groupby(["team_key", "period", "callout_kind"], as_index=False, dropna=False, observed=True).agg(
        labour_hours=("hours", "sum"), overtime_hours=("overtime_hours", "sum"), travel_hours=("travel_hours", "sum"))
    out = tk.merge(lb, on=["team_key", "period", "callout_kind"], how="outer")
    out["n_tickets"] = out["n_tickets"].fillna(0).astype(int)
    for c in ("labour_hours", "overtime_hours", "travel_hours"):
        out[c] = out[c].fillna(0.0).round(2)
    return out.sort_values(["team_key", "period", "callout_kind"]).reset_index(drop=True)


@staged(sources=("service.on_call_rota.team_key", "service.on_call_rota.week_start", "service.on_call_rota.primary_emp_key", "service.on_call_rota.secondary_emp_key"), oracle="py:repo_tests/test_oracle_callouts_release.py::test_oracle_on_call_baseline_every_day_every_team")
def on_call(on_call_rota: pd.DataFrame, on_date: DateLike, *, team_key: str | None = None, days: int = 7) -> pd.DataFrame:
    """Use this when you need who is primary and secondary on call on a given date, per team.

    The rota row of each team that started on or before the date and ends where the next row of the team starts; the last row of a team runs `days` (7) days. A team without a row for the date is not listed. `team_key` narrows to one team or a list.

    Args:
        on_call_rota: The service.on_call_rota frame, columns team_key, week_start, primary_emp_key and secondary_emp_key.
        on_date: The date to look up.
        team_key: Optional team key, or a list of team keys, to narrow the result; all teams when omitted.
        days: How many days a row runs at most, and how long the last row of a team runs (default 7); a whole number of one or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns team_key, week_start, primary_emp_key and secondary_emp_key, one row per team on call on the date, sorted by team_key.

    Raises:
        FrameError: a column of on_call_rota is missing; days is not a whole number of one or more; on_date is not a date; a week_start is not a date or is missing (or has a time zone); the rota has more than one row for a team and week.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import on_call
        >>> ctx = Context(stage="month12", role="analyst")
        >>> r = pd.DataFrame({"team_key": ["TEAM-900001", "TEAM-900001"], "week_start": ["2025-03-03", "2025-03-10"],
        ...                   "primary_emp_key": ["EMP-900001", "EMP-900002"], "secondary_emp_key": ["EMP-900003", "EMP-900004"]})
        >>> out = on_call(r, "2025-03-12", context=ctx)
        >>> out[["team_key", "primary_emp_key", "secondary_emp_key"]].to_dict("records")
        [{'team_key': 'TEAM-900001', 'primary_emp_key': 'EMP-900002', 'secondary_emp_key': 'EMP-900004'}]
    """
    _need(on_call_rota, ["team_key", "week_start", "primary_emp_key", "secondary_emp_key"], "service.on_call_rota")
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise FrameError(f"days must be a whole number of days, one or more (got {value_text(days)})")
    d = _day_series([on_date], "on_date").iloc[0]
    if pd.isna(d):
        raise FrameError(f"on_date must be a date (got {value_text(on_date)})")
    r = on_call_rota.assign(week_start=_day_series(on_call_rota["week_start"], "service.on_call_rota.week_start").to_numpy())
    if r["week_start"].isna().any():
        raise FrameError("service.on_call_rota has a row without a week start")
    if r.duplicated(["team_key", "week_start"]).any():
        raise FrameError("service.on_call_rota has more than one row for a team and week")
    r = r.sort_values(["team_key", "week_start"], kind="stable")
    nxt = r.groupby("team_key")["week_start"].shift(-1)
    end = nxt.where(nxt.notna() & (nxt <= r["week_start"] + pd.Timedelta(days=days)), r["week_start"] + pd.Timedelta(days=days))      # a row runs to the next row of its team, at most `days` days
    x = r[(r["week_start"] <= d) & (d < end)]
    if team_key is not None:
        x = x[x["team_key"].isin([team_key] if isinstance(team_key, str) else list(team_key))]
    return cast(pd.DataFrame, x[["team_key", "week_start", "primary_emp_key", "secondary_emp_key"]].sort_values("team_key").reset_index(drop=True))


def _clock(local: pd.Series[Any], region: str, start: float, end: float, origin: pd.Timestamp) -> np.ndarray[Any, Any]:
    """Cumulative service hours since the `origin` day at each local naive timestamp: `end - start` hours for every earlier working day of the region plus the hours of the day inside [start, end].
    Differences of two clocks are only meaningful with the same origin."""
    day = local.dt.normalize()
    lo, hi = origin, max(day.max(), origin)
    days = pd.date_range(lo, hi, freq="D")
    wk = np.array([is_working_day(d.date(), region) for d in days], dtype=float)
    cum = np.concatenate([[0.0], np.cumsum((end - start) * wk)])
    idx = ((day - lo).dt.days).to_numpy()
    h = ((local - day).dt.total_seconds() / 3600.0).to_numpy()
    return cast("np.ndarray[Any, Any]", cum[idx] + wk[idx] * np.clip(h - start, 0.0, end - start))


def _local_naive(ts: pd.Series[Any], region: str, what: str, country_of_region: Mapping[str, str]) -> pd.Series[Any]:
    if region not in country_of_region:
        raise FrameError(f"no time zone country for the region {region!r}; known: {sorted(country_of_region)}")
    zone = _zone(_TIMEZONES[country_of_region[region]])
    return cast("pd.Series[Any]", ts.dt.tz_localize("UTC").dt.tz_convert(zone).dt.tz_localize(None))


@staged(sources=("service.service_ticket.tkt_key", "service.service_ticket.team_key", "service.service_ticket.opened", "service.service_ticket.first_response_ts", "service.service_ticket.on_site_ts",
                 "service.service_ticket.resolved_ts", "service.service_ticket.due_date", "service.service_ticket.ticket_type", "service.service_ticket.sla_met",
                 "service.service_ticket.sla_response_target_h", "service.service_ticket.sla_attendance_target_h", "service.service_ticket.priority", "service.service_ticket.status"),
        oracle="py:tests/test_service.py::test_sla_and_credits")
def sla_attainment(service_ticket: pd.DataFrame, *, team_region: Mapping[str, str] | None = None, by: tuple[str, ...] = ("team_key", "priority"), service_start: float = 7.0, service_end: float = 16.0,
                   grace_days: int = 14, tolerance_h: float = 0.01, country_of_region: Mapping[str, str] = _COUNTRY_OF_REGION) -> pd.DataFrame:
    """Use this when you need the share of tickets that met their service level, per group such as team and priority, optionally recomputed on the service-hours clock.

    The share uses `sla_met` as stored, per group of `by` (default team and priority).
    With `team_region` (team key to holiday region, for example {'TEAM-900001': 'DK'}) the verdict is recomputed and the columns n_recomputed, n_recomputed_met, share_recomputed_met,
    n_hours_differ (response or attendance hours that differ from the stored ones by more than `tolerance_h`, 0.01) and n_verdict_differs are added. The recompute is the generator's rule:
    response_h and attendance_h (rounded to two decimals, as stored) are the service hours (working days of the team's region, `service_start` 7 to `service_end` 16 local time, PROPOSED config hours) between opened and the first response or the
    arrival; a corrective or enquiry ticket that is not cancelled and has a first response is met when response_h is within its target and attendance_h within its target (no arrival counts as in target);
    a planned ticket (preventive, inspection) is met when resolved on or before the due date plus `grace_days` (14, PROPOSED config planned.grace_days). Credits and money are not computed here.

    Args:
        service_ticket: The service.service_ticket frame, columns tkt_key, team_key, opened, ticket_type, sla_met and priority, plus the `by` columns. With `team_region` also first_response_ts, on_site_ts, resolved_ts, due_date, sla_response_target_h, sla_attendance_target_h, status, response_h and attendance_h.
        team_region: Optional mapping of team key to holiday region (DK or DE-HH by default); when given, the verdict is recomputed. Every team of the frame needs a region.
        by: The columns to group by (default team_key and priority); at least one.
        service_start: Hour of the day when service hours start (PROPOSED 7.0); with service_end it must satisfy 0 <= start < end <= 24.
        service_end: Hour of the day when service hours end (PROPOSED 16.0).
        grace_days: Days after the due date within which a planned ticket still counts as met (PROPOSED 14); a whole number of zero or more.
        tolerance_h: Largest difference in hours between recomputed and stored response or attendance hours that is not counted as differing (default 0.01).
        country_of_region: PROPOSED mapping of holiday region to the country whose time zone applies (default DK to DK, DE-HH to DE).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the `by` columns, n_tickets, n_assessed (stored sla_met not null), n_met and share_met (null when nothing is assessed); with `team_region` also n_recomputed, n_recomputed_met, share_recomputed_met, n_hours_differ and n_verdict_differs. Sorted by the `by` columns.

    Raises:
        FrameError: a column of service_ticket or of `by` is missing; by is empty; sla_met holds text or numbers; service_ticket repeats a tkt_key; the service hours do not satisfy 0 <= start < end <= 24; with team_region: grace_days is not a whole number of zero or more,
            a team has no region (or a null team), opened has a null, a region has no time zone country, or a first response or an arrival lies before the ticket was opened.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import sla_attainment
        >>> ctx = Context(stage="month12", role="analyst")
        >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002", "TKT-900003"], "team_key": "TEAM-900001", "opened": pd.to_datetime(["2025-03-03 08:00"] * 3),
        ...                   "ticket_type": "corrective", "sla_met": [True, False, True], "priority": "high"})
        >>> out = sla_attainment(t, context=ctx)
        >>> out[["team_key", "priority", "n_tickets", "n_assessed", "n_met", "share_met"]].to_dict("records")
        [{'team_key': 'TEAM-900001', 'priority': 'high', 'n_tickets': 3, 'n_assessed': 3, 'n_met': 2, 'share_met': 0.6667}]
    """
    _need(service_ticket, ["tkt_key", "team_key", "opened", "ticket_type", "sla_met", "priority"], "service.service_ticket")
    by = tuple(by)
    if not by:
        raise FrameError(f"by needs at least one column (got {value_text(by)})")
    _need(service_ticket, list(by), "service.service_ticket")
    if not all(isinstance(v, (bool, np.bool_)) for v in service_ticket["sla_met"].dropna()):
        raise FrameError("service.service_ticket.sla_met must hold true or false (or null), not text or numbers")
    if service_ticket["tkt_key"].duplicated().any():
        raise FrameError("service.service_ticket has more than one row for a ticket")
    if not 0 <= service_start < service_end <= 24:
        raise FrameError("service hours must satisfy 0 <= start < end <= 24")
    st = service_ticket.reset_index(drop=True)
    met = st["sla_met"].astype("boolean")
    g = st.assign(_assessed=met.notna(), _met=met.fillna(False).astype(bool))
    out = g.groupby(list(by), as_index=False, dropna=False, observed=True).agg(n_tickets=("tkt_key", "size"), n_assessed=("_assessed", "sum"), n_met=("_met", "sum"))
    out["share_met"] = (out["n_met"] / out["n_assessed"].where(out["n_assessed"] > 0)).round(4)
    if team_region is None:
        return out.sort_values(list(by)).reset_index(drop=True)
    _need(st, ["first_response_ts", "on_site_ts", "resolved_ts", "due_date", "sla_response_target_h", "sla_attendance_target_h", "status", "response_h", "attendance_h"], "service.service_ticket")
    if isinstance(grace_days, bool) or not isinstance(grace_days, int) or grace_days < 0:
        raise FrameError(f"grace_days must be a whole number of days, zero or more (got {value_text(grace_days)})")
    missing = sorted(set(st["team_key"].dropna().astype(str)) - set(team_region))
    if missing or st["team_key"].isna().any():
        raise FrameError(f"team_region has no region for team(s) {missing or ['(null)']}")
    if st["opened"].isna().any():
        raise FrameError("service.service_ticket.opened must be a time on every row")
    resp, att = pd.Series(np.nan, index=st.index), pd.Series(np.nan, index=st.index)
    verdict = pd.Series(pd.NA, index=st.index, dtype="boolean")
    planned = st["ticket_type"].isin(_PLANNED)
    for region in sorted(set(team_region[t] for t in st["team_key"].astype(str).unique())):
        m = st["team_key"].astype(str).map(team_region) == region
        if not m.any():
            continue
        op = _local_naive(_utc(st.loc[m, "opened"], "opened"), region, "opened", country_of_region)
        origin = op.dt.normalize().min()
        co = pd.Series(_clock(op, region, service_start, service_end, origin), index=op.index)
        for src, dst in (("first_response_ts", resp), ("on_site_ts", att)):
            s = _utc(st.loc[m, src], src)
            ok = s.notna()
            if ok.any():
                loc = _local_naive(s[ok], region, src, country_of_region)
                if (loc.dt.normalize() < origin).any():
                    raise FrameError("a first response or an arrival lies before the ticket was opened")
                dst.loc[loc.index] = _clock(loc, region, service_start, service_end, origin) - co.loc[loc.index].to_numpy()
    if ((resp < 0) | (att < 0)).any():
        raise FrameError("a first response or an arrival lies before the ticket was opened")
    resp, att = resp.round(2), att.round(2)                                       # the stored hours are rounded to 2 decimals before they are compared with the targets
    resp[planned], att[planned] = np.nan, np.nan
    corr = ~planned & (st["status"] != "cancelled")
    ok_r = resp.le(st["sla_response_target_h"] + 1e-9)
    ok_a = st["on_site_ts"].isna() | att.le(st["sla_attendance_target_h"] + 1e-9)
    known = st["first_response_ts"].notna()
    verdict[corr & known] = (ok_r & ok_a)[corr & known].astype("boolean")
    due = pd.to_datetime(st["due_date"])
    done = _utc(st["resolved_ts"], "resolved_ts")
    pl = planned & done.notna() & due.notna()
    if pl.any():
        loc = pd.Series(pd.NaT, index=st.index, dtype="datetime64[ns]")
        for team, region in team_region.items():
            mm = pl & (st["team_key"].astype(str) == team)
            if mm.any():
                loc[mm] = _local_naive(done[mm], region, "resolved_ts", country_of_region).dt.normalize()
        verdict[pl] = (loc[pl] <= due[pl] + pd.Timedelta(days=grace_days)).astype("boolean")
    differs_h = ((resp.notna() != st["response_h"].notna()) | (att.notna() != st["attendance_h"].notna()) |
                 ((resp - st["response_h"]).abs() > tolerance_h + 1e-9) | ((att - st["attendance_h"]).abs() > tolerance_h + 1e-9))
    differs_v = verdict.notna() & met.notna() & (verdict != met) | (verdict.notna() != met.notna())
    g = g.assign(_rv=verdict.notna(), _rm=verdict.fillna(False).astype(bool), _dh=differs_h, _dv=differs_v)
    extra = g.groupby(list(by), as_index=False, dropna=False, observed=True).agg(n_recomputed=("_rv", "sum"), n_recomputed_met=("_rm", "sum"), n_hours_differ=("_dh", "sum"), n_verdict_differs=("_dv", "sum"))
    out = out.merge(extra, on=list(by))
    out["share_recomputed_met"] = (out["n_recomputed_met"] / out["n_recomputed"].where(out["n_recomputed"] > 0)).round(4)
    return out.sort_values(list(by)).reset_index(drop=True)


@staged(sources=("service.maintenance_plan.net_key", "service.maintenance_plan.plan_no", "service.maintenance_plan.plan_type", "service.maintenance_plan.requires_electrical_authorisation",
                 "service.maintenance_plan.team_key", "service.maintenance_plan.status"), oracle="py:repo_tests/test_oracle_callouts_release.py::test_oracle_requires_authorisation_baseline_per_team_and_plan_type")
def requires_authorisation(maintenance_plan: pd.DataFrame, *, active_status: tuple[str, ...] = ("active",)) -> pd.DataFrame:
    """Use this when you need how many active maintenance plans need electrical authorisation, per team and plan type.

    The active plans with the flag `requires_electrical_authorisation` are counted. Who holds the authorisation is competence data and not read here (halvaro-hr).

    Args:
        maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, requires_electrical_authorisation (true or false), team_key and status.
        active_status: The statuses that count as active (default only "active"); a tuple, not a single text.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns team_key, plan_type, n_plans, n_requiring and share_requiring (rounded to four decimals), sorted by team_key and plan_type; an empty frame with these columns when no plan is active.

    Raises:
        FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; the flag has nulls or holds text or numbers; active_status is a single text.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import requires_authorisation
        >>> ctx = Context(stage="month12", role="analyst")
        >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "plan_no": [1, 1, 1], "plan_type": "condition_inspection",
        ...                   "requires_electrical_authorisation": [True, False, True], "team_key": "TEAM-900001", "status": ["active", "active", "closed"]})
        >>> out = requires_authorisation(p, context=ctx)
        >>> out[["team_key", "plan_type", "n_plans", "n_requiring", "share_requiring"]].to_dict("records")
        [{'team_key': 'TEAM-900001', 'plan_type': 'condition_inspection', 'n_plans': 2, 'n_requiring': 1, 'share_requiring': 0.5}]
    """
    _need(maintenance_plan, ["net_key", "plan_no", "plan_type", "requires_electrical_authorisation", "team_key", "status"], "service.maintenance_plan")
    if maintenance_plan.duplicated(["net_key", "plan_no"]).any():
        raise FrameError("service.maintenance_plan has more than one row for an element and plan number")
    flag = _flag(maintenance_plan["requires_electrical_authorisation"], "service.maintenance_plan.requires_electrical_authorisation")
    if isinstance(active_status, (str, bytes)):
        raise FrameError(f"active_status must be a tuple of statuses, not a single text (got {value_text(active_status)})")
    keep = maintenance_plan["status"].isin(list(active_status)).to_numpy()
    p = maintenance_plan[keep].assign(_req=flag.to_numpy()[keep])               # by position: a Series assigned to an empty frame would bring its index along
    if p.empty:
        return pd.DataFrame(columns=["team_key", "plan_type", "n_plans", "n_requiring", "share_requiring"])
    g = p.groupby(["team_key", "plan_type"], as_index=False, dropna=False, observed=True).agg(n_plans=("net_key", "size"), n_requiring=("_req", "sum"))
    g["share_requiring"] = (g["n_requiring"] / g["n_plans"]).round(4)
    return g.sort_values(["team_key", "plan_type"]).reset_index(drop=True)
