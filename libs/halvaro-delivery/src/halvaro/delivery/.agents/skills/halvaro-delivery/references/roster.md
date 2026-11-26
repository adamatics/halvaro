# roster

Module `halvaro.delivery.history`. Import: `from halvaro.delivery import roster`.

```python
roster(project_role: pd.DataFrame, project: pd.DataFrame, prj_keys: Sequence[str], *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the role rows of a list of projects as stored, with the legacy flag of each project.

The columns are prj_key, emp_key, project_role, start, end, hours_total, basis and legacy; there is no ranking. Hours of legacy roster rows are estimates; hr experience_summary keeps the two bases apart. A project of the list without role rows is not an error; a project that is not in the project frame is.

Args:
    project_role: The projects.project_role frame; it needs prj_key, emp_key, project_role, start, end, hours_total and basis.
    project: The projects.project frame, one row per prj_key; it needs prj_key and legacy.
    prj_keys: The project keys to list (one key as text is also accepted).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns prj_key, emp_key, project_role, start, end, hours_total, basis, legacy, sorted by prj_key, emp_key, project_role, start.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; project has more than one row for a prj_key; a project of the list is not in project.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import roster
    >>> ctx = Context(stage="month12", role="analyst")
    >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900002", "EMP-900001"], "project_role": ["engineer", "manager"],
    ...                       "start": ["2026-01-01"] * 2, "end": [None, None], "hours_total": [100.0, 50.0], "basis": ["time_entries"] * 2})
    >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "legacy": [False]})
    >>> roster(roles, proj, ["PRJ-900001"], context=ctx)["emp_key"].tolist()
    ['EMP-900001', 'EMP-900002']

## Source columns

- `projects.project_role.prj_key`
- `projects.project_role.emp_key`
- `projects.project_role.project_role`
- `projects.project_role.start`
- `projects.project_role.end`
- `projects.project_role.hours_total`
- `projects.project_role.basis`
- `projects.project.legacy`
