"""Golden cases of the finance slice (standard 3.2, issue #201, lane V, V4): every file of tests/golden/finance is one case, loaded and run against the function it names.

A case holds the input, the expected output and the documents it cites. A string that starts with "=" is a formula over core facts (fact('id')), date(y, m, d), days(n), round, min, max, abs and the
names of the case's `let` block, so no legal number is typed in a case. The expected values are written by hand from the rule and the facts, not taken from the function.
Input frames are written as {columns: [...], rows: [[...]]}; `context: month3` names the stage of the context (default month12).
Expect blocks: `empty` (the result frame has no row), `rows` (one dict per row of the frame in order, the listed columns only, the row count must match), `rows_by` ({key, rows}: the rows with
these key values, the listed columns only), `contains` ({column: [values]}: each value appears in the column) and `fields` (some keys of a dict).
"""
import ast
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest
import yaml

import halvaro.finance as fin
from halvaro.core import Context, fact

GOLDEN = Path(__file__).resolve().parent / "golden" / "finance"
SLICE = {"cash_forecast_checks", "liquidity_headroom", "forecast_accuracy", "vat_return_from_ledger", "vat_code_check", "vat_settlement", "vat_filing_calendar", "tax_provision",
         "einvoice_format_share", "einvoice_gap", "rebuild_subledger_reconciliation", "fixed_asset_rollforward", "inventory_valuation_check", "bank_reconciliation", "intercompany_agreement", "open_items_ar", "open_items_ap", "retention_receivable", "ageing", "bad_debt_candidates", "customer_exposure"}
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


def test_there_is_a_case_for_every_function_of_the_slice():
    assert len(CASES) >= 21
    assert {c["function"] for _, c in CASES} == SLICE
    for stem, case in CASES:
        assert {"name", "function", "cites", "by_hand", "input", "expect"} <= set(case), stem
        assert case["cites"] and all(isinstance(c, str) for c in case["cites"]), f"{stem}: a golden case cites at least one document"


@pytest.mark.parametrize("stem,case", CASES, ids=[s for s, _ in CASES])
def test_golden_case(stem, case):
    names: dict = {}
    for k, v in (case.get("let") or {}).items():
        names[k] = resolve(v, names)
    context = Context(stage=case.get("context", "month12"), role="golden")
    result = getattr(fin, case["function"])(**build_input(case["input"], names), context=context)
    frame = result.value if hasattr(result, "value") else result
    expect = resolve(case["expect"], names)
    assert set(expect) <= {"empty", "rows", "rows_by", "contains", "fields"}, f"{stem}: unknown expect block"
    if "empty" in expect:
        assert frame.empty is expect["empty"], f"{stem}: expected empty={expect['empty']}, got {len(frame)} row(s)"
    if "fields" in expect:
        for k, want in expect["fields"].items():
            same(frame[k], want, f"{stem}.{k}")
    if "rows" in expect:
        assert len(frame) == len(expect["rows"]), f"{stem}: {len(frame)} rows, expected {len(expect['rows'])}"
        for i, want in enumerate(expect["rows"]):
            for col, w in want.items():
                same(frame.iloc[i][col], w, f"{stem}.row{i}.{col}")
    if "rows_by" in expect:
        key = expect["rows_by"]["key"]
        for want in expect["rows_by"]["rows"]:
            hit = frame[frame[key] == want[key]]
            assert len(hit) == 1, f"{stem}: {len(hit)} rows with {key} = {want[key]!r}"
            for col, w in want.items():
                same(hit.iloc[0][col], w, f"{stem}.{key}={want[key]}.{col}")
    for col, values in (expect.get("contains") or {}).items():
        missing = [v for v in values if v not in set(frame[col])]
        assert not missing, f"{stem}: column {col} lacks {missing}, has {sorted(set(frame[col]))}"


def test_the_evaluator_refuses_anything_but_arithmetic_on_facts():
    for bad in ("__import__('os')", "fact.__class__", "[1][0]", "open('x')", "1 if 2 else 3"):
        with pytest.raises(ValueError):
            evaluate(bad, {})
    assert evaluate("round(1 / 4 * 2, 1) + 1", {}) == 1.5
