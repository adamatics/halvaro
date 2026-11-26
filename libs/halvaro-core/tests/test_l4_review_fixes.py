"""Inputs the bodies accepted before the L4.3 checks must still give the same result (review of #562)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def _chunks():
    return [pd.DataFrame({"g": ["a", "a"], "v": [1, 2]}), pd.DataFrame({"g": ["a", "b"], "v": [4, 8]})]


@pytest.mark.parametrize("pair", [np.array(["v", "sum"]), pd.Series(["v", "sum"]), ("v", "sum"), ["v", "sum"]])
def test_reduce_chunks_accepts_any_pair_that_unpacks_into_two(pair):
    out = core.reduce_chunks(_chunks(), ["g"], {"s": pair})
    assert out["s"].tolist() == [7, 8]                    # a: 1+2+4, b: 8


@pytest.mark.parametrize("pair", ["vs", "v", ("v",), ("v", "sum", "x"), 5])
def test_reduce_chunks_refuses_what_is_not_a_pair(pair):
    with pytest.raises(core.FrameError, match="must be a pair"):
        core.reduce_chunks(_chunks(), ["g"], {"s": pair})


@pytest.mark.parametrize("interval", [True, 1])
def test_line_with_gaps_accepts_a_bool_interval_for_numbers_as_the_number_one(interval):
    out = core.line_with_gaps([1, 2, 4], [10.0, 20.0, 40.0], interval=interval)   # threshold 1.5: the step 2 breaks the line
    assert out["x"].tolist() == [1, 2, 3, 4]              # the step 2 exceeds 1.5 * 1: a null point at 2 + 1
    assert out["y"].isna().tolist() == [False, False, True, False]


def test_line_with_gaps_still_refuses_a_text_interval():
    with pytest.raises(core.FrameError, match="interval must be a number"):
        core.line_with_gaps([1, 2, 4], [1.0, 2.0, 3.0], interval="1")


def test_assert_aggregate_min_group_text_is_blamed_on_min_group_not_count_column():
    frame = pd.DataFrame({"m": [1.0], "n": [5]})
    with pytest.raises(core.FrameError, match="min_group must be a number"):
        core.assert_aggregate(frame, "m", min_group="3", count_column="n")
    core.assert_aggregate(frame, "m", min_group=5, count_column="n")              # 5 >= 5 passes as before


def test_assert_aggregate_text_count_column_keeps_its_message():
    frame = pd.DataFrame({"m": [1.0], "n": ["5"]})
    with pytest.raises(core.FrameError, match="count_column n must hold numbers"):
        core.assert_aggregate(frame, "m", min_group=2, count_column="n")


def test_release_now_infinite_increment_is_the_frame_error():
    row = {"release": ["r1"], "now": ["2026-11-30"], "generated_at": ["2026-12-01 08:00:00"], "base_seed": ["s"], "increment": [2]}
    assert core.release_now({"a": pd.DataFrame(row)}).increment == 2
    row["increment"] = [np.inf]
    with pytest.raises(core.FrameError, match="whole number"):
        core.release_now({"a": pd.DataFrame(row)})
