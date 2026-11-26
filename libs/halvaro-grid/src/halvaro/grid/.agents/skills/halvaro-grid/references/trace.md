# trace

Module `halvaro.grid.topology`. Import: `from halvaro.grid import trace`.

```python
trace(tree: Tree, net_key: str, direction: str = 'downstream', *, context: halvaro.core.access.Context) -> list[str]
```

Use this when you need the elements downstream or upstream of one element of a tree built by build_tree.

Downstream gives all descendants, nearest first, then by key; upstream gives the path to the root, the nearest parent first. The element itself is not included.

Args:
    tree: The Tree returned by build_tree.
    net_key: The element to start from; it must be in the tree.
    direction: "downstream" (default) or "upstream".
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A list of net keys in the order described above (empty for a leaf downstream or a root upstream).

Raises:
    FrameError: tree is not the result of build_tree; direction is not 'downstream' or 'upstream'; the element is not in the tree; the tree has a parent or child cycle.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import build_tree, trace
    >>> ctx = Context(stage="month12", role="analyst")
    >>> nc = pd.DataFrame({"net_from": ["NET-900001", "NET-900002"], "net_to": ["NET-900002", "NET-900003"],
    ...                    "role": ["feeds"] * 2, "zone_key": ["ZONE-0001"] * 2})
    >>> tree = build_tree(nc, context=ctx)
    >>> trace(tree, "NET-900001", context=ctx)
    ['NET-900002', 'NET-900003']
    >>> trace(tree, "NET-900003", "upstream", context=ctx)
    ['NET-900002', 'NET-900001']

## Source columns

- `gis.network_connection.net_from`
- `gis.network_connection.net_to`
