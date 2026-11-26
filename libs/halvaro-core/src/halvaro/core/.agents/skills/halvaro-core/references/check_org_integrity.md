# check_org_integrity

```python
check_org_integrity(team: pd.DataFrame, department: pd.DataFrame, site: pd.DataFrame, cost_centre: pd.DataFrame | None = None, expected: dict[str, int] | None = None) -> pd.DataFrame
```

Use this when you need to check the organisation frames for broken references, missing leads and cost centres, and wrong counts.

Rule: one violation row is written per broken rule, with the rule count (the row count differs from the expected count, or a key is repeated), no_cost_centre, cost_centre_not_unique (shared by several teams), no_lead, dangling (the department or site key of a team is not in its frame) or pairing (only when cost_centre is passed: the cost centre of a team is missing there or points to another team). A team without a cost centre therefore also gets a pairing row when cost_centre is passed. A clean organisation gives an empty frame.

## Args

team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, site_key and lead_emp_key.
department: Department frame (hr.department) with dep_key.
site: Site frame (hr.site) with site_key.
cost_centre: Optional cost centre frame (finance.cost_centre) with cc_key and team_key. Without it the pairing rule is not checked.
expected: Optional expected row counts as a dict with the keys teams, departments and sites. Without it (or when empty) the counts of the snapshot are used.

## Returns

pandas.DataFrame: one row per violation with the columns table, key, rule and detail, sorted by those four columns; empty when nothing is broken.

## Raises

FrameError: the team frame lacks a column, or the cost centre frame lacks cc_key or team_key.
KeyError: the department frame lacks dep_key, the site frame lacks site_key, or expected lacks one of teams, departments and sites.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_org_integrity
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "dep_key": ["D1", "D1"], "cost_centre_key": ["CC-1", "CC-2"], "site_key": ["S1", "S1"], "lead_emp_key": ["EMP-X", None]})
>>> department, site = pd.DataFrame({"dep_key": ["D1"]}), pd.DataFrame({"site_key": ["S1"]})
>>> found = check_org_integrity(team, department, site, expected={"teams": 2, "departments": 1, "sites": 1})
>>> found.to_dict("records")
[{'table': 'hr.team', 'key': 'T2', 'rule': 'no_lead', 'detail': 'team has no lead'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.lead_emp_key`, `hr.department.dep_key`, `hr.site.site_key`.
