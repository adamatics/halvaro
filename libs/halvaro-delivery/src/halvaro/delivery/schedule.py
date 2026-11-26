"""Schedule: overrun against the plan, delay event days, plan version slip, milestones, plan against actual per activity (plan 5.1). Row level results keep the source columns and add derived ones; aggregates (delay_days, activity_plan_vs_actual) keep the keys."""
from __future__ import annotations

import datetime as dt
from typing import NamedTuple, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from .projects import _day, _days, _need, _status

_KB = ("DA.REF.212",)
_KB_PLAN = ("DA.REF.212",)      # kb-halvaro-delivery/delay-causes-and-contingency and plan-versions-and-milestones are planned, not written
_O3 = "py:tests/test_projects.py::test_cell_calibration"
_O4 = "py:tests/test_projects.py::test_story_project"
_O5 = "py:tests/test_projects.py::test_milestones_and_plans"
_NOW = ("world.now",)          # the release date: the stored actuals and forecasts are the state on it


def _frame_need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    if frame.columns.duplicated().any():
        raise FrameError(f"{what} has duplicate column names ({', '.join(map(str, frame.columns[frame.columns.duplicated()]))})")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys:
        if frame[list(keys)].isna().any().any():
            raise FrameError(f"{what} has rows with a null in {', '.join(keys)}")
        dup = frame[frame.duplicated(list(keys), keep=False)]
        if len(dup):
            raise FrameError(f"{what} has {len(dup)} rows sharing {', '.join(keys)} (for example {dup.iloc[0][keys[0]]}); one row per key is required")


def _date_col(frame: pd.DataFrame, column: str, what: str) -> pd.Series:
    try:
        out = pd.to_datetime(frame[column])
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"{what}.{column} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"{what}.{column} has a time zone; dates here are calendar days")
    return out.dt.normalize()


@staged(sources=("projects.project.prj_key", "projects.project.start", "projects.project.planned_end", "projects.project.actual_end", "projects.project.forecast_end"),
        facts=_NOW, kb=_KB_PLAN, oracle=_O3)
def schedule_overrun(project: pd.DataFrame, as_of: dt.date, *, include_forecast: bool = True) -> pd.DataFrame:
    """Use this when you need the schedule overrun of each project on a date, in days and as a fraction of the planned days.

    Overrun is (end minus planned_end) in days over (planned_end minus start plus 1) planned days, the definition of the generator test test_cell_calibration (PROPOSED, policy.delivery.overrun_definition is needed).
    End is actual_end for a project completed on the date (basis actual). With include_forecast an active project with a forecast_end is listed with basis forecast and that end. The stored forecast_end is the one on the release date
    (fact world.now): for an as_of before it the forecast of an active project is not the forecast that stood on that date, so its basis is "current forecast" (same end, a later view than the date); at or after the release date
    the basis is "forecast". Planned projects, and active ones without a forecast, are not listed. Overrun is negative for a project that ended early.

    Args:
        project: The projects.project frame, one row per prj_key; it needs prj_key, start, planned_end, actual_end and forecast_end.
        as_of: The date on which the status of each project is taken (a date, a Timestamp or an ISO text).
        include_forecast: True lists active projects with a forecast_end on the basis of that forecast; False lists only completed projects.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns prj_key, as_of, basis (actual, forecast or current forecast), planned_days, overrun_days and overrun (a fraction, negative: early), one row per listed project, in the order of the input.

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a project has no start date; a date column holds an unreadable value or a time zone; a completed project has no planned_end or one before its start.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import schedule_overrun
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"],
        ...                     "start": ["2029-01-01", "2030-01-01"], "planned_end": ["2029-01-10", "2030-01-10"],
        ...                     "actual_end": ["2029-01-15", None], "forecast_end": [None, "2030-01-12"]})
        >>> out = schedule_overrun(prj, "2030-01-05", context=ctx)
        >>> out["basis"].tolist()
        ['actual', 'forecast']
        >>> out["overrun_days"].tolist()
        [5.0, 2.0]
        >>> out["overrun"].round(2).tolist()
        [0.5, 0.2]"""
    _need(project, ["prj_key", "start", "planned_end", "actual_end", "forecast_end"])
    d = _day(as_of)
    status = _status(project, d)["status"]
    start, planned = _days(project["start"], "start"), _days(project["planned_end"], "planned_end")
    actual, forecast = _days(project["actual_end"], "actual_end"), _days(project["forecast_end"], "forecast_end")
    bad = planned.isna() | (planned < start)
    done = (status == "completed").to_numpy()
    if (bad.to_numpy() & done).any():
        k = project.loc[bad.to_numpy() & done, "prj_key"].iloc[0]
        raise FrameError(f"{int((bad.to_numpy() & done).sum())} completed projects have no planned_end or one before the start (for example {k}); an overrun needs a plan")
    has_fc = (status == "active").to_numpy() & forecast.notna().to_numpy() & planned.notna().to_numpy() & (planned >= start).to_numpy() & include_forecast
    use = done | has_fc
    end = actual.where(done, forecast)
    fc_basis = "forecast" if d >= pd.Timestamp(fact("world.now").value) else "current forecast"
    out = pd.DataFrame({"prj_key": project["prj_key"].to_numpy(), "as_of": d, "basis": np.where(done, "actual", fc_basis)}, index=project.index)
    out["planned_days"] = ((planned - start).dt.days + 1).astype("float64")
    out["overrun_days"] = (end - planned).dt.days.astype("float64")
    out["overrun"] = out["overrun_days"] / out["planned_days"]
    return out[use]


class DelayDays(NamedTuple):
    """Result of delay_days: event days per project and cause, and the tie of the event days to the date difference."""

    by_cause: pd.DataFrame
    tie: pd.DataFrame


@staged(sources=("projects.delay_event.prj_key", "projects.delay_event.cause_code", "projects.delay_event.responsible_party", "projects.delay_event.days", "projects.delay_event.seq",
                 "projects.project.prj_key", "projects.project.planned_end", "projects.project.actual_end"),
        kb=_KB_PLAN, oracle="py:tests/test_projects.py::test_delay_events")
def delay_days(delay_event: pd.DataFrame, project: pd.DataFrame | None = None) -> DelayDays:
    """Use this when you need the delay event days of each project by cause and responsible party, and how they tie to the date difference between actual and planned end.

    Returns delay event days per project, cause_code and responsible_party (by_cause), and per project the total event days next to the date difference actual_end minus planned_end (tie).
    The tie compares the two for completed projects that have at least one event (the generator test inner joins events to projects); other projects are listed with diff and ties false or null, never dropped.
    Without a project frame the tie has event_days only. The project frame may be a subset (for example one cell): events of projects not in it are left out of both results and counted in attrs['events_outside_projects'] (0 without a frame);
    a frame sharing no project with the events is refused (the wrong frame). Event rows sharing prj_key and seq (when seq is loaded) and days of zero or less are refused (FrameError); they would be summed silently.

    Args:
        delay_event: The projects.delay_event frame; it needs prj_key, cause_code, responsible_party and days (whole days above zero, no nulls), and may have seq.
        project: The projects.project frame with prj_key, planned_end and actual_end, or None for a tie of event days only. It may be a subset of the projects.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DelayDays tuple. by_cause has prj_key, cause_code, responsible_party, events and days, sorted by those keys. tie has prj_key, event_days and events (sorted by prj_key); with a project frame it also has date_diff, diff (event_days minus date_diff) and ties (a nullable boolean, null where date_diff is null) and holds every project of the frame.
        Both frames carry attrs['events_outside_projects'].

    Raises:
        FrameError: delay_event is not a DataFrame, has duplicate column names or lacks a needed column; days is not numeric, has nulls, has a fraction or is zero or negative; prj_key, cause_code or responsible_party has a null; prj_key and seq are repeated; project lacks a needed column or has a null or repeated prj_key; no project of the events is in the project frame; a date column of project is unreadable.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import delay_days
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ev = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "cause_code": ["C-A", "C-B"],
        ...                    "responsible_party": ["P-1", "P-2"], "days": [3, 2]})
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "planned_end": ["2029-01-10"], "actual_end": ["2029-01-15"]})
        >>> res = delay_days(ev, prj, context=ctx)
        >>> res.by_cause["days"].tolist()
        [3, 2]
        >>> res.tie[["event_days", "date_diff", "ties"]].to_dict("records")
        [{'event_days': 5, 'date_diff': 5.0, 'ties': True}]"""
    _frame_need(delay_event, ["prj_key", "cause_code", "responsible_party", "days"], "projects.delay_event")
    if not pd.api.types.is_numeric_dtype(delay_event["days"]) or pd.api.types.is_bool_dtype(delay_event["days"]):
        raise FrameError("projects.delay_event.days must be numeric")
    if delay_event["days"].isna().any():
        raise FrameError("projects.delay_event.days has nulls")
    if (delay_event["days"] % 1 != 0).any():
        raise FrameError("projects.delay_event.days must be whole days")
    if (delay_event["days"] <= 0).any():
        raise FrameError(f"projects.delay_event.days must be positive; {int((delay_event['days'] <= 0).sum())} rows are zero or negative (for example {delay_event.loc[delay_event['days'] <= 0, 'prj_key'].iloc[0]})")
    nulls = [c for c in ("prj_key", "cause_code", "responsible_party") if delay_event[c].isna().any()]
    if nulls:
        raise FrameError(f"projects.delay_event has rows with a null {', '.join(nulls)}; they would drop out of one result and not the other")
    if "seq" in delay_event.columns:
        dup = delay_event[delay_event.duplicated(["prj_key", "seq"], keep=False)]
        if len(dup):
            raise FrameError(f"projects.delay_event has {len(dup)} rows sharing prj_key and seq (for example {dup.iloc[0]['prj_key']} {dup.iloc[0]['seq']}); a repeated event would be summed twice")
    outside = 0
    if project is not None:
        _need(project, ["prj_key", "planned_end", "actual_end"])
        inside = delay_event["prj_key"].isin(project["prj_key"]).to_numpy()
        if len(delay_event) and not inside.any():
            raise FrameError(f"the {delay_event['prj_key'].nunique()} projects in the delay events are not in the project frame, none of them (for example {delay_event['prj_key'].iloc[0]}); is it the right frame?")
        outside = int((~inside).sum())
        delay_event = delay_event[inside]
    by = (delay_event.groupby(["prj_key", "cause_code", "responsible_party"], as_index=False, sort=True)
          .agg(events=("days", "size"), days=("days", "sum")))
    total = delay_event.groupby("prj_key", as_index=False, sort=True).agg(event_days=("days", "sum"), events=("days", "size"))
    by.attrs["events_outside_projects"] = total.attrs["events_outside_projects"] = outside
    if project is None:
        return DelayDays(by, total)
    p = project[["prj_key"]].copy()
    p["date_diff"] = (_days(project["actual_end"], "actual_end") - _days(project["planned_end"], "planned_end")).dt.days.to_numpy().astype("float64")
    tie = p.merge(total, on="prj_key", how="outer", validate="one_to_one")
    tie["event_days"] = tie["event_days"].fillna(0).astype("int64")
    tie["events"] = tie["events"].fillna(0).astype("int64")
    tie["diff"] = tie["event_days"] - tie["date_diff"]
    tie["ties"] = (tie["diff"] == 0).astype("boolean").where(tie["date_diff"].notna())
    tie = tie.sort_values("prj_key").reset_index(drop=True)
    tie.attrs["events_outside_projects"] = outside
    return DelayDays(by, tie)


@staged(sources=("projects.plan_version.prj_key", "projects.plan_version.plan_version", "projects.plan_version.created", "projects.plan_version.reason", "projects.plan_version.planned_end"),
        kb=_KB_PLAN, oracle=_O4)
def plan_slip(plan_version: pd.DataFrame, as_of: dt.date | None = None) -> pd.DataFrame:
    """Use this when you need how far each plan version moved planned_end against the baseline (version 1) and against the version before it.

    Gives planned_end of each plan version against version 1 (baseline) and against the version before it: slip_days, step_days, with created and reason. A project without a version 1 has baseline_end null and slip_days null.
    With as_of only versions created on or before it are kept (a plan not yet written does not exist; a version with no created date is kept). Source columns are kept.

    Args:
        plan_version: The projects.plan_version frame, one row per prj_key and plan_version; it needs prj_key, plan_version (numeric), created, reason and planned_end.
        as_of: A date; only versions created on or before it are kept. None keeps all versions.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by prj_key and plan_version with the source columns (created and planned_end as calendar days) and the added columns baseline_end, slip_days (planned_end minus baseline_end) and step_days (planned_end minus the previous version's), in days.

    Raises:
        FrameError: plan_version is not a DataFrame, has duplicate column names or lacks a needed column; prj_key or plan_version has a null; a prj_key and plan_version pair is repeated; plan_version is not numeric; created or planned_end holds an unreadable value or a time zone.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import plan_slip
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pv = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "plan_version": [1, 2, 3],
        ...                    "created": ["2029-01-01", "2029-02-01", "2029-03-01"], "reason": ["base", "r1", "r2"],
        ...                    "planned_end": ["2029-06-01", "2029-06-11", "2029-06-21"]})
        >>> plan_slip(pv, context=ctx)["slip_days"].tolist()
        [0.0, 10.0, 20.0]
        >>> plan_slip(pv, "2029-02-15", context=ctx)["plan_version"].tolist()
        [1, 2]"""
    _frame_need(plan_version, ["prj_key", "plan_version", "created", "reason", "planned_end"], "projects.plan_version", keys=("prj_key", "plan_version"))
    if not pd.api.types.is_numeric_dtype(plan_version["plan_version"]):
        raise FrameError("projects.plan_version.plan_version must be numeric")
    v = plan_version.copy()
    v["created"], v["planned_end"] = _date_col(v, "created", "projects.plan_version"), _date_col(v, "planned_end", "projects.plan_version")
    if as_of is not None:
        d = _day(as_of)
        v = v[v["created"].isna() | (v["created"] <= d)]
    v = v.sort_values(["prj_key", "plan_version"]).reset_index(drop=True)
    base = v[v["plan_version"] == 1].set_index("prj_key")["planned_end"]
    v["baseline_end"] = v["prj_key"].map(base)
    v["slip_days"] = (v["planned_end"] - v["baseline_end"]).dt.days.astype("float64")
    v["step_days"] = v.groupby("prj_key")["planned_end"].diff().dt.days.astype("float64")
    return v


@staged(sources=("projects.milestone.prj_key", "projects.milestone.milestone_no", "projects.milestone.planned_date", "projects.milestone.actual_date"),
        kb=_KB_PLAN, oracle=_O5)
def milestone_slippage(milestone: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the state of each milestone on a date: done with its slip, or open with its overdue days.

    A milestone is done when actual_date is on or before the date, then slip_days is actual_date minus planned_date. Otherwise it is open: overdue_days is the date minus planned_date when that is positive (state open_overdue, else open).
    The source columns are kept (actual_date is null if after the date).

    Args:
        milestone: The projects.milestone frame, one row per prj_key and milestone_no; it needs prj_key, milestone_no, planned_date and actual_date.
        as_of: The date on which the state of each milestone is taken (a date, a Timestamp or an ISO text).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by prj_key and milestone_no with the source columns (dates as calendar days) and the added columns state (done, open_overdue or open), slip_days (null unless done) and overdue_days (null unless open and overdue).

    Raises:
        FrameError: milestone is not a DataFrame, has duplicate column names or lacks a needed column; prj_key or milestone_no has a null; a prj_key and milestone_no pair is repeated; a row has no planned_date; a date column holds an unreadable value or a time zone.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import milestone_slippage
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ms = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "milestone_no": [1, 2, 3],
        ...                    "planned_date": ["2029-03-01", "2029-04-01", "2029-12-01"],
        ...                    "actual_date": ["2029-03-05", None, None]})
        >>> out = milestone_slippage(ms, "2029-05-01", context=ctx)
        >>> out["state"].tolist()
        ['done', 'open_overdue', 'open']
        >>> out["slip_days"].tolist()[0], out["overdue_days"].tolist()[1]
        (4.0, 30.0)"""
    _frame_need(milestone, ["prj_key", "milestone_no", "planned_date", "actual_date"], "projects.milestone", keys=("prj_key", "milestone_no"))
    d = _day(as_of)
    m = milestone.copy()
    planned, actual = _date_col(m, "planned_date", "projects.milestone"), _date_col(m, "actual_date", "projects.milestone")
    if planned.isna().any():
        raise FrameError(f"projects.milestone has {int(planned.isna().sum())} rows without planned_date")
    done = actual.notna() & (actual <= d)
    m["planned_date"], m["actual_date"] = planned, actual.where(done)
    overdue = (d - planned).dt.days
    m["state"] = np.where(done, "done", np.where(overdue > 0, "open_overdue", "open"))
    m["slip_days"] = (m["actual_date"] - planned).dt.days.astype("float64")
    m["overdue_days"] = overdue.where(~done & (overdue > 0)).astype("float64")
    return m.sort_values(["prj_key", "milestone_no"]).reset_index(drop=True)


@staged(sources=("projects.plan_activity.prj_key", "projects.plan_activity.plan_version", "projects.plan_activity.activity_code", "projects.plan_activity.name", "projects.plan_activity.start",
                 "projects.plan_activity.end", "projects.plan_activity.predecessor", "projects.plan_activity.critical", "projects.actual_activity.prj_key", "projects.actual_activity.activity_code",
                 "projects.actual_activity.actual_start", "projects.actual_activity.actual_end", "projects.actual_activity.percent_complete", "projects.plan_version.prj_key", "projects.plan_version.plan_version", "projects.plan_version.created"),
        facts=_NOW, kb=_KB_PLAN, oracle=_O4)
def activity_plan_vs_actual(plan_activity: pd.DataFrame, actual_activity: pd.DataFrame, as_of: dt.date | None = None, *, plan_version: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need each activity's baseline plan, latest plan and actual dates side by side, with the start and end slip.

    Per activity: baseline start and end (lowest plan_version of the activity), latest start and end (highest version, name, predecessor and critical from it), actual_start, actual_end and percent_complete,
    plus start_slip_days (actual_start minus baseline start), end_slip_days (latest end minus baseline end) and plan_versions. With as_of, actual dates after it are null, and so is the percent of an activity that had not started on that date.
    The stored percent is the one on the release date (fact world.now) and the final one for a finished activity: for an as_of before the release date the percent of a started, unfinished activity is null (the percent on that date is not in the data);
    at or after it the stored percent of a started activity is kept. LEAK: without plan_version the plan versions are not filtered by date (the plan frame has no created date), so for a past as_of the latest version, end_slip_days and plan_versions
    include re-plans that did not exist yet. Pass plan_version (the projects.plan_version frame: prj_key, plan_version, created) with as_of to drop the activity rows of versions created after the date (a version with no created date, or absent from
    that frame, is kept); an activity with no version left on the date is not listed. plan_version without as_of filters nothing. Activities without actual rows stay, with nulls.

    Args:
        plan_activity: The projects.plan_activity frame, one row per prj_key, plan_version and activity_code; it needs prj_key, plan_version, activity_code, name, start, end, predecessor and critical.
        actual_activity: The projects.actual_activity frame, one row per prj_key and activity_code; it needs prj_key, activity_code, actual_start, actual_end and percent_complete.
        as_of: A date; actuals after it are treated as not yet known. None uses the stored actuals as they are.
        plan_version: The projects.plan_version frame (prj_key, plan_version, created), or None; with as_of it drops plan versions created after the date.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by prj_key and activity_code with name, baseline_start, baseline_end, latest_start, latest_end, predecessor, critical, plan_versions, actual_start, actual_end, percent_complete, start_slip_days and end_slip_days (days as floats).

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; a key column has a null or a key is repeated (prj_key, plan_version and activity_code of the plan; prj_key and activity_code of the actuals; prj_key and plan_version of plan_version); a date column holds an unreadable value or a time zone; an actual activity has no plan activity.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import activity_plan_vs_actual
        >>> ctx = Context(stage="month12", role="analyst")
        >>> plan = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "plan_version": [1, 2], "activity_code": ["A10", "A10"], "name": ["Dig", "Dig"],
        ...                      "start": ["2029-01-01", "2029-01-05"], "end": ["2029-01-10", "2029-01-20"], "predecessor": [None, None], "critical": [True, True]})
        >>> act = pd.DataFrame({"prj_key": ["PRJ-900001"], "activity_code": ["A10"], "actual_start": ["2029-01-06"],
        ...                     "actual_end": ["2029-01-22"], "percent_complete": [100.0]})
        >>> out = activity_plan_vs_actual(plan, act, context=ctx)
        >>> out[["plan_versions", "start_slip_days", "end_slip_days"]].to_dict("records")
        [{'plan_versions': 2, 'start_slip_days': 5.0, 'end_slip_days': 10.0}]"""
    _frame_need(plan_activity, ["prj_key", "plan_version", "activity_code", "name", "start", "end", "predecessor", "critical"], "projects.plan_activity",
                keys=("prj_key", "plan_version", "activity_code"))
    _frame_need(actual_activity, ["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"], "projects.actual_activity", keys=("prj_key", "activity_code"))
    p = plan_activity.copy()
    all_keys = p[["prj_key", "activity_code"]].drop_duplicates()
    if plan_version is not None:
        _frame_need(plan_version, ["prj_key", "plan_version", "created"], "projects.plan_version", keys=("prj_key", "plan_version"))
    p["start"], p["end"] = _date_col(p, "start", "projects.plan_activity"), _date_col(p, "end", "projects.plan_activity")
    p = p.sort_values(["prj_key", "activity_code", "plan_version"], kind="stable")
    if plan_version is not None and as_of is not None:
        v = plan_version[["prj_key", "plan_version"]].assign(created=_date_col(plan_version, "created", "projects.plan_version"))
        created = p[["prj_key", "plan_version"]].merge(v, on=["prj_key", "plan_version"], how="left")["created"].to_numpy()
        p = p[~(pd.Series(created, index=p.index) > _day(as_of)).to_numpy()]      # a version created after the date did not exist; no created date: kept
    k = ["prj_key", "activity_code"]
    first, last = p.drop_duplicates(k, keep="first").set_index(k), p.drop_duplicates(k, keep="last").set_index(k)     # rows, not column wise first(): a null stays null
    out = pd.DataFrame({"name": last["name"], "baseline_start": first["start"], "baseline_end": first["end"], "latest_start": last["start"], "latest_end": last["end"],
                        "predecessor": last["predecessor"], "critical": last["critical"], "plan_versions": p.groupby(k, sort=True).size()}).reset_index()
    a = actual_activity[["prj_key", "activity_code", "actual_start", "actual_end", "percent_complete"]].copy()
    a["actual_start"], a["actual_end"] = _date_col(a, "actual_start", "projects.actual_activity"), _date_col(a, "actual_end", "projects.actual_activity")
    if as_of is not None:
        d = _day(as_of)
        started = a["actual_start"].notna() & (a["actual_start"] <= d)
        finished = started & a["actual_end"].notna() & (a["actual_end"] <= d)
        a["actual_end"] = a["actual_end"].where(finished)
        a["actual_start"] = a["actual_start"].where(started)
        known = started if d >= pd.Timestamp(fact("world.now").value) else finished     # the stored percent is the one at the release date and final for a finished activity
        a["percent_complete"] = a["percent_complete"].where(known)
    out = out.merge(a, on=["prj_key", "activity_code"], how="left", validate="one_to_one")
    orphan = a.merge(all_keys, on=["prj_key", "activity_code"], how="left", indicator=True)
    if (orphan["_merge"] == "left_only").any():
        r = orphan[orphan["_merge"] == "left_only"].iloc[0]
        raise FrameError(f"{int((orphan['_merge'] == 'left_only').sum())} actual activities have no plan activity (for example {r['prj_key']} {r['activity_code']})")
    out["start_slip_days"] = (out["actual_start"] - out["baseline_start"]).dt.days.astype("float64")
    out["end_slip_days"] = (out["latest_end"] - out["baseline_end"]).dt.days.astype("float64")
    return out
