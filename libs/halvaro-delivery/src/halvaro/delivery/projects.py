"""Projects: the project master with its flags, and project status on a date from the dates. Results keep the index of the input frame."""
from __future__ import annotations

import datetime as dt
from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, PeriodError, fact, make_envelope

from ._guard import staged

STORY_PRJ_KEYS = ("PRJ-000001",)    # PROPOSED default of project_frame (review item 7 of #440): no fact names it, so it is a keyword parameter.
_SOURCES = ("projects.project.prj_key", "projects.project.start", "projects.project.actual_end")
_FRAME_SOURCES = ("projects.project.prj_key", "projects.project.data_depth", "projects.project.legacy", "projects.project.route_length_m", "projects.project.currency")
_KB = ("DA.REF.212",)
_FACTS = ("world.projects.full_total", "world.projects.legacy_total")
_ORACLE = "py:tests/test_projects.py::test_status_counts"


def _need(project: pd.DataFrame, columns: Sequence[str]) -> None:
    if not isinstance(project, pd.DataFrame):
        raise FrameError(f"the projects.project frame must be a DataFrame, not {type(project).__name__}")
    if project.columns.duplicated().any():
        raise FrameError(f"projects.project frame has duplicate column names ({', '.join(map(str, project.columns[project.columns.duplicated()]))})")
    missing = [c for c in columns if c not in project.columns]
    if missing:
        raise FrameError(f"projects.project frame lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if project["prj_key"].isna().any():
        raise FrameError(f"projects.project has {int(project['prj_key'].isna().sum())} rows without prj_key")
    dup = project["prj_key"][project["prj_key"].duplicated()]
    if len(dup):
        raise FrameError(f"projects.project has {len(dup)} duplicate prj_key values (for example {dup.iloc[0]}); one row per project is required")


def _day(as_of: Any) -> pd.Timestamp:
    if isinstance(as_of, (bool, int, float, np.number)):
        raise PeriodError(f"as_of {as_of!r} is a number, not a date; pass a date, a Timestamp or an ISO text such as 2026-11-30")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise PeriodError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d):
        raise PeriodError(f"as_of {as_of!r} is not a date")
    if d.tzinfo is not None:
        raise PeriodError(f"as_of {as_of!r} has a time zone; dates here are calendar days, pass it without one")
    return d.normalize()


def _days(column: pd.Series, name: str) -> pd.Series:
    """The column as calendar days (time of day dropped); text, dates and Timestamps are accepted, a time zone or an unreadable value is refused."""
    try:
        out = pd.to_datetime(column)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"projects.project.{name} holds a value that is not a date: {e}") from None
    if getattr(out.dt, "tz", None) is not None:
        raise FrameError(f"projects.project.{name} has a time zone; dates here are calendar days")
    return out.dt.normalize()


def _status(project: pd.DataFrame, as_of: Any) -> pd.DataFrame:
    """planned if start is after the date, completed if actual_end is set and before it, else active. The status column is not read."""
    _need(project, ["prj_key", "start", "actual_end"])
    d = _day(as_of)
    start, end = _days(project["start"], "start"), _days(project["actual_end"], "actual_end")
    if start.isna().any():
        raise FrameError(f"{int(start.isna().sum())} projects have no start date (for example {project.loc[start.isna(), 'prj_key'].iloc[0]}); a status on a date needs it")
    status = np.where(start > d, "planned", np.where(end.notna() & (end < d), "completed", "active"))
    return pd.DataFrame({"prj_key": project["prj_key"].to_numpy(), "as_of": d, "status": status}, index=project.index)


def _flag(column: pd.Series, name: str) -> pd.Series:
    """A boolean column as bool; a null or a value that is not True or False is refused, never cast."""
    if column.dtype == bool:
        return column
    if column.isna().any() or not column.isin([True, False]).all() or column.map(lambda v: isinstance(v, str)).any():
        bad = column[column.isna() | ~column.isin([True, False]) | column.map(lambda v: isinstance(v, str))]
        raise FrameError(f"projects.project.{name} must be True or False on every row; {len(bad)} are not (for example {bad.iloc[0]!r} on {bad.index[0]})")
    return column.astype(bool)


@staged(sources=_FRAME_SOURCES, facts=_FACTS, kb=_KB, oracle="py:tests/test_projects.py::test_counts_and_keys")
def project_frame(project: pd.DataFrame, *, story_prj_keys: Sequence[str] = STORY_PRJ_KEYS) -> Envelope:
    """Use this when you need the project master with its flags: full or summary depth, legacy, route length known and story project.

    The result is the project master with is_full, legacy, has_route_length and is_story added (input index kept); `value` is the frame. A count off the full and legacy facts (world.projects.full_total, world.projects.legacy_total) is a warning, as is a project that is both or neither of full and legacy and a data_depth other than full or summary. The keys flagged by is_story are the keyword parameter story_prj_keys (PROPOSED default, review item 7 of #440). The legacy column must be True or False on every row; a null or another value is refused, never cast.

    Args:
        project: The projects.project frame, one row per prj_key; it needs prj_key, data_depth, legacy, route_length_m and currency, and must not already have is_full, has_route_length or is_story.
        story_prj_keys: The project keys flagged as story projects (PROPOSED default; one key as text is also accepted, None means none).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An Envelope whose `value` is the project frame with the added columns is_full (data_depth is full), has_route_length (route_length_m is not null) and is_story (prj_key in story_prj_keys), with the facts, sources and warnings of the check.

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; the frame already has is_full, has_route_length or is_story; legacy has a null or a value that is not True or False.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import project_frame
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "data_depth": ["full", "summary"], "legacy": [False, True],
        ...                     "route_length_m": [1500.0, None], "currency": ["EUR", "DKK"]})
        >>> env = project_frame(prj, story_prj_keys=["PRJ-900002"], context=ctx)
        >>> env.value["is_full"].tolist()
        [True, False]
        >>> env.value["has_route_length"].tolist()
        [True, False]
        >>> env.value["is_story"].tolist()
        [False, True]"""
    _need(project, ["prj_key", "data_depth", "legacy", "route_length_m", "currency"])
    clash = [c for c in ("is_full", "has_route_length", "is_story") if c in project.columns]
    if clash:
        raise FrameError(f"projects.project frame already has column(s) {', '.join(clash)}; project_frame adds them, pass the source frame")
    keys = [] if story_prj_keys is None else [story_prj_keys] if isinstance(story_prj_keys, str) else list(story_prj_keys)
    out = project.copy()
    out["legacy"] = _flag(out["legacy"], "legacy")
    out["is_full"] = out["data_depth"].eq("full")
    out["has_route_length"] = out["route_length_m"].notna()
    out["is_story"] = out["prj_key"].isin(keys)
    full, legacy = fact("world.projects.full_total"), fact("world.projects.legacy_total")
    warnings = []
    if int(out["is_full"].sum()) != full.value:
        warnings.append(f"{int(out['is_full'].sum())} full projects, {full.id} says {full.value}")
    if int(out["legacy"].sum()) != legacy.value:
        warnings.append(f"{int(out['legacy'].sum())} legacy projects, {legacy.id} says {legacy.value}")
    odd = int((out["legacy"] == out["is_full"]).sum())
    if odd:
        warnings.append(f"{odd} projects are both or neither of full and legacy")
    other = out["data_depth"].isna() | ~out["data_depth"].isin(["full", "summary"])
    if other.any():
        warnings.append(f"{int(other.sum())} projects have a data_depth other than full or summary (for example {out.loc[other, 'data_depth'].iloc[0]!r})")
    return make_envelope(out, "halvaro.delivery.projects.project_frame", facts=(full, legacy), sources=_FRAME_SOURCES, warnings=warnings)


@staged(sources=_SOURCES, kb=_KB, oracle=_ORACLE)
def project_status_on(project: pd.DataFrame, as_of: dt.date) -> pd.DataFrame:
    """Use this when you need the status of each project on a date (planned, active or completed) worked out from its dates.

    The status is computed from the dates, not read from the status column: planned if start is after the date, completed if actual_end is set and before it, else active. Not the leave status of halvaro.hr. Results keep the index of the input frame.

    Args:
        project: The projects.project frame; it needs prj_key, start and actual_end, one row per prj_key.
        as_of: The day of the status (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with prj_key, as_of and status (planned, active, completed), one row per project, in the index of the input.

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a start has no date; start or actual_end holds a value that is not a date or has a time zone.
        PeriodError: as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import project_status_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "start": ["2026-01-01", "2026-03-01", "2025-01-01"],
        ...                     "actual_end": [None, None, "2025-12-31"]})
        >>> project_status_on(prj, "2026-02-01", context=ctx)["status"].tolist()
        ['active', 'planned', 'completed']"""
    return _status(project, as_of)


@staged(sources=_SOURCES, kb=_KB, oracle=_ORACLE)
def active_on(project: pd.DataFrame, as_of: dt.date) -> list[Any]:
    """Use this when you need the keys of the projects that are active on a date.

    A project is active when it has started and has not ended before the date (status computed from start and actual_end, as in project_status_on).

    Args:
        project: The projects.project frame; it needs prj_key, start and actual_end, one row per prj_key.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A list of the prj_key values of the active projects, sorted.

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; a start has no date; start or actual_end holds a value that is not a date or has a time zone.
        PeriodError: as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import active_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900002", "PRJ-900001", "PRJ-900003"], "start": ["2026-01-01", "2026-01-01", "2026-03-01"],
        ...                     "actual_end": [None, "2025-12-31", None]})
        >>> active_on(prj, "2026-02-01", context=ctx)
        ['PRJ-900002']"""
    s = _status(project, as_of)
    return sorted(s.loc[s["status"] == "active", "prj_key"])
