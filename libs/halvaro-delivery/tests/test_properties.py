"""Property tests of halvaro-delivery (standard 3.2.3; lane P3, #482): two rules that every function must keep, checked on the calls of its docstring examples.

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

import halvaro.delivery as lib


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
        mod = importlib.import_module(f"halvaro.delivery.{module}")
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


def test_property_commercial_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("commercial", ['customer_carbon_limit', 'customer_projects', 'open_tenders', 'tender_profile', 'win_rate'])


def test_property_comparables_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("comparables", ['comparable_coverage', 'comparable_set', 'profile_rules', 'variants_table'])


def test_property_contracts_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("contracts", ['clauses_on', 'contracts_for_project', 'framework_for', 'legal_flags', 'notification_clauses_on', 'notification_hours_by_customer', 'obligation_status', 'price_adjustment_terms'])


def test_property_estimating_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("estimating", ['cause_shares', 'contingency_advice', 'estimate_amount_per_metre', 'estimate_bridge', 'overrun_distribution', 'risk_lessons_summary'])


def test_property_history_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("history", ['attendance', 'decisions', 'executive_attendance', 'executive_gap', 'experience_network', 'first_record', 'minutes_refs', 'roster', 'timeline'])


def test_property_pricing_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("pricing", ['price_gaps', 'price_list_on'])


def test_property_projects_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("projects", ['active_on', 'project_frame', 'project_status_on'])


def test_property_schedule_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("schedule", ['activity_plan_vs_actual', 'delay_days', 'milestone_slippage', 'plan_slip', 'schedule_overrun'])


def test_property_supply_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("supply", ['at_risk_items', 'blocked_projects', 'elements_per_spare_unit', 'exposed_demand', 'supply_strain_answer', 'lead_time_alerts', 'lead_time_on', 'minimum_stock', 'open_po_lines', 'reserved_demand', 'spot_orders', 'stock_on', 'supplier_performance_recompute', 'supplier_performance_window'])


def test_property_views_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("views", ['attendance_view', 'cause_bars_view', 'experience_network_view', 'gantt_view', 'performance_view', 'stock_view', 'timeline_view', 'waterfall_view'])


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
