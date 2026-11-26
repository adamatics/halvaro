# energy_use_mwh

Module `halvaro.esg.activity`. Import: `from halvaro.esg import energy_use_mwh`.

```python
energy_use_mwh(c: pd.DataFrame, m: pd.DataFrame, *, kwh_per_litre: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the energy use per carrier in MWh.

kWh is divided by 1,000 and MWh is taken as is. Litres need the energy content of the fuel, which no file holds (fact needed, VERIFY): pass kwh_per_litre as {carrier: kWh per litre} for them, or consumption in litres raises and names the missing fact.
PROPOSED: kwh_per_litre has no default.

Args:
    c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity and unit.
    m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit.
    kwh_per_litre: Map from carrier to kWh per litre for the carriers metered in litres (default none).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns carrier, unit (the metered unit), quantity (three decimals) and mwh (six decimals), sorted by carrier and unit.

Raises:
    FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
    FrameError: a period is not text like 2025-03 (month 01 to 12); quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
    FrameError: a carrier is metered in litres and kwh_per_litre has no value for it, or the value is not a positive finite number; a unit is not kWh, MWh or l.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import energy_use_mwh
    >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"], "quantity": [5000.0, 100.0], "unit": ["kWh", "l"]})
    >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "diesel"], "unit": ["kWh", "l"]})
    >>> out = energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0}, context=ctx)
    >>> out[["carrier", "unit", "mwh"]].values.tolist()
    [['diesel', 'l', 1.0], ['electricity', 'kWh', 5.0]]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.unit`
