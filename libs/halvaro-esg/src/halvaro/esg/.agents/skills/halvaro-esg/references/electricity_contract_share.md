# electricity_contract_share

Module `halvaro.esg.activity`. Import: `from halvaro.esg import electricity_contract_share`.

```python
electricity_contract_share(c: pd.DataFrame, m: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the share of electricity kWh on a renewable_certified contract per period and site.

The share is taken from the contract of each month in the consumption table (not today's contract of the meter, T9). Only electricity meters count; their unit must be kWh. The share is null when a site has no kWh in a period.

Args:
    c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity, unit and contract_type.
    m: The energy-esg.energy_meter table, with the columns mtr_key, carrier, unit and site_key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns period, site_key, kwh, renewable_kwh and share (renewable_kwh over kwh), sorted by period and site_key.

Raises:
    FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
    FrameError: a period is not text like 2025-03 (month 01 to 12); quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
    FrameError: an electricity meter has no site_key; electricity consumption is not in kWh; an electricity row has no contract_type.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import electricity_contract_share
    >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"], "quantity": [300.0, 100.0],
    ...                   "unit": ["kWh", "kWh"], "contract_type": ["renewable_certified", "standard"]})
    >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"],
    ...                   "unit": ["kWh", "kWh"], "site_key": ["SITE-900001", "SITE-900001"]})
    >>> out = electricity_contract_share(c, m, context=ctx)
    >>> out[["site_key", "kwh", "renewable_kwh", "share"]].values.tolist()
    [['SITE-900001', 400.0, 300.0, 0.75]]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.unit`
- `energy-esg.energy_meter.site_key`
- `energy-esg.energy_consumption.contract_type`
