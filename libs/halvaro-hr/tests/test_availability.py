"""availability_hours, utilisation, allocation_hours: synthetic boundaries (Easter 2026 falls on 5 April); the baseline tests are in the closed repository."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, PeriodError, registry
from halvaro.hr.availability import HOURS_PER_DAY, allocation_hours, availability_hours, utilisation

D = dt.date
P = [(D(2026, 3, 30), D(2026, 4, 10))]            # DK: 10 weekdays minus Maundy Thursday, Good Friday, Easter Monday = 7; DE: minus Good Friday and Easter Monday = 8


def _emp(rows):
    return pd.DataFrame(rows, columns=["emp_key", "hire_date", "leave_date"])


def _term(rows):
    return pd.DataFrame(rows, columns=["emp_key", "valid_from", "valid_to", "team_key", "role_key", "fte"])


TEAM = pd.DataFrame({"team_key": ["T-DK", "T-HH", "T-NI"], "site_key": ["SITE-01", "SITE-05", "SITE-06"], "dep_key": ["DEP-A", "DEP-A", "DEP-B"]})
NOLV = pd.DataFrame({"emp_key": [], "start": [], "end": [], "leave_type": []})


def _lv(rows):
    return pd.DataFrame(rows, columns=["emp_key", "start", "end", "leave_type"])


def _av(emp, term, lv=NOLV, periods=P, **k):
    return availability_hours(emp, term, lv, TEAM, periods, **k)


def test_working_days_are_regional_and_hours_are_fte_times_hours_per_day():
    emp = _emp([("EMP-1", D(2020, 1, 1), None), ("EMP-2", D(2020, 1, 1), None), ("EMP-3", D(2020, 1, 1), None)])
    term = _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0), ("EMP-2", D(2020, 1, 1), None, "T-HH", "R", 0.5), ("EMP-3", D(2020, 1, 1), None, "T-NI", "R", 1.0)])
    a = _av(emp, term).set_index("emp_key")
    assert a.working_days.to_dict() == {"EMP-1": 7, "EMP-2": 8, "EMP-3": 8} and a.region.to_dict() == {"EMP-1": "DK", "EMP-2": "DE-HH", "EMP-3": "DE-NI"}
    assert a.hours.to_dict() == pytest.approx({"EMP-1": 7 * 7.4, "EMP-2": 8 * 0.5 * 7.4, "EMP-3": 8 * 7.4}) and (a.leave_days == 0).all()
    assert _av(emp, term, hours_per_day=8).hours.tolist() == pytest.approx([56.0, 32.0, 64.0])
    assert HOURS_PER_DAY == 7.4


def test_leave_counts_only_on_working_days_once_and_by_type():
    emp, term = _emp([("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    lv = _lv([("EMP-1", D(2026, 4, 1), D(2026, 4, 7), "holiday"), ("EMP-1", D(2026, 4, 6), D(2026, 4, 8), "sick")])
    a = _av(emp, term, lv).iloc[0]
    assert (a.working_days, a.leave_days, a.net_days) == (7, 3, 4), "1 April, 7 and 8 April are working days on leave; the 2nd, 3rd and 6th are holidays; overlap counted once"
    assert _av(emp, term, lv, leave_types=["sick"]).iloc[0].leave_days == 2
    assert _av(emp, term, lv, leave_types=[]).iloc[0].leave_days == 0
    assert _av(emp, term, _lv([("EMP-1", D(2026, 4, 4), D(2026, 4, 5), "holiday")])).iloc[0].leave_days == 0, "a weekend is not a leave day"
    assert _av(emp, term, _lv([("EMP-9", D(2026, 4, 8), D(2026, 4, 8), "sick")])).iloc[0].leave_days == 0, "leave of another person"


def test_employment_edges_are_inclusive_and_a_person_not_employed_has_no_row():
    term = _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    e = lambda h, l: _av(_emp([("EMP-1", h, l)]), term)
    assert e(D(2026, 4, 9), D(2026, 4, 9)).iloc[0].working_days == 1, "hire date and leave date both count"
    assert e(D(2026, 4, 9), None).iloc[0].working_days == 2 and e(D(2020, 1, 1), D(2026, 4, 1)).iloc[0].working_days == 3
    assert e(D(2026, 4, 11), None).empty and e(D(2020, 1, 1), D(2026, 3, 29)).empty, "hired after, left before"
    assert e(D(2026, 4, 4), D(2026, 4, 5)).empty, "employed on a weekend only: no working day, no row"
    assert _av(_emp([("EMP-1", D(2020, 1, 1), None)]), term.assign(valid_from=D(2026, 4, 9))).iloc[0].working_days == 2, "no term before the 9th: not available"


def test_a_term_change_inside_the_period_switches_fte_and_region():
    emp = _emp([("EMP-1", D(2020, 1, 1), None)])
    term = _term([("EMP-1", D(2020, 1, 1), D(2026, 4, 1), "T-DK", "R", 1.0), ("EMP-1", D(2026, 4, 2), None, "T-HH", "R", 0.5)])
    a = _av(emp, term).iloc[0]
    # 30 and 31 March, 1 April on DK terms (3 days at fte 1); 2 April onwards on DE-HH: 2, 7, 8, 9, 10 April (no Maundy Thursday in Hamburg) = 5 days at 0.5
    assert a.working_days == 8 and a.hours == pytest.approx((3 * 1.0 + 5 * 0.5) * 7.4) and a.region == "DK", "the region column is that of the first working day of the period"
    with pytest.raises(FrameError, match="overlaps"):
        _av(emp, term.assign(valid_to=[D(2026, 4, 2), None]))


def test_several_periods_and_inputs_that_are_refused():
    emp, term = _emp([("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    a = _av(emp, term, periods=[(D(2026, 4, 6), D(2026, 4, 6)), (D(2026, 4, 7), D(2026, 4, 7)), (D(2026, 4, 8), D(2026, 4, 8))])
    assert a.working_days.tolist() == [1, 1] and a.period_start.dt.day.tolist() == [7, 8], "Easter Monday has no row"
    assert _av(emp, term, periods=[]).empty
    for bad, m in ((dict(periods=[(D(2026, 4, 2), D(2026, 4, 1))]), "ends before"), (dict(periods=[D(2026, 4, 1)]), "pair"), (dict(hours_per_day=0), "hours_per_day"),
                   (dict(hours_per_day=True), "hours_per_day"), (dict(hours_per_day=25), "hours_per_day"), (dict(periods=[("x", "y")]), "not a date")):
        with pytest.raises(FrameError, match=m):
            _av(emp, term, **bad)
    with pytest.raises(FrameError, match="fte"):
        _av(emp, term.assign(fte=1.5))
    with pytest.raises(FrameError, match="teams that hr.team does not have"):
        _av(emp, term.assign(team_key="T-XX"))
    with pytest.raises(FrameError, match="more than one row"):
        _av(pd.concat([emp, emp]), term)
    with pytest.raises(FrameError, match="lacks column"):
        _av(emp.drop(columns="leave_date"), term)


def test_utilisation_is_project_hours_over_availability_for_the_project_roles_at_mid_period():
    emp = _emp([("EMP-1", D(2020, 1, 1), None), ("EMP-2", D(2020, 1, 1), None), ("EMP-3", D(2020, 1, 1), None)])
    term = _term([("EMP-1", D(2020, 1, 1), None, "T-HH", "ENG", 1.0), ("EMP-2", D(2020, 1, 1), D(2026, 4, 1), "T-HH", "ENG", 1.0), ("EMP-2", D(2026, 4, 2), None, "T-NI", "ENG", 1.0),
                  ("EMP-3", D(2020, 1, 1), None, "T-HH", "OFFICE", 1.0)])
    av = _av(emp, term)
    te = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-2", "EMP-2", "EMP-3", "EMP-1"], "work_date": [D(2026, 3, 30), D(2026, 4, 10), D(2026, 4, 9), D(2026, 3, 29), D(2026, 4, 7), D(2026, 4, 11)],
                       "hours": [8.0, 8.0, 8.0, 99.0, 50.0, 77.0]})
    u = utilisation(te, av, term, TEAM, pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]}), project_roles=["ENG"]).set_index(["level", "key"])
    # EMP-1 (8 working days, T-HH, DEP-A) and EMP-2 (middle of the period is 3 April: term T-NI from 2 April, DEP-B)
    assert u.loc[("team", "T-HH"), ["availability_hours", "project_hours", "n_persons"]].tolist() == pytest.approx([8 * 7.4, 16.0, 1]), "hours on the last day of the period count, one day after do not"
    assert u.loc[("team", "T-NI"), ["availability_hours", "project_hours"]].tolist() == pytest.approx([8 * 7.4, 8.0]), "EMP-2: the whole period goes to the team valid at the middle; hours of 29 March are outside"
    assert ("team", "T-DK") not in u.index and u.loc[("department", "PDL"), "utilisation"] == pytest.approx(16 / (8 * 7.4)) and u.loc[("department", "ENG"), "project_hours"] == 8.0, "EMP-3 has no project role"
    assert utilisation(te, av, term, TEAM, pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]}), project_roles="ENG", before=D(2026, 3, 30)).empty, "the period starts on the date: not before it"
    with pytest.raises(FrameError, match="project_roles is empty"):
        utilisation(te, av, term, TEAM, pd.DataFrame({"dep_key": [], "dep_code": []}), project_roles=[])
    with pytest.raises(FrameError, match="more than one row"):
        utilisation(te, pd.concat([av, av]), term, TEAM, pd.DataFrame({"dep_key": [], "dep_code": []}), project_roles=["ENG"])


def test_the_term_valid_at_the_middle_of_the_period_includes_its_last_day():
    emp = _emp([("EMP-2", D(2020, 1, 1), None)])
    term = _term([("EMP-2", D(2020, 1, 1), D(2026, 4, 4), "T-HH", "ENG", 1.0), ("EMP-2", D(2026, 4, 5), None, "T-NI", "ENG", 1.0)])
    av = _av(emp, term, periods=[(D(2026, 3, 30), D(2026, 4, 9))])
    u = utilisation(pd.DataFrame({"emp_key": [], "work_date": [], "hours": []}), av, term, TEAM, pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]}), project_roles=["ENG"])
    assert u[u.level == "team"].key.tolist() == ["T-HH"], "the middle is 4 April 00:00, the last day of the first term"


def test_allocation_hours_is_percent_of_the_availability_inside_the_stint_split_at_the_date():
    emp, term = _emp([("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    al = pd.DataFrame({"alc_key": ["A1", "A2"], "emp_key": ["EMP-1", "EMP-1"], "prj_key": ["P1", "P2"], "start": [D(2026, 3, 30), D(2026, 4, 8)], "end": [D(2026, 4, 10), D(2026, 4, 9)], "percent": [50.0, 100.0]})
    r = allocation_hours(al, emp, term, NOLV, TEAM, D(2026, 4, 7)).set_index("alc_key")
    assert r.availability_hours.to_dict() == pytest.approx({"A1": 7 * 7.4, "A2": 2 * 7.4}) and r.hours.to_dict() == pytest.approx({"A1": 3.5 * 7.4, "A2": 2 * 7.4})
    assert r.hours_before.to_dict() == pytest.approx({"A1": 0.5 * 7.4 * 4, "A2": 0.0}), "30 and 31 March, 1 and 7 April: up to and including the 7th"
    assert r.hours_after.to_dict() == pytest.approx({"A1": 0.5 * 7.4 * 3, "A2": 2 * 7.4}) and r.after_now.tolist() == [True, True]
    assert (r.hours_before + r.hours_after).to_dict() == pytest.approx(r.hours.to_dict())
    done = allocation_hours(al, emp, term, NOLV, TEAM, D(2026, 4, 10)).set_index("alc_key")
    assert done.hours_after.eq(0).all() and done.after_now.tolist() == [False, False] and done.hours_before.to_dict() == pytest.approx(done.hours.to_dict()), "the stint ends on the date: nothing after"
    assert r.no_term_days.eq(0).all()
    late = _term([("EMP-1", D(2026, 4, 9), None, "T-DK", "R", 1.0)])
    g = allocation_hours(al, emp, late, NOLV, TEAM, D(2026, 4, 7)).set_index("alc_key")
    assert g.no_term_days.to_dict() == {"A1": 10, "A2": 1} and g.availability_hours.to_dict() == pytest.approx({"A1": 2 * 7.4, "A2": 7.4}), "days before the first term carry no hours and are counted"
    lv = _lv([("EMP-1", D(2026, 4, 8), D(2026, 4, 8), "sick")])
    assert allocation_hours(al, emp, term, lv, TEAM, D(2026, 4, 7)).set_index("alc_key").hours["A2"] == pytest.approx(7.4), "leave inside the stint"
    assert {"alc_key", "emp_key", "prj_key", "start", "end", "percent"} <= set(al.columns) and {"alc_key", "prj_key", "percent"} <= set(r.reset_index().columns), "the input columns are kept"


def test_allocation_hours_refuses_open_stints_unknown_people_and_bad_percent():
    emp, term = _emp([("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    al = pd.DataFrame({"alc_key": ["A1"], "emp_key": ["EMP-1"], "prj_key": ["P1"], "start": [D(2026, 3, 30)], "end": [D(2026, 4, 10)], "percent": [50.0]})
    f = lambda a, **k: allocation_hours(a, emp, term, NOLV, TEAM, D(2026, 4, 7), **k)
    for bad, m in ((al.assign(end=None), "open allocation"), (al.assign(end=D(2026, 3, 1)), "ends before"), (al.assign(percent=120.0), "percent"), (al.assign(percent=np.nan), "percent"),
                   (al.assign(emp_key="EMP-9"), "does not have")):
        with pytest.raises(FrameError, match=m):
            f(bad)
    assert f(al.iloc[:0]).empty
    with pytest.raises(FrameError, match="as_of"):
        allocation_hours(al, emp, term, NOLV, TEAM, "garbage")


def test_review_fixes_time_of_day_odd_span_mid_term_overlap_and_bad_dates():
    ts = pd.Timestamp
    emp, term = _emp([("EMP-1", ts("2026-04-09 15:00"), None)]), _term([("EMP-1", ts("2020-01-01 08:00"), None, "T-DK", "R", 1.0)])
    assert _av(emp, term).iloc[0].working_days == 2, "a hire date with a time of day is the whole day"
    lv = _lv([("EMP-1", ts("2026-04-08 08:00"), ts("2026-04-08 17:00"), "sick")])
    assert _av(_emp([("EMP-1", D(2020, 1, 1), None)]), term, lv).iloc[0].leave_days == 1
    al = pd.DataFrame({"alc_key": ["A1"], "emp_key": ["EMP-1"], "prj_key": ["P1"], "start": [ts("2026-04-09 10:00")], "end": [D(2026, 4, 10)], "percent": [100.0]})
    assert allocation_hours(al, emp, term, NOLV, TEAM, D(2026, 4, 7)).iloc[0].availability_hours == pytest.approx(2 * 7.4), "a stint start with a time of day keeps the last day of every term"
    emp2 = _emp([("EMP-2", D(2020, 1, 1), None)])
    t2 = _term([("EMP-2", D(2020, 1, 1), D(2026, 4, 4), "T-HH", "ENG", 1.0), ("EMP-2", D(2026, 4, 5), None, "T-NI", "ENG", 1.0)])
    av = _av(emp2, t2, periods=[(D(2026, 3, 30), D(2026, 4, 10))])
    u = utilisation(pd.DataFrame({"emp_key": [], "work_date": [], "hours": []}), av, t2, TEAM, pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]}), project_roles=["ENG"])
    assert u[u.level == "team"].key.tolist() == ["T-HH"], "an odd span has its middle at noon: the day counts, so the person does not vanish between two terms"
    te = pd.DataFrame({"emp_key": ["EMP-2"], "work_date": [ts("2026-04-10 09:00")], "hours": [5.0]})
    assert utilisation(te, av, t2, TEAM, pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]}), project_roles=["ENG"]).set_index("key").loc["T-HH", "project_hours"] == 5.0
    both = _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 0.0), ("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    for bad, m in ((both, "overlaps"), (term.assign(valid_to=D(2019, 1, 1)), "ends before it starts"), (term.assign(valid_from=None), "valid_from has nulls")):
        with pytest.raises(FrameError, match=m):
            _av(emp, bad)
    for bad_emp, m in ((_emp([("EMP-1", None, None)]), "hire_date has nulls"),):
        with pytest.raises(FrameError, match=m):
            _av(bad_emp, term)
    with pytest.raises(FrameError, match="ends before it starts"):
        _av(emp, term, _lv([("EMP-1", D(2026, 4, 8), D(2026, 4, 7), "sick")]))
    with pytest.raises(FrameError, match="has nulls"):
        _av(emp, term, _lv([("EMP-1", None, D(2026, 4, 8), "sick")]))
    with pytest.raises(FrameError, match="same period twice"):
        _av(emp, term, periods=P + P)
    with pytest.raises(FrameError, match="lacks column"):
        _av(emp, term, NOLV.drop(columns="leave_type"), leave_types=["sick"])
    with pytest.raises(FrameError, match="days are supported|at most"):
        availability_hours(emp, term, NOLV, TEAM, [(D(1900, 1, 1), D(2100, 1, 1))])


def test_registered_and_in_the_index():
    reg = registry.registered()
    for n in ("availability_hours", "utilisation", "allocation_hours"):
        m = reg[f"halvaro.hr.availability.{n}"]
        assert m.oracle.startswith("py:tests/") and m.sources
    assert registry.check() == [] and hr.availability_hours is availability_hours


# review 3: numbers and time zones are not dates, validated inputs of utilisation, the other input errors, boundaries

DEP = pd.DataFrame({"dep_key": ["DEP-A", "DEP-B"], "dep_code": ["PDL", "ENG"]})
NOTE = pd.DataFrame({"emp_key": [], "work_date": [], "hours": []})
EMP1, TERM1 = _emp([("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-HH", "ENG", 1.0)])
AL1 = pd.DataFrame({"alc_key": ["A1"], "emp_key": ["EMP-1"], "prj_key": ["P1"], "start": [D(2026, 3, 30)], "end": [D(2026, 4, 10)], "percent": [50.0]})


def _alloc(a=AL1, emp=EMP1, term=TERM1, lv=NOLV, as_of=D(2026, 4, 7), **k):
    return allocation_hours(a, emp, term, lv, TEAM, as_of, **k)


def _util(te=NOTE, av=None, term=TERM1, team=TEAM, dep=DEP, **k):
    av = _av(EMP1, TERM1) if av is None else av
    return utilisation(te, av, term, team, dep, **{"project_roles": ["ENG"], **k})


def test_a_number_is_not_a_date_and_a_time_zone_is_refused_in_every_date_argument():
    for bad in (20260401, 20260401.0, True, np.int64(20260401), np.float64(20260401.0), np.int8(1)):
        for call, m in ((lambda: _alloc(as_of=bad), "as_of"), (lambda: _av(EMP1, TERM1, periods=[(bad, D(2026, 4, 10))]), "period start"),
                        (lambda: _av(EMP1, TERM1, periods=[(D(2026, 3, 30), bad)]), "period end"), (lambda: _util(before=bad), "before")):
            with pytest.raises(FrameError, match=m + " is a number"):
                call()
            with pytest.raises(PeriodError, match=m + " is a number"):
                call()
    for tz in (pd.Timestamp("2026-04-01", tz="UTC"), dt.datetime(2026, 4, 1, 12, tzinfo=dt.timezone.utc), pd.Timestamp("2026-04-01 10:00", tz="Europe/Copenhagen")):
        for call, m in ((lambda: _alloc(as_of=tz), "as_of"), (lambda: _av(EMP1, TERM1, periods=[(tz, D(2026, 4, 10))]), "period start"),
                        (lambda: _av(EMP1, TERM1, periods=[(D(2026, 3, 30), tz)]), "period end"), (lambda: _util(before=tz), "before")):
            for exc in (FrameError, PeriodError):
                with pytest.raises(exc, match=m + " is not a date without a time zone"):
                    call()
    for bad in (None, pd.NaT, float("nan")):
        with pytest.raises(FrameError, match="as_of"):
            _alloc(as_of=bad)
    assert _alloc(as_of="2026-04-07").after_now.tolist() == [True] and _alloc(as_of=pd.Timestamp("2026-04-07 18:30")).after_now.tolist() == [True], "text and a time of day are dates"


def test_numbers_and_time_zones_in_date_columns_are_refused():
    ts_utc = pd.to_datetime(pd.Series([D(2020, 1, 1)])).dt.tz_localize("UTC")
    cols = {"int": 20200101, "float": 20200101.0, "bool": True, "np.int64": np.int64(20200101)}
    for kind, v in cols.items():
        for call in (lambda: _av(_emp([("EMP-1", v, None)]), TERM1), lambda: _av(EMP1, TERM1.assign(valid_from=v)), lambda: _av(EMP1, TERM1.assign(valid_to=v)),
                     lambda: _av(EMP1, TERM1, _lv([("EMP-1", v, D(2026, 4, 8), "sick")])), lambda: _av(EMP1, TERM1, _lv([("EMP-1", D(2026, 4, 8), v, "sick")])),
                     lambda: _alloc(AL1.assign(start=v)), lambda: _alloc(AL1.assign(end=v)),
                     lambda: _util(av=_av(EMP1, TERM1).assign(period_start=v)), lambda: _util(av=_av(EMP1, TERM1).assign(period_end=v)),
                     lambda: _util(te=pd.DataFrame({"emp_key": ["EMP-1"], "work_date": [v], "hours": [1.0]}))):
            with pytest.raises(FrameError, match="holds numbers, not dates"):
                call()
    with pytest.raises(FrameError, match="holds numbers, not dates"):
        _av(_emp([("EMP-1", D(2020, 1, 1), None), ("EMP-2", 20200101, None)]), TERM1)
    for call in (lambda: _av(_emp([("EMP-1", ts_utc[0], None)]), TERM1), lambda: _av(EMP1, TERM1.assign(valid_from=ts_utc[0])), lambda: _alloc(AL1.assign(start=ts_utc[0])),
                 lambda: _util(te=pd.DataFrame({"emp_key": ["EMP-1"], "work_date": ts_utc, "hours": [1.0]}))):
        with pytest.raises(FrameError, match="time zone"):
            call()
    with pytest.raises(FrameError, match="not a date"):
        _av(_emp([("EMP-1", "garbage", None)]), TERM1)
    nan_to = TERM1.assign(valid_to=np.nan)
    assert nan_to.valid_to.dtype == float and _av(EMP1, nan_to).iloc[0].working_days == 8, "an all null float valid_to is open ended, not a number column"


def test_utilisation_validates_the_availability_frame_and_the_time_entries():
    av = _av(EMP1, TERM1)
    row = av.iloc[0]
    other = lambda a, b, **k: pd.DataFrame([{**row.to_dict(), "period_start": pd.Timestamp(a), "period_end": pd.Timestamp(b), **k}])
    with pytest.raises(FrameError, match="ends before it starts"):
        _util(av=av.assign(period_end=D(2026, 3, 1)))
    assert _util(av=other("2026-04-10", "2026-04-10")).shape[0] == 2, "a one day period is a period"
    # overlaps: a shared day, a period inside another, one before another that shares its first day, and a nested one followed by a third
    for extra in ((("2026-04-10", "2026-04-12"),), (("2026-04-01", "2026-04-02"),), (("2026-04-01", "2026-04-02"), ("2026-04-05", "2026-04-06")), (("2026-03-29", "2026-03-30"),)):
        with pytest.raises(FrameError, match="overlapping periods"):
            _util(av=pd.concat([av] + [other(a, b) for a, b in extra], ignore_index=True))
    touching = pd.concat([av, other("2026-04-11", "2026-04-12", hours=1.0), other("2026-03-01", "2026-03-29", hours=2.0)], ignore_index=True)
    assert _util(av=touching).loc[lambda u: u.level == "team", "availability_hours"].iloc[0] == pytest.approx(8 * 7.4 + 3.0), "periods that follow each other day by day are not overlapping"
    two = pd.concat([av, av.assign(emp_key="EMP-2")], ignore_index=True)
    assert _util(av=two, term=pd.concat([TERM1, TERM1.assign(emp_key="EMP-2")])).n_persons.tolist() == [2, 2], "the same period of two persons is not an overlap"
    for bad in (-0.5, "7.4", True, np.nan, None, np.inf):
        with pytest.raises(FrameError, match="availability hours"):
            _util(av=av.assign(hours=bad))
    assert _util(av=av.assign(hours=0.0)).utilisation.isna().all(), "zero availability is allowed and gives no utilisation"
    with pytest.raises(FrameError, match="emp_key has nulls"):
        _util(av=av.assign(emp_key=None))
    te = lambda **k: pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "work_date": [D(2026, 3, 31), D(2026, 4, 1)], "hours": [3.0, 4.0], **k})
    assert _util(te=te(hours=[0.0, 4.0])).project_hours.tolist() == [4.0, 4.0], "zero hours are allowed"
    for bad in ([np.nan, 4.0], [None, 4.0], ["3", 4.0], [True, 4.0], [np.inf, 4.0]):
        with pytest.raises(FrameError, match="time_entry.hours"):
            _util(te=te(hours=bad))
    with pytest.raises(FrameError, match="projects.time_entry.emp_key has nulls"):
        _util(te=te(emp_key=["EMP-1", None]))
    with pytest.raises(FrameError, match="mixes"):
        _util(te=te(emp_key=["EMP-1", 7]))
    with pytest.raises(FrameError, match="not of one kind"):
        _util(te=te(emp_key=[7, 7]))


def test_utilisation_counts_a_person_once_per_team_and_reads_a_string_role_as_one_role():
    av = _av(EMP1, TERM1, periods=[(D(2026, 3, 30), D(2026, 4, 5)), (D(2026, 4, 6), D(2026, 4, 10))])
    te = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "work_date": [D(2026, 3, 31), D(2026, 4, 8)], "hours": [3.0, 4.0]})
    u = _util(te=te, av=av).set_index(["level", "key"])
    assert u.n_persons.to_dict() == {("team", "T-HH"): 1, ("department", "PDL"): 1}, "two periods of one person are one person"
    assert u.loc[("team", "T-HH"), "project_hours"] == 7.0 and u.loc[("team", "T-HH"), "availability_hours"] == pytest.approx(8 * 7.4)
    as_text = _util(te=te, av=av, project_roles="ENG")
    assert not as_text.empty and as_text.equals(_util(te=te, av=av, project_roles=["ENG"])), "'ENG' is the role ENG, not the letters E, N and G"
    assert _util(te=te, av=av, project_roles={"ENG"}).equals(as_text) and _util(te=te, av=av, project_roles="OFFICE").empty
    assert _util(te=te, av=av, before=D(2026, 4, 6)).set_index("key").loc["T-HH", "availability_hours"] == pytest.approx(4 * 7.4), "before: only the first period (30 March to 5 April) starts before 6 April"


def test_utilisation_refuses_teams_departments_and_terms_that_do_not_fit():
    twice = pd.concat([TEAM, TEAM.iloc[:1]], ignore_index=True)
    with pytest.raises(FrameError, match="hr.team has more than one row"):
        _util(team=twice)
    with pytest.raises(FrameError, match="hr.department has more than one row"):
        _util(dep=pd.concat([DEP, DEP.iloc[:1]], ignore_index=True))
    with pytest.raises(FrameError, match="hr.team has more than one row"):
        availability_hours(EMP1, TERM1, NOLV, twice, P)
    with pytest.raises(FrameError, match=r"hr.employment_term has teams that hr.team does not have: \['T-HH'\]"):
        _util(team=TEAM[TEAM.team_key != "T-HH"])
    with pytest.raises(FrameError, match="department hr.department does not have"):
        _util(dep=DEP[DEP.dep_key != "DEP-A"])
    two = pd.concat([TERM1, TERM1.assign(team_key="T-NI")], ignore_index=True)
    with pytest.raises(FrameError, match="two terms valid at the middle"):
        _util(term=two)
    assert _util(term=pd.concat([TERM1, TERM1.assign(team_key="T-NI", valid_from=D(2027, 1, 1))], ignore_index=True)).key.tolist() == ["T-HH", "PDL"], "a term that is not valid at the middle is not a second term"


def test_a_term_that_starts_on_the_middle_day_of_the_period_is_the_one_valid_there():
    emp = _emp([("EMP-2", D(2020, 1, 1), None)])
    term = _term([("EMP-2", D(2020, 1, 1), D(2026, 4, 3), "T-HH", "ENG", 1.0), ("EMP-2", D(2026, 4, 4), None, "T-NI", "ENG", 1.0)])
    av = _av(emp, term, periods=[(D(2026, 3, 30), D(2026, 4, 9))])
    assert utilisation(NOTE, av, term, TEAM, DEP, project_roles=["ENG"]).query("level == 'team'").key.tolist() == ["T-NI"], "the middle is 4 April: the second term starts there"


def test_periods_come_back_sorted_and_the_period_edges_are_inclusive():
    emp, term = _emp([("EMP-2", D(2020, 1, 1), None), ("EMP-1", D(2020, 1, 1), None)]), _term([("EMP-1", D(2020, 1, 1), None, "T-DK", "R", 1.0), ("EMP-2", D(2020, 1, 1), None, "T-DK", "R", 1.0)])
    late, early = (D(2026, 4, 8), D(2026, 4, 9)), (D(2026, 4, 7), D(2026, 4, 7))
    a = _av(emp, term, periods=[late, early])
    assert a.emp_key.tolist() == ["EMP-1", "EMP-1", "EMP-2", "EMP-2"] and a.period_start.dt.day.tolist() == [7, 8, 7, 8] and a.working_days.tolist() == [1, 2, 1, 2]
    assert _av(emp, term, periods=[(D(2026, 4, 9), D(2026, 4, 9))]).working_days.tolist() == [1, 1], "a one day period"
    assert _av(emp, term, hours_per_day=24).hours.tolist() == pytest.approx([7 * 24.0] * 2), "24 hours a day is the most"
    assert _av(emp, term, hours_per_day=np.float64(8.5)).hours.tolist() == pytest.approx([7 * 8.5] * 2)


def test_periods_with_a_time_of_day_are_whole_days_each():
    ts = pd.Timestamp
    a = _av(EMP1, TERM1, periods=[(ts("2026-04-07 09:00"), ts("2026-04-07 17:00")), (ts("2026-04-08 08:00"), ts("2026-04-09 20:00"))])
    assert a.working_days.tolist() == [1, 2] and a.period_start.tolist() == [ts("2026-04-07"), ts("2026-04-08")] and a.period_end.tolist() == [ts("2026-04-07"), ts("2026-04-09")]


def test_a_one_day_term_and_a_term_over_the_whole_table():
    emp = _emp([("EMP-1", D(2020, 1, 1), None)])
    one = _term([("EMP-1", D(2026, 4, 8), D(2026, 4, 8), "T-DK", "R", 1.0)])
    a = _av(emp, one).iloc[0]
    assert (a.working_days, a.hours) == (1, pytest.approx(7.4)), "a term from and to the same day"
    for fte, h in ((0.0, 0.0), (1.0, 7.4), (0.5, 3.7)):
        assert _av(emp, one.assign(fte=fte)).iloc[0].hours == pytest.approx(h), "fte 0 and 1 are the limits"
    # overlaps are found over every term, also outside the days asked for and for persons that are not in hr.employee
    old = lambda *r: _term([("EMP-1", D(*a), None if b is None else D(*b), "T-DK", "R", 1.0) for a, b in r])
    for rows in ((((2019, 1, 1), (2019, 12, 31)), ((2019, 12, 31), (2020, 1, 31))), (((2019, 1, 1), None), ((2024, 1, 1), None)),
                 (((2019, 1, 1), (2019, 12, 31)), ((2019, 3, 1), (2019, 3, 2)), ((2019, 6, 1), (2019, 6, 5))), (((2019, 1, 1), (2019, 1, 1)), ((2019, 1, 1), (2019, 1, 1)))):
        with pytest.raises(FrameError, match="overlaps"):
            _av(emp, pd.concat([one, old(*rows)], ignore_index=True))
        with pytest.raises(FrameError, match="overlaps"):
            _alloc(AL1, emp, pd.concat([one, old(*rows)], ignore_index=True))
        with pytest.raises(FrameError, match="EMP-1 overlaps|EMP-7 overlaps"):
            _av(emp, pd.concat([one, old(*rows).assign(emp_key="EMP-7")], ignore_index=True))
    fine = pd.concat([one, old(((2019, 1, 1), (2019, 12, 31)), ((2020, 1, 1), (2020, 1, 31)), ((2020, 2, 1), (2026, 4, 7)))], ignore_index=True)
    assert _av(emp, fine).iloc[0].working_days == 5, "terms that follow each other day by day are not overlapping (30, 31 March, 1, 7 and 8 April in Denmark)"


def test_other_inputs_that_are_refused_with_a_frame_error():
    for bad in ("0.5", True, np.nan, None, -0.1, 1.01, np.inf):
        with pytest.raises(FrameError, match="fte"):
            _av(EMP1, TERM1.assign(fte=bad))
    for bad in ("50", True, np.nan, None, -1.0, 100.5, np.inf):
        with pytest.raises(FrameError, match="percent"):
            _alloc(AL1.assign(percent=bad))
    zero, full = _alloc(AL1.assign(percent=0)).iloc[0], _alloc(AL1.assign(percent=100)).iloc[0]
    assert zero.hours == 0 and zero.hours_before == 0 and zero.availability_hours == pytest.approx(8 * 7.4) and full.hours == pytest.approx(8 * 7.4), "percent 0 and 100 are the limits"
    assert _alloc(AL1.assign(percent=np.int64(50))).iloc[0].hours == pytest.approx(4 * 7.4)
    with pytest.raises(FrameError, match="open allocation"):
        _alloc(AL1.assign(end=None))
    mix = _emp([("EMP-1", D(2020, 1, 1), None), (7, D(2020, 1, 1), None)])
    sick = lambda *keys: _lv([(k, D(2026, 4, 8), D(2026, 4, 8), "sick") for k in keys])
    for call, m in ((lambda: _av(mix, TERM1), "hr.employee.emp_key mixes"), (lambda: _av(EMP1, pd.concat([TERM1, TERM1.assign(emp_key=7)])), "hr.employment_term.emp_key mixes"),
                    (lambda: _av(EMP1, TERM1, sick("EMP-1", 7)), "hr.leave_record.emp_key mixes"), (lambda: _alloc(pd.concat([AL1, AL1.assign(emp_key=7)])), "hr.allocation.emp_key mixes"),
                    (lambda: _alloc(AL1, mix), "hr.employee.emp_key mixes")):
        with pytest.raises(FrameError, match=m):
            call()
    assert _av(_emp([(7, D(2020, 1, 1), None), (8, D(2020, 1, 1), None)]), TERM1.assign(emp_key=7)).emp_key.tolist() == [7], "number keys alone are fine"
    for call in (lambda: _av(_emp([(None, D(2020, 1, 1), None)]), TERM1), lambda: _av(EMP1, TERM1.assign(emp_key=None)), lambda: _av(EMP1, TERM1, _lv([(None, D(2026, 4, 8), D(2026, 4, 8), "x")])),
                 lambda: _alloc(AL1.assign(emp_key=None))):
        with pytest.raises(FrameError, match="emp_key has nulls"):
            call()


def test_allocation_edges_one_day_stints_and_days_without_a_term():
    one = AL1.assign(start=D(2026, 4, 8), end=D(2026, 4, 8), percent=100.0)
    for as_of, before, after, now in ((D(2026, 4, 7), 0.0, 7.4, True), (D(2026, 4, 8), 7.4, 0.0, False), (D(2026, 4, 9), 7.4, 0.0, False), (D(2026, 1, 1), 0.0, 7.4, True)):
        r = _alloc(one, as_of=as_of).iloc[0]
        assert (r.availability_hours, r.hours, r.hours_before, r.hours_after, r.after_now, r.no_term_days) == (pytest.approx(7.4), pytest.approx(7.4), pytest.approx(before), pytest.approx(after), now, 0), as_of
    late = _term([("EMP-1", D(2026, 4, 9), None, "T-DK", "R", 1.0)])
    r = _alloc(one, EMP1, late).iloc[0]
    assert (r.no_term_days, r.availability_hours, r.hours) == (1, 0.0, 0.0), "a one day stint on a day without a term"
    # only days of employment count: not hired yet (9 days), employed without a term (7 days), left (days after the leave date)
    wide = AL1.assign(percent=100.0)
    assert _alloc(wide, _emp([("EMP-1", D(2026, 4, 8), None)]), _term([("EMP-1", D(2026, 4, 8), None, "T-DK", "R", 1.0)])).iloc[0].no_term_days == 0, "before the hire date is not a day without a term"
    assert _alloc(wide, _emp([("EMP-1", D(2026, 4, 1), None)]), _term([("EMP-1", D(2026, 4, 8), None, "T-DK", "R", 1.0)])).iloc[0].no_term_days == 7
    left = _alloc(wide, _emp([("EMP-1", D(2020, 1, 1), D(2026, 4, 5))]), _term([("EMP-1", D(2020, 1, 1), D(2026, 4, 3), "T-DK", "R", 1.0)])).iloc[0]
    assert left.no_term_days == 2 and left.availability_hours == pytest.approx(3 * 7.4), "4 and 5 April: employed, no term; nothing after the leave date"


# the baseline


def test_a_leave_without_an_end_is_open_to_the_end_of_the_window_like_org_status_on():
    # P is the window of the other tests; the open leave starts on 2026-04-08 (a Wednesday)
    end = max(p[1] for p in P)
    open_ = _av(EMP1, TERM1, _lv([("EMP-1", D(2026, 4, 8), None, "sick")]))
    same = _av(EMP1, TERM1, _lv([("EMP-1", D(2026, 4, 8), end, "sick")]))
    pd.testing.assert_frame_equal(open_, same)
    assert open_.leave_days.sum() > 0 and open_.net_days.sum() < _av(EMP1, TERM1).net_days.sum(), "the open leave removes days"
    # other leave types are not affected, and an open leave that starts after the window removes nothing
    mixed = _lv([("EMP-1", D(2026, 4, 8), None, "extended_leave"), ("EMP-2", D(2026, 4, 8), None, "extended_leave")])
    pd.testing.assert_frame_equal(_av(EMP1, TERM1, mixed, leave_types=["sick"]), _av(EMP1, TERM1))
    pd.testing.assert_frame_equal(_av(EMP1, TERM1, _lv([("EMP-1", end + pd.Timedelta(days=1), None, "sick")])), _av(EMP1, TERM1))
    with pytest.raises(FrameError, match="start has nulls"):
        _av(EMP1, TERM1, _lv([("EMP-1", None, None, "sick")]))
    with pytest.raises(FrameError, match="ends before it starts"):
        _av(EMP1, TERM1, _lv([("EMP-1", D(2026, 4, 8), D(2026, 4, 7), "sick")]))
    a = _alloc(lv=_lv([("EMP-1", D(2026, 4, 8), None, "sick")]))
    b = _alloc(lv=_lv([("EMP-1", D(2026, 4, 8), D(2026, 4, 10), "sick")]))
    pd.testing.assert_frame_equal(a, b)                                                              # allocation_hours: the window is the stints (up to 2026-04-10), so open means to their end


def test_utilisation_keeps_negative_booked_hours_as_corrections_like_planned_vs_actual_hours():
    te = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "work_date": [D(2026, 3, 31), D(2026, 4, 1)], "hours": [8.0, -2.0]})
    u = _util(te=te)
    assert u.project_hours.tolist() == [6.0, 6.0], "a reversal reduces the hours"
    assert _util(te=te.assign(hours=[-3.0, 1.0])).project_hours.tolist() == [-2.0, -2.0]
    for bad in ([np.nan, 4.0], [-np.inf, 4.0], ["-3", 4.0], [True, 4.0]):
        with pytest.raises(FrameError, match="time_entry.hours"):
            _util(te=te.assign(hours=bad))
