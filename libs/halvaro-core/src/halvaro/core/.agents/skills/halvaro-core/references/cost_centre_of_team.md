# cost_centre_of_team

```python
cost_centre_of_team(team: pd.DataFrame, team_key: str) -> str
```

Use this when you need the cost centre key of one team.

Rule: the team frame is searched for the team key and the cost centre key of that one row is returned. A team that is missing or listed more than once is refused, never guessed.

## Args

team: Team frame (hr.team) with team_key and cost_centre_key.
team_key: The key of the team, for example "T1".

## Returns

str: the cost centre key of the team, for example "CC-1".

## Raises

FrameError: the frame lacks a column, or the team key does not match exactly one row.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import cost_centre_of_team
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
>>> cost_centre_of_team(team, "T2")
'CC-2'
>>> cost_centre_of_team(team, "T9")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: team T9 has 0 rows in hr.team; expected 1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.cost_centre_key`.
