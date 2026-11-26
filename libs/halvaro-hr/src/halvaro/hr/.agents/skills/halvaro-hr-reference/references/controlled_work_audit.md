# controlled_work_audit

```python
controlled_work_audit(time_entry: pd.DataFrame, allocation: pd.DataFrame, project: pd.DataFrame, employment_term: pd.DataFrame, role: pd.DataFrame, employee: pd.DataFrame, cert: pd.DataFrame, rules: pd.DataFrame, as_of: dt.date | str | pd.Timestamp, *, role_groups: Mapping[str, Sequence[str]] | None = None, first_term_from_hire: bool = True, time_entries_until_as_of: bool = False, context: Context | None = None) -> ControlledAudit
```

Use this when you need the time entries and allocation days of controlled work that have no valid certificate on the day.

Rule: a row is controlled by a rule when the person's role (the employment term valid on the row's date, role name from hr.role) is in the rule's roles (role names, keys of role_groups, or '*' for every role; an unknown name raises), the person's legal entity equals the rule's entity (empty: any), the project type is in the rule's project_types (empty or 'any': every type) and, for time entries, the cost code is in the rule's cst (numbers such as 430 or 'CST-430'; empty or 'any': every code). A certificate is valid from issued to expires, both inclusive, an empty expires is open; a time of day in a date is dropped.
Kinds: time_entry (audited whatever its date, also after as_of, unless time_entries_until_as_of is true); allocation_start (the start day of a stint that starts on or before as_of); allocation_end (the end day, never later than as_of; an open stint counts as ending on as_of, so one that starts after it has only its planned start); allocation_planned (the start day of a stint that starts after as_of and the end day of one that ends after it: planned days, so a certificate that expires before them is a forward warning, not a breach that has happened). Allocations use only rules with allocation true, whatever the cost code, and take the role at the stint's start for every check of the stint.
first_term_from_hire (proposed default, MEDIUM): the first employment term of a person counts from the hire date (a later hire date never moves the start later); with false, rows before the first term are unchecked. Keys of any dtype are read as keys, so an empty frame is simply empty; an integer cost code such as 430 is read as 'CST-430'. An audit with no violations is clean only when the unchecked counts are zero too.

## Args

time_entry: Time entries (projects.time_entry) with emp_key, work_date, prj_key and cst_key.
allocation: Allocation stints (hr.allocation) with emp_key, prj_key, start and end; an empty end is open.
project: Projects (projects.project) with prj_key and type, one row per project.
employment_term: Employment terms (hr.employment_term) with emp_key, valid_from, valid_to and role_key; an empty valid_to is open.
role: Roles (hr.role) with role_key and name, one row per role.
employee: Employees (hr.employee) with emp_key, legal_entity_key and hire_date, one row per person.
cert: Certificates (competence.certification_held) with emp_key, qual_key, issued and expires.
rules: The controlled rules with rule_id, qual_key, roles, entity, project_types, cst and allocation (true: the rule also applies to allocations; 0 and 1 are read as false and true).
as_of: The audit date (a date, a timestamp or an ISO date text); dates must be dates, not numbers such as 20250601.
role_groups: Names that stand for several roles in the rules' roles; None means no groups.
first_term_from_hire: Whether the first term of a person counts from the hire date (see the Rule).
time_entries_until_as_of: True leaves out the time entries dated after as_of.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

ControlledAudit, a named tuple of three pandas.DataFrame. violations: kind, rule_id, emp_key, prj_key, work_date, cst_key (null for allocations), qual_key and planned (true for allocation_planned), one row per checked day without a valid certificate, sorted by kind (time_entry, allocation_start, allocation_end, allocation_planned), rule_id, emp_key, work_date and prj_key. checked: kind, rule_id, checked (the (row, rule) pairs checked; a row that two rules control counts twice) and violations among them. unchecked: kind, unchecked (no employment term on the date, so no role), no_project_type, no_cst_key and no_entity (rows with a role a rule names that lack the project type, cost code or legal entity that rule needs; a person with no hr.employee row counts under no_entity); a row counts once per column however many rules it escapes.

## Raises

FrameError: a frame lacks a column, role_groups is not a mapping or a group is not a role name or a list of them, a key is not unique in project, role or employee, a time entry or allocation names a project that is not in project, a term has an unknown role_key, two terms are valid on the same day for a person, a term, stint or certificate ends before it starts or expires before it was issued, a rule has no roles, an unknown role, a duplicate rule_id, a cost code that is not a whole number or 'CST-n' or an allocation flag that is not true or false, or a date column holds numbers, a time zone, nulls where a date is needed or text that is not a date.
PeriodError: as_of is not a date.
StageRefusal: a context is given and its stage does not hold the projects or competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import controlled_work_audit
>>> time_entry = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "work_date": ["2026-03-10", "2026-06-10"], "prj_key": ["PRJ-001"] * 2, "cst_key": [430, 430]})
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001"], "prj_key": ["PRJ-001"], "start": ["2026-02-01"], "end": [None]})
>>> project = pd.DataFrame({"prj_key": ["PRJ-001"], "type": ["install"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2025-01-01"], "valid_to": [None], "role_key": ["ROLE-01"]})
>>> role = pd.DataFrame({"role_key": ["ROLE-01"], "name": ["technician"]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "legal_entity_key": ["LE-01"], "hire_date": ["2025-01-01"]})
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "issued": ["2026-01-01"], "expires": ["2026-05-31"]})
>>> rules = pd.DataFrame({"rule_id": ["R1"], "qual_key": ["QUAL-01"], "roles": [["technician"]], "entity": [None], "project_types": ["any"], "cst": [430], "allocation": [True]})
>>> audit = controlled_work_audit(time_entry, allocation, project, term, role, employee, cert, rules, "2026-06-30")
>>> audit.violations[["kind", "rule_id", "emp_key", "work_date"]].astype(str).to_dict("records")
[{'kind': 'time_entry', 'rule_id': 'R1', 'emp_key': 'EMP-000001', 'work_date': '2026-06-10'}, {'kind': 'allocation_end', 'rule_id': 'R1', 'emp_key': 'EMP-000001', 'work_date': '2026-06-30'}]
>>> audit.checked.to_dict("records")[0]
{'kind': 'time_entry', 'rule_id': 'R1', 'checked': 2, 'violations': 1}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `projects.time_entry.emp_key`, `projects.time_entry.work_date`, `projects.time_entry.prj_key`, `projects.time_entry.cst_key`, `hr.allocation.emp_key`, `hr.allocation.prj_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.employment_term.role_key`, `hr.role.name`, `hr.employee.legal_entity_key`, `hr.employee.hire_date`, `projects.project.type`, `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`.
