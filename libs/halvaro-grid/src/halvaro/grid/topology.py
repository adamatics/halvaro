"""The network of a zone as a tree: parent, children, depth, root and the elements upstream or downstream of one element.

`gis.network_connection` lists a feeding (or branching) connection from one element to the next; each zone is one tree with one root (an element that is nobody's child), every element reachable
and at most one parent (O14). Built without a graph library.
"""
from __future__ import annotations

from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need
from ._tail import value_text


class Tree(NamedTuple):
    """parent: net_key to its parent (roots are not in it); children: net_key to the sorted list of children; roots: zone_key to root net_key; depth: net_key to the number of connections from the root;
    zone: net_key to zone_key."""
    parent: pd.Series
    children: dict[str, list[str]]
    roots: pd.Series
    depth: pd.Series
    zone: pd.Series


@staged(sources=tuple(f"gis.network_connection.{c}" for c in ("net_from", "net_to", "role", "zone_key")), oracle="py:tests/test_gis.py::test_topology")
def build_tree(network_connection: pd.DataFrame, grid_element: pd.DataFrame | None = None, *, root_types: tuple[str, ...] = ("pump_station", "substation")) -> Tree:
    """Use this when you need the directed tree of each zone (parent, children, root and depth of every element) built from the network connections.

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
    """
    if not isinstance(root_types, (tuple, list, set, frozenset)) or not root_types or not all(isinstance(x, str) for x in root_types):
        raise FrameError(f"root_types is a tuple of element types (got {value_text(root_types)})")
    _need(network_connection, ["net_from", "net_to", "role", "zone_key"], "gis.network_connection")
    c = network_connection
    if c[["net_from", "net_to", "zone_key"]].isna().any().any():
        raise FrameError("gis.network_connection has null keys")
    if c.duplicated(["net_from", "net_to"]).any():
        raise FrameError("gis.network_connection lists a connection twice")
    if c["net_to"].duplicated().any():
        raise FrameError(f"{int(c['net_to'].duplicated().sum())} elements have more than one parent (for example {c.loc[c['net_to'].duplicated(), 'net_to'].iloc[0]})")
    if (c["net_from"] == c["net_to"]).any():
        raise FrameError("an element is connected to itself")
    zone = pd.concat([c.set_index("net_from")["zone_key"], c.set_index("net_to")["zone_key"]])
    if zone.index.duplicated().any() and zone.groupby(level=0).nunique().gt(1).any():
        raise FrameError("a connection joins elements of different zones")
    zone = zone[~zone.index.duplicated()]
    parent = c.set_index("net_to")["net_from"]
    kids: dict[str, list[str]] = {}
    for a, b in zip(c["net_from"], c["net_to"]):
        kids.setdefault(a, []).append(b)
    kids = {k: sorted(v) for k, v in kids.items()}
    nodes = set(zone.index)
    roots_all = sorted(nodes - set(parent.index))
    roots: dict[str, str] = {}
    for r in roots_all:
        z = zone[r]
        if z in roots:
            raise FrameError(f"zone {z} has more than one root ({roots[z]} and {r})")
        roots[z] = r
    if set(zone.unique()) - set(roots):
        raise FrameError(f"zone {sorted(set(zone.unique()) - set(roots))[0]} has no root: the connections form a cycle")
    depth = {}
    for z, r in roots.items():
        stack = [(r, 0)]
        while stack:
            n, d = stack.pop()
            if n in depth:
                raise FrameError("the connections form a cycle")
            depth[n] = d
            stack += [(k, d + 1) for k in kids.get(n, [])]
    unreached = nodes - set(depth)
    if unreached:
        raise FrameError(f"{len(unreached)} elements cannot be reached from the root of their zone (for example {sorted(unreached)[0]})")
    if grid_element is not None:
        _need(grid_element, ["net_key", "zone_key", "element_type"], "gis.grid_element")
        if grid_element["net_key"].duplicated().any():
            raise FrameError(f"gis.grid_element lists {int(grid_element['net_key'].duplicated().sum())} elements twice (for example {grid_element.loc[grid_element['net_key'].duplicated(), 'net_key'].iloc[0]})")
        ge = grid_element.set_index("net_key")
        unknown = sorted(nodes - set(ge.index))
        if unknown:
            raise FrameError(f"{len(unknown)} connected elements are not in grid_element (for example {unknown[0]})")
        missing = sorted(set(ge.index) - nodes)
        if missing:
            raise FrameError(f"{len(missing)} elements are in no connection (for example {missing[0]})")
        wrong = [(z, r) for z, r in roots.items() if r not in ge.index or ge.at[r, "element_type"] not in root_types]
        if wrong:
            raise FrameError(f"the root {wrong[0][1]} of zone {wrong[0][0]} is not one of {', '.join(root_types)}")
        if (ge.loc[sorted(nodes & set(ge.index)), "zone_key"] != zone.reindex(sorted(nodes & set(ge.index))).to_numpy()).any():
            raise FrameError("an element is connected in another zone than its own")
    return Tree(parent.sort_index(), kids, pd.Series(roots).sort_index(), pd.Series(depth).sort_index(), zone.sort_index())


@staged(sources=tuple(f"gis.network_connection.{c}" for c in ("net_from", "net_to")), oracle="py:tests/test_gis.py::test_topology")
def trace(tree: Tree, net_key: str, direction: str = "downstream") -> list[str]:
    """Use this when you need the elements downstream or upstream of one element of a tree built by build_tree.

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
    """
    if not isinstance(tree, Tree):
        raise FrameError(f"tree must be the result of build_tree (got {type(tree).__name__})")
    if direction not in ("downstream", "upstream"):
        raise FrameError(f"direction is 'downstream' or 'upstream' (got {value_text(direction)})")
    try:
        known = net_key in tree.depth.index
    except TypeError:
        known = False
    if not known:
        raise FrameError(f"{net_key!r} is not in the tree")
    if direction == "upstream":
        out, cur = [], net_key
        while cur in tree.parent.index:
            cur = tree.parent[cur]
            out.append(cur)
            if len(out) > len(tree.parent):
                raise FrameError("the tree has a parent cycle")
        return out
    out, level = [], tree.children.get(net_key, [])
    while level:
        out += level
        if len(out) > len(tree.depth):
            raise FrameError("the tree has a child cycle")
        level = sorted(k for n in level for k in tree.children.get(n, []))
    return out
