"""Regional calendar: public holidays, working days and leave netting. Same rules as the generator, no silent fallback to another region."""
from __future__ import annotations

import datetime as dt
import functools
from typing import Sequence

import numpy as np
import pandas as pd

from . import snapshot
from .errors import FrameError, UnknownRegion
from .facts import fact
from .registry import function

REGIONS = ("DK", "DE-HH", "DE-NI")
_FACTS = ("legal.public_holidays.DK_store_bededag_abolished_from", "legal.public_holidays.DE_reformationstag_from")


def _easter(year: int) -> dt.date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * el) // 433
    month = (h + el - 7 * m + 90) // 25
    return dt.date(year, month, (h + el - 7 * m + 114) % 31 + 1)


@functools.lru_cache(maxsize=None)
def _holidays(year: int, region: str) -> frozenset[dt.date]:
    e = _easter(year)
    d = lambda n: e + dt.timedelta(days=n)       # noqa: E731
    hol = {dt.date(year, 1, 1), d(-2), d(1), d(39), dt.date(year, 12, 25), dt.date(year, 12, 26)}
    if region == "DK":
        hol |= {d(-3), d(0), d(49), d(50)}
        if year < fact("legal.public_holidays.DK_store_bededag_abolished_from").value:
            hol.add(d(26))                        # Store bededag (VERIFY)
    else:                                         # DE-HH and DE-NI share one rule set, as in the generator
        hol |= {dt.date(year, 5, 1), d(50), dt.date(year, 10, 3)}
        if year >= fact("legal.public_holidays.DE_reformationstag_from").value:
            hol.add(dt.date(year, 10, 31))
    return frozenset(hol)


@function(facts=_FACTS, oracle="py:../libs/halvaro-core/tests/test_oracle_older_calendar.py::test_public_holidays_oracle_the_set_of_a_year_equals_the_hand_list")
def public_holidays(year: int, region: str) -> frozenset[dt.date]:
    """Use this when you need the public holidays of a year in one of the three regions.

    Rule: the dates are computed from the Easter date and the fixed dates of the region. The parameters are provisional (VERIFY) and the functions that read them carry that status.

    Args:
        year: The calendar year.
        region: DK, DE-HH or DE-NI.

    Returns:
        frozenset: the holidays as datetime.date values, all in the year.

    Raises:
        UnknownRegion: the region is none of DK, DE-HH and DE-NI.

    Example:
        >>> from halvaro.core import public_holidays
        >>> days = public_holidays(2026, "DK")
        >>> all(d.year == 2026 for d in days), type(days).__name__
        (True, 'frozenset')
        >>> public_holidays(2026, "XX")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.UnknownRegion: region 'XX' is unknown; use one of DK, DE-HH, DE-NI
    """
    if region not in REGIONS:
        raise UnknownRegion(f"region {region!r} is unknown; use one of {', '.join(REGIONS)}")
    return _holidays(year, region)


@function(sources=("hr.site.site_key", "hr.site.country"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_calendar_repo.py::test_region_of_oracle_baseline_sites_and_teams")
def region_of(site_key: str | None = None, *, country: str | None = None) -> str:
    """Use this when you need the calendar region (DK, DE-HH or DE-NI) of a site or of a country with one region.

    Rule: a site key gives the region of that site. A country gives its region only when it has exactly one (Denmark); Germany has two, so the site key of the person's team is needed.

    Args:
        site_key: The key of a site, for example "SITE-05". Optional.
        country: DK, when no site key is given.

    Returns:
        str: the region.

    Raises:
        UnknownRegion: the site key is not a known site, the country is DE (two regions, pass the site key) or the country has no region.

    Example:
        >>> from halvaro.core import region_of
        >>> region_of("SITE-05"), region_of(country="DK")
        ('DE-HH', 'DK')
        >>> region_of(country="DE")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.UnknownRegion: country DE has two regions (DE-HH, DE-NI); pass the site key of the person's team
    """
    regions: dict[str, str] = snapshot.load()["regions"]
    if site_key is not None:
        if site_key not in regions:
            raise UnknownRegion(f"site {site_key!r} has no region; known sites: {', '.join(sorted(regions))}")
        return regions[site_key]
    if country == "DK":
        return "DK"
    if country == "DE":
        raise UnknownRegion("country DE has two regions (DE-HH, DE-NI); pass the site key of the person's team")
    raise UnknownRegion(f"country {country!r} has no region; pass a site key")


@function(facts=_FACTS, oracle="py:../libs/halvaro-core/tests/test_oracle_calendar.py::test_is_working_day_oracle_hand_listed_holidays_and_numpy_business_days")
def is_working_day(day: dt.date, region: str) -> bool:
    """Use this when you need to know whether a date is a working day in a region.

    Rule: a working day is Monday to Friday that is no public holiday of the region. The holidays come from public_holidays, which carries the status of the facts it reads (VERIFY).

    Args:
        day: The date.
        region: DK, DE-HH or DE-NI.

    Returns:
        bool: True on a working day, False on a weekend or a public holiday.

    Raises:
        UnknownRegion: the region is none of DK, DE-HH and DE-NI.

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import is_working_day
        >>> is_working_day(dt.date(2026, 3, 11), "DK"), is_working_day(dt.date(2026, 3, 14), "DK")
        (True, False)
    """
    return day.weekday() < 5 and day not in public_holidays(day.year, region)


@function(facts=_FACTS, oracle="py:../libs/halvaro-core/tests/test_oracle_older_calendar.py::test_working_days_oracle_numpy_business_day_count_for_random_ranges")
def working_days(start: dt.date, end: dt.date, region: str) -> int:
    """Use this when you need the number of working days between two dates in a region, both days included.

    Rule: each day of the range is counted when is_working_day is true for the region. A range whose end is before its start has no days and the result is zero.

    Args:
        start: First day of the range.
        end: Last day of the range.
        region: DK, DE-HH or DE-NI.

    Returns:
        int: the number of working days in [start, end].

    Raises:
        UnknownRegion: the region is none of DK, DE-HH and DE-NI, also for an empty range.

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import working_days
        >>> working_days(dt.date(2026, 3, 9), dt.date(2026, 3, 13), "DK")
        5
    """
    public_holidays(start.year, region)           # validates the region even for an empty range
    return sum(is_working_day(start + dt.timedelta(days=i), region) for i in range(max(0, (end - start).days + 1)))


@function(facts=_FACTS, oracle="py:../libs/halvaro-core/tests/test_oracle_calendar.py::test_add_working_days_oracle_numpy_business_day_offset")
def add_working_days(start: dt.date, n: int, region: str) -> dt.date:
    """Use this when you need the date that is a number of working days from a start date, the start date counting as the first when it is a working day.

    Rule: the n-th working day on or after start. Weekends and the public holidays of the region are skipped.

    Args:
        start: The first day to look at.
        n: Which working day, 1 or more. With 1 the result is the start itself when it is a working day.
        region: DK, DE-HH or DE-NI.

    Returns:
        datetime.date: the n-th working day on or after start.

    Raises:
        FrameError: n is less than 1.
        UnknownRegion: the region is none of DK, DE-HH and DE-NI.

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import add_working_days
        >>> friday = dt.date(2026, 3, 13)
        >>> add_working_days(friday, 1, "DK"), add_working_days(friday, 2, "DK")
        (datetime.date(2026, 3, 13), datetime.date(2026, 3, 16))
    """
    if n < 1:
        raise FrameError("n must be 1 or more")
    day, count = start, 0
    while True:
        count += is_working_day(day, region)
        if count == n:
            return day
        day += dt.timedelta(days=1)


@function(sources=("hr.leave_record.start", "hr.leave_record.end", "hr.leave_record.leave_type"), facts=_FACTS, oracle="py:../libs/halvaro-core/repo_tests/test_oracle_calendar_repo.py::test_net_working_days_oracle_baseline_leave_counted_day_by_day")
def net_working_days(persons: pd.DataFrame, leave: pd.DataFrame, start: dt.date, end: dt.date, *, person_key: str = "emp_key", region_column: str = "region",
                     leave_types: Sequence[str] | None = None) -> pd.DataFrame:
    """Use this when you need, per person, the working days of a period, the leave days that fall on working days and the days left after leave.

    Rule: working days are counted per person with is_working_day for the region of that person, from start to end, both days included, and carry the status of the facts that calendar reads (VERIFY). A leave record covers its start and end days both included; the records of one person are merged day by day, so overlapping leave is counted once, and only days that are also working days count as leave days. Leave days outside the period are ignored. net_days is working_days minus leave_days.

    Args:
        persons: One row per person with the person key and the region, for example DK.
        leave: Leave records with the person key, start, end and, when leave_types is used, leave_type.
        start: First day of the period.
        end: Last day of the period; it must not be before start (an empty range fails inside numpy).
        person_key: The name of the person key column in both frames. Optional, default emp_key.
        region_column: The name of the region column in persons. Optional, default region.
        leave_types: The leave types to count. Optional; without it every record counts.

    Returns:
        pandas.DataFrame: one row per row of persons, in that order, with the columns person_key, region_column, working_days, leave_days and net_days (whole numbers).

    Raises:
        FrameError: persons lacks the person key or the region column, leave lacks the person key, start or end, end is before start, or a leave record that is read has a null start or end.
        UnknownRegion: a region in persons is none of DK, DE-HH and DE-NI.
        KeyError: leave_types is given but leave has no leave_type column.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import net_working_days
        >>> persons = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "region": ["DK", "DK"]})
        >>> leave = pd.DataFrame({"emp_key": ["EMP-000001"] * 3,
        ...                       "start": [dt.date(2026, 3, 10), dt.date(2026, 3, 11), dt.date(2026, 3, 14)],
        ...                       "end": [dt.date(2026, 3, 11), dt.date(2026, 3, 12), dt.date(2026, 3, 15)]})
        >>> net_working_days(persons, leave, dt.date(2026, 3, 9), dt.date(2026, 3, 15))
              emp_key region  working_days  leave_days  net_days
        0  EMP-000001     DK             5           3         2
        1  EMP-000002     DK             5           0         5
    """
    for c in (person_key, region_column):
        if c not in persons.columns:
            raise FrameError(f"persons frame lacks column {c}")
    for c in (person_key, "start", "end"):
        if c not in leave.columns:
            raise FrameError(f"leave frame lacks column {c}")
    lv = leave if leave_types is None else leave[leave["leave_type"].isin(list(leave_types))]
    if pd.Timestamp(end) < pd.Timestamp(start):
        raise FrameError(f"end {end} is before start {start}; pass the first day and the last day of the period")
    days = pd.date_range(start, end).date
    n = len(days)
    wd = {r: np.array([is_working_day(d, r) for d in days]) for r in sorted(persons[region_column].unique())}
    spans = {k: g for k, g in lv.groupby(person_key)}
    rows = []
    for p, r in persons[[person_key, region_column]].itertuples(index=False):
        mask = np.zeros(n, dtype=bool)
        if p in spans:
            for s, e in zip(pd.to_datetime(spans[p]["start"]).dt.date, pd.to_datetime(spans[p]["end"]).dt.date):
                if pd.isna(s) or pd.isna(e):
                    raise FrameError(f"leave records need a start and an end date; a record of {person_key} {p} has {'no start' if pd.isna(s) else 'no end'} (null); drop the record or fill the date")
                i0, i1 = max(0, (s - start).days), min(n - 1, (e - start).days)
                if i1 >= i0:
                    mask[i0:i1 + 1] = True
        total, taken = int(wd[r].sum()), int((mask & wd[r]).sum())
        rows.append((p, r, total, taken, total - taken))
    return pd.DataFrame(rows, columns=[person_key, region_column, "working_days", "leave_days", "net_days"])
