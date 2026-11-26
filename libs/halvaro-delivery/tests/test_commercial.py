"""Commercial (plan 5.8): hand computed opportunities and their boundaries."""

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")


def _opp(rows):
    c = ["opp_key", "name", "cus_key", "stage", "is_open", "project_type", "country", "soil_class", "route_length_m", "zone_key", "bid_deadline", "requirements", "carbon_limit_kgco2e_per_m", "created_date",
         "decision_date", "expected_value_dkk"]
    return pd.DataFrame(rows, columns=c)


OPP = _opp([("O1", "a", "C1", "tender", True, "dh_network", "DE", "clay", 6000.0, "Z3", "2026-12-18", "req", np.nan, "2026-02-01", None, 100.0),
            ("O2", "b", "C1", "tender", True, "dh_network", "DK", "sand", 100.0, "Z1", "2026-11-20", None, 90.0, "2026-01-01", None, 100.0),
            ("O3", "c", "C2", "lead", True, "dh_station", "DK", "sand", np.nan, None, "2027-01-10", None, np.nan, "2026-10-01", None, 100.0),
            ("O4", "d", "C2", "tender", True, "dh_network", "DK", "sand", 50.0, None, "2027-02-01", None, np.nan, "2027-01-01", None, 100.0),
            ("O5", "e", "C1", "won", False, "dh_network", "DK", "sand", 50.0, None, "2025-02-01", None, np.nan, "2025-01-01", "2025-03-10", 1000.0),
            ("O6", "f", "C2", "lost", False, "dh_network", "DK", "sand", 50.0, None, "2025-05-01", None, np.nan, "2025-01-01", "2025-06-01", 700.0),
            ("O7", "g", "C2", "lost", False, "dh_network", "DK", "sand", 50.0, None, "2026-01-01", None, np.nan, "2025-11-01", "2026-01-15", 300.0),
            ("O8", "h", "C1", "withdrawn", False, "dh_network", "DK", "sand", 50.0, None, "2025-04-01", None, np.nan, "2025-01-01", "2025-05-05", 200.0),
            ("O9", "i", "C2", "won", False, "dh_network", "DK", "sand", 50.0, None, "2026-01-01", None, np.nan, "2025-12-01", "2026-02-02", 500.0)])
CUS = pd.DataFrame({"cus_key": ["C1", "C2", "C3"], "name": ["One", "Two", "Three"], "tier": ["anchor", "standard", "occasional"]})


def test_open_tenders_stage_creation_day_and_deadline_flag():
    t = delivery.open_tenders(OPP, "2026-11-30", context=CTX)
    assert t.opp_key.tolist() == ["O2", "O1"], "sorted by deadline; O4 was created after the day, O3 is a lead"
    assert t.days_to_deadline.tolist() == [-10, 18] and t.deadline_passed.tolist() == [True, False], "a passed deadline is shown, not hidden"
    assert delivery.open_tenders(OPP, "2026-11-30", stages=("tender", "lead"), context=CTX).opp_key.tolist() == ["O2", "O1", "O3"]
    assert delivery.open_tenders(OPP, "2027-01-02", context=CTX).opp_key.tolist() == ["O2", "O1", "O4"]
    assert delivery.open_tenders(OPP.assign(is_open=False), "2026-11-30", context=CTX).empty
    with pytest.raises(FrameError, match="stages"):
        delivery.open_tenders(OPP, "2026-11-30", stages="tender", context=CTX)
    with pytest.raises(FrameError, match="more than one"):
        delivery.open_tenders(pd.concat([OPP, OPP.iloc[:1]]), "2026-11-30", context=CTX)
    with pytest.raises(FrameError, match="is_open"):
        delivery.open_tenders(OPP.assign(is_open=[None] + OPP.is_open.tolist()[1:]), "2026-11-30", context=CTX)


def test_tender_profile_row_and_refusals():
    r = delivery.tender_profile(OPP, "O1", context=CTX)
    assert (r["type"], r["country"], r["soil_class"], r["route_length_m"], str(r["bid_deadline"].date())) == ("dh_network", "DE", "clay", 6000.0, "2026-12-18")
    with pytest.raises(FrameError, match="not in"):
        delivery.tender_profile(OPP, "O99", context=CTX)
    with pytest.raises(FrameError, match="one text"):
        delivery.tender_profile(OPP, ["O1"], context=CTX)
    assert np.isnan(delivery.tender_profile(OPP, "O3", context=CTX)["route_length_m"]), "a null length stays null"


def test_customer_carbon_limit_rows_and_refusals():
    r = delivery.customer_carbon_limit(OPP, context=CTX)
    assert r.opp_key.tolist() == ["O2"] and r.carbon_limit_kgco2e_per_m.tolist() == [90.0]
    with pytest.raises(FrameError, match="above zero"):
        delivery.customer_carbon_limit(OPP.assign(carbon_limit_kgco2e_per_m=[0.0] + [np.nan] * 8), context=CTX)
    with pytest.raises(FrameError, match="without a customer"):
        delivery.customer_carbon_limit(OPP.assign(cus_key=[None, None] + OPP.cus_key.tolist()[2:]), context=CTX)


def test_win_rate_from_won_over_decided_by_period_and_tier():
    y = delivery.win_rate(OPP, CUS, by_tier=False, context=CTX).set_index("period")
    assert y.loc["2025"].tolist() == [1, 1, 2, 0.5, 1] and y.loc["2026"].tolist() == [1, 1, 2, 0.5, 0], "withdrawn is neither won nor lost"
    t = delivery.win_rate(OPP, CUS, context=CTX).set_index(["period", "tier"])
    assert t.loc[("2025", "anchor"), "win_rate"] == 1.0 and t.loc[("2025", "standard"), "win_rate"] == 0.0 and t.loc[("2025", "anchor"), "withdrawn"] == 1
    q = delivery.win_rate(OPP, CUS, freq="quarter", by_tier=False, context=CTX).set_index("period")
    assert q.index.tolist() == ["2025-Q1", "2025-Q2", "2026-Q1"] and q.loc["2025-Q2", "withdrawn"] == 1
    a = delivery.win_rate(OPP, CUS, freq=None, by_tier=False, context=CTX)
    assert a.period.tolist() == ["all"] and a.win_rate.tolist() == [0.5]
    only_w = delivery.win_rate(OPP[OPP.stage == "withdrawn"], CUS, freq=None, by_tier=False, context=CTX)
    assert np.isnan(only_w.win_rate.iloc[0]) and only_w.decided.iloc[0] == 0, "nothing decided: no rate"
    sh = pd.DataFrame({"opp_key": ["O5", "O6"], "stage": ["won", "lost"], "entered_date": ["2025-03-10", "2025-06-01"]})
    assert delivery.win_rate(OPP, CUS, sh, by_tier=False, context=CTX).win_rate.notna().all()
    with pytest.raises(FrameError, match="stage history"):
        delivery.win_rate(OPP, CUS, sh.assign(entered_date=["2025-03-11", "2025-06-01"]), by_tier=False, context=CTX)
    with pytest.raises(FrameError, match="no decision date"):
        delivery.win_rate(OPP.assign(decision_date=[None] * 5 + ["2025-03-10"] * 4), CUS, context=CTX)
    with pytest.raises(FrameError, match="does not hold"):
        delivery.win_rate(OPP, CUS.iloc[:1], context=CTX)
    with pytest.raises(FrameError, match="freq"):
        delivery.win_rate(OPP, CUS, freq="week", context=CTX)


PRJ = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "customer_key": ["C1", "C1", "C2"], "status": ["active", "completed", "active"]})
CON = pd.DataFrame({"con_key": ["K1", "K2", "K3"], "cus_key": ["C1", None, "C2"], "type": ["customer_project", "supplier_framework", "customer_service"]})


def test_customer_projects_by_customer_and_tier():
    c = delivery.customer_projects(CUS, PRJ, CON, OPP, context=CTX).set_index("cus_key")
    assert c.loc["C1", ["n_projects", "n_active", "n_contracts", "won_value_dkk"]].tolist() == [2, 1, 1, 1000.0] and c.loc["C3", ["n_projects", "n_contracts", "won_value_dkk"]].tolist() == [0, 0, 0.0]
    assert c.loc["C2", "won_value_dkk"] == 500.0
    t = delivery.customer_projects(CUS, PRJ, CON, OPP, by="tier", context=CTX)
    assert t.tier.tolist() == ["anchor", "standard", "occasional"], "tier order, not alphabetical"
    assert t.share_of_projects.tolist() == [0.6667, 0.3333, 0.0] and t.share_of_won_value.tolist() == [0.6667, 0.3333, 0.0]
    assert "won_value_dkk" not in delivery.customer_projects(CUS, PRJ, CON, context=CTX).columns
    assert delivery.customer_projects(CUS, PRJ, CON, contract_types=("supplier_framework",), context=CTX).n_contracts.sum() == 0
    with pytest.raises(FrameError, match="does not hold"):
        delivery.customer_projects(CUS, PRJ.assign(customer_key=["C1", "C1", "C9"]), CON, context=CTX)
    with pytest.raises(FrameError, match="by is"):
        delivery.customer_projects(CUS, PRJ, CON, by="x", context=CTX)
    with pytest.raises(FrameError, match="contract_types"):
        delivery.customer_projects(CUS, PRJ, CON, contract_types="customer_project", context=CTX)


def test_registration_and_stage():
    for n in ("open_tenders", "tender_profile", "customer_carbon_limit", "win_rate", "customer_projects"):
        assert f"halvaro.delivery.commercial.{n}" in registry.registered() and n in delivery.__all__
    with pytest.raises(StageRefusal):
        delivery.win_rate(OPP, CUS, context=Context(stage="month3", role="r"))
