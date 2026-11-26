# lever_fuel_switch

Module `halvaro.esg.levers`. Import: `from halvaro.esg import lever_fuel_switch`.

```python
lever_fuel_switch(L: pd.DataFrame, F: pd.DataFrame, P: pd.DataFrame | None = None, to: str = 'hvo100', *, context: halvaro.core.access.Context) -> object
```

Use this when you need the kilograms CO2e that moving the site diesel of each project to HVO100 would save, per project and optionally per route metre.

Kilograms CO2e saved per project (and per route metre with `P`, projects.project with route_length_m) if the site diesel of the project moved to HVO100, combustion plus well to tank. Diesel combustion lines are current-basis scope 1 lines whose factor family is fuel_diesel, the well to tank lines are the lines of the family fuel_wtt_diesel. Each diesel quantity is priced again with the HVO factor of the same factor set and region and the same unit; a missing HVO factor row raises FrameError. Property: 0 <= saved <= diesel_kgco2e as long as HVO is not worse. Lines without a project are left out. The result is an estimate with the status VERIFY+synthetic and a warning that the biogenic treatment of HVO100 is a policy decision still needed (VERIFY).

Args:
    L: The energy-esg.emission_line table with the columns prj_key, le_key, period, scope, category, line_no, quantity, efac_key, kgco2e, is_superseded, restated_from_period, supersedes_line_no and unit.
    F: The energy-esg.emission_factor table with the columns efac_key, category, region, factor_set, kgco2e_per_unit and unit.
    P: Optional projects.project table with prj_key and route_length_m; when given, the per metre columns are added.
    to: The target fuel; only "hvo100" is known (PROPOSED: its combustion family fuel_hvo and well to tank family fuel_wtt_hvo).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns prj_key, diesel_litres, diesel_kgco2e (combustion plus well to tank), switched_kgco2e, saved_kgco2e, worse (the target factor is higher) and, with `P`, route_length_m and saved_kgco2e_per_m (null when the route length is not above zero), one row per project sorted by prj_key, kgco2e to three decimals.

Raises:
    FrameError: `to` is not a known target fuel, or L or F lacks a column, or the line checks of current_basis fail (repeated line key, bad restatement links).
    FrameError: F has more than one row for a factor key, a fuel line has no efac_key, or L names a factor that F does not hold.
    FrameError: a diesel line has no quantity or no kgco2e, or its unit differs from the unit of its factor.
    FrameError: a target factor row has no kgco2e_per_unit, F has two target rows for the same family, set, region and unit, or no HVO factor row exists for the family, set, region and unit of a diesel line.
    FrameError: P lacks prj_key or route_length_m, or has more than one row for a project.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import lever_fuel_switch
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"]
    >>> L = pd.DataFrame([
    ...     ("PRJ-900001", "LE-900001", "2025-03", 1, "mobile_combustion", 1, 100.0, "EF-900001", 270.0, False, None, None, "l"),
    ...     ("PRJ-900001", "LE-900001", "2025-03", 3, "fuel_and_energy_related", 2, 100.0, "EF-900002", 60.0, False, None, None, "l")], columns=cols)
    >>> F = pd.DataFrame([
    ...     ("EF-900001", "fuel_diesel", "DE", "S1", 2.7, "l"), ("EF-900002", "fuel_wtt_diesel", "DE", "S1", 0.6, "l"),
    ...     ("EF-900003", "fuel_hvo", "DE", "S1", 0.2, "l"), ("EF-900004", "fuel_wtt_hvo", "DE", "S1", 0.5, "l")],
    ...     columns=["efac_key", "category", "region", "factor_set", "kgco2e_per_unit", "unit"])
    >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0]})
    >>> r = lever_fuel_switch(L, F, P, context=ctx)
    >>> r.value[["prj_key", "diesel_kgco2e", "switched_kgco2e", "saved_kgco2e", "saved_kgco2e_per_m"]].to_dict("records")
    [{'prj_key': 'PRJ-900001', 'diesel_kgco2e': 330.0, 'switched_kgco2e': 70.0, 'saved_kgco2e': 260.0, 'saved_kgco2e_per_m': 2.6}]
    >>> r.status
    'VERIFY+synthetic'

## Source columns

- `energy-esg.emission_line.prj_key`
- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.quantity`
- `energy-esg.emission_line.efac_key`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
- `energy-esg.emission_line.supersedes_line_no`
- `energy-esg.emission_line.unit`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.factor_set`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.unit`
- `projects.project.prj_key`
- `projects.project.route_length_m`
