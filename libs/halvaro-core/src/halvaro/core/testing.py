"""Test helpers for libraries and apps (plan 5.11): the stage matrix, the as-of stability check and the loader contract. They return problems as text or raise AssertionError; nothing here reads a release."""
from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

from . import snapshot
from .access import Context, visible_sources
from .errors import HalvaroError, StageRefusal
from .registry import function, registered


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_testing.py::test_stage_matrix_oracle_a_correct_function_refuses_exactly_where_sources_are_missing")
def stage_matrix(function_id: str, frames: Mapping[str, pd.DataFrame], call: Callable[[dict[str, pd.DataFrame], Context], Any], *, role: str = "test", stages: Sequence[str] | None = None,
                 strict: bool = True) -> list[dict[str, Any]]:
    """Use this when you need to prove that a function gives a result where all its sources are visible and refuses, naming the missing sources, where they are not.

    Rule: for each stage the call is run with only those frames whose source the stage can see. A stage that sees every registered source of the function must give a result; a stage that misses a source must raise StageRefusal naming exactly the missing sources. A result where a refusal was expected, a refusal naming other sources, or a refusal at a stage that misses none is not ok; any other exception from call propagates.

    Args:
        function_id: The id of a registered function, for example "halvaro.core.org.cost_centre_of_team".
        frames: The frames to offer, as {"source.table": frame}.
        call: A function that takes the visible frames (a dict of the same form) and a Context, and runs the function under test.
        role: The role written into the Context. Default "test".
        stages: The stages to run, in order. Default: all stages of the snapshot.
        strict: Whether a row that is not ok raises AssertionError. Default True.

    Returns:
        list: one dict per stage with the keys stage, expected ("result" or "refusal"), outcome ("result" or "refusal") and ok (True or False).

    Raises:
        HalvaroError: the function id is not registered.
        ProfileError: a stage is not a known stage.
        AssertionError: strict is true and a stage did not behave as expected.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import cost_centre_of_team, stage_matrix
        >>> frames = {"hr.team": pd.DataFrame({"team_key": ["T1"], "cost_centre_key": ["CC-1"]})}
        >>> rows = stage_matrix("halvaro.core.org.cost_centre_of_team", frames, lambda visible, ctx: cost_centre_of_team(visible["hr.team"], "T1"), stages=["day1", "month3"])
        >>> [(r["stage"], r["outcome"], r["ok"]) for r in rows]
        [('day1', 'result', True), ('month3', 'result', True)]
    """
    meta = registered().get(function_id)
    if meta is None:
        raise HalvaroError(f"{function_id} is not a registered function")
    needed = {s.split(".")[0] for s in meta.sources}
    rows = []
    for stage in stages or snapshot.load()["stage_order"]:
        seen = visible_sources(stage)
        missing = sorted(needed - seen)
        visible = {k: v for k, v in frames.items() if k.split(".")[0] in seen}
        expected = "refusal" if missing else "result"
        try:
            call(visible, Context(stage=stage, role=role))
            outcome, ok = "result", not missing
        except StageRefusal as e:
            outcome, ok = "refusal", bool(missing) and sorted(e.missing_sources) == missing
        rows.append({"stage": stage, "expected": expected, "outcome": outcome, "ok": ok})
    bad = [r for r in rows if not r["ok"]]
    if strict and bad:
        raise AssertionError(f"stage matrix of {function_id}: " + "; ".join(f"{r['stage']} expected {r['expected']}, got {r['outcome']}" for r in bad))
    return rows


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_testing.py::test_asof_stable_oracle_equal_changed_added_and_allowed_rows")
def asof_stable(call: Callable[[Mapping[str, pd.DataFrame], dt.date], Any], baseline: Mapping[str, pd.DataFrame], later: Mapping[str, pd.DataFrame], as_of: dt.date, *, key: str,
                allowed_keys: Iterable[Any] = ()) -> bool:
    """Use this when you need to prove that a result as of a date does not change when a later data release is loaded, except for rows that an effective dated change may alter.

    Rule: the call is run on the baseline frames and on the later frames with the same date. Both results (or the value of each, when it is an envelope) must have the same columns. They are then matched on the key column: a key present on one side only, or with a different value in any shared column (two empty values are equal), counts as changed. Changed keys that are not in allowed_keys fail the check. Row order does not matter.

    Args:
        call: A function that takes a mapping of frames and the date and returns a frame, or an envelope whose value is a frame.
        baseline: The frames of the baseline release, as {"source.table": frame}.
        later: The frames of the later release, in the same form.
        as_of: The date given to the call for both releases.
        key: Name of the column that identifies a row in the result.
        allowed_keys: Values of the key column whose rows may differ. Default none.

    Returns:
        bool: True when the check passes (a failure raises instead).

    Raises:
        AssertionError: the two results have different columns, or rows differ for a key that is not allowed.
        KeyError: the key is not a column of a result.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import asof_stable
        >>> base = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 2]})}
        >>> later = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 3]})}
        >>> call = lambda frames, day: frames["t"]
        >>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k", allowed_keys=["B"])
        True
        >>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k")
        Traceback (most recent call last):
        ...
        AssertionError: results at 2026-06-30 differ between releases for k ['B']
    """
    a, b = (call(f, as_of) for f in (baseline, later))
    a, b = (getattr(r, "value", r) for r in (a, b))
    only = sorted(set(map(str, a.columns)) ^ set(map(str, b.columns)))
    if only:
        raise AssertionError(f"results at {as_of} have different columns between releases: {only}")
    a, b = a.sort_values(key).reset_index(drop=True), b.sort_values(key).reset_index(drop=True)
    m = a.merge(b, how="outer", on=key, suffixes=("_a", "_b"), indicator=True)
    changed = set(m.loc[m["_merge"] != "both", key])
    for c in [c for c in a.columns if c != key and c in b.columns]:
        both = m[m["_merge"] == "both"]
        x, y = both[f"{c}_a"], both[f"{c}_b"]
        diff = ~((x == y) | (x.isna() & y.isna()))
        changed |= set(both.loc[diff, key])
    unexpected = sorted(changed - set(allowed_keys), key=str)
    if unexpected:
        raise AssertionError(f"results at {as_of} differ between releases for {key} {unexpected[:10]}{' ...' if len(unexpected) > 10 else ''}")
    return True


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_testing.py::test_loader_contract_oracle_each_defect_gives_exactly_one_problem_naming_the_table")
def loader_contract(loader: Any, expected_columns: Mapping[str, list[str]], *, context: Context | None = None, restricted_columns: Iterable[str] = (),
                    where: Mapping[str, tuple[str, Any]] | None = None) -> list[str]:
    """Use this when you need to check that an app loader (SQL or API) keeps the loading contract, and get the problems as text.

    Rule: for each table the loader is called and checked: the column names are exactly the expected ones, in order; no timestamp column is time zone aware; the columns argument returns just the first two expected columns (only those two are requested); a where condition (column equal to value) is honoured; no restricted column is present when the context does not allow restricted access; and the chunks of iter_chunks put together equal load. One problem is written per broken check. Only the first load call of a table is guarded: a table that fails it is a problem and the other checks of that table are skipped; exceptions raised by later load calls or by iter_chunks propagate. Dtype checks are not run.

    Args:
        loader: An object with load(source, table, columns=None, where=None) and iter_chunks(source, table, columns=None, where=None), both returning frames.
        expected_columns: The exact source column names per table, as {"source.table": [columns]}.
        context: The caller. The restricted check runs only when it is given and does not allow restricted access. Default None.
        restricted_columns: Names of the restricted columns. Default none.
        where: Optional equality conditions as {"source.table": (column, value)}.

    Returns:
        list: the problems as text, one per broken check, each starting with the table name; empty when the loader passes.

    Raises:
        ValueError: a table name in expected_columns does not have the form source.table.
        KeyError: a where column is not a column of the loaded table.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import loader_contract
        >>> class Loader:
        ...     frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        ...     def load(self, source, table, columns=None, where=None):
        ...         return self.frame if columns is None else self.frame[columns]
        ...     def iter_chunks(self, source, table, columns=None, where=None):
        ...         yield self.frame.iloc[:1]
        ...         yield self.frame.iloc[1:]
        >>> loader_contract(Loader(), {"s.t": ["a", "b"]})
        []
        >>> loader_contract(Loader(), {"s.t": ["b", "a"]})
        ["s.t: columns ['a', 'b'] differ from ['b', 'a']"]
    """
    found = []
    where = where or {}
    for name, cols in expected_columns.items():
        source, table = name.split(".", 1)
        try:
            full = loader.load(source, table)
        except Exception as e:                      # noqa: BLE001 the problem is the failure
            found.append(f"{name}: load failed: {e}")
            continue
        if list(full.columns) != list(cols):
            found.append(f"{name}: columns {list(full.columns)} differ from {list(cols)}")
        for c in full.columns:
            if pd.api.types.is_datetime64tz_dtype(full[c]):  # type: ignore[attr-defined] # removed from the pandas stubs, still in pandas 2.x (behaviour kept)
                found.append(f"{name}.{c}: timestamps must be UTC naive, found tz aware")
        if context is not None and not context.restricted_ok:
            leaked = sorted(set(restricted_columns) & set(full.columns))
            if leaked:
                found.append(f"{name}: restricted columns present for a context that forbids them: {leaked}")
        pick = [c for c in cols if c in full.columns][:2]
        if pick:
            got = loader.load(source, table, columns=pick)
            if list(got.columns) != pick:
                found.append(f"{name}: columns={pick} returned {list(got.columns)}")
        if name in where:
            col, val = where[name]
            got = loader.load(source, table, where={col: val})
            if len(got) != int((full[col] == val).sum()) or (len(got) and not (got[col] == val).all()):
                found.append(f"{name}: where {col}={val!r} not honoured")
        chunks = list(loader.iter_chunks(source, table))
        joined = pd.concat(chunks, ignore_index=True) if chunks else full.iloc[0:0]
        if not joined.reset_index(drop=True).equals(full.reset_index(drop=True)):
            found.append(f"{name}: iter_chunks joined does not equal load")
    return found
