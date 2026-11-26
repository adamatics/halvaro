"""Golden cases of the holiday functions (standard 3.2, issue #196, F4): every file of tests/golden/holiday is one case, loaded and run against the function it names.

A case holds the input, the expected output and the provisions it cites. A string that starts with "=" is a formula over core facts (fact('id')), date(y, m, d), days(n), round, min, max, abs and the
names of the case's `let` block, so no legal number is typed in a case. The expected values are written by hand from the rule and the facts, not taken from the function.
Expect blocks: `value` (a text, or a list for a tuple), `fields` (some keys of a dict) or `rows` (one dict per row of the frame, the listed columns only, the row count must match).
"""
import ast
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest
import yaml

import halvaro.hr as hr
from halvaro.core import fact
from halvaro.hr.holiday_results import RESULT_CONTAINERS

GOLDEN = Path(__file__).resolve().parent / "golden" / "holiday"
FUNCTIONS = {"holiday_year_label", "holiday_year_bounds", "holiday_balance", "holiday_ledger", "carry_over_position", "carry_over_projection", "accrual_expected", "leave_vs_ledger", "high_carry_over"}
RESULT_CONTAINERS_TYPES = tuple(RESULT_CONTAINERS.values())
_CALLS = {"fact": lambda i: fact(i).value, "date": dt.date, "days": lambda n: dt.timedelta(days=n), "round": round, "min": min, "max": max, "abs": abs}


def evaluate(formula: str, names: dict):
    """Value of a formula: numbers, names of `let`, the calls above and + - * / only."""
    def node(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str)):
            return n.value
        if isinstance(n, ast.Name) and n.id in names:
            return names[n.id]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -node(n.operand) if isinstance(n.op, ast.USub) else node(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = node(n.left), node(n.right)
            return a + b if isinstance(n.op, ast.Add) else a - b if isinstance(n.op, ast.Sub) else a * b if isinstance(n.op, ast.Mult) else a / b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _CALLS and not n.keywords:
            return _CALLS[n.func.id](*[node(a) for a in n.args])
        raise ValueError(f"formula {formula!r}: {ast.dump(n)[:60]} is not allowed")
    return node(ast.parse(formula, mode="eval").body)


def resolve(value, names: dict):
    """Evaluate every formula string inside a loaded YAML value."""
    if isinstance(value, str) and value.startswith("="):
        return evaluate(value[1:], names)
    if isinstance(value, list):
        return [resolve(v, names) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, names) for k, v in value.items()}
    return value


def load_cases() -> list:
    return [(p.stem, yaml.safe_load(p.read_text(encoding="utf-8"))) for p in sorted(GOLDEN.glob("*.yaml"))]


def build_input(spec: dict, names: dict) -> dict:
    out = {}
    for key, value in spec.items():
        if isinstance(value, dict) and "columns" in value and "rows" in value:
            out[key] = pd.DataFrame([resolve(r, names) for r in value["rows"]], columns=value["columns"])
        else:
            out[key] = resolve(value, names)
    return out


def same(actual, expected, where: str) -> None:
    if expected is None:
        assert actual is None or pd.isna(actual), f"{where}: expected a missing value, got {actual!r}"
    elif isinstance(expected, bool):
        assert bool(actual) is expected, f"{where}: expected {expected}, got {actual!r}"
    elif isinstance(expected, (int, float)):
        assert actual == pytest.approx(expected, abs=1e-9), f"{where}: expected {expected}, got {actual!r}"
    else:
        assert actual == expected, f"{where}: expected {expected!r}, got {actual!r}"


CASES = load_cases()


def test_there_are_cases_for_the_holiday_act_rules():
    assert len(CASES) >= 12 and {c["function"] for _, c in CASES} <= FUNCTIONS
    assert {"holiday_year_label", "holiday_year_bounds", "accrual_expected", "carry_over_position", "carry_over_projection", "holiday_balance", "holiday_ledger", "leave_vs_ledger"} <= {c["function"] for _, c in CASES}
    for stem, case in CASES:
        assert {"name", "function", "cites", "input", "expect"} <= set(case), stem
        assert case["cites"] and all(isinstance(c, str) for c in case["cites"]), f"{stem}: a golden case cites at least one provision"


@pytest.mark.parametrize("stem,case", CASES, ids=[s for s, _ in CASES])
def test_golden_case(stem, case):
    names: dict = {}
    for k, v in (case.get("let") or {}).items():
        names[k] = resolve(v, names)
    result = getattr(hr, case["function"])(**build_input(case["input"], names))
    if isinstance(result, RESULT_CONTAINERS_TYPES):          # typed results (issue #233): the cases are written over the columns and keys, so read the frame or the dict form
        result = result.to_frame()
    elif isinstance(result, hr.HolidayBalance):
        result = result.to_dict()
    expect = resolve(case["expect"], names)
    assert set(expect) <= {"value", "fields", "rows"}, f"{stem}: unknown expect block"
    if "value" in expect:
        want = expect["value"]
        same(list(result) if isinstance(want, list) else result, want, stem)
    if "fields" in expect:
        for k, want in expect["fields"].items():
            same(result[k], want, f"{stem}.{k}")
    if "rows" in expect:
        assert len(result) == len(expect["rows"]), f"{stem}: {len(result)} rows, expected {len(expect['rows'])}"
        for i, want in enumerate(expect["rows"]):
            for col, w in want.items():
                same(result.iloc[i][col], w, f"{stem}.row{i}.{col}")


def test_the_evaluator_refuses_anything_but_arithmetic_on_facts():
    for bad in ("__import__('os')", "fact.__class__", "[1][0]", "open('x')", "1 if 2 else 3"):
        with pytest.raises(ValueError):
            evaluate(bad, {})
    assert evaluate("round(1 / 4 * 2, 1) + 1", {}) == 1.5
