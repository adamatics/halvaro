# project_crew

```python
project_crew(allocation: pd.DataFrame, crew_plan: pd.DataFrame, prj_key: str, as_of: dt.date, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the people on a project on a date: the allocations that cover the date, or the crew plan when the project has no allocation yet.

Rule: allocations that cover the date (an empty end is open). When the project has no allocation row at all, the crew plan rows that cover the date are used; a project with allocations that none cover the date has an empty crew. One row per person, the larger percent when a person has several.

## Args

allocation: Allocation frame (hr.allocation) with emp_key, prj_key, start, end and percent.
crew_plan: Crew plan frame (competence.crew_plan) with prj_key, emp_key, planned_start, planned_end and percent.
prj_key: The project.
as_of: The date.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame with emp_key, percent and source (allocation or crew_plan).

## Raises

FrameError: a frame lacks a column or an allocation of the project has no start.
PeriodError: as_of is not a valid date.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import project_crew
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "prj_key": ["PRJ-1", "PRJ-1"], "start": ["2026-01-01", "2026-01-01"], "end": ["2026-06-30", None], "percent": [100, 50]})
>>> plan = pd.DataFrame({"prj_key": ["PRJ-2"], "emp_key": ["EMP-000003"], "planned_start": ["2026-01-01"], "planned_end": [None], "percent": [100]})
>>> project_crew(allocation, plan, "PRJ-1", dt.date(2026, 3, 1))[["emp_key", "percent", "source"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'percent': 100, 'source': 'allocation'}, {'emp_key': 'EMP-000002', 'percent': 50, 'source': 'allocation'}]
>>> project_crew(allocation, plan, "PRJ-2", dt.date(2026, 3, 1))["source"].tolist()
['crew_plan']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.allocation.emp_key`, `hr.allocation.prj_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`, `competence.crew_plan.prj_key`, `competence.crew_plan.emp_key`, `competence.crew_plan.planned_start`, `competence.crew_plan.planned_end`, `competence.crew_plan.percent`.
