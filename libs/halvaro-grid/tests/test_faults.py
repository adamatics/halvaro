"""Faults (plan 5.7): hand computed rates, repeats and causes."""

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")


def _fe(rows):
    return pd.DataFrame(rows, columns=["tkt_key", "net_key", "fault_ts", "repeat_of_tkt_key", "cause"])


def test_fault_rate_months_baseline_window_and_ratios():
    rows = [(f"T{i}", "A" if i < 4 else "B", f"2024-0{1 + i % 2}-05 10:00", None, "wear_ageing") for i in range(8)] + [(f"W{i}", "A", "2025-12-05 10:00", None, "overload") for i in range(6)] + [(f"V{i}", "B", "2026-01-05 10:00", None, "overload") for i in range(3)]
    fe = _fe(rows)
    ge = pd.DataFrame({"net_key": ["A", "B", "C"]})
    r = grid.fault_rate(fe, ["A"], baseline=("2024-01", "2024-02"), window=("2025-12", "2026-01"), grid_element=ge, context=M12)
    assert r.group_baseline_per_month == 2.0 and r.group_window_per_month == 3.0 and r.group_ratio == 1.5, "A: 4 faults in two baseline months, 6 in the two window months"
    assert r.rest_baseline_per_month == 2.0 and r.rest_window_per_month == 1.5 and r.rest_ratio == 0.75 and r.spike_vs_rest == 2.0
    assert (r.n_group_elements, r.n_rest_elements) == (1, 2) and r.group_window_per_element_month == 3.0 and r.rest_window_per_element_month == 0.75
    assert np.isnan(grid.fault_rate(fe, ["C"], baseline=("2024-01", "2024-02"), window=("2025-12", "2026-01"), context=M12).group_ratio), "no baseline faults: no ratio"
    for kw, msg in ((dict(baseline=("2024-03", "2024-01")), "out of order"), (dict(window=("2024-02", "2024-03")), "overlap"), (dict(baseline=("x", "y")), "pair of months")):
        with pytest.raises(FrameError, match=msg):
            grid.fault_rate(fe, ["A"], context=M12, **kw)
    with pytest.raises(FrameError, match="no element"):
        grid.fault_rate(fe, [], context=M12)


def test_repeat_faults_gap_chain_and_link_agreement():
    fe = _fe([("T1", "A", "2025-01-01 08:00", None, "x"), ("T2", "A", "2025-02-15 08:00", "T1", "x"), ("T3", "A", "2025-02-15 09:00", None, "x"), ("T4", "A", "2025-04-30 08:00", None, "x"),
              ("T5", "B", "2025-01-01 08:00", None, "x"), ("T6", "B", "2025-02-16 08:00", None, "x")])
    r = grid.repeat_faults(fe, context=M12).set_index("tkt_key")
    assert r.loc["T2", "repeat"] and r.loc["T2", "gap_days"] == 45.0 and r.loc["T2", "chain_length"] == 1 and bool(r.loc["T2", "agrees"]), "exactly 45 days is a repeat"
    assert r.loc["T3", "repeat"] and r.loc["T3", "chain_length"] == 2 and r.loc["T3", "previous_tkt_key"] == "T2" and not bool(r.loc["T3", "agrees"]), "a repeat without the stored link"
    assert not r.loc["T4", "repeat"] and r.loc["T4", "chain_length"] == 0 and not r.loc["T6", "repeat"], "T6 is 46 days after T5"
    assert grid.repeat_faults(fe, gap_days=46, context=M12).set_index("tkt_key").loc["T6", "repeat"]
    assert r.index.tolist()[:2] == ["T1", "T2"] and r.loc["T1", "gap_days"] != r.loc["T1", "gap_days"]
    with pytest.raises(FrameError, match="more than one row"):
        grid.repeat_faults(pd.concat([fe, fe.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="gap_days"):
        grid.repeat_faults(fe, gap_days=-1, context=M12)


def test_fault_causes_share_window_group_and_closed_list():
    fe = _fe([("T1", "A", "2025-12-01 08:00", None, "overload"), ("T2", "A", "2025-12-02 08:00", None, "overload"), ("T3", "A", "2026-02-28 23:00", None, "wear_ageing"), ("T4", "B", "2025-12-03 08:00", None, "wear_ageing"),
              ("T5", "A", "2026-03-01 00:00", None, "insulation_breakdown"), ("T6", "A", "2025-12-04 08:00", None, None)])
    r = grid.fault_causes(fe, ["A"], window=("2025-12-01", "2026-02-28"), context=M12).set_index("cause")
    assert r.loc["overload", ["n", "share", "n_total"]].tolist() == [2, 0.5, 4] and r.loc["wear_ageing", "n"] == 1 and r.loc["unknown", "n"] == 1 and "insulation_breakdown" not in r.index
    assert grid.fault_causes(fe, context=M12).n_total.iloc[0] == 6 and grid.fault_causes(fe, "B", context=M12).cause.tolist() == ["wear_ageing"]
    with pytest.raises(FrameError, match="outside the accepted list"):
        grid.fault_causes(fe, ["A"], allowed_causes=["overload", "wear_ageing"], context=M12)
    ok = grid.fault_causes(fe.iloc[:4], ["A"], allowed_causes=["overload", "wear_ageing"], context=M12)
    assert ok.n.sum() == 3
    with pytest.raises(FrameError, match="in order"):
        grid.fault_causes(fe, window=("2026-02-28", "2025-12-01"), context=M12)
    assert grid.fault_causes(fe, ["Z"], context=M12).empty


def test_stage_registry_and_facade_for_faults():
    reg = registry.registered()
    for n in ("fault_rate", "repeat_faults", "fault_causes"):
        assert f"halvaro.grid.faults.{n}" in reg and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.repeat_faults(pd.DataFrame(), context=Context(stage="month3", role="r"))



def test_fault_causes_refuse_wording_of_intent_by_default():
    fe = _fe([("T1", "A", "2025-12-05 10:00", None, "wear_ageing"), ("T2", "A", "2025-12-06 10:00", None, "intent: deliberate damage")])
    with pytest.raises(FrameError, match="intent or blame"):
        grid.fault_causes(fe, context=M12)
    assert grid.fault_causes(fe.iloc[:1], context=M12).cause.tolist() == ["wear_ageing"]
    assert grid.fault_causes(fe, refuse_words=(), context=M12).n.sum() == 2, "the guard is a keyword"
    with pytest.raises(FrameError, match="outside the accepted list"):
        grid.fault_causes(fe, allowed_causes=["wear_ageing", "overload"], context=M12)
    with pytest.raises(FrameError, match="single text"):
        grid.fault_causes(fe, allowed_causes="wear_ageing", context=M12)
