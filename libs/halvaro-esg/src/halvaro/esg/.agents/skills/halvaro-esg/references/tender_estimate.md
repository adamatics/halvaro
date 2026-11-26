# tender_estimate

Module `halvaro.esg.footprint`. Import: `from halvaro.esg import tender_estimate`.

```python
tender_estimate(EB: pd.DataFrame, CC: pd.DataFrame, PF: pd.DataFrame, P: pd.DataFrame, TC: pd.DataFrame | None, metres: float, *, estimate_type: str = 'tender', component_of_category: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> TenderEstimate
```

Use this when you need a labelled footprint estimate of an open tender from the intensity of its comparable projects.

The estimate is kilograms per unit of estimate cost for each footprint component in each currency (the footprint of the comparable projects over the cost of the estimate categories that drive the component,
PROPOSED map material to materials, labour and equipment to site, subcontractor to subcontractor, 'other' to none; transport is added to materials), times the cost `TC` of the tender by category that the app passes in.
The cross-check is the median kg per route metre of the comparables times `metres`. Without `TC` only the cross-check is returned and `warnings` says so; a currency of `TC` that no comparable estimate has gives no row and a warning; a component with tender cost in a currency whose comparables carry no cost for that component gives no row and no warning.
Amounts of different currencies are never added. Legacy summary projects have no estimate lines and are not in EB. An estimate, not a measurement; synthetic data.

Args:
    EB: The lines frame of estimate_bridge of the comparables, with the columns prj_key, type, cst_key, amount and currency.
    CC: The projects.cost_code table, with the columns cst_key and category (group rows are left out when is_group is present).
    PF: The energy-esg.project_footprint table, with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e, subcontractor_kgco2e and total_kgco2e.
    P: The projects.project table, with the columns prj_key and route_length_m.
    TC: The cost of the tender by category, with the columns category, amount and currency (passed in by the app), or None for the cross-check only.
    metres: The planned route metres of the tender, a positive finite number.
    estimate_type: The type of the estimate lines used from EB (default tender).
    component_of_category: Map from cost category to footprint component (default the PROPOSED map: material materials, labour and equipment site, subcontractor subcontractor).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A TenderEstimate with rows (component, currency, intensity_kg_per_unit, tender_cost, estimated_kg), estimated_kg (null without a cost frame), the cross-check from the comparables (median_kg_per_m, metres, cross_check_kg),
    ratio (estimate over cross-check; null when the cross-check is zero or there is no estimate), n_projects, label and warnings.

Raises:
    FrameError: EB, CC, PF, P or TC lacks a needed column; metres is not a positive finite number (a boolean is refused); projects.cost_code has two rows for a cst_key or projects.project two rows for a project.
    FrameError: an estimate line has a cost code that projects.cost_code does not hold; no comparable project has both an estimate and a footprint; no comparable project has a route length.
    FrameError: a tender cost is not a number of zero or more; the tender cost frame matches no component and currency of the comparables.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> ctx = Context(stage="month12", role="analyst")
    >>> from halvaro.esg import tender_estimate
    >>> EB = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tender"], "cst_key": ["CST-900001"], "amount": [1000.0], "currency": ["EUR"]})
    >>> CC = pd.DataFrame({"cst_key": ["CST-900001"], "category": ["material"]})
    >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001"], "period": ["2025-01"], "materials_kgco2e": [100.0], "transport_kgco2e": [10.0],
    ...                    "site_kgco2e": [50.0], "subcontractor_kgco2e": [0.0], "total_kgco2e": [160.0]})
    >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0]})
    >>> TC = pd.DataFrame({"category": ["material"], "amount": [2000.0], "currency": ["EUR"]})
    >>> r = tender_estimate(EB, CC, PF, P, TC, 500.0, context=ctx)
    >>> (r.estimated_kg, r.cross_check_kg, r.ratio, r.n_projects)
    (220.0, 800.0, 0.275, 1)

## Source columns

- `projects.estimate_line.cst_key`
- `projects.estimate_line.amount`
- `projects.cost_code.category`
- `energy-esg.project_footprint.prj_key`
- `energy-esg.project_footprint.period`
- `energy-esg.project_footprint.materials_kgco2e`
- `energy-esg.project_footprint.transport_kgco2e`
- `energy-esg.project_footprint.site_kgco2e`
- `energy-esg.project_footprint.subcontractor_kgco2e`
- `energy-esg.project_footprint.total_kgco2e`
- `projects.project.route_length_m`
