# energy_cost

Module `halvaro.esg.activity`. Import: `from halvaro.esg import energy_cost`.

```python
energy_cost(c: pd.DataFrame, m: pd.DataFrame, *, to_dkk: bool = False, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the cost, quantity and unit price of energy per carrier, unit and currency.

The currency is kept (DKK sites and EUR sites are never added, T20). With to_dkk the cost is also given in DKK at the fixed booking rates of core convert, converted per consumption row and summed. There is no window: all periods of the frame count, so the unit price is an average over them.
The unit price is cost over quantity, four decimals, null without quantity.

Args:
    c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity, unit, cost_amount and currency.
    m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit.
    to_dkk: When true, add cost_dkk (default false).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns carrier, unit, currency, quantity (three decimals), cost (two decimals), unit_price and, with to_dkk, cost_dkk, sorted by carrier, unit and currency.

Raises:
    FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
    FrameError: a period is not text like 2025-03 (month 01 to 12); quantity or cost_amount is not numeric; quantity, cost_amount or currency is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
    BasisError: with to_dkk, a currency has no booking rate to DKK (known: DKK, EUR, SEK).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import energy_cost
    >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900001"], "period": ["2025-01", "2025-02"], "quantity": [100.0, 100.0],
    ...                   "unit": ["kWh", "kWh"], "cost_amount": [20.0, 30.0], "currency": ["DKK", "DKK"]})
    >>> m = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": ["electricity"], "unit": ["kWh"]})
    >>> out = energy_cost(c, m, context=ctx)
    >>> out[["carrier", "currency", "quantity", "cost", "unit_price"]].values.tolist()
    [['electricity', 'DKK', 200.0, 50.0, 0.25]]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.unit`
- `energy-esg.energy_consumption.cost_amount`
- `energy-esg.energy_consumption.currency`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.fx_eur_dkk_fixed`
- `world.fx_sek_dkk_fixed`
