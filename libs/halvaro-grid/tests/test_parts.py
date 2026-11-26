"""Parts used (plan 5.8): hand computed use rows, then the baseline release against the parts oracle (ITM-000001 to 3)."""
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")

USE = pd.DataFrame({"tkt_key": ["T1", "T1", "T2", "T3", "T4"], "itm_key": ["I1", "I2", "I1", "I1", "I3"], "qty": [2.0, 1.0, 3.0, 4.0, 5.0], "uom": ["pcs", "pcs", "pcs", "m", "pcs"],
                    "used_on": ["2026-01-05", "2026-01-05", "2026-01-20", "2026-02-02", "2026-01-31"]})
TK = pd.DataFrame({"tkt_key": ["T1", "T2", "T3", "T4"], "net_key": ["N1", "N2", "N1", None]})
EL = pd.DataFrame({"net_key": ["N1", "N2"], "element_type": ["valve", "pump_station"]})
ITEM = pd.DataFrame({"itm_key": ["I1", "I2", "I3", "I4"], "critical": [True, False, True, True]})


def test_part_usage_sums_by_item_unit_element_type_and_month():
    r = grid.part_usage(USE, TK, EL, context=M12)
    key = r.set_index(["itm_key", "uom", "element_type", "period"])
    assert key.loc[("I1", "pcs", "valve", "2026-01"), "units"] == 2.0 and key.loc[("I1", "pcs", "pump_station", "2026-01"), "units"] == 3.0
    assert key.loc[("I1", "m", "valve", "2026-02"), "units"] == 4.0, "metres are never added to pieces"
    assert key.loc[("I3", "pcs", "none", "2026-01"), "units"] == 5.0, "off-grid ticket: no element"
    assert r.units.sum() == 15.0 and key.loc[("I1", "pcs", "valve", "2026-01"), "n_tickets"] == 1
    assert set(grid.part_usage(USE, TK, context=M12).element_type) == {"unknown", "none"}


def test_part_usage_refusals():
    with pytest.raises(FrameError, match="does not hold"):
        grid.part_usage(USE, TK.iloc[:2], EL, context=M12)
    with pytest.raises(FrameError, match="grid_element does not hold"):
        grid.part_usage(USE, TK, EL.iloc[:1], context=M12)
    with pytest.raises(FrameError, match="more than one row for a ticket, item"):
        grid.part_usage(pd.concat([USE, USE.iloc[:1]]), TK, EL, context=M12)
    with pytest.raises(FrameError, match="qty"):
        grid.part_usage(USE.assign(qty=[-1.0, 1, 1, 1, 1]), TK, EL, context=M12)
    with pytest.raises(FrameError, match="used_on"):
        grid.part_usage(USE.assign(used_on=["x", "2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"]), TK, EL, context=M12)


def test_critical_spares_use_the_flag_and_list_idle_critical_items():
    r = grid.critical_spares_issued(USE, ITEM, context=M12).set_index(["itm_key", "uom"])
    assert r.loc[("I1", "pcs"), "units"] == 5.0 and r.loc[("I1", "m"), "units"] == 4.0 and r.loc[("I3", "pcs"), "units"] == 5.0
    assert "I2" not in r.index.get_level_values(0), "I2 is not critical"
    assert r.loc[("I1", "pcs"), "n_tickets"] == 2 and str(r.loc[("I1", "pcs"), "first_used"].date()) == "2026-01-05" and str(r.loc[("I1", "pcs"), "last_used"].date()) == "2026-01-20"
    w = grid.critical_spares_issued(USE, ITEM, window=("2026-01-20", "2026-01-31"), context=M12)
    assert w[w.itm_key == "I1"].units.tolist() == [3.0] and w[w.itm_key == "I4"].units.tolist() == [0.0], "I4 is critical and not issued"
    flipped = grid.critical_spares_issued(USE, ITEM.assign(critical=[False, False, False, True]), context=M12)
    assert flipped.itm_key.tolist() == ["I4"], "no id list: the flag decides"
    with pytest.raises(FrameError, match="does not hold"):
        grid.critical_spares_issued(USE, ITEM.iloc[:1], context=M12)
    with pytest.raises(FrameError, match="nulls"):
        grid.critical_spares_issued(USE, ITEM.assign(critical=[True, None, True, True]), context=M12)
    with pytest.raises(FrameError, match="ends before"):
        grid.critical_spares_issued(USE, ITEM, window=("2026-02-01", "2026-01-01"), context=M12)


def test_stage_and_facade():
    for n in ("part_usage", "critical_spares_issued"):
        assert f"halvaro.grid.parts.{n}" in registry.registered() and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.part_usage(USE, TK, context=Context(stage="month3", role="r"))



def test_flags_infinite_quantities_window_edges_and_ticket_counts():
    with pytest.raises(FrameError, match="true or false"):
        grid.critical_spares_issued(USE, ITEM.assign(critical=["True", "False", "True", "True"]), context=M12)
    with pytest.raises(FrameError, match="qty"):
        grid.part_usage(USE.assign(qty=[float("inf"), 1, 1, 1, 1]), TK, EL, context=M12)
    w = grid.critical_spares_issued(USE, ITEM, window=("2026-01-05", "2026-01-31"), context=M12)
    assert w[w.itm_key == "I3"].units.tolist() == [5.0], "a use on the last day of the window counts"
    two_days = pd.concat([USE.iloc[:1], USE.iloc[:1].assign(used_on="2026-01-06")])
    assert grid.critical_spares_issued(two_days, ITEM, context=M12).set_index("itm_key").loc["I1", "n_tickets"] == 1, "one ticket on two days is one ticket"
    assert grid.part_usage(two_days, TK, EL, context=M12).n_tickets.tolist() == [1] and grid.part_usage(two_days, TK, EL, context=M12).n_lines.tolist() == [2]
    zero = grid.part_usage(USE.assign(qty=[0.0, 1, 1, 1, 1]), TK, EL, context=M12)
    assert zero.units.sum() == 4.0, "a use of zero units is allowed"
    cat = ITEM.assign(itm_key=ITEM.itm_key.astype("category"))
    assert len(grid.critical_spares_issued(USE.assign(itm_key=USE.itm_key.astype("category")), cat, context=M12)) == 4


def test_second_round_categorical_element_types_with_off_grid_tickets():
    cat = EL.assign(element_type=EL.element_type.astype("category"), net_key=EL.net_key.astype("category"))
    r = grid.part_usage(USE, TK.assign(net_key=TK.net_key.astype("category")), cat, context=M12)
    assert "none" in set(r.element_type) and r.units.sum() == 15.0, "off-grid tickets get 'none' also when the element type is categorical"
