# check_meters

Module `halvaro.esg.activity`. Import: `from halvaro.esg import check_meters`.

```python
check_meters(m: pd.DataFrame, *, unit_by_carrier: Mapping[str, Any] = {'diesel': 'l', 'petrol': 'l', 'natural_gas': 'kWh', 'electricity': 'kWh', 'district_heat': 'MWh'}, scope_by_carrier: Mapping[str, Any] = {'diesel': 1, 'petrol': 1, 'natural_gas': 1, 'electricity': 2, 'district_heat': 2}, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to check the meter list against the unit and scope that each carrier must have.

Violations (table, key, rule, detail) of the meter list: unknown_carrier, unit (not the unit of the carrier), scope (not the scope of the carrier), duplicate_meter.

PROPOSED: the carrier maps are the units and scopes of the baseline meters; no file states the rule (candidate in the plan, ghg-inventory-method is planned).

Args:
    m: The energy-esg.energy_meter table, with the columns mtr_key, carrier, scope and unit.
    unit_by_carrier: Map from carrier to its metered unit (PROPOSED default: diesel and petrol l, natural_gas and electricity kWh, district_heat MWh).
    scope_by_carrier: Map from carrier to its scope (PROPOSED default: diesel, petrol and natural_gas 1, electricity and district_heat 2).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A violation frame with the columns table, key, rule and detail, in a stable order; empty when the meters follow the rule.

Raises:
    FrameError: m is not a DataFrame or lacks mtr_key, carrier, scope or unit.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import check_meters
    >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["diesel", "electricity"],
    ...                   "scope": [1, 2], "unit": ["kWh", "kWh"]})
    >>> out = check_meters(m, context=ctx)
    >>> out[["key", "rule"]].values.tolist()
    [['MTR-900001', 'unit']]

## Source columns

- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.scope`
- `energy-esg.energy_meter.unit`
