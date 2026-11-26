# experience_summary

```python
experience_summary(roster: pd.DataFrame, employee: pd.DataFrame | None = None, *, lead_roles: Sequence[str] = ('project manager', 'lead engineer', 'lead designer', 'site manager', 'foreman'), as_of: dt.date | str | pd.Timestamp | None = None, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the hours, projects, roles and lead flag of each person over a roster, ranked by hours.

Rule: hours are the total over both bases (time_entries and roster) as the generator truth sums them, kept apart in hours_time_entries and hours_roster (legacy roster hours are estimates). Ranked by hours, high first, then emp_key (hours equal to six decimals tie); the lead roles are proposed. With as_of a leaver is a person whose leave_date is before it, strictly: on the leave date itself the person is still there. Without as_of a leaver is any person with a leave date, also a future one, so a staffing decision must use the date specific status of org.status_on and never this flag. A person missing from the employee frame has leaver false and no leave date.

## Args

roster: Roster frame with prj_key, emp_key, project_role, hours_total and basis (time_entries or roster), and optional legacy.
employee: Optional employee frame (hr.employee) with emp_key and leave_date; adds leave_date and leaver.
lead_roles: Project roles that make a person a lead. Default LEAD_ROLES (proposed).
as_of: Optional date for the leaver flag.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: rank, emp_key, hours, hours_time_entries, hours_roster, n_projects, projects, roles, lead_roles, is_lead, legacy_projects (when the roster has legacy), and leave_date and leaver (with an employee frame).

## Raises

FrameError: a column is missing, hours_total is not numeric or has nulls, a key or role is null, basis is neither time_entries nor roster, legacy is not True or False, or employee has duplicate emp_key values.
StageRefusal: a context is given and its stage does not hold the projects source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import experience_summary
>>> roster = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-1"], "emp_key": ["EMP-000001", "EMP-000001", "EMP-000002"],
...                        "project_role": ["project manager", "electrician", "electrician"],
...                        "hours_total": [100.0, 50.0, 80.0], "basis": ["time_entries", "roster", "time_entries"]})
>>> experience_summary(roster)[["rank", "emp_key", "hours", "n_projects", "is_lead"]].to_dict("records")
[{'rank': 1, 'emp_key': 'EMP-000001', 'hours': 150.0, 'n_projects': 2, 'is_lead': True}, {'rank': 2, 'emp_key': 'EMP-000002', 'hours': 80.0, 'n_projects': 1, 'is_lead': False}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `projects.project_role.emp_key`, `projects.project_role.prj_key`, `projects.project_role.project_role`, `projects.project_role.hours_total`, `projects.project_role.basis`, `hr.employee.leave_date`.
