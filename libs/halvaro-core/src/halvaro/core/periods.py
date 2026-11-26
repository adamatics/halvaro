"""Periods (YYYY-MM), effective dated frames, as-of joins and the release identity."""
from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Any, Callable, Mapping, NamedTuple, Sequence

import numpy as np
import pandas as pd

from . import violations
from .errors import AmbiguousKey, FrameError, FrameMissing, PeriodError, ReleaseMismatch
from .registry import function

PERIOD_RE = re.compile(r"^([0-9]{4})-(0[1-9]|1[0-2])$")
RULES = ("reversed", "two_open", "open_not_last", "overlap", "gap")


class ReleaseInfo(NamedTuple):
    release: str
    now: dt.date
    generated_at: pd.Timestamp
    base_seed: object                  # as stored: the baseline seed is text such as 'halvaro-2026'
    increment: int


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_older_periods.py::test_parse_period_oracle_every_period_text_from_0001_to_9999_equals_strptime")
def parse_period(text: str) -> tuple[int, int]:
    """Use this when you have a period written YYYY-MM and need its year and month as numbers.

    Args:
        text: The period as text, for example "2026-11".

    Returns:
        tuple: (year, month) as two whole numbers.

    Raises:
        PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12 and a year from 0001 to 9999.

    Example:
        >>> from halvaro.core import parse_period
        >>> parse_period("2026-11")
        (2026, 11)
        >>> parse_period("2026-13")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.PeriodError: '2026-13' is not a period; expected YYYY-MM such as 2026-11, with a year from 0001 to 9999
    """
    m = PERIOD_RE.fullmatch(text) if isinstance(text, str) else None
    if not m or int(m.group(1)) < 1:
        raise PeriodError(f"{text!r} is not a period; expected YYYY-MM such as 2026-11, with a year from 0001 to 9999")
    return int(m.group(1)), int(m.group(2))


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_period_text.py::test_period_of_oracle_every_day_1950_to_2100_and_the_round_trips")
def period_of(day: dt.date) -> str:
    """Use this when you have a date and need its period written YYYY-MM.

    Args:
        day: A date (a datetime.date or a timestamp).

    Returns:
        str: the period, for example 2026-03.

    Raises:
        PeriodError: day is not a date or a timestamp (a text, for example).

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import period_of
        >>> period_of(dt.date(2026, 3, 31))
        '2026-03'
    """
    if not (hasattr(day, "year") and hasattr(day, "month")):
        raise PeriodError(f"period_of takes a date or a timestamp, not {day!r}")
    return f"{day.year:04d}-{day.month:02d}"


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_period_text.py::test_month_start_and_month_end_oracle_numpy_month_arithmetic_for_every_period_1900_to_2200")
def month_start(period: str) -> dt.date:
    """Use this when you need the first calendar day of a period written YYYY-MM.

    Args:
        period: A period as text, for example "2026-02".

    Returns:
        datetime.date: the first day of that month.

    Raises:
        PeriodError: the text is not a period of the form YYYY-MM.

    Example:
        >>> from halvaro.core import month_start
        >>> month_start("2026-02")
        datetime.date(2026, 2, 1)
    """
    y, m = parse_period(period)
    return dt.date(y, m, 1)


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_period_text.py::test_month_start_and_month_end_oracle_numpy_month_arithmetic_for_every_period_1900_to_2200")
def month_end(period: str) -> dt.date:
    """Use this when you need the last calendar day of a period written YYYY-MM.

    Args:
        period: A period as text, for example "2026-02".

    Returns:
        datetime.date: the last day of that month, leap years included.

    Raises:
        PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12.

    Example:
        >>> from halvaro.core import month_end
        >>> month_end("2026-02")
        datetime.date(2026, 2, 28)
    """
    y, m = parse_period(period)
    return dt.date(y, m, calendar.monthrange(y, m)[1])


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_period_text.py::test_add_months_oracle_numpy_months_and_the_group_laws")
def add_months(period: str, n: int) -> str:
    """Use this when you need the period a number of months after, or before, a period.

    Args:
        period: A period as text, for example "2026-11".
        n: Number of months to move. Negative moves back; zero returns the same period.

    Returns:
        str: the period YYYY-MM, with the year carried over.

    Raises:
        PeriodError: the text is not a period of the form YYYY-MM, or the result is outside the years 0001 to 9999.

    Example:
        >>> from halvaro.core import add_months
        >>> add_months("2026-11", 3), add_months("2026-01", -1)
        ('2027-02', '2025-12')
    """
    y, m = parse_period(period)
    k = y * 12 + (m - 1) + n
    if not 1 <= k // 12 <= 9999:
        raise PeriodError(f"{n} months after {period} is outside the years 0001 to 9999")
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_period_text.py::test_compare_periods_oracle_month_counts_antisymmetry_and_sorting")
def compare_periods(a: str, b: str) -> int:
    """Use this when you need to order two periods written YYYY-MM.

    Args:
        a: The first period.
        b: The second period.

    Returns:
        int: -1 when a is before b, 0 when they are equal, 1 when a is after b.

    Raises:
        PeriodError: a or b is not a period of the form YYYY-MM.

    Example:
        >>> from halvaro.core import compare_periods
        >>> compare_periods("2026-02", "2026-11"), compare_periods("2026-11", "2026-11"), compare_periods("2027-01", "2026-11")
        (-1, 0, 1)
    """
    pa, pb = parse_period(a), parse_period(b)
    return (pa > pb) - (pa < pb)


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_older_periods.py::test_period_range_oracle_numpy_months_for_random_pairs_and_reversed_pairs_are_empty")
def period_range(first: str, last: str) -> list[str]:
    """Use this when you need every month between two periods, both included, as a list of periods.

    Rule: the list runs from first to last in steps of one month. When last is before first the list is empty.

    Args:
        first: The first period as text, for example "2026-11".
        last: The last period as text.

    Returns:
        list: the periods YYYY-MM from first to last, oldest first; empty when last is before first.

    Raises:
        PeriodError: first or last is not a period of the form YYYY-MM.

    Example:
        >>> from halvaro.core import period_range
        >>> period_range("2026-11", "2027-02")
        ['2026-11', '2026-12', '2027-01', '2027-02']
        >>> period_range("2027-02", "2026-11")
        []
    """
    return [add_months(first, i) for i in range(max(0, _months_between(first, last) + 1))]


def _months_between(a: str, b: str) -> int:
    (ya, ma), (yb, mb) = parse_period(a), parse_period(b)
    return (yb - ya) * 12 + (mb - ma)


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_older_periods.py::test_year_of_oracle_pandas_period_arithmetic_for_every_start_month")
def year_of(period: str, start_month: int) -> int:
    """Use this when you need the year, counted from a start month, that a period belongs to: a fiscal year or a holiday year that does not begin in January.

    Rule: a period from the start month on belongs to the year it is in; an earlier period belongs to the year before. With start month 1 this is the calendar year.

    Args:
        period: A period as text, for example "2026-03".
        start_month: The month in which the year starts, from 1 to 12. The caller gets it from a fact or a setting of its own.

    Returns:
        int: the year that starts in the start month and contains the period.

    Raises:
        PeriodError: the start month is not from 1 to 12, or the period is not of the form YYYY-MM.

    Example:
        >>> from halvaro.core import year_of
        >>> year_of("2026-03", 9), year_of("2026-10", 9), year_of("2026-03", 1)
        (2025, 2026, 2026)
    """
    if not 1 <= start_month <= 12:
        raise PeriodError(f"start month {start_month} is not 1 to 12")
    y, m = parse_period(period)
    return y if m >= start_month else y - 1


def _dates(frame: pd.DataFrame, valid_from: str, valid_to: str) -> tuple[pd.Series, pd.Series]:
    for c in (valid_from, valid_to):
        if c not in frame.columns:
            raise FrameError(f"column {c} is missing in the frame; effective dated frames need {valid_from} and {valid_to}")
    return pd.to_datetime(frame[valid_from]).astype("datetime64[ns]"), pd.to_datetime(frame[valid_to]).astype("datetime64[ns]")


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_periods_release.py::test_rows_on_oracle_a_loop_over_the_term_rows_for_ten_dates")
def rows_on(frame: pd.DataFrame, on: dt.date, key: str | Sequence[str] | None = None, valid_from: str = "valid_from", valid_to: str = "valid_to") -> pd.DataFrame:
    """Use this when a table has effective dating (valid_from, valid_to) and you need the rows that are valid on one date.

    Rule: a row is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. With key, two valid rows of the same key are refused instead of both being returned.

    Args:
        frame: The table, one row per version, with the two date columns.
        on: The date.
        key: Column name, or list of column names, that identify the thing the rows are versions of. Optional; without it no check for two valid rows is made.
        valid_from: Name of the start column. Default "valid_from".
        valid_to: Name of the end column; empty means open. Default "valid_to".

    Returns:
        pandas.DataFrame: the rows of the frame that are valid on the date, in the order of the frame.

    Raises:
        FrameError: a date column is missing from the frame.
        AmbiguousKey: key is given and two rows with the same key are valid on the date.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import rows_on
        >>> versions = pd.DataFrame({"k": ["A", "A", "B"], "valid_from": ["2026-01-01", "2026-02-01", "2026-01-01"], "valid_to": ["2026-12-31", None, None]})
        >>> rows_on(versions, dt.date(2026, 1, 15))["k"].tolist()
        ['A', 'B']
        >>> rows_on(versions, dt.date(2026, 3, 1), key="k")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.AmbiguousKey: Key A matches 2 candidates: valid_from=2026-01-01, valid_from=2026-02-01. Pass a date or a more specific key.
    """
    vf, vt = _dates(frame, valid_from, valid_to)
    d = pd.Timestamp(on)
    out = frame[(vf <= d) & (vt.isna() | (vt >= d))]
    if key:
        cols = [key] if isinstance(key, str) else list(key)
        dup = out[out.duplicated(cols, keep=False)]
        if len(dup):
            first = tuple(dup.iloc[0][cols])
            raise AmbiguousKey(first[0] if len(first) == 1 else first, [f"{valid_from}={r[valid_from]}" for _, r in dup[dup[cols].eq(first).all(axis=1)].iterrows()])
    return out


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_periods_release.py::test_check_contiguity_oracle_baseline_employment_terms_and_injected_defects")
def check_contiguity(frame: pd.DataFrame, key: str | Sequence[str], valid_from: str = "valid_from", valid_to: str = "valid_to", convention: str = "day_after", table: str = "") -> pd.DataFrame:
    """Use this when a table has effective dating (valid_from, valid_to per key) and you need the rows that break the dating rules.

    Rule: per key the rows are ordered by valid_from. A row is reversed when valid_to is before valid_from, two_open when a key has more than one open row (valid_to empty), open_not_last when an open row is followed by another row, overlap when the next row starts before the previous one ends, and gap when it starts later. With convention "day_after" the next row starts the day after valid_to; with "touching" it starts on the same day.

    Args:
        frame: The table, one row per version.
        key: Column name, or list of column names, that identify the thing the rows are versions of.
        valid_from: Name of the start column. Default "valid_from".
        valid_to: Name of the end column; empty means open. Default "valid_to".
        convention: "day_after" or "touching". Default "day_after".
        table: A label written into the table column of the result, for example "hr.employment_term".

    Returns:
        pandas.DataFrame: one row per violation with the columns table, key, rule and detail; empty when the dating is clean.

    Raises:
        FrameError: the frame has no valid_from or valid_to column (the names are the arguments).
        PeriodError: the convention is neither day_after nor touching.
        ValueError: a date column holds text that is not a date (the parsing error of pandas, a ValueError).

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import check_contiguity
        >>> frame = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-02-05"], "valid_to": ["2026-01-31", None]})
        >>> check_contiguity(frame, "k")[["key", "rule", "detail"]].to_dict("records")
        [{'key': 'A', 'rule': 'gap', 'detail': 'next row starts 2026-02-05, previous ends 2026-01-31'}]
    """
    if convention not in ("day_after", "touching"):
        raise PeriodError(f"convention {convention!r} is not day_after or touching")
    cols = [key] if isinstance(key, str) else list(key)
    vf, vt = _dates(frame, valid_from, valid_to)
    df = frame[cols].copy()
    df["f_"], df["t_"] = vf.values, vt.values
    df = df.sort_values(cols + ["f_"], kind="stable")
    g = df.groupby(cols, sort=False)
    df["nf_"] = g["f_"].shift(-1)
    df["last_"] = df["nf_"].isna()
    n_open = df.groupby(cols, sort=False)["t_"].transform(lambda s: s.isna().sum())
    step = np.timedelta64(1 if convention == "day_after" else 0, "D")
    rows = []

    def add(mask: pd.Series, rule: str, detail: Callable[[Any], str]) -> None:
        for r in df[mask].itertuples(index=False):
            k = ", ".join(str(getattr(r, c)) for c in cols)
            rows.append((table, k, rule, detail(r)))

    add(df["t_"].notna() & (df["t_"] < df["f_"]), "reversed", lambda r: f"{valid_to} {r.t_.date()} before {valid_from} {r.f_.date()}")
    add(df["t_"].isna() & (n_open > 1), "two_open", lambda r: f"open row from {r.f_.date()}")
    add(df["t_"].isna() & ~df["last_"], "open_not_last", lambda r: f"open row from {r.f_.date()} is followed by a row from {r.nf_.date()}")
    paired = df["t_"].notna() & ~df["last_"]
    add(paired & (df["nf_"] < df["t_"] + step), "overlap", lambda r: f"next row starts {r.nf_.date()}, previous ends {r.t_.date()}")
    add(paired & (df["nf_"] > df["t_"] + step), "gap", lambda r: f"next row starts {r.nf_.date()}, previous ends {r.t_.date()}")
    return violations.frame(rows)


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_older_periods.py::test_asof_join_oracle_a_loop_with_bisect_over_random_effective_dated_rows")
def asof_join(left: pd.DataFrame, right: pd.DataFrame, date_column: str, key: str | Sequence[str], valid_from: str = "valid_from", valid_to: str = "valid_to",
              suffix: str = "_r") -> pd.DataFrame:
    """Use this when you need to attach to each row the version of an effective dated table that was valid on the row's date.

    Rule: every left row keeps its place. It gets the right row with the same key whose valid_from is the latest on or before the left date, provided its valid_to is empty or on or after that date; otherwise the right columns are empty. A left date written YYYY-MM counts as the first day of that month. The right frame must have no overlapping, reversed or doubly open rows; gaps are allowed and give empty right columns.

    Args:
        left: The table that needs the lookup, one row per event.
        right: The effective dated table, one row per version, with the two date columns.
        date_column: Name of the column in left that holds the date, a date or a YYYY-MM period text.
        key: Column name, or list of column names, that exist in both frames and identify the thing.
        valid_from: Name of the start column of right. Default "valid_from".
        valid_to: Name of the end column of right; empty means open. Default "valid_to".
        suffix: Added to the name of a right column that has the same name as a left column (the key columns excepted). Default "_r".

    Returns:
        pandas.DataFrame: the columns of left in their order, then the other columns of right (including its valid_from and valid_to), one row per left row in the order of left with a fresh index.

    Raises:
        PeriodError: the right frame has overlapping, reversed or doubly open rows.
        FrameError: right lacks the valid_from or valid_to column.
        KeyError: date_column or a key column is missing from left, or a key column is missing from right.
        FrameError: the left date column contains a null.
        ValueError: the dates of the left column or of the date columns of right are text that is not a date.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import asof_join
        >>> left = pd.DataFrame({"k": ["A", "A", "B"], "month": ["2026-02", "2026-04", "2026-02"]})
        >>> right = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-03-01"], "valid_to": ["2026-02-28", None], "rate": [10, 20]})
        >>> asof_join(left, right, "month", "k")["rate"].tolist()
        [10.0, 20.0, nan]
    """
    cols = [key] if isinstance(key, str) else list(key)
    bad = check_contiguity(right, cols, valid_from, valid_to)
    bad = bad[bad["rule"].isin(["overlap", "two_open", "reversed"])]
    if len(bad):
        raise PeriodError(f"right frame has {len(bad)} overlapping or reversed rows, for example key {bad.iloc[0]['key']}: {bad.iloc[0]['detail']}")
    d = left[date_column]
    if d.isna().any():
        raise FrameError(f"left column {date_column} must hold a date in every row, found {int(d.isna().sum())} null value(s); drop those rows or fill the date")
    when = pd.to_datetime(d.map(lambda p: month_start(p) if isinstance(p, str) and PERIOD_RE.fullmatch(p) else p)).astype("datetime64[ns]")
    lf = left.assign(_asof=when.values, _row=range(len(left))).sort_values("_asof", kind="stable")
    rf = right.copy()
    rf["_vf"], rf["_vt"] = _dates(right, valid_from, valid_to)[0].values, _dates(right, valid_from, valid_to)[1].values
    rf = rf.sort_values("_vf", kind="stable")
    rf = rf.rename(columns={c: c + suffix for c in rf.columns if c in left.columns and c not in cols and c not in ("_vf", "_vt")})
    m = pd.merge_asof(lf, rf, left_on="_asof", right_on="_vf", by=cols, direction="backward")
    stale = m["_vt"].notna() & (m["_vt"] < m["_asof"])
    right_cols = [c for c in rf.columns if c not in cols and c not in ("_vf", "_vt")]
    m.loc[stale, right_cols] = pd.NA
    return m.sort_values("_row").drop(columns=["_asof", "_row", "_vf", "_vt"]).reset_index(drop=True)


@function(sources=("hr.data_release.release",), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_periods_release.py::test_release_now_oracle_the_data_release_rows_of_the_baseline_read_directly")
def release_now(data_releases: Mapping[str, pd.DataFrame]) -> ReleaseInfo:
    """Use this when you need the one release identity (release, now, generated_at, base seed and increment) that all loaded sources share.

    Rule: each data_release frame must hold exactly one row. The five values are compared as text across the sources and must be equal; the result is then built from them, with now as a date, generated_at as a timestamp and increment as a whole number.

    Args:
        data_releases: The data_release frame of each source as {source: frame}, with the columns release, now, generated_at, base_seed and increment.

    Returns:
        ReleaseInfo: a named tuple with release (text), now (date), generated_at (timestamp), base_seed (as stored) and increment (whole number).

    Raises:
        FrameMissing: no frame was passed.
        FrameError: a frame does not have exactly one row, increment is not a whole number, or now or generated_at is not a date.
        ReleaseMismatch: the sources disagree on one of the five values.
        KeyError: a frame lacks one of the five columns.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import release_now
        >>> row = {"release": ["r1"], "now": ["2026-11-30"], "generated_at": ["2026-12-01 08:00:00"], "base_seed": ["seed-a"], "increment": [2]}
        >>> info = release_now({"hr": pd.DataFrame(row), "finance": pd.DataFrame(row)})
        >>> info.release, info.now.isoformat(), info.increment
        ('r1', '2026-11-30', 2)
    """
    if not data_releases:
        raise FrameMissing("no data_release frame was passed; pass {source: frame} for at least one source")
    seen: dict[str, Any] = {}
    for src, df in sorted(data_releases.items()):
        if len(df) != 1:
            raise FrameError(f"{src}.data_release has {len(df)} rows; it must have exactly one")
        for c in ("release", "now", "generated_at", "base_seed", "increment"):
            seen.setdefault(c, {})[src] = df.iloc[0][c]
    for c, per in seen.items():
        if len({str(v) for v in per.values()}) > 1:
            raise ReleaseMismatch(f"data_release.{c} differs between sources: " + ", ".join(f"{s}={v}" for s, v in sorted(per.items())[:4]) + ". Load all frames from one release.")
    one = {c: next(iter(per.values())) for c, per in seen.items()}
    try:
        increment = int(one["increment"])
    except (ValueError, TypeError, OverflowError):
        raise FrameError(f"data_release.increment must be a whole number, not {one['increment']!r}") from None
    stamps = {}
    for c in ("now", "generated_at"):
        try:
            stamps[c] = pd.Timestamp(one[c])
        except (ValueError, TypeError):
            raise FrameError(f"data_release.{c} must be a date, not {one[c]!r}") from None
    return ReleaseInfo(str(one["release"]), stamps["now"].date(), stamps["generated_at"], one["base_seed"], increment)


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_periods.py::test_interval_join_oracle_nested_loop")
def interval_join(points: pd.DataFrame, intervals: pd.DataFrame, *, point_ts: str = "ts", start: str = "from_ts", end: str = "to_ts", key: str | Sequence[str] | None = None,
                  inclusive_end: bool = True, how: str = "left") -> pd.DataFrame:
    """Use this when you need to attach to each point in time the interval that contains it, such as a sample and the quality event that covers it.

    Rule: a point matches an interval when start <= ts and either end is empty (an open interval) or ts <= end (ts < end without inclusive_end). With key the key columns must also be equal. A point inside two intervals appears twice. With how "left" a point without an interval is kept with empty interval columns, with "inner" it is dropped. The join runs as one merge on the key (a cross join without key), so pass a chunk of points when there are millions.

    Args:
        points: The points, one row per point, with the timestamp column and the key columns.
        intervals: The intervals, one row per interval, with the start and end columns and the key columns.
        point_ts: Name of the timestamp column of points. Default "ts".
        start: Name of the start column of intervals. Default "from_ts".
        end: Name of the end column of intervals; empty means open. Default "to_ts".
        key: Column name, or list of column names, present in both frames that must match as well. Optional.
        inclusive_end: Whether a point at the end moment is inside. Default True.
        how: "left" or "inner". Default "left".

    Returns:
        pandas.DataFrame: the columns of points, then the other columns of intervals (a name that is also a point column gets the suffix _iv), ordered by the position of the point and then the interval start, with a fresh index.

    Raises:
        FrameError: how is neither left nor inner, or a frame lacks a needed column.
        TypeError: the timestamps cannot be compared, for example one side is time zone aware and the other is not.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import interval_join
        >>> points = pd.DataFrame({"ts": [5, 12]})
        >>> intervals = pd.DataFrame({"from_ts": [0], "to_ts": [5], "label": ["X"]})
        >>> interval_join(points, intervals)["label"].tolist()
        ['X', nan]
        >>> interval_join(points, intervals, inclusive_end=False, how="inner").shape[0]
        0
    """
    if how not in ("left", "inner"):
        raise FrameError("how must be 'left' or 'inner'")
    keys = [] if key is None else [key] if isinstance(key, str) else list(key)
    for frame, cols, name in ((points, [point_ts, *keys], "points"), (intervals, [start, end, *keys], "intervals")):
        lacking = [c for c in cols if c not in frame.columns]
        if lacking:
            raise FrameError(f"{name} lacks the columns {lacking}")
    p = points.reset_index(drop=True).assign(_pt=range(len(points)))
    iv = intervals.reset_index(drop=True)
    m = p.merge(iv, on=keys, how="inner", suffixes=("", "_iv")) if keys else p.merge(iv, how="cross", suffixes=("", "_iv"))
    s_col, e_col = (start if start not in p.columns else start + "_iv"), (end if end not in p.columns else end + "_iv")
    ts = m[point_ts]
    upper = (ts <= m[e_col]) if inclusive_end else (ts < m[e_col])
    hit = m[(ts >= m[s_col]) & (m[e_col].isna() | upper)]
    if how == "left":
        miss = p[~p["_pt"].isin(hit["_pt"])]
        hit = pd.concat([hit, miss], ignore_index=True)
    return hit.sort_values(["_pt", s_col], kind="stable").drop(columns="_pt").reset_index(drop=True)
