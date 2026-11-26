"""Golden error cases of halvaro-finance (standard 3.2.2, lane P2, issue #469).

Every public function that refuses a wrong input with an error of the library (FrameError and the other errors of halvaro.core that are not a stage or access refusal) or with a ValueError has a
golden case, one YAML file per case in tests/golden_errors (`<function>.yaml`, a second case `<function>.2.yaml`; the files carry the keys `function` and `raises` that tools/check_lib_standard.py reads): a wrong input, the class of the error and its message as the golden text. A reworded message or another class fails the case, on purpose: a caller reads the
message. A function without a case is listed in no_case.yaml with the reason. The inputs are empty or invented frames; no restricted column carries a value.

Case format: `args` and `kwargs` are YAML values; a mapping `{frame: {columns: [...], rows: [[...]]}}` is a DataFrame (`{frame: {}}` is an empty one) and a date is a date. `context` names the stage of a
Context (role analyst) or is a mapping of Context arguments. `message` is the whole text; `message_starts` is used only where the text ends in a list that grows with the data (the case says why).
"""
import pathlib

import pandas as pd
import pytest
import yaml

import halvaro.finance as lib
import halvaro.core as core
from halvaro.core import Context, snapshot

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden_errors"
FILES = sorted(p for p in GOLDEN.glob("*.yaml") if p.name != "no_case.yaml")
CASES = [(yaml.safe_load(p.read_text(encoding="utf-8")), p.name) for p in FILES]
CASES = [(case["function"], name, case) for case, name in CASES]
NO_CASE = yaml.safe_load((GOLDEN / "no_case.yaml").read_text(encoding="utf-8"))["no_case"]
RESTRICTED = {c.rsplit(".", 1)[-1] for c in snapshot.load()["restricted_columns"]}


def build(value):
    if isinstance(value, dict) and set(value) == {"frame"}:
        spec = value["frame"]
        return pd.DataFrame(spec.get("rows", []), columns=spec["columns"]) if spec.get("columns") else pd.DataFrame()
    if isinstance(value, dict):
        return {k: build(v) for k, v in value.items()}
    if isinstance(value, list):
        return [build(v) for v in value]
    return value


def context_of(spec):
    if spec is None:
        return None
    return Context(stage=spec, role="analyst") if isinstance(spec, str) else Context(**spec)


def registered() -> dict:
    return {n: getattr(lib, n) for n in lib.__all__ if hasattr(getattr(lib, n, None), "__halvaro__")}


def check(function: str, case: dict) -> None:
    """Run one case; AssertionError when it does not raise, raises another class, or the message differs."""
    kwargs = build(case.get("kwargs", {}))
    if "context" in case:
        kwargs["context"] = context_of(case["context"])
    try:
        registered()[function](*build(case.get("args", [])), **kwargs)
    except Exception as e:                                                  # the class and the text are what is checked
        assert type(e).__name__ == case["raises"], f"{function}: raised {type(e).__name__}, the case says {case['raises']}: {e}"
        text = str(e)
        if "message_starts" in case:
            assert text.startswith(case["message_starts"]), f"{function}: {text!r} does not start with {case['message_starts']!r}"
        else:
            assert text == case["message"], f"{function}: the message is {text!r}, the golden text is {case['message']!r}"
    else:
        raise AssertionError(f"{function}: no error, the case says {case['raises']}")


@pytest.mark.parametrize("function,file,case", CASES, ids=[name.removesuffix(".yaml") for _, name, _ in CASES])
def test_golden_error_case(function, file, case):
    check(function, case)


def test_every_registered_function_has_a_case_or_a_reason():
    names = set(registered())
    with_case, without = {fn for fn, _, _ in CASES}, set(NO_CASE)
    assert not with_case & without, f"both a case and a reason: {sorted(with_case & without)}"
    assert names == with_case | without, f"no case and no reason: {sorted(names - with_case - without)}; not registered: {sorted((with_case | without) - names)}"
    assert all(isinstance(r, str) and len(r) >= 20 for r in NO_CASE.values()), "a reason is a sentence"


def test_every_case_names_the_error_and_says_why():
    for fn, i, case in CASES:
        assert i.split(".")[0] == fn, f"{i}: the file is named after the function"
        assert case["raises"] in dir(core) or case["raises"] == "ValueError", f"{fn}-{i}: {case['raises']} is not an error of halvaro.core"
        assert ("message" in case) != ("message_starts" in case), f"{fn}-{i}: exactly one of message and message_starts"
        assert len(case.get("why", "")) >= 15, f"{fn}-{i}: the case says why"
        assert case["raises"] not in ("StageRefusal", "RestrictedColumnRefusal", "AggregateRefusal"), f"{fn}-{i}: a refusal has its own tests"


def test_no_case_carries_a_restricted_column_with_a_value():
    def frames(v):
        if isinstance(v, dict) and set(v) == {"frame"}:
            yield v["frame"]
        elif isinstance(v, dict):
            for x in v.values():
                yield from frames(x)
        elif isinstance(v, list):
            for x in v:
                yield from frames(x)
    for fn, i, case in CASES:
        for spec in frames([case.get("args", []), case.get("kwargs", {})]):
            assert not (set(spec.get("columns", [])) & RESTRICTED and spec.get("rows")), f"{fn}-{i}: a restricted column with rows"


def test_the_check_fails_on_a_changed_message_a_changed_class_and_a_missing_error(monkeypatch):
    function, _, case = next((fn, i, c) for fn, i, c in CASES if "message" in c)
    for bad in ({**case, "message": case["message"] + " changed"}, {**case, "raises": "ValueError" if case["raises"] != "ValueError" else "FrameError"}):
        with pytest.raises(AssertionError):
            check(function, bad)
    monkeypatch.setitem(globals(), "registered", lambda: {"quiet": lambda: None})
    with pytest.raises(AssertionError, match="no error"):
        check("quiet", {"raises": "FrameError", "message": "x"})
