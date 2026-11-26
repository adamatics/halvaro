# expected_lines_s123

Module `halvaro.esg.recompute`. Import: `from halvaro.esg import expected_lines_s123`.

```python
expected_lines_s123(c: pd.DataFrame, m: pd.DataFrame, f: pd.DataFrame, *, heat_region_by_site: Mapping[str, Any] | None = None, restate: Mapping[str, Any] | None = None, include_tanks: bool = False, contract_types: Sequence[str] = ('grid_mix', 'renewable_certified'), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the scope 1, scope 2 and scope 3.3 emission lines that the consumption of each meter and month should produce.

The scope 1, scope 2 (location and market) and scope 3.3 lines expected from the consumption of each meter and month, one row per meter, month and line kind. Scope 1 category is stationary_combustion for gas and generator
meters, else mobile_combustion; scope 3.3 is the well to tank factor of the same fuel (region EU). Electricity location uses the grid average of the country; market uses certified renewable
in a month whose contract is renewable_certified, else the residual mix. District heat uses the network of the site (`heat_region_by_site`, required when heat meters are present; the networks
are not in any table). `restate={'year': 2025, 'factor_date': '2026-01-01'}` takes the factors valid on that date for the periods of that year (the restated basis); without it the factor of
the first day of each period (as first booked). Scope 1 lines of the estate are split over projects: compare with recompute_diff, which sums per meter. Meters of kind po_site_tank are left out
unless include_tanks (their fuel can be HVO, which the meter does not say; with include_tanks a tank filled with HVO does not tie, because the meter does not say which fuel the purchase order delivered).
Electricity contract types other than `contract_types` (PROPOSED: grid_mix and renewable_certified; null is the residual mix) raise, as do negative or null quantities and a factor unit that differs from the line unit.

Args:
    c: The energy-esg.energy_consumption table with the columns mtr_key, period (text YYYY-MM), quantity, unit and contract_type; one row per meter and period.
    m: The energy-esg.energy_meter table with the columns mtr_key (one row per meter), carrier, kind, country, site_key, unit and le_key.
    f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set (and unit, which must then equal the consumption unit).
    heat_region_by_site: Mapping (or Series) from site_key to the heat network region; required when district heat meters are present, else None.
    restate: None for the factors of the first day of each period (as first booked), or a mapping with exactly the keys year and factor_date for the restated basis of that year.
    include_tanks: True to keep the meters of kind po_site_tank, which are left out otherwise.
    contract_types: The electricity contract types that are accepted (PROPOSED: grid_mix and renewable_certified); another non null type raises.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns ref_key (the meter), period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor and expected_kg (quantity times factor, rounded to 3 decimals), sorted by ref_key, period, scope, ghg_category and method; empty with these columns when no line is expected.

Raises:
    FrameError: c, m or f is not a frame or lacks a needed column; a meter is twice in m or a meter and period twice in c; a consumption row names a meter that is not in m or has another unit than its meter.
    FrameError: a quantity is text or boolean, null, negative or infinite; an electricity contract_type is not in contract_types (or null); a carrier has no factor family in the rule.
    FrameError: heat_region_by_site is not a mapping, has a site twice, maps a site to no region, or lacks a site of a district heat meter.
    FrameError: restate is not a mapping with exactly the keys year (a whole year from 1900 to 2200) and factor_date (a date), the restate year has no period in the data, or a period is not text YYYY-MM.
    FrameError: a line has no valid factor or more than one valid factor on its date, or the factor unit differs from the consumption unit.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import expected_lines_s123
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set", "unit"]
    >>> F = pd.DataFrame([
    ...     ("EF-900001", "fuel_natural_gas", "natural_gas", "DE", None, 2.0, "2031-01-01", None, "FS-A", "m3"),
    ...     ("EF-900002", "fuel_wtt_natural_gas", "natural_gas", "EU", None, 0.5, "2031-01-01", None, "FS-A", "m3")], columns=cols)
    >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"], "period": ["2031-03"], "quantity": [100.0], "unit": ["m3"], "contract_type": [None]})
    >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": ["natural_gas"], "kind": ["gas"], "country": ["DE"],
    ...                   "site_key": ["SITE-900001"], "unit": ["m3"], "le_key": ["LE-900001"]})
    >>> out = expected_lines_s123(C, M, F, context=ctx)
    >>> out[["scope", "ghg_category", "expected_kg"]].values.tolist()
    [[1, '1', 200.0], [3, '3.3', 50.0]]

## Source columns

- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_consumption.contract_type`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.kind`
- `energy-esg.energy_meter.country`
- `energy-esg.energy_meter.site_key`
- `energy-esg.energy_meter.le_key`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
- `energy-esg.emission_factor.factor_set`
- `energy-esg.energy_meter.valid_from`
