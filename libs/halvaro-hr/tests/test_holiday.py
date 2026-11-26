"""Holiday module: synthetic frames for the contract (the baseline tests are in the closed repository)."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, fact

D = dt.date


def _ent(rows):
    return pd.DataFrame(rows, columns=["emp_key", "holiday_year", "entitlement_days", "carried_in_days", "carry_over_agreement", "opening_balance"])


def _acc(rows):
    return pd.DataFrame(rows, columns=["emp_key", "holiday_year", "period", "accrued_days", "taken_days"])


def test_holiday_year_label_and_bounds_follow_the_legal_facts():
    assert hr.holiday_year_label("DK", D(2026, 8, 31)) == "2025/26" and hr.holiday_year_label("DK", D(2026, 9, 1)) == "2026/27"
    assert hr.holiday_year_label("DE", D(2026, 12, 31)) == "2026" and hr.holiday_year_label("DE", D(2026, 1, 1)) == "2026"
    assert hr.holiday_year_label("DK", D(2099, 12, 31)) == "2099/00"
    assert hr.holiday_year_bounds("2026/27") == (D(2026, 9, 1), D(2027, 8, 31)) and hr.holiday_year_bounds("2024") == (D(2024, 1, 1), D(2024, 12, 31))
    with pytest.raises(FrameError):
        hr.holiday_year_label("SE", D(2026, 1, 1))


def test_holiday_balance_reads_the_month_end_and_returns_a_zero_record_without_entitlement():
    ent = _ent([("EMP-1", "2026/27", 25.0, 4.0, True, False)])
    acc = _acc([("EMP-1", "2026/27", "2026-09", 2.08, 1.0), ("EMP-1", "2026/27", "2026-10", 2.08, 3.0), ("EMP-1", "2026/27", "2026-11", 2.08, 0.0)])
    b = hr.holiday_balance(ent, acc, "EMP-1", "2026/27", D(2026, 10, 15))
    assert (b.accrued_days_ytd, b.taken_days_ytd, b.carried_in_days, b.balance_days) == (4.16, 4.0, 4.0, 4.16), "mid month reads the whole month"
    assert b.as_of == "2026-10-15" and b.carry_over_agreement is True and b.has_entitlement_row and b.legal_status == "VERIFY"
    assert hr.holiday_balance(ent, acc, "EMP-1", "2026/27", D(2026, 8, 31)).balance_days == 4.0, "before the first period only the carry-in"
    z = hr.holiday_balance(ent, acc, "NOBODY", "2026/27", D(2026, 11, 30))
    assert z.balance_days == 0.0 and z.entitlement_days == 0.0 and not z.has_entitlement_row
    with pytest.raises(FrameError, match="2 entitlement rows"):
        hr.holiday_balance(pd.concat([ent, ent]), acc, "EMP-1", "2026/27", D(2026, 11, 30))
    with pytest.raises(FrameError, match="hr.holiday_accrual"):
        hr.holiday_balance(ent, acc.drop(columns="taken_days"), "EMP-1", "2026/27", D(2026, 11, 30))


def test_holiday_ledger_running_balance_and_flags():
    ent = _ent([("EMP-1", "2026/27", 25.0, 1.0, False, False), ("EMP-2", "2026/27", 25.0, 0.0, False, True)])
    acc = _acc([("EMP-1", "2026/27", "2026-10", 2.08, 4.0), ("EMP-1", "2026/27", "2026-09", 2.08, 0.0), ("EMP-2", "2026/27", "2026-09", 2.08, 0.0), ("EMP-3", "2026/27", "2026-09", 2.08, 0.0)])
    led = hr.holiday_ledger(ent, acc).to_frame().set_index(["emp_key", "period"])
    assert led.loc[("EMP-1", "2026-09"), "balance"] == 3.08 and led.loc[("EMP-1", "2026-10"), "balance"] == 1.16, "sorted by period, running"
    assert bool(led.loc[("EMP-1", "2026-10"), "negative"]) is False and bool(led.loc[("EMP-2", "2026-09"), "opening_balance"])
    assert bool(led.loc[("EMP-3", "2026-09"), "missing_entitlement"]) and led.missing_entitlement.sum() == 1
    neg = hr.holiday_ledger(ent, _acc([("EMP-1", "2026/27", "2026-09", 0.0, 5.0)])).to_frame()
    assert bool(neg.negative.iloc[0]) and neg.balance.iloc[0] == -4.0


def test_carry_over_position_basis_cap_headroom_deadline_and_status():
    ent = _ent([("A", "2026/27", 25.0, 3.0, False, False), ("B", "2026/27", 25.0, 10.0, True, False), ("C", "2026/27", 25.0, 6.0, False, False),
                ("D", "2026/27", 25.0, 9.9, False, True), ("G", "2026", 30.0, 12.0, False, False)])
    p = hr.carry_over_position(ent).to_frame().set_index("emp_key")
    assert p.loc["A", ["basis", "cap", "headroom"]].tolist() == ["default", fact("legal.DK.holiday.carryover.default_max_days").value, 2.0]
    assert p.loc["B", ["basis", "cap", "headroom"]].tolist() == ["agreement", fact("legal.DK.holiday.carryover.agreement_max_days").value, 0.0] and bool(p.loc["B", "at_cap"])
    assert p.loc["C", "headroom"] == -1.0, "above the cap of its basis shows as negative headroom"
    assert pd.isna(p.loc["D", "cap"]) and not bool(p.loc["D", "at_cap"]), "an opening row has no cap"
    assert p.loc["G", ["basis", "cap", "country"]].tolist() == ["default", 30.0, "DE"] and p.loc["G", "deadline"] == D(2026, 3, 31) and p.loc["A", "deadline"] is None
    assert set(p.legal_status) == {"VERIFY"}


def test_accrual_expected_part_months_unpaid_leave_and_tolerance():
    emp = pd.DataFrame({"emp_key": ["H", "L", "X", "S"], "hire_date": [D(2026, 9, 16), D(2020, 1, 1), D(2020, 1, 1), D(2020, 1, 1)],
                        "leave_date": [None, D(2026, 10, 15), None, None]})
    lv = pd.DataFrame({"emp_key": ["X", "S"], "leave_type": ["extended_leave", "sick"], "start": [D(2026, 10, 1), D(2026, 10, 1)], "end": [D(2026, 10, 10), D(2026, 10, 10)]})
    acc = _acc([("H", "2026/27", "2026-09", 1.04, 0.0), ("L", "2026/27", "2026-10", 1.01, 0.0), ("X", "2026/27", "2026-10", 1.41, 0.0),
                ("S", "2026/27", "2026-10", 2.08, 0.0), ("H", "2026/27", "2026-10", 2.0, 0.0)])
    out = hr.accrual_expected(emp, lv, acc, D(2026, 11, 30)).to_frame().set_index(["emp_key", "period"])
    assert out.loc[("H", "2026-09"), "expected_days"] == 1.04 and out.loc[("L", "2026-10"), "expected_days"] == 1.01, "15 of 30 and 15 of 31 days"
    assert out.loc[("X", "2026-10"), "expected_days"] == 1.41 and out.loc[("S", "2026-10"), "expected_days"] == 2.08, "unpaid leave deducts, sick leave accrues"
    bad = out.loc[("H", "2026-10")]
    assert bad.expected_days == 2.08 and not bool(bad.within_tolerance) and bad.difference == -0.08
    assert out.within_tolerance.sum() == 4 and set(out.legal_status) == {"VERIFY"}
    capped = hr.accrual_expected(emp, lv, _acc([("H", "2026/27", "2026-11", 0.0, 0.0)]), D(2026, 11, 15)).to_frame().set_index("period").loc["2026-11"]
    assert capped.expected_days == 1.04, "the month stops at now: 15 of 30 days"
    wide = hr.accrual_expected(emp, lv, acc, D(2026, 11, 30), tolerance=0.1).to_frame().set_index(["emp_key", "period"])
    assert bool(wide.loc[("H", "2026-10"), "within_tolerance"])


def test_leave_vs_ledger_per_person_year_and_total():
    acc = _acc([("EMP-1", "2026/27", "2026-09", 2.08, 3.0), ("EMP-1", "2026/27", "2026-10", 2.08, 2.0), ("EMP-2", "2026", "2026-03", 2.5, 4.0)])
    lv = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-2", "EMP-2", "EMP-1"], "leave_type": ["holiday", "holiday", "holiday", "sick", "holiday"],
                       "days": [3, 3, 4, 9, 7], "end": [D(2026, 9, 5), D(2026, 10, 9), D(2026, 3, 10), D(2026, 3, 11), D(2026, 12, 20)]})
    out = hr.leave_vs_ledger(lv, acc, D(2026, 11, 30)).to_frame().set_index(["emp_key", "holiday_year"])
    assert out.loc[("EMP-1", "2026/27"), ["leave_days", "taken_days", "difference"]].tolist() == [6, 5.0, -1.0], "the record ending after now and the sick record are left out"
    assert out.loc[("EMP-2", "2026"), "difference"] == 0.0 and out.total_difference_days.iloc[0] == -1.0 and bool(out.within_total_tolerance.all())
    assert not hr.leave_vs_ledger(lv, acc, D(2026, 11, 30), total_tolerance_days=0.5).to_frame().within_total_tolerance.any()


def test_high_carry_over_is_strictly_greater_and_leaves_opening_rows_out():
    ent = _ent([("A", "2026/27", 25.0, 10.0, True, False), ("B", "2026/27", 25.0, 8.0, True, False), ("C", "2026/27", 25.0, 8.1, True, False),
                ("D", "2026/27", 25.0, 15.0, False, True), ("E", "2025/26", 25.0, 10.0, True, False), ("G", "2026", 30.0, 20.0, False, False)])
    assert hr.high_carry_over(ent).to_frame().emp_key.tolist() == ["A", "C"], "8.0 is not above 8.0; opening and other years are left out"
    assert hr.high_carry_over(ent, threshold=7.0).to_frame().emp_key.tolist() == ["A", "B", "C"]
    assert hr.high_carry_over(ent, "2026", "DE", 12.0).to_frame().emp_key.tolist() == ["G"]
    with pytest.raises(FrameError, match="not a DE label"):
        hr.high_carry_over(ent, "2026/27", "DE")


# ---- review round: stronger tests --------------------------------------------------------------------------------------------------------------------
def test_ledger_balance_column_over_several_people_and_years():
    ent = _ent([("EMP-1", "2025/26", 25.0, 2.0, False, False), ("EMP-1", "2026/27", 25.0, 1.5, False, False), ("EMP-2", "2026/27", 25.0, 4.0, False, False)])
    acc = _acc([("EMP-2", "2026/27", "2026-10", 2.08, 1.0), ("EMP-1", "2026/27", "2026-09", 2.08, 0.0), ("EMP-1", "2025/26", "2026-08", 2.08, 1.0), ("EMP-1", "2025/26", "2026-07", 2.08, 0.0),
                ("EMP-2", "2026/27", "2026-09", 2.08, 0.0), ("EMP-1", "2026/27", "2026-10", 2.08, 0.5)])
    led = hr.holiday_ledger(ent, acc).to_frame()
    got = {(r.emp_key, r.holiday_year, r.period): r.balance for r in led.itertuples()}
    assert got == {("EMP-1", "2025/26", "2026-07"): 4.08, ("EMP-1", "2025/26", "2026-08"): 5.16, ("EMP-1", "2026/27", "2026-09"): 3.58, ("EMP-1", "2026/27", "2026-10"): 5.16,
                   ("EMP-2", "2026/27", "2026-09"): 6.08, ("EMP-2", "2026/27", "2026-10"): 7.16}, "every person-year restarts at its own carry-in"
    assert set(led.legal_status) == {"VERIFY"}


def test_ledger_negative_flag_boundary_and_duplicate_entitlements():
    ent = _ent([("EMP-1", "2026/27", 25.0, 0.0, False, False), ("EMP-2", "2026/27", 25.0, 0.0, False, False), ("EMP-3", "2026/27", 25.0, 0.0, False, False)])
    acc = _acc([("EMP-1", "2026/27", "2026-09", 0.0, 0.0), ("EMP-2", "2026/27", "2026-09", 0.0, 0.5), ("EMP-3", "2026/27", "2026-09", 1.0, 0.0)])
    led = hr.holiday_ledger(ent, acc).to_frame().set_index("emp_key")
    assert led.negative.to_dict() == {"EMP-1": False, "EMP-2": True, "EMP-3": False}, "exactly zero is not negative, minus 0.5 is"
    with pytest.raises(FrameError, match="several rows"):
        hr.holiday_ledger(pd.concat([ent, ent.iloc[[0]]]), acc)


def test_holiday_balance_entitlement_de_person_and_inconsistent_frames(recwarn):
    ent = _ent([("G1", "2026", 30.0, 2.5, False, False), ("EMP-1", "2026/27", 25.0, 4.0, False, False)])
    acc = _acc([("G1", "2026", "2026-01", 2.5, 1.0), ("G1", "2026", "2026-02", 2.5, 0.0), ("EMP-1", "2026/27", "2026-09", 2.08, 0.0), ("EMP-3", "2026/27", "2026-09", 2.08, 0.0)])
    g = hr.holiday_balance(ent, acc, "G1", "2026", D(2026, 2, 28))
    assert (g.entitlement_days, g.carried_in_days, g.accrued_days_ytd, g.taken_days_ytd, g.balance_days) == (30.0, 2.5, 5.0, 1.0, 6.5)
    assert hr.holiday_balance(ent, acc, "EMP-1", "2026/27", D(2026, 9, 30)).entitlement_days == 25.0
    with pytest.raises(FrameError, match="no entitlement row"):
        hr.holiday_balance(ent, acc, "EMP-3", "2026/27", D(2026, 9, 30))
    with pytest.warns(UserWarning, match="frozen"):
        late = hr.holiday_balance(ent, acc, "EMP-1", "2026/27", D(2026, 12, 31))
    assert late.balance_days == 6.08, "past the last ledger period the sums stay as they are"
    with pytest.raises(FrameError, match="matches no label format"):
        hr.holiday_balance(ent, acc, "EMP-1", "2026-27", D(2026, 9, 30))


def test_carry_over_position_at_cap_is_exact_and_the_caps_come_from_the_facts(monkeypatch):
    import dataclasses

    import halvaro.hr.holiday as hol
    ent = _ent([("A", "2026/27", 25.0, 5.0, False, False), ("B", "2026/27", 25.0, 6.0, False, False), ("C", "2026/27", 25.0, 10.0, True, False), ("G", "2026", 30.0, 30.0, False, False)])
    p = hr.carry_over_position(ent).to_frame().set_index("emp_key")
    assert p.at_cap.to_dict() == {"A": True, "B": False, "C": True, "G": True} and p.loc["B", "headroom"] == -1.0
    real = hol.fact
    monkeypatch.setattr(hol, "fact", lambda i: dataclasses.replace(real(i), value={"legal.DK.holiday.carryover.default_max_days": 7, "legal.DK.holiday.carryover.agreement_max_days": 12}.get(i, real(i).value)))
    q = hr.carry_over_position(ent).to_frame().set_index("emp_key")
    assert q.loc["A", ["cap", "headroom"]].tolist() == [7.0, 2.0] and q.loc["C", "cap"] == 12.0 and q.loc["G", "cap"] == 30.0


def test_accrual_expected_de_rate_month_crossing_leave_and_exact_tolerance():
    emp = pd.DataFrame({"emp_key": ["G", "U", "P"], "hire_date": [D(2020, 1, 1), D(2020, 1, 1), D(2026, 10, 10)], "leave_date": [None, None, None]})
    lv = pd.DataFrame({"emp_key": ["U", "U", "P"], "leave_type": ["extended_leave", "extended_leave", "extended_leave"],
                       "start": [D(2026, 10, 25), D(2026, 11, 20), D(2026, 9, 1)], "end": [D(2026, 11, 4), D(2026, 11, 22), D(2026, 10, 12)]})
    acc = _acc([("G", "2026", "2026-03", 2.5, 0.0), ("U", "2026/27", "2026-10", 1.61, 0.0), ("U", "2026/27", "2026-11", 1.59, 0.0), ("P", "2026/27", "2026-10", 1.27, 0.0)])
    out = hr.accrual_expected(emp, lv, acc, D(2026, 11, 30)).to_frame().set_index(["emp_key", "period"])
    assert out.loc[("G", "2026-03"), "expected_days"] == 2.5, "the DE rate, not the DK rate"
    assert out.loc[("U", "2026-10"), "expected_days"] == 1.61 and out.loc[("U", "2026-11"), "expected_days"] == 1.59, "24 of 31 days; unpaid 25 Oct to 4 Nov crosses the month and a second span (20 to 22 Nov) counts too: 23 of 30"
    assert out.loc[("P", "2026-10"), "expected_days"] == 1.27, "19 of 31 days: unpaid leave from 1 Sep is clipped to the employed window (10 to 12 Oct)"
    near = hr.accrual_expected(emp, lv, _acc([("G", "2026", "2026-03", 2.51, 0.0)]), D(2026, 11, 30)).to_frame()
    row = near.set_index("period").loc["2026-03"]
    assert bool(row.within_tolerance) and row.difference == 0.01, "a difference of exactly the tolerance is within it"
    with pytest.raises(FrameError, match="not in hr.employee"):
        hr.accrual_expected(emp.iloc[:1], lv, acc, D(2026, 11, 30))


def test_accrual_expected_reports_a_missing_month():
    emp = pd.DataFrame({"emp_key": ["H"], "hire_date": [D(2025, 3, 10)], "leave_date": [None]})
    lv = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
    acc = _acc([("H", "2024/25", p, 2.08, 0.0) for p in ("2025-03", "2025-05", "2025-06", "2025-07", "2025-08")])
    out = hr.accrual_expected(emp, lv, acc, D(2026, 11, 30)).to_frame()
    miss = out[out.missing_month]
    assert miss.period.tolist() == ["2025-04"] and miss.accrued_days.isna().all() and not miss.within_tolerance.any() and miss.expected_days.iloc[0] == 2.08
    assert out[~out.missing_month].period.tolist() == ["2025-03", "2025-05", "2025-06", "2025-07", "2025-08"]


def test_leave_vs_ledger_year_boundary_leave_only_taken_only_and_positive_total():
    acc = _acc([("EMP-1", "2025/26", "2026-08", 2.08, 2.0), ("EMP-1", "2026/27", "2026-09", 2.08, 1.0), ("EMP-2", "2026/27", "2026-09", 2.08, 6.0)])
    lv = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1", "EMP-3"], "leave_type": ["holiday"] * 3, "days": [2, 1, 4], "end": [D(2026, 8, 31), D(2026, 9, 1), D(2026, 9, 2)]})
    out = hr.leave_vs_ledger(lv, acc, D(2026, 11, 30), total_tolerance_days=3.0).to_frame().set_index(["emp_key", "holiday_year"])
    assert out.loc[("EMP-1", "2025/26"), "leave_days"] == 2 and out.loc[("EMP-1", "2026/27"), "leave_days"] == 1, "31 August closes the old year, 1 September opens the next"
    assert out.loc[("EMP-2", "2026/27"), ["leave_days", "taken_days", "difference"]].tolist() == [0.0, 6.0, 6.0], "taken without a record"
    assert out.reset_index().holiday_year.isna().sum() == 1, "a record of a person without ledger rows has no holiday year"
    assert out.total_difference_days.iloc[0] == 2.0 and bool(out.within_total_tolerance.all()) and set(out.legal_status) == {"VERIFY"}
    assert not hr.leave_vs_ledger(lv, acc, D(2026, 11, 30), total_tolerance_days=1.0).to_frame().within_total_tolerance.any(), "a positive total beyond the tolerance fails too"


def test_high_carry_over_sorted_status_and_unknown_label():
    ent = _ent([("C", "2026/27", 25.0, 9.0, True, False), ("A", "2026/27", 25.0, 10.0, True, False), ("B", "2026/27", 25.0, 8.5, True, False)])
    out = hr.high_carry_over(ent).to_frame()
    assert out.emp_key.tolist() == ["A", "B", "C"] and set(out.legal_status) == {"VERIFY"}
    with pytest.raises(FrameError, match="matches no label format"):
        hr.high_carry_over(ent, "abc")


def test_high_carry_over_default_is_the_policy_fact_and_carries_its_status():
    from halvaro.core import fact
    ent = _ent([("A", "2026/27", 25.0, 10.0, True, False), ("B", "2026/27", 25.0, 8.0, True, False), ("C", "2026/27", 25.0, 8.1, True, False)])
    f = fact("policy.holiday.high_carry_over_days")
    assert f.value == 8 and f.status in ("proposed", "verified"), "owner decision 2026-10-31: 8, proposed (verified when lane F2 accepted it)"      # lane F3 (issue #543), approved edit
    out = hr.high_carry_over(ent).to_frame()
    assert out.emp_key.tolist() == ["A", "C"] and out.attrs["policy_status"] == {"policy.holiday.high_carry_over_days": fact("policy.holiday.high_carry_over_days").status}      # lane F3 (issue #543), approved edit: the status of the fact, whichever it is
    assert "policy_status" not in hr.high_carry_over(ent, threshold=7.0).to_frame().attrs and hr.high_carry_over(ent, threshold=7.0).to_frame().emp_key.tolist() == ["A", "B", "C"], "a caller's number is used as it is"


def _led(rows):
    return pd.DataFrame(rows, columns=["emp_key", "holiday_year", "period", "balance"])


def test_carry_over_projection_caps_flag_of_the_closing_year_and_the_next_year_check():
    dk, agr, de = (fact("legal.DK.holiday.carryover.default_max_days").value, fact("legal.DK.holiday.carryover.agreement_max_days").value, fact("legal.DE.holiday.carryover.default_max_days").value)
    ent = _ent([("A", "2025/26", 25.0, 0.0, False, False), ("A", "2026/27", 25.0, dk, False, False), ("B", "2025/26", 25.0, 0.0, True, False), ("B", "2026/27", 25.0, agr - 1.0, True, False),
                ("C", "2025/26", 25.0, 0.0, False, False), ("C", "2026/27", 25.0, 0.0, False, False), ("D", "2025/26", 25.0, 0.0, False, False), ("E", "2026", 30.0, 0.0, False, False),
                ("E", "2027", 30.0, 3.0, False, False)])
    led = _led([("A", "2025/26", "2026-08", 99.0), ("A", "2025/26", "2026-07", 1.0), ("B", "2025/26", "2026-08", 50.0), ("C", "2025/26", "2026-08", -1.5), ("D", "2025/26", "2026-08", 2.0),
                ("E", "2026", "2026-12", 3.04)])
    p = hr.carry_over_projection(led, ent).to_frame().set_index("emp_key")
    assert p.loc["A", "next_holiday_year"] == "2026/27" and p.loc["A", "year_end_balance"] == 99.0, "the balance of the last period counts, however the rows are ordered"
    assert (p.loc["A", "basis"], p.loc["A", "cap"], p.loc["A", "projected_carry_in"]) == ("default", dk, dk) and bool(p.loc["A", "matches"])
    assert (p.loc["B", "basis"], p.loc["B", "cap"], p.loc["B", "projected_carry_in"]) == ("agreement", agr, agr) and p.loc["B", "difference"] == 1.0 and not bool(p.loc["B", "matches"]), "the stored carry-in is 1 day below the cap"
    assert p.loc["C", "projected_carry_in"] == 0.0 and bool(p.loc["C", "matches"]), "a negative balance carries nothing"
    assert p.loc["D", "projected_carry_in"] == 2.0 and pd.isna(p.loc["D", "stored_carry_in"]) and pd.isna(p.loc["D", "matches"]), "no next year row: nothing to compare"
    assert p.loc["E", "next_holiday_year"] == "2027" and p.loc["E", "country"] == "DE" and p.loc["E", "cap"] == de and p.loc["E", "projected_carry_in"] == 3.04 and bool(p.loc["E", "matches"]), "DE: within the 0.05 day rounding of the stored value"
    assert not bool(hr.carry_over_projection(led, ent, tolerance=0.0).to_frame().set_index("emp_key").loc["E", "matches"]), "the tolerance is a keyword: 0.04 days apart is a difference at 0"
    assert p.legal_status.iloc[0] in ("ok", "VERIFY", "VERIFY+synthetic")
    noflag = hr.carry_over_projection(led, ent[ent.emp_key != "B"]).to_frame().set_index("emp_key")
    assert noflag.loc["B", "basis"] == "default", "a closing year without an entitlement row has the default cap"


def test_carry_over_projection_refusals():
    ent = _ent([("A", "2025/26", 25.0, 0.0, False, False)])
    led = _led([("A", "2025/26", "2026-08", 1.0)])
    with pytest.raises(FrameError, match="several rows"):
        hr.carry_over_projection(led, pd.concat([ent, ent]))
    with pytest.raises(FrameError, match="lacks column"):
        hr.carry_over_projection(led.drop(columns="balance"), ent)
    with pytest.raises(FrameError, match="tolerance"):
        hr.carry_over_projection(led, ent, tolerance=-1)
    with pytest.raises(FrameError, match="label"):
        hr.carry_over_projection(_led([("A", "FY26", "2026-08", 1.0)]), ent)
    assert hr.carry_over_projection(led.iloc[:0], ent).to_frame().empty
