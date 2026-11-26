# Reference of the other functions of halvaro-hr, flat reference

# adjusted_gap

```python
adjusted_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None, extra_controls: str | Sequence[str] = ()) -> dict[str, Any]
```

Use this when you need the pay difference between women and men after taking tenure, legal entity and grade into account, with its standard error.

Rule: an OLS of ln(rate_dkk) on a dummy for women, tenure, one indicator per legal entity and one per grade; the gap is (1 minus exp(b)) times 100 in percent, positive when women are paid less. The result is suppressed (NaN, suppressed True) below minimum_group people per gender (proposed 8), when the sample is too small for the model, and for nothing else. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key and level.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.
extra_controls: Names of numeric columns added to the model, for instance education_rank from with_education. Default none.

## Returns

dict: n_women, n_men, adjusted_gap_pct and adjusted_gap_se_pct (percent, NaN when suppressed), suppressed (bool) and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, an extra control is not numeric, infinite, missing, repeated or already in the model, or the rate, entity, grade or tenure values are missing or not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import adjusted_gap
>>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6})
>>> result = adjusted_gap(people, minimum_group=3, context=access)
>>> result["n_women"], result["n_men"], result["suppressed"], round(result["adjusted_gap_pct"], 1)
(3, 3, False, 9.1)
>>> adjusted_gap(people, context=access)["suppressed"]
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.

# allocation_hours

```python
allocation_hours(allocation: pd.DataFrame, employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, as_of: dt.date | str | pd.Timestamp, *, hours_per_day: float = 7.4, leave_types: Sequence[str] | None = None) -> pd.DataFrame
```

Use this when you need the hours that each allocation stint stands for, split into the hours up to a date and the hours after it.

Rule: the percent of the stint divided by 100 times the availability hours of the person inside the stint (the rules of availability_hours). hours_before counts stint days up to and including the date, hours_after the days after it; after_now says that the stint has days after the date.

## Args

allocation: Allocation frame (hr.allocation) with emp_key, prj_key, start, end and percent; start and end must be dates.
employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
employment_term: Employment term frame (hr.employment_term).
leave_record: Leave frame (hr.leave_record).
team: Team frame (hr.team) with team_key and site_key.
as_of: The date that splits realised from planned hours.
hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
leave_types: The leave types that count as leave; None means all.

## Returns

pandas.DataFrame: the columns of the allocation frame plus availability_hours, hours, hours_before, hours_after, no_term_days and after_now.

## Raises

FrameError: a frame lacks a column, a stint has no start or end, a person of the allocations is not in hr.employee, or hours_per_day is not above zero and at most 24.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import allocation_hours
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001"], "prj_key": ["PRJ-1"], "start": ["2026-03-02"], "end": ["2026-03-06"], "percent": [50]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
>>> result = allocation_hours(allocation, employee, term, leave, team, dt.date(2026, 3, 4))
>>> result[["availability_hours", "hours", "hours_before", "hours_after", "after_now"]].to_dict("records")
[{'availability_hours': 29.6, 'hours': 14.8, 'hours_before': 7.4, 'hours_after': 7.4, 'after_now': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.allocation.emp_key`, `hr.allocation.prj_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.leave_record.start`, `hr.leave_record.end`.

# allocation_load

```python
allocation_load(allocation: pd.DataFrame, limit: float | PolicyDefault = policy:policy.staffing.max_allocation_percent) -> pd.DataFrame
```

Use this when you need to see how loaded each person is over time: the allocation percents of all projects added up per day, as segments of constant load.

Rule: the percents of the allocations that cover a day are summed per person; neighbouring days with the same sum form one segment; days with no load are not listed. A load above the limit is flagged. The default limit is the fact policy.staffing.max_allocation_percent (status proposed); the frame then carries attrs["policy_status"]. An allocation with no end is open: its segment has an empty end.

## Args

allocation: Allocation frame (hr.allocation) with emp_key, start, end and percent (numbers of zero or more, no nulls).
limit: The largest accepted load in percent per person per day. Default the fact.

## Returns

pandas.DataFrame with emp_key, start, end (included), load and over_limit, sorted by person and start.

## Raises

FrameError: limit is not a number, an allocation has no emp_key or start, percent is not numeric and zero or more, an allocation ends before it starts, or an end date is in the year 2200 or later.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import allocation_load
>>> allocation = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "prj_key": ["PRJ-1", "PRJ-2"], "start": ["2026-01-01", "2026-01-01"],
...                            "end": ["2026-01-31", "2026-01-15"], "percent": [60, 50]})
>>> allocation_load(allocation, limit=100)[["start", "end", "load", "over_limit"]].astype(str).values.tolist()
[['2026-01-01', '2026-01-15', '110.0', 'True'], ['2026-01-16', '2026-01-31', '60.0', 'False']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.max_allocation_percent`.

Source columns: `hr.allocation.emp_key`, `hr.allocation.start`, `hr.allocation.end`, `hr.allocation.percent`.

# availability_hours

```python
availability_hours(employee: pd.DataFrame, employment_term: pd.DataFrame, leave_record: pd.DataFrame, team: pd.DataFrame, periods: Sequence[tuple[dt.date | str, dt.date | str]], *, hours_per_day: float = 7.4, leave_types: Sequence[str] | None = None) -> pd.DataFrame
```

Use this when you need the hours each person can work in each period: employed working days of the region, less leave, times the fte, times the hours of a day.

Rule: per period (a pair of dates, both included) the days on which the person is employed and which are working days of the region of the team's site; leave days are taken off; the rest times the fte of the term valid that day and times hours_per_day (PROPOSED default, world.staffing.hours_per_day). A person with no term on a day gives no hours there.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.
employment_term: Employment term frame (hr.employment_term) with emp_key, valid_from, valid_to, team_key and fte.
leave_record: Leave frame (hr.leave_record) with emp_key, start, end and leave_type; an empty end is open.
team: Team frame (hr.team) with team_key and site_key.
periods: A list of (start, end) date pairs, both days included.
hours_per_day: Hours of a full time day. Default 7.4 (PROPOSED).
leave_types: The leave types that count as leave; None means all.

## Returns

pandas.DataFrame with emp_key, period_start, period_end, region, working_days, leave_days, net_days and hours, sorted by person and period; a person with no employed working day in a period has no row.

## Raises

FrameError: a frame lacks a column, a date is not a date, hours_per_day is not above zero and at most 24, or a period is not a pair of dates.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import availability_hours
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": ["2020-01-01"], "valid_to": [None], "team_key": ["TEAM-01"], "role_key": ["ROLE-1"], "fte": [1.0]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "start": ["2026-03-04"], "end": ["2026-03-04"], "leave_type": ["sick"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "site_key": ["SITE-01"], "dep_key": ["DEP-1"]})
>>> week = [(dt.date(2026, 3, 2), dt.date(2026, 3, 6))]
>>> availability_hours(employee, term, leave, team, week)[["working_days", "leave_days", "net_days", "hours"]].to_dict("records")
[{'working_days': 5, 'leave_days': 1, 'net_days': 4, 'hours': 29.6}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.employment_term.team_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.leave_record.start`, `hr.leave_record.end`, `hr.leave_record.leave_type`, `hr.team.site_key`.

# band_position

```python
band_position(frame: pd.DataFrame, grade: pd.DataFrame, *, context: Context, as_of: dt.date | None = None, bands_year: int = 2026) -> pd.DataFrame
```

Use this when you want to see where each person's pay lies in the band of the grade, in the currency of the person's term.

Rule: vs_midpoint is the rate over the band midpoint (the compa ratio); position_in_band is (rate less band minimum) over (maximum less minimum), so below 0 or above 1 is outside the band; in_band says whether it is inside. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning says that the position is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with emp_key, gender (only F and M rows count), grade_key, currency, rate_local and compa.
grade: Grade frame (hr.grade) with gra_key and the band limits in DKK and EUR.
context: The caller; the role must be allowed to read pay.
as_of: The date the position is read at. Optional.
bands_year: The year the bands are set at. Default 2026 (proposed).

## Returns

pandas.DataFrame with emp_key, grade_key, currency, rate_local, band_min, band_mid, band_max, vs_midpoint, position_in_band and in_band.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, a grade is held twice or not at all, a term is not in DKK or EUR, or a band maximum is not above its minimum.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import band_position
>>> people = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "grade_key": ["GRA-4"], "currency": ["DKK"], "rate_local": [45000.0], "compa": [1.0]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-4"], "level": [4], "band_min_dkk": [40000.0], "band_max_dkk": [50000.0], "band_min_eur": [5000.0], "band_max_eur": [6700.0]})
>>> band_position(people, grade, context=access)[["band_mid", "vs_midpoint", "position_in_band", "in_band"]].values.tolist()
[[45000.0, 1.0, 0.5, True]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.

# booked_renewals

```python
booked_renewals(attendance: pd.DataFrame, event: pd.DataFrame, as_of: dt.date, data_releases: Mapping[str, pd.DataFrame], *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the seats booked on training courses that start after the release date, to see who will renew a certificate in time.

Rule: bookings carry no booking date, so the function only answers for the release date itself (data_now of the passed data_release frames); another date is refused. Only attendance with the status booked counts; any other status (for example cancelled) does not.

## Args

attendance: Attendance frame (competence.training_attendance) with event_no, emp_key and status.
event: Training event frame (competence.training_event) with event_no, qual_key, date, end_date, capacity, seats_taken, country and location_site_key.
as_of: The date; it must be the release date.
data_releases: A mapping of source name to its data_release frame, for example {"competence": frame}.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame with emp_key, qual_key, event_no, course_date, course_end, capacity, seats_taken, free_seats, country and location_site_key.

## Raises

FrameError: data_releases is not a mapping, a frame lacks a column, event_no is duplicated, a booked seat is listed twice or names an event that is missing, or a booked course does not start after the date.
PeriodError: as_of is not the release date.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import booked_renewals
>>> release = pd.DataFrame({"release": ["r1"], "now": ["2026-03-31"], "generated_at": ["2026-04-01"], "base_seed": [1], "increment": [0]})
>>> attendance = pd.DataFrame({"event_no": [7, 7], "emp_key": ["EMP-000001", "EMP-000002"], "status": ["booked", "cancelled"]})
>>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-05-10"], "end_date": ["2026-05-11"], "capacity": [10], "seats_taken": [4], "country": ["DK"], "location_site_key": ["SITE-01"]})
>>> booked_renewals(attendance, event, dt.date(2026, 3, 31), {"competence": release})[["emp_key", "qual_key", "free_seats"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'qual_key': 'QUAL-01', 'free_seats': 6}]
>>> booked_renewals(attendance, event, dt.date(2026, 3, 1), {"competence": release})
Traceback (most recent call last):
...
halvaro.core.errors.PeriodError: booked renewals are only known at the release date 2026-03-31: bookings have no booking date, so 2026-03-01 cannot be rebuilt
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.training_attendance.status`, `competence.training_attendance.event_no`, `competence.training_attendance.emp_key`, `competence.training_event.date`, `competence.training_event.end_date`, `competence.training_event.qual_key`, `competence.training_event.capacity`, `competence.training_event.seats_taken`, `competence.training_event.country`, `competence.training_event.location_site_key`, `competence.data_release.now`.

# build_username_index

```python
build_username_index(username_history: pd.DataFrame, shared_account: pd.DataFrame) -> pd.DataFrame
```

Use this when you need one effective dated list of usernames and pool accounts with their holders.

Rule: usernames of employees (kind employee) and pool accounts of teams (kind pool) are put in one frame; a null valid_to is open. The result is sorted by username and start date.

## Args

username_history: Frame hr.username_history with username, emp_key, valid_from and valid_to.
shared_account: Frame hr.shared_account with account_name, team_key, valid_from and valid_to.

## Returns

pandas.DataFrame with username, kind, holder, emp_key, team_key, valid_from and valid_to.

## Raises

FrameError: a column is missing, a row has no username, holder or start date, or a row ends before it starts.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import build_username_index
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> build_username_index(history, pool)[["username", "kind", "holder"]].to_dict("records")
[{'username': 'ab', 'kind': 'employee', 'holder': 'EMP-000001'}, {'username': 'ops-pool', 'kind': 'pool', 'holder': 'TEAM-01'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.username`, `hr.username_history.emp_key`, `hr.username_history.valid_from`, `hr.username_history.valid_to`, `hr.shared_account.account_name`, `hr.shared_account.team_key`, `hr.shared_account.valid_from`, `hr.shared_account.valid_to`.

# cert_intervals

```python
cert_intervals(cert: pd.DataFrame, *, context: Context | None = None) -> dict[tuple[str, str], list[tuple[Any, Any]]]
```

Use this when you check coverage for many projects and want to build the validity intervals of the certificates once.

Rule: every certificate is an interval from issued to expires (an empty expires is open); the intervals of one person and qualification are listed together. Pass the result to coverage_gap(..., intervals=...) to avoid building it again.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

dict: {(emp_key, qual_key): [(issued, expires), ...]} with NaT for an open end.

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import cert_intervals
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "issued": ["2024-01-01"], "expires": [None]})
>>> intervals = cert_intervals(cert)
>>> list(intervals), len(intervals[("EMP-000001", "QUAL-01")])
([('EMP-000001', 'QUAL-01')], 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`.

# cert_status_on

```python
cert_status_on(cert: pd.DataFrame, as_of: dt.date, stored_at: dt.date | None = None, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the status of every certificate on a date, worked out from the dates and not read from the stored status.

Rule: not_yet_valid before issued, expired after expires, superseded when a strictly later issue of the same person and qualification is issued and still in force, otherwise valid. matches_stored is set only when as_of equals stored_at, the date the stored status was computed for.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires and status.
as_of: The date.
stored_at: The date the stored status was computed for (the release date). Optional.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: one row per certificate with emp_key, qual_key, issued, expires, as_of, status_on, stored_status and matches_stored (null unless stored_at equals as_of).

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import cert_status_on
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2024-01-01"],
...                      "expires": ["2023-12-31", "2026-12-31"], "status": ["expired", "valid"]})
>>> cert_status_on(cert, dt.date(2025, 6, 1))["status_on"].tolist()
['expired', 'valid']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.certification_held.status`.

# check_term_contiguity

```python
check_term_contiguity(term: pd.DataFrame, employee: pd.DataFrame) -> pd.DataFrame
```

Use this when you check the employment term history of every person for gaps, overlaps and other breaks in the dating.

Rule: per person the terms are ordered by valid_from. The rules are reversed, gap, overlap, two_open, open_not_last, null_key, no_employee, hire_missing, leave_before_hire, no_terms, first_row (the first term does not start on the expected day: the hire date, or the start of the data window when the person was hired before it and still works), open_row and last_row_not_leave_date.

## Args

term: Employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; empty when the history is clean.

## Raises

FrameError: a frame lacks a column.
FactNotFound: the fact for the start of the data window is not known.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import check_term_contiguity
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "valid_from": ["2024-01-01", "2025-03-01"], "valid_to": ["2024-12-31", None]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2024-01-01"], "leave_date": [None]})
>>> check_term_contiguity(term, employee)["rule"].tolist()
['gap']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.window_start`.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.employee.hire_date`, `hr.employee.leave_date`.

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

# cover_candidates

```python
cover_candidates(skill_latest: pd.DataFrame, org: pd.DataFrame, cert: pd.DataFrame, qualification: pd.DataFrame, event: pd.DataFrame, crew_plan: pd.DataFrame, leave_record: pd.DataFrame, *, qual_key: str, skl_key: str, prj_key: str, crew: Sequence[str] | str | pd.DataFrame, country: str, start: dt.date, now: dt.date, list_level: int | PolicyDefault = policy:policy.certificates.candidate_list_level, plausible_level: int | PolicyDefault = policy:policy.certificates.candidate_plausible_level, leave_days: int | PolicyDefault = policy:policy.certificates.candidate_leave_days, seat_days: int | PolicyDefault = policy:policy.certificates.candidate_seat_days, leave_types: Sequence[str] | str | PolicyDefault = policy:policy.staffing.unavailable_leave_types, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the people who could cover a qualification on a project that starts on a given day, with the reasons that make a candidate less plausible.

Rule: a candidate is active in org (output of org_on on `now`), not in the crew, without a valid certificate of the qualification on the start day (issued to expires inclusive), and has a latest rating of skill skl_key (output of skill_latest) of list_level or more. `plausible` is true when no reason applies. Reasons: skill_level_below_<plausible_level>; country_scope_mismatch (the qualification is scoped to DK or DE and the person's country differs) or other_country (otherwise, the person is not in the project country); prerequisite_missing (the prerequisite qualification is not valid on the start day); long_leave (a leave of an unavailable type that starts no later than leave_days after the start day and does not end before it); planned_on_other_project (the crew plan has 100 percent or more on another project; the dates of the plan rows are not read); no_seat_before_start_plus_<seat_days>d (no course of the qualification after `now`, up to the start day plus seat_days, with a free seat in the person's country). The four numbers default to the facts policy.certificates.candidate_list_level, candidate_plausible_level, candidate_leave_days and candidate_seat_days, and the leave types to policy.staffing.unavailable_leave_types (all status proposed; the frame then carries attrs["policy_status"]). Sorted plausible first, then skill level (high first), then emp_key.

## Args

skill_latest: Output of skill_latest with emp_key, skl_key and level, one row per person and skill.
org: Output of org_on with emp_key, active, country, role_name and legal_entity_key, one row per person.
cert: Certificate frame (competence.certification_held) with emp_key, qual_key, issued and expires.
qualification: Qualifications (competence.qualification) with qual_key, prerequisite_qual_key and country_scope; qual_key must appear exactly once.
event: Training events (competence.training_event) with event_no, qual_key, date, capacity, seats_taken and country.
crew_plan: Crew plan rows (competence.crew_plan) with prj_key, emp_key and percent.
leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
qual_key: The qualification to cover.
skl_key: The skill whose latest rating ranks the candidates.
prj_key: The project; its crew plan rows do not count as planned elsewhere.
crew: The people already on the project: a list of emp_key, one emp_key, or the project_crew frame with an emp_key column.
country: The project country.
start: The project start day.
now: The data date; courses must start after it.
list_level: The lowest skill level that is listed (default the fact policy, proposed).
plausible_level: The lowest skill level that is plausible (default the fact policy, proposed).
leave_days: How many days after the start a leave still counts as long leave (default the fact policy, proposed).
seat_days: How many days after the start a course seat still counts (default the fact policy, proposed).
leave_types: The leave types that count as long leave (a list or one type; default the fact policy, proposed).
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame with emp_key, role_name, legal_entity_key, skill_level, plausible, reasons (a list of the reason texts), next_seat_event and next_seat_date (the first course with a free seat in the person's country, empty when none).

## Raises

FrameError: a frame lacks a column, qualification does not hold qual_key exactly once, org or skill_latest has more than one row for a key, a skill level is null or not a number, the percent of the crew plan is not a number, list_level, plausible_level, leave_days or seat_days is not a number (for example text), leave_types is not a leave type name or a list of them (None, a number), crew is not a list of emp_key, one emp_key or a frame (None, a number), a policy default is not a whole number or lists no leave type, or a date column is not a date.
PeriodError: start or now is not a date without a time zone.
FactNotFound: a default is used and its fact is not in the snapshot.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import cover_candidates
>>> keys = ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"]
>>> skill = pd.DataFrame({"emp_key": keys, "skl_key": ["SKL-01"] * 4, "level": [3, 2, 3, 3]})
>>> org = pd.DataFrame({"emp_key": keys, "active": [True] * 4, "country": ["DK"] * 4, "role_name": ["technician"] * 4, "legal_entity_key": ["LE-01"] * 4})
>>> cert = pd.DataFrame({"emp_key": ["EMP-000004"], "qual_key": ["QUAL-01"], "issued": ["2025-01-01"], "expires": ["2027-12-31"]})
>>> qualification = pd.DataFrame({"qual_key": ["QUAL-01"], "prerequisite_qual_key": [None], "country_scope": [None]})
>>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-08-15"], "capacity": [10], "seats_taken": [4], "country": ["DK"]})
>>> plan = pd.DataFrame({"prj_key": ["PRJ-002"], "emp_key": ["EMP-000002"], "percent": [50]})
>>> leave = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
>>> out = cover_candidates(skill, org, cert, qualification, event, plan, leave, qual_key="QUAL-01", skl_key="SKL-01", prj_key="PRJ-001", crew=["EMP-000003"], country="DK",
...                        start=dt.date(2026, 9, 1), now=dt.date(2026, 6, 30), list_level=2, plausible_level=3, leave_days=90, seat_days=60, leave_types=["extended_leave"])
>>> out[["emp_key", "skill_level", "plausible", "reasons", "next_seat_event"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'skill_level': 3, 'plausible': True, 'reasons': [], 'next_seat_event': 7}, {'emp_key': 'EMP-000002', 'skill_level': 2, 'plausible': False, 'reasons': ['skill_level_below_3'], 'next_seat_event': 7}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.certificates.candidate_leave_days`, `policy.certificates.candidate_list_level`, `policy.certificates.candidate_plausible_level`, `policy.certificates.candidate_seat_days`, `policy.staffing.unavailable_leave_types`.

Source columns: `competence.skill_rating.level`, `competence.qualification.prerequisite_qual_key`, `competence.qualification.country_scope`, `competence.training_event.date`, `competence.training_event.capacity`, `competence.training_event.seats_taken`, `competence.crew_plan.percent`, `hr.leave_record.start`, `hr.leave_record.end`.

# coverage_gap

```python
coverage_gap(requirements: pd.DataFrame, crew: pd.DataFrame, cert: pd.DataFrame, booked: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, *, leave_types: Sequence[str] | None = None, intervals: dict[tuple[str, str], list[tuple[Any, Any]]] | None = None, context: Context | None = None) -> pd.DataFrame
```

Use this when you need, for each requirement of a minimum head count, how many people of a crew hold a valid certificate and are not on leave on a date, and when the gap closes.

Rule: per requirement row with a min_headcount the frame has required, crew_with_cert (valid on record on the date), available (and not on leave on the date), available_incl_booked (a booking covers from its course date, so a course on or before the date counts), gap_on_record and gap_incl_booked (required minus available, at least 0), gap_closes_on (the first date from the given date on when the head count is met counting booked renewals and the end of each leave; empty if never), first_expiry and first_expiry_emp (the earliest expiry among the certificates of crew members that overlap the date; this can belong to a certificate that was renewed since, which is the generator truth kept for parity), first_expiry_renewed_aware and first_expiry_renewed_aware_emp (the earliest expiry after taking, per person and qualification, the latest expiry among the certificates valid on the date; a person with an open certificate never expires and is left out), and the emp_key lists on_leave, without_cert and booked_for_crew. leave_types None counts every leave record as leave, a one day holiday included (the generator rule; org.status_on counts long leave only): pass the unavailable types to count those only. Leave comes from hr.leave_record only.

## Args

requirements: Requirement rows with scope_type, scope_key, qual_key and min_headcount.
crew: Crew frame with emp_key.
cert: Certification frame (competence.certification_held).
booked: The output of booked_renewals (emp_key, qual_key, course_date).
leave_record: Leave frame (hr.leave_record) with emp_key, leave_type, start and end.
as_of: The date.
leave_types: Leave types that count as leave, or None for all.
intervals: The output of cert_intervals(cert), to run it faster in a loop. Optional.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: one row per requirement with a min_headcount, columns as in the rule.

## Raises

FrameError: a frame lacks a column, a crew key is null, or min_headcount is not a whole number of zero or more.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import coverage_gap
>>> requirements = pd.DataFrame({"scope_type": ["project"], "scope_key": ["PRJ-1"], "qual_key": ["QUAL-01"], "min_headcount": [2]})
>>> crew = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01", "QUAL-01"], "issued": ["2025-01-01", "2025-01-01"], "expires": ["2027-12-31", "2026-12-31"]})
>>> booked = pd.DataFrame({"emp_key": pd.Series([], dtype=str), "qual_key": pd.Series([], dtype=str), "course_date": pd.Series([], dtype="datetime64[ns]")})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_type": ["parental"], "start": ["2026-11-01"], "end": ["2027-02-28"]})
>>> gap = coverage_gap(requirements, crew, cert, booked, leave, dt.date(2026, 11, 30), leave_types=["parental"])
>>> gap[["required", "crew_with_cert", "available", "gap_on_record", "on_leave"]].to_dict("records")
[{'required': 2, 'crew_with_cert': 2, 'available': 1, 'gap_on_record': 1, 'on_leave': ['EMP-000001']}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.requirement.qual_key`, `competence.requirement.min_headcount`, `hr.leave_record.emp_key`, `hr.leave_record.start`, `hr.leave_record.end`.

# data_now

```python
data_now(data_releases: Mapping[str, pd.DataFrame], as_of: dt.date | None = None) -> dt.date
```

Use this when you need the date of the data release (the "now" of the data) and want to refuse a date after it.

Rule: all data_release frames passed must agree; the release date is their now. Ledgers and status caches end there, so a later as_of is refused.

## Args

data_releases: A mapping of source name to its data_release frame (one row each), for example {"hr": frame}.
as_of: Optional date to check against the release date.

## Returns

datetime.date: the release date.

## Raises

FrameMissing: no data_release frame was passed.
FrameError: a data_release frame does not have exactly one row.
ReleaseMismatch: the frames name different releases.
PeriodError: as_of is after the release date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import data_now
>>> release = pd.DataFrame({"release": ["r1"], "now": ["2026-03-31"], "generated_at": ["2026-04-01"], "base_seed": [1], "increment": [0]})
>>> data_now({"hr": release})
datetime.date(2026, 3, 31)
>>> data_now({"hr": release}, dt.date(2026, 4, 30))
Traceback (most recent call last):
...
halvaro.core.errors.PeriodError: as_of 2026-04-30 is after the data release date 2026-03-31: holiday ledgers and status caches end there. Use a date up to 2026-03-31.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.data_release.release`, `hr.data_release.now`.

# education_explained_share

```python
education_explained_share(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> dict[str, Any]
```

Use this when you want to know how much of the adjusted pay difference goes away once education is taken into account.

Rule: adjusted_gap without and with education_rank as a further control; explained_pp is gap without minus gap with, in percentage points. Everything is NaN with suppressed True below minimum_group people per gender (proposed 8). n_without_record counts people of the two genders with no education record. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame with education (the output of with_education).
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay and education. Optional keyword.

## Returns

dict: n_women, n_men, gap_without_education_pct, gap_with_education_pct, explained_pp (percent and percentage points), n_without_record and suppressed.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
StageRefusal: the stage does not yet allow the pay and education sources.
FrameError: education_rank or has_education_record is missing, or the frame fails adjusted_gap.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import education_explained_share
>>> people = pd.DataFrame({"gender": ["F", "M"], "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"], "level": [3, 3],
...                         "education_rank": [2, 3], "has_education_record": [True, False]})
>>> result = education_explained_share(people, context=access)
>>> result["suppressed"], result["n_without_record"]
(True, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `competence.education_record.level_rank`.

# education_level

```python
education_level(education: pd.DataFrame, *, context: Context | None = None) -> pd.Series
```

Use this when you need the highest education level of each person from the education records.

Rule: the highest level_rank per person; people without a record are not in the result. The rank scale is in the competence config.

## Args

education: Education record frame (competence.education_record) with emp_key and level_rank (whole numbers, zero or more, no nulls).
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.Series named education_rank, indexed by emp_key and sorted by it.

## Raises

FrameError: a column is missing, a key is null, or level_rank is not a whole number of zero or more.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import education_level
>>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001", "EMP-000002"], "level_rank": [2, 3, 1]})
>>> education_level(education).to_dict()
{'EMP-000001': 3, 'EMP-000002': 1}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.education_record.emp_key`, `competence.education_record.level_rank`.

# executives_on

```python
executives_on(org: pd.DataFrame, role: pd.DataFrame, roles: Sequence[str]) -> Executives
```

Use this when you need the holders of named executive roles on the date of an org_on frame, and the roles that nobody holds.

Rule: the roles are named by the caller (hr keeps no list of executive roles). A holder is a person who is active in the org frame with one of the roles. Leave status is not applied. A vacant role is listed, an unknown role raises.

## Args

org: An org_on frame for one date, with emp_key, as_of, active, role_name, dep_code and team_key.
role: The role frame (hr.role) with the column name.
roles: One role name or a list of distinct role names.

## Returns

Executives: .frame has emp_key, role_name, dep_code and team_key sorted by role and person; .vacant lists the named roles that nobody holds.

## Raises

FrameError: a frame lacks a column or has duplicate column names, no role is named, the roles are not distinct text, a role is not in hr.role, or the org frame is not for exactly one date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import executives_on
>>> org = pd.DataFrame({"emp_key": ["EMP-000001"], "as_of": [pd.Timestamp("2026-06-01")], "active": [True],
...                     "role_name": ["Chief Financial Officer"], "dep_code": ["FIN"], "team_key": ["TEAM-01"]})
>>> role = pd.DataFrame({"name": ["Chief Financial Officer", "Director Service"]})
>>> result = executives_on(org, role, ["Chief Financial Officer", "Director Service"])
>>> result.frame["emp_key"].tolist(), result.vacant
(['EMP-000001'], ('Director Service',))
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.role.name`, `hr.department.dep_code`, `hr.employment_term.team_key`.

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

# expiring

```python
expiring(valid: pd.DataFrame, booked: pd.DataFrame, as_of: dt.date, window_days: int | PolicyDefault = policy:policy.certificates.expiry_warning_days, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the valid certificates that expire soon, with the first booked renewal course after the date and the days a person would be without a valid certificate.

Rule: window_days defaults to the fact policy.certificates.expiry_warning_days (status proposed: the owner has not decided); when the default is used the frame carries attrs["policy_status"] with the fact status. A certificate is listed when it expires on the date or within window_days after it. gap_days is the number of days between the expiry and the first booked course without a valid certificate, 0 when the course is on or before the expiry day, empty when nothing is booked.

## Args

valid: The output of valid_on for the same date.
booked: The output of booked_renewals.
as_of: The date. It must be the date of the valid frame.
window_days: Whole number of days, zero or more, or the default fact.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: emp_key, qual_key, as_of, expires, booked, course_date, event_no, free_seats and gap_days, sorted by expiry, person and qualification.

## Raises

FrameError: a frame lacks a column, window_days is not a whole number of days of zero or more, the valid frame is for another date or has two rows for a person and qualification, or the default fact is not a whole number.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import expiring, valid_on
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01", "QUAL-02"],
...                      "issued": ["2025-01-10", "2024-05-01"], "expires": ["2027-01-09", "2026-12-31"]})
>>> booked = pd.DataFrame({"emp_key": ["EMP-000002"], "qual_key": ["QUAL-02"], "course_date": [pd.Timestamp("2027-01-20")], "event_no": [7], "free_seats": [3]})
>>> soon = expiring(valid_on(cert, dt.date(2026, 11, 30)), booked, dt.date(2026, 11, 30), window_days=60)
>>> soon[["emp_key", "booked", "gap_days"]].to_dict("records")
[{'emp_key': 'EMP-000002', 'booked': True, 'gap_days': 19.0}, {'emp_key': 'EMP-000001', 'booked': False, 'gap_days': nan}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.certificates.expiry_warning_days`.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.expires`.

# expiry_report

```python
expiry_report(cert: pd.DataFrame, booked: pd.DataFrame, event: pd.DataFrame, employee: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, *, expiry_date: dt.date, qual_key: str, holder_qual_key: str | None = None, unavailable_leave_types: Sequence[str] | PolicyDefault = policy:policy.staffing.unavailable_leave_types, context: Context | None = None) -> ExpiryReport
```

Use this when you need the people whose certificate for a qualification runs out on a given date: whether each has a renewal course booked, the free seats, and who is on leave during the course.

Rule: the report covers people who hold qual_key on as_of (valid_on rule, issued to expires inclusive) with a certificate expiring on expiry_date and who have not left (a missing leave_date, or one on or after as_of, counts as current; a person with no hr.employee row is treated as left: not in the frame and counted in former_employees). Only the latest issue per person and qualification counts (valid_on), so a person who holds a later certificate is dropped from the frame and counted in superseded. Per person it takes the earliest booked course of qual_key (from booked_renewals) that starts after as_of, with its free seats; gap_days is 0 for a course starting on the expiry day or the day after, otherwise the course date minus the expiry date minus 1, and empty when nothing is booked; on_leave_at_course is true when a leave of an unavailable type overlaps any day of the course. Courses of the qualification after as_of are listed separately, and the holders of holder_qual_key are listed when it is given. expiry_date and qual_key are supplied by the caller. The unavailable leave types default to the fact policy.staffing.unavailable_leave_types (proposed).

## Args

cert: Certificate frame (competence.certification_held) with emp_key, qual_key, issued and expires; an empty expires is open.
booked: Output of booked_renewals with emp_key, qual_key, course_date, course_end, event_no and free_seats.
event: Training events (competence.training_event) with event_no, qual_key, date, capacity, seats_taken, country and location_site_key.
employee: Employee frame (hr.employee) with emp_key, leave_date and legal_entity_key, one row per person.
leave_record: Leave rows (hr.leave_record) with emp_key, leave_type, start and end; an empty end is open.
as_of: The date on which certificates are read; also the lower bound (exclusive) of the courses that count.
expiry_date: The expiry date the report covers.
qual_key: The qualification the report covers.
holder_qual_key: A second qualification whose current valid holders are listed; None lists none.
unavailable_leave_types: The leave types that count as absence (a list or one type); the default reads the fact policy.staffing.unavailable_leave_types.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

ExpiryReport, a named tuple of frame, counts, events and holders. frame is a pandas.DataFrame with emp_key, legal_entity_key, expires, booked, course_date, event_no, free_seats, gap_days and on_leave_at_course, one row per person sorted by emp_key. counts is a dict with the keys expiry_date, qual_key, n_expiring, n_booked, n_not_booked, rows_expiring_on_date, former_employees, superseded, n_holders and booked_on_leave_at_course. former_employees counts the certificate rows of qual_key expiring on expiry_date whose holder has left or has no hr.employee row; superseded counts such rows, still unexpired on as_of, whose holder has a later issue in force on as_of; rows_expiring_on_date counts all raw certificate rows of qual_key expiring on expiry_date, of any issue date. events is a pandas.DataFrame with event_no, date, country, location_site_key, capacity, seats_taken and free_seats. holders is a sorted tuple of emp_key.

## Raises

FrameError: a frame lacks a column, hr.employee has a duplicate emp_key, the certificate frame has duplicate columns, a missing key or issued date or an expiry before its issue, a date column holds numbers or text that is not a date, capacity or seats_taken of the training events is not a number, unavailable_leave_types is not a leave type name or a list of them (None, a number), or the leave type default lists no type.
PeriodError: as_of or expiry_date is not a date without a time zone (the message names the argument).
FactNotFound: the default leave types are used and the fact is not in the snapshot.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import expiry_report
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "qual_key": ["QUAL-01"] * 2, "issued": ["2023-01-01"] * 2, "expires": ["2026-12-31"] * 2})
>>> booked = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "course_date": ["2026-10-10"], "course_end": ["2026-10-11"], "event_no": [7], "free_seats": [6]})
>>> event = pd.DataFrame({"event_no": [7], "qual_key": ["QUAL-01"], "date": ["2026-10-10"], "capacity": [10], "seats_taken": [4], "country": ["DK"], "location_site_key": ["SITE-01"]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "leave_date": [None, None], "legal_entity_key": ["LE-01", "LE-01"]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["extended_leave"], "start": ["2026-09-01"], "end": [None]})
>>> r = expiry_report(cert, booked, event, employee, leave, dt.date(2026, 6, 30), expiry_date=dt.date(2026, 12, 31), qual_key="QUAL-01", unavailable_leave_types=["extended_leave"])
>>> r.frame[["emp_key", "booked", "free_seats"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'booked': True, 'free_seats': 6.0}, {'emp_key': 'EMP-000002', 'booked': False, 'free_seats': nan}]
>>> r.counts["n_expiring"], r.counts["n_booked"], r.counts["n_not_booked"]
(2, 1, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.unavailable_leave_types`.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.training_event.date`, `competence.training_event.qual_key`, `competence.training_event.capacity`, `competence.training_event.seats_taken`, `hr.employee.leave_date`, `hr.leave_record.leave_type`, `hr.leave_record.start`, `hr.leave_record.end`.

# gap_table

```python
gap_table(frame: pd.DataFrame, by: str = 'department', *, minimum_group: int = 8, watch: float = 0.03, context: Context | None = None) -> pd.DataFrame
```

Use this when you want the pay difference between women and men per department or per grade in one table, with a flag for each group and a ranking.

Rule: for each group the counts, the raw gap (raw_gap) and the adjusted gap (adjusted_gap) in percent. The flag is above_threshold at or above the legal joint assessment threshold (a fact), watch at or above watch times 100 percent (proposed 0.03), otherwise ok. A group under minimum_group people per gender (proposed 8) keeps its counts, loses the gaps, is flagged suppressed and has no rank. The rank is by adjusted gap, highest first. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key, level and the grouping column (dep_key or level).
by: Either department (groups by dep_key) or grade (groups by level). Default department.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
watch: The share at or above which a group is flagged watch. Default 0.03 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

pandas.DataFrame: one row per group with the key column, n_women, n_men, raw_gap_pct, adjusted_gap_pct, adjusted_gap_se_pct, flag, suppressed, rank and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: by is not department or grade, or a column is missing.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import gap_table
>>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6, "dep_key": ["DEP-01"] * 6})
>>> table = gap_table(people, minimum_group=3, context=access)
>>> table[["dep_key", "n_women", "n_men", "suppressed"]].values.tolist(), round(float(table["raw_gap_pct"].iloc[0]), 1)
([['DEP-01', 3, 3, False]], 9.1)
>>> gap_table(people, context=access)["flag"].tolist()
['suppressed']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.pay_transparency.joint_assessment_gap_threshold`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.

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

# headcount_on

```python
headcount_on(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, as_of: dt.date, level: str = 'department') -> pd.DataFrame
```

Use this when you need the number of active people and their full time equivalents on a date, by department, team or legal entity.

Rule: a person is active on the date when the hire date is on or before it and the leave date is empty or on or after it. The team and the fte come from the employment term valid on the date.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date, leave_date and legal_entity_key, one row per person.
term: Employment term frame (hr.employment_term).
team: Team frame (hr.team) with team_key and dep_key.
as_of: The date.
level: "department", "team" or "entity". Default "department".

## Returns

pandas.DataFrame: one row per department, team or entity with headcount and fte, sorted by the key.

## Raises

FrameError: the level is not allowed, a frame lacks a column, an active person has no term on the date, or a team is missing in the team frame.
AmbiguousKey: one person has two terms valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import headcount_on
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "hire_date": ["2020-01-01", "2027-01-01"],
...                          "leave_date": [None, None], "legal_entity_key": ["LE-01", "LE-01"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2020-01-01", "2027-01-01"], "valid_to": [None, None],
...                      "team_key": ["TEAM-01", "TEAM-01"], "fte": [1.0, 0.5]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "dep_key": ["DEP-1"]})
>>> headcount_on(employee, term, team, dt.date(2026, 6, 1)).to_dict("records")
[{'dep_key': 'DEP-1', 'headcount': 1, 'fte': 1.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.employment_term.fte`, `hr.team.dep_key`.

# intake_compa_by_grade

```python
intake_compa_by_grade(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8, context: Context | None = None) -> pd.DataFrame
```

Use this when you want to compare women and men hired from a given date in one department, grade by grade, on their position in the pay band.

Rule: among people in the department, hired on or after the date and in the given grades, the gap is (mean compa of women over mean compa of men minus 1) times 100; negative means women are below men. One row per grade and one row all for the pool. A row with fewer than minimum_group people (proposed 8) of one gender has NaN and suppressed True. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level and compa.
dep: The department key (required).
hired_from: The first hire date that counts (required: the caller decides which intake it asks about).
grades: The grade levels that count (required).
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

pandas.DataFrame: one row per grade plus all, with grade_level, n_women, n_men, women_vs_men_compa_pct (percent, NaN when suppressed), suppressed and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import intake_compa_by_grade
>>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0]})
>>> by_grade = intake_compa_by_grade(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), minimum_group=1, context=access)
>>> by_grade[["grade_level", "n_women", "n_men"]].values.tolist()
[[2, 1, 1], ['all', 1, 1]]
>>> round(float(by_grade["women_vs_men_compa_pct"].iloc[0]), 6)
-10.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.department.dep_code`.

# intake_pay_difference

```python
intake_pay_difference(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8, context: Context | None = None) -> dict[str, Any]
```

Use this when you want to know whether the women hired from an intake date are paid differently from the men and from the other women of the same department.

Rule: the by-grade frame of intake_compa_by_grade, and an OLS of ln(rate_dkk) on a dummy for women hired from the intake date, a dummy for the other women, tenure, entity and grade, over the whole department. The estimates are 100 times (exp(b) minus 1): negative when the women earn less (the sign of a pay level, not of adjusted_gap). The intake estimate is NaN with suppressed True when fewer than minimum_group women (proposed 8) were hired from the intake date or fewer men are in the department; the estimate of the other women is NaN when they number fewer than minimum_group. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level, compa, rate_dkk, tenure_years and legal_entity_key.
dep: The department key (required).
hired_from: The first hire date of the intake (required: the caller decides which intake it asks about).
grades: The grade levels of the by-grade frame (required).
minimum_group: The smallest number of people per group. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

dict: by_grade (the intake_compa_by_grade frame), n_intake_women, n_other_women, n_men, intake_women_pct and its se, other_women_pct and its se (percent), suppressed (bool) and legal_status.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, or the rate, entity, grade or tenure values are missing or not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import intake_pay_difference
>>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0],
...                         "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"]})
>>> result = intake_pay_difference(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), context=access)
>>> result["suppressed"], result["n_intake_women"], result["n_men"]
(True, 1, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.department.dep_code`.

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

# overlapping_usernames

```python
overlapping_usernames(index: pd.DataFrame) -> list[str]
```

Use this when you want to check that no username was held by two holders on overlapping dates.

Rule: a username is never reused, so the list is expected to be empty.

## Args

index: The output of build_username_index.

## Returns

list: the usernames that map to different holders on overlapping dates, sorted; empty when the index is clean.

## Raises

FrameError: the index lacks a column or a date is not a date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, overlapping_usernames
>>> history = pd.DataFrame({"username": ["ab", "ab"], "emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2024-01-01", "2024-06-01"], "valid_to": [None, None]})
>>> pool = pd.DataFrame(columns=["account_name", "team_key", "valid_from", "valid_to"])
>>> overlapping_usernames(build_username_index(history, pool))
['ab']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.emp_key`, `hr.username_history.username`, `hr.username_history.valid_from`, `hr.username_history.valid_to`.

# pay_frame

```python
pay_frame(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, as_of: dt.date, *, context: Context, bands_year: int = 2026) -> pd.DataFrame
```

Use this when you need the person frame on a date with the monthly full-time rate, tenure and position in the pay band; it is the input of every pay difference function.

Rule: the terms valid on the date, with rate_local = base_salary over fte; rate_dkk is rate_local for a DKK term and rate_local times the fixed EUR to DKK rate (a fact) for an EUR term. tenure_years is the days from hire_date to as_of over 365.25; compa is rate_local over the band midpoint in the currency of the term. base_salary itself is not returned. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning in attrs["warnings"] says that compa is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

employee: Employee frame with emp_key, gender, hire_date and legal_entity_key.
term: Employment term frame with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency and base_salary.
team: Team frame with team_key and dep_key.
grade: Grade frame with gra_key, level and the DKK and EUR band minimum and maximum.
as_of: The date the frame describes.
context: The caller; the role must be allowed to read pay (required keyword).
bands_year: The year the grade bands are set at. Default 2026 (proposed).

## Returns

pandas.DataFrame: one row per valid term with the employee, team and grade columns, rate_local, rate_dkk, tenure_years and compa, and warnings in attrs.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the term frame has no base_salary.
FrameError: a column is missing, a valid term has fte not above zero, a missing or infinite salary or a currency other than DKK and EUR, or a valid term has no employee, team or grade.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> import datetime as dt
>>> from halvaro.hr import pay_frame
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "hire_date": [dt.date(2020, 1, 1)], "legal_entity_key": ["LE-01"]})
>>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": [dt.date(2020, 1, 1)], "valid_to": [None], "team_key": ["TEAM-1"], "grade_key": ["GRA-1"], "fte": [1.0],
...                       "currency": ["DKK"], "base_salary": [50000.0]})
>>> team = pd.DataFrame({"team_key": ["TEAM-1"], "dep_key": ["DEP-01"]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-1"], "level": [3], "band_min_dkk": [40000.0], "band_max_dkk": [60000.0], "band_min_eur": [5000.0], "band_max_eur": [8000.0]})
>>> frame = pay_frame(employee, term, team, grade, dt.date(2026, 6, 1), context=access)
>>> frame[["rate_dkk", "compa"]].values.tolist()
[[50000.0, 1.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.

# payroll_aggregate

```python
payroll_aggregate(term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, first_month: str, last_month: str, *, minimum_group: int | PolicyDefault = policy:policy.pay_gap.minimum_cohort_size, on_small: str = 'pool', context: Context) -> pd.DataFrame
```

Use this when you need the gross pay of the employment terms per legal entity, cost centre, month and currency, without employee keys and without base salary, for the tie-out with finance.

Rule: pay is restricted, so the context must be allowed to read hr.employment_term.base_salary. For each month from first_month to last_month, each term in force in the month (valid_from to valid_to inclusive; an empty valid_to is open) weighs days in force over days in the month; terms are grouped by the legal entity and cost centre of their team and by currency. A group with fewer than minimum_group distinct people is small: on_small 'pool' (default) adds the small cost centres of one entity, currency and month into one row with cc_key POOLED, which is itself suppressed when it still has fewer people; 'suppress' keeps each small group with null numbers; 'refuse' raises. Suppressed rows have null numbers. Without suppression the total over all rows equals the sum over the terms. Months without a term give no row. A grade band value that is null adds 0 to the band totals (the sum skips nulls), and a term with valid_to before valid_from is accepted but has weight 0, so it is left out of the month (no row of its own, not counted in n_people).

## Args

term: Employment terms (hr.employment_term) with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency (DKK or EUR) and base_salary; fte above zero, no nulls except valid_to.
team: Teams (hr.team) with team_key, cost_centre_key and legal_entity_key, one row per team.
grade: Grades (hr.grade) with gra_key, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per grade.
first_month: The first month as text, YYYY-MM.
last_month: The last month as text, YYYY-MM; not before first_month.
minimum_group: The smallest number of people a group may show, a whole number of one or more (default the fact policy.pay_gap.minimum_cohort_size, status proposed; the status then goes into attrs["policy_status"]).
on_small: What to do with a small group: 'pool', 'suppress' or 'refuse'.
context: The caller (stage, role and whether restricted columns may be read); the role must be allowed to read pay.

## Returns

pandas.DataFrame with le_key, cc_key, period (YYYY-MM), currency, hr_gross_pay (base salary times fte times days in force over days in the month, the rule of finance.payroll_hr_reconciliation), hr_headcount_month_end (terms in force on the last day of the month), hr_fte (fte weighted by days), band_minimum_total and band_maximum_total (grade band times weighted fte, in the currency of the term), n_people (distinct people with a term in the month), n_cost_centres, cost_centres (the cost centre keys of the group, comma separated: one key, or the members of a POOLED row) and suppressed, sorted by le_key, cc_key, period and currency.

## Raises

RestrictedColumnRefusal: the context may not read base salary, or term has no base_salary column.
FrameError: context is not a Context (None, text), fte or base_salary holds text, on_small or minimum_group is invalid, a month is not YYYY-MM or first_month is after last_month, a frame lacks a column, hr.team or hr.grade has a duplicate key, term has missing values, a currency other than DKK or EUR or an fte of zero or less, a term names a team or grade that is not in hr.team or hr.grade, a date is not a date, a policy default is not a whole number, or on_small is 'refuse' and a group is small.
FactNotFound: the default minimum group is used and its fact is not in the snapshot.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.hr import payroll_aggregate
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2025-01-01", "2026-01-16"], "valid_to": [None, None], "team_key": ["TEAM-01"] * 2,
...                      "grade_key": ["GRA-01"] * 2, "fte": [1.0, 1.0], "currency": ["DKK"] * 2, "base_salary": [100.0, 100.0]})
>>> team = pd.DataFrame({"team_key": ["TEAM-01"], "cost_centre_key": ["CC-01"], "legal_entity_key": ["LE-01"]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-01"], "band_min_dkk": [50.0], "band_max_dkk": [150.0], "band_min_eur": [7.0], "band_max_eur": [20.0]})
>>> reader = Context(stage="month12", role="analyst", restricted_ok=True)
>>> shown = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=2, context=reader)
>>> shown[["cc_key", "period", "hr_headcount_month_end", "n_people", "suppressed"]].to_dict("records")
[{'cc_key': 'CC-01', 'period': '2026-01', 'hr_headcount_month_end': 2.0, 'n_people': 2, 'suppressed': False}]
>>> round(float(shown["hr_fte"].iloc[0]), 3)
1.516
>>> held = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=3, context=reader)
>>> held[["cc_key", "n_people", "suppressed"]].to_dict("records"), bool(held["hr_fte"].isna().all())
([{'cc_key': 'POOLED', 'n_people': 2, 'suppressed': True}], True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.pay_gap.minimum_cohort_size`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employment_term.team_key`, `hr.employment_term.grade_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`, `hr.team.cost_centre_key`, `hr.team.legal_entity_key`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.

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

# project_requirements

```python
project_requirements(requirement: pd.DataFrame, project: pd.DataFrame, prj_key: str, *, role_keys: Sequence[str] = (), context: Context | None = None) -> pd.DataFrame
```

Use this when you need the qualifications that a project must cover, from the requirements of its project, contract, project type and roles.

Rule: the rows of each scope that match the project are kept apart (column via) and never merged. Scope project matches the project key, contract its contract_key, project_type its type and role the role keys passed in.

## Args

requirement: Requirement frame (competence.requirement) with scope_type, scope_key, qual_key, min_headcount and requirement_level.
project: Project frame (projects.project) with prj_key, type and contract_key.
prj_key: The project.
role_keys: The role keys of the crew, for the scope role. Default none.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: the columns of the requirement frame plus via, sorted by scope and qual_key; min_headcount is null for role rows.

## Raises

FrameError: a column is missing, the project is not in the project frame exactly once, or a scope_type is unknown.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import project_requirements
>>> requirement = pd.DataFrame({"scope_type": ["project", "project_type", "project_type"], "scope_key": ["PRJ-1", "dh_network", "other"], "qual_key": ["QUAL-01", "QUAL-02", "QUAL-03"],
...                              "min_headcount": [2, 1, 1], "requirement_level": ["must", "must", "must"]})
>>> project = pd.DataFrame({"prj_key": ["PRJ-1"], "type": ["dh_network"], "contract_key": [None]})
>>> project_requirements(requirement, project, "PRJ-1")[["via", "qual_key", "min_headcount"]].to_dict("records")
[{'via': 'project', 'qual_key': 'QUAL-01', 'min_headcount': 2}, {'via': 'project_type', 'qual_key': 'QUAL-02', 'min_headcount': 1}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.requirement.scope_type`, `competence.requirement.scope_key`, `competence.requirement.qual_key`, `competence.requirement.min_headcount`, `competence.requirement.requirement_level`, `projects.project.prj_key`, `projects.project.type`, `projects.project.contract_key`.

# raw_gap

```python
raw_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> float
```

Use this when you need the raw pay difference between women and men: how much less the women are paid on average, before any adjustment.

Rule: one minus the mean rate of women over the mean rate of men, in percent; positive means women are paid less. The result is NaN when either gender has fewer than minimum_group people (proposed 8). The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with gender and rate_dkk; only F and M rows count.
minimum_group: The smallest number of people per gender. Default 8 (proposed).
context: The caller; with it the role must be allowed to read pay. Optional keyword.

## Returns

float: the gap in percent, or NaN below the minimum group size.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: the frame lacks the column gender.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import raw_gap
>>> people = pd.DataFrame({"gender": ["F", "F", "M", "M"], "rate_dkk": [90.0, 110.0, 190.0, 210.0]})
>>> raw_gap(people, minimum_group=2, context=access)
50.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`.

# renewal_chains

```python
renewal_chains(cert: pd.DataFrame, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need to see how certificates follow each other for a person and qualification: the chains of renewals, with lapses and overlaps.

Rule: a certificate with no renews_issued starts a chain; a renewal names the issue date of the one it renews. link_ok says that renews_issued is the previous issue. lapse_days are the days without a valid certificate before this one, overlap_days the days both are valid; both are given only for a renewal whose link is ok.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires, origin, event_no and renews_issued.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: the certificate rows with chain, position, previous issue and expiry, link_ok, covered_until, lapse_days and overlap_days.

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import renewal_chains
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2023-12-01"], "expires": ["2023-12-31", "2025-12-31"],
...                      "origin": ["initial", "renewal"], "event_no": [1, 2], "renews_issued": [None, "2022-01-01"]})
>>> renewal_chains(cert)[["position", "link_ok", "lapse_days", "overlap_days"]].fillna(-1).values.tolist()
[[1, True, -1.0, -1.0], [2, True, 0.0, 31.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.certification_held.origin`, `competence.certification_held.event_no`, `competence.certification_held.renews_issued`.

# resolve_assignments

```python
resolve_assignments(assignment: pd.DataFrame, index: pd.DataFrame, employee: pd.DataFrame, as_of: dt.date, asset_return_days: int | PolicyDefault = policy:policy.offboarding.asset_return_days, *, context: Context | None = None) -> Resolution
```

Use this when you check who holds each asset assignment: the person or team behind each username at the start of the assignment, and whether they still hold it until the end.

Rule: each assignment is resolved with the username index at its valid_from; unresolved and ambiguous rows are counted, not dropped. The kind follows assignment_type (named employee, pool_account pool, team no username but a pool_team_key). Further columns say whether the person was employed on the start day, held the username to the end or the leave date, and returned the asset after the leave date. asset_return_days defaults to the fact policy.offboarding.asset_return_days (status proposed); the diagnostics carry the value and its status.

## Args

assignment: Assignment frame (it-assets.assignment) with assignment_type, assigned_username, valid_from, valid_to and pool_team_key.
index: The output of build_username_index.
employee: Employee frame (hr.employee) with emp_key and leave_date.
as_of: The date the open assignments are judged on.
asset_return_days: Whole number of days an asset may be returned after the leave date. Default the fact.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

Resolution: .frame is the assignment frame with resolution, kind, emp_key, team_key, kind_ok, employed_on_start, leave_date, holds_to_end, returned_after_leave_days, open_after_leave and late_return; .diagnostics counts the cases.

## Raises

FrameError: asset_return_days is not a whole number, the assignment frame already has a column that is added, the employee frame has a person twice, assignment_type is unknown, or an assignment ends before it starts.
StageRefusal: a context is given and its stage does not hold the it-assets and hr sources.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, resolve_assignments
>>> assignment = pd.DataFrame({"assignment_type": ["named", "pool_account"], "assigned_username": ["ab", "ops-pool"], "valid_from": ["2025-01-01"] * 2, "valid_to": [None, None], "pool_team_key": [None, "TEAM-01"]})
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"], "leave_date": [None]})
>>> result = resolve_assignments(assignment, build_username_index(history, pool), employee, dt.date(2026, 3, 1))
>>> result.frame["kind"].tolist(), result.diagnostics["resolved"], result.diagnostics["unresolved"]
(['employee', 'pool'], 2, 0)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.offboarding.asset_return_days`.

Source columns: `it-assets.assignment.assigned_username`, `it-assets.assignment.valid_from`, `it-assets.assignment.valid_to`, `it-assets.assignment.assignment_type`, `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`.

# resolve_username

```python
resolve_username(index: pd.DataFrame, username: str, on: dt.date) -> dict[str, Any] | None
```

Use this when you have a username or a pool account name and a date and need to know who held it.

Rule: the index is effective dated; the row valid on the date gives the holder. A username is never reused, so two holders on one date is an error.

## Args

index: The output of build_username_index.
username: The username or pool account name.
on: The date.

## Returns

dict | None: {'kind': 'employee' or 'pool', 'emp_key', 'team_key'} (the key that does not apply is None), or None when nobody held the name on that date.

## Raises

FrameError: the index lacks a column or a date is not a date.
AmbiguousUsername: two holders on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import build_username_index, resolve_username
>>> history = pd.DataFrame({"username": ["ab"], "emp_key": ["EMP-000001"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> pool = pd.DataFrame({"account_name": ["ops-pool"], "team_key": ["TEAM-01"], "valid_from": ["2024-01-01"], "valid_to": [None]})
>>> index = build_username_index(history, pool)
>>> resolve_username(index, "ab", dt.date(2026, 3, 1))
{'kind': 'employee', 'emp_key': 'EMP-000001', 'team_key': None}
>>> resolve_username(index, "ops-pool", dt.date(2026, 3, 1))["kind"], resolve_username(index, "nobody", dt.date(2026, 3, 1))
('pool', None)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.username_history.username`, `hr.shared_account.account_name`.

# skill_latest

```python
skill_latest(skill_rating: pd.DataFrame, skill: pd.DataFrame, as_of: dt.date | None = None, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the latest rating of each person and skill, with the name of the skill.

Rule: the latest rating is the one with the highest assessed_on. On the same day the higher round_no wins when the column exists (a null round_no loses to any number), then the higher level. With as_of only ratings assessed on or before that date count.

## Args

skill_rating: Rating frame (competence.skill_rating) with emp_key, skl_key, level and assessed_on.
skill: Skill frame (competence.skill) with skl_key and name, one row per skill.
as_of: Optional date; later ratings are ignored.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: emp_key, skl_key, name, level and assessed_on, sorted by emp_key and skl_key.

## Raises

FrameError: a frame lacks a column, skl_key is duplicated in the skill frame, a rating has a null emp_key, skl_key, level or assessed_on, or a rating points at a skill that is not in the skill frame.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import skill_latest
>>> rating = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "skl_key": ["SKL-1", "SKL-1"], "level": [2, 3], "assessed_on": ["2025-01-01", "2026-01-01"]})
>>> skill = pd.DataFrame({"skl_key": ["SKL-1"], "name": ["Welding"]})
>>> skill_latest(rating, skill, dt.date(2025, 12, 31))[["name", "level"]].to_dict("records")
[{'name': 'Welding', 'level': 2}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.skill_rating.emp_key`, `competence.skill_rating.skl_key`, `competence.skill_rating.level`, `competence.skill_rating.assessed_on`, `competence.skill.name`.

# staffing_candidates

```python
staffing_candidates(experience: pd.DataFrame, status: Mapping[str, pd.DataFrame], *, valid: Mapping[str, pd.DataFrame] | None = None, qual_keys: Sequence[str] = ()) -> pd.DataFrame
```

Use this when you want the experience ranking with the staffing status of each person on one or more dates.

Rule: for each label of status the status on that date (available, on_leave, left, not_hired) goes in status_<label> and staffable_<label> is true when it is available. Leavers are shown and never staffable. With valid and qual_keys, certs_<label> is true when the person holds every qualification on that date. The order of the experience frame is kept.

## Args

experience: The output of experience_summary.
status: A mapping of label to the status_on output of that date.
valid: A mapping of label to the valid_on output of that date. Optional; needs qual_keys.
qual_keys: The qualifications to check with valid. Default none.

## Returns

pandas.DataFrame: the experience frame with status_<label>, staffable_<label> and, when valid is given, certs_<label>. A person missing from a status frame gets a null status and is not staffable.

## Raises

FrameError: a status frame has more than one row for a person, or valid is given without qual_keys.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import staffing_candidates
>>> experience = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "rank": [1, 2], "hours": [100.0, 50.0]})
>>> status = {"mar": pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "status": ["available", "on_leave"]})}
>>> staffing_candidates(experience, status)[["emp_key", "status_mar", "staffable_mar"]].values.tolist()
[['EMP-000001', 'available', True], ['EMP-000002', 'on_leave', False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.leave_date`, `hr.leave_record.leave_type`.

# status_on

```python
status_on(employee: pd.DataFrame, leave_record: pd.DataFrame, as_of: dt.date, unavailable_leave_types: Sequence[str] | PolicyDefault = policy:policy.staffing.unavailable_leave_types) -> pd.DataFrame
```

Use this when you need to know, for each person, whether they have left, are on leave, are not yet hired or are available on a date.

Rule: left when leave_date is before the date, not_hired when hire_date is after it, on_leave when a leave of an unavailable type covers it (a leave with no end is open), otherwise available. The leave types default to the fact policy.staffing.unavailable_leave_types (status proposed: the owner has not decided); when the default is used the frame carries attrs["policy_status"] with the fact status.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
leave_record: Leave frame (hr.leave_record) with emp_key, leave_type, start and end.
as_of: The date.
unavailable_leave_types: Leave types that make a person unavailable, as a list, or the default fact.

## Returns

pandas.DataFrame: one row per employee with emp_key, as_of and status (left, on_leave, not_hired or available).

## Raises

FrameError: a frame lacks a column, employee has duplicate emp_key values, or a person has no hire_date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import status_on
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003", "EMP-000004"],
...                          "hire_date": ["2020-01-01", "2021-01-01", "2027-01-01", "2019-01-01"],
...                          "leave_date": [None, None, None, "2025-06-30"]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["parental"], "start": ["2026-03-01"], "end": [None]})
>>> status_on(employee, leave, dt.date(2026, 6, 1), unavailable_leave_types=["parental"])["status"].tolist()
['available', 'on_leave', 'not_hired', 'left']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.staffing.unavailable_leave_types`.

Source columns: `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`, `hr.leave_record.emp_key`, `hr.leave_record.leave_type`, `hr.leave_record.start`, `hr.leave_record.end`.

# suppress_small_cells

```python
suppress_small_cells(table: pd.DataFrame, value_columns: str | Sequence[str], *, count_columns: Sequence[str] = ('n_women', 'n_men'), minimum_group: int = 8) -> pd.DataFrame
```

Use this when you publish a gap table and must hide the values of groups that are too small.

Rule: in a row where any count is under minimum_group (proposed 8) or missing, the value columns are set to null; the flag becomes suppressed, the rank empty and the standard error null where those columns exist. The column suppressed only turns on, so suppressing twice gives the same table.

## Args

table: The gap table with the value columns and the count columns.
value_columns: One column name or a list of names whose values are hidden for a small group.
count_columns: The columns with the group sizes. Default n_women and n_men.
minimum_group: The smallest group size that may be shown. Default 8 (proposed).

## Returns

pandas.DataFrame: a copy of the table with the small groups hidden and a boolean column suppressed.

## Raises

FrameError: the table lacks a value column or a count column.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import suppress_small_cells
>>> table = pd.DataFrame({"group": ["a", "b"], "n_women": [10, 3], "n_men": [12, 9], "gap_pct": [1.5, 2.5]})
>>> suppress_small_cells(table, ["gap_pct"])[["group", "gap_pct", "suppressed"]].astype(str).values.tolist()
[['a', '1.5', 'False'], ['b', 'nan', 'True']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# tenure_years

```python
tenure_years(employee: pd.DataFrame, as_of: dt.date, days_per_year: float = 365.25) -> pd.Series
```

Use this when you need the years of service of each person on a date.

Rule: (date minus hire_date) in days over days_per_year. A leaver is measured to the leave date. The value is NaN before the hire date and when the leave date is before the hire date.

## Args

employee: Employee frame (hr.employee) with emp_key, hire_date and leave_date, one row per person.
as_of: The date.
days_per_year: Days in a year for the division. Default 365.25. Must be positive.

## Returns

pandas.Series: years of service, named tenure_years and indexed by emp_key.

## Raises

FrameError: employee lacks a column or has duplicate emp_key values, or days_per_year is not positive.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import tenure_years
>>> employee = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000003"], "hire_date": ["2020-01-01", "2027-01-01"], "leave_date": [None, None]})
>>> tenure_years(employee, dt.date(2026, 1, 1)).round(2).to_dict()
{'EMP-000001': 6.0, 'EMP-000003': nan}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.emp_key`, `hr.employee.hire_date`, `hr.employee.leave_date`.

# term_changes

```python
term_changes(term: pd.DataFrame) -> pd.DataFrame
```

Use this when you need the events behind the employment terms: one row per name in the change reason of each term.

Rule: a change reason such as pay_review+promotion gives two events with combined true; a single name gives one event with combined false. The known names are hire, window_start, summary, pay_review, promotion and fte_change.

## Args

term: Employment term frame (hr.employment_term) with emp_key, valid_from and change_reason.

## Returns

pandas.DataFrame with emp_key, valid_from, event and combined, sorted by person, date and event.

## Raises

FrameError: a column is missing, a term has no change_reason, or a name is not one of the known names.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import term_changes
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2024-01-01", "2025-01-01"], "change_reason": ["hire", "pay_review+promotion"]})
>>> term_changes(term)[["valid_from", "event", "combined"]].to_dict("records")
[{'valid_from': '2024-01-01', 'event': 'hire', 'combined': False}, {'valid_from': '2025-01-01', 'event': 'pay_review', 'combined': True}, {'valid_from': '2025-01-01', 'event': 'promotion', 'combined': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.change_reason`, `hr.employment_term.valid_from`.

# terms_on

```python
terms_on(term: pd.DataFrame, as_of: dt.date) -> pd.DataFrame
```

Use this when you need the one employment term that is valid on a date for each person, without the restricted pay column.

Rule: a term is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. The org layer never returns a restricted column, so the pay column is dropped from the result.

## Args

term: The employment term frame (hr.employment_term) with emp_key, valid_from and valid_to.
as_of: The date.

## Returns

pandas.DataFrame: one row per person with a term valid on the date, the columns of the frame except the restricted ones.

## Raises

FrameError: the frame lacks emp_key, valid_from or valid_to.
AmbiguousKey: one person has two terms valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import terms_on
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2025-01-01", "2026-01-01"],
...                      "valid_to": ["2025-12-31", None], "team_key": ["TEAM-01", "TEAM-02"]})
>>> terms_on(term, dt.date(2026, 6, 1))[["emp_key", "team_key"]].to_dict("records")
[{'emp_key': 'EMP-000001', 'team_key': 'TEAM-02'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.valid_from`, `hr.employment_term.valid_to`.

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

# valid_on

```python
valid_on(cert: pd.DataFrame, as_of: dt.date, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the certificates that are valid on a date, one row per person and qualification.

Rule: a certificate is valid when issued is on or before the date and expires is empty (no expiry) or on or after the date, both ends included. The status column is never read. Per person and qualification the latest issue is kept.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
as_of: The date.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: emp_key, qual_key, issued, expires and as_of, sorted by person and qualification.

## Raises

FrameError: a column is missing or duplicated, a row has no emp_key, qual_key or issued, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import valid_on
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "qual_key": ["QUAL-01", "QUAL-01"],
...                      "issued": ["2023-01-10", "2025-01-10"], "expires": ["2025-01-09", "2027-01-09"]})
>>> valid = valid_on(cert, dt.date(2026, 11, 30))
>>> valid["qual_key"].tolist(), valid["expires"].dt.strftime("%Y-%m-%d").tolist()
(['QUAL-01'], ['2027-01-09'])
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`.

# with_education

```python
with_education(frame: pd.DataFrame, education: pd.DataFrame, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you want the education level of each person next to the pay frame, so that it can be used as a control in the adjusted gap.

Rule: education_rank is the highest level_rank of the person's education records and 0 without a record; has_education_record says which. People without a record are kept, so the control treats no record as rank 0. The input is not changed.

## Args

frame: A pay frame (the output of pay_frame) with emp_key.
education: Education record frame (competence.education_record) with emp_key and level_rank.
context: The caller. Optional keyword.

## Returns

pandas.DataFrame: the frame plus education_rank and has_education_record.

## Raises

RestrictedColumnRefusal: a context is given and its role may not read pay.
StageRefusal: a context is given and its stage does not hold the pay and education sources.
FrameError: a column is missing, the pay frame already has one of the new columns, or level_rank is not valid.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import with_education
>>> people = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
>>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "level_rank": [2, 3]})
>>> with_education(people, education, context=access)[["emp_key", "education_rank", "has_education_record"]].values.tolist()
[['EMP-000001', 3, True], ['EMP-000002', 0, False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `competence.education_record.emp_key`, `competence.education_record.level_rank`.
