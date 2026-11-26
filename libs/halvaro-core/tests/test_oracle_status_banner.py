"""Property oracles of halvaro.core.facts.combine_status and halvaro.core.access.stage_banner (lane L1): a truth table written by hand and laws over all subsets and permutations."""
import inspect
import itertools

import pytest

import halvaro.core as core
from halvaro.core import errors, snapshot

VOCAB = ["verified", "VERIFY", "proposed", "synthetic"]            # the statuses a fact can carry


# The 16 subsets of the four statuses and their envelope, written out one by one. Read: VERIFY or proposed give VERIFY, synthetic is added, verified changes nothing.
TABLE = {
    (): "ok",
    ('verified',): "ok",
    ('VERIFY',): "VERIFY",
    ('proposed',): "VERIFY",
    ('synthetic',): "synthetic",
    ('verified', 'VERIFY'): "VERIFY",
    ('verified', 'proposed'): "VERIFY",
    ('verified', 'synthetic'): "synthetic",
    ('VERIFY', 'proposed'): "VERIFY",
    ('VERIFY', 'synthetic'): "VERIFY+synthetic",
    ('proposed', 'synthetic'): "VERIFY+synthetic",
    ('verified', 'VERIFY', 'proposed'): "VERIFY",
    ('verified', 'VERIFY', 'synthetic'): "VERIFY+synthetic",
    ('verified', 'proposed', 'synthetic'): "VERIFY+synthetic",
    ('VERIFY', 'proposed', 'synthetic'): "VERIFY+synthetic",
    ('verified', 'VERIFY', 'proposed', 'synthetic'): "VERIFY+synthetic",
}


def _want(statuses) -> str:
    return TABLE[tuple(s for s in VOCAB if s in set(statuses))]


def test_combine_status_oracle_every_subset_of_the_statuses_and_every_order():
    """halvaro.core.facts.combine_status: for all 16 subsets of the four statuses, all orders and duplicates, the envelope equals the table written out above; a generator works."""
    seen = set()
    for r in range(len(VOCAB) + 1):
        for subset in itertools.combinations(VOCAB, r):
            for perm in itertools.permutations(subset):
                assert core.combine_status(perm) == _want(subset), perm
                assert core.combine_status(list(perm) + list(perm)) == _want(subset), "duplicates change nothing"
                assert core.combine_status(x for x in perm) == _want(subset)
            seen.add(_want(subset))
    assert seen == {"ok", "synthetic", "VERIFY", "VERIFY+synthetic"}, "the table reaches all four results"
    assert core.combine_status([]) == "ok"
    assert [core.combine_status(["verified"]), core.combine_status(["proposed"]), core.combine_status(["VERIFY", "synthetic"])] == ["ok", "VERIFY", "VERIFY+synthetic"]


def test_combine_status_oracle_union_laws():
    """halvaro.core.facts.combine_status: combining two groups at once equals the flags of the two group results put together (VERIFY if either has it, synthetic if either has it)."""
    for a in itertools.chain.from_iterable(itertools.combinations(VOCAB, r) for r in range(5)):
        for b in itertools.chain.from_iterable(itertools.combinations(VOCAB, r) for r in range(5)):
            ra, rb, both = core.combine_status(a), core.combine_status(b), core.combine_status(a + b)
            assert ("VERIFY" in both) == ("VERIFY" in ra or "VERIFY" in rb) and ("synthetic" in both) == ("synthetic" in ra or "synthetic" in rb), (a, b)


def test_combine_status_oracle_every_fact_of_the_library_combines_to_what_the_files_say():
    """halvaro.core.facts.combine_status: the statuses of all facts of the snapshot give the envelope the table gives for the set of statuses present, so the library and the table agree on real data."""
    statuses = [core.fact(i).status for i in snapshot.load()["facts"]]
    assert set(statuses) <= set(VOCAB)
    assert core.combine_status(statuses) == _want(statuses)


def test_stage_banner_oracle_hand_worked_texts():
    """halvaro.core.access.stage_banner: the banner of a stage refusal names every missing source, the stage where it appears and the stage held; the banner of a restricted column names column, role
    and stage; both are one line."""
    stage = core.StageRefusal(["finance", "projects"], "month12", "day1")
    assert core.stage_banner(stage) == "Needs finance, projects (appears at stage month12). This session holds stage day1."
    restricted = core.RestrictedColumnRefusal("hr.employment_term.base_salary", "mcp_people", "day1")
    assert core.stage_banner(restricted) == "Restricted column hr.employment_term.base_salary: role mcp_people at stage day1 may not read it."
    assert "\n" not in core.stage_banner(stage) and "\n" not in core.stage_banner(restricted)


def _instances():
    """One instance of every error class of the library, built from the signature of its constructor."""
    out = []
    for name, cls in inspect.getmembers(errors, inspect.isclass):
        if not issubclass(cls, errors.HalvaroError):
            continue
        try:
            params = [p for p in inspect.signature(cls).parameters.values() if p.default is p.empty]
        except ValueError:                                                                   # no constructor of its own: the message is the only argument
            params = [inspect.Parameter("message", inspect.Parameter.POSITIONAL_ONLY)]
        args = {"missing_sources": ["a"], "stage_needed": "month3", "stage_held": "day1", "column": "x.y.z", "role": "r", "stage": "day1", "key": "K", "candidates": ["A", "B"], "side": "left", "keys": ["K"]}
        out.append((name, cls(*[args.get(p.name, "message text") for p in params])))
    return out


@pytest.mark.parametrize("name, error", _instances(), ids=lambda v: v if isinstance(v, str) else "")
def test_stage_banner_oracle_every_error_of_the_library_gives_one_non_empty_line_with_its_message(name, error):
    """halvaro.core.access.stage_banner: for every error class of halvaro.core.errors the banner is one non empty line, and for the classes other than the two refusals it carries the message of the error."""
    banner = core.stage_banner(error)
    assert isinstance(banner, str) and banner.strip() and "\n" not in banner, name
    if not isinstance(error, (core.StageRefusal, core.RestrictedColumnRefusal)):
        assert str(error) in banner, name


def test_the_error_classes_found_by_the_test_include_every_exported_error():
    """halvaro.core.access.stage_banner: the helper above sees every error class the package exports, so a new exported class cannot be left out of the banner test unnoticed."""
    names = {n for n, _ in _instances()}
    exported = {n for n in core.__all__ if isinstance(getattr(core, n), type) and issubclass(getattr(core, n), errors.HalvaroError)}
    assert {"StageRefusal", "RestrictedColumnRefusal", "FrameError", "PeriodError", "AggregateRefusal", "AmbiguousKey", "UnmatchedKeys"} <= names
    assert exported <= names and "FactNotFound" in exported
