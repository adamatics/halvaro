"""Payroll aggregate (plan 5.5 request from halvaro-finance): hand computed terms, the access guard and small groups, then the baseline release against the restricted source and finance.payroll_hr_reconciliation."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import Context, FrameError, RestrictedColumnRefusal, registry

D = dt.date
HR = Context.from_profile("mcp_people_hr", stage="day1")
OPEN = Context.from_profile("mcp_business", stage="day1")


def _team():
    return pd.DataFrame({"team_key": ["T1", "T2", "T3", "T4"], "cost_centre_key": ["CC-1", "CC-1", "CC-2", "CC-3"], "legal_entity_key": ["LE-01", "LE-01", "LE-01", "LE-02"]})


def _grade():
    return pd.DataFrame({"gra_key": ["G1", "G2"], "band_min_dkk": [30000.0, 40000.0], "band_max_dkk": [40000.0, 50000.0], "band_min_eur": [4000.0, 5000.0], "band_max_eur": [5000.0, 6000.0]})


def _terms(n_cc1=9, n_cc2=3, n_cc3=8):
    rows = []
    for i in range(n_cc1):
        rows.append((f"EMP-1{i}", D(2025, 1, 1), None, "T1" if i % 2 else "T2", "G1", 1.0, "DKK", 30000.0 + i))
    for i in range(n_cc2):
        rows.append((f"EMP-2{i}", D(2025, 1, 1), None, "T3", "G2", 0.5, "DKK", 40000.0))
    for i in range(n_cc3):
        rows.append((f"EMP-3{i}", D(2025, 1, 1), None, "T4", "G1", 1.0, "EUR", 4000.0))
    # a person who changes grade in the middle of February 2025 (days 1 to 14 and 15 to 28)
    rows[0] = ("EMP-10", D(2025, 1, 1), D(2025, 2, 14), "T2", "G1", 1.0, "DKK", 30000.0)
    rows.append(("EMP-10", D(2025, 2, 15), None, "T2", "G2", 1.0, "DKK", 40000.0))
    return pd.DataFrame(rows, columns=["emp_key", "valid_from", "valid_to", "team_key", "grade_key", "fte", "currency", "base_salary"])


def test_pay_per_cost_centre_and_month_with_days_in_force_and_weighted_fte():
    out = hr.payroll_aggregate(_terms(), _team(), _grade(), "2025-01", "2025-02", context=HR, on_small="suppress").set_index(["cc_key", "period"])
    jan, feb = out.loc[("CC-1", "2025-01")], out.loc[("CC-1", "2025-02")]
    base = sum(30000.0 + i for i in range(1, 9))
    assert jan.hr_gross_pay == pytest.approx(base + 30000.0) and jan.hr_headcount_month_end == 9 and jan.hr_fte == pytest.approx(9.0) and jan.n_people == 9 and not jan.suppressed
    assert jan.band_minimum_total == pytest.approx(9 * 30000.0) and jan.band_maximum_total == pytest.approx(9 * 40000.0)
    w1, w2 = 14 / 28, 14 / 28
    assert feb.hr_gross_pay == pytest.approx(base + 30000.0 * w1 + 40000.0 * w2), "the term that ends 14 February counts 14 days, the new one 14 days"
    assert feb.hr_headcount_month_end == 9 and feb.n_people == 9 and feb.hr_fte == pytest.approx(9.0), "month end headcount counts the new term only; FTE is weighted by days"
    assert feb.band_minimum_total == pytest.approx(8 * 30000.0 + 30000.0 * w1 + 40000.0 * w2)
    eur = out.loc[("CC-3", "2025-01")]
    assert eur.currency == "EUR" and eur.le_key == "LE-02" and eur.hr_gross_pay == pytest.approx(8 * 4000.0) and eur.band_minimum_total == pytest.approx(8 * 4000.0)
    part = out.loc[("CC-2", "2025-01")]
    assert bool(part.suppressed) and part.n_people == 3 and np.isnan(part.hr_gross_pay), "three people are under the minimum of 8"


def test_small_groups_are_pooled_suppressed_or_refused_and_the_result_has_no_individual_columns():
    kw = dict(context=HR)
    t, tm, g = _terms(n_cc3=5), _team(), _grade()
    pooled = hr.payroll_aggregate(t, tm, g, "2025-01", "2025-01", **kw)
    from halvaro.core import fact      # lane F3 (issue #543), approved edit: the status of the fact, whichever it is
    assert pooled.attrs["policy_status"] == {hr.payroll._MIN.fact_id: fact(hr.payroll._MIN.fact_id).status}
    row = pooled[pooled.cc_key == hr.payroll.POOLED].set_index("le_key")
    assert len(row) == 2 and row.loc["LE-01", "n_people"] == 3 and row.loc["LE-02", "n_people"] == 5 and row.suppressed.all(), "CC-2 (3 people) and CC-3 (5 people) are pooled per entity, each pool is still under 8 and suppressed"
    both = hr.payroll_aggregate(_terms(n_cc1=5), tm.assign(cost_centre_key=["CC-1", "CC-9", "CC-2", "CC-3"]), g, "2025-01", "2025-01", minimum_group=4, **kw)
    p = both[both.cc_key == hr.payroll.POOLED]
    assert len(p) == 1 and p.n_cost_centres.iloc[0] == 3 and not p.suppressed.iloc[0] and p.n_people.iloc[0] == 8 and p.cost_centres.iloc[0] == "CC-1,CC-2,CC-9", "three small cost centres of one entity (CC-1, CC-9, CC-2) add up to one row of 8 people"
    assert row.loc["LE-01", "cost_centres"] == "CC-2" and pooled[pooled.cc_key == "CC-1"].cost_centres.iloc[0] == "CC-1"
    s = hr.payroll_aggregate(t, tm, g, "2025-01", "2025-01", on_small="suppress", **kw)
    assert s[s.suppressed].cc_key.tolist() == ["CC-2", "CC-3"] and s[s.suppressed][list(["hr_gross_pay", "band_minimum_total"])].isna().all().all()
    with pytest.raises(FrameError, match="fewer than 8 people"):
        hr.payroll_aggregate(t, tm, g, "2025-01", "2025-01", on_small="refuse", **kw)
    for frame in (pooled, s):
        assert "base_salary" not in frame.columns and not any("emp" in c or "salary" in c for c in frame.columns), "no individual pay, no employee key"


def test_access_inputs_and_months_are_checked():
    t, tm, g = _terms(), _team(), _grade()
    with pytest.raises(Exception) as e:
        hr.payroll_aggregate(t, tm, g, "2025-01", "2025-01", context=OPEN)
    assert "base_salary" in str(e.value) or isinstance(e.value, RestrictedColumnRefusal)
    with pytest.raises(RestrictedColumnRefusal):
        hr.payroll_aggregate(t.drop(columns="base_salary"), tm, g, "2025-01", "2025-01", context=HR)
    for args, msg in ((("2025-1", "2025-02"), "period text"), (("2025-03", "2025-02"), "after"), (("2025-01", 202502), "period text")):
        with pytest.raises(FrameError, match=msg):
            hr.payroll_aggregate(t, tm, g, *args, context=HR)
    for kw, msg in ((dict(on_small="x"), "on_small"), (dict(minimum_group=0), "minimum_group"), (dict(minimum_group=True), "minimum_group")):
        with pytest.raises(FrameError, match=msg):
            hr.payroll_aggregate(t, tm, g, "2025-01", "2025-01", context=HR, **kw)
    with pytest.raises(FrameError, match="missing"):
        hr.payroll_aggregate(t.assign(base_salary=lambda d: d.base_salary.where(d.index != 0, np.nan)), tm, g, "2025-01", "2025-01", context=HR)
    with pytest.raises(FrameError, match="not in hr.team"):
        hr.payroll_aggregate(t, tm.iloc[1:], g, "2025-01", "2025-01", context=HR)
    with pytest.raises(FrameError, match="DKK or EUR"):
        hr.payroll_aggregate(t.assign(currency="SEK"), tm, g, "2025-01", "2025-01", context=HR)
    assert hr.payroll_aggregate(t[t.valid_from > D(2030, 1, 1)], tm, g, "2025-01", "2025-02", context=HR).empty


def test_registered_with_restricted_source_and_oracle():
    m = registry.registered()["halvaro.hr.payroll.payroll_aggregate"]
    assert "hr.employment_term.base_salary" in m.sources and "payroll_aggregate" in hr.__all__ and m.restricted == ("hr.employment_term.base_salary",)
