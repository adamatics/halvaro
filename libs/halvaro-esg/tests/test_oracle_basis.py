"""Oracle tests of halvaro.esg.basis: provenance, size_evidence.

provenance is checked as a property of the join (union, order, repetition, status table); size_evidence against the thresholds read as facts and against the baseline statutory reports read directly.
"""
import dataclasses
import datetime as dt
import itertools

import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, Envelope, FrameError, fact, make_envelope

M12 = Context(stage="month12", role="r")


def _prov(value, *, status, synthetic=True, sets=(), notes=(), sources=(), warnings=(), facts=(), as_of=None):
    env = make_envelope(value, "halvaro.esg.factors.factor_on", sources=sources, as_of=as_of, warnings=warnings, cls=esg.Provenance, factor_sets=sets, verify_facts=notes)
    return dataclasses.replace(env, status=status, synthetic=synthetic, facts_used=tuple(facts))


def _plain(*, status="ok", synthetic=False, sources=(), warnings=(), as_of=None):
    return dataclasses.replace(make_envelope(0, None, sources=sources, as_of=as_of, warnings=warnings), status=status, synthetic=synthetic)


def _joined(p):
    return (p.factor_sets, p.verify_facts, p.status, p.synthetic, p.as_of, frozenset(p.sources), frozenset(p.warnings), frozenset(p.facts_used))


def _three():
    a = _prov(1, status="VERIFY", sets=("FS-H", "FS-B", "FS-D", "FS-A"), notes=("v9", "v2", "v1", "v7"), sources=("energy-esg.emission_factor", "energy-esg.emission_line"), warnings=("w1",), facts=(("f1", 1, "VERIFY"),), as_of=dt.date(2025, 12, 31))
    b = _prov(2, status="synthetic", sets=("FS-A", "FS-C", "FS-G", "FS-F", "FS-E"), notes=("v1", "v3", "v8", "v5", "v4", "v6"), sources=("energy-esg.emission_line", "energy-esg.target"), warnings=("w1", "w2"),
              facts=(("f1", 1, "VERIFY"), ("f2", 2, "synthetic")), as_of=dt.date(2026, 1, 31))
    c = _plain(sources=("projects.project",), warnings=("w3",))
    return a, b, c


# ---- provenance


def test_oracle_provenance_union_is_sorted_unique_and_order_free():
    """route: hand built results with overlapping sets and notes; the union written out, then every order of the inputs and every repetition compared with it."""
    a, b, c = _three()
    keep = [dataclasses.replace(x) for x in (a, b, c)]
    p = esg.provenance(a, b, c)
    assert isinstance(p, esg.Provenance) and isinstance(p, Envelope) and p.function == "halvaro.esg.basis.provenance"
    assert p.factor_sets == tuple(f"FS-{c}" for c in "ABCDEFGH") and p.verify_facts == tuple(f"v{i}" for i in range(1, 10))
    assert set(p.sources) == {"energy-esg.emission_factor", "energy-esg.emission_line", "energy-esg.target", "projects.project"} and len(p.sources) == 4
    assert set(p.warnings) == {"w1", "w2", "w3"} and len(p.warnings) == 3
    assert set(p.facts_used) == {("f1", 1, "VERIFY"), ("f2", 2, "synthetic")} and len(p.facts_used) == 2
    assert p.value == 3 and p.as_of == dt.date(2026, 1, 31) and p.synthetic is True and p.status == "VERIFY+synthetic"
    for perm in itertools.permutations([a, b, c]):
        assert _joined(esg.provenance(*perm)) == _joined(p)
    assert _joined(esg.provenance(a, a, b, b, c, c, a)) == _joined(p), "a result given twice adds nothing"
    assert esg.provenance(a, a, b, b, c, c, a).value == 7, "the value is the number of results given"
    assert _joined(esg.provenance(p, a, b, c)) == _joined(p), "combining a combined result with its parts again changes nothing"
    assert _joined(esg.provenance(esg.provenance(a, b), c)) == _joined(p)
    assert _joined(esg.provenance(p)) == _joined(p) and esg.provenance(p).value == 1
    assert [a, b, c] == keep, "the inputs are not changed"


STATUS_CASES = [
    (("ok",), (False,), "ok", False),
    (("ok", "ok"), (False, False), "ok", False),
    (("synthetic",), (True,), "synthetic", True),
    (("VERIFY",), (False,), "VERIFY", False),
    (("VERIFY",), (True,), "VERIFY", True),
    (("VERIFY+synthetic",), (True,), "VERIFY+synthetic", True),
    (("ok", "synthetic"), (False, True), "synthetic", True),
    (("ok", "VERIFY"), (False, False), "VERIFY", False),
    (("VERIFY", "synthetic"), (False, True), "VERIFY+synthetic", True),
    (("VERIFY", "VERIFY+synthetic", "ok"), (False, False, False), "VERIFY+synthetic", False),
    (("synthetic", "synthetic"), (True, True), "synthetic", True),
]


def _check_status_case(statuses, flags, expected, synthetic):
    results = [_plain(status=s, synthetic=f) for s, f in zip(statuses, flags)]
    p = esg.provenance(*results)
    assert p.status == expected and p.synthetic is synthetic, (statuses, flags)
    assert p.status != "verified"
    assert esg.provenance(*reversed(results)).status == expected


@pytest.mark.parametrize("statuses, flags, expected, synthetic", STATUS_CASES)
def test_oracle_provenance_status_and_synthetic_follow_the_inputs(statuses, flags, expected, synthetic):
    """route: hand table of input statuses and flags; VERIFY and synthetic each survive a join, ok joins with anything, and the status is never 'verified'."""
    _check_status_case(statuses, flags, expected, synthetic)


def test_oracle_provenance_as_of_is_the_latest_given_and_null_without_any():
    """route: hand results with dates; the latest day wins, results without a day are skipped, no day at all stays null."""
    d1, d2 = dt.date(2025, 3, 1), dt.date(2025, 9, 30)
    assert esg.provenance(_plain(as_of=d1), _plain(as_of=d2), _plain()).as_of == d2
    assert esg.provenance(_plain(as_of=d2), _plain(as_of=d1)).as_of == d2
    assert esg.provenance(_plain(), _plain()).as_of is None
    assert esg.provenance(_plain(as_of=d1)).as_of == d1


def test_oracle_provenance_refuses_nothing_and_non_results():
    """route: hand inputs the join cannot work with, and the error it must raise."""
    with pytest.raises(FrameError, match="at least one"):
        esg.provenance()
    for bad in (1, "result", None, pd.DataFrame(), {"value": 1}):
        with pytest.raises(FrameError, match="Envelope or Provenance"):
            esg.provenance(_plain(), bad)


def test_oracle_provenance_every_route():
    """route: the union, order, repetition, status table, latest day and refusal checks of the provenance tests above, run together."""
    test_oracle_provenance_union_is_sorted_unique_and_order_free()
    for case in STATUS_CASES:
        _check_status_case(*case)
    test_oracle_provenance_as_of_is_the_latest_given_and_null_without_any()
    test_oracle_provenance_refuses_nothing_and_non_results()


# ---- size_evidence

COUNTRY = {"LE-01": "DK", "LE-02": "DE"}
SR_COLS = ["le_key", "scope", "fiscal_year", "average_employees", "revenue", "reporting_class"]


def _thresholds():
    ids = {"DK": ("frep.annual_reports.DK.size_thresholds.average_full_time_employees", "frep.annual_reports.DK.size_thresholds.net_revenue"),
           "DE": ("frep.annual_reports.DE.size_thresholds.average_employees", "frep.annual_reports.DE.size_thresholds.net_revenue")}
    return {c: (fact(e), fact(r)) for c, (e, r) in ids.items()}


def _expected_flag(value, threshold):
    return pd.NA if pd.isna(value) else bool(value > threshold)


def test_oracle_size_evidence_hand_example_at_and_around_the_thresholds():
    """route: hand rows placed on, one above and one below each threshold, the thresholds read as facts, and each comparison written out with a plain python greater-than."""
    th = _thresholds()
    te = {c: float(v[0].value) for c, v in th.items()}
    tr = {c: float(v[1].value) for c, v in th.items()}
    mid = (tr["DK"] + tr["DE"]) / 2
    rows = [("LE-01", "entity", 2020, te["DK"], tr["DK"], "x1"), ("LE-01", "entity", 2021, te["DK"] + 1, tr["DK"] + 1, "x2"), ("LE-01", "entity", 2022, te["DK"] - 1, None, "x3"),
            ("LE-02", "entity", 2020, te["DE"] + 0.5, mid, "y1"), ("LE-02", "entity", 2021, None, tr["DE"] - 1, "y2"), ("LE-02", "entity", 2022, te["DE"], tr["DE"], "y3"),
            (None, "group", 2020, 10 * te["DK"], 10 * tr["DK"], "g")]
    SR = pd.DataFrame(rows, columns=SR_COLS)
    before = SR.copy(deep=True)
    r = esg.size_evidence(SR.iloc[::-1], context=M12)
    pd.testing.assert_frame_equal(SR, before)
    msg = "thresholds read: " + ", ".join(f"{f.id}={f.value}" for pair in th.values() for f in pair)
    v = r.value
    assert list(v.columns) == ["le_key", "fiscal_year", "country", "average_employees", "threshold_employees", "exceeds_employees", "revenue", "threshold_revenue", "exceeds_revenue", "reporting_class"]
    assert list(zip(v.le_key, v.fiscal_year)) == [("LE-01", 2020), ("LE-01", 2021), ("LE-01", 2022), ("LE-02", 2020), ("LE-02", 2021), ("LE-02", 2022)], "entity rows only, sorted"
    for row, src in zip(v.itertuples(), SR[SR.scope == "entity"].sort_values(["le_key", "fiscal_year"]).itertuples()):
        c = COUNTRY[src.le_key]
        assert row.country == c and row.threshold_employees == te[c] and row.threshold_revenue == tr[c], msg
        assert row.reporting_class == src.reporting_class
        for got, value, thr in ((row.exceeds_employees, src.average_employees, te[c]), (row.exceeds_revenue, src.revenue, tr[c])):
            want = _expected_flag(value, thr)
            assert (pd.isna(got) and want is pd.NA) or (got == want and not pd.isna(want)), (src.le_key, src.fiscal_year, value, thr, msg)
    flags = v.set_index(["le_key", "fiscal_year"])
    assert flags.loc[("LE-01", 2020), ["exceeds_employees", "exceeds_revenue"]].tolist() == [False, False], "a value equal to the threshold does not exceed it"
    assert flags.loc[("LE-01", 2021), ["exceeds_employees", "exceeds_revenue"]].tolist() == [True, True]
    assert pd.isna(flags.loc[("LE-01", 2022), "exceeds_revenue"]) and flags.loc[("LE-01", 2022), "exceeds_employees"] == False  # noqa: E712
    assert pd.isna(flags.loc[("LE-02", 2021), "exceeds_employees"]) and flags.loc[("LE-02", 2021), "exceeds_revenue"] == False  # noqa: E712
    assert flags.loc[("LE-02", 2020), "exceeds_revenue"] == (mid > tr["DE"]) and flags.loc[("LE-01", 2020), "exceeds_revenue"] == (tr["DK"] > tr["DK"])
    used = {t[0]: t for t in r.facts_used}
    assert set(used) == {f.id for pair in th.values() for f in pair} and len(r.facts_used) == 4
    assert all(used[f.id] == (f.id, f.value, f.status) for pair in th.values() for f in pair), msg
    assert r.status == ("VERIFY" if any(f.status == "VERIFY" for pair in th.values() for f in pair) else "ok"), msg
    assert r.synthetic is True and r.sources == ("finance-reporting.statutory_report",)
    assert not any(k in c for c in v.columns for k in ("duty", "applies", "required")), "evidence only"


def test_oracle_size_evidence_country_map_decides_which_thresholds_apply():
    """route: hand rows with the country map given by keyword; swapping the two countries swaps the thresholds the rows are compared with."""
    th = _thresholds()
    te = {c: float(v[0].value) for c, v in th.items()}
    tr = {c: float(v[1].value) for c, v in th.items()}
    SR = pd.DataFrame([("LE-01", "entity", 2024, te["DK"] + 0.5, (tr["DK"] + tr["DE"]) / 2, "a"), ("LE-02", "entity", 2024, te["DE"] + 0.5, (tr["DK"] + tr["DE"]) / 2, "b")], columns=SR_COLS)
    swapped = esg.size_evidence(SR, country_of={"LE-01": "DE", "LE-02": "DK"}, context=M12).value.set_index("le_key")
    plain = esg.size_evidence(SR, context=M12).value.set_index("le_key")
    for key, own, other in (("LE-01", "DK", "DE"), ("LE-02", "DE", "DK")):
        assert plain.loc[key, "country"] == own and swapped.loc[key, "country"] == other
        assert plain.loc[key, "threshold_revenue"] == tr[own] and swapped.loc[key, "threshold_revenue"] == tr[other]
        assert plain.loc[key, "threshold_employees"] == te[own] and swapped.loc[key, "threshold_employees"] == te[other]
        assert bool(swapped.loc[key, "exceeds_revenue"]) == (SR.revenue.iloc[0] > tr[other]) and bool(plain.loc[key, "exceeds_revenue"]) == (SR.revenue.iloc[0] > tr[own])
    no_scope = esg.size_evidence(SR.drop(columns="scope"), context=M12).value
    assert len(no_scope) == 2, "without a scope column every row is an entity row"
    with pytest.raises(FrameError, match="no country"):
        esg.size_evidence(SR, country_of={"LE-01": "DK"}, context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        esg.size_evidence(pd.concat([SR, SR.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="no entity rows"):
        esg.size_evidence(SR.assign(scope="group"), context=M12)


def test_oracle_size_evidence_every_route():
    """route: the hand examples and the country map checks above. The release step (the baseline reports) is a separate test that needs the closed repository."""
    test_oracle_size_evidence_hand_example_at_and_around_the_thresholds()
    test_oracle_size_evidence_country_map_decides_which_thresholds_apply()
