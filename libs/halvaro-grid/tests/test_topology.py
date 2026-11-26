"""Network tree (plan 5.5): hand built trees, then the baseline release (four zones, four roots)."""
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _nc(rows):
    return pd.DataFrame(rows, columns=["net_from", "net_to", "role", "zone_key"])


ROWS = [("A", "B", "feeds", "Z1"), ("A", "C", "branch", "Z1"), ("B", "D", "feeds", "Z1"), ("D", "E", "feeds", "Z1"), ("X", "Y", "feeds", "Z2")]


def test_tree_parents_children_roots_and_depth():
    t = grid.build_tree(_nc(ROWS), context=M12)
    assert t.roots.to_dict() == {"Z1": "A", "Z2": "X"} and t.parent.to_dict() == {"B": "A", "C": "A", "D": "B", "E": "D", "Y": "X"}
    assert t.children == {"A": ["B", "C"], "B": ["D"], "D": ["E"], "X": ["Y"]} and t.depth.to_dict() == {"A": 0, "B": 1, "C": 1, "D": 2, "E": 3, "X": 0, "Y": 1}
    assert t.zone.to_dict()["E"] == "Z1"
    assert grid.trace(t, "B", context=M12) == ["D", "E"] and grid.trace(t, "A", context=M12) == ["B", "C", "D", "E"], "downstream: nearest first, then by key"
    assert grid.trace(t, "E", "upstream", context=M12) == ["D", "B", "A"] and grid.trace(t, "A", "upstream", context=M12) == [] and grid.trace(t, "E", context=M12) == []
    for bad, msg in (((t, "Q"), "not in the tree"), ((t, "A", "sideways"), "downstream"), (("tree", "A"), "result of build_tree")):
        with pytest.raises(FrameError, match=msg):
            grid.trace(*bad, context=M12)


def test_tree_checks():
    with pytest.raises(FrameError, match="more than one parent"):
        grid.build_tree(_nc(ROWS + [("C", "D", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="more than one root"):
        grid.build_tree(_nc(ROWS + [("P", "Q", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="no root"):
        grid.build_tree(_nc([("A", "B", "feeds", "Z1"), ("B", "A", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="cannot be reached"):
        grid.build_tree(_nc([("A", "B", "feeds", "Z1"), ("C", "D", "feeds", "Z1"), ("D", "C", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="different zones"):
        grid.build_tree(_nc([("A", "B", "feeds", "Z1"), ("B", "C", "feeds", "Z2")]), context=M12)
    with pytest.raises(FrameError, match="connected to itself"):
        grid.build_tree(_nc([("A", "A", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="twice"):
        grid.build_tree(_nc(ROWS + [("A", "B", "feeds", "Z1")]), context=M12)
    with pytest.raises(FrameError, match="null keys"):
        grid.build_tree(_nc([("A", None, "feeds", "Z1")]), context=M12)
    ge = pd.DataFrame({"net_key": list("ABCDEXY"), "zone_key": ["Z1"] * 5 + ["Z2"] * 2, "element_type": ["pump_station", "pipe_segment", "valve", "pipe_segment", "pipe_segment", "substation", "cable_section"]})
    assert grid.build_tree(_nc(ROWS), ge, context=M12).roots.tolist() == ["A", "X"]
    with pytest.raises(FrameError, match="not one of"):
        grid.build_tree(_nc(ROWS), ge.assign(element_type="valve"), context=M12)
    with pytest.raises(FrameError, match="in no connection"):
        grid.build_tree(_nc(ROWS), pd.concat([ge, ge.iloc[:1].assign(net_key="Z")]), context=M12)
    with pytest.raises(FrameError, match="another zone"):
        grid.build_tree(_nc(ROWS), ge.assign(zone_key="Z9"), context=M12)
    assert grid.build_tree(_nc(ROWS), ge.assign(element_type="valve"), root_types=("valve",), context=M12).roots.tolist() == ["A", "X"]




def test_tree_grid_element_and_trace_edge_cases():
    ge = pd.DataFrame({"net_key": list("ABCDEXY"), "zone_key": ["Z1"] * 5 + ["Z2"] * 2, "element_type": ["pump_station", "pipe_segment", "valve", "pipe_segment", "pipe_segment", "substation", "cable_section"]})
    with pytest.raises(FrameError, match="not in grid_element"):
        grid.build_tree(_nc(ROWS + [("C", "UNKNOWN", "feeds", "Z1")]), ge, context=M12)
    with pytest.raises(FrameError, match="twice"):
        grid.build_tree(_nc(ROWS), pd.concat([ge, ge.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="root_types"):
        grid.build_tree(_nc(ROWS), ge, root_types="pump_station", context=M12)
    t = grid.build_tree(_nc(ROWS), context=M12)
    for bad in (["A"], {"A": 1}, None, 3):
        with pytest.raises(FrameError, match="not in the tree"):
            grid.trace(t, bad, context=M12)
    cyc = t._replace(parent=pd.Series({"B": "C", "C": "B"}))
    with pytest.raises(FrameError, match="cycle"):
        grid.trace(cyc._replace(depth=pd.Series({"B": 1, "C": 1})), "B", "upstream", context=M12)


def test_trace_orders_cousins_by_depth_then_key():
    rows = [("R", "B", "feeds", "Z"), ("R", "A", "feeds", "Z"), ("B", "B2", "feeds", "Z"), ("A", "A2", "feeds", "Z"), ("A", "A1", "feeds", "Z")]
    t = grid.build_tree(_nc(rows), context=M12)
    assert grid.trace(t, "R", context=M12) == ["A", "B", "A1", "A2", "B2"], "nearest first; within a level by key across parents"
    assert t.children["A"] == ["A1", "A2"]


def test_round2_trace_cousin_order_root_types_and_child_cycle():
    rows = [("R", "B", "feeds", "Z"), ("R", "A", "feeds", "Z"), ("A", "Z9", "feeds", "Z"), ("B", "C", "feeds", "Z")]
    t = grid.build_tree(_nc(rows), context=M12)
    assert grid.trace(t, "R", context=M12) == ["A", "B", "C", "Z9"], "the second level is sorted across parents, not parent by parent"
    for bad in (5, None, (), ["x", 3]):
        with pytest.raises(FrameError, match="root_types"):
            grid.build_tree(_nc(ROWS), root_types=bad, context=M12)
    loop = t._replace(children={"R": ["A"], "A": ["R"]})
    with pytest.raises(FrameError, match="cycle"):
        grid.trace(loop, "R", context=M12)
