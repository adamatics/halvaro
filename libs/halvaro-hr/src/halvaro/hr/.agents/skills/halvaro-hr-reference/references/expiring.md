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
