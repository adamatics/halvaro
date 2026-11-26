"""Stage guard of the hr functions that read a source above Day 1 (HF-05, decision of 2026-11-01): the function refuses itself, not only the MCP layer."""
from __future__ import annotations

import inspect

import pytest

import halvaro.hr as hr
from halvaro.core import Context, FrameError, StageRefusal, registry
from halvaro.core.access import stage_of_sources

DAY1 = Context.from_profile("mcp_people_hr", stage="day1")
MONTH12 = Context.from_profile("mcp_people_hr", stage="month12")


def _staged_functions():
    out = []
    for fid, meta in sorted(registry.registered().items()):
        if not fid.startswith("halvaro.hr.") or not meta.sources:
            continue
        stage = stage_of_sources(meta.sources)
        if stage and stage != "day1":
            out.append((fid.split(".")[-1], meta))
    return out


STAGED = _staged_functions()


def test_the_list_of_staged_hr_functions_is_complete():
    names = {n for n, _ in STAGED}
    assert len(names) >= 20
    assert {"with_education", "education_explained_share", "coverage_gap", "project_crew", "cover_candidates", "expiry_report", "valid_on", "utilisation", "experience_summary"} <= names


@pytest.mark.parametrize("name,meta", STAGED, ids=[n for n, _ in STAGED])
def test_day1_context_is_refused_before_the_function_runs(name, meta):
    fn = getattr(hr, name)
    arity = len([p for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
    with pytest.raises(StageRefusal) as e:
        fn(*([None] * arity), context=DAY1)
    missing = {s.split(".")[0] for s in meta.sources if s.split(".")[0] != "hr"}
    assert any(m in str(e.value) for m in missing), f"{name}: the refusal must name {missing}, got: {e.value}"
    assert name in str(e.value) or meta.id in str(e.value)


@pytest.mark.parametrize("name,meta", STAGED, ids=[n for n, _ in STAGED])
def test_month12_context_passes_the_guard(name, meta):
    fn = getattr(hr, name)
    arity = len([p for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
    try:
        fn(*([None] * arity), context=MONTH12)
    except StageRefusal:
        pytest.fail(f"{name} refused a month12 session")
    except Exception:
        pass   # the dummy arguments fail later and elsewhere: only the guard is under test


def test_context_stays_optional_and_must_be_a_context():
    assert "context" in inspect.signature(hr.coverage_gap).parameters and inspect.signature(hr.coverage_gap).parameters["context"].default is None
    with pytest.raises(FrameError, match="halvaro.core.Context"):
        hr.coverage_gap(None, None, None, None, None, None, context="day1")


def test_registered_parameters_are_those_of_the_function():
    # existing tests pin the registered parameters; the optional context is not added to them
    assert registry.registered()["halvaro.hr.crosswalk.resolve_assignments"].parameters == ("assignment", "index", "employee", "as_of", "asset_return_days")


def test_day1_sessions_still_use_the_day1_functions():
    for n in ("pay_frame", "gap_table", "headcount_on", "holiday_balance"):
        assert n not in {x for x, _ in STAGED}
