# experience_network_view

Module `halvaro.delivery.views`. Import: `from halvaro.delivery import experience_network_view`.

```python
experience_network_view(network: ExperienceNetwork, *, as_of: DateLike | None = None, n_no_route: int | None = None, context: halvaro.core.access.Context) -> ViewSpec
```

Use this when you need the experience network as nodes and edges for a force or bipartite drawing.

The frame is the edge list (prj_key, emp_key, roles, start, end, hours_total, basis, legacy), extra holds the nodes (leavers marked) and the co-working pairs. No ranking, no pay. The number of legacy edges is in the caption: their hours are estimates.

Args:
    network: The result of experience_network (an ExperienceNetwork).
    as_of: Optional as-of date, shown in the caption.
    n_no_route: Optional number of projects without a route length, shown in the caption.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ViewSpec of kind 'network': `frame` the edges of the network, x emp_key, y prj_key, n the number of edges, extra['nodes'] and extra['pairs'] the nodes and the co-working pairs of the network.

Raises:
    FrameError: network is not the result of experience_network.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import experience_network, experience_network_view
    >>> ctx = Context(stage="month12", role="analyst")
    >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900001", "EMP-900002"], "project_role": ["manager", "engineer"],
    ...                       "start": ["2026-01-01", "2026-01-06"], "end": ["2026-01-10", "2026-01-20"], "hours_total": [80.0, 100.0], "basis": ["time_entries"] * 2})
    >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tunnel"], "soil_class": ["clay"], "country": ["NL"], "legacy": [False]})
    >>> net = experience_network(roles, proj, ["PRJ-900001"], as_of="2026-02-01", context=ctx)
    >>> spec = experience_network_view(net, as_of="2026-02-01", context=ctx)
    >>> spec.n
    2
    >>> sorted(spec.extra)
    ['nodes', 'pairs']

## Source columns

- `projects.project_role.prj_key`
- `projects.project_role.emp_key`
