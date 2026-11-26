"""Golden cases of halvaro-core as YAML (standard 3.2.2, lane W1, issue #504): every file of tests/golden is one case, loaded and run against the function it names.

A case holds the input, the expected output and a by_hand text that says how the expected value was worked out from the rule, not taken from the function. Argument values: plain YAML values
(dates are dates), `{frame: {columns, rows}}`, `{context: {stage, role, restricted_ok}}`, `{envelope: {as_of, basis}}`, `{refusal: {sources, stage, held, function}}` and `{call: name}` for a function
from CALLS below (the three functions that take a function). Expect: `value` (equality, numpy numbers read as plain numbers), `columns` (the columns of a frame), `raises` ({error, message_contains}).
"""
import builtins
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest
import yaml

import halvaro.core as core
from halvaro.core import Context

GOLDEN = Path(__file__).resolve().parent / "golden"
FILES = sorted(GOLDEN.glob("*.yaml"))


class Loader:
    """A loader that follows the contract (exact columns in order, `columns` honoured, chunks that add up to the table)."""

    def __init__(self):
        self.frame = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "team_key": ["T1", "T2"]})

    def load(self, source, table, columns=None, where=None):
        return (self.frame if columns is None else self.frame[list(columns)]).reset_index(drop=True)

    def iter_chunks(self, source, table, columns=None, where=None):
        frame = self.load(source, table, columns)
        for i in range(0, len(frame), 1):
            yield frame.iloc[i:i + 1]


CALLS = {
    "rows_until_the_date": lambda frames, as_of: frames["t"][pd.to_datetime(frames["t"]["d"]) <= pd.Timestamp(as_of)],
    "needs_hr_site": lambda frames, ctx: core.require_sources(ctx, ["hr.site"]),
    "needs_finance_line": lambda frames, ctx: core.require_sources(ctx, ["finance.journal_line"]),
    "contract_loader": Loader(),
}


def build(v):
    if isinstance(v, dict) and set(v) == {"frame"}:
        f = v["frame"]
        return pd.DataFrame(f.get("rows", []), columns=f["columns"])
    if isinstance(v, dict) and set(v) == {"context"}:
        return Context(**v["context"])
    if isinstance(v, dict) and set(v) == {"envelope"}:
        return core.make_envelope(1, None, **v["envelope"])
    if isinstance(v, dict) and set(v) == {"refusal"}:
        r = v["refusal"]
        return core.StageRefusal(r["sources"], r["stage"], r["held"], r["function"])
    if isinstance(v, dict) and set(v) == {"call"}:
        return CALLS[v["call"]]
    if isinstance(v, dict):
        return {k: build(x) for k, x in v.items()}
    if isinstance(v, list):
        return [build(x) for x in v]
    return v


def plain(x):
    if hasattr(x, "item") and getattr(x, "ndim", 1) == 0:
        return x.item()
    if isinstance(x, pd.DataFrame):
        return x.to_dict("records")
    return x


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_golden_case(path):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn = getattr(core, case["function"])
    args, kwargs = build(case["input"].get("args", [])), build(case["input"].get("kwargs", {}))
    expect = case["expect"]
    if "raises" in expect:
        with pytest.raises(getattr(core, expect["raises"]["error"], None) or getattr(builtins, expect["raises"]["error"])) as e:
            fn(*args, **kwargs)
        assert expect["raises"]["message_contains"] in str(e.value)
        return
    got = fn(*args, **kwargs)
    if "columns" in expect:
        assert list(got.columns) == expect["columns"]
    if "value" in expect:
        assert plain(got) == expect["value"]


def test_every_case_names_a_registered_function_and_says_how_it_was_worked_out():
    names = {n for n in core.__all__ if hasattr(getattr(core, n, None), "__halvaro__")}
    for p in FILES:
        case = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert case["function"] in names and len(case.get("by_hand", "")) >= 20 and ("value" in case["expect"] or "columns" in case["expect"] or "raises" in case["expect"]), p.name
