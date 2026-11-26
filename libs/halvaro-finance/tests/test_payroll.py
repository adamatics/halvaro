"""Payroll (plan 5.5): hand computed ledger lines and aggregates, then the baseline release (ledger gross pay, tie-out against the hr aggregate, on-costs, absorption)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal, registry

M3, M12 = Context(stage="month3", role="r"), Context(stage="month12", role="r")
D1 = Context(stage="day1", role="r")


def _jl(rows):
    return pd.DataFrame(rows, columns=["le_key", "cc_key", "gl_key", "period", "amount"])


def test_ledger_gross_pay_sums_the_salary_accounts_per_cost_centre_and_month_in_cents():
    jl = _jl([("LE-01", "CC-1", "GL-7000", "2025-01", 100.005), ("LE-01", "CC-1", "GL-7005", "2025-01", 50.0), ("LE-01", "CC-1", "GL-7050", "2025-01", 10.0), ("LE-01", "CC-1", "GL-7010", "2025-01", 99.0),
              ("LE-01", "CC-2", "GL-7000", "2025-01", 20.0), ("LE-01", "CC-1", "GL-7000", "2025-02", -5.0), ("LE-02", "CC-9", "GL-7000", "2025-01", 1.0), ("LE-01", "CC-1", "GL-1000", "2025-01", 7.0)])
    out = fin.ledger_gross_pay(jl, context=M3).set_index(["le_key", "cc_key", "period"]).ledger_gross_pay
    assert out.loc[("LE-01", "CC-1", "2025-01")] == pytest.approx(160.0, abs=0.011) and out.loc[("LE-01", "CC-2", "2025-01")] == 20.0 and out.loc[("LE-01", "CC-1", "2025-02")] == -5.0
    assert len(out) == 4 and ("LE-01", "CC-1", "2025-01") in out.index, "overtime and other accounts are not gross salary"
    assert fin.ledger_gross_pay(jl, accounts=("GL-7010",), context=M3).ledger_gross_pay.tolist() == [99.0]
    with pytest.raises(FrameError, match="without a cost centre"):
        fin.ledger_gross_pay(jl.assign(cc_key=jl.cc_key.where(jl.index != 0, None)), context=M3)
    for bad in ("GL-7000", ()):
        with pytest.raises(FrameError, match="tuple"):
            fin.ledger_gross_pay(jl, accounts=bad, context=M3)
    with pytest.raises(FrameError, match="lacks column"):
        fin.ledger_gross_pay(jl.drop(columns="cc_key"), context=M3)


def _agg(rows):
    cols = ["le_key", "cc_key", "period", "currency", "hr_gross_pay", "band_minimum_total", "band_maximum_total", "cost_centres", "suppressed"]
    return pd.DataFrame(rows, columns=cols)


def _led(rows):
    return pd.DataFrame(rows, columns=["le_key", "cc_key", "period", "ledger_gross_pay"])


def test_tie_out_tolerance_band_envelope_pooled_groups_and_ledger_only_rows():
    led = _led([("LE-01", "CC-1", "2025-01", 1000.0), ("LE-01", "CC-2", "2025-01", 500.03), ("LE-01", "CC-3", "2025-01", 300.0), ("LE-01", "CC-4", "2025-01", 200.0), ("LE-01", "CC-5", "2025-01", 50.0)])
    hr = _agg([("LE-01", "CC-1", "2025-01", "DKK", 1000.0, 900.0, 1200.0, "CC-1", False), ("LE-01", "CC-2", "2025-01", "DKK", 500.0, 480.0, 520.0, "CC-2", False),
               ("LE-01", "POOLED", "2025-01", "DKK", 500.0, 450.0, 600.0, "CC-3,CC-4", False)])
    r = fin.tie_out(led, hr, context=M3)
    v = r.value.set_index("cc_key")
    assert r.status == ("VERIFY" if r.facts_used[0][2] == "proposed" else "ok")      # lane F3 (issue #543), approved edit: ok once lane F2 accepted the fact (status verified)
    assert r.facts_used[0][0] == "policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk" and r.facts_used[0][2] in ("proposed", "verified") and "not an audit" in r.warnings[0]
    assert v.loc["CC-1", "status"] == "tied" and v.loc["CC-1", "difference"] == 0.0
    assert v.loc["CC-2", "difference"] == 0.03 and bool(v.loc["CC-2", "within_tolerance"]) and v.loc["CC-2", "status"] == "tied", "0.03 is inside 0.05"
    assert v.loc["POOLED", "ledger_gross_pay"] == 500.0 and v.loc["POOLED", "status"] == "tied", "the ledger of CC-3 and CC-4 is added up for the pooled row"
    assert v.loc["CC-5", "status"] == "ledger_only" and v.loc["CC-5", "hr_gross_pay"] != v.loc["CC-5", "hr_gross_pay"]
    assert fin.tie_out(led, hr, tolerance=0.02, context=M3).value.set_index("cc_key").loc["CC-2", "status"] == "difference"
    assert fin.tie_out(led, hr, tolerance=0.02, context=M3).facts_used == ()
    out_of_band = led.assign(ledger_gross_pay=led.ledger_gross_pay.where(led.cc_key != "CC-1", 1230.0))
    h = hr.assign(hr_gross_pay=hr.hr_gross_pay.where(hr.cc_key != "CC-1", 1230.0))
    assert fin.tie_out(out_of_band, h, context=M3).value.set_index("cc_key").loc["CC-1", "status"] == "outside_band", "1230 is above 1200 times 1.02"
    assert fin.tie_out(out_of_band, h, band_ceiling_factor=1.03, context=M3).value.set_index("cc_key").loc["CC-1", "status"] == "tied"
    sup = hr.assign(suppressed=[False, False, True], hr_gross_pay=[1000.0, 500.0, np.nan])
    s = fin.tie_out(led, sup, context=M3).value.set_index("cc_key")
    assert s.loc["POOLED", "status"] == "suppressed" and s.loc["POOLED", "difference"] != s.loc["POOLED", "difference"]


def test_tie_out_refuses_individual_pay_and_bad_inputs():
    led = _led([("LE-01", "CC-1", "2025-01", 1000.0)])
    hr = _agg([("LE-01", "CC-1", "2025-01", "DKK", 1000.0, 900.0, 1200.0, "CC-1", False)])
    for col in ("emp_key", "base_salary", "employee_salary"):
        with pytest.raises(FrameError, match="individual columns"):
            fin.tie_out(led, hr.assign(**{col: "x"}), context=M3)
    for kw in (dict(tolerance=-1), dict(tolerance=True), dict(band_floor_factor=0), dict(band_ceiling_factor=np.nan)):
        with pytest.raises(FrameError):
            fin.tie_out(led, hr, context=M3, **kw)
    with pytest.raises(FrameError, match="more than one row"):
        fin.tie_out(pd.concat([led, led]), hr, context=M3)
    with pytest.raises(FrameError, match="more than one row"):
        fin.tie_out(led, pd.concat([hr, hr]), context=M3)
    with pytest.raises(FrameError, match="two groups"):
        fin.tie_out(led, pd.concat([hr, hr.assign(cc_key="POOLED", currency="EUR", cost_centres="CC-1")]), context=M3)
    with pytest.raises(FrameError, match="lacks column"):
        fin.tie_out(led, hr.drop(columns="cost_centres"), context=M3)


def test_employer_oncosts_use_the_country_facts_on_gross_plus_overtime_and_carry_the_status():
    g = pd.DataFrame({"le_key": ["LE-01", "LE-02"], "cc_key": ["CC-1", "CC-9"], "period": "2025-01", "gross_salary": [1000.0, 2000.0], "overtime": [100.0, np.nan]})
    r = fin.employer_oncosts(g, country_of={"LE-01": "DK", "LE-02": "DE"}, context=M3)
    v = r.value.set_index("le_key")
    assert r.status == "VERIFY" and v.loc["LE-01", "base_amount"] == 1100.0 and v.loc["LE-01", "employer_pension"] == 88.0 and v.loc["LE-01", "employer_social"] == 13.2
    assert v.loc["LE-02", "employer_pension"] == 0.0 and v.loc["LE-02", "employer_social"] == 410.0, "DE: no pension share, social 20.5 percent; a null overtime counts as zero"
    assert fin.employer_oncosts(g, country_of={"LE-01": "DK", "LE-02": "DE"}, base="gross", context=M3).value.set_index("le_key").loc["LE-01", "employer_pension"] == 80.0
    for kw, msg in ((dict(country_of={"LE-01": "DK"}), "country_of"), (dict(country_of={"LE-01": "DK", "LE-02": "SE"}), "country_of"), (dict(country_of={"LE-01": "DK", "LE-02": "DE"}, base="x"), "base")):
        with pytest.raises(FrameError, match=msg):
            fin.employer_oncosts(g, context=M3, **kw)


def test_labour_absorption_check_per_entity_month_and_over_the_window():
    rows = [("LE-01", "2025-01", "GL-6100", 100.0), ("LE-01", "2025-01", "GL-7900", -100.0), ("LE-01", "2025-02", "GL-6100", 50.0), ("LE-01", "2025-02", "GL-7900", -49.0),
            ("LE-01", "2025-01", "GL-6610", 80.0), ("LE-02", "2025-01", "GL-6620", 10.0), ("LE-01", "2025-01", "GL-7910", -100.0)]
    jl = pd.DataFrame(rows, columns=["le_key", "period", "gl_key", "amount"])
    r = fin.labour_absorption_check(jl, context=M3)
    assert r.rule.tolist() == ["project_labour_not_absorbed"] and r.key.tolist() == ["LE-01 2025-02"], "service: 90 of 100 absorbed, the 10 rest is 10 percent, inside 20"
    r2 = fin.labour_absorption_check(jl, max_warranty_share=0.05, context=M3)
    assert set(r2.rule) == {"project_labour_not_absorbed", "service_labour_not_absorbed"}
    r3 = fin.labour_absorption_check(jl.assign(amount=jl.amount.where(jl.gl_key != "GL-7910", -50.0)), context=M3)
    assert "service_labour_not_absorbed" in set(r3.rule), "service labour above what is absorbed"
    assert "project_labour_not_absorbed" not in set(fin.labour_absorption_check(jl, tolerance=1.5, context=M3).rule), "a difference of 1.00 is inside a tolerance of 1.5"
    with pytest.raises(FrameError, match="max_warranty_share"):
        fin.labour_absorption_check(jl, max_warranty_share=1.0, context=M3)


def test_cost_centre_team_map_checks_both_directions():
    cc = pd.DataFrame({"cc_key": ["CC-1", "CC-2", "CC-3", "CC-4"], "team_key": ["T1", "T2", None, "T9"]})
    tm = pd.DataFrame({"team_key": ["T1", "T2", "T5"], "cost_centre_key": ["CC-1", "CC-7", "CC-8"]})
    r = fin.cost_centre_team_map(cc, tm, context=M12).set_index(["table", "key"]).rule
    assert r.loc[("finance.cost_centre", "CC-4")] == "cost_centre_without_team" and r.loc[("finance.cost_centre", "CC-2")] == "cost_centre_team_mismatch"
    assert r.loc[("hr.team", "T5")] == "team_without_cost_centre" and ("hr.team", "T2") in r.index and ("finance.cost_centre", "CC-3") not in r.index and ("finance.cost_centre", "CC-1") not in r.index
    ok = fin.cost_centre_team_map(cc.iloc[:1], tm.iloc[:1], context=M12)
    assert ok.empty
    with pytest.raises(FrameError, match="one row per key"):
        fin.cost_centre_team_map(pd.concat([cc, cc]), tm, context=M12)


def test_stage_registry_and_facade_for_payroll():
    reg = registry.registered()
    ids = {"ledger_gross_pay", "tie_out", "employer_oncosts", "labour_absorption_check", "cost_centre_team_map"}
    for n in ids:
        assert f"halvaro.finance.payroll.{n}" in reg and n in fin.__all__
    with pytest.raises(StageRefusal):
        fin.ledger_gross_pay(pd.DataFrame(), context=D1)
    assert not [m for k, m in reg.items() if k.startswith("halvaro.finance.payroll.") and any("base_salary" in s for s in m.sources)], "no function reads the restricted pay column"


def test_labour_absorption_refuses_a_service_window_that_mixes_currencies():
    jl = pd.DataFrame({"le_key": ["LE-01", "LE-02"], "gl_key": ["GL-6610", "GL-7910"], "period": ["2025-01", "2025-01"], "amount": [100.0, -100.0], "currency": ["DKK", "EUR"]})
    with pytest.raises(FrameError, match="more than one currency"):
        fin.labour_absorption_check(jl, context=M3)
    ok = fin.labour_absorption_check(jl.assign(amount_dkk=[100.0, -100.0]), context=M3)
    assert ok.empty


def test_tie_out_individual_columns_nulls_and_spaces_in_cost_centres():
    led = _led([("LE-01", "CC-3", "2025-01", 300.0), ("LE-01", "CC-4", "2025-01", 200.0)])
    ok = _agg([("LE-01", "POOLED", "2025-01", "DKK", 500.0, 450.0, 600.0, "CC-3, CC-4", False)])
    assert fin.tie_out(led, ok, context=M3).value.status.tolist() == ["tied"], "a space after the comma is no other cost centre"
    for col in ("EMP_KEY", "employee_id", "person_key", "monthly_pay", "Base_Salary"):
        with pytest.raises(FrameError, match="individual"):
            fin.tie_out(led, ok.assign(**{col: "x"}), context=M3)
    with pytest.raises(FrameError, match="individual"):
        fin.tie_out(led.assign(emp_key="P1"), ok, context=M3)
    with pytest.raises(FrameError, match="individual"):
        fin.tie_out(led, ok.set_index(pd.Index(["P1"], name="emp_key")), context=M3)
    with pytest.raises(FrameError, match="suppressed must be true or false"):
        fin.tie_out(led, ok.assign(suppressed=[None]), context=M3)
    with pytest.raises(FrameError, match="suppressed must be true or false"):
        fin.tie_out(led, ok.assign(suppressed=[np.nan]), context=M3)
    with pytest.raises(FrameError, match="cost_centres is null"):
        fin.tie_out(led, ok.assign(cost_centres=[None]), context=M3)
    with pytest.raises(FrameError, match="null pay or band"):
        fin.tie_out(led, ok.assign(hr_gross_pay=[np.nan]), context=M3)
    assert fin.tie_out(led, ok.assign(suppressed=[True], hr_gross_pay=[np.nan]), context=M3).value.status.tolist() == ["suppressed"], "a suppressed row may have no pay"
    bounds = fin.tie_out(led, ok.assign(hr_gross_pay=[499.95]), context=M3).value.status.tolist()
    assert bounds == ["tied"], "a difference of exactly the tolerance (0.05) is tied"
    assert fin.tie_out(led, ok.assign(hr_gross_pay=[499.94]), context=M3).value.status.tolist() == ["difference"]


def test_oncosts_and_absorption_null_and_duplicate_guards_and_tolerance_in_whole_cents():
    g = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2025-01"], "gross_salary": [1000.0]})
    with pytest.raises(FrameError, match="nulls"):
        fin.employer_oncosts(g.assign(gross_salary=[np.nan]), country_of={"LE-01": "DK"}, context=M3)
    with pytest.raises(FrameError, match="more than one row"):
        fin.employer_oncosts(pd.concat([g, g]), country_of={"LE-01": "DK"}, context=M3)
    jl = _jl([("LE-01", "CC-1", "GL-6100", "2025-01", 100.02), ("LE-01", "CC-1", "GL-7900", "2025-01", -100.0)])
    assert not fin.labour_absorption_check(jl, tolerance=0.015, context=M3).empty, "0.015 allows one cent, not two (no round half to even)"
    assert fin.labour_absorption_check(jl, tolerance=0.02, context=M3).empty
    for kw in (dict(tolerance=float("nan")), dict(tolerance=-1), dict(service_accounts="GL-6610")):
        with pytest.raises(FrameError):
            fin.labour_absorption_check(jl, context=M3, **kw)
    with pytest.raises(FrameError, match="le_key"):
        fin.labour_absorption_check(jl.assign(le_key=[None, "LE-01"]), context=M3)
