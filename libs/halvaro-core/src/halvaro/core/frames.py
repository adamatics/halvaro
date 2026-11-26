"""Frame joins across sources with a report of the keys that found no partner, and the check that a loaded frame has the source column names."""
from __future__ import annotations

import dataclasses
from typing import Any, Iterable, Mapping, NamedTuple, Sequence, cast

import pandas as pd

from . import snapshot
from .access import Context, _rank
from .errors import FrameError, UnmatchedKeys
from .keys import KEY_RE
from .registry import function

ORPHAN, NOT_VISIBLE, NULL_KEY = "orphan", "master_not_visible_at_stage", "null_key"
_HOW = ("inner", "left", "right", "outer")


@dataclasses.dataclass(frozen=True)
class UnmatchedReport:
    """Keys without a partner: `left_only` and `right_only` hold one row per distinct key (key columns plus `class`), sorted by key; `counts` summarises both sides."""

    left_only: pd.DataFrame
    right_only: pd.DataFrame
    counts: dict[str, Any]

    def classes(self, side: str = "left") -> dict[Any, int]:
        """Number of unmatched keys per class on one side."""
        frame = {"left": self.left_only, "right": self.right_only}[side]
        return cast("dict[Any, int]", frame["class"].value_counts().to_dict())

    def has_orphans(self) -> bool:
        return bool((self.left_only["class"] == ORPHAN).any() or (self.right_only["class"] == ORPHAN).any())


class JoinResult(NamedTuple):
    frame: pd.DataFrame
    report: UnmatchedReport


def _key_class(values: Sequence[Any], context: Context | None) -> str:
    """Class of an unmatched key: null_key, master_not_visible_at_stage (a typed key whose master source is above the caller's stage), else orphan."""
    if any(pd.isna(v) for v in values):
        return NULL_KEY
    if context is None:
        return ORPHAN
    masters, held = snapshot.load()["masters"], _rank(context.stage)
    for v in values:
        m = KEY_RE.fullmatch(v) if isinstance(v, str) else None
        if m and m.group(1) in masters and _rank(masters[m.group(1)]["stage"]) > held:
            return NOT_VISIBLE
    return ORPHAN


def _as_list(x: Any) -> list[Any]:
    return [] if x is None else [x] if isinstance(x, str) else list(x)


def _unmatched(frame: pd.DataFrame, cols: list[Any], other: pd.DataFrame, other_cols: list[Any], context: Context | None) -> pd.DataFrame:
    keys = frame[cols].drop_duplicates()
    nulls = keys[cols].isna().any(axis=1)
    nn = keys[~nulls]
    probe = other[other_cols].dropna().drop_duplicates()
    probe.columns = cols
    lost = nn.merge(probe, on=cols, how="left", indicator=True)
    lost = lost[lost["_merge"] == "left_only"].drop(columns="_merge")
    out = pd.concat([lost, keys[nulls]], ignore_index=True)
    out["class"] = [_key_class(tuple(r), context) for r in out[cols].itertuples(index=False, name=None)]
    return out.sort_values(cols + ["class"], kind="stable", na_position="last").reset_index(drop=True)


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_join_report_oracle_counters_over_the_keys_for_four_random_pairs_of_frames",
          summary="Use this when you join two frames on key columns and need the keys without a partner, classed as orphan, null_key or master_not_visible_at_stage.",
          parameters=("left", "right", "on", "left_on", "right_on", "how", "context", "strict", "validate", "suffixes"))
def join_report(left: pd.DataFrame, right: pd.DataFrame, on: str | Sequence[str] | None = None, *, left_on: str | Sequence[str] | None = None, right_on: str | Sequence[str] | None = None,
                how: str = "left", context: Context | None = None, strict: bool | str = False, validate: str | None = None, suffixes: tuple[str, str] = ("", "_right")) -> JoinResult:
    """Use this when you join two frames on key columns and need the keys without a partner, classed as orphan, null_key or master_not_visible_at_stage.

    Rule: a null key never matches; it is reported as null_key and its row follows the matched rows. A key whose master source is above the stage of `context` is not an orphan (master_not_visible_at_stage). With strict=True orphans raise UnmatchedKeys on the sides the join has to complete (left for how="left", right for how="right", both otherwise); strict="left" or "right" checks one side whatever the join.

    Args:
        left: The left frame.
        right: The right frame.
        on: Key column name, or list of names, present in both frames. Use it or left_on and right_on, not both.
        left_on: Key column name or names of the left frame.
        right_on: Key column name or names of the right frame, as many as left_on.
        how: "inner", "left", "right" or "outer". Default "left".
        context: The caller, to tell an orphan from a key whose master is not visible at its stage. Optional.
        strict: False, True, "left" or "right". Default False.
        validate: Passed to pandas merge, for example "one_to_one". Optional.
        suffixes: Suffixes for columns that exist on both sides. Default ("", "_right").

    Returns:
        JoinResult: .frame is the joined DataFrame, .report is an UnmatchedReport with left_only, right_only and counts (rows, keys, keys without partner, null key rows).

    Raises:
        FrameError: how or strict is not one of the allowed values, the key columns are not named correctly, a key column is missing in a frame or is called "class".
        UnmatchedKeys: strict is set and a checked side has orphan keys.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import join_report
        >>> left = pd.DataFrame({"k": ["A", "B", None]})
        >>> right = pd.DataFrame({"k": ["A", "C"], "v": [1, 2]})
        >>> result = join_report(left, right, on="k")
        >>> list(result.frame.columns), result.report.counts["left_only_keys"], result.report.counts["right_only_keys"]
        (['k', 'v'], 2, 1)
        >>> result.report.left_only.to_dict("records")
        [{'k': 'B', 'class': 'orphan'}, {'k': None, 'class': 'null_key'}]
    """
    if how not in _HOW:
        raise FrameError(f"how {how!r} is not one of {', '.join(_HOW)}")
    if strict not in (False, True, "left", "right"):
        raise FrameError("strict is True, 'left' or 'right'")
    if on is not None and (left_on is not None or right_on is not None):
        raise FrameError("name the key columns with on, or with left_on and right_on, not both")
    lk, rk = _as_list(left_on if left_on is not None else on), _as_list(right_on if right_on is not None else on)
    if not lk or len(lk) != len(rk):
        raise FrameError("name the key columns with on, or left_on and right_on of the same length")
    if "class" in lk + rk:
        raise FrameError("a key column cannot be called 'class': the report uses that name; rename it first")
    for frame, cols, side in ((left, lk, "left"), (right, rk, "right")):
        missing = [c for c in cols if c not in frame.columns]
        if missing:
            raise FrameError(f"the {side} frame lacks key column(s) {', '.join(missing)}")
    lnull, rnull = left[lk].isna().any(axis=1), right[rk].isna().any(axis=1)
    kw: dict[str, Any] = dict(left_on=lk, right_on=rk, suffixes=suffixes)
    merged = left[~lnull].merge(right[~rnull], how=cast(Any, how), validate=cast(Any, validate), **kw)
    parts = [merged]
    if how in ("left", "outer") and lnull.any():
        parts.append(left[lnull].merge(right.iloc[:0], how="left", **kw))
    if how in ("right", "outer") and rnull.any():
        parts.append(left.iloc[:0].merge(right[rnull], how="right", **kw))
    frame = pd.concat(parts, ignore_index=True) if len(parts) > 1 else merged.reset_index(drop=True)
    left_only, right_only = _unmatched(left, lk, right, rk, context), _unmatched(right, rk, left, lk, context)
    counts = {"left_rows": len(left), "right_rows": len(right), "left_keys": int(left[lk].drop_duplicates().shape[0]), "right_keys": int(right[rk].drop_duplicates().shape[0]),
              "left_only_keys": len(left_only), "right_only_keys": len(right_only), "left_null_key_rows": int(lnull.sum()), "right_null_key_rows": int(rnull.sum()),
              "left_only_rows": int(left.merge(left_only.loc[left_only["class"] != NULL_KEY, lk], on=lk, how="inner").shape[0]) + int(lnull.sum()),
              "right_only_rows": int(right.merge(right_only.loc[right_only["class"] != NULL_KEY, rk], on=rk, how="inner").shape[0]) + int(rnull.sum())}
    report = UnmatchedReport(left_only, right_only, counts)
    if strict:
        wanted = {"left": ("left",), "right": ("right",)}.get(how, ("left", "right")) if strict is True else (strict,)
        for side, rep, cols in (("left", left_only, lk), ("right", right_only, rk)):
            orphans = rep[rep["class"] == ORPHAN] if side in wanted else rep.iloc[:0]
            if len(orphans):
                raise UnmatchedKeys(side, [r[0] if len(cols) == 1 else r for r in orphans[cols].itertuples(index=False, name=None)])
    return JoinResult(frame, report)


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_require_frame_columns_oracle_the_columns_of_the_data_dictionary_for_every_table")
def require_frame_columns(frame: pd.DataFrame, source_table: str, columns: Sequence[str] | str) -> None:
    """Use this when a loaded frame must carry the source column names of a table before you use it, so a renamed or dropped column is caught early.

    Rule: the table must be a 'source.table' of the data dictionary, every named column must be a column of that table in the dictionary, and every named column must exist in the frame. Extra columns in the frame are fine.

    Args:
        frame: The loaded frame of the table.
        source_table: The table as source.table, for example "hr.employee".
        columns: The column names the caller needs, as a list or a single name.

    Returns:
        None: nothing happens when all named columns are in the dictionary and in the frame.

    Raises:
        FrameError: source_table is not a source.table of the data dictionary, a named column is not a column of that table in the dictionary, or a named column is missing in the frame.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import require_frame_columns
        >>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"]})
        >>> require_frame_columns(frame, "hr.employee", ["emp_key", "hire_date"])
        >>> require_frame_columns(frame, "hr.employee", ["emp_key", "email"])
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: the frame for hr.employee lacks column(s) email; it has emp_key, hire_date. Load the source column names without renaming them.
    """
    columns = _as_list(columns)
    known = {c.split(".", 2)[2] for c in snapshot.load()["columns"] if c.startswith(source_table + ".") and c.count(".") == 2}
    if source_table.count(".") != 1 or not known:
        raise FrameError(f"{source_table!r} is not a table of the data dictionary; use source.table")
    unknown = [c for c in columns if c not in known]
    if unknown:
        raise FrameError(f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not column(s) of {source_table}; its columns are {', '.join(sorted(known))}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"the frame for {source_table} lacks column(s) {', '.join(missing)}; it has {', '.join(map(str, frame.columns[:12]))}. Load the source column names without renaming them.")


_REDUCERS = {"sum": "sum", "count": "sum", "min": "min", "max": "max"}


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_frames.py::test_reduce_chunks_oracle_loop_over_all_rows_for_any_cut_into_chunks")
def reduce_chunks(chunks: Iterable[pd.DataFrame], by: str | Sequence[str], aggregations: Mapping[str, tuple[str, str]]) -> pd.DataFrame:
    """Use this when the rows come as an iterable of frames (chunks) and you need grouped sums, counts, minima or maxima with the same result as one frame, without holding all rows at once.

    Rule: each chunk is reduced on its own per group, then the partial results are combined (sum for sum and count, min of minima, max of maxima), so memory is one chunk plus one row per group. count counts the non null values. Groups with a null key are kept. The result is sorted by the by columns. With no by columns the result has one row over all chunks. An empty chunk adds nothing; when every chunk is empty the result has no rows.

    Args:
        chunks: The frames to reduce, for example read one after the other. At least one frame is needed; an empty frame is fine.
        by: The column or columns to group by, a name or a list. An empty list gives one row over all rows.
        aggregations: A mapping from an output column to a pair (input column, function), the function being sum, count, min or max.

    Returns:
        pandas.DataFrame: the by columns followed by the output columns in the order of aggregations, one row per group, sorted by the by columns.

    Raises:
        FrameError: chunks is one frame and not an iterable of frames; an aggregation is not a (column, function) pair; a function is none of sum, count, min and max; no chunk was given; or a chunk lacks a by column or an input column (the message names the chunk number).

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import reduce_chunks
        >>> first = pd.DataFrame({"g": ["x", "x", "y"], "v": [1, 2, 3], "w": [1, 2, None]})
        >>> second = pd.DataFrame({"g": ["y", "z"], "v": [10, 20], "w": [None, 4]})
        >>> reduce_chunks([first, second], "g", {"total": ("v", "sum"), "n": ("w", "count")})
           g  total  n
        0  x      3  2
        1  y     13  0
        2  z     20  1
    """
    if isinstance(chunks, pd.DataFrame):
        raise FrameError("chunks must be an iterable of frames, not one frame; pass [frame]")
    by = [by] if isinstance(by, str) else list(by)
    for out, pair in aggregations.items():
        try:
            if isinstance(pair, str):
                raise TypeError
            col, fn = pair
        except (TypeError, ValueError):
            raise FrameError(f"aggregation {out!r} must be a pair (column, function), not {pair!r}") from None
        if fn not in _REDUCERS:
            raise FrameError(f"aggregation {out!r}: function {fn!r} is not one of {', '.join(_REDUCERS)}")
    parts, seen = [], 0
    for chunk in chunks:
        seen += 1
        need = [*by, *{col for col, _ in aggregations.values()}]
        lacking = [c for c in need if c not in chunk.columns]
        if lacking:
            raise FrameError(f"chunk {seen} lacks the columns {lacking}")
        if chunk.empty:
            continue
        if by:
            g = chunk.groupby(by, dropna=False)
            part = pd.concat({out: getattr(g[col], fn)() for out, (col, fn) in aggregations.items()}, axis=1).reset_index()
        else:
            part = pd.DataFrame({out: [getattr(chunk[col], fn)()] for out, (col, fn) in aggregations.items()})
        parts.append(part)
    if not seen:
        raise FrameError("reduce_chunks got no chunk; pass at least one frame (an empty one is fine)")
    cols = [*by, *aggregations]
    if not parts:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in cols})
    allp = pd.concat(parts, ignore_index=True)
    comb = {out: _REDUCERS[fn] for out, (_, fn) in aggregations.items()}
    if by:
        res = allp.groupby(by, dropna=False).agg(comb).reset_index().sort_values(by, kind="stable").reset_index(drop=True)
    else:
        res = pd.DataFrame({out: [getattr(allp[out], f)()] for out, f in comb.items()})
    return cast(pd.DataFrame, res[cols])
