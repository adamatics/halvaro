"""C1: facts and status."""
import datetime as dt

import pytest

import halvaro.core as core
from halvaro.core import snapshot


def test_fact_values_and_status():
    a = core.fact("legal.DK.holiday.annual_days")
    assert (a.value, a.status) == (25, "VERIFY") and a.file.endswith("legal-parameters.provisional.yaml")
    fx = core.fact("world.fx_eur_dkk_fixed")
    assert (fx.value, fx.status) == (7.46, "verified")
    assert core.fact("world.now").value == dt.date(2026, 11, 30), "date facts come back as dates"
    assert core.fact("core.calendar.DE_reformationstag_from").status == "VERIFY"


def test_unknown_fact_is_a_key_error_with_a_suggestion():
    with pytest.raises(KeyError, match="annual_days"):
        core.fact("legal.DK.holiday.annual_day")
    with pytest.raises(core.FactNotFound):
        core.fact("nonsense")


def test_cfg_reads_a_path_of_a_fact_file():
    assert core.cfg("config/world.yaml", "fx_eur_dkk_fixed") == core.fact("world.fx_eur_dkk_fixed")
    with pytest.raises(core.FactNotFound, match="not a fact file"):
        core.cfg("config/nope.yaml", "x")


def test_combine_status():
    c = core.combine_status
    assert c([]) == "ok" and c(["verified", "verified"]) == "ok" and c(["verified", "VERIFY"]) == "VERIFY"
    assert c(["synthetic", "verified"]) == "synthetic" and c(["VERIFY", "synthetic"]) == "VERIFY+synthetic"


def test_every_fact_of_the_snapshot_resolves():
    facts = snapshot.load()["facts"]
    assert len(facts) > 400
    assert all(core.fact(i).id == i for i in facts)
    assert {f["status"] for f in facts.values()} == {"verified", "VERIFY", "proposed"}


def test_authored_decision_with_a_status_is_one_fact_and_proposed_reads_as_verify():
    a = core.fact("policy.certificates.lookahead_days")
    assert (a.value, a.file) == (120, "corpus/facts.authored.yaml") and a.status in ("proposed", "verified")
    assert core.combine_status([a.status]) == ("VERIFY" if a.status == "proposed" else "ok") and core.combine_status(["verified", "proposed", "synthetic"]) == "VERIFY+synthetic"
    assert core.combine_status(["proposed"]) == "VERIFY", "a proposed fact reads as VERIFY, whatever the status of the fact above"
    with pytest.raises(core.FactNotFound):
        core.fact("policy.certificates.lookahead_days.value"), "the mapping is one leaf, not four facts"
    with pytest.raises(core.FactNotFound):
        core.fact("policy.certificates.lookahead_days.owner")
