# planned_vs_actual_hours

```python
planned_vs_actual_hours(estimate_version: pd.DataFrame, estimate_line: pd.DataFrame, time_entry: pd.DataFrame, *, version_type: str = 'budget', labour_cost_codes: Sequence[int] = (110, 120, 130, 140, 430, 440, 540, 610, 620, 630), context: Context | None = None) -> pd.DataFrame
```

Use this when you need the plan hours of each project against the hours booked in time entries.

Rule: plan hours are the quantity of the lines of the labour cost codes in the estimate version of version_type (default budget), one version per project and type. actual_hours are the booked hours of the project; negative booked hours are kept as corrections. ratio is actual over plan and empty without plan hours. The labour cost codes are proposed (a fact is needed). Bad input raises instead of giving a quiet zero.

## Args

estimate_version: Estimate version frame (projects.estimate_version) with prj_key, estimate_version and type.
estimate_line: Estimate line frame (projects.estimate_line) with prj_key, estimate_version, cst_key (CST-<digits>) and quantity.
time_entry: Time entry frame (projects.time_entry) with prj_key and hours.
version_type: The estimate type to read. Default "budget".
labour_cost_codes: Whole cost code numbers that count as labour. Default LABOUR_COST_CODES (proposed).
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: prj_key, plan_hours, actual_hours and ratio, sorted by prj_key.

## Raises

FrameError: a column is missing, a cost key is not CST-<digits>, quantity or hours is not numeric without nulls, no version of version_type exists in a non-empty frame, a project has two versions of that type, a labour line has negative plan hours, a time entry has no prj_key, or labour_cost_codes is not a list of whole numbers.
StageRefusal: a context is given and its stage does not hold the projects source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import planned_vs_actual_hours
>>> version = pd.DataFrame({"prj_key": ["PRJ-1"], "estimate_version": [1], "type": ["budget"]})
>>> line = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "estimate_version": [1, 1], "cst_key": ["CST-110", "CST-500"], "quantity": [100.0, 9.0]})
>>> entry = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "hours": [60.0, 45.0]})
>>> planned_vs_actual_hours(version, line, entry).to_dict("records")
[{'prj_key': 'PRJ-1', 'plan_hours': 100.0, 'actual_hours': 105.0, 'ratio': 1.05}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `projects.estimate_version.prj_key`, `projects.estimate_version.estimate_version`, `projects.estimate_version.type`, `projects.estimate_line.cst_key`, `projects.estimate_line.quantity`, `projects.time_entry.prj_key`, `projects.time_entry.hours`.
