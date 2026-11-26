# translation_check

```python
translation_check(trial_balance: pd.DataFrame, *, month: int = 12, rate_tolerance: float = 0.001, eur_rate: float | None = None, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you check the rounding of the line by line EUR to DKK translation of a trial balance at each fiscal year end.

Rule: per period of the chosen month, the stored DKK closing balance of the EUR lines is compared with the closing balance times the fixed rate rounded to the cent (half away from zero). At a fixed rate only cent rounding is left, so the difference is the stored sum less the recomputed sum. A period whose EUR lines (balance above 1 in absolute value) are translated at an implied rate (sum of DKK over sum of EUR, absolute values) that differs from the fixed rate by more than rate_tolerance is an error, because a translation difference would arise.

## Args

trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-12), gl_key, closing_balance, currency and closing_balance_dkk.
month: The month number (1 to 12) that ends the fiscal year. Default 12 (proposed).
rate_tolerance: Largest accepted gap between the implied rate and the fixed rate. Default 0.001 (proposed).
eur_rate: The EUR to DKK rate to test against; None takes the fixed rate of the core fact world.fx_eur_dkk_fixed. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with period, n_lines, sum_dkk, sum_recomputed_dkk, rounding_dkk (stored less recomputed) and max_line_rounding_dkk, one row per period of the month; empty when no EUR line is in that month.

## Raises

FrameError: a column is missing, month is not a whole number from 1 to 12, eur_rate is not a positive number, or the EUR lines of a period are translated at a rate that differs from the fixed rate by more than rate_tolerance.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import translation_check
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-02"], "period": ["2026-12"], "gl_key": ["GL-1"], "closing_balance": [100.0], "currency": ["EUR"], "closing_balance_dkk": [750.01]})
>>> translation_check(tb, eur_rate=7.5, context=ctx).value[["period", "n_lines", "rounding_dkk"]].values.tolist()
[['2026-12', 1, 0.01]]
>>> translation_check(tb, month=13, eur_rate=7.5, context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: month is a whole month number from 1 to 12
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.closing_balance`, `finance.trial_balance.currency`, `finance.trial_balance.closing_balance_dkk`.
