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
