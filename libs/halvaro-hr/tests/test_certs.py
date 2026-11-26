"""Certificates: validity from the dates, status on a date, chains, booked renewals, expiring, expiry report, on synthetic frames (the baseline tests are in the closed repository)."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, PeriodError, registry

D = dt.date
NOW = D(2026, 11, 30)


def _c(rows):
    """rows: (emp, qual, issued, expires, status, origin, renews_issued, event_no)"""
    return pd.DataFrame(rows, columns=["emp_key", "qual_key", "issued", "expires", "status", "origin", "renews_issued", "event_no"])


def _row(emp, qual, issued, expires, status="valid", origin="course", renews=None, event=1):
    return (emp, qual, issued, expires, status, origin, renews, event)


# valid_on

def test_valid_on_is_inclusive_on_both_ends_and_null_expiry_is_open():
    c = _c([_row("EMP-000001", "QUAL-001", D(2024, 1, 1), D(2024, 12, 31)), _row("EMP-000002", "QUAL-001", D(2024, 1, 2), None), _row("EMP-000003", "QUAL-001", D(2020, 1, 1), D(2023, 12, 31))])
    assert hr.valid_on(c, D(2024, 1, 1)).emp_key.tolist() == ["EMP-000001"], "issued the day after is not yet valid; expired the day before is gone"
    assert hr.valid_on(c, D(2024, 1, 2)).emp_key.tolist() == ["EMP-000001", "EMP-000002"]
    assert hr.valid_on(c, D(2024, 12, 31)).emp_key.tolist() == ["EMP-000001", "EMP-000002"], "expires is the last valid day"
    assert hr.valid_on(c, D(2025, 1, 1)).emp_key.tolist() == ["EMP-000002"] and hr.valid_on(c, D(2099, 1, 1)).emp_key.tolist() == ["EMP-000002"]
    assert hr.valid_on(c, D(2019, 1, 1)).empty and list(hr.valid_on(c, D(2024, 1, 2)).columns) == ["emp_key", "qual_key", "issued", "expires", "as_of"]


def test_valid_on_never_reads_status_and_keeps_the_latest_of_overlapping_issues():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2024, 6, 30), status="expired"), _row("EMP-000001", "QUAL-001", D(2024, 3, 1), D(2028, 6, 30), status="superseded", origin="renewal", renews=D(2020, 1, 1)),
            _row("EMP-000001", "QUAL-002", D(2024, 1, 1), D(2030, 1, 1), status="expired")])
    v = hr.valid_on(c.drop(columns="status"), D(2024, 5, 1))
    assert v[["qual_key", "issued"]].values.tolist() == [["QUAL-001", pd.Timestamp(2024, 3, 1)], ["QUAL-002", pd.Timestamp(2024, 1, 1)]] and v.expires.tolist()[0] == pd.Timestamp(2028, 6, 30)
    assert len(hr.valid_on(c, D(2022, 1, 1))) == 1, "before the renewal only the first issue is in force"


def test_valid_on_refuses_bad_input():
    c = _c([_row("EMP-000001", "QUAL-001", D(2024, 1, 1), D(2023, 1, 1))])
    with pytest.raises(FrameError, match="expire before they are issued"):
        hr.valid_on(c, NOW)
    with pytest.raises(FrameError, match="need emp_key, qual_key and issued"):
        hr.valid_on(_c([_row("EMP-000001", "QUAL-001", None, None)]), NOW)
    with pytest.raises(FrameError, match="lacks column.*expires"):
        hr.valid_on(c.drop(columns="expires"), NOW)
    with pytest.raises(FrameError, match="time zone"):
        hr.valid_on(c.assign(issued=pd.to_datetime(c.issued).dt.tz_localize("UTC")), NOW)
    for bad in (None, "junk", 20240101, pd.Timestamp("2024-01-01", tz="UTC")):
        with pytest.raises(PeriodError):
            hr.valid_on(_c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), None)]), bad)
    assert hr.valid_on(_c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), None)]).iloc[:0], NOW).empty


# cert_status_on

def test_status_on_a_date_and_the_stored_comparison():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2022, 12, 31), status="expired"), _row("EMP-000001", "QUAL-001", D(2022, 6, 1), D(2026, 12, 31), status="superseded", origin="renewal", renews=D(2020, 1, 1)),
            _row("EMP-000001", "QUAL-001", D(2026, 1, 1), D(2030, 1, 1), status="valid", origin="renewal", renews=D(2022, 6, 1)), _row("EMP-000002", "QUAL-001", D(2027, 1, 1), None, status="valid")])
    s = hr.cert_status_on(c, NOW, stored_at=NOW)
    assert s.status_on.tolist() == ["expired", "superseded", "valid", "not_yet_valid"] and s.matches_stored.tolist() == [True, True, True, False]
    assert hr.cert_status_on(c, D(2022, 5, 31)).status_on.tolist() == ["valid", "not_yet_valid", "not_yet_valid", "not_yet_valid"], "the later issue has to be issued to supersede"
    assert hr.cert_status_on(c, D(2022, 6, 1)).status_on.tolist() == ["superseded", "valid", "not_yet_valid", "not_yet_valid"]
    assert hr.cert_status_on(c, D(2022, 12, 31)).status_on.tolist()[0:2] == ["superseded", "valid"], "the last valid day of the first issue: still superseded, not expired"
    assert hr.cert_status_on(c, D(2023, 1, 1)).status_on.tolist()[:2] == ["expired", "valid"]
    assert hr.cert_status_on(c, NOW).matches_stored.isna().all() and hr.cert_status_on(c, NOW, stored_at=D(2026, 11, 29)).matches_stored.isna().all()
    assert hr.cert_status_on(c, D(2026, 12, 31)).status_on.tolist()[1] == "superseded" and hr.cert_status_on(c, D(2027, 1, 1)).status_on.tolist()[1] == "expired"
    assert list(s.columns) == ["emp_key", "qual_key", "issued", "expires", "as_of", "status_on", "stored_status", "matches_stored"] and s.emp_key.tolist() == c.emp_key.tolist()


# renewal_chains

def test_chains_links_lapse_and_overlap():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2022, 12, 31), event=1),
            _row("EMP-000001", "QUAL-001", D(2022, 12, 1), D(2025, 12, 31), origin="renewal", renews=D(2020, 1, 1), event=2),            # 31 days overlap
            _row("EMP-000001", "QUAL-001", D(2026, 1, 11), D(2029, 1, 10), origin="renewal", renews=D(2022, 12, 1), event=3),            # 10 days lapse
            _row("EMP-000002", "QUAL-001", D(2021, 1, 1), D(2023, 12, 31), event=4),
            _row("EMP-000002", "QUAL-001", D(2024, 1, 1), D(2026, 12, 31), origin="renewal", renews=D(2020, 5, 5), event=5),            # link to a date that is not the previous issue
            _row("EMP-000003", "QUAL-001", D(2023, 1, 1), None, origin="recognised", event=None)])
    ch = hr.renewal_chains(c.sample(frac=1, random_state=3)).set_index(["emp_key", "event_no"], drop=False)
    e1 = ch.loc["EMP-000001"]
    assert e1.position.tolist() == [1, 2, 3] and e1.chain.tolist() == [1, 1, 1] and e1.link_ok.tolist() == [True, True, True]
    assert pd.isna(e1.lapse_days.iloc[0]) and e1.overlap_days.tolist()[1:] == [31.0, 0.0] and e1.lapse_days.tolist()[1:] == [0.0, 10.0]
    e2 = ch.loc["EMP-000002"]
    assert e2.link_ok.tolist() == [True, False] and e2.lapse_days.isna().all() and e2.overlap_days.isna().all(), "no lapse or overlap for a link that does not hold"
    assert ch.loc["EMP-000003"].link_ok.all() and ch.loc["EMP-000003"].position.tolist() == [1]
    assert list(hr.renewal_chains(c).columns)[:4] == ["emp_key", "qual_key", "chain", "position"] and hr.renewal_chains(c.iloc[:0]).empty


def test_a_course_in_the_middle_starts_a_new_chain():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2022, 1, 1)), _row("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2026, 1, 1)),
            _row("EMP-000001", "QUAL-001", D(2026, 2, 1), D(2029, 1, 1), origin="renewal", renews=D(2023, 1, 1))])
    ch = hr.renewal_chains(c)
    assert ch.chain.tolist() == [1, 2, 2] and ch.position.tolist() == [1, 1, 2] and ch.link_ok.tolist() == [True, True, True]


# booked_renewals

def _ev(rows):
    """rows: (event_no, qual_key, date, capacity, seats_taken, country, site); every course lasts two days."""
    f = pd.DataFrame(rows, columns=["event_no", "qual_key", "date", "capacity", "seats_taken", "country", "location_site_key"])
    f.insert(3, "end_date", [d + dt.timedelta(days=1) for d in f["date"]])
    return f


def _att(rows):
    return pd.DataFrame(rows, columns=["event_no", "emp_key", "outcome", "status"])


def _rel(now=NOW):
    return {"competence": pd.DataFrame({"release": ["r"], "now": [now], "generated_at": ["2026-11-30T00:00:00"], "base_seed": [1], "increment": [0]})}


def test_booked_renewals_only_at_the_release_now_and_only_booked_seats():
    ev = _ev([(1, "QUAL-004", D(2027, 1, 14), 12, 4, "DK", "SITE-01"), (2, "QUAL-004", D(2026, 5, 1), 12, 12, "DK", "SITE-01")])
    att = _att([(1, "EMP-000001", None, "booked"), (1, "EMP-000002", None, "booked"), (2, "EMP-000003", "attended", "completed")])
    b = hr.booked_renewals(att, ev, NOW, _rel())
    assert b.emp_key.tolist() == ["EMP-000001", "EMP-000002"] and b.free_seats.tolist() == [8, 8] and b.course_date.iloc[0] == pd.Timestamp(2027, 1, 14)
    assert list(b.columns) == ["emp_key", "qual_key", "event_no", "course_date", "course_end", "capacity", "seats_taken", "free_seats", "country", "location_site_key"]
    assert b.course_end.iloc[0] == pd.Timestamp(2027, 1, 15)
    with pytest.raises(PeriodError, match="only known at the release date 2026-11-30"):
        hr.booked_renewals(att, ev, D(2026, 11, 29), _rel())
    with pytest.raises(PeriodError, match="cannot be rebuilt"):
        hr.booked_renewals(att, ev, D(2026, 12, 1), _rel())
    with pytest.raises(FrameError, match="not after 2026-11-30"):
        hr.booked_renewals(_att([(2, "EMP-000003", None, "booked")]), ev, NOW, _rel())
    with pytest.raises(FrameError, match="event_no that is not in"):
        hr.booked_renewals(_att([(9, "EMP-000003", None, "booked")]), ev, NOW, _rel())
    with pytest.raises(FrameError, match="more seats taken than capacity"):
        hr.booked_renewals(att, ev.assign(seats_taken=[13, 12]), NOW, _rel())
    with pytest.raises(FrameError, match="duplicate event_no"):
        hr.booked_renewals(att, pd.concat([ev, ev]), NOW, _rel())
    assert hr.booked_renewals(att.iloc[2:], ev, NOW, _rel()).empty


# expiring

def _booked(rows):
    f = pd.DataFrame(rows, columns=["emp_key", "qual_key", "course_date", "event_no", "free_seats"])
    f.insert(3, "course_end", [d + dt.timedelta(days=1) for d in f["course_date"]])
    return f


def test_expiring_window_booked_cover_and_gap():
    c = _c([_row("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2027, 1, 14)), _row("EMP-000002", "QUAL-001", D(2023, 1, 1), D(2027, 2, 28)), _row("EMP-000003", "QUAL-001", D(2023, 1, 1), D(2027, 2, 28)),
            _row("EMP-000004", "QUAL-001", D(2023, 1, 1), D(2027, 3, 1)), _row("EMP-000005", "QUAL-001", D(2023, 1, 1), D(2026, 11, 30)), _row("EMP-000006", "QUAL-001", D(2023, 1, 1), None),
            _row("EMP-000007", "QUAL-001", D(2023, 1, 1), D(2026, 11, 29))])
    v = hr.valid_on(c, NOW)
    b = _booked([("EMP-000001", "QUAL-001", D(2027, 1, 14), 1896, 10), ("EMP-000002", "QUAL-001", D(2027, 3, 5), 1900, 3), ("EMP-000002", "QUAL-001", D(2027, 4, 5), 1901, 9), ("EMP-000009", "QUAL-001", D(2027, 1, 1), 1, 1)])
    x = hr.expiring(v, b, NOW).set_index("emp_key")
    assert x.index.tolist() == ["EMP-000005", "EMP-000001", "EMP-000002", "EMP-000003"], "sorted by expiry date, then person"
    assert "EMP-000004" not in x.index, "2027-03-01 is 91 days after 2026-11-30"
    assert x.loc["EMP-000001", ["booked", "event_no", "free_seats", "gap_days"]].tolist() == [True, 1896, 10, 0.0], "course on the expiry day: no gap"
    assert x.loc["EMP-000002", ["booked", "event_no", "gap_days"]].tolist() == [True, 1900, 4.0] and x.loc["EMP-000003", "booked"] == False and pd.isna(x.loc["EMP-000003", "gap_days"])
    assert x.loc["EMP-000005", "booked"] == False
    assert hr.expiring(v, b, NOW, window_days=0).emp_key.tolist() == ["EMP-000005"], "expires on the date itself is inside a zero day window"
    assert len(hr.expiring(v, b, NOW, window_days=91)) == 5 and "EMP-000004" in set(hr.expiring(v, b, NOW, window_days=91).emp_key)
    with pytest.raises(FrameError, match="window_days"):
        hr.expiring(v, b, NOW, window_days=-1)
    assert hr.expiring(v.iloc[:0], b, NOW).empty


# expiry_report

EXPIRY = D(2026, 12, 31)


def _expiry_frames():
    c = _c([_row("EMP-000001", "QUAL-004", D(2021, 12, 7), EXPIRY), _row("EMP-000002", "QUAL-004", D(2021, 12, 7), EXPIRY), _row("EMP-000003", "QUAL-004", D(2021, 12, 7), EXPIRY),
            _row("EMP-000004", "QUAL-004", D(2021, 12, 7), EXPIRY), _row("EMP-000005", "QUAL-004", D(2021, 12, 7), D(2027, 1, 1)), _row("EMP-000006", "QUAL-003", D(2023, 1, 1), D(2027, 6, 1)),
            _row("EMP-000007", "QUAL-003", D(2023, 1, 1), D(2027, 6, 1)), _row("EMP-000001", "QUAL-004", D(2026, 12, 1), D(2031, 12, 1), origin="renewal", renews=D(2021, 12, 7))])
    c = c.iloc[:-1]
    emp = pd.DataFrame({"emp_key": [f"EMP-00000{i}" for i in range(1, 8)], "leave_date": [None, None, None, D(2026, 11, 1), None, None, D(2026, 10, 1)], "legal_entity_key": ["LE-01"] * 7})
    ev = _ev([(10, "QUAL-004", D(2027, 1, 14), 12, 2, "DK", "SITE-01"), (11, "QUAL-004", D(2027, 2, 17), 12, 12, "DK", "SITE-02"), (12, "QUAL-003", D(2027, 1, 20), 8, 1, "DK", "SITE-01"),
              (13, "QUAL-004", D(2026, 5, 1), 12, 9, "DK", "SITE-01")])
    b = _booked([("EMP-000001", "QUAL-004", D(2027, 1, 14), 10, 10), ("EMP-000003", "QUAL-004", D(2027, 2, 17), 11, 0)])
    lv = pd.DataFrame({"emp_key": ["EMP-000003", "EMP-000001"], "leave_type": ["extended_leave", "sick"], "start": [D(2027, 1, 1), D(2027, 1, 1)], "end": [D(2027, 3, 1), D(2027, 3, 1)]})
    return c, b, ev, emp, lv


def test_expiry_report_booked_not_booked_leave_and_counts():
    c, b, ev, emp, lv = _expiry_frames()
    r = hr.expiry_report(c, b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004", holder_qual_key="QUAL-003")
    f = r.frame.set_index("emp_key")
    assert f.index.tolist() == ["EMP-000001", "EMP-000002", "EMP-000003"], "EMP-000004 left, EMP-000005 expires a day later"
    assert f.booked.tolist() == [True, False, True] and f.event_no.iloc[0] == 10 and f.free_seats.tolist()[0] == 10 and f.free_seats.tolist()[2] == 0 and pd.isna(f.course_date.iloc[1])
    assert f.gap_days.iloc[0] == 13.0 and f.gap_days.iloc[2] == 47.0 and pd.isna(f.gap_days.iloc[1])
    assert f.on_leave_at_course.tolist() == [False, False, True], "extended leave covers the course of EMP-000003, sick leave does not count"
    assert r.counts == {"expiry_date": EXPIRY, "qual_key": "QUAL-004", "n_expiring": 3, "n_booked": 2, "n_not_booked": 1, "rows_expiring_on_date": 4, "former_employees": 1, "superseded": 0,
                        "n_holders": 1, "booked_on_leave_at_course": 1}
    assert r.holders == ("EMP-000006",)
    assert r.events.event_no.tolist() == [10, 11] and r.events.free_seats.tolist() == [10, 0], "only courses of the qualification after the date"


def test_expiry_report_holders_current_people_only_and_a_renewal_takes_a_person_out():
    c, b, ev, emp, lv = _expiry_frames()
    r = hr.expiry_report(c, b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004", holder_qual_key="QUAL-003")
    assert r.holders == ("EMP-000006",), "EMP-000007 left"
    renewed = pd.concat([c, _c([_row("EMP-000002", "QUAL-004", D(2026, 11, 1), D(2031, 11, 1), origin="renewal", renews=D(2021, 12, 7))])])
    r2 = hr.expiry_report(renewed, b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert r2.frame.emp_key.tolist() == ["EMP-000001", "EMP-000003"] and r2.counts["superseded"] == 1 and r2.holders == ()
    none = hr.expiry_report(c, b, ev, emp, lv, NOW, expiry_date=D(2030, 1, 1), qual_key="QUAL-004")
    assert none.frame.empty and none.counts["n_expiring"] == 0 and none.counts["rows_expiring_on_date"] == 0


def test_expiry_report_refusals():
    c, b, ev, emp, lv = _expiry_frames()
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.expiry_report(c, b, ev, pd.concat([emp, emp]), lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    with pytest.raises(FrameError, match="lacks column.*free_seats"):
        hr.expiry_report(c, b.drop(columns="free_seats"), ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    with pytest.raises(TypeError):
        hr.expiry_report(c, b, ev, emp, lv, NOW)


def test_registered_and_exported():
    reg = registry.registered()
    for n in ("valid_on", "cert_status_on", "renewal_chains", "booked_renewals", "expiring", "expiry_report"):
        m = reg[f"halvaro.hr.certs.{n}"]
        assert m.sources and all(s.startswith(("competence.", "hr.")) for s in m.sources)
    assert reg["halvaro.hr.certs.expiry_report"].parameters[-4:] == ("expiry_date", "qual_key", "holder_qual_key", "unavailable_leave_types")
    assert {"valid_on", "cert_status_on", "renewal_chains", "booked_renewals", "expiring", "expiry_report", "ExpiryReport"} <= set(hr.__all__) and registry.check() == []


# baseline


# review fixes

def test_a_later_issue_that_is_shorter_or_already_expired_does_not_supersede():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2030, 1, 1)), _row("EMP-000001", "QUAL-001", D(2022, 1, 1), D(2024, 1, 1), origin="renewal", renews=D(2020, 1, 1))])
    assert hr.cert_status_on(c, D(2023, 1, 1)).status_on.tolist() == ["superseded", "valid"]
    s = hr.cert_status_on(c, D(2025, 1, 1)).status_on.tolist()
    assert s == ["valid", "expired"], "the later issue ran out; the first one is the one in force"
    v = hr.valid_on(c, D(2025, 1, 1))
    assert v.issued.tolist() == [pd.Timestamp(2020, 1, 1)] and len(v) == 1
    cl = _c([_row("EMP-000001", "QUAL-004", D(2021, 12, 7), EXPIRY), _row("EMP-000001", "QUAL-004", D(2022, 1, 1), D(2026, 6, 1), origin="renewal", renews=D(2021, 12, 7))])
    emp = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_date": [None], "legal_entity_key": ["LE-01"]})
    r = hr.expiry_report(cl, _booked([]), _ev([]), emp, pd.DataFrame(columns=["emp_key", "leave_type", "start", "end"]), NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert r.counts["n_expiring"] == 1 and r.counts["superseded"] == 0


def test_tied_issue_dates_do_not_depend_on_the_input_order_and_do_not_supersede_each_other():
    a = _row("EMP-000001", "QUAL-001", D(2022, 1, 1), D(2025, 12, 31), event=1)
    b = _row("EMP-000001", "QUAL-001", D(2022, 1, 1), D(2022, 12, 31), event=2)
    for rows in ([a, b], [b, a]):
        c = _c(rows)
        v = hr.valid_on(c, D(2022, 6, 1))
        assert v.expires.tolist() == [pd.Timestamp(2025, 12, 31)] and set(hr.cert_status_on(c, D(2022, 6, 1)).status_on) == {"valid"}
        assert hr.renewal_chains(c).event_no.tolist() == [2, 1], "ties are ordered by expiry then event_no"
    openended = _c([_row("EMP-000001", "QUAL-001", D(2022, 1, 1), None, event=3), a])
    assert hr.valid_on(openended, D(2024, 1, 1)).expires.isna().all()


def test_chain_lapse_and_overlap_use_everything_issued_before_and_only_for_linked_renewals():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2030, 1, 1), event=1), _row("EMP-000001", "QUAL-001", D(2021, 1, 1), D(2022, 1, 1), origin="renewal", renews=D(2020, 1, 1), event=2),
            _row("EMP-000001", "QUAL-001", D(2025, 1, 1), D(2028, 1, 1), origin="renewal", renews=D(2021, 1, 1), event=3),
            _row("EMP-000002", "QUAL-001", D(2020, 1, 1), None, event=4), _row("EMP-000002", "QUAL-001", D(2023, 1, 1), D(2026, 1, 1), origin="renewal", renews=D(2020, 1, 1), event=5),
            _row("EMP-000003", "QUAL-001", D(2020, 1, 1), D(2021, 1, 1), event=6), _row("EMP-000003", "QUAL-001", D(2025, 1, 1), D(2028, 1, 1), origin="renewal", renews=D(1999, 1, 1), event=7)])
    ch = hr.renewal_chains(c).set_index("event_no")
    assert ch.loc[3, "lapse_days"] == 0 and ch.loc[3, "covered_until"] == pd.Timestamp(2030, 1, 1) and ch.loc[3, "overlap_days"] == (pd.Timestamp(2030, 1, 1) - pd.Timestamp(2025, 1, 1)).days + 1
    assert pd.isna(ch.loc[5, "covered_until"]) and ch.loc[5, "lapse_days"] == 0 and pd.isna(ch.loc[5, "overlap_days"]), "an open ended earlier issue covers for ever"
    assert not ch.loc[7, "link_ok"] and pd.isna(ch.loc[7, "lapse_days"]) and pd.isna(ch.loc[7, "overlap_days"])


def test_a_leave_on_any_day_of_a_multi_day_course_counts():
    c = _c([_row("EMP-000001", "QUAL-004", D(2021, 12, 7), EXPIRY)])
    emp = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_date": [None], "legal_entity_key": ["LE-01"]})
    ev = _ev([(10, "QUAL-004", D(2027, 1, 10), 12, 2, "DK", "SITE-01")])
    b = _booked([("EMP-000001", "QUAL-004", D(2027, 1, 10), 10, 10)])
    def on_leave(start, end, kind="extended_leave"):
        lv = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_type": [kind], "start": [start], "end": [end]})
        return hr.expiry_report(c, b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004").frame.on_leave_at_course.iloc[0]
    assert on_leave(D(2027, 1, 11), D(2027, 1, 12)) and on_leave(D(2027, 1, 1), D(2027, 1, 10)) and on_leave(D(2027, 1, 11), None)
    assert not on_leave(D(2027, 1, 12), D(2027, 1, 20)) and not on_leave(D(2027, 1, 1), D(2027, 1, 9)) and not on_leave(D(2027, 1, 10), D(2027, 1, 11), kind="sick")
    r = hr.expiry_report(c, b, ev, emp, pd.DataFrame(columns=["emp_key", "leave_type", "start", "end"]), NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert r.frame.on_leave_at_course.dtype == bool


def test_booked_renewals_refuse_duplicate_seats_and_mismatched_inputs():
    ev = _ev([(1, "QUAL-004", D(2027, 1, 14), 12, 4, "DK", "SITE-01")])
    att = _att([(1, "EMP-000001", None, "booked"), (1, "EMP-000001", None, "booked")])
    with pytest.raises(FrameError, match="appear twice"):
        hr.booked_renewals(att, ev, NOW, _rel())
    with pytest.raises(FrameError, match="mapping"):
        hr.booked_renewals(att.iloc[:1], ev, NOW, _rel()["competence"])
    with pytest.raises(FrameError, match="lacks column.*end_date"):
        hr.booked_renewals(att.iloc[:1], ev.drop(columns="end_date"), NOW, _rel())
    with pytest.raises(FrameError, match="do not match in type"):
        hr.booked_renewals(att.iloc[:1].assign(event_no="1"), ev, NOW, _rel())


def test_expiring_checks_its_inputs():
    c = _c([_row("EMP-000001", "QUAL-001", D(2023, 1, 1), D(2027, 1, 14))])
    v = hr.valid_on(c, NOW)
    b = _booked([("EMP-000001", "QUAL-001", D(2026, 11, 1), 5, 5), ("EMP-000001", "QUAL-001", D(2026, 12, 20), 6, 5)])
    x = hr.expiring(v, b, NOW)
    assert x.event_no.tolist() == [6] and x.gap_days.tolist() == [0.0], "a course before the date is not a cover"
    with pytest.raises(FrameError, match="valid frame is for 2026-11-30, not 2026-12-01"):
        hr.expiring(v, b, D(2026, 12, 1))
    for bad in (None, 90.5, "90", True, -1):
        with pytest.raises(FrameError, match="window_days"):
            hr.expiring(v, b, NOW, window_days=bad)
    with pytest.raises(FrameError, match="more than one row"):
        hr.expiring(pd.concat([v, v]), b, NOW)
    extra = v.assign(event_no=9, free_seats=1)
    assert hr.expiring(extra, b, NOW).event_no.tolist() == [6]
    assert hr.expiring(v, b, NOW).as_of.dtype == "datetime64[ns]" and hr.valid_on(c, NOW).as_of.dtype == "datetime64[ns]"


def test_date_columns_as_text_numbers_and_string_dtype():
    c = _c([_row("EMP-000001", "QUAL-001", "2020-01-01 10:00", "2030-01-01")])
    assert hr.valid_on(c.astype({"issued": "string", "expires": "string"}), NOW).issued.tolist() == [pd.Timestamp(2020, 1, 1)]
    assert hr.valid_on(c, NOW).issued.tolist() == [pd.Timestamp(2020, 1, 1)]
    with pytest.raises(FrameError, match="holds numbers, not dates"):
        hr.valid_on(c.assign(issued=20200101), NOW)


# survivors of the mutation review

def _expiry_args():
    c, b, ev, emp, lv = _expiry_frames()
    return c, b, ev, emp, lv


def test_expiry_leave_types_parameter_and_plain_string():
    c, b, ev, emp, lv = _expiry_args()
    sick = pd.DataFrame({"emp_key": ["EMP-000002"], "leave_type": ["sick"], "start": [D(2027, 1, 1)], "end": [D(2027, 3, 1)]})
    b2 = pd.concat([b, _booked([("EMP-000002", "QUAL-004", D(2027, 1, 14), 10, 10)])])
    for types in (("sick",), "sick"):
        r = hr.expiry_report(c, b2, ev, emp, sick, NOW, expiry_date=EXPIRY, qual_key="QUAL-004", unavailable_leave_types=types)
        assert r.frame.set_index("emp_key").on_leave_at_course["EMP-000002"]
    assert not hr.expiry_report(c, b2, ev, emp, sick, NOW, expiry_date=EXPIRY, qual_key="QUAL-004").frame.set_index("emp_key").on_leave_at_course["EMP-000002"]


def test_expiry_only_counts_the_named_qualification_and_the_date_of_the_report():
    c, b, ev, emp, lv = _expiry_args()
    other = _c([_row("EMP-000001", "QUAL-009", D(2021, 12, 7), EXPIRY), _row("EMP-000006", "QUAL-009", D(2021, 12, 7), EXPIRY)])
    r = hr.expiry_report(pd.concat([c, other]), b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert r.frame.emp_key.tolist() == ["EMP-000001", "EMP-000002", "EMP-000003"] and r.counts["rows_expiring_on_date"] == 4 and r.counts["former_employees"] == 1
    other_booking = pd.concat([b, _booked([("EMP-000002", "QUAL-009", D(2027, 1, 5), 99, 1)])])
    assert hr.expiry_report(c, other_booking, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004").frame.set_index("emp_key").booked["EMP-000002"] == False
    renewal_later = pd.concat([c, _c([_row("EMP-000002", "QUAL-004", D(2026, 12, 15), D(2031, 12, 15), origin="renewal", renews=D(2021, 12, 7))])])
    r2 = hr.expiry_report(renewal_later, b, ev, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert "EMP-000002" in r2.frame.emp_key.tolist(), "a renewal issued after the report date is not known yet"
    after = hr.expiry_report(c, b, ev, emp, lv, D(2027, 1, 5), expiry_date=EXPIRY, qual_key="QUAL-004")
    assert after.frame.empty and after.counts["n_expiring"] == 0 and after.counts["superseded"] == 0, "after the expiry date nobody holds it any more"


def test_earliest_booked_course_wins_in_expiry_report_and_expiring_whatever_the_input_order():
    c = _c([_row("EMP-000001", "QUAL-004", D(2021, 12, 7), EXPIRY)])
    emp = pd.DataFrame({"emp_key": ["EMP-000001"], "leave_date": [None], "legal_entity_key": ["LE-01"]})
    b = _booked([("EMP-000001", "QUAL-004", D(2027, 2, 17), 11, 3), ("EMP-000001", "QUAL-004", D(2027, 1, 14), 10, 7)])
    nolv = pd.DataFrame(columns=["emp_key", "leave_type", "start", "end"])
    r = hr.expiry_report(c, b, _ev([]), emp, nolv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert r.frame.event_no.tolist() == [10] and r.frame.free_seats.tolist() == [7] and r.frame.legal_entity_key.tolist() == ["LE-01"]
    x = hr.expiring(hr.valid_on(c, NOW), b, NOW, window_days=60)
    assert x.event_no.tolist() == [10]
    early = _booked([("EMP-000001", "QUAL-004", D(2026, 12, 1), 12, 4)])
    assert hr.expiry_report(c, early, _ev([]), emp, nolv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004").frame.gap_days.tolist() == [0.0], "a course before the expiry leaves no gap"
    past = _booked([("EMP-000001", "QUAL-004", NOW, 13, 4), ("EMP-000001", "QUAL-004", D(2026, 10, 1), 14, 4)])
    assert hr.expiry_report(c, past, _ev([]), emp, nolv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004").frame.booked.tolist() == [False], "a course on or before the report date is not a booking"
    assert hr.expiring(hr.valid_on(c, NOW), past, NOW).booked.tolist() == [False]


def test_supersede_with_an_open_ended_or_just_ending_later_issue():
    first = _row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2030, 1, 1), event=1)
    open_later = _row("EMP-000001", "QUAL-001", D(2022, 1, 1), None, origin="renewal", renews=D(2020, 1, 1), event=2)
    assert hr.cert_status_on(_c([first, open_later]), D(2025, 1, 1)).status_on.tolist() == ["superseded", "valid"]
    ends_today = _row("EMP-000001", "QUAL-001", D(2022, 1, 1), D(2025, 1, 1), origin="renewal", renews=D(2020, 1, 1), event=2)
    assert hr.cert_status_on(_c([first, ends_today]), D(2025, 1, 1)).status_on.tolist() == ["superseded", "valid"], "the later issue is valid on its last day"
    assert hr.cert_status_on(_c([first, ends_today]), D(2025, 1, 2)).status_on.tolist() == ["valid", "expired"]


def test_a_person_who_leaves_on_the_report_date_is_still_current_and_a_stranger_is_not():
    c, b, ev, emp, lv = _expiry_args()
    emp2 = emp.assign(leave_date=[None, None, D(2026, 11, 30), D(2026, 11, 1), None, None, D(2026, 10, 1)])
    r = hr.expiry_report(c, b, ev, emp2, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004", holder_qual_key="QUAL-003")
    assert "EMP-000003" in r.frame.emp_key.tolist() and r.counts["former_employees"] == 1
    r2 = hr.expiry_report(c, b, ev, emp.iloc[1:], lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert "EMP-000001" not in r2.frame.emp_key.tolist() and r2.counts["former_employees"] == 2, "no row in hr.employee: not a current employee"


def test_events_on_the_report_date_are_not_after_it_and_a_cert_frame_without_status_is_accepted():
    c, b, ev, emp, lv = _expiry_args()
    ev2 = pd.concat([ev, _ev([(20, "QUAL-004", NOW, 12, 1, "DK", "SITE-01")])])
    r = hr.expiry_report(c.drop(columns="status"), b, ev2, emp, lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004")
    assert 20 not in r.events.event_no.tolist() and r.events.event_no.tolist() == [10, 11]


def test_booked_renewals_edge_cases():
    ev = _ev([(1, "QUAL-004", NOW, 12, 4, "DK", "SITE-01"), (2, "QUAL-004", D(2027, 1, 14), 12, 12, "DK", "SITE-01")])
    with pytest.raises(FrameError, match="not after 2026-11-30"):
        hr.booked_renewals(_att([(1, "EMP-000001", None, "booked")]), ev, NOW, _rel())
    b = hr.booked_renewals(_att([(2, "EMP-000001", None, "booked")]), ev, NOW, _rel())
    assert b.free_seats.tolist() == [0], "a full course is a valid booking"
    sh = _ev([(1, "QUAL-004", D(2027, 3, 1), 12, 1, "DK", "S"), (2, "QUAL-004", D(2027, 1, 14), 12, 1, "DE", "S")])
    out = hr.booked_renewals(_att([(1, "EMP-000002", None, "booked"), (2, "EMP-000002", None, "booked"), (1, "EMP-000001", None, "booked")]), sh, NOW, _rel())
    assert out[["emp_key", "event_no"]].values.tolist() == [["EMP-000001", 1], ["EMP-000002", 2], ["EMP-000002", 1]], "by person, then course date"


def test_chain_details_links_per_qualification_and_chain_starts():
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2022, 1, 1), event=1), _row("EMP-000001", "QUAL-001", D(2021, 6, 1), D(2025, 1, 1), origin="renewal", renews=D(2023, 1, 1), event=2),
            _row("EMP-000001", "QUAL-002", D(2020, 1, 1), D(2022, 1, 1), event=3), _row("EMP-000001", "QUAL-002", D(2023, 1, 1), D(2026, 1, 1), event=4)])
    ch = hr.renewal_chains(c).set_index("event_no")
    assert not ch.loc[2, "link_ok"], "renews_issued after the previous issue is no link"
    assert ch.chain.to_dict() == {1: 1, 2: 1, 3: 1, 4: 2}, "chains count per person and qualification, a course starts a new one"
    assert pd.isna(ch.loc[4, "lapse_days"]) and pd.isna(ch.loc[4, "overlap_days"]), "a chain start has no lapse to measure"


def test_input_validation_and_small_boundaries():
    same_day = _c([_row("EMP-000001", "QUAL-001", D(2024, 1, 1), D(2024, 1, 1))])
    assert hr.valid_on(same_day, D(2024, 1, 1)).emp_key.tolist() == ["EMP-000001"] and hr.valid_on(same_day, D(2024, 1, 2)).empty
    with pytest.raises(FrameError, match="need emp_key, qual_key and issued"):
        hr.valid_on(_c([_row(None, "QUAL-001", D(2024, 1, 1), None)]), NOW)
    with pytest.raises(FrameError, match="need emp_key, qual_key and issued"):
        hr.valid_on(_c([_row("EMP-000001", None, D(2024, 1, 1), None)]), NOW)
    with pytest.raises(FrameError, match="duplicate column names"):
        hr.valid_on(pd.concat([same_day, same_day[["issued"]]], axis=1), NOW)
    c = _c([_row("EMP-000001", "QUAL-001", D(2020, 1, 1), None, status="valid")])
    assert hr.cert_status_on(c, NOW, stored_at=D(2027, 1, 1)).matches_stored.isna().all()
    assert hr.cert_status_on(c, NOW, stored_at=NOW).matches_stored.tolist() == [True]


def test_outputs_are_sorted_whatever_the_input_order():
    c = _c([_row("EMP-000002", "QUAL-002", D(2020, 1, 1), None), _row("EMP-000001", "QUAL-003", D(2020, 1, 1), None), _row("EMP-000001", "QUAL-001", D(2020, 1, 1), None)])
    assert hr.valid_on(c, NOW)[["emp_key", "qual_key"]].values.tolist() == [["EMP-000001", "QUAL-001"], ["EMP-000001", "QUAL-003"], ["EMP-000002", "QUAL-002"]]
    exp = _c([_row("EMP-000003", "QUAL-001", D(2020, 1, 1), D(2027, 1, 20)), _row("EMP-000002", "QUAL-001", D(2020, 1, 1), D(2027, 1, 10)), _row("EMP-000001", "QUAL-001", D(2020, 1, 1), D(2027, 1, 10))])
    assert hr.expiring(hr.valid_on(exp, NOW), _booked([]), NOW).emp_key.tolist() == ["EMP-000001", "EMP-000002", "EMP-000003"]
    c2, b, ev, emp, lv = _expiry_args()
    r = hr.expiry_report(c2.iloc[::-1], b.iloc[::-1], ev.iloc[::-1], emp.iloc[::-1], lv, NOW, expiry_date=EXPIRY, qual_key="QUAL-004", holder_qual_key="QUAL-003")
    assert r.frame.emp_key.tolist() == sorted(r.frame.emp_key) and r.events.event_no.tolist() == [10, 11]


def test_no_registered_hr_function_is_private():
    """A helper that keeps a stray @function decorator would be listed in the index and the KB as a public function."""
    private = [k for k in registry.registered() if k.startswith("halvaro.hr.") and any(part.startswith("_") for part in k.split("."))]
    assert private == []
    assert "halvaro.hr.certs.education_level" in registry.registered()
