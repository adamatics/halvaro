"""The stage guard: refusal above the stage, context required, registration with the core registry."""
import pandas as pd
import pytest

from halvaro.core import Context, FrameError, StageRefusal, registry
from halvaro.delivery._guard import staged

DAY1, MONTH3, MONTH12 = (Context(stage=s, role="r") for s in ("day1", "month3", "month12"))


@pytest.fixture
def guarded():
    ids = []

    def make(sources, name="probe", **meta):
        calls = []

        @staged(sources=sources, id=f"halvaro.delivery.testguard.{name}", **meta)
        def probe(frame, flag=False, *, extra=1):
            """Summary of the probe."""
            calls.append((len(frame), flag, extra))
            return len(frame) + extra

        ids.append(f"halvaro.delivery.testguard.{name}")
        probe.calls = calls
        return probe

    yield make
    for i in ids:
        registry._REGISTRY.pop(i, None)


def test_day1_is_refused_for_projects_and_the_function_never_runs(guarded):
    fn = guarded(("projects.project",))
    with pytest.raises(StageRefusal) as e:
        fn(pd.DataFrame({"a": [1]}), context=DAY1)
    assert "projects" in str(e.value) and "month12" in str(e.value) and fn.calls == []


def test_month3_is_refused_for_a_month12_source_and_month12_runs(guarded):
    fn = guarded(("projects.project",))
    with pytest.raises(StageRefusal):
        fn(pd.DataFrame({"a": [1]}), context=MONTH3)
    assert fn(pd.DataFrame({"a": [1, 2]}), True, extra=5, context=MONTH12) == 7 and fn.calls == [(2, True, 5)]


def test_a_day1_source_runs_at_day1_and_the_highest_source_decides(guarded):
    low, mixed = guarded(("hr.employee",), "low"), guarded(("hr.employee", "projects.project"), "mixed")
    assert low(pd.DataFrame({"a": [1]}), context=DAY1) == 2
    with pytest.raises(StageRefusal, match="projects"):
        mixed(pd.DataFrame({"a": [1]}), context=DAY1)
    assert mixed(pd.DataFrame({"a": [1]}), context=MONTH12) == 2


def test_context_is_required_and_must_be_a_context(guarded):
    fn = guarded(("hr.employee",))
    with pytest.raises(TypeError):
        fn(pd.DataFrame({"a": [1]}))
    for bad in (None, "day1", {"stage": "day1"}):
        with pytest.raises(FrameError, match="Context"):
            fn(pd.DataFrame({"a": [1]}), context=bad)
    assert fn.calls == []


def test_the_wrapper_keeps_the_name_the_doc_and_the_registry_record(guarded):
    fn = guarded(("projects.project",), oracle="py:tests/x.py::y", tags=("T7",))
    meta = registry.registered()["halvaro.delivery.testguard.probe"]
    assert fn.__name__ == "probe" and fn.__doc__ == "Summary of the probe." and fn.__halvaro__ is meta
    assert meta.sources == ("projects.project",) and meta.oracle == "py:tests/x.py::y" and meta.tags == ("T7",)
    assert meta.parameters == ("frame", "flag", "extra", "context"), "context is listed, keyword-only arguments are not lost"
    rec = next(r for r in registry.export_index(library="halvaro-delivery") if r["id"] == meta.id)
    assert rec["library"] == "halvaro-delivery" and rec["version"] == "0.1.0"
    assert rec["stage"] == "month12" and rec["parameters"] == ["frame", "flag", "extra", "context"]


def test_a_second_registration_of_the_same_id_is_refused(guarded):
    guarded(("hr.employee",))
    with pytest.raises(ValueError, match="twice"):
        guarded(("hr.employee",))


def test_a_shared_decorator_does_not_leak_parameters_between_functions():
    deco = staged(sources=("hr.employee.emp_key",))
    ids = []
    try:
        @deco
        def shared_one(a, b):
            return a

        @deco
        def shared_two(c):
            return c

        ids = [shared_one.__halvaro__.id, shared_two.__halvaro__.id]
        reg = registry.registered()
        assert reg[ids[0]].parameters == ("a", "b", "context") and reg[ids[1]].parameters == ("c", "context")
    finally:
        for i in ids:
            registry._REGISTRY.pop(i, None)


def test_explicit_parameters_win_and_a_context_parameter_is_refused(guarded):
    fn = guarded(("hr.employee",), "explicit", parameters=("frame",))
    assert registry.registered()["halvaro.delivery.testguard.explicit"].parameters == ("frame",) and fn.__name__ == "probe"
    with pytest.raises(TypeError, match="parameter called context"):
        @staged(sources=("hr.employee",), id="halvaro.delivery.testguard.ctx")
        def bad(frame, context=None):
            return frame
    assert "halvaro.delivery.testguard.ctx" not in registry.registered()


def test_stacking_staged_is_refused():
    inner = staged(sources=("hr.employee",), id="halvaro.delivery.testguard.inner")(lambda frame: frame)
    try:
        with pytest.raises(TypeError, match="already registered"):
            staged(sources=("hr.employee",), id="halvaro.delivery.testguard.outer")(inner)
    finally:
        registry._REGISTRY.pop("halvaro.delivery.testguard.inner", None)


@pytest.mark.parametrize("bad", ["projects.project", (), [], None, ("projects.project", ""), ("projects.project", 3)])
def test_sources_must_be_a_non_empty_tuple_of_names(bad):
    with pytest.raises(TypeError, match="non-empty tuple"):
        staged(sources=bad)


def test_a_source_given_as_a_table_or_a_source_name_guards_the_same_way(guarded):
    for src in (("projects",), ("projects.project",), ("projects.project.start",)):
        with pytest.raises(StageRefusal):
            guarded(src, "t" + str(len(src[0])))(pd.DataFrame({"a": [1]}), context=DAY1)
        registry._REGISTRY.pop(f"halvaro.delivery.testguard.t{len(src[0])}", None)


def test_the_refusal_names_the_function_and_the_signature_shows_context(guarded):
    import inspect

    fn = guarded(("projects.project",), "named")
    with pytest.raises(StageRefusal, match="halvaro.delivery.testguard.named"):
        fn(pd.DataFrame({"a": [1]}), context=DAY1)
    params = inspect.signature(fn).parameters
    assert list(params) == ["frame", "flag", "extra", "context"] and params["context"].kind is inspect.Parameter.KEYWORD_ONLY and params["context"].default is params["context"].empty
