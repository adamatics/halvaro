"""Oracle of element_age: ages counted by hand in days over 365.25, and a plain python loop over the stored elements; the function is never used to compute an expected value."""
import datetime as dt

import pandas as pd

import halvaro.grid as grid
from halvaro.core import Context, fact

M12 = Context(stage="month12", role="r")


def _ge(rows):
    return pd.DataFrame(rows, columns=["install_year", "status", "commissioned_date"])




def test_oracle_element_age_hand_worked_days_over_365_25():
    """route: a hand worked example on 1 January 2026, each age written down from a day count (14610 days is 40 years with ten leap days, and so on)."""
    ge = _ge([(1986, "in_service", "1986-01-01"),          # 14610 days = 40.0 exactly
              (1986, "in_service", "1986-01-02"),          # 14609 days = 39.997, two decimals: 40.0
              (1986, "in_service", "1986-01-17"),          # 14594 days = 39.956: 39.96
              (2000, "in_service", "2000-07-01"),          # 9315 days = 25.503: 25.5
              (2010, "in_service", None),                  # no date: 1 January 2010, 5844 days = 16.0
              (2025, "in_service", "2025-12-31"),          # 1 day = 0.0027: 0.0
              (2026, "in_service", "2026-01-01"),          # commissioned on the date: 0.0
              (2026, "in_service", "2026-01-02"),          # commissioned after the date: no age
              (2000, "planned", "2000-07-01"),             # not in service: no age
              (2000, "out_of_service", "2000-07-01"),
              (None, "in_service", None),                  # nothing to count from
              (2016, "in_service", "2016-02-29")])         # 3594 days = 9.84
    ge.index = pd.Index(list("abcdefghijkl"))
    before = ge.copy()
    a = grid.element_age(ge, "2026-01-01", context=M12)
    assert a.name == "age_years" and a.index.tolist() == list("abcdefghijkl"), "the index of the frame, the name age_years"
    want = [40.0, 40.0, 39.96, 25.5, 16.0, 0.0, 0.0, None, None, None, None, 9.84]
    for k, w in zip(a.index, want):
        if w is None:
            assert pd.isna(a[k]), f"row {k} has no age"
        else:
            assert a[k] == w, f"row {k}"
    pd.testing.assert_frame_equal(ge, before)
    # the commissioning date wins over the install year; the install year is used only without a date
    assert grid.element_age(_ge([(1900, "in_service", "2000-07-01")]), "2026-07-01", context=M12).iloc[0] == 26.0, "9496 days = 25.9986: 26.0"
    assert grid.element_age(_ge([(2024, "in_service", "2024-02-29")]), "2024-02-29", context=M12).iloc[0] == 0.0
    assert grid.element_age(_ge([(1999, "in_service", "1999-12-31")]), "2000-12-30", context=M12).iloc[0] == 1.0, "365 days over a leap year: 0.9993 shows as 1.0"
    # the age never falls when the date moves on
    later = grid.element_age(ge, "2030-06-15", context=M12)
    ok = a.notna()
    assert (later[ok] > a[ok]).all() and pd.notna(later["h"]) and later[["i", "j", "k"]].isna().all(), "later date: older elements, the element commissioned on 2 January now has an age, the others still have none"


def test_oracle_element_age_default_date_is_the_fact_world_now():
    """route: the date of the fact world.now read here, the age of two elements counted by hand from 1 January 2000 and from 4 April 1957."""
    now = pd.Timestamp(fact("world.now").value).date()
    ge = _ge([(2000, "in_service", None), (1957, "in_service", "1957-04-04")])
    got = grid.element_age(ge, context=M12).tolist()
    want = [round((now - dt.date(2000, 1, 1)).days / 365.25, 2), round((now - dt.date(1957, 4, 4)).days / 365.25, 2)]
    assert got == want, f"default date world.now = {now}"
    assert got == grid.element_age(ge, now.isoformat(), context=M12).tolist(), f"the default is the date world.now = {now}"
