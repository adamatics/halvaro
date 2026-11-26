"""Golden error cases of halvaro-esg (standard 3.2.2 and 3.7.5; lane P3, #482): tests/golden/<module>/*.yaml, one file per case. A case names the function, the frames it is called
with (keyword: rows), the other arguments and the error it must raise, with the message as the golden text: an error names the argument, the value and what is allowed. The expected
message is written when the case is written and only changes with a behaviour-changes entry."""
from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest
import yaml
from halvaro.core import Context

import halvaro.esg as lib

GOLDEN = Path(__file__).resolve().parent / "golden"
CASES = sorted(GOLDEN.rglob("*.yaml"))
PUBLIC = {n: getattr(lib, n) for n in lib.__all__ if inspect.isfunction(getattr(lib, n)) and hasattr(getattr(lib, n), "__halvaro__")}


def _frame(rows):
    frame = pd.DataFrame(rows["rows"] if isinstance(rows, dict) else rows)
    if isinstance(rows, dict):
        for c in rows.get("dates", []):
            frame[c] = pd.to_datetime(frame[c])
    return frame


def test_every_case_names_a_function_of_its_module_folder():
    assert CASES, "no golden case"
    for p in CASES:
        case = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert case["id"] == p.stem and case.get("rule"), f"{p.name}: an id equal to the file name and a rule"
        fn = PUBLIC[case["function"]]
        assert fn.__module__.rsplit(".", 1)[1] == p.parent.name, f"{p.name}: the folder is the module of {case['function']}"


@pytest.mark.parametrize("path", CASES, ids=[f"{p.parent.name}/{p.stem}" for p in CASES])   # the module folder is part of the id: e01-... is unique per folder only (lane W2)
def test_golden_case(path):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn = PUBLIC[case["function"]]
    kwargs = {k: _frame(v) for k, v in (case.get("frames") or {}).items()}
    kwargs.update(case.get("args") or {})
    if "context" in inspect.signature(fn).parameters:
        kwargs["context"] = Context(stage=case.get("stage", "month12"), role="golden")
    want = case["raises"]
    with pytest.raises(Exception) as e:
        fn(*[_frame(v) for v in case.get("positional_frames", [])], *case.get("positional", []), **kwargs)
    assert type(e.value).__name__ == want["error"], f"{type(e.value).__name__}: {e.value}"
    assert str(e.value) == want["message"]
    assert all(w in str(e.value) for w in want.get("names", [])), "the message names the argument and the value"
