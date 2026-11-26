# org_on

```python
org_on(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, role: pd.DataFrame, grade: pd.DataFrame, department: pd.DataFrame, site: pd.DataFrame, as_of: dt.date) -> pd.DataFrame
```

Use this when you need one frame with each person on a date: term, employee, team, role, grade, department, country and calendar region.

Rule: the terms valid on the date are joined to the employee, team, role, grade, department and site frames. There is no pay column. active follows the hire and leave dates.

## Args

employee: Employee frame (hr.employee) with emp_key, gender, hire_date, leave_date and legal_entity_key.
term: Employment term frame (hr.employment_term).
team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, legal_entity_key and site_key.
role: Role frame (hr.role) with role_key and name.
grade: Grade frame (hr.grade) with gra_key and level.
department: Department frame (hr.department) with dep_key and dep_code.
site: Site frame (hr.site) with site_key and country.
as_of: The date.

## Returns

pandas.DataFrame with one row per person with a term on the date: emp_key, as_of, active, gender, hire_date, leave_date, legal_entity_key, team_key, role_key, role_name, grade_key, level, dep_key, dep_code, site_key, country, region, fte, valid_from and valid_to.

## Raises

FrameError: a frame lacks a column, the employee frame has a person twice, a person employed on the date has no term, or a term valid on the date has no row in the employee frame.
AmbiguousKey: one person has two terms valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import org_on
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "hire_date": ["2020-01-01"], "leave_date": [None], "legal_entity_key": ["LE-01"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "grade_key": ["GRA-1"], "fte": [1.0]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"], "cost_centre_key": ["CC-1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-05"]})
>>> role = pd.DataFrame({"role_key": ["ROLE-1"], "name": ["Pipe fitter"]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-1"], "level": [4]})
>>> department = pd.DataFrame({"dep_key": ["DEP-1"], "dep_code": ["ENG"]})
>>> site = pd.DataFrame({"site_key": ["SITE-05"], "country": ["DE"]})
>>> org_on(employee, term, team, role, grade, department, site, dt.date(2026, 3, 31))[["emp_key", "role_name", "dep_code", "country", "region"]].values.tolist()
[['EMP-000001', 'Pipe fitter', 'ENG', 'DE', 'DE-HH']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.emp_key`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employee.legal_entity_key`, `hr.employment_term.team_key`, `hr.employment_term.role_key`, `hr.employment_term.grade_key`, `hr.employment_term.fte`, `hr.team.dep_key`, `hr.team.site_key`, `hr.role.name`, `hr.grade.level`, `hr.department.dep_code`.
