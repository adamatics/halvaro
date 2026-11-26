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
