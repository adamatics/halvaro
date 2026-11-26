"""Oracle tests of payroll.cost_centre_team_map: a hand worked crosswalk, and the baseline cost centres and teams against pair set differences, untouched and with seeded edits."""
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
COLS = ["table", "key", "rule", "detail"]


def _cc(rows):
    return pd.DataFrame(rows, columns=["cc_key", "team_key"])


def _team(rows):
    return pd.DataFrame(rows, columns=["team_key", "cost_centre_key"])


def _triples(frame):
    return sorted(zip(frame["table"], frame["key"], frame["rule"]))


def test_oracle_cost_centre_team_map_hand_crosswalk_in_both_directions():
    """route: hand worked crosswalk with one case of each rule on each side, and the pairs that agree or need no team, listed by hand."""
    cc = _cc([("CC-1", "T1"), ("CC-2", "T2"), ("CC-3", None), ("CC-4", "T9"), ("CC-5", None)])
    tm = _team([("T1", "CC-1"), ("T2", "CC-7"), ("T5", "CC-8"), ("T6", "CC-3"), ("T7", "CC-2")])
    cc0, tm0 = cc.copy(deep=True), tm.copy(deep=True)
    r = fin.cost_centre_team_map(cc, tm, context=M12)
    assert list(r.columns) == COLS
    assert _triples(r) == [
        ("finance.cost_centre", "CC-2", "cost_centre_team_mismatch"),        # finance says T2, hr says T2 belongs to CC-7
        ("finance.cost_centre", "CC-4", "cost_centre_without_team"),         # T9 is not an hr team
        ("hr.team", "T2", "team_without_cost_centre"),                       # CC-7 is not a finance cost centre
        ("hr.team", "T5", "team_without_cost_centre"),                       # CC-8 is not a finance cost centre
        ("hr.team", "T6", "cost_centre_team_mismatch"),                      # CC-3 exists and names no team
        ("hr.team", "T7", "cost_centre_team_mismatch"),                      # CC-2 exists and names T2
    ]
    assert len(r) == 6, "one row per violation, none for CC-1 and T1 (they agree) or for CC-3 and CC-5 (a cost centre without a team)"
    assert r.index.tolist() == list(range(6)) and r.sort_values(COLS, kind="stable").equals(r), "ordered by table, key, rule"
    detail = r.set_index(["table", "key"]).detail
    assert "T9" in detail[("finance.cost_centre", "CC-4")] and "CC-7" in detail[("hr.team", "T2")] and "T2" in detail[("hr.team", "T7")] and "CC-7" in detail[("finance.cost_centre", "CC-2")]
    pd.testing.assert_frame_equal(cc, cc0)
    pd.testing.assert_frame_equal(tm, tm0)


def test_oracle_cost_centre_team_map_agreeing_sides_and_an_extra_hr_team_for_a_cost_centre_without_a_team():
    """route: hand frames: pairs that agree give no row, a cost centre without a team is no violation by itself, an hr team that points at it is."""
    assert fin.cost_centre_team_map(_cc([("CC-1", "T1"), ("CC-2", "T2"), ("CC-3", None)]), _team([("T1", "CC-1"), ("T2", "CC-2")]), context=M12).empty
    r = fin.cost_centre_team_map(_cc([("CC-1", "T1"), ("CC-3", None)]), _team([("T1", "CC-1"), ("T3", "CC-3")]), context=M12)
    assert _triples(r) == [("hr.team", "T3", "cost_centre_team_mismatch")]
    swapped = fin.cost_centre_team_map(_cc([("CC-1", "T2"), ("CC-2", "T1")]), _team([("T1", "CC-1"), ("T2", "CC-2")]), context=M12)
    assert _triples(swapped) == [("finance.cost_centre", "CC-1", "cost_centre_team_mismatch"), ("finance.cost_centre", "CC-2", "cost_centre_team_mismatch"),
                                 ("hr.team", "T1", "cost_centre_team_mismatch"), ("hr.team", "T2", "cost_centre_team_mismatch")], "swapped partners are seen from both sides"
    assert fin.cost_centre_team_map(_cc([]), _team([]), context=M12).empty
    assert _triples(fin.cost_centre_team_map(_cc([]), _team([("T1", "CC-1")]), context=M12)) == [("hr.team", "T1", "team_without_cost_centre")]
    with pytest.raises(FrameError, match="one row per key"):
        fin.cost_centre_team_map(_cc([("CC-1", "T1"), ("CC-1", "T2")]), _team([("T1", "CC-1")]), context=M12)
    with pytest.raises(FrameError, match="one row per key"):
        fin.cost_centre_team_map(_cc([("CC-1", "T1")]), _team([("T1", "CC-1"), ("T1", "CC-2")]), context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        fin.cost_centre_team_map(_cc([("CC-1", "T1")]), _team([("T1", "CC-1")]).drop(columns="cost_centre_key"), context=M12)
