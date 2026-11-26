"""Property oracles of the period helpers of halvaro.core.periods (lane L1): period_of, month_start, month_end, add_months and compare_periods. The expected values come from numpy month
and day arithmetic, from integer month counts and from round trips between the functions; no baseline needed."""
import datetime as dt
import functools
import random

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core

D1 = np.timedelta64(1, "D")
PERIODS = [f"{y:04d}-{m:02d}" for y in range(1900, 2201) for m in range(1, 13)]        # 3612 periods, leap years and centuries included


def _np(p: str) -> np.datetime64:
    return np.datetime64(p, "M")


def test_month_start_and_month_end_oracle_numpy_month_arithmetic_for_every_period_1900_to_2200():
    """halvaro.core.periods.month_start and halvaro.core.periods.month_end: the first day is numpy's month cast to a day, the last day is the day before the next month; the month lengths add up to 365 or 366 a year."""
    for p in PERIODS:
        first = _np(p).astype("datetime64[D]")
        last = (_np(p) + 1).astype("datetime64[D]") - D1
        assert core.month_start(p) == first.item(), p
        assert core.month_end(p) == last.item(), p
    for y in (1900, 2000, 2023, 2024, 2100):
        days = sum((core.month_end(f"{y}-{m:02d}") - core.month_start(f"{y}-{m:02d}")).days + 1 for m in range(1, 13))
        assert days == (366 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 365), y
    assert core.month_end("2024-02") == dt.date(2024, 2, 29) and core.month_end("2100-02") == dt.date(2100, 2, 28)


def test_period_of_oracle_every_day_1950_to_2100_and_the_round_trips():
    """halvaro.core.periods.period_of: for every day from 1950 to 2100 the period is numpy's month of the day as text; the period of a period's first and last day is the period itself, and the
    day after the last day belongs to the next period; dates, datetimes and timestamps give the same period."""
    days = np.arange(np.datetime64("1950-01-01"), np.datetime64("2101-01-01"))
    for d in days:
        assert core.period_of(d.item()) == str(d.astype("datetime64[M]")), d
    rng = random.Random(3)
    for p in rng.sample(PERIODS, 300):
        assert core.period_of(core.month_start(p)) == p == core.period_of(core.month_end(p))
        assert core.period_of(core.month_end(p) + dt.timedelta(days=1)) == core.add_months(p, 1)
    assert core.period_of(dt.datetime(2026, 11, 30, 23, 59, 59, 999999)) == core.period_of(pd.Timestamp("2026-11-30 23:59:59.999999999")) == "2026-11"
    assert core.period_of(pd.Timestamp("2026-12-01 00:30", tz="Europe/Copenhagen")) == "2026-12", "a timestamp keeps its own calendar day: 00:30 on 1 December in Copenhagen is still 30 November in UTC"


def test_add_months_oracle_numpy_months_and_the_group_laws():
    """halvaro.core.periods.add_months: the result is numpy's month plus n for 5000 random periods and shifts of up to 100 years either way; zero is the identity, shifts add up, a shift and its
    inverse cancel, and a shift of one lands on the period of the day after the last day."""
    rng = random.Random(11)
    for _ in range(5000):
        p, n = rng.choice(PERIODS[12 * 10:-12 * 10]), rng.randint(-1200, 1200)
        assert core.add_months(p, n) == str(_np(p) + n), (p, n)
    for _ in range(2000):
        p, a, b = rng.choice(PERIODS[600:-600]), rng.randint(-500, 500), rng.randint(-500, 500)
        assert core.add_months(p, 0) == p
        assert core.add_months(core.add_months(p, a), b) == core.add_months(p, a + b)
        assert core.add_months(core.add_months(p, a), -a) == p
        assert core.compare_periods(core.add_months(p, a), p) == (a > 0) - (a < 0)
    for p in PERIODS[::37]:
        assert core.add_months(p, 1) == core.period_of(core.month_end(p) + dt.timedelta(days=1)), "one month on is the period of the day after the last day"
    assert core.add_months("2026-11", 2) == "2027-01" and core.add_months("2026-01", -1) == "2025-12" and core.add_months("2026-12", 12) == "2027-12"


def _key(p: str) -> int:
    y, m = int(p[:4]), int(p[5:])
    return y * 12 + m


def test_compare_periods_oracle_month_counts_antisymmetry_and_sorting():
    """halvaro.core.periods.compare_periods: the sign equals the sign of the difference of the month counts (year times twelve plus month), swapping the arguments flips it, and sorting a shuffled
    list with it gives the same order as sorting the zero padded text; equal periods compare 0."""
    rng = random.Random(5)
    for _ in range(3000):
        a, b = rng.choice(PERIODS), rng.choice(PERIODS)
        want = (_key(a) > _key(b)) - (_key(a) < _key(b))
        assert core.compare_periods(a, b) == want == -core.compare_periods(b, a)
        assert core.compare_periods(a, a) == 0
    sample = rng.sample(PERIODS, 400)
    assert sorted(sample, key=functools.cmp_to_key(core.compare_periods)) == sorted(sample)
    assert core.compare_periods("2025-12", "2026-01") == -1 and core.compare_periods("2026-02", "2025-12") == 1


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "2026-1", "202611", "26-11", "2026/11", " 2026-11", "2026-11 ", "2026-11-01", "", None, 202611, dt.date(2026, 11, 1)])
def test_period_helpers_oracle_a_text_that_is_not_a_period_is_refused(bad):
    """halvaro.core.periods.month_start, month_end, add_months and compare_periods: text that is not YYYY-MM with a month from 01 to 12 raises PeriodError in each of them."""
    for call in (lambda: core.month_start(bad), lambda: core.month_end(bad), lambda: core.add_months(bad, 1), lambda: core.compare_periods(bad, "2026-11"), lambda: core.compare_periods("2026-11", bad)):
        with pytest.raises(core.PeriodError):
            call()
