# team_context

```python
team_context(team: pd.DataFrame, site: pd.DataFrame) -> pd.DataFrame
```

Use this when you need per team its department, cost centre, legal entity, site, country and calendar region in one frame.

Rule: the site frame is joined to the team frame on the site key; the region is read from the site key by region_of.

## Args

team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, legal_entity_key and site_key.
site: Site frame (hr.site) with site_key and country.

## Returns

pandas.DataFrame: the five team columns, country and region, one row per team in the order of the team frame.

## Raises

FrameError: a frame lacks a column.
UnknownRegion: a team has a site that has no region.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import team_context
>>> team = pd.DataFrame({"team_key": ["T1"], "dep_key": ["D1"], "cost_centre_key": ["CC-1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-05"]})
>>> site = pd.DataFrame({"site_key": ["SITE-05"], "country": ["DE"]})
>>> team_context(team, site)[["team_key", "country", "region"]].to_dict("records")
[{'team_key': 'T1', 'country': 'DE', 'region': 'DE-HH'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.dep_key`, `hr.team.cost_centre_key`, `hr.team.legal_entity_key`, `hr.team.site_key`, `hr.site.country`.
