# team_of_cost_centre

```python
team_of_cost_centre(team: pd.DataFrame, cost_centre_key: str) -> str
```

Use this when you need the team that owns one cost centre.

Rule: the team frame is searched for the cost centre key and the team key of that one row is returned. A cost centre that is missing or shared by several teams is refused, never guessed.

## Args

team: Team frame (hr.team) with team_key and cost_centre_key.
cost_centre_key: The cost centre key, for example "CC-1".

## Returns

str: the key of the team that has the cost centre, for example "T1".

## Raises

FrameError: the frame lacks a column, or the cost centre does not belong to exactly one team.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import team_of_cost_centre
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
>>> team_of_cost_centre(team, "CC-2")
'T2'
>>> team_of_cost_centre(team, "CC-9")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: cost centre CC-9 belongs to 0 teams; expected 1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.cost_centre_key`.
