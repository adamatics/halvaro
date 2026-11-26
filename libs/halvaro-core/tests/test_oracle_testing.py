"""Oracles of halvaro.core.testing (lane L1). The helpers are checked with small hand built functions, loaders and frames whose outcome is known: a correct one passes, and each defect of a loader gives exactly one problem. No release needed. The restricted column appears by name only, its frames hold the placeholder 1.0."""
import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import testing as T

ORDER = ["day1", "month3", "month12"]


def _fake_registry(monkeypatch, sources):
    monkeypatch.setattr(T, "registered", lambda: {"x.needs": SimpleNamespace(sources=tuple(sources))})


def _call_requiring(sources):
    """A function that does what a correct library function does: it refuses at a stage that does not see its sources."""
    def call(frames, ctx):
        core.require_sources(ctx, sources)
        return pd.DataFrame({"n": [len(frames)]})
    return call


def test_stage_matrix_oracle_a_correct_function_refuses_exactly_where_sources_are_missing(monkeypatch):
    """halvaro.core.testing.stage_matrix: a function over hr and finance gives a refusal at day1 and a result at month3 and month12, written out by hand; the call only sees the frames of the visible sources."""
    srcs = ["hr.team.team_key", "finance.customer_invoice.net_amount"]
    _fake_registry(monkeypatch, srcs)
    seen = {}
    inner = _call_requiring(srcs)

    def call(frames, ctx):
        seen[ctx.stage] = sorted(frames)
        return inner(frames, ctx)

    frames = {"hr.team": pd.DataFrame({"a": [1]}), "finance.customer_invoice": pd.DataFrame({"a": [1]}), "projects.project": pd.DataFrame({"a": [1]})}
    rows = T.stage_matrix("x.needs", frames, call)
    assert rows == [{"stage": "day1", "expected": "refusal", "outcome": "refusal", "ok": True}, {"stage": "month3", "expected": "result", "outcome": "result", "ok": True},
                    {"stage": "month12", "expected": "result", "outcome": "result", "ok": True}]
    assert seen == {"day1": ["hr.team"], "month3": ["finance.customer_invoice", "hr.team"], "month12": ["finance.customer_invoice", "hr.team", "projects.project"]}


def test_stage_matrix_oracle_a_function_that_ignores_the_stage_or_names_the_wrong_sources_is_found(monkeypatch):
    """halvaro.core.testing.stage_matrix: a function that never refuses fails at day1, one that refuses with the wrong source names fails there too, strict=False returns the rows with ok False,
    and a subset of stages is honoured; an id that is not registered raises HalvaroError."""
    _fake_registry(monkeypatch, ["hr.team.team_key", "finance.customer_invoice.net_amount"])
    frames = {"hr.team": pd.DataFrame({"a": [1]})}
    with pytest.raises(AssertionError, match="day1 expected refusal, got result"):
        T.stage_matrix("x.needs", frames, lambda f, c: None)
    rows = T.stage_matrix("x.needs", frames, lambda f, c: None, strict=False)
    assert [r["ok"] for r in rows] == [False, True, True]
    wrong = _call_requiring(["hr.team.team_key", "projects.project.prj_key"])

    def refuses_wrongly(f, c):
        if c.stage == "day1":
            wrong(f, c)
        return None
    assert [r["ok"] for r in T.stage_matrix("x.needs", frames, refuses_wrongly, strict=False)] == [False, True, True]
    assert [r["stage"] for r in T.stage_matrix("x.needs", frames, _call_requiring(["finance.t.c"]), stages=["month3", "month12"])] == ["month3", "month12"]
    with pytest.raises(core.HalvaroError, match="not a registered function"):
        T.stage_matrix("halvaro.core.nothing.here", frames, lambda f, c: None)


def test_stage_matrix_oracle_a_real_registered_function_over_one_source(monkeypatch):
    """halvaro.core.testing.stage_matrix: for the registered library function team_context, which reads only hr, every stage gives a result."""
    team = pd.DataFrame({"team_key": ["T1"], "dep_key": ["D1"], "cost_centre_key": ["C1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-01"]})
    site = pd.DataFrame({"site_key": ["SITE-01"], "country": ["DK"]})
    rows = T.stage_matrix("halvaro.core.org.team_context", {"hr.team": team, "hr.site": site}, lambda f, c: core.team_context(f["hr.team"], f["hr.site"]))
    assert [(r["stage"], r["expected"], r["ok"]) for r in rows] == [(s, "result", True) for s in ORDER]


def _result(rows):
    return pd.DataFrame(rows, columns=["k", "v", "w"])


def test_asof_stable_oracle_equal_changed_added_and_allowed_rows():
    """halvaro.core.testing.asof_stable: equal results pass whatever the row order (also with a null on both sides); a changed value, a row only in the later release or a row only in the baseline
    raises AssertionError naming the key; a key in allowed_keys is exempt; a result object with a .value is unwrapped."""
    base = _result([("A", 1.0, None), ("B", 2.0, "x"), ("C", 3.0, "y")])
    assert T.asof_stable(lambda f, d: f["t"], {"t": base}, {"t": base.iloc[::-1].reset_index(drop=True)}, dt.date(2026, 1, 1), key="k") is True
    changed = base.copy()
    changed.loc[1, "v"] = 2.5
    with pytest.raises(AssertionError, match="'B'"):
        T.asof_stable(lambda f, d: f["t"], {"t": base}, {"t": changed}, dt.date(2026, 1, 1), key="k")
    assert T.asof_stable(lambda f, d: f["t"], {"t": base}, {"t": changed}, dt.date(2026, 1, 1), key="k", allowed_keys=["B"]) is True
    added = pd.concat([base, _result([("D", 4.0, "z")])], ignore_index=True)
    with pytest.raises(AssertionError, match="'D'"):
        T.asof_stable(lambda f, d: f["t"], {"t": base}, {"t": added}, dt.date(2026, 1, 1), key="k")
    with pytest.raises(AssertionError, match="'D'"):
        T.asof_stable(lambda f, d: f["t"], {"t": added}, {"t": base}, dt.date(2026, 1, 1), key="k")
    null_changed = base.copy()
    null_changed.loc[0, "w"] = "now set"
    with pytest.raises(AssertionError, match="'A'"):
        T.asof_stable(lambda f, d: f["t"], {"t": base}, {"t": null_changed}, dt.date(2026, 1, 1), key="k")
    assert T.asof_stable(lambda f, d: SimpleNamespace(value=f["t"]), {"t": base}, {"t": base}, dt.date(2026, 1, 1), key="k") is True


def test_asof_stable_oracle_the_date_is_handed_to_the_call_and_many_changes_are_listed_briefly():
    """halvaro.core.testing.asof_stable: the call receives the as-of date and, first, the frames of the baseline, then those of the later release; more than ten differing keys are named up to ten and then '...'."""
    got = []
    base = pd.DataFrame({"k": [f"K{i:02d}" for i in range(14)], "v": range(14)})
    later = base.assign(v=base["v"] + 1)

    def call(frames, as_of):
        got.append((as_of, frames["t"]["v"].tolist()))
        return frames["t"]
    with pytest.raises(AssertionError) as e:
        T.asof_stable(call, {"t": base}, {"t": later}, dt.date(2026, 3, 4), key="k")
    assert got == [(dt.date(2026, 3, 4), list(range(14))), (dt.date(2026, 3, 4), list(range(1, 15)))]
    assert "K00" in str(e.value) and "K09" in str(e.value) and "K10" not in str(e.value) and str(e.value).endswith("...")


def test_stage_matrix_oracle_the_refusal_must_name_exactly_the_missing_sources(monkeypatch):
    """halvaro.core.testing.stage_matrix: with two sources missing at day1 a refusal that names both is ok, a refusal that names only one or one more is not ok."""
    _fake_registry(monkeypatch, ["projects.p.c", "crm.t.c"])
    frames = {"hr.team": pd.DataFrame({"a": [1]})}
    both = lambda f, c: core.require_sources(c, ["projects.p.c", "crm.t.c"])                      # noqa: E731
    one = lambda f, c: core.require_sources(c, ["projects.p.c"])                                  # noqa: E731
    three = lambda f, c: core.require_sources(c, ["projects.p.c", "crm.t.c", "telemetry.t.c"])    # noqa: E731
    assert [r["ok"] for r in T.stage_matrix("x.needs", frames, both, stages=["day1"], strict=False)] == [True]
    assert [r["ok"] for r in T.stage_matrix("x.needs", frames, one, stages=["day1"], strict=False)] == [False]
    assert [r["ok"] for r in T.stage_matrix("x.needs", frames, three, stages=["day1"], strict=False)] == [False]


def test_stage_matrix_oracle_an_error_that_is_not_a_stage_refusal_is_not_swallowed(monkeypatch):
    """halvaro.core.testing.stage_matrix: a call that fails with another error raises it as it is, and a call that refuses at a stage where nothing is missing is reported as not ok."""
    _fake_registry(monkeypatch, ["hr.team.team_key"])
    with pytest.raises(KeyError):
        T.stage_matrix("x.needs", {"hr.team": pd.DataFrame({"a": [1]})}, lambda f, c: {}["missing"])
    rows = T.stage_matrix("x.needs", {"hr.team": pd.DataFrame({"a": [1]})}, lambda f, c: core.require_sources(c, ["projects.p.c"]), stages=["month3"], strict=False)
    assert rows == [{"stage": "month3", "expected": "result", "outcome": "refusal", "ok": False}]


class _Loader:
    """A loader that follows the contract; the defect flags break one rule each."""

    def __init__(self, **defects):
        self.defects = defects
        self.frame = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"], "team_key": ["T1", "T1", "T2", "T2"],
                                   "valid_from": pd.to_datetime(["2026-01-01"] * 4)})
        self.restricted = "base_salary"

    def _base(self):
        f = self.frame.copy()
        if self.defects.get("leak"):
            f[self.restricted] = 1.0
        if self.defects.get("tz"):
            f["valid_from"] = f["valid_from"].dt.tz_localize("UTC")
        if self.defects.get("order"):
            f = f[["team_key", "emp_key", "valid_from"]]
        return f

    def load(self, source, table, columns=None, where=None):
        if self.defects.get("boom"):
            raise RuntimeError("database is down")
        f = self._base()
        if where and not self.defects.get("where"):
            (c, v), = where.items()
            f = f[f[c] != v] if self.defects.get("wrongrows") else f[f[c] == v]
        if columns and not self.defects.get("columns"):
            f = f[list(columns)]
        return f.reset_index(drop=True)

    def iter_chunks(self, source, table, columns=None, where=None):
        f = self._base()
        if self.defects.get("chunks"):
            f = f.iloc[:-1]
        if self.defects.get("nochunks"):
            return
        for i in range(0, len(f), 3):
            yield f.iloc[i:i + 3]


EXPECTED = {"hr.employment_term": ["emp_key", "team_key", "valid_from"]}


def test_loader_contract_oracle_a_correct_loader_has_no_problem():
    """halvaro.core.testing.loader_contract: a loader that follows every rule gives an empty list, also with a context that forbids restricted columns and a where filter."""
    ctx = core.Context(stage="day1", role="mcp_people")
    assert T.loader_contract(_Loader(), EXPECTED) == []
    assert T.loader_contract(_Loader(), EXPECTED, context=ctx, restricted_columns=["base_salary", "birth_date"], where={"hr.employment_term": ("team_key", "T1")}) == []


@pytest.mark.parametrize("defect, fragment", [("boom", "load failed: database is down"), ("order", "differ from"), ("tz", "must be UTC naive"), ("leak", "restricted columns present"),
                                              ("columns", "columns=['emp_key', 'team_key'] returned"), ("where", "where team_key='T1' not honoured"), ("chunks", "iter_chunks joined does not equal load"),
                                              ("nochunks", "iter_chunks joined does not equal load"), ("wrongrows", "where team_key='T1' not honoured")])
def test_loader_contract_oracle_each_defect_gives_exactly_one_problem_naming_the_table(defect, fragment):
    """halvaro.core.testing.loader_contract: a loader with one defect (load fails, columns out of order, tz aware timestamps, a restricted column leaked, `columns` ignored, `where` ignored, chunks
    that do not add up to the table, no chunks at all, a `where` that returns as many rows as it should but the wrong ones) gives exactly one problem, naming the table and the rule, and the same loader without the defect gives none."""
    ctx = core.Context(stage="day1", role="mcp_people")
    expected = dict(EXPECTED)
    if defect == "leak":                                    # the restricted column is in the loader's table; the contract lists it as an expected column so that only the restricted rule fires
        expected = {"hr.employment_term": EXPECTED["hr.employment_term"] + ["base_salary"]}
    kw = {"context": ctx, "restricted_columns": ["base_salary", "birth_date"], "where": {"hr.employment_term": ("team_key", "T1")}}
    found = T.loader_contract(_Loader(**{defect: True}), expected, **kw)
    assert len(found) == 1 and found[0].startswith("hr.employment_term") and fragment in found[0], (defect, found)
    assert T.loader_contract(_Loader(), EXPECTED, **kw) == []


def test_loader_contract_oracle_the_restricted_check_needs_a_context_that_forbids_the_columns():
    """halvaro.core.testing.loader_contract: restricted columns in the load are a problem only for a context without restricted access; a context with restricted access or no context gives none."""
    leaky = _Loader(leak=True)
    leak_columns = list(EXPECTED["hr.employment_term"]) + ["base_salary"]
    expected = {"hr.employment_term": leak_columns}
    assert T.loader_contract(leaky, expected, context=core.Context(stage="day1", role="mcp_people_hr", restricted_ok=True), restricted_columns=["base_salary"]) == []
    assert T.loader_contract(leaky, expected, restricted_columns=["base_salary"]) == []
    assert len(T.loader_contract(leaky, expected, context=core.Context(stage="day1", role="mcp_people"), restricted_columns=["base_salary"])) == 1
