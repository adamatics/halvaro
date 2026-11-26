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
