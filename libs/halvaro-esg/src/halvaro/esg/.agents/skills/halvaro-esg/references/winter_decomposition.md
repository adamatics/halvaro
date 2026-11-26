# winter_decomposition

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import winter_decomposition`.

```python
winter_decomposition(C: pd.DataFrame, M: pd.DataFrame, MA: pd.DataFrame, now: Sequence[str] = ('2025-12', '2026-02'), prev: Sequence[str] = ('2024-12', '2025-02'), *, carrier: str = 'diesel', by: str = 'meter', context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the litres of a fuel in a winter window against the same months a year earlier, per meter, meter kind or asset type.

Litres of a fuel in a winter window against the same months a year earlier, per meter (by='meter'), meter kind or asset type. Columns: [mtr_key,] [kind,] asset_type (the most common asset type of the
meter in `MA`, null without an asset), litres_now, litres_prev, extra_litres (now less prev; null when a window has no consumption row), months_now, months_prev (distinct periods with a consumption row of the group in the window, so a
gap shows only when no meter of the group has a row), pct_change. Meters of another carrier are left out. The generator's own 'extra litres' is build state and is not reproduced (plan: candidate); this is the difference of the metered litres.

Args:
    C: Frame energy-esg.energy_consumption with mtr_key, period, quantity and unit, one row per meter and period.
    M: Frame energy-esg.energy_meter with mtr_key, carrier, kind and unit, one row per meter.
    MA: Frame energy-esg.energy_meter_asset with mtr_key and asset_type.
    now: The (first, last) periods of the later window, inclusive (default ('2025-12', '2026-02')).
    prev: The (first, last) periods of the window a year earlier, with as many months as now (default ('2024-12', '2025-02')).
    carrier: The carrier of the meters to count (default 'diesel').
    by: 'meter' (mtr_key, kind and asset_type), 'kind' or 'asset_type'; the grouping of the rows.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    DataFrame with the columns above (mtr_key, kind and asset_type for by='meter', else the one group column), sorted by the group columns with nulls last; litres to three decimals, pct_change to two.

Raises:
    FrameError: a window is not a (first, last) pair of period text in order, the two windows have a different number of months, by is not meter, kind or asset_type, C, M or MA lacks a column, a meter or a meter and period is repeated, the meters of the carrier have more than one unit, or the consumption has null quantities.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import winter_decomposition
    >>> ctx = Context(stage="month12", role="analyst")
    >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"] * 4, "period": ["2024-12", "2025-01", "2025-12", "2026-01"], "quantity": [100.0, 100.0, 150.0, 150.0], "unit": "l"})
    >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": "diesel", "kind": "generator", "unit": "l"})
    >>> MA = pd.DataFrame({"mtr_key": ["MTR-900001"], "asset_type": ["generator_set"]})
    >>> r = winter_decomposition(C, M, MA, now=("2025-12", "2026-01"), prev=("2024-12", "2025-01"), context=ctx)
    >>> r.to_dict("records")
    [{'mtr_key': 'MTR-900001', 'kind': 'generator', 'asset_type': 'generator_set', 'litres_now': 300.0, 'litres_prev': 200.0, 'extra_litres': 100.0, 'months_now': 2, 'months_prev': 2, 'pct_change': 50.0}]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.kind`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter_asset.mtr_key`
- `energy-esg.energy_meter_asset.asset_type`
