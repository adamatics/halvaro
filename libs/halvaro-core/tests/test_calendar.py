"""C3: calendar. Values of test_easter_and_holidays plus leave netting."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core

D = dt.date


def test_public_holidays_values_of_the_generator_test():
    assert len(core.public_holidays(2025, "DK")) == 10
    assert D(2026, 10, 3) in core.public_holidays(2026, "DE-HH") and D(2026, 10, 3) not in core.public_holidays(2026, "DK")
    assert D(2025, 4, 18) in core.public_holidays(2025, "DK") and D(2025, 4, 21) in core.public_holidays(2025, "DK")   # Good Friday, Easter Monday
    assert core.public_holidays(2026, "DE-NI") == core.public_holidays(2026, "DE-HH"), "the generator keeps one German rule set"


def test_cutoffs_are_read_from_facts():
    assert len(core.public_holidays(2023, "DK")) == len(core.public_holidays(2024, "DK")) + 1, "Store bededag until 2023"
    assert D(2018, 10, 31) in core.public_holidays(2018, "DE-HH") and D(2017, 10, 31) not in core.public_holidays(2017, "DE-HH")


@pytest.mark.parametrize("region", ["DE", "SE", "dk", "", None])
def test_unknown_region_raises_instead_of_falling_back(region):
    with pytest.raises(core.UnknownRegion):
        core.public_holidays(2026, region)
    with pytest.raises(core.UnknownRegion):
        core.working_days(D(2026, 7, 1), D(2026, 7, 31), region)


def test_region_of_site_or_country():
    assert [core.region_of(s) for s in ("SITE-01", "SITE-04", "SITE-05", "SITE-06")] == ["DK", "DK", "DE-HH", "DE-NI"]
    assert core.region_of(country="DK") == "DK"
    for kw in ({"site_key": "SITE-99"}, {"country": "DE"}, {"country": "SE"}, {}):
        with pytest.raises(core.UnknownRegion):
            core.region_of(**kw)


def test_working_days():
    assert core.working_days(D(2026, 7, 1), D(2026, 7, 31), "DK") == 23
    assert core.working_days(D(2025, 10, 1), D(2025, 10, 7), "DE-HH") == 4 and core.working_days(D(2025, 10, 1), D(2025, 10, 7), "DK") == 5, "3 October 2025 is a Friday"
    assert core.working_days(D(2026, 10, 1), D(2026, 10, 7), "DE-HH") == 5, "3 October 2026 is a Saturday"
    assert core.working_days(D(2026, 7, 5), D(2026, 7, 4), "DK") == 0
    assert not core.is_working_day(D(2026, 7, 4), "DK") and core.is_working_day(D(2026, 7, 6), "DK") and not core.is_working_day(D(2025, 12, 25), "DK")
    assert core.add_working_days(D(2026, 7, 3), 1, "DK") == D(2026, 7, 3) and core.add_working_days(D(2026, 7, 3), 2, "DK") == D(2026, 7, 6)
    assert core.add_working_days(D(2025, 12, 24), 2, "DK") == D(2025, 12, 29)
    with pytest.raises(core.FrameError):
        core.add_working_days(D(2026, 7, 3), 0, "DK")


def test_net_working_days_counts_overlapping_leave_once_and_only_working_days():
    persons = pd.DataFrame({"emp_key": ["a", "b", "c"], "region": ["DK", "DK", "DE-HH"]})
    leave = pd.DataFrame({"emp_key": ["a", "a", "a", "b", "c"], "leave_type": ["holiday", "holiday", "sick", "holiday", "holiday"],
                          "start": [D(2026, 7, 6), D(2026, 7, 8), D(2026, 7, 27), D(2026, 6, 25), D(2025, 10, 2)],
                          "end": [D(2026, 7, 10), D(2026, 7, 14), D(2026, 8, 5), D(2026, 7, 3), D(2025, 10, 6)]})
    out = core.net_working_days(persons, leave, D(2026, 7, 1), D(2026, 7, 31)).set_index("emp_key")
    assert out.loc["a", ["working_days", "leave_days", "net_days"]].tolist() == [23, 7 + 5, 11], "6 to 14 July once (7 days), 27 to 31 July (5 days)"
    assert out.loc["b", "leave_days"] == 3 and out.loc["c", "leave_days"] == 0
    only = core.net_working_days(persons, leave, D(2026, 7, 1), D(2026, 7, 31), leave_types=["sick"]).set_index("emp_key")
    assert only.loc["a", "leave_days"] == 5
    de = core.net_working_days(persons, leave, D(2025, 10, 1), D(2025, 10, 7)).set_index("emp_key")
    assert de.loc["c", ["working_days", "leave_days"]].tolist() == [4, 2], "leave 2 to 6 October 2025: the holiday on the 3rd does not count"
