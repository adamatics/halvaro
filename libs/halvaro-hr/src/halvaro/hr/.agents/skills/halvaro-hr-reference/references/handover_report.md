# handover_report

```python
handover_report(allocation: pd.DataFrame, leave_record: pd.DataFrame, *, leave_types: Sequence[str] | str | PolicyDefault = policy:policy.staffing.unavailable_leave_types, lookback_days: int = 7, replacement_days: int = 7, crew_plan: pd.DataFrame | None = None) -> pd.DataFrame
```

Use this when you need, around each long leave, the allocations that ended or still run at its start, the people who replace the absent person on the project, and where the person returns.

Rule: long leaves are the rows of leave_types (default the fact policy.staffing.unavailable_leave_types, status proposed; the frame then carries attrs["policy_status"]); duplicate leave rows are reported once. Per person and leave the kinds are: ends_before_leave (own allocations that end in the lookback_days before the leave starts); overlaps_leave (own allocations running on the leave start day: they end on or after it or are open); replacement (allocations of other people on the projects where the person has an ends_before_leave or overlaps_leave allocation, and only those projects, that start from the leave start to replacement_days later, so the first working day after a weekend leave start is covered); planned_return (per project the first own allocation that starts after the leave ended and before the person's next long leave; none while the leave has no end). Lookback and replacement days default to 7 (proposed).
crew_plan (optional, not a registered source, so the function stays day 1): its rows of the person that start after the leave ended (and before the next long leave) are planned_return candidates too, with start and end from planned_start and planned_end (a null planned_end is open); per project the earliest start wins and an allocation wins a tie. Plan rows that start inside the leave (from the leave start to the leave end, both inclusive; any day from the start when the leave has no end) are reported as plan_during_leave, last per leave: the plan seats a person who is on leave, a conflict hr.allocation cannot show. Without crew_plan there are no plan_during_leave rows and no source column.

## Args

allocation: Allocation rows (hr.allocation) with emp_key, prj_key, start, end and percent; an empty end is open.
leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
leave_types: The leave types that count as long leave (a list or one type).
lookback_days: How many days before the leave start an ending allocation still counts (proposed 7).
replacement_days: How many days after the leave start a replacing allocation may start (proposed 7).
crew_plan: Optional crew plan (competence.crew_plan) with emp_key, prj_key, planned_start, planned_end and percent; None leaves it out.

## Returns

pandas.DataFrame with leave_emp_key, leave_type, leave_start, leave_end, kind, prj_key, emp_key, percent, start and end (and source, allocation or crew_plan, when crew_plan is given), ordered by leave, kind (in the order above), project, start and emp_key.

## Raises

FrameError: a frame lacks a column, lookback_days or replacement_days is not a whole number of zero or more, leave_types is None or the default lists no type, a long leave has no start or ends before it starts, an allocation or plan row has no start, ends before it starts or is a duplicate (a repeated alc_key, or all columns identical), or a date column is not a date.
FactNotFound: the default leave types are used and the fact is not in the snapshot.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import handover_report
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000001"], "prj_key": ["PRJ-001", "PRJ-001", "PRJ-002"],
...                            "start": ["2026-01-01", "2026-03-03", "2026-05-04"], "end": [None, None, None], "percent": [100, 100, 100]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_type": ["extended_leave"], "start": ["2026-03-02"], "end": ["2026-04-30"]})
>>> out = handover_report(allocation, leave, leave_types=["extended_leave"])
>>> out[["leave_emp_key", "kind", "prj_key", "emp_key"]].to_dict("records")
[{'leave_emp_key': 'EMP-000001', 'kind': 'overlaps_leave', 'prj_key': 'PRJ-001', 'emp_key': 'EMP-000001'}, {'leave_emp_key': 'EMP-000001', 'kind': 'replacement', 'prj_key': 'PRJ-001', 'emp_key': 'EMP-000002'}, {'leave_emp_key': 'EMP-000001', 'kind': 'planned_return', 'prj_key': 'PRJ-002', 'emp_key': 'EMP-000001'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.unavailable_leave_types`.

Source columns: `hr.allocation.emp_key`, `hr.allocation.prj_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`, `hr.leave_record.emp_key`, `hr.leave_record.leave_type`, `hr.leave_record.start`, `hr.leave_record.end`.
