"""ESG score (plan 5.11, proposed): hand computed indicator values and scores, the properties of plan section 8 (bounds, monotonic, weights sum to 1, deterministic), the missing data rule and the baseline run."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, registry

M12 = Context(stage="month12", role="r")
LCOLS = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "prj_key", "quantity", "efac_key",
         "ref_type", "ref_key", "unit", "site_key", "subcategory"]


def _frames():
    T = pd.DataFrame({"target_no": [1, 2], "scope": ["1", "project_intensity"], "baseline_year": [2023, 2025], "target_year": [2030, 2028], "baseline_value": [1000.0, 90.0], "target_value": [500.0, 72.0]})
    rows = [("LE-01", f"2025-{m:02d}", 1, "mobile_combustion", m, None, "1", 80.0, False, None) for m in range(1, 13)]
    L = pd.DataFrame([r + (None, None, np.nan, None, None, None, None, None, None) for r in rows], columns=LCOLS).astype({"supersedes_line_no": "Int64"})
    M = pd.DataFrame({"mtr_key": ["M1", "M2"], "carrier": ["electricity", "electricity"], "unit": ["kWh", "kWh"], "site_key": ["S1", "S2"]})
    C = pd.DataFrame({"mtr_key": ["M1", "M2", "M1", "M2"], "period": ["2025-01", "2025-01", "2025-02", "2025-02"], "quantity": [100.0, 300.0, 100.0, 300.0], "unit": ["kWh"] * 4,
                      "contract_type": ["renewable_certified", "grid_mix", "renewable_certified", "grid_mix"]})
    E = pd.DataFrame({"itm_key": ["I1", "I2", "I3", "I4"], "valid_from": ["2023-01-01"] * 4, "valid_to": [None, None, "2025-12-31", None], "source": ["supplier EPD (synthetic)", "generic database value (synthetic)", "supplier EPD (synthetic)",
                      "supplier EPD (synthetic)"]})
    A = pd.DataFrame({"site_key": ["S1", "S2"], "year": [2024, 2020], "audit_date": ["2024-05-01", "2020-05-01"], "due_date": ["2024-05-01", "2020-05-01"], "status": ["completed", "completed"]})
    return T, L, C, M, E, A


def test_indicator_values_are_hand_computed_facts_without_judgement():
    T, L, C, M, E, A = _frames()
    v = esg.indicator_values(T, L, C, M, E, A, "2026-11-30", intensity_actual=82.0, context=M12).value.set_index("indicator")
    glide = round(1000 - 500 * 2 / 7, 3)                      # target_progress rounds the glide value to three decimals
    assert v.loc["scope1", "value"] == pytest.approx((1000 - 960) / (1000 - glide)) and v.loc["scope1", "actual"] == 960.0 and v.loc["scope1", "kind"] == "glide"
    assert np.isnan(v.loc["project_intensity", "value"]), "no required reduction in the baseline year: null with a note"
    assert "no required reduction" in v.loc["project_intensity", "note"]
    assert v.loc["renewable_electricity_share", "value"] == pytest.approx(0.25) and v.loc["renewable_electricity_share", "n"] == 2
    assert v.loc["epd_coverage", "value"] == pytest.approx(2 / 3), "I3 ended in 2025: three live items, two with a supplier EPD"
    assert v.loc["audit_currency", "value"] == pytest.approx(0.5), "S2 audited 2020 is overdue on a 4 year cycle"
    assert list(v.index) == list(esg.score.INDICATORS) and len(v) == 7
    assert np.isnan(v.loc["scope3", "value"]) and "no target" in v.loc["scope3", "note"]


def test_indicator_values_year_with_missing_months_and_missing_intensity_are_null_with_a_note():
    T, L, C, M, E, A = _frames()
    short = esg.indicator_values(T, L.iloc[:6], C, M, E, A, "2026-11-30", context=M12).value.set_index("indicator")
    assert np.isnan(short.loc["scope1", "value"]) and "6 months" in short.loc["scope1", "note"]
    noint = esg.indicator_values(T, L, C, M, E, A, "2026-11-30", context=M12).value.set_index("indicator")
    assert "per route metre" in noint.loc["project_intensity", "note"]
    for bad in ("x", 5):
        with pytest.raises(FrameError):
            esg.indicator_values(T, L, C, M, E, A, bad, context=M12)


def _v(values):
    return pd.DataFrame({"indicator": [f"i{k}" for k in range(len(values))], "kind": ["share"] * len(values), "value": values})


def test_scores_are_bounded_monotonic_banded_and_deterministic():
    vals = [-0.5, 0.0, 0.39, 0.4, 0.59, 0.6, 0.79, 0.8, 1.0, 1.7, np.nan]
    s = esg.score_indicators(_v(vals), context=M12).value
    assert s.score.dropna().between(0, 100).all()
    ok = s.dropna(subset=["score"]).sort_values("value")
    assert ok.score.is_monotonic_increasing, "monotonic in the value"
    assert dict(zip(ok.value, ok.band)) == {-0.5: "D", 0.0: "D", 0.39: "D", 0.4: "C", 0.59: "C", 0.6: "B", 0.79: "B", 0.8: "A", 1.0: "A", 1.7: "A"}
    assert s[s.value.isna()].band.isna().all() and s[s.value.isna()].score.isna().all()
    pd.testing.assert_frame_equal(s, esg.score_indicators(_v(vals), context=M12).value)


def test_the_proposed_policy_is_read_from_facts_and_can_be_replaced_and_is_checked():
    r = esg.score_indicators(_v([0.7]), context=M12)
    assert r.status == "VERIFY+synthetic" and {f[0] for f in r.facts_used} >= {"policy.esg.scoring_band_a_min", "policy.esg.scoring_band_b_min"} and all(f[2] in ("proposed", "verified") for f in r.facts_used)      # lane F3 (issue #543), approved edit: lane F2 accepted the policy facts (status verified)
    assert esg.score_indicators(_v([0.7]), {"band_a_min": 70, "band_b_min": 50, "band_c_min": 30}, context=M12).value.band.tolist() == ["A"]
    for bad in ({"band_a_min": 50, "band_b_min": 60}, {"missing_data_min_weight": 0}, {"nope": 1}, {"band_c_min": "x"}):
        with pytest.raises(FrameError):
            esg.score_indicators(_v([0.7]), bad, context=M12)
    with pytest.raises(FrameError, match="twice"):
        esg.score_indicators(pd.concat([_v([0.1]), _v([0.2])]), context=M12)
    with pytest.raises(FrameError, match="kind"):
        esg.score_indicators(_v([0.1]).assign(kind="odd"), context=M12)


def _scored(scores):
    return pd.DataFrame({"indicator": [f"i{k}" for k in range(len(scores))], "score": scores})


def test_scorecard_weights_missing_data_rule_label_and_status():
    c = esg.scorecard(_scored([100.0, 50.0, 0.0, 70.0]), as_of="2026-11-30", context=M12)
    assert c.score == 55.0 and c.band == "C" and c.missing == () and c.weight_present == pytest.approx(1.0) and c.indicators.weight.tolist() == [0.25] * 4
    assert "not for external use" in c.label and "CSRD" in c.label and c.status == "VERIFY+synthetic" and str(c.as_of.date()) == "2026-11-30" and "synthetic" in c.external_use
    w = esg.scorecard(_scored([100.0, 0.0]), as_of="2026-11-30", weights={"i0": 0.75, "i1": 0.25}, context=M12)
    assert w.score == 75.0 and w.band == "B"
    gap = esg.scorecard(_scored([100.0, 50.0, np.nan, 70.0]), as_of="2026-11-30", context=M12)
    assert gap.missing == ("i2",) and gap.weight_present == pytest.approx(0.75) and gap.score == pytest.approx(73.33) and gap.band == "B", "75 percent of the weight is present: a score, the rest listed"
    few = esg.scorecard(_scored([100.0, np.nan, np.nan, 70.0]), as_of="2026-11-30", context=M12)
    assert few.score is None and few.band is None and few.missing == ("i1", "i2") and few.weight_present == pytest.approx(0.5)
    assert esg.scorecard(_scored([100.0, np.nan]), {"missing_data_min_weight": 0.5}, as_of="2026-11-30", context=M12).score == 100.0
    for bad in ({"i0": 0.5, "i1": 0.4}, {"i0": 1.5, "i1": -0.5}, {"i0": 1.0}):
        with pytest.raises(FrameError):
            esg.scorecard(_scored([1.0, 2.0]), as_of="2026-11-30", weights=bad, context=M12)
    with pytest.raises(FrameError):
        esg.scorecard(_scored([1.0, 2.0]), as_of=None, context=M12)


def test_a_higher_value_never_lowers_the_overall_score():
    base = [0.2, 0.4, 0.6, 0.8]
    prev = -1.0
    for step in np.linspace(0.0, 0.3, 7):
        s = esg.score_indicators(_v([b + step for b in base]), context=M12).value
        c = esg.scorecard(s, as_of="2026-11-30", context=M12).score
        assert c >= prev
        prev = c


def test_registration_and_the_stage_of_the_score_functions():
    ids = {"indicator_values", "score_indicators", "scorecard"}
    reg = {k.split(".")[-1]: v for k, v in registry.registered().items() if k.startswith("halvaro.esg.score.")}
    assert set(reg) == ids
    assert all("policy.esg.scoring_band_a_min" in m.facts for k, m in reg.items() if k != "indicator_values")
    stages = {r["id"].split(".")[-1]: r["stage"] for r in registry.export_index(library="halvaro-esg") if r["id"].startswith("halvaro.esg.score.")}
    assert set(stages) == ids and all(stages.values()), "the stage is derived from the sources"
    assert registry.check() == []
