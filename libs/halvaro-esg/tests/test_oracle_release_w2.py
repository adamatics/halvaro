"""Release oracle tests of halvaro.esg: answer_pack, energy_use_mwh, lever_report, provenance, tender_estimate.

Every expectation is computed another way than the function: a direct pandas reading of the baseline release tables (groupby, merge, sums), or a property that must hold on the release
(the pack carries exactly the totals and targets it was given, sums of parts equal the total, the union of the inputs is the union of the result, a tender that costs what the comparables
cost is estimated at their footprint). The inputs of the assembling functions are built from the release with the library's own functions; computed is compared with computed, no figure of the
release is written into a test.
"""
import datetime as dt

import pandas as pd

import halvaro.esg as esg
from halvaro.core import Context, Envelope

M12 = Context(stage="month12", role="r")


# ---- lever_report


def test_oracle_lever_report_a_footprint_after_the_lever_exactly_at_the_limit_is_below_it_hand_worked():
    """halvaro.esg.levers.lever_report: hand worked boundary. The docstring says below_limit_after is "at or below the limit; a footprint exactly at the limit is not above it".
    100 m at 10 kg/m: lever exact saves 100 kg = 1.00 kg/m, after 9.00 = the limit 9.0 -> True; short saves 99 kg = 0.99 kg/m, after 9.01 -> False; over saves 150 kg, after 8.50 -> True."""
    pm = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0], "kgco2e_per_m": [10.0]})
    levers = pd.DataFrame({"lever": ["exact", "short", "over"], "saved_kgco2e": [100.0, 99.0, 150.0]})
    r = esg.lever_report(pm, levers, 9.0, top=3, context=M12).set_index("lever")
    assert r.loc["exact", "per_m_after"] == 9.0 and bool(r.loc["exact", "below_limit_after"]) is True
    assert r.loc["short", "per_m_after"] == 9.01 and bool(r.loc["short", "below_limit_after"]) is False
    assert bool(r.loc["over", "below_limit_after"]) is True
    # the same boundary where the float subtraction lands a hair above the limit: 10 m at 0.4 kg/m, a saving of 1 kg = 0.1 kg/m, after 0.4 - 0.1 (0.30000000000000004 in binary) against 0.3
    pm2 = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [10.0], "kgco2e_per_m": [0.4]})
    r2 = esg.lever_report(pm2, pd.DataFrame({"lever": ["tenth"], "saved_kgco2e": [1.0]}), 0.3, context=M12)
    assert r2["per_m_after"].tolist() == [0.3] and r2["below_limit_after"].tolist() == [True]


# ---- provenance


def test_oracle_provenance_status_as_of_synthetic_and_factor_sets_hand_worked():
    """halvaro.esg.basis.provenance: hand worked inputs that differ in every joined field (the release inputs share as_of None and one status, so they cannot tell these apart).
    a: ok, as_of 2031-01-31, not synthetic. b: a Provenance, VERIFY, as_of 2030-06-30, synthetic, factor sets set2 and set1. c: synthetic status, no as_of, not synthetic.
    By the docstring: the latest as_of of the inputs, synthetic true if any input is, the status combined from all inputs (VERIFY beats ok, synthetic is kept next to it), the factor sets sorted."""
    a = Envelope(value=1, status="ok", as_of=dt.date(2031, 1, 31), synthetic=False, sources=("energy-esg.emission_line",), warnings=("warn.a",), facts_used=(("fact.a", 1, "verified"),))
    b = esg.Provenance(value=2, status="VERIFY", as_of=dt.date(2030, 6, 30), synthetic=True, sources=("energy-esg.target", "energy-esg.emission_line"), factor_sets=("set2", "set1"), verify_facts=("note.b",))
    c = Envelope(value=3, status="synthetic", as_of=None, synthetic=False)
    p = esg.provenance(a, b, c)
    assert (p.value, p.status, p.as_of, p.synthetic) == (3, "VERIFY+synthetic", dt.date(2031, 1, 31), True)
    assert (p.factor_sets, p.verify_facts, p.sources, p.warnings) == (("set1", "set2"), ("note.b",), ("energy-esg.emission_line", "energy-esg.target"), ("warn.a",))
    assert p.facts_used == (("fact.a", 1, "verified"),)
    ab = esg.provenance(a, b)
    assert (ab.status, ab.as_of, ab.synthetic) == ("VERIFY", dt.date(2031, 1, 31), True), "the status of the second input counts, the later as_of wins"
    ba = esg.provenance(b, a)
    assert (ba.status, ba.as_of, ba.synthetic) == ("VERIFY", dt.date(2031, 1, 31), True), "the order does not matter"
    ac = esg.provenance(a, c)
    assert (ac.status, ac.as_of, ac.synthetic) == ("synthetic", dt.date(2031, 1, 31), False), "no input is synthetic: the result is not; a missing as_of is skipped"
    assert esg.provenance(c).as_of is None and esg.provenance(a).status == "ok"


# ---- tender_estimate


def test_oracle_tender_estimate_hand_worked_two_projects():
    """halvaro.esg.footprint.tender_estimate: hand worked. A (100 m) has tender lines material 1000 EUR, labour 500 EUR and other 50 EUR, and a final line that is not used; its footprint in two months sums to
    materials 100, transport 20, site 40, subcontractor 0, total 160. B (50 m) has labour 300, equipment 200 and subcontractor 400 EUR; footprint materials 60, transport 10, site 30, subcontractor 50, total 150.
    materials: only A carries material cost: (100 + 20 transport) / 1000 = 0.12 kg/EUR (B's 60 + 10 do not count). site: labour and equipment, A 500 + B 500 = 1000 EUR for A 40 + B 30 = 70 kg: 0.07.
    subcontractor: B only, 50 / 400 = 0.125. The tender: material 2000 -> 240.0 kg, labour 1000 -> 70.0 kg, subcontractor 800 -> 100.0 kg, other ignored; 410.0 kg.
    Cross-check: per metre A 160 / 100 = 1.6, B 150 / 50 = 3.0, median 2.3; at 500 m 1150.0 kg; ratio 410 / 1150 = 0.357."""
    EB = pd.DataFrame({"prj_key": ["PRJ-900001"] * 4 + ["PRJ-900002"] * 3, "type": ["tender", "tender", "tender", "final", "tender", "tender", "tender"],
                       "cst_key": ["CST-1", "CST-2", "CST-5", "CST-1", "CST-2", "CST-3", "CST-4"], "amount": [1000.0, 500.0, 50.0, 5000.0, 300.0, 200.0, 400.0], "currency": ["EUR"] * 7})
    CC = pd.DataFrame({"cst_key": ["CST-1", "CST-2", "CST-3", "CST-4", "CST-5"], "category": ["material", "labour", "equipment", "subcontractor", "other"]})
    PF = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001", "PRJ-900002"], "period": ["2025-01", "2025-02", "2025-01"], "materials_kgco2e": [60.0, 40.0, 60.0],
                       "transport_kgco2e": [5.0, 15.0, 10.0], "site_kgco2e": [25.0, 15.0, 30.0], "subcontractor_kgco2e": [0.0, 0.0, 50.0], "total_kgco2e": [90.0, 70.0, 150.0]})
    P = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "route_length_m": [100.0, 50.0]})
    TC = pd.DataFrame({"category": ["material", "labour", "subcontractor", "other"], "amount": [2000.0, 1000.0, 800.0, 999.0], "currency": ["EUR"] * 4})
    r = esg.tender_estimate(EB, CC, PF, P, TC, 500.0, context=M12)
    got = {row.component: (row.intensity_kg_per_unit, row.tender_cost, row.estimated_kg) for row in r.rows.itertuples()}
    assert got == {"materials": (0.12, 2000.0, 240.0), "site": (0.07, 1000.0, 70.0), "subcontractor": (0.125, 800.0, 100.0)}
    assert set(r.rows["currency"]) == {"EUR"}
    assert (r.estimated_kg, r.median_kg_per_m, r.cross_check_kg, r.ratio, r.n_projects) == (410.0, 2.3, 1150.0, 0.357, 2)
