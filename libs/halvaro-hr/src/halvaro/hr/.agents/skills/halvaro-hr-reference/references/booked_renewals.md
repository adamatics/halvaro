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
