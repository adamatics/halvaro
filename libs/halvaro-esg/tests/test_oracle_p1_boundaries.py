"""Boundary cases that the oracles of lane L2 left open (lane P1, third round of P1.5): a mutation that refuses a bought quantity of exactly zero was not caught. No release needed."""
import pytest

import halvaro.esg as esg
from halvaro.core import FrameError
import pandas as pd

from test_oracle_levers import EPD, ITEMS, M12, SHARE


def test_lever_material_substitution_oracle_a_bought_quantity_of_zero_is_valid_and_saves_zero():
    """halvaro.esg.levers.lever_material_substitution: a quantity of exactly zero is allowed ("zero or more") and saves 0.0; a negative, a missing and an infinite quantity raise FrameError. By hand: 0 x (100 - 60) x 0.25 = 0."""
    G = pd.DataFrame({"itm_key": ["I-A", "I-B"], "quantity": [0.0, 10.0]})
    v = esg.lever_material_substitution(G, ITEMS, EPD, {"I-A": "I-B", "I-B": "I-C"}, SHARE, context=M12).value.set_index("itm_key")
    assert v.loc["I-A", "quantity"] == 0.0 and v.loc["I-A", "saved_kgco2e"] == 0.0 and not bool(v.loc["I-A", "worse"])
    assert v.loc["I-B", "saved_kgco2e"] == -150.0
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(FrameError, match="zero or more"):
            esg.lever_material_substitution(G.assign(quantity=[bad, 10.0]), ITEMS, EPD, {"I-A": "I-B", "I-B": "I-C"}, SHARE, context=M12)


def test_size_evidence_oracle_the_employee_threshold_of_the_country_is_used_when_the_two_facts_differ(monkeypatch):
    """halvaro.esg.basis.size_evidence: the Danish and the German employee thresholds are equal as facts today, so a mix up of the two is invisible; with the German one replaced by a stand in of 100, an entity
    with 150 employees is below the threshold in Denmark (the fact, 250 today) and above it in Germany (100), and the threshold in the row is the one of the country. By hand."""
    import dataclasses

    import halvaro.esg.basis as basis
    real = basis.fact
    de = "frep.annual_reports.DE.size_thresholds.average_employees"
    monkeypatch.setattr(basis, "fact", lambda fid: dataclasses.replace(real(fid), value=100) if fid == de else real(fid))
    SR = pd.DataFrame([("LE-01", "entity", 2024, 150.0, 1.0, "a"), ("LE-02", "entity", 2024, 150.0, 1.0, "b")],
                      columns=["le_key", "scope", "fiscal_year", "average_employees", "revenue", "reporting_class"])
    dk_value = float(real("frep.annual_reports.DK.size_thresholds.average_full_time_employees").value)
    assert dk_value > 150
    got = esg.size_evidence(SR, context=M12).value.set_index("le_key")
    assert got.loc["LE-01", ["country", "threshold_employees"]].tolist() == ["DK", dk_value] and not bool(got.loc["LE-01", "exceeds_employees"])
    assert got.loc["LE-02", ["country", "threshold_employees"]].tolist() == ["DE", 100.0] and bool(got.loc["LE-02", "exceeds_employees"])
    swapped = esg.size_evidence(SR, country_of={"LE-01": "DE", "LE-02": "DK"}, context=M12).value.set_index("le_key")
    assert swapped.loc["LE-01", "threshold_employees"] == 100.0 and bool(swapped.loc["LE-01", "exceeds_employees"]) and swapped.loc["LE-02", "threshold_employees"] == dk_value
