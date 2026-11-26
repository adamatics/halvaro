"""Property tests of halvaro-esg (standard 3.2.3; lane P3, #482): two rules that every function must keep, checked on the calls of its docstring examples.

Each test runs the examples of one module with every public function of the module wrapped. On each call the arguments are copied first; after the call they must equal the copies
(a function never changes its inputs), and a second call with the same arguments must give an equal result (the result depends on the arguments only: no hidden state, no clock, no
randomness). A function that no example calls fails the test, so the examples cannot lose a function. The expected values are the inputs themselves and the first result, never a copy
of the function body."""
from __future__ import annotations

import copy
import dataclasses
import doctest
import importlib
import math

import numpy as np
import pandas as pd

import halvaro.esg as lib


def _equal(a, b) -> bool:
    if isinstance(a, (pd.DataFrame, pd.Series, pd.Index)):
        return type(a) is type(b) and a.equals(b) and (not isinstance(a, pd.DataFrame) or list(a.columns) == list(b.columns))
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.shape == b.shape and all(_equal(x, y) for x, y in zip(a.ravel().tolist(), b.ravel().tolist()))
    if dataclasses.is_dataclass(a) and not isinstance(a, type):
        return type(a) is type(b) and all(_equal(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a))
    if isinstance(a, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return isinstance(b, dict) and list(a) == list(b) and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    try:
        same = a == b
        return bool(same) if not isinstance(same, (np.ndarray, pd.Series)) else bool(np.all(same))
    except (TypeError, ValueError):
        return a is b


def _check(module: str, names: list[str]) -> None:
    calls: dict[str, int] = {n: 0 for n in names}
    problems: list[str] = []
    real = {n: getattr(lib, n) for n in names}

    def wrapped(name):
        fn = real[name]

        def call(*args, **kwargs):
            before = copy.deepcopy((args, kwargs))
            first = fn(*args, **kwargs)
            if not _equal((args, kwargs), before):
                problems.append(f"{name} changed its inputs")
            second = fn(*copy.deepcopy(before[0]), **copy.deepcopy(before[1]))
            if not _equal(first, second):
                problems.append(f"{name} gave a different result on a second call with the same arguments")
            calls[name] += 1
            return first
        return call

    for n in names:
        setattr(lib, n, wrapped(n))
    try:
        mod = importlib.import_module(f"halvaro.esg.{module}")
        runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
        for test in doctest.DocTestFinder(exclude_empty=True).find(mod, mod.__name__):
            runner.run(test, out=lambda s: None)
        failed = runner.summarize(verbose=False).failed
    finally:
        for n in names:
            setattr(lib, n, real[n])
    assert failed == 0, f"{failed} docstring example(s) of {module} fail"
    assert [n for n, k in calls.items() if not k] == [], "no example calls these functions"
    assert problems == [], "; ".join(sorted(set(problems)))


def test_property_activity_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("activity", ['check_meters', 'consumption_by', 'electricity_contract_share', 'energy_cost', 'energy_use_mwh', 'invoice_tie_out'])


def test_property_audit_targets_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("audit_targets", ['audit_schedule', 'target_progress'])


def test_property_basis_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("basis", ['provenance', 'reporting_basis', 'size_evidence'])


def test_property_data_requests_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("data_requests", ['answer_pack', 'open_requests', 'request_timeliness', 'tender_limit'])


def test_property_factors_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("factors", ['factor_on', 'factor_set_diff', 'family_key', 'flag_synthetic', 'product_basis_share'])


def test_property_footprint_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("footprint", ['component_split', 'limit_check', 'per_metre', 'project_footprint_from_lines', 'project_scope_split', 'tender_estimate'])


def test_property_ghg_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("ghg", ['intensity', 'renewable_effect', 'scope2_dual', 'scope3_by_category', 'scope3_coverage', 'scope_totals', 'statement_inputs', 'winter_decomposition', 'winter_ratio'])


def test_property_levers_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("levers", ['lever_fuel_switch', 'lever_material_substitution', 'lever_report'])


def test_property_lines_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("lines", ['as_first_booked', 'as_of_view', 'assert_no_double_count', 'current_basis', 'restatement_bridge', 'restatement_pairs', 'validate_lines'])


def test_property_recompute_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("recompute", ['expected_goods_lines', 'expected_lines_s123', 'expected_service_lines', 'expected_waste_lines', 'recompute_diff'])


def test_property_score_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("score", ['indicator_values', 'score_indicators', 'scorecard'])


def test_property_lists_name_every_public_function_of_each_module():
    import ast
    import inspect
    from pathlib import Path
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    listed = {c.args[0].value: sorted(e.value for e in c.args[1].elts) for c in ast.walk(tree)
              if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_check" and isinstance(c.args[0], ast.Constant)}
    want: dict[str, list[str]] = {}
    for n in lib.__all__:
        f = getattr(lib, n, None)
        if inspect.isfunction(f) and hasattr(f, "__halvaro__"):
            want.setdefault(f.__module__.rsplit(".", 1)[1], []).append(n)
    assert listed == {m: sorted(v) for m, v in want.items()}, "a module or a function is missing from the property tests: run the generator of lane P3 again or add it by hand"
