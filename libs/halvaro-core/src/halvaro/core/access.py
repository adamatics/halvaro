"""Stage and access guard: what a session sees, which columns are restricted, aggregates of restricted measures."""
from __future__ import annotations

import dataclasses
import datetime as dt
import re
from typing import Any, Iterable, Sequence

import pandas as pd

from . import snapshot
from .errors import AggregateRefusal, FrameError, HalvaroError, ProfileError, RestrictedColumnRefusal, StageRefusal
from .registry import function

PERSON_KEY_RE = re.compile(r"^EMP-[0-9]{6}$")


@dataclasses.dataclass(frozen=True)
class Context:
    """The caller: stage, role, release date and whether restricted columns may be read. No default for stage or restricted access."""

    stage: str
    role: str
    now: dt.date | None = None
    restricted_ok: bool = False

    def __post_init__(self) -> None:
        if self.stage not in snapshot.load()["stage_order"]:
            raise ProfileError(f"stage {self.stage!r} is not one of {', '.join(snapshot.load()['stage_order'])}")

    @classmethod
    def from_profile(cls, profile: str, *, stage: str | None = None, now: dt.date | None = None, restricted_ok: bool | None = None) -> "Context":
        """Context of halvaro-stage1 to 3, mcp_<group>, mcp_<group>_hr or api_<source>. Roles other than the stage profiles need `stage`."""
        snap = snapshot.load()
        m = re.fullmatch(r"halvaro[-_]stage([1-3])", profile)
        if m:
            held = snap["stage_order"][int(m.group(1)) - 1]
            return cls(stage=held, role=f"halvaro_stage{m.group(1)}", now=now, restricted_ok=bool(restricted_ok))
        if re.fullmatch(r"mcp_[a-z_]+|api_[a-z_]+", profile):
            if stage is None:
                raise ProfileError(f"role {profile} does not fix a stage; pass stage= one of {', '.join(snap['stage_order'])}")
            default = profile.endswith("_hr") or profile.startswith("api_")
            return cls(stage=stage, role=profile, now=now, restricted_ok=default if restricted_ok is None else restricted_ok)
        raise ProfileError(f"profile {profile!r} is not halvaro-stage1 to 3, mcp_<group>, mcp_<group>_hr or api_<source>")


@dataclasses.dataclass(frozen=True)
class RestrictedAggregate:
    """An aggregate of a restricted column that passed the guard."""

    frame: pd.DataFrame
    restricted_column: str
    group_columns: tuple[str, ...]
    min_group: int | None


def _rank(stage: str) -> int:
    order: list[str] = snapshot.load()["stage_order"]
    if stage not in order:
        raise ProfileError(f"stage {stage!r} is not one of {', '.join(order)}")
    return order.index(stage)


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_source_stage_and_visible_sources_oracle_the_stage_profiles_of_the_design_file")
def source_stage(source: str) -> str:
    """Use this when you need to know at which stage a source (hr, finance, projects and so on) becomes visible to a session.

    Args:
        source: The name of the source, for example "hr".

    Returns:
        str: the stage, one of day1, month3 and month12.

    Raises:
        FrameError: the source is not known; the message lists the known sources.

    Example:
        >>> from halvaro.core import source_stage
        >>> source_stage("hr"), source_stage("finance")
        ('day1', 'month3')
    """
    s: str | None = snapshot.load()["stages"].get(source)
    if s is None:
        raise FrameError(f"source {source!r} is unknown; sources: {', '.join(sorted(snapshot.load()['stages']))}")
    return s


def stage_of_sources(sources: Iterable[str]) -> str | None:
    """Highest stage of a set of sources or 'source.table.column' ids (None for an empty set)."""
    held = [source_stage(s.split(".")[0]) for s in sources]
    return max(held, key=_rank) if held else None


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_source_stage_and_visible_sources_oracle_the_stage_profiles_of_the_design_file")
def visible_sources(stage: str) -> frozenset[str]:
    """Use this when you need the sources that a session at a stage can see.

    Rule: the stages are cumulative, so a later stage sees everything an earlier stage sees.

    Args:
        stage: The stage, one of day1, month3 and month12.

    Returns:
        frozenset: the names of the visible sources.

    Raises:
        ProfileError: the stage is not one of day1, month3 and month12.

    Example:
        >>> from halvaro.core import visible_sources
        >>> "hr" in visible_sources("day1"), "finance" in visible_sources("day1"), "finance" in visible_sources("month3")
        (True, False, True)
    """
    snap = snapshot.load()
    return frozenset(s for s, st in snap["stages"].items() if _rank(st) <= _rank(stage))


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_access.py::test_require_sources_oracle_every_source_alone_and_in_pairs_against_the_stage_profiles")
def require_sources(context: Context, sources: Sequence[str], function: str | None = None) -> None:
    """Use this when a function reads tables of some sources and must refuse a session whose stage does not hold them yet.

    Rule: the sources are reduced to their source name (the part before the first dot). Every source whose stage is above the stage of the context is named in the refusal together with the stage where it appears.

    Args:
        context: The caller (stage, role, release date, restricted access).
        sources: Source names or table names such as "hr.employee" or "finance".
        function: The name of the calling function, written into the refusal. Optional.

    Returns:
        None: nothing happens when every source is visible at the stage of the context.

    Raises:
        StageRefusal: one or more sources appear at a later stage than the context holds.
        FrameError: a source name is unknown, for example "zz"; the message lists the known sources.

    Example:
        >>> from halvaro.core import Context, require_sources
        >>> day1 = Context(stage="day1", role="analyst")
        >>> require_sources(day1, ["hr.employee"])
        >>> require_sources(day1, ["finance.journal_line"], function="trial_balance")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.StageRefusal: Sources finance appear at stage month3; the session holds stage day1 (trial_balance). Ask for a session at stage month3 or use only the sources of stage day1.
    """
    names = sorted({s.split(".")[0] for s in sources})
    missing = [s for s in names if _rank(source_stage(s)) > _rank(context.stage)]
    if missing:
        raise StageRefusal(missing, max((source_stage(s) for s in missing), key=_rank), context.stage, function)


@function(restricted=("hr.employment_term.base_salary",), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_require_columns_oracle_exactly_the_restricted_list_is_refused_for_a_role_without_access")
def require_columns(context: Context, columns: Sequence[str]) -> None:
    """Use this when a function reads columns that are restricted (pay, birth date) and must refuse a session that may not read them.

    Rule: only the columns that the data dictionary lists as restricted count. When the context has restricted access nothing happens.

    Args:
        context: The caller (stage, role and whether restricted columns may be read).
        columns: Column ids of the form source.table.column, for example "hr.employment_term.base_salary".

    Returns:
        None: nothing happens when no column is restricted or the context may read them.

    Raises:
        RestrictedColumnRefusal: a column is restricted and the context has no restricted access; the message names the column, the role and the stage.

    Example:
        >>> from halvaro.core import Context, require_columns
        >>> analyst = Context(stage="day1", role="analyst")
        >>> require_columns(analyst, ["hr.employee.emp_key"])
        >>> require_columns(analyst, ["hr.employment_term.base_salary"])
        Traceback (most recent call last):
        ...
        halvaro.core.errors.RestrictedColumnRefusal: Column hr.employment_term.base_salary is restricted; role analyst at stage day1 may not read it. Use an aggregate above the minimum group size or a role with restricted access.
        >>> require_columns(Context(stage="day1", role="analyst", restricted_ok=True), ["hr.employment_term.base_salary"])
    """
    hits = [c for c in columns if c in snapshot.load()["restricted_columns"]]
    if hits and not context.restricted_ok:
        raise RestrictedColumnRefusal(", ".join(sorted(hits)), context.role, context.stage)


def _is_person_key(value: Any) -> bool:
    return bool(PERSON_KEY_RE.match(str(value)))


def _has_person_key(values: Any) -> bool:
    """True when any value of a column or index level is an EMP key. Numbers, booleans and dates are skipped; every other dtype (text, categorical, Arrow text, objects) is read as text."""
    dtype = values.dtype
    if pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_datetime64_any_dtype(dtype) or pd.api.types.is_timedelta64_dtype(dtype):
        return False
    return bool(values.dropna().astype(object).map(_is_person_key).any())


def _person_columns(frame: pd.DataFrame) -> list[Any]:
    """Columns and index levels in which at least one value is an EMP key (a column that also holds blanks or other text still ties the measure to people)."""
    out = [frame.columns[i] for i in range(frame.shape[1]) if _has_person_key(frame.iloc[:, i])]
    for i, name in enumerate(frame.index.names):
        if _has_person_key(frame.index.get_level_values(i)):
            out.append(f"index {name if name else i}")
    return out


@function(restricted=("hr.employment_term.base_salary",), oracle="py:../libs/halvaro-core/tests/test_oracle_aggregate.py::test_assert_aggregate_oracle_refusal_equals_a_loop_over_every_value")
def assert_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> None:
    """Use this when a frame holds an aggregate of a restricted measure (pay, birth date) and you must check that it names no person and has no group that is too small.

    Rule: the frame is refused when any column or index level holds an EMP key in at least one value (text columns are read as text; numbers, dates and durations are skipped). When min_group is given, every row of count_column must be at least min_group, and a row with no count is refused as well. group_columns is not read by the check; it is only carried by mark_aggregate.

    Args:
        frame: The aggregate, one row per group.
        restricted_column: The column that holds the restricted measure; it must be a column of the frame.
        group_columns: The columns the aggregate is grouped by. Optional; not used by the check itself.
        min_group: The smallest number of people a group may have. Optional; without it the group sizes are not checked.
        count_column: The column with the number of people per group. Needed when min_group is given.

    Returns:
        None: nothing happens when the frame passes the guard.

    Raises:
        FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
        AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import assert_aggregate
        >>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 1]})
        >>> assert_aggregate(frame, "measure", ["grade"], min_group=1, count_column="people")
        >>> assert_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.AggregateRefusal: 1 groups have fewer than 2 people or no count; suppress them or widen the grouping.
        >>> by_person = pd.DataFrame({"emp_key": ["EMP-000001"], "measure": [10.0]})
        >>> assert_aggregate(by_person, "measure")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.AggregateRefusal: measure sits next to person keys in column(s) emp_key. Group by department, grade or similar and drop the person key.
    """
    if restricted_column not in frame.columns:
        raise FrameError(f"column {restricted_column} is missing in the frame")
    persons = _person_columns(frame)
    if persons:
        raise AggregateRefusal(f"{restricted_column} sits next to person keys in column(s) {', '.join(map(str, persons))}. Group by department, grade or similar and drop the person key.")
    if min_group is not None:
        if count_column is None or count_column not in frame.columns:
            raise FrameError("min_group needs count_column, the column with the number of people per group")
        try:
            small = frame[(frame[count_column] < min_group) | frame[count_column].isna()]
        except TypeError:
            if pd.api.types.is_numeric_dtype(frame[count_column]):
                raise FrameError(f"min_group must be a number (the smallest number of people per group), not {min_group!r}") from None
            raise FrameError(f"count_column {count_column} must hold numbers (the number of people per group) to be compared with min_group {min_group}, found {frame[count_column].dtype} values") from None
        if len(small):
            raise AggregateRefusal(f"{len(small)} groups have fewer than {min_group} people or no count; suppress them or widen the grouping.")


@function(restricted=("hr.employment_term.base_salary",), oracle="none, wrapper: calls assert_aggregate and wraps the frame, the column, the group columns as a tuple and min_group in a RestrictedAggregate, no logic of its own")
def mark_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> RestrictedAggregate:
    """Use this when you have checked an aggregate of a restricted measure and want to hand it on marked as safe to show.

    Rule: the frame is first checked with assert_aggregate (same arguments, same refusals); when it passes, it is wrapped unchanged together with the column name, the group columns as a tuple and min_group.

    Args:
        frame: The aggregate, one row per group.
        restricted_column: The column that holds the restricted measure; it must be a column of the frame.
        group_columns: The columns the aggregate is grouped by. Optional; kept as a tuple in the result.
        min_group: The smallest number of people a group may have. Optional; kept in the result.
        count_column: The column with the number of people per group. Needed when min_group is given.

    Returns:
        RestrictedAggregate: a record with the fields frame, restricted_column, group_columns (a tuple) and min_group.

    Raises:
        FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
        AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import mark_aggregate
        >>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 2]})
        >>> marked = mark_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
        >>> marked.restricted_column, marked.group_columns, marked.min_group, len(marked.frame)
        ('measure', ('grade',), 2, 2)
    """
    assert_aggregate(frame, restricted_column, group_columns, min_group, count_column)
    return RestrictedAggregate(frame, restricted_column, tuple(group_columns), min_group)


@function(restricted=("hr.employment_term.base_salary",), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_access.py::test_strip_restricted_oracle_every_restricted_name_goes_and_nothing_else")
def strip_restricted(frame: pd.DataFrame, context: Context) -> pd.DataFrame:
    """Use this when you have a frame and must remove the restricted columns (pay, birth date) before a session that may not read them sees it.

    Rule: when the context has restricted access the frame is returned as it is. Otherwise every column whose header, read after its last dot, equals the bare name of a restricted column of the data dictionary is dropped, so a qualified header such as 'table.column' or the full 'source.table.column' id cannot carry it past the guard. Other columns, their order and the rows are kept.

    Args:
        frame: The frame to clean.
        context: The caller (stage, role and whether restricted columns may be read).

    Returns:
        pandas.DataFrame: the frame without the restricted columns, or the same frame when the context may read them.

    Raises:
        This function raises no error of its own.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context, strip_restricted
        >>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hr.employee.birth_date": [0], "team": ["A"]})
        >>> list(strip_restricted(frame, Context(stage="day1", role="analyst")).columns)
        ['emp_key', 'team']
        >>> list(strip_restricted(frame, Context(stage="day1", role="analyst", restricted_ok=True)).columns)
        ['emp_key', 'hr.employee.birth_date', 'team']
    """
    if context.restricted_ok:
        return frame
    bare = {c.split(".")[-1] for c in snapshot.load()["restricted_columns"]}
    return frame.drop(columns=[c for c in frame.columns if str(c).split(".")[-1] in bare])


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_status_banner.py::test_stage_banner_oracle_hand_worked_texts")
def stage_banner(refusal: HalvaroError) -> str:
    """Use this when a stage or column refusal must be shown to the user as one plain line.

    Rule: a StageRefusal gives the missing sources, the stage where they appear and the stage the session holds. A RestrictedColumnRefusal gives the column, the role and the stage. Any other error gives its own message text.

    Args:
        refusal: The error that was raised, normally a StageRefusal or a RestrictedColumnRefusal.

    Returns:
        str: one line of text.

    Raises:
        This function raises no error of its own.

    Example:
        >>> from halvaro.core import StageRefusal, stage_banner
        >>> stage_banner(StageRefusal(["finance"], "month3", "day1"))
        'Needs finance (appears at stage month3). This session holds stage day1.'
    """
    if isinstance(refusal, StageRefusal):
        return f"Needs {', '.join(refusal.missing_sources)} (appears at stage {refusal.stage_needed}). This session holds stage {refusal.stage_held}."
    if isinstance(refusal, RestrictedColumnRefusal):
        return f"Restricted column {refusal.column}: role {refusal.role} at stage {refusal.stage} may not read it."
    return str(refusal)
