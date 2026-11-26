"""Requests (plan 5.8): status from dates, the tender cross-check, the answer pack and the time to answer."""

import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, registry

M12 = Context(stage="month12", role="r")


def _r(rows):
    return pd.DataFrame(rows, columns=["cus_key", "request_no", "request_type", "received", "due", "answered_date", "status", "opp_key", "limit_kgco2e_per_m"])


R = _r([("C1", 1, "annual_questionnaire", "2026-01-10", "2026-02-10", "2026-02-01", "answered", None, None), ("C1", 2, "annual_questionnaire", "2026-03-01", "2026-04-01", None, "open", None, None),
        ("C2", 1, "tender_requirement", "2026-02-09", "2026-12-11", None, "open", "OPP-1", 90.0), ("C2", 2, "project_footprint_report", "2026-05-01", "2026-05-20", "2026-05-25", "answered", None, None)])


def test_open_requests_status_from_dates_not_from_the_snapshot():
    r = esg.open_requests(R, "2026-04-02", context=M12).set_index(["cus_key", "request_no"])
    assert r.loc[("C1", 1), "status_as_of"] == "answered" and r.loc[("C1", 2), "status_as_of"] == "overdue" and r.loc[("C2", 1), "status_as_of"] == "open"
    assert r.loc[("C2", 2), "status_as_of"] == "not_received" and esg.open_requests(R, "2026-06-01", context=M12).set_index(["cus_key", "request_no"]).loc[("C2", 2), "status_as_of"] == "answered" and r.loc[("C1", 2), "days_to_due"] == -1 and r.loc[("C2", 1), "days_to_due"] == 253
    e = esg.open_requests(R, "2026-04-01", context=M12).set_index(["cus_key", "request_no"])
    assert e.loc[("C1", 2), "status_as_of"] == "open" and e.loc[("C1", 2), "days_to_due"] == 0, "due on the day is not overdue"
    early = esg.open_requests(R, "2026-05-22", context=M12).set_index(["cus_key", "request_no"])
    assert early.loc[("C2", 2), "status_as_of"] == "overdue" and pd.isna(early.loc[("C2", 2), "answered_date"]), "answered on the 25th: not yet answered on the 22nd"
    assert esg.open_requests(R, "2026-01-01", context=M12).status_as_of.eq("not_received").all()
    assert not esg.open_requests(R.assign(status="answered"), "2026-04-02", context=M12).status_agrees.all(), "the snapshot status is informative only"
    assert not esg.open_requests(R, "2026-04-02", context=M12).set_index(["cus_key", "request_no"]).loc[("C1", 2), "status_agrees"], "stored open, overdue by the dates: a difference, not hidden"
    rec = esg.open_requests(R, "2026-01-10", context=M12).set_index(["cus_key", "request_no"])
    assert rec.loc[("C1", 1), "status_as_of"] == "open", "received on the day is received"
    ans = esg.open_requests(R, "2026-02-01", context=M12).set_index(["cus_key", "request_no"])
    assert ans.loc[("C1", 1), "status_as_of"] == "answered", "answered on the day counts as answered"


def test_open_requests_refusals():
    with pytest.raises(FrameError, match="more than one"):
        esg.open_requests(pd.concat([R, R.iloc[:1]]), "2026-04-02", context=M12)
    with pytest.raises(FrameError, match="due before"):
        esg.open_requests(R.assign(due=["2025-01-01"] * 4), "2026-04-02", context=M12)
    with pytest.raises(FrameError, match="not a date"):
        esg.open_requests(R.assign(due=["x"] * 4), "2026-04-02", context=M12)
    with pytest.raises(FrameError, match="as_of"):
        esg.open_requests(R, 20260402, context=M12)
    with pytest.raises(FrameError, match="numbers"):
        esg.open_requests(R.assign(due=[20260110] * 4), "2026-04-02", context=M12)


def test_tender_limit_cross_check_reports_and_never_corrects():
    cl = pd.DataFrame({"opp_key": ["OPP-1"], "carbon_limit_kgco2e_per_m": [90.0]})
    ot = pd.DataFrame({"opp_key": ["OPP-1"], "bid_deadline": ["2026-12-11"]})
    t = esg.tender_limit(R, cl, ot, context=M12)
    assert len(t) == 1 and t[0].limit_agrees is True and t[0].due_agrees is True and t[0].warnings == () and t[0].crm_limit == 90.0
    bad = esg.tender_limit(R, cl.assign(carbon_limit_kgco2e_per_m=95.0), ot.assign(bid_deadline="2026-12-12"), context=M12)[0]
    assert bad.limit_kgco2e_per_m == 90.0 and bad.limit_agrees is False and bad.due_agrees is False and len(bad.warnings) == 2, "reported, never corrected"
    assert "not cross-checked" in esg.tender_limit(R, context=M12)[0].warnings[0]
    assert "partly" in esg.tender_limit(R, cl, context=M12)[0].warnings[0] and "limit only" in esg.tender_limit(R, cl, context=M12)[0].warnings[0]
    assert any("customer" in w for w in esg.tender_limit(R, cl.assign(cus_key="C9"), ot, context=M12)[0].warnings)
    assert esg.tender_limit(R, cl.assign(cus_key="C2"), ot, context=M12)[0].warnings == ()
    assert any("missing" in w for w in esg.tender_limit(R, cl, ot.assign(bid_deadline=None), context=M12)[0].warnings)
    assert "no limit on the crm side" in esg.tender_limit(R, cl.assign(opp_key="OPP-9"), ot, context=M12)[0].warnings[0]
    with pytest.raises(FrameError, match="needs an opp_key"):
        esg.tender_limit(R.assign(opp_key=None), context=M12)
    with pytest.raises(FrameError, match="more than one"):
        esg.tender_limit(R, pd.concat([cl, cl]), ot, context=M12)


def test_answer_pack_follows_the_basis_of_the_totals_and_refuses_one_entity():
    tot = pd.DataFrame({"le_key": ["ALL"], "basis": ["first_booked"], "year": [2025], "months": [12], "scope1": [100.0], "scope2_location": [50.0], "scope2_market": [80.0], "scope3": [400.0]})
    tg = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2023], "target_year": [2030], "reduction_percent": [42.0], "basis": ["a"], "status": ["adopted"]})
    assert "first_booked basis" in esg.answer_pack(R.iloc[:1], tot, tg, context=M12)["notes"][0]
    assert "current basis: earlier" in esg.answer_pack(R.iloc[:1], tot.assign(basis="current"), tg, context=M12)["notes"][0]
    with pytest.raises(FrameError, match="whole company"):
        esg.answer_pack(R.iloc[:1], tot.assign(le_key="LE-01"), tg, context=M12)
    with pytest.raises(FrameError, match="nulls"):
        esg.answer_pack(R.iloc[:1], tot.assign(scope1=None), tg, context=M12)


def test_answer_pack_keeps_both_scope_2_values_and_never_adds_them():
    tot = pd.DataFrame({"year": [2025], "months": [12], "scope1": [100.0], "scope2_location": [50.0], "scope2_market": [80.0], "scope3": [400.0]})
    tg = pd.DataFrame({"target_no": [2, 1], "scope": ["2_location", "1"], "baseline_year": [2023, 2023], "target_year": [2030, 2030], "reduction_percent": [50.0, 42.0], "basis": ["a", "b"], "status": ["adopted"] * 2})
    p = esg.answer_pack(R.iloc[:1], tot, tg, context=M12)
    assert (p["scope2_location"], p["scope2_market"]) == (50.0, 80.0) and "scope2" not in p and [t["target_no"] for t in p["targets"]] == [1, 2]
    assert any("not added" in n for n in p["notes"]) and not any("months of data" in n for n in p["notes"])
    assert any("11 months" in n for n in esg.answer_pack(R.iloc[:1], tot.assign(months=11), tg, context=M12)["notes"])
    with pytest.raises(FrameError, match="one request row"):
        esg.answer_pack(R, tot, tg, context=M12)


def test_request_timeliness_by_type_and_as_of():
    t = esg.request_timeliness(R, context=M12).set_index("request_type")
    assert t.loc["annual_questionnaire", "n"] == 2 and t.loc["annual_questionnaire", "n_answered"] == 1 and t.loc["annual_questionnaire", "mean_days_to_answer"] == 22.0 and t.loc["annual_questionnaire", "share_on_time"] == 1.0
    assert t.loc["project_footprint_report", "share_on_time"] == 0.0 and t.loc["project_footprint_report", "mean_days_to_answer"] == 24.0, "answered 5 days after the due date"
    assert pd.isna(t.loc["tender_requirement", "share_on_time"])
    e = esg.request_timeliness(R, as_of="2026-05-22", context=M12).set_index("request_type")
    assert e.loc["project_footprint_report", "n_answered"] == 0 and "tender_requirement" in e.index
    with pytest.raises(FrameError, match="without a request_type"):
        esg.request_timeliness(R.assign(request_type=[None, "x", "y", "z"]), context=M12)
    with pytest.raises(FrameError, match="before it was received"):
        esg.request_timeliness(R.assign(answered_date=["2025-01-01", None, None, None]), context=M12)


def test_registration():
    for n in ("open_requests", "tender_limit", "answer_pack", "request_timeliness"):
        assert f"halvaro.esg.data_requests.{n}" in registry.registered() and n in esg.__all__
