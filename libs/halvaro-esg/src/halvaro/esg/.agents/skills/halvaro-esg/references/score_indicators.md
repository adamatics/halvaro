# score_indicators

Module `halvaro.esg.score`. Import: `from halvaro.esg import score_indicators`.

```python
score_indicators(v: pd.DataFrame, policy: Mapping[str, Any] | None = None, *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need each indicator value turned into a score from 0 to 100 and a band from A to D.

A glide indicator scores its value times 100 (achieved over required reduction), a share indicator its share times 100, both clipped to 0 to 100 (PROPOSED,
policy.esg.scoring_thresholds); a null value stays null and gets no band. Bands: A from policy.esg.scoring_band_a_min (80), B from band_b_min (60), C from band_c_min (40), else D. `policy` is a
mapping that replaces any of the policy keys (band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis, external_use); the rest come from the proposed facts.
Properties (tested): scores between 0 and 100, monotonic in the value, deterministic.

Args:
    v: The output of indicator_values (a Provenance or its frame) with the columns indicator, kind ('glide' or 'share') and value.
    policy: A mapping that replaces any of the policy keys band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis and external_use; None to take every key from the proposed policy facts.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic, the policy facts that were read) whose value is a frame with the columns indicator, kind, value, score (0 to 100, rounded to 2 decimals) and band (A, B, C, D, or null when the score is null), in the order of v.

Raises:
    FrameError: v lacks indicator, kind or value; an indicator is twice in v; a kind is not glide or share.
    FrameError: policy has a key that is not known; a band limit or missing_data_min_weight is not a number; the band limits do not satisfy 0 <= C < B < A <= 100; missing_data_min_weight is not above 0 and at most 1.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import score_indicators
    >>> ctx = Context(stage="month12", role="analyst")
    >>> v = pd.DataFrame({"indicator": ["scope1", "epd_coverage", "audit_currency"], "kind": ["glide", "share", "share"], "value": [1.4, 0.5, None]})
    >>> out = score_indicators(v, context=ctx).value
    >>> out[["indicator", "score", "band"]].values.tolist()
    [['scope1', 100.0, 'A'], ['epd_coverage', 50.0, 'C'], ['audit_currency', nan, None]]

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
