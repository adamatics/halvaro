# intercompany_match

```python
intercompany_match(match: pd.DataFrame, *, tolerance_dkk: float = 1.0, eur_rate: float | None = None, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the intercompany pairs of the two legal entities recomputed and compared with what is stored.

Rule: difference_dkk is the amount booked by LE-01 less the amount booked by LE-02 in DKK. status is matched when the difference is within tolerance_dkk (PROPOSED 1.0, the group tolerance of the plan) and difference otherwise. fx_ok is true when the EUR amount of LE-02 at the fixed rate is within 0.011 of its DKK amount. agrees is true when the recomputed status and difference equal the stored ones.

## Args

match: Frame finance-reporting.intercompany_match with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, amount_le02_eur, difference_dkk and status, one row per ic_ref.
tolerance_dkk: Largest difference in DKK that still counts as matched (default 1.0, PROPOSED).
eur_rate: The EUR to DKK rate; without it the fixed rate of the fact world.fx_eur_dkk_fixed is used and listed in the envelope.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, difference_dkk, status, stored_status, fx_ok and agrees.

## Raises

FrameError: a column is missing, an ic_ref is empty or repeated, tolerance_dkk is negative or not a number, or eur_rate is not a positive number.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import intercompany_match
>>> ctx = Context(stage="month12", role="analyst")
>>> match = pd.DataFrame({"ic_ref": ["IC-1", "IC-2"], "kind": ["loan", "trade"], "period": ["2026-03"] * 2, "amount_le01_dkk": [1000.0, 500.0],
...                       "amount_le02_dkk": [1000.0, 498.0], "amount_le02_eur": [100.0, 49.8], "difference_dkk": [0.0, 2.0], "status": ["matched", "difference"]})
>>> result = intercompany_match(match, eur_rate=10.0, context=ctx)
>>> result.value[["ic_ref", "difference_dkk", "status", "fx_ok", "agrees"]].to_dict("records")
[{'ic_ref': 'IC-1', 'difference_dkk': 0.0, 'status': 'matched', 'fx_ok': True, 'agrees': True}, {'ic_ref': 'IC-2', 'difference_dkk': 2.0, 'status': 'difference', 'fx_ok': True, 'agrees': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `finance-reporting.intercompany_match.ic_ref`, `finance-reporting.intercompany_match.amount_le01_dkk`, `finance-reporting.intercompany_match.amount_le02_dkk`, `finance-reporting.intercompany_match.amount_le02_eur`, `finance-reporting.intercompany_match.difference_dkk`, `finance-reporting.intercompany_match.status`.
