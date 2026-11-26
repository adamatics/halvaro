# statement_inputs

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import statement_inputs`.

```python
statement_inputs(L: pd.DataFrame, C: pd.DataFrame, M: pd.DataFrame, T: pd.DataFrame, year: int | None = None, le: str = 'ALL', *, basis: str = 'current', kwh_per_litre: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> StatementInputs
```

Use this when you need the numbers for a statutory statement or a questionnaire of one entity or of the company: totals, comparatives, energy use and targets.

The scope totals of `year` on `basis` (default current; the basis decision is open, so the first booked totals are given too in the comparatives), the previous year on both bases, the energy use of the
year in MWh by carrier (litres need `kwh_per_litre`, as in energy_use_mwh; no default), and the targets. Notes say which basis was used, the months covered, that scope 2 is given by both methods and
never added, and that factors are synthetic. No text of a statement is written here.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    C: Frame energy-esg.energy_consumption with mtr_key, period, quantity and unit.
    M: Frame energy-esg.energy_meter with mtr_key, carrier and unit (and le_key when le is one entity).
    T: Frame energy-esg.target with target_no, returned as stored sorted by target_no.
    year: The whole year, like 2025; the year before the year of world.now when None.
    le: One le_key, or 'ALL' (default) for the company.
    basis: 'current' (default) or 'first_booked'; the basis of the totals.
    kwh_per_litre: Mapping from a carrier metered in litres to its kWh per litre (VERIFY, no default); needed when the year has litres.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    StatementInputs, a named tuple of totals (the scope totals frame of the year), comparatives (the scope totals of the previous year on the current and on the first_booked basis, with a basis column), energy_use (carrier, unit, quantity, mwh), targets (frame T sorted by target_no) and notes (a tuple of text).

Raises:
    FrameError: there are no emission lines for the year and entity, C, M or T lacks a column, the lines fail as in scope_totals (missing column, null kgco2e, bad year, basis or scope, restated lines not flagged), or the consumption fails as in energy_use_mwh (a repeated meter or period, an unknown meter, a unit that differs from the meter, a carrier in litres without a positive kwh_per_litre, a unit that is not kWh, MWh or l).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import statement_inputs
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
    ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
    >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"] * 2, "period": ["2025-12", "2025-11"], "quantity": [100.0, 200.0], "unit": "l"})
    >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": "diesel", "unit": "l", "le_key": "LE-900001"})
    >>> T = pd.DataFrame({"target_no": ["TGT-900001"]})
    >>> s = statement_inputs(L, C, M, T, 2025, kwh_per_litre={"diesel": 10.0}, context=ctx)
    >>> s.totals.loc[0, ["scope1", "scope3", "total_location_based"]].astype(float).tolist()
    [100.0, 30.0, 130.0]
    >>> s.energy_use.to_dict("records")
    [{'carrier': 'diesel', 'unit': 'l', 'quantity': 300.0, 'mwh': 3.0}]
    >>> s.notes[0]
    'totals are on the current basis'

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
- `energy-esg.energy_consumption.mtr_key`
- `energy-esg.energy_consumption.period`
- `energy-esg.energy_consumption.quantity`
- `energy-esg.energy_consumption.unit`
- `energy-esg.energy_meter.mtr_key`
- `energy-esg.energy_meter.carrier`
- `energy-esg.energy_meter.le_key`
- `energy-esg.target.target_no`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
