# build_tree

Module `halvaro.grid.topology`. Import: `from halvaro.grid import build_tree`.

```python
build_tree(network_connection: pd.DataFrame, grid_element: pd.DataFrame | None = None, *, root_types: tuple[str, ...] = ('pump_station', 'substation'), context: halvaro.core.access.Context) -> Tree
```

Use this when you need the directed tree of each zone (parent, children, root and depth of every element) built from the network connections.

Raises FrameError when a zone has no root or several, an element has two parents, a connection runs between zones, the connections form a cycle, or an element of the zone cannot be reached from its root.
With grid_element (net_key, zone_key, element_type) every element of a zone must be in its tree and the root of a zone must be one of root_types (PROPOSED: pump station or substation, as the generator
test states). The root type is not matched against the network type of the zone (heat or electric): root_types is the union. A connected element missing from grid_element, or a duplicate net_key in it, raises.

Args:
    network_connection: The gis.network_connection table; needs net_from, net_to, role and zone_key.
    grid_element: Optional gis.grid_element table with net_key, zone_key and element_type, to check the elements and the root types.
    root_types: The element types a root may have (PROPOSED: pump_station, substation); a non-empty tuple of texts.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Tree with parent (net_key to its parent; roots are not in it), children (net_key to the sorted list of children), roots (zone_key to root net_key), depth (net_key to the number of connections
    from the root) and zone (net_key to zone_key).

Raises:
    FrameError: root_types is not a non-empty tuple of texts; a needed column is missing; a key is null; a connection is listed twice or joins an element to itself or elements of different zones; an element has more than one parent; a zone has no root or more than one; the connections form a cycle; an element cannot be reached from its root; with grid_element, an element is listed twice, a connected element is missing from it, an element is in no connection, a root is not of a root type, or an element is connected in another zone than its own.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import build_tree
    >>> ctx = Context(stage="month12", role="analyst")
    >>> nc = pd.DataFrame({"net_from": ["NET-900001", "NET-900001", "NET-900002"], "net_to": ["NET-900002", "NET-900003", "NET-900004"],
    ...                    "role": ["feeds"] * 3, "zone_key": ["ZONE-0001"] * 3})
    >>> tree = build_tree(nc, context=ctx)
    >>> tree.roots.to_dict(), tree.children["NET-900001"], int(tree.depth["NET-900004"])
    ({'ZONE-0001': 'NET-900001'}, ['NET-900002', 'NET-900003'], 2)

## Source columns

- `gis.network_connection.net_from`
- `gis.network_connection.net_to`
- `gis.network_connection.role`
- `gis.network_connection.zone_key`
