# renewable_effect

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import renewable_effect`.

```python
renewable_effect(L: pd.DataFrame, C: pd.DataFrame, before: Sequence[str] | None = None, after: Sequence[str] | None = None, *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the monthly average of scope 2 before and after the renewable contract, market against location, with the percent change.

Monthly average of scope 2 on the current basis before and after the renewable contract, market against location, for electricity and for all scope 2, with the percent change. The windows come
from the data when not given: `after` runs from the first period with a renewable_certified contract in the consumption table to the last period of the lines, `before` is the 12 months ending the
month before. The market method falls with the contract, the location method does not (T10, T11).

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    C: Frame energy-esg.energy_consumption with period and contract_type (used to find the first renewable_certified period when after is None).
    before: The (first, last) periods like ('2024-01', '2024-12') of the window before the contract; the 12 months ending the month before after when None.
    after: The (first, last) periods of the window after the contract starts; from the first renewable_certified period to the last period of the lines when None.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with measure (location_all, location_electricity, market_all, market_electricity), avg_before_kg, avg_after_kg, change_percent (null without a positive before average), months_before and months_after, one row per measure in that order.

Raises:
    FrameError: L or C is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, a restated line has no supersedes_line_no or its original is not flagged is_superseded, no consumption is on a renewable_certified contract and the windows are not passed, a window is not a (first, last) pair of periods in order, the windows overlap or are in the wrong order, or a window lacks scope 2 lines (location or market, all or purchased_electricity) for some of its months.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import renewable_effect
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
    ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 40.0, False, None),
    ...     ("LE-900001", "2025-02", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
    ...     ("LE-900001", "2025-02", 2, "purchased_electricity", 2, "market", None, 10.0, False, None)], columns=cols)
    >>> C = pd.DataFrame({"period": ["2025-01", "2025-02"], "contract_type": ["standard", "renewable_certified"]})
    >>> r = renewable_effect(L, C, before=("2025-01", "2025-01"), after=("2025-02", "2025-02"), context=ctx)
    >>> r.value.set_index("measure")["change_percent"].to_dict()
    {'location_all': 0.0, 'location_electricity': 0.0, 'market_all': -75.0, 'market_electricity': -75.0}

## Source columns

- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.method`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.contract_type`
