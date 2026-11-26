"""Property tests of halvaro-grid (standard 3.2.3; lane P3, #482): two rules that every function must keep, checked on the calls of its docstring examples.

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

import halvaro.grid as lib


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
        mod = importlib.import_module(f"halvaro.grid.{module}")
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


def test_property_alarms_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("alarms", ['alarm_rules_table', 'alarm_summary', 'alarm_ticket_link', 'incident_groups', 'recompute_alarms'])


def test_property_assets_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("assets", ['condition_trend', 'element_peak_load', 'strained_elements', 'zone_strain_summary'])


def test_property_callouts_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("callouts", ['callout_summary', 'on_call', 'requires_authorisation', 'sla_attainment'])


def test_property_capacity_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("capacity", ['cold_snaps', 'hours_above', 'load_duration_curve', 'peak_load', 'rank_zones', 'recompute_design_capacity', 'winter_label', 'zone_design_capacity', 'zone_load_percent'])


def test_property_faults_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("faults", ['fault_causes', 'fault_rate', 'repeat_faults'])


def test_property_geometry_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("geometry", ['condition_class_from_score', 'element_age', 'geometry_as_of', 'parse_geom', 'route_change', 'validate_versions'])


def test_property_maintenance_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("maintenance", ['due_within', 'inspection_interval_check', 'overdue_plans', 'planned_backlog'])


def test_property_parts_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("parts", ['critical_spares_issued', 'part_usage'])


def test_property_quality_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("quality", ['classify_flags', 'completeness', 'daily_from_raw', 'gap_report', 'sensor_quality_board', 'valid_samples'])


def test_property_recipes_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("recipes", ['grid_strain_answer', 'winter_peak_answer', 'route_facts'])


def test_property_series_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("series", ['bucket_peak', 'interval_hours', 'outdoor_at', 'to_local'])


def test_property_spatial_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("spatial", ['age_group_clusters', 'fault_clusters', 'fault_density', 'majority_soil', 'route_conditions_summary', 'route_ground_intersection'])


def test_property_topology_inputs_are_unchanged_and_a_second_call_gives_the_same_result():
    _check("topology", ['build_tree', 'trace'])


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
