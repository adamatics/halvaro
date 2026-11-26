"""Oracles of halvaro.core.calendar (lane L1). Public holidays are written by hand for 2023, 2025 and 2026 (Easter Sunday 2023-04-09, 2025-04-20, 2026-04-05); working days are counted with
numpy's business day functions and the leave of the baseline is counted day by day. A second reference is the generator's own calendar module. The two cut-off years are VERIFY facts:
the tests read them through the fact ids and state the value used."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core

D = dt.date

HOLIDAYS = {                                                 # by hand, from the Easter dates above and the fixed days
    ("DK", 2023): [D(2023, 1, 1), D(2023, 4, 6), D(2023, 4, 7), D(2023, 4, 9), D(2023, 4, 10), D(2023, 5, 5), D(2023, 5, 18), D(2023, 5, 28), D(2023, 5, 29), D(2023, 12, 25), D(2023, 12, 26)],
    ("DK", 2025): [D(2025, 1, 1), D(2025, 4, 17), D(2025, 4, 18), D(2025, 4, 20), D(2025, 4, 21), D(2025, 5, 29), D(2025, 6, 8), D(2025, 6, 9), D(2025, 12, 25), D(2025, 12, 26)],
    ("DK", 2026): [D(2026, 1, 1), D(2026, 4, 2), D(2026, 4, 3), D(2026, 4, 5), D(2026, 4, 6), D(2026, 5, 14), D(2026, 5, 24), D(2026, 5, 25), D(2026, 12, 25), D(2026, 12, 26)],
    ("DE", 2023): [D(2023, 1, 1), D(2023, 4, 7), D(2023, 4, 10), D(2023, 5, 1), D(2023, 5, 18), D(2023, 5, 29), D(2023, 10, 3), D(2023, 10, 31), D(2023, 12, 25), D(2023, 12, 26)],
    ("DE", 2025): [D(2025, 1, 1), D(2025, 4, 18), D(2025, 4, 21), D(2025, 5, 1), D(2025, 5, 29), D(2025, 6, 9), D(2025, 10, 3), D(2025, 10, 31), D(2025, 12, 25), D(2025, 12, 26)],
    ("DE", 2026): [D(2026, 1, 1), D(2026, 4, 3), D(2026, 4, 6), D(2026, 5, 1), D(2026, 5, 14), D(2026, 5, 25), D(2026, 10, 3), D(2026, 10, 31), D(2026, 12, 25), D(2026, 12, 26)],
}
YEARS = (2023, 2025, 2026)
REGIONS = ("DK", "DE-HH", "DE-NI")


def _hand(region: str, year: int) -> list:
    return HOLIDAYS[("DK" if region == "DK" else "DE", year)]


def _all(region: str) -> list:
    return [d for y in YEARS for d in _hand(region, y)]


def test_is_working_day_oracle_the_two_cutoff_years_by_hand():
    """halvaro.core.calendar.is_working_day: Store bededag (Friday 5 May 2023) is a holiday in Denmark and its successor Friday 26 April 2024 is a working day (the fact says it is gone from 2024); Reformationstag
    (Monday 31 October 2016) is a working day in Hamburg and Lower Saxony and Wednesday 31 October 2018 is a holiday there (from 2018), and never in Denmark. 2017 is left out: that one day was a holiday in all of Germany."""
    assert core.is_working_day(D(2023, 5, 5), "DK") is False and core.is_working_day(D(2024, 4, 26), "DK") is True
    for region in ("DE-HH", "DE-NI"):
        assert core.is_working_day(D(2016, 10, 31), region) is True and core.is_working_day(D(2018, 10, 31), region) is False
    assert core.is_working_day(D(2018, 10, 31), "DK") is True


def test_cutoff_facts_have_the_values_the_hand_lists_assume():
    """halvaro.core.calendar.is_working_day: the hand lists above assume two VERIFY facts: Store bededag is a holiday until 2023 and Reformationstag in Hamburg and Lower Saxony from 2018. A changed fact must change the lists."""
    assert core.fact("legal.public_holidays.DK_store_bededag_abolished_from").value == 2024
    assert core.fact("core.calendar.DE_reformationstag_from").value == 2018


@pytest.mark.parametrize("region", REGIONS)
def test_is_working_day_oracle_hand_listed_holidays_and_numpy_business_days(region):
    """halvaro.core.calendar.is_working_day: every day of 2023, 2025 and 2026 equals numpy's business day test with the hand listed holidays of the region."""
    hol = _all(region)
    days = [d for y in YEARS for d in pd.date_range(D(y, 1, 1), D(y, 12, 31)).date]
    want = np.is_busday(np.array(days, dtype="datetime64[D]"), holidays=np.array(hol, dtype="datetime64[D]"))
    got = np.array([core.is_working_day(d, region) for d in days])
    assert (got == want).all(), [d for d, g, w in zip(days, got, want) if g != w][:5]
    assert core.is_working_day(D(2025, 12, 24), "DK") is True, "24 December is a working day in this calendar"
    assert core.is_working_day(D(2025, 6, 5), "DK") is True, "Constitution Day is not a public holiday here"


@pytest.mark.parametrize("region", REGIONS)
def test_add_working_days_oracle_numpy_business_day_offset(region):
    """halvaro.core.calendar.add_working_days: the n-th working day on or after a start equals numpy's busday_offset with the hand listed holidays; the result is a working day and
    working days from start to result are n."""
    hol = np.array(_all(region), dtype="datetime64[D]")
    rng = np.random.default_rng(5)
    for _ in range(120):
        start = D(2025, 1, 2) + dt.timedelta(days=int(rng.integers(0, 600)))          # inside 2025 and 2026, the years the hand lists cover, result before 2026-11
        n = int(rng.integers(1, 40))
        want = np.busday_offset(np.datetime64(start), n - 1, roll="forward", holidays=hol)
        got = core.add_working_days(start, n, region)
        assert np.datetime64(got) == want, (start, n)
        assert core.is_working_day(got, region) and core.working_days(start, got, region) == n
    assert core.add_working_days(D(2025, 12, 24), 2, "DK") == D(2025, 12, 29), "25 and 26 December and the weekend are skipped"
    assert core.add_working_days(D(2026, 4, 3), 1, "DK") == D(2026, 4, 7), "Good Friday, the weekend and Easter Monday are skipped"
    for bad in (0, -3):
        with pytest.raises(core.FrameError):
            core.add_working_days(D(2026, 1, 5), bad, "DK")
    with pytest.raises(core.UnknownRegion):
        core.add_working_days(D(2026, 1, 5), 1, "SE")


def test_net_working_days_oracle_hand_worked_overlap_and_edges():
    """halvaro.core.calendar.net_working_days: two overlapping leave rows count each working day once; leave that starts before the window or ends after it is cut at the edge, leave wholly outside it counts nothing; a Danish and a German person differ on 1 May; column names can be given."""
    persons = pd.DataFrame({"emp_key": ["A", "B", "C", "D"], "region": ["DK", "DE-HH", "DK", "DK"]})
    leave = pd.DataFrame({"emp_key": ["A", "A", "A", "B", "D", "D"], "start": [D(2026, 4, 27), D(2026, 4, 29), D(2026, 4, 1), D(2026, 4, 30), D(2026, 4, 20), D(2026, 5, 7)],
                          "end": [D(2026, 4, 30), D(2026, 5, 5), D(2026, 4, 2), D(2026, 5, 4), D(2026, 4, 28), D(2026, 5, 20)], "leave_type": ["holiday"] * 6})
    got = core.net_working_days(persons, leave, D(2026, 4, 27), D(2026, 5, 8)).set_index("emp_key")
    # window 27 April to 8 May 2026 has 10 weekdays; 1 May is a holiday in Hamburg only
    assert got.loc["A", "working_days"] == 10 and got.loc["B", "working_days"] == 9 and got.loc["C", "working_days"] == 10
    assert got.loc["A", "leave_days"] == 7, "27, 28, 29, 30 April, 1, 4 and 5 May; the row of 1 to 2 April is outside the window and the overlap 29 and 30 April counts once"
    assert got.loc["B", "leave_days"] == 2 and got.loc["B", "net_days"] == 7, "30 April and 4 May; 1 May is a holiday and 2 and 3 May are a weekend"
    assert got.loc["C", "leave_days"] == 0
    assert got.loc["D", "leave_days"] == 4, "20 to 28 April counts 27 and 28 April, 7 to 20 May counts 7 and 8 May: leave across the edge of the window is cut"
    renamed = core.net_working_days(persons.rename(columns={"emp_key": "who", "region": "reg"}), leave.rename(columns={"emp_key": "who"}), D(2026, 4, 27), D(2026, 5, 8), person_key="who", region_column="reg")
    assert renamed.set_index("who")["net_days"].to_dict() == got["net_days"].to_dict(), "custom column names"
    with pytest.raises(core.FrameError):
        core.net_working_days(persons.drop(columns="region"), leave, D(2026, 4, 27), D(2026, 5, 8))
    with pytest.raises(core.FrameError):
        core.net_working_days(persons, leave.drop(columns="end"), D(2026, 4, 27), D(2026, 5, 8))
