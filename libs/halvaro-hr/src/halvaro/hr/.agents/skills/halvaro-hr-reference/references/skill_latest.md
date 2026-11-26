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
