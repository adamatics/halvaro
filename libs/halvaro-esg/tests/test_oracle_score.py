"""Oracles of indicator_values, score_indicators and scorecard (plan 5.11, scoring PROPOSED).

The reading tested: a glide indicator is the achieved reduction over the required reduction on a straight glide path (rounded to three decimals as the plan says), a share indicator is a share, a score is the value times 100
clipped to 0 to 100, a band is the highest band whose proposed minimum the score reaches, and the overall score is the weighted mean over the weight present when that weight reaches the proposed minimum.
The proposed limits are read through their fact ids (policy.esg.scoring_*); the tests state the value they used and do not claim the value is right.
"""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
KEYS = ("band_a_min", "band_b_min", "band_c_min", "missing_data_min_weight")


def _limits():
    v = {k: fact(f"policy.esg.scoring_{k}").value for k in KEYS}
    assert 0 <= v["band_c_min"] < v["band_b_min"] < v["band_a_min"] <= 100 and 0 < v["missing_data_min_weight"] <= 1, f"proposed limits read from the facts: {v}"
    return v


def _band(score, a, b, c):
    return None if score is None or np.isnan(score) else "A" if score >= a else "B" if score >= b else "C" if score >= c else "D"


def test_oracle_score_indicators_scores_and_bands_follow_the_proposed_limits():
    """route: python arithmetic on boundary values built from the limits read through the fact ids (limit minus a hundredth, the limit itself, above 100, below 0, null)."""
    L = _limits()
    a, b, c = L["band_a_min"], L["band_b_min"], L["band_c_min"]
    vals = [-0.5, 0.0, c / 100 - 0.0001, c / 100, b / 100 - 0.0001, b / 100, a / 100 - 0.0001, a / 100, 1.0, 1.7, np.nan]
    frame = pd.DataFrame({"indicator": [f"i{k}" for k in range(len(vals))], "kind": ["share"] * len(vals), "value": vals})
    before = frame.copy()
    r = esg.score_indicators(frame, context=M12)
    pd.testing.assert_frame_equal(frame, before)
    out = r.value
    for v, s, band in zip(vals, out["score"], out["band"]):
        want = None if np.isnan(v) else round(min(max(v * 100.0, 0.0), 100.0), 2)
        assert (np.isnan(s) if want is None else s == want), (v, s, want)
        assert (band is None or (isinstance(band, float) and np.isnan(band))) if want is None else band == _band(want, a, b, c), (v, s, band, L)
    assert r.status == "VERIFY+synthetic" and out["score"].dropna().between(0, 100).all()
    srt = out.dropna(subset=["score"]).sort_values("value")["score"]
    assert srt.is_monotonic_increasing, "property: a higher value never scores lower"
    pd.testing.assert_series_equal(out["score"], esg.score_indicators(frame, context=M12).value["score"])             # property: deterministic


def test_oracle_score_indicators_policy_override_replaces_the_facts():
    """route: hand reading with limits 90, 70, 50 given in the mapping: the facts are not consulted for those keys."""
    pol = {"band_a_min": 90, "band_b_min": 70, "band_c_min": 50, "missing_data_min_weight": 0.5, "basis": "x", "external_use": "y"}
    v = pd.DataFrame({"indicator": list("abcde"), "kind": ["glide"] * 5, "value": [0.9, 0.89, 0.7, 0.5, 0.49]})
    got = esg.score_indicators(v, pol, context=M12).value
    assert got["band"].tolist() == ["A", "B", "B", "C", "D"] and got["score"].tolist() == [90.0, 89.0, 70.0, 50.0, 49.0]
    with pytest.raises(FrameError, match="C < B < A"):
        esg.score_indicators(v, {**pol, "band_b_min": 95}, context=M12)
    with pytest.raises(FrameError, match="unknown policy keys"):
        esg.score_indicators(v, {"nope": 1}, context=M12)


def test_oracle_scorecard_is_the_weighted_mean_over_the_weight_present():
    """route: numpy dot product of scores and weights by hand, with the present weight set against the proposed minimum read from the fact."""
    L = _limits()
    m, a, b, c = L["missing_data_min_weight"], L["band_a_min"], L["band_b_min"], L["band_c_min"]
    n = 10
    scores = np.array([95.0, 85.0, 75.0, 65.0, 55.0, 45.0, 35.0, 25.0, 15.0, 5.0])
    names = [f"i{k}" for k in range(n)]

    def frame(k):
        s = scores.copy().astype(float)
        s[k:] = np.nan
        return pd.DataFrame({"indicator": names, "score": s})

    need = int(np.ceil(m * n - 1e-9))                           # the smallest number of equal weights that reaches the minimum
    ok = esg.scorecard(frame(need), as_of="2026-11-30", context=M12)
    assert ok.score == round(scores[:need].mean(), 2) and ok.band == _band(ok.score, a, b, c), f"minimum weight {m} (proposed)"
    assert ok.weight_present == pytest.approx(need / n) and ok.missing == tuple(names[need:])
    low = esg.scorecard(frame(need - 1), as_of="2026-11-30", context=M12)
    assert low.score is None and low.band is None and low.weight_present == pytest.approx((need - 1) / n), "below the minimum weight there is no score"
    w = {nm: x for nm, x in zip(names, [0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05])}
    wc = esg.scorecard(frame(10), as_of="2026-11-30", weights=w, context=M12)
    assert wc.score == round(float(np.dot(scores, list(w.values()))), 2) and wc.indicators["weight"].tolist() == list(w.values())
    assert wc.label.startswith("demo score") and wc.status == "VERIFY+synthetic" and wc.version == "v0 proposed" and wc.as_of == pd.Timestamp("2026-11-30")
    for bad in ({**w, "i0": 0.4}, {k: v for k, v in w.items() if k != "i9"}, {**w, "i0": -0.1, "i1": 0.5}):
        with pytest.raises(FrameError):
            esg.scorecard(frame(10), as_of="2026-11-30", weights=bad, context=M12)
