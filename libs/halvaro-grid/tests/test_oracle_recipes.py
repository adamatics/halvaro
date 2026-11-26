"""Oracle of grid_strain_answer: the answer is the four inputs carried over plus two lists of keys; every expected value is written by hand or derived from the stored tables with plain pandas, never from the function."""
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")

# words that must not reach the delivery side through the key lists: stock, order, price, cost, money, credit and intent
KEPT_OUT = ("stock", "order", "price", "cost", "amount", "money", "credit", "intent")


def _hand_inputs():
    strained = pd.DataFrame({"net_key": ["N3", "N1", "N2", "N4"], "zone_key": ["Z4", "Z2", "Z2", "Z4"], "strained": pd.array([True, False, pd.NA, True], dtype="boolean"),
                             "load_strained": pd.array([pd.NA, False, pd.NA, True], dtype="boolean")}, index=[30, 10, 20, 40])
    zone = pd.DataFrame({"zone_key": ["Z4", "Z2", "Z4"], "cus_key": ["C2", "C1", "C3"], "n_elements": [5, 7, 2], "n_strained": [2, 0, 1]}, index=[7, 8, 9])
    part_use = pd.DataFrame({"itm_key": ["I9", "I1"], "units": [3.0, 1.5]})
    issued = pd.DataFrame({"itm_key": ["I2", "I1", "I3", "I1", "I4", "I5", "I6", "I7"], "uom": ["pcs", "pcs", "pcs", "m", "pcs", "pcs", "pcs", "pcs"],
                           "units": [1.0, 2.0, 0.0, 5.0, -1.0, float("nan"), 0.001, 0.0]})
    return strained, zone, part_use, issued


def test_oracle_grid_strain_answer_hand_worked_pieces_and_key_lists():
    """route: hand frames of four, three, two and eight rows; the carried frames are compared row for row with the inputs and the two key lists are written down by hand."""
    strained, zone, part_use, issued = _hand_inputs()
    copies = [f.copy() for f in (strained, zone, part_use, issued)]
    a = grid.grid_strain_answer(strained, zone, part_use, issued, context=M12)
    for f, c in zip((strained, zone, part_use, issued), copies):
        pd.testing.assert_frame_equal(f, c)
    # no row is lost or added, the values are those of the input, unknown strain stays unknown
    pd.testing.assert_frame_equal(a.strained, strained.reset_index(drop=True))
    pd.testing.assert_frame_equal(a.zone_summary, zone.reset_index(drop=True))
    pd.testing.assert_frame_equal(a.part_use, part_use.reset_index(drop=True))
    assert len(a.strained) == 4 and len(a.zone_summary) == 3 and len(a.part_use) == 2
    assert a.strained["strained"].isna().sum() == 1 and a.strained["load_strained"].isna().sum() == 2, "the unknown stays unknown"
    # the critical items that were issued: units above zero (zero, negative, null and 0.001 as the edge), once each, sorted; the zones once each, sorted
    assert a.item_keys == ("I1", "I2", "I6"), "I1 is issued in two units of measure; I3 and I7 have zero units, I4 negative, I5 null; 0.001 counts"
    assert a.zone_keys == ("Z2", "Z4"), "the zones of the summary, once each"
    assert isinstance(a.item_keys, tuple) and isinstance(a.zone_keys, tuple) and all(type(k) is str for k in a.item_keys + a.zone_keys)
    assert a.labels == ("synthetic data",)
    assert a._fields == ("strained", "zone_summary", "part_use", "item_keys", "zone_keys", "labels")
    # nothing issued: no item to ask about, the zones are still listed
    none = grid.grid_strain_answer(strained, zone, part_use, issued.assign(units=0.0), context=M12)
    assert none.item_keys == () and none.zone_keys == ("Z2", "Z4")
    # no zone rows: no zone keys
    nozone = grid.grid_strain_answer(strained, zone.iloc[:0], part_use, issued, context=M12)
    assert nozone.zone_keys == () and len(nozone.zone_summary) == 0 and nozone.item_keys == ("I1", "I2", "I6")
    # the words that must not reach the key lists, in each of the four inputs
    for word in KEPT_OUT:
        for where in WHERE:
            _assert_refused(word, where)
    test_oracle_grid_strain_answer_whole_words_only_and_null_keys()


WHERE = ("strained", "zone_summary", "part_use", "critical_issued")


def _assert_refused(word, where):
    strained, zone, part_use, issued = _hand_inputs()
    frames = {"strained": strained, "zone_summary": zone, "part_use": part_use, "critical_issued": issued}
    frames[where] = frames[where].assign(**{f"unit_{word}": 1.0})
    with pytest.raises(FrameError, match=f"{where}.unit_{word}"):
        grid.grid_strain_answer(frames["strained"], frames["zone_summary"], frames["part_use"], frames["critical_issued"], context=M12)


@pytest.mark.parametrize("word", KEPT_OUT)
@pytest.mark.parametrize("where", WHERE)
def test_oracle_grid_strain_answer_refuses_stock_order_price_cost_money_credit_and_intent_columns(word, where):
    """route: each word that must stay out of the key lists added as a column of each of the four inputs in turn; the answer must be refused and name the column."""
    _assert_refused(word, where)


def test_oracle_grid_strain_answer_whole_words_only_and_null_keys():
    """route: column names that contain a forbidden word only as part of a longer word are accepted; a null item key or zone key is refused, as is a missing column."""
    strained, zone, part_use, issued = _hand_inputs()
    ok = grid.grid_strain_answer(strained, zone.assign(reorder_level=1.0, border_km=2.0), part_use.assign(postcode="x"), issued.assign(costume=1), context=M12)
    assert ok.item_keys == ("I1", "I2", "I6") and ok.zone_keys == ("Z2", "Z4"), "reorder, border, postcode and costume are not the words order, po and cost"
    with pytest.raises(FrameError, match="null"):
        grid.grid_strain_answer(strained, zone, part_use, issued.assign(itm_key=[None] + issued["itm_key"].tolist()[1:]), context=M12)
    with pytest.raises(FrameError, match="null"):
        grid.grid_strain_answer(strained, zone.assign(zone_key=[None, "Z2", "Z4"]), part_use, issued, context=M12)
    for pos, drop in enumerate(("strained", "n_strained", "units", "units")):
        args = [strained, zone, part_use, issued]
        args[pos] = args[pos].drop(columns=drop)
        with pytest.raises(FrameError, match=drop):
            grid.grid_strain_answer(*args, context=M12)
