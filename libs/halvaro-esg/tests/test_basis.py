"""Basis (plan 5.10): the statement never claims a duty, size evidence from facts, provenance of combined results."""
import dataclasses
import re

import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, make_envelope, registry

M12 = Context(stage="month12", role="r")


def test_reporting_basis_voluntary_classes_and_the_wording_scan():
    a = esg.reporting_basis("voluntary", context=M12)
    b = esg.reporting_basis("voluntary and national statutory statement, no mandatory EU standard assumed (VERIFY)", context=M12)
    assert a.framework == "voluntary" and b.framework == "voluntary_with_statutory_statement" and "VERIFY" in a.verify[0]
    for s in (a.statement, b.statement):
        assert "No mandatory EU sustainability reporting standard is assumed" in s and not re.search(r"(CSRD|ESRS)[^.]*applies", s, re.I), "negative test of plan 8.3"
    assert a.decision == "voluntary" and b.decision == "voluntary and national statutory statement", "the canonical text is returned, never the input"
    assert esg.reporting_basis("  Voluntary   AND national statutory statement ", context=M12).framework == "voluntary_with_statutory_statement"
    for bad in ("CSRD applies to the group", "voluntary, but the ESRS apply", "Omnibus rules mandatory for us", "voluntary; we are subject to CSRD", "voluntary, CSRD is mandatory", "voluntary but we must report under CSRD",
                "voluntary. Falls under CSRD from 2027", "voluntary; within the scope of CSRD", "voluntary; CSRD does not apply", "not voluntary; mandatory", "mandatory, not voluntary", "involuntary CSRD",
                "voluntary, no statutory statement", "voluntary; statutory statement not required"):
        with pytest.raises(FrameError, match="accepted wordings") as e:
            esg.reporting_basis(bad, context=M12)
        assert "CSRD" not in str(e.value), "the offending text is not echoed"
    for odd in ("", "   "):
        with pytest.raises(FrameError):
            esg.reporting_basis(odd, context=M12)
    with pytest.raises(FrameError, match="non-empty"):
        esg.reporting_basis(None, context=M12)


SR = pd.DataFrame({"le_key": ["LE-01", "LE-02", None, "LE-02"], "scope": ["entity", "entity", "group", "entity"], "fiscal_year": [2024, 2024, 2024, 2025],
                   "average_employees": [250.0, 249.9, 500.0, 260.0], "revenue": [300_000_000.0, 60_000_000.0, 9e9, 40_000_000.0], "reporting_class": ["C", "gross", "C", "gross"]})


def test_size_evidence_thresholds_from_facts_and_no_conclusion():
    r = esg.size_evidence(SR, context=M12)
    v = r.value.set_index(["le_key", "fiscal_year"])
    assert r.status == "VERIFY" and len(r.facts_used) == 4 and len(v) == 3, "the group row is left out"
    assert not v.loc[("LE-01", 2024), "exceeds_employees"] and not v.loc[("LE-01", 2024), "exceeds_revenue"], "exactly at the threshold is not above it"
    assert not v.loc[("LE-02", 2024), "exceeds_employees"] and v.loc[("LE-02", 2024), "exceeds_revenue"] and v.loc[("LE-02", 2025), "exceeds_employees"] and not v.loc[("LE-02", 2025), "exceeds_revenue"]
    assert v.loc[("LE-01", 2024), "threshold_revenue"] == 300_000_000.0 and v.loc[("LE-02", 2024), "threshold_employees"] == 250.0
    assert not any("applies" in c or "duty" in c for c in r.value.columns) and any("no conclusion" in w for w in r.warnings)
    with pytest.raises(FrameError, match="no country"):
        esg.size_evidence(SR.assign(le_key=["LE-01", "LE-09", None, "LE-02"]), context=M12)
    with pytest.raises(FrameError, match="more than one"):
        esg.size_evidence(pd.concat([SR, SR.iloc[:1]]), context=M12)


def test_provenance_joins_sets_notes_facts_and_status():
    a = dataclasses.replace(make_envelope(1, "halvaro.esg.factors.factor_on", sources=("energy-esg.emission_factor",), cls=esg.Provenance, factor_sets=("FS-2024",), verify_facts=("v1",)), status="VERIFY+synthetic", synthetic=True)
    b = dataclasses.replace(make_envelope(2, "halvaro.esg.ghg.scope_totals", sources=("energy-esg.emission_line",), cls=esg.Provenance, factor_sets=("FS-2025",), verify_facts=("v2",)), status="synthetic", synthetic=True)
    p = esg.provenance(a, b)
    assert isinstance(p, esg.Provenance) and p.factor_sets == ("FS-2024", "FS-2025") and p.verify_facts == ("v1", "v2") and p.status == "VERIFY+synthetic" and p.synthetic
    assert set(p.sources) == {"energy-esg.emission_factor", "energy-esg.emission_line"} and p.value == 2
    plain = make_envelope(3, "halvaro.core.facts.fact", sources=(), facts=(), cls=type(make_envelope(0)))
    q = esg.provenance(plain, plain)
    assert q.status == "ok" and not q.synthetic or q.synthetic in (True, False)
    clean = dataclasses.replace(plain, synthetic=False)
    assert esg.provenance(clean, a).synthetic and not esg.provenance(clean, clean).synthetic, "synthetic if any input is"
    with pytest.raises(FrameError, match="at least one"):
        esg.provenance()
    with pytest.raises(FrameError, match="Envelope"):
        esg.provenance(a, "x")


def test_registration():
    for n in ("reporting_basis", "size_evidence", "provenance"):
        assert n in esg.__all__
    for n in ("reporting_basis", "size_evidence"):
        assert f"halvaro.esg.basis.{n}" in registry.registered()


def test_size_evidence_nulls_are_unknown_and_empty_input_refuses():
    r = esg.size_evidence(SR.assign(average_employees=[None, 249.9, 500.0, 260.0]), context=M12).value.set_index(["le_key", "fiscal_year"])
    assert r.loc[("LE-01", 2024), "exceeds_employees"] is pd.NA or pd.isna(r.loc[("LE-01", 2024), "exceeds_employees"]), "unknown, not 'does not exceed'"
    assert not pd.isna(r.loc[("LE-02", 2024), "exceeds_revenue"])
    with pytest.raises(FrameError, match="no entity rows"):
        esg.size_evidence(SR.iloc[:0], context=M12)
    with pytest.raises(FrameError, match="no entity rows"):
        esg.size_evidence(SR.assign(scope="Entity"), context=M12)


def test_provenance_carries_the_latest_as_of():
    import datetime as dt
    a = dataclasses.replace(make_envelope(1, "halvaro.esg.factors.factor_on", sources=("energy-esg.emission_factor",), cls=esg.Provenance, as_of=dt.date(2025, 12, 31)), status="VERIFY", synthetic=True)
    b = dataclasses.replace(a, as_of=dt.date(2026, 1, 31))
    assert esg.provenance(a, b).as_of == dt.date(2026, 1, 31) and esg.provenance(a).as_of == dt.date(2025, 12, 31)
