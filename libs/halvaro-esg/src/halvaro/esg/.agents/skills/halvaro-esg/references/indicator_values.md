# indicator_values

Module `halvaro.esg.score`. Import: `from halvaro.esg import indicator_values`.

```python
indicator_values(T: pd.DataFrame, L: pd.DataFrame, C: pd.DataFrame, M: pd.DataFrame, E: pd.DataFrame, A: pd.DataFrame, as_of: DateLike, *, year: int | None = None, cycle_years: int = 4, intensity_actual: float | None = None, epd_marker: str = 'supplier EPD', context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the seven environment indicator values (glide path and share indicators) before they are scored.

The seven indicator values as facts, no judgement. Four are glide path indicators from
`target_progress` (scope 1, scope 2 location, scope 3, project intensity): value = achieved reduction over the required reduction at `year` (PROPOSED reading: (baseline - actual) / (baseline - glide value) at that year,
current factor basis; a value above 1 is possible and is clipped only when scored), null when the year has fewer than 12 months of lines or the required reduction is zero. `intensity_actual` is the per route metre median, which
this library does not hold (it comes from halvaro-delivery); without it the project intensity value is null. Three are shares: renewable electricity (kWh on a renewable_certified contract over all
electricity kWh in `year`), EPD coverage (share of the items valid on the day whose `item_epd.source` contains `epd_marker`, PROPOSED), audit currency (share of audited sites that are not overdue, `cycle_years`
is the VERIFY keyword of audit_schedule). `year` defaults to the year before `as_of`, as in target_progress. The result has the status VERIFY+synthetic.

Args:
    T: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, baseline_value and target_value.
    L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period.
    C: The energy-esg.energy_consumption table with the columns mtr_key, period, quantity, unit and contract_type.
    M: The energy-esg.energy_meter table with the columns mtr_key, carrier, unit and site_key.
    E: The energy-esg.item_epd table with the columns itm_key, valid_from, valid_to and source.
    A: The energy-esg.energy_audit table with the columns site_key, audit_date, due_date and status.
    as_of: The day (date, Timestamp, ISO text or YYYY-MM) of the reading; the items and audits are taken as of this day.
    year: The whole year of the readings; the year before as_of when None.
    cycle_years: The audit cycle in whole years (the VERIFY keyword of audit_schedule).
    intensity_actual: The per route metre median of the year, from halvaro-delivery; None leaves the project intensity value null.
    epd_marker: The text that item_epd.source must contain for an item to count as covered (PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a frame with the columns indicator, kind ('glide' or 'share'), value, baseline, actual, glide_value, n and note, one row per indicator in the order scope1, scope2_location, scope3, project_intensity, renewable_electricity_share, epd_coverage, audit_currency; a value that cannot be read is null and the note says why.

Raises:
    FrameError: T lacks a column, has a target twice, has no rows, has nulls in a baseline or target value or year, a target scope that is not known, or a target that ends before its baseline year; year is not a whole year; as_of is a number, not a date, or has a time zone.
    FrameError: L lacks a column or is not a valid emission line frame (is_superseded has nulls, a line key is repeated, kgco2e is null, a scope is not 1, 2 or 3, a scope 3 line has no known ghg_category, a scope 2 line has another method than location or market, a restated line has no supersedes_line_no).
    FrameError: C or M lacks a column, has a meter or a meter and period twice, has a period that is not text YYYY-MM, a non numeric or null quantity, a consumption row of an unknown meter or of another unit than its meter, an electricity meter without site_key, electricity not in kWh or without a contract_type.
    FrameError: E lacks a column; A lacks a column, has a null status or site_key, a completed audit without an audit date, an open audit without a due date, two open audits for a site, a value that is not a date, or cycle_years is not a whole number from 1 to 100.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import indicator_values
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([("LE-900001", f"{y}-{m:02d}", 1, "stationary_combustion", 1, None, None, kg, False, None)
    ...                   for y, kg in ((2029, 100.0), (2031, 70.0)) for m in range(1, 13)], columns=cols)
    >>> T = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2029], "target_year": [2035],
    ...                   "baseline_value": [1200.0], "target_value": [600.0]})
    >>> C = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2031-01", "2031-01"], "quantity": [300.0, 100.0],
    ...                   "unit": ["kWh", "kWh"], "contract_type": ["renewable_certified", "grid_mix"]})
    >>> M = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"],
    ...                   "unit": ["kWh", "kWh"], "site_key": ["SITE-900001", "SITE-900001"]})
    >>> E = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "valid_from": ["2030-01-01", "2030-01-01"],
    ...                   "valid_to": [None, None], "source": ["supplier EPD", "estimate"]})
    >>> A = pd.DataFrame({"site_key": ["SITE-900001"], "audit_date": ["2030-06-01"], "due_date": [None], "status": ["completed"]})
    >>> r = indicator_values(T, L, C, M, E, A, "2032-02-01", context=ctx)
    >>> r.status
    'VERIFY+synthetic'
    >>> r.value.set_index("indicator")["value"].round(2).loc[["scope1", "renewable_electricity_share", "epd_coverage", "audit_currency"]].tolist()
    [1.8, 0.75, 0.5, 1.0]

## Source columns

- `energy-esg.target.target_no`
- `energy-esg.target.scope`
- `energy-esg.target.baseline_year`
- `energy-esg.target.target_year`
- `energy-esg.target.baseline_value`
- `energy-esg.target.target_value`
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
- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_consumption.contract_type`
- `energy-esg.item_epd.itm_key`
- `energy-esg.item_epd.valid_from`
- `energy-esg.item_epd.valid_to`
- `energy-esg.item_epd.source`
- `energy-esg.energy_audit.site_key`
- `energy-esg.energy_audit.audit_date`
- `energy-esg.energy_audit.due_date`
- `energy-esg.energy_audit.status`
