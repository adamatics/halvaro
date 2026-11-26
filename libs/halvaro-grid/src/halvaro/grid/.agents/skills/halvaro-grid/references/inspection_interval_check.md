# inspection_interval_check

Module `halvaro.grid.maintenance`. Import: `from halvaro.grid import inspection_interval_check`.

```python
inspection_interval_check(maintenance_plan: pd.DataFrame, grid_element: pd.DataFrame, *, plan_type: str = 'condition_inspection', cycle_months: dict[str, Any] | None = None, type_multiplier: dict[str, Any] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the inspection plans whose interval in months deviates from the rule for the condition class and element type.

Interval = cycle of the condition class (A 120, B 84, C 54, D 32, E 26 months, PROPOSED) times the multiplier of the element type
(PROPOSED: pipe 1.25, valve 1.2, substation and pump station 0.7, transformer station 0.9, others 1.0), rounded half to even (32.5 months is 32, as Python's round in the generator).
Elements without a class or with an unknown type are listed with expected_months null. Plans of other types than `plan_type` are ignored.

Args:
    maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, interval_months and valid_from.
    grid_element: The gis.grid_element frame, columns net_key, condition_class and element_type.
    plan_type: The plan type that is checked (default "condition_inspection").
    cycle_months: PROPOSED mapping of condition class to cycle in months; None reads the facts policy.grid.inspection_cycle_months.A to E (proposed, today A 120, B 84, C 54, D 32, E 26).
    type_multiplier: PROPOSED mapping of element type to multiplier; None reads the facts policy.grid.inspection_type_multiplier.<type> (proposed).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame of the deviating plans with the columns net_key, plan_no, element_type, condition_class, interval_months, expected_months and valid_from, sorted by net_key and plan_no.

Raises:
    FrameError: a column of maintenance_plan or grid_element is missing; grid_element has more than one row for a net_key; a fact of the rule cannot be read.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import inspection_interval_check
    >>> ctx = Context(stage="month12", role="analyst")
    >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "plan_no": [1, 1], "plan_type": "condition_inspection", "interval_months": [54, 60], "valid_from": ["2025-01-01", "2025-01-01"]})
    >>> g = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "condition_class": ["C", "C"], "element_type": ["cable_section", "cable_section"]})
    >>> out = inspection_interval_check(p, g, context=ctx)
    >>> out[["net_key", "interval_months", "expected_months"]].to_dict("records")
    [{'net_key': 'NET-900002', 'interval_months': 60, 'expected_months': 54.0}]

## Source columns

- `service.maintenance_plan.net_key`
- `service.maintenance_plan.plan_no`
- `service.maintenance_plan.plan_type`
- `service.maintenance_plan.interval_months`
- `service.maintenance_plan.valid_from`
- `gis.grid_element.net_key`
- `gis.grid_element.condition_class`
- `gis.grid_element.element_type`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `policy.grid.inspection_cycle_months.A`
- `policy.grid.inspection_cycle_months.B`
- `policy.grid.inspection_cycle_months.C`
- `policy.grid.inspection_cycle_months.D`
- `policy.grid.inspection_cycle_months.E`
- `policy.grid.inspection_type_multiplier.pipe_segment`
- `policy.grid.inspection_type_multiplier.valve`
- `policy.grid.inspection_type_multiplier.heat_exchanger_station`
- `policy.grid.inspection_type_multiplier.cable_section`
- `policy.grid.inspection_type_multiplier.transformer_station`
- `policy.grid.inspection_type_multiplier.substation`
- `policy.grid.inspection_type_multiplier.pump_station`
