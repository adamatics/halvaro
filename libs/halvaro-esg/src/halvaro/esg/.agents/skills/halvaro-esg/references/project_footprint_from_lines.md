# project_footprint_from_lines

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import project_footprint_from_lines`.

```python
project_footprint_from_lines(L: pd.DataFrame, basis: str = 'current', *, component_map: Mapping[tuple[str, str], str] = {('3.1', 'purchased_goods'): 'materials', ('3.1', 'purchased_services'): 'subcontractor', ('3.4', 'upstream_transport'): 'transport'}, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the four footprint components of each project and period from the emission lines that carry a project.

The result has the shape of energy-esg.project_footprint (without route_length_m and basis). Scope 1 and scope 3.3 (the fuel of the site and its well to tank) are the site component; purchased goods (3.1) are materials, purchased services (3.1) subcontractors and upstream transport (3.4) transport.
A project line that fits no component raises, and so does a component_map value that is not one of the four components (the map cannot move scope 1 or 3.3 lines out of the site component). Lines without a project (scope 2, waste) are not project footprint.
basis is current (restated lines replace the superseded originals) or first_booked. PROPOSED: the map, as in the generator.

Args:
    L: The energy-esg.emission_line table, with the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period.
    basis: current (superseded originals left out, the default) or first_booked (restated lines left out).
    component_map: Map from (ghg_category, category) to materials, transport, site or subcontractor (PROPOSED default: (3.1, purchased_goods) materials, (3.1, purchased_services) subcontractor, (3.4, upstream_transport) transport).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e, subcontractor_kgco2e and total_kgco2e (three decimals), sorted by prj_key and period.

Raises:
    FrameError: component_map is not a mapping or has a value that is not materials, transport, site or subcontractor.
    FrameError: L is not a DataFrame or lacks one of the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period; is_superseded has nulls; two lines share le_key, period, scope, category and line_no; basis is not current or first_booked.
    FrameError: a project line has a null kgco2e, scope or period; kgco2e or scope holds text, booleans or infinite values.
    FrameError: a project line fits no component.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import project_footprint_from_lines
    >>> L = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "le_key": ["LE-900001"] * 3, "period": ["2025-01"] * 3, "scope": [1, 3, 3],
    ...                   "category": ["fuel", "purchased_goods", "upstream_transport"], "line_no": [1, 2, 3],
    ...                   "ghg_category": ["1", "3.1", "3.4"], "kgco2e": [10.0, 20.0, 5.0],
    ...                   "is_superseded": [False] * 3, "restated_from_period": [None] * 3})
    >>> out = project_footprint_from_lines(L, context=ctx)
    >>> out[["prj_key", "materials_kgco2e", "transport_kgco2e", "site_kgco2e", "total_kgco2e"]].values.tolist()
    [['PRJ-900001', 20.0, 5.0, 10.0, 35.0]]

## Source columns

- `energy-esg.emission_line.prj_key`
- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
