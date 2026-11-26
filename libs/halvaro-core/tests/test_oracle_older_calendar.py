"""Oracles of lane P1 (P1.4a) for halvaro.core.calendar.public_holidays and working_days, which had a pointer to a generator test: the holidays are written by hand per year and region (the lists
of the L1 calendar oracle plus 2024, the first year without Store bededag), and the working days are counted with numpy business days."""
import datetime as dt
import random

import numpy as np
import pytest

import halvaro.core as core
from test_oracle_calendar import HOLIDAYS

D = dt.date
HAND = dict(HOLIDAYS)
HAND[("DK", 2024)] = [D(2024, 1, 1), D(2024, 3, 28), D(2024, 3, 29), D(2024, 3, 31), D(2024, 4, 1), D(2024, 5, 9), D(2024, 5, 19), D(2024, 5, 20), D(2024, 12, 25), D(2024, 12, 26)]
HAND[("DE", 2024)] = [D(2024, 1, 1), D(2024, 3, 29), D(2024, 4, 1), D(2024, 5, 1), D(2024, 5, 9), D(2024, 5, 20), D(2024, 10, 3), D(2024, 10, 31), D(2024, 12, 25), D(2024, 12, 26)]
REGIONS = ("DK", "DE-HH", "DE-NI")


def _hand(region, year):
    return HAND[("DK" if region == "DK" else "DE", year)]


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("year", [2023, 2024, 2025, 2026])
def test_public_holidays_oracle_the_set_of_a_year_equals_the_hand_list(region, year):
    """halvaro.core.calendar.public_holidays: the whole set of public holidays of 2023, 2024, 2025 and 2026 in Denmark, Hamburg and Lower Saxony equals the list written by hand from the Easter
    date (Easter Sunday and Monday, and the other Sundays and Mondays that are holidays, included in the Danish lists); Store bededag is in the 2023 list and not in 2024, Reformationstag is in the German lists; the answer is a frozenset of dates inside the year."""
    got = core.public_holidays(year, region)
    assert got == frozenset(_hand(region, year)) and isinstance(got, frozenset)
    assert all(d.year == year for d in got)


def test_public_holidays_oracle_an_unknown_region_is_refused_not_answered_with_another_calendar():
    """halvaro.core.calendar.public_holidays: a region outside DK, DE-HH and DE-NI (also a country code and a lower case name) raises UnknownRegion naming the known ones."""
    for bad in ("SE", "DE", "dk", "", None):
        with pytest.raises(core.UnknownRegion, match="DK, DE-HH, DE-NI"):
            core.public_holidays(2026, bad)


@pytest.mark.parametrize("region", REGIONS)
def test_working_days_oracle_numpy_business_day_count_for_random_ranges(region):
    """halvaro.core.calendar.working_days: for 400 random ranges from 2025 to 2026 (one day, a week, a quarter, a year) both ends included, the count equals numpy's busday_count with the hand
    listed holidays; a range whose end is before its start counts 0 and still validates the region."""
    hol = np.array(_hand(region, 2025) + _hand(region, 2026), dtype="datetime64[D]")
    rng = random.Random(8)
    for _ in range(400):
        start = D(2025, 1, 1) + dt.timedelta(days=rng.randint(0, 700))
        end = start + dt.timedelta(days=rng.choice([0, 1, 6, 30, 90, 364]))
        if end > D(2026, 12, 31):
            end = D(2026, 12, 31)
        want = int(np.busday_count(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"), holidays=hol))
        assert core.working_days(start, end, region) == want, (start, end)
    assert core.working_days(D(2026, 3, 10), D(2026, 3, 9), region) == 0
    with pytest.raises(core.UnknownRegion):
        core.working_days(D(2026, 3, 10), D(2026, 3, 9), "SE")
