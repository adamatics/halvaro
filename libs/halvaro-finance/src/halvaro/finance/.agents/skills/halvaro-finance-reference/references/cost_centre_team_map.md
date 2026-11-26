# cost_centre_team_map

```python
cost_centre_team_map(cost_centre: pd.DataFrame, team: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that finance cost centres and hr teams point at each other.

Rule: finance.cost_centre.team_key and hr.team.cost_centre_key are compared both ways. A cost centre without a team key (overhead) is not a violation.

## Args

cost_centre: Frame finance.cost_centre with cc_key and team_key, one row per cost centre.
team: Frame hr.team with team_key and cost_centre_key, one row per team.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail: cost_centre_without_team (a team key that hr does not have), team_without_cost_centre (an hr team whose cost centre finance does not have) and cost_centre_team_mismatch (the two views name different partners); empty when they agree.

## Raises

FrameError: a column is missing or a frame has more than one row for a key.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_centre_team_map
>>> ctx = Context(stage="month12", role="analyst")
>>> cost_centre = pd.DataFrame({"cc_key": ["CC-1", "CC-2"], "team_key": ["TEAM-1", "TEAM-9"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-1", "TEAM-2"], "cost_centre_key": ["CC-1", "CC-3"]})
>>> cost_centre_team_map(cost_centre, team, context=ctx)[["key", "rule"]].values.tolist()
[['CC-2', 'cost_centre_without_team'], ['TEAM-2', 'team_without_cost_centre']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.cost_centre.cc_key`, `finance.cost_centre.team_key`, `hr.team.team_key`, `hr.team.cost_centre_key`.
