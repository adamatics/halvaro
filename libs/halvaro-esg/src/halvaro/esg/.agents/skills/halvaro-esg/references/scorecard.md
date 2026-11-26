# scorecard

Module `halvaro.esg.score`. Import: `from halvaro.esg import scorecard`.

```python
scorecard(s: pd.DataFrame, policy: Mapping[str, Any] | None = None, *, as_of: DateLike, weights: Mapping[str, Any] | None = None, version: str = 'v0 proposed', context: halvaro.core.access.Context) -> Scorecard
```

Use this when you need the weighted overall score and band of the scored indicators, with the missing data list and the demo label.

The weighted overall score, band, missing data list, version, as-of and the demo label. Indicators without a score are listed in `missing` and left out; the score is the weighted mean over the weight that is present, and is null (and so is the band) when the present
weight is below policy.esg.scoring_missing_data_min_weight (0.7). The `version` names the policy version (effective dated, change needs sign-off: policy.esg.scoring_governance, not coded).

Args:
    s: The output of score_indicators (a Provenance or its frame) with the columns indicator and score.
    policy: A mapping that replaces any of the policy keys band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis and external_use; None to take every key from the proposed policy facts.
    as_of: The day (date, Timestamp, ISO text or YYYY-MM) that is printed on the scorecard.
    weights: Mapping from each indicator to its weight (default equal: the proposed policy.esg.scoring_weights); it must name exactly the indicators of s, be non negative and sum to 1.
    version: The name of the policy version that is printed on the scorecard.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Scorecard with score (null when too little weight is present) and band, indicators (a frame with indicator, score, band and weight), missing (the indicators without a score), weight_present, version, as_of, basis (the policy text), external_use (the policy text), label (the demo label), status (VERIFY+synthetic) and facts_used.

Raises:
    FrameError: s lacks indicator or score; an indicator is twice in s; as_of is a number, not a date, or has a time zone.
    FrameError: policy has a key that is not known; a band limit or missing_data_min_weight is not a number; the band limits do not satisfy 0 <= C < B < A <= 100; missing_data_min_weight is not above 0 and at most 1.
    FrameError: weights does not name exactly the indicators of s, has a negative weight, or does not sum to 1.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import scorecard
    >>> ctx = Context(stage="month12", role="analyst")
    >>> s = pd.DataFrame({"indicator": ["scope1", "epd_coverage"], "score": [90.0, 50.0]})
    >>> card = scorecard(s, as_of="2032-02-01", weights={"scope1": 0.5, "epd_coverage": 0.5}, context=ctx)
    >>> card.score, card.band, card.missing, card.weight_present
    (70.0, 'B', (), 1.0)
    >>> s2 = pd.DataFrame({"indicator": ["scope1", "epd_coverage", "audit_currency"], "score": [90.0, 50.0, None]})
    >>> thin = scorecard(s2, as_of="2032-02-01", context=ctx)
    >>> thin.score, thin.band, thin.missing
    (None, None, ('audit_currency',))

## Source columns

- `energy-esg.target.baseline_value`
- `energy-esg.target.target_value`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `policy.esg.scoring_band_a_min`
- `policy.esg.scoring_band_b_min`
- `policy.esg.scoring_band_c_min`
- `policy.esg.scoring_missing_data_min_weight`
- `policy.esg.scoring_basis`
- `policy.esg.scoring_external_use`
