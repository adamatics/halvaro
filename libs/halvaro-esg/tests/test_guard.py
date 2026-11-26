"""The stage guard: refusal above the stage, context required, registration with the core registry."""
import pandas as pd
import pytest

from halvaro.core import Context, FrameError, StageRefusal, registry
from halvaro.esg._guard import staged

DAY1, MONTH3, MONTH12 = (Context(stage=s, role="r") for s in ("day1", "month3", "month12"))


@pytest.fixture
def guarded():
    ids = []

    def make(sources, name="probe", **meta):
        calls = []

        @staged(sources=sources, id=f"halvaro.esg.testguard.{name}", **meta)
        def probe(frame, flag=False, *, extra=1):
            """Summary of the probe."""
            calls.append((len(frame), flag, extra))
            return len(frame) + extra

        ids.append(f"halvaro.esg.testguard.{name}")
        probe.calls = calls
        return probe

    yield make
    for i in ids:
        registry._REGISTRY.pop(i, None)


def test_day1_is_refused_for_energy_esg_and_the_function_never_runs(guarded):
    fn = guarded(("energy-esg.emission_factor",))
    with pytest.raises(StageRefusal) as e:
        fn(pd.DataFrame({"a": [1]}), context=DAY1)
    assert "energy-esg" in str(e.value) and "month12" in str(e.value) and fn.calls == []


def test_month3_is_refused_for_a_month12_source_and_month12_runs(guarded):
    fn = guarded(("energy-esg.emission_factor",))
    with pytest.raises(StageRefusal):
        fn(pd.DataFrame({"a": [1]}), context=MONTH3)
    assert fn(pd.DataFrame({"a": [1, 2]}), True, extra=5, context=MONTH12) == 7 and fn.calls == [(2, True, 5)]


def test_a_day1_source_runs_at_day1_and_the_highest_source_decides(guarded):
    low, mixed = guarded(("hr.employee",), "low"), guarded(("hr.employee", "energy-esg.emission_factor"), "mixed")
    assert low(pd.DataFrame({"a": [1]}), context=DAY1) == 2
    with pytest.raises(StageRefusal, match="energy-esg"):
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


def test_a_second_registration_of_the_same_id_is_refused(guarded):
    guarded(("hr.employee",))
    with pytest.raises(ValueError, match="twice"):
        guarded(("hr.employee",))


@pytest.mark.parametrize("bad", ["energy-esg.emission_factor", (), [], None, ("energy-esg.emission_factor", ""), ("energy-esg.emission_factor", 3)])
def test_sources_must_be_a_non_empty_tuple_of_names(bad):
    with pytest.raises(TypeError, match="non-empty tuple"):
        staged(sources=bad)


def test_the_refusal_names_the_function_and_the_signature_shows_context(guarded):
    import inspect

    fn = guarded(("energy-esg.emission_factor",), "named")
    with pytest.raises(StageRefusal, match="halvaro.esg.testguard.named"):
        fn(pd.DataFrame({"a": [1]}), context=DAY1)
    params = inspect.signature(fn).parameters
    assert list(params) == ["frame", "flag", "extra", "context"] and params["context"].kind is inspect.Parameter.KEYWORD_ONLY and params["context"].default is params["context"].empty
