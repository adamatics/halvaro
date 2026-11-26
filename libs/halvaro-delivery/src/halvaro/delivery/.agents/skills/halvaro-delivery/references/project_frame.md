# project_frame

Module `halvaro.delivery.projects`. Import: `from halvaro.delivery import project_frame`.

```python
project_frame(project: pd.DataFrame, *, story_prj_keys: Sequence[str] = ('PRJ-000001',), context: halvaro.core.access.Context) -> Envelope
```

Use this when you need the project master with its flags: full or summary depth, legacy, route length known and story project.

The result is the project master with is_full, legacy, has_route_length and is_story added (input index kept); `value` is the frame. A count off the full and legacy facts (world.projects.full_total, world.projects.legacy_total) is a warning, as is a project that is both or neither of full and legacy and a data_depth other than full or summary. The keys flagged by is_story are the keyword parameter story_prj_keys (PROPOSED default, review item 7 of #440). The legacy column must be True or False on every row; a null or another value is refused, never cast.

Args:
    project: The projects.project frame, one row per prj_key; it needs prj_key, data_depth, legacy, route_length_m and currency, and must not already have is_full, has_route_length or is_story.
    story_prj_keys: The project keys flagged as story projects (PROPOSED default; one key as text is also accepted, None means none).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An Envelope whose `value` is the project frame with the added columns is_full (data_depth is full), has_route_length (route_length_m is not null) and is_story (prj_key in story_prj_keys), with the facts, sources and warnings of the check.

Raises:
    FrameError: project is not a DataFrame, has duplicate column names or lacks a needed column; a prj_key is null or repeated; the frame already has is_full, has_route_length or is_story; legacy has a null or a value that is not True or False.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import project_frame
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "data_depth": ["full", "summary"], "legacy": [False, True],
    ...                     "route_length_m": [1500.0, None], "currency": ["EUR", "DKK"]})
    >>> env = project_frame(prj, story_prj_keys=["PRJ-900002"], context=ctx)
    >>> env.value["is_full"].tolist()
    [True, False]
    >>> env.value["has_route_length"].tolist()
    [True, False]
    >>> env.value["is_story"].tolist()
    [False, True]

## Source columns

- `projects.project.prj_key`
- `projects.project.data_depth`
- `projects.project.legacy`
- `projects.project.route_length_m`
- `projects.project.currency`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.projects.full_total`
- `world.projects.legacy_total`
