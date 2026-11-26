"""Third round (L4.3, #562): one test for each input check that no earlier test caught when it was removed or loosened."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core


def _release(**over):
    row = {"release": ["r1"], "now": ["2026-11-30"], "generated_at": ["2026-12-01 08:00:00"], "base_seed": ["s"], "increment": [2]}
    row.update(over)
    return {"a": pd.DataFrame(row)}


def test_release_now_valid_row_still_works():
    info = core.release_now(_release())
    assert (info.now, info.increment) == (dt.date(2026, 11, 30), 2)


@pytest.mark.parametrize("bad", [None, [1, 2], {"k": 1}])
def test_release_now_increment_of_the_wrong_type_is_the_frame_error(bad):
    with pytest.raises(core.FrameError, match="increment must be a whole number"):
        core.release_now(_release(increment=pd.Series([bad], dtype=object)))


@pytest.mark.parametrize("col", ["now", "generated_at"])
@pytest.mark.parametrize("bad", ["not a date", [1, 2]])
def test_release_now_names_the_date_column_that_is_not_a_date(col, bad):
    with pytest.raises(core.FrameError, match=f"data_release.{col} must be a date"):
        core.release_now(_release(**{col: pd.Series([bad], dtype=object)}))


def _leave(start, end):
    return pd.DataFrame({"emp_key": ["p1"], "start": [start], "end": [end]})


def _persons():
    return pd.DataFrame({"emp_key": ["p1"], "region": ["DK"]})


def test_net_working_days_valid_leave_still_works():
    out = core.net_working_days(_persons(), _leave(pd.Timestamp("2026-03-03"), pd.Timestamp("2026-03-04")), dt.date(2026, 3, 2), dt.date(2026, 3, 6))
    assert out["leave_days"].tolist() == [2] and out["net_days"].tolist() == [3]     # Mon-Fri 2-6 March: 5 days, leave Tue+Wed


@pytest.mark.parametrize("start, end, side", [(pd.NaT, pd.Timestamp("2026-03-04"), "no start"), (pd.Timestamp("2026-03-03"), pd.NaT, "no end")])
def test_net_working_days_a_null_leave_date_names_the_missing_side(start, end, side):
    with pytest.raises(core.FrameError, match=side):
        core.net_working_days(_persons(), _leave(start, end), dt.date(2026, 3, 2), dt.date(2026, 3, 6))


def test_line_with_gaps_valid_input_still_works():
    out = core.line_with_gaps([1, 2, 3, 6, 7], [10, 20, 30, 60, 70])
    assert out["y"].isna().sum() == 1 and out["x"].tolist() == [1.0, 2.0, 3.0, 4.5, 6.0, 7.0]


@pytest.mark.parametrize("name, args", [("y", ([1, 2, 3], "abc")), ("y", ([1, 2, 3], b"abc")), ("y", ([1, 2, 3], 5)), ("x", ("abc", [1, 2, 3])), ("x", (5, [1, 2, 3]))])
def test_line_with_gaps_names_the_argument_that_is_text_or_a_scalar(name, args):
    with pytest.raises(core.FrameError, match=f"^{name} must be a list, array or Series"):
        core.line_with_gaps(*args)


@pytest.mark.parametrize("x", [[b"a", b"b", b"c"], [1.5, True, 2.5], [1, True, 2], [True, False, True], ["a", "b", "c"]])
def test_line_with_gaps_x_that_is_not_numbers_or_dates_is_the_frame_error(x):
    with pytest.raises(core.FrameError, match="x must hold numbers or dates"):
        core.line_with_gaps(x, [1.0, 2.0, 3.0])


@pytest.mark.parametrize("interval", [1, 1.5, "1 day"])
def test_line_with_gaps_dates_need_a_timedelta_interval(interval):
    x = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    with pytest.raises(core.FrameError, match="interval must be a timedelta when x holds dates"):
        core.line_with_gaps(x, [1.0, 2.0, 3.0], interval=interval)
    assert core.line_with_gaps(x, [1.0, 2.0, 3.0], interval=pd.Timedelta(days=1))["y"].isna().sum() == 1     # the step of 3 days is a gap


@pytest.mark.parametrize("interval", [dt.timedelta(days=1), pd.Timedelta(days=1), pd.Timedelta(days=1).to_timedelta64(), "1", [1]])
def test_line_with_gaps_numbers_need_a_number_interval(interval):
    with pytest.raises(core.FrameError, match="interval must be a number when x holds numbers"):
        core.line_with_gaps([1, 2, 4], [1.0, 2.0, 3.0], interval=interval)
    assert core.line_with_gaps([1, 2, 4], [1.0, 2.0, 3.0], interval=1)["y"].isna().sum() == 1
