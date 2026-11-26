# consumption_by

Module `halvaro.esg.activity`. Import: `from halvaro.esg import consumption_by`.

```python
consumption_by(c: pd.DataFrame, m: pd.DataFrame, by: str, p0: str, p1: str, *, exclude_kinds: Sequence[str] | None = (), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the consumption per period and carrier, site or kind in the native unit of the meters for a window of periods.

Quantity per period and carrier, site or kind in the native unit of the meters, for the periods p0 to p1 inclusive. A carrier has one unit, so units never mix; a consumption row whose unit differs from its meter raises. `by` is carrier, site or kind.
Caution (T12): the purchase order tank meters (kind po_site_tank) carry the administrative site, not the site where the fuel was used, so a site total mixes metered and allocated fuel (part of the litres of a site can be allocated, not metered; the share is computed, not stated here);
exclude_kinds drops kinds from the result, for example ('po_site_tank',). The meters and the window decide the coverage.

Args:
    c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity and unit.
    m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit, plus site_key when by is site and kind when by is kind or exclude_kinds is used.
    by: What to group by: carrier, site or kind.
    p0: First period of the window, text like 2025-03.
    p1: Last period of the window (inclusive), text like 2025-03.
    exclude_kinds: Meter kinds to drop before grouping (default none); a sequence of text, not one string.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns period, <by>, unit, quantity and n_meters (distinct meters), sorted by period, <by> and unit.

Raises:
    FrameError: by is not carrier, site or kind; p0 or p1 is not a period text like 2025-03; p0 is after p1; exclude_kinds is a single string or holds non-text.
    FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
    FrameError: a period is not text like 2025-03 (month 01 to 12) or is null; quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier.
    FrameError: a consumption row has another unit than its meter (units are never converted silently).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import consumption_by
    >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"],
    ...                   "quantity": [100.0, 50.0], "unit": ["kWh", "kWh"]})
    >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"], "unit": ["kWh", "kWh"]})
    >>> out = consumption_by(c, m, "carrier", "2025-01", "2025-01", context=ctx)
    >>> out[["period", "carrier", "quantity", "n_meters"]].values.tolist()
    [['2025-01', 'electricity', 150.0, 2]]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.unit`
- `energy-esg.energy_meter.site_key`
- `energy-esg.energy_meter.kind`
