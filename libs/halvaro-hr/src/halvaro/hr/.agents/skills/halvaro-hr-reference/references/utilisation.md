# utilisation

```python
utilisation(time_entry: pd.DataFrame, availability: pd.DataFrame, employment_term: pd.DataFrame, team: pd.DataFrame, department: pd.DataFrame, *, project_roles: Sequence[str], before: dt.date | str | pd.Timestamp | None = None, context: Context | None = None) -> pd.DataFrame
```

Use this when you need project hours over availability by team and by department, for the people who hold a project role.

Rule: the basis is proposed (policy.staffing.utilisation_basis): project hours over availability net of leave and public holidays, limited to the project roles. Per person and period of an availability_hours frame, the team and role are those of the employment term valid at the middle of the period (start plus half the span, the time of day dropped). The person counts when the role key is in project_roles. Project hours are the time entries of the person with work_date inside the period, both ends included; negative hours are corrections and are summed. With before only periods that start before that date count. Hours of persons or periods outside the availability frame are not counted.

## Args

time_entry: Time entry frame (projects.time_entry) with emp_key, work_date and hours.
availability: The output of availability_hours: emp_key, period_start, period_end and hours (availability).
employment_term: Employment term frame (hr.employment_term) with emp_key, valid_from, valid_to, team_key and role_key.
team: Team frame (hr.team) with team_key and dep_key.
department: Department frame (hr.department) with dep_key and dep_code.
project_roles: The role keys that count as project roles.
before: Optional date; only periods that start before it count.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: level (team or department), key (team_key or dep_code), availability_hours, project_hours, utilisation (empty when availability is zero) and n_persons.

## Raises

FrameError: a frame lacks a column, project_roles is empty, a team or department key is duplicated, availability has a reversed, duplicate or overlapping period, two terms are valid at the middle of a period, or a team or department is missing.
StageRefusal: a context is given and its stage does not hold the projects source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import utilisation
>>> entries = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "work_date": ["2026-03-02", "2026-03-03"], "hours": [7.5, 6.0]})
>>> availability = pd.DataFrame({"emp_key": ["EMP-000001"], "period_start": ["2026-03-01"], "period_end": ["2026-03-31"], "hours": [150.0]})
>>> terms = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2025-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"]})
>>> teams = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"]})
>>> departments = pd.DataFrame({"dep_key": ["DEP-1"], "dep_code": ["ENG"]})
>>> result = utilisation(entries, availability, terms, teams, departments, project_roles=["ROLE-1"])
>>> result[["level", "key", "project_hours", "n_persons"]].to_dict("records")
[{'level': 'team', 'key': 'TEAM-01', 'project_hours': 13.5, 'n_persons': 1}, {'level': 'department', 'key': 'ENG', 'project_hours': 13.5, 'n_persons': 1}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `projects.time_entry.emp_key`, `projects.time_entry.work_date`, `projects.time_entry.hours`, `hr.employment_term.team_key`, `hr.employment_term.role_key`, `hr.team.dep_key`, `hr.department.dep_code`.
