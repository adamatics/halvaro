# project_requirements

```python
project_requirements(requirement: pd.DataFrame, project: pd.DataFrame, prj_key: str, *, role_keys: Sequence[str] = (), context: Context | None = None) -> pd.DataFrame
```

Use this when you need the qualifications that a project must cover, from the requirements of its project, contract, project type and roles.

Rule: the rows of each scope that match the project are kept apart (column via) and never merged. Scope project matches the project key, contract its contract_key, project_type its type and role the role keys passed in.

## Args

requirement: Requirement frame (competence.requirement) with scope_type, scope_key, qual_key, min_headcount and requirement_level.
project: Project frame (projects.project) with prj_key, type and contract_key.
prj_key: The project.
role_keys: The role keys of the crew, for the scope role. Default none.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: the columns of the requirement frame plus via, sorted by scope and qual_key; min_headcount is null for role rows.

## Raises

FrameError: a column is missing, the project is not in the project frame exactly once, or a scope_type is unknown.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import project_requirements
>>> requirement = pd.DataFrame({"scope_type": ["project", "project_type", "project_type"], "scope_key": ["PRJ-1", "dh_network", "other"], "qual_key": ["QUAL-01", "QUAL-02", "QUAL-03"],
...                              "min_headcount": [2, 1, 1], "requirement_level": ["must", "must", "must"]})
>>> project = pd.DataFrame({"prj_key": ["PRJ-1"], "type": ["dh_network"], "contract_key": [None]})
>>> project_requirements(requirement, project, "PRJ-1")[["via", "qual_key", "min_headcount"]].to_dict("records")
[{'via': 'project', 'qual_key': 'QUAL-01', 'min_headcount': 2}, {'via': 'project_type', 'qual_key': 'QUAL-02', 'min_headcount': 1}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.requirement.scope_type`, `competence.requirement.scope_key`, `competence.requirement.qual_key`, `competence.requirement.min_headcount`, `competence.requirement.requirement_level`, `projects.project.prj_key`, `projects.project.type`, `projects.project.contract_key`.
