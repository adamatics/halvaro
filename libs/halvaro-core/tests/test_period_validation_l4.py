"""Boundaries of the validation added by lane L4 (L4.3, #546): a one day period is valid, a reversed period is refused, a timestamp is a date for period_of."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core


def test_a_period_of_one_day_is_valid_and_counts_that_day_when_it_is_a_working_day():
    persons = pd.DataFrame({"emp_key": ["EMP-X"], "region": ["DK"]})
    leave = pd.DataFrame({"emp_key": [], "start": [], "end": []})
    monday = dt.date(2026, 3, 9)                         # a Monday, no public holiday in Denmark: one working day by hand
    out = core.net_working_days(persons, leave, monday, monday)
    assert out["working_days"].tolist() == [1] and out["net_days"].tolist() == [1]
    saturday = dt.date(2026, 3, 14)                      # a Saturday: no working day
    assert core.net_working_days(persons, leave, saturday, saturday)["working_days"].tolist() == [0]


def test_a_period_that_ends_the_day_before_it_starts_is_refused():
    persons = pd.DataFrame({"emp_key": ["EMP-X"], "region": ["DK"]})
    leave = pd.DataFrame({"emp_key": [], "start": [], "end": []})
    with pytest.raises(core.FrameError, match="is before start"):
        core.net_working_days(persons, leave, dt.date(2026, 3, 9), dt.date(2026, 3, 8))


def test_period_of_reads_a_date_and_a_timestamp_alike_and_refuses_a_number():
    assert core.period_of(dt.date(2026, 3, 31)) == core.period_of(pd.Timestamp("2026-03-31 23:59")) == "2026-03"
    with pytest.raises(core.PeriodError):
        core.period_of(202603)
