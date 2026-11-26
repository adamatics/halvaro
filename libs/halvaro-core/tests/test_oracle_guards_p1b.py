"""Oracles of lane P1 for three small guards of halvaro-core (items N8 to N10 of the review issue of lane P1). No release needed."""
import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def test_parse_period_oracle_only_ascii_digits_make_a_period():
    """halvaro.core.periods.parse_period: a period written with fullwidth digits, Arabic-Indic digits or other digit characters raises PeriodError, while the same period in ASCII digits is read as (2026, 11)."""
    assert core.parse_period("2026-11") == (2026, 11)
    for bad in ("２０２６-11", "2026-１１", "٢٠٢٦-11"):
        with pytest.raises(core.PeriodError):
            core.parse_period(bad)


def test_join_report_oracle_an_unmatched_key_with_a_final_newline_is_an_orphan_not_a_hidden_master():
    """halvaro.core.frames.join_report: at the stage day1 an unmatched PRJ key whose master is above that stage is classed master_not_visible_at_stage, the same key with a final newline is classed orphan,
    and so is a key of an unknown shape."""
    ctx = core.Context(stage="day1", role="r")
    left = pd.DataFrame({"k": ["PRJ-000001", "PRJ-000002\n", "ZZZ"]})
    right = pd.DataFrame({"k": ["OTHER"]})
    out = core.join_report(left, right, on="k", context=ctx).report.left_only.set_index("k")["class"].to_dict()
    assert out == {"PRJ-000001": "master_not_visible_at_stage", "PRJ-000002\n": "orphan", "ZZZ": "orphan"}


@pytest.mark.parametrize("b", [0, -1, -7])
def test_rdiv_oracle_a_divisor_of_zero_or_less_is_refused(b):
    """halvaro.core.money.rdiv: a divisor of zero or a negative one raises FrameError naming it; the divisor 1 gives the numbers back and 2 rounds halves away from zero (by hand: 3 / 2 is 2, -3 / 2 is -2)."""
    with pytest.raises(core.FrameError, match="positive"):
        core.rdiv(np.array([5, -5]), b)
    assert core.rdiv(np.array([5, -5, 3, -3]), 1).tolist() == [5, -5, 3, -3]
    assert core.rdiv(np.array([3, -3]), 2).tolist() == [2, -2]
