"""Property style tests of the finance modules that had none: project_view, planning, consolidation, payroll, cash, subledgers, exposure, reconcile, statements (standard 3.2.3, lane P2, issue #469).

Each test states a rule that must hold for many inputs drawn from a seeded generator (no extra package): a bound, a relation between two functions, an invariance under the order of the rows or under how the
rows are split, an identity of two columns, or that the inputs are left as they were. The rules are written from the documented behaviour, not from the function bodies. project_costs is covered by the cost per metre view (labour_cost_overrun is a function of lane P1 and is left to it).
"""
import datetime as dt
import random

import numpy as np
import pandas as pd

from halvaro.core import Context, fact
from halvaro.finance import (ageing, cash_forecast_checks, contract_position, cost_per_metre_by_cost_code, cost_to_completion, eliminations, fixed_asset_rollforward, group_trial_balance, intercompany_match, ledger_gross_pay,
                             loss_provision, open_items_ar, percent_complete, project_margin, revenue_recognised, size_class, supplier_spend, utilisation, write_down_journal)

CTX = Context(stage="month12", role="analyst")
CAP = 0.95
PERIOD_END = dt.date(2026, 3, 31)


def rng(seed: int) -> random.Random:
    return random.Random(20261119 + seed)


def untouched(before: dict, after: dict) -> None:
    for name, frame in before.items():
        assert frame.equals(after[name]), f"{name} was changed by the call"


def by_key(frame: pd.DataFrame, key: str = "prj_key") -> pd.DataFrame:
    return frame.sort_values(key).reset_index(drop=True)


# ---------------------------------------------------------------- project_view
def projects(r: random.Random, n: int = 12):
    rows, ends = [], {}
    for i in range(n):
        eac = round(r.uniform(500, 9000), 2)
        rows.append({"prj_key": f"PRJ-{i + 1:06d}", "period": "2026-03", "contract_value": round(r.uniform(500, 9000), 2), "eac": eac,
                     "actual_cost": round(r.uniform(0, eac * 1.1), 2), "billed": round(r.uniform(0, 9000), 2), "committed_cost": round(r.uniform(0, 500), 2), "currency": "DKK"})
        if r.random() < 0.3:
            ends[rows[-1]["prj_key"]] = (dt.date(2026, 3, 1) + dt.timedelta(days=r.randint(-90, 29))).isoformat()
    return pd.DataFrame(rows), ends


def test_percent_complete_is_from_0_to_100_100_when_ended_and_never_above_the_cap_when_running():
    r, seen = rng(1), {"ended": 0, "running": 0}
    for _ in range(40):
        pf, ends = projects(r)
        pct = percent_complete(pf, ends, cap=CAP, context=CTX)
        assert pct.between(0, 100).all() and list(pct.index) == list(pf.index)
        ended = pf["prj_key"].isin(ends)
        assert (pct[ended] == 100.0).all() and (pct[~ended] <= CAP * 100 + 1e-9).all()
        seen["ended"] += int(ended.sum()); seen["running"] += int((~ended).sum())
    assert seen["ended"] > 20 and seen["running"] > 100                          # both kinds of project were drawn


def test_percent_complete_is_monotone_in_the_actual_cost():
    r = rng(2)
    for _ in range(40):
        pf, ends = projects(r)
        more = pf.assign(actual_cost=pf["actual_cost"] + pd.Series([r.uniform(0, 500) for _ in range(len(pf))]))
        assert (percent_complete(more, ends, cap=CAP, context=CTX) >= percent_complete(pf, ends, cap=CAP, context=CTX) - 1e-9).all()


def test_the_project_view_functions_leave_their_inputs_alone_and_do_not_depend_on_the_order_of_the_rows():
    r = rng(3)
    for _ in range(20):
        pf, ends = projects(r)
        for fn in (percent_complete, revenue_recognised, loss_provision):
            before = {"pf": pf.copy()}
            first = fn(pf, ends, cap=CAP, context=CTX)
            untouched(before, {"pf": pf})
            order = list(range(len(pf)))
            r.shuffle(order)
            shuffled = pf.iloc[order]
            again = fn(shuffled, ends, cap=CAP, context=CTX)
            assert first.set_axis(pf["prj_key"]).sort_index().equals(again.set_axis(shuffled["prj_key"]).sort_index())


def test_revenue_is_at_most_the_contract_value_and_all_of_it_when_ended():
    r = rng(4)
    for _ in range(40):
        pf, ends = projects(r)
        rev = revenue_recognised(pf, ends, cap=CAP, context=CTX)
        assert (rev >= 0).all() and (rev <= pf["contract_value"] + 0.005).all()
        ended = pf["prj_key"].isin(ends)
        assert np.allclose(rev[ended], pf.loc[ended, "contract_value"], atol=0.005)


def test_the_loss_provision_is_never_negative_never_above_the_expected_loss_and_zero_when_ended_or_no_loss_is_expected():
    r = rng(5)
    for _ in range(40):
        pf, ends = projects(r)
        lp = loss_provision(pf, ends, cap=CAP, context=CTX)
        expected = (pf["eac"] - pf["contract_value"]).clip(lower=0)
        assert (lp >= 0).all() and (lp <= expected + 0.005).all()
        assert (lp[pf["prj_key"].isin(ends) | (expected == 0)] == 0).all()


def test_the_contract_asset_less_the_contract_liability_is_the_position_and_one_of_them_is_zero():
    r = rng(6)
    for _ in range(40):
        pf, ends = projects(r)
        cp = contract_position(pf, ends, cap=CAP, context=CTX)
        assert np.allclose(cp["wip"] - cp["contract_liability"], cp["contract_position"], atol=0.005)
        assert (cp[["wip", "contract_liability"]].min(axis=1) == 0).all() and (cp[["wip", "contract_liability"]] >= 0).all().all()
        assert np.allclose(cp["contract_position"], cp["revenue_recognised"] - cp["billed"], atol=0.005)


def test_the_forecast_margin_has_the_sign_of_contract_value_less_eac_and_a_project_without_revenue_has_no_margin_to_date():
    r = rng(7)
    for _ in range(40):
        pf, ends = projects(r)
        pf = pf.assign(revenue_recognised=revenue_recognised(pf, ends, cap=CAP, context=CTX), loss_provision=loss_provision(pf, ends, cap=CAP, context=CTX))
        pf.loc[pf.index[0], "revenue_recognised"] = 0.0
        m = project_margin(pf, context=CTX)
        gap = pf["contract_value"] - pf["eac"]
        clear = gap.abs() > 0.01 * pf["contract_value"]                           # a gap too small to survive the rounding to two decimals has no sign to compare
        assert clear.any() and (np.sign(m.loc[clear, "forecast_margin_pct"]) == np.sign(gap[clear])).all()
        assert np.isnan(m.loc[pf.index[0], "margin_pct"]) and list(m["prj_key"]) == list(pf["prj_key"])


def test_cost_to_completion_lists_the_projects_in_the_order_asked_and_the_uncommitted_is_what_is_left_after_the_commitments():
    r = rng(8)
    for _ in range(30):
        pf, _ = projects(r)
        keys = [f"PRJ-{i:06d}" for i in r.sample(range(1, 16), 9)]                 # some of them have no row
        before = {"pf": pf.copy()}
        out = cost_to_completion(pf, keys, "2026-03", context=CTX)
        untouched(before, {"pf": pf})
        assert list(out["prj_key"]) == keys
        have = out["reason"].isna()
        assert set(out.loc[~have, "reason"]) <= {"no finance row"} and set(out.loc[~have, "prj_key"]).isdisjoint(pf["prj_key"])
        assert np.allclose(out.loc[have, "cost_to_completion"] - out.loc[have, "committed_cost"], out.loc[have, "uncommitted"], atol=0.011)


def test_the_write_down_lines_are_those_of_the_project_and_the_account_in_the_order_of_posting():
    r = rng(9)
    for _ in range(30):
        n = 25
        manual = pd.DataFrame({"le_key": "LE-01", "journal_no": [f"J-{i:04d}" for i in r.sample(range(1, 999), n)],
                               "posting_date": [(dt.date(2026, 1, 1) + dt.timedelta(days=r.randint(0, 80))).isoformat() for _ in range(n)], "description": "x",
                               "gl_key": [r.choice(["GL-5190", "GL-5000"]) for _ in range(n)], "prj_key": [r.choice(["PRJ-1", "PRJ-2"]) for _ in range(n)], "currency": "DKK",
                               "amount": [round(r.uniform(1, 99), 2) for _ in range(n)]})
        manual["amount_dkk"] = manual["amount"]
        out = write_down_journal(manual, "PRJ-1", context=CTX)
        want = manual[(manual["prj_key"] == "PRJ-1") & (manual["gl_key"] == "GL-5190")]
        assert sorted(out["journal_no"]) == sorted(want["journal_no"])
        assert list(zip(out["posting_date"], out["journal_no"])) == sorted(zip(out["posting_date"], out["journal_no"]))


# ---------------------------------------------------------------- planning
def department_hours(r: random.Random, periods: int = 6):
    rows = []
    for le in ("LE-01", "LE-02"):
        for dep in ("DEP-1", "DEP-2", "DEP-3"):
            for p in range(periods):
                avail = r.choice([0.0, round(r.uniform(100, 200), 1)])
                proj, serv = (round(r.uniform(0, avail), 1), round(r.uniform(0, 20), 1)) if avail else (0.0, 0.0)
                rows.append({"le_key": le, "dep_key": dep, "period": f"2026-{p + 1:02d}", "utilisation_pct": 50.0, "project_hours": proj, "service_hours": serv, "available_hours": avail})
    return pd.DataFrame(rows)


def test_utilisation_by_department_is_invariant_to_how_the_periods_are_cut_or_ordered():
    r = rng(10)
    for _ in range(25):
        m = department_hours(r)
        before = {"m": m.copy()}
        whole = utilisation(m, by="department", context=CTX).sort_values(["le_key", "dep_key"]).reset_index(drop=True)
        untouched(before, {"m": m})
        merged = m.assign(period=m["period"].map(lambda p: "2026-01" if p in ("2026-01", "2026-02") else p))        # two periods become one
        merged = merged.groupby(["le_key", "dep_key", "period"], as_index=False).agg({"utilisation_pct": "mean", "project_hours": "sum", "service_hours": "sum", "available_hours": "sum"})
        again = utilisation(merged.sample(frac=1, random_state=r.randint(0, 99)), by="department", context=CTX).sort_values(["le_key", "dep_key"]).reset_index(drop=True)
        assert whole.drop(columns="utilisation_pct").round(6).equals(again.drop(columns="utilisation_pct").round(6)) and np.allclose(whole["utilisation_pct"].fillna(-1), again["utilisation_pct"].fillna(-1))


def test_utilisation_by_period_has_no_value_without_available_hours_and_the_recomputed_value_is_booked_over_available():
    r = rng(11)
    for _ in range(25):
        out = utilisation(department_hours(r), context=CTX)
        none = out["available_hours"] == 0
        assert out.loc[none, "utilisation_pct"].isna().all() and out.loc[~none, "utilisation_pct"].notna().all()
        want = (out["project_hours"] + out["service_hours"]) / out["available_hours"].where(~none) * 100
        assert np.allclose(out.loc[~none, "utilisation_pct"], want[~none])
        assert list(out[["le_key", "dep_key", "period"]].itertuples(index=False)) == sorted(out[["le_key", "dep_key", "period"]].itertuples(index=False))


# ---------------------------------------------------------------- consolidation
IC = ["ic_ref", "kind", "period", "amount_le01_dkk", "amount_le02_dkk", "amount_le02_eur", "difference_dkk", "status"]
CE = ["fiscal_year", "period", "entry_no", "entry_type", "basis", "debit_le_key", "debit_gl_key", "credit_le_key", "credit_gl_key", "amount_dkk", "difference_dkk"]


def pairs(r: random.Random, n: int = 15) -> pd.DataFrame:
    rows = []
    for i in range(n):
        a = round(r.uniform(100, 9000), 2)
        b = round(a + r.choice([0, 0, 0.5, -0.5, 1.0, -1.0, 3.0, -7.25]), 2)               # a difference of exactly 1.0 sits on the default tolerance
        rows.append({"ic_ref": f"IC-{i + 1:04d}", "kind": r.choice(["loan", "trade"]), "period": "2026-03", "amount_le01_dkk": a, "amount_le02_dkk": b, "amount_le02_eur": round(b / 7.46, 2),
                     "difference_dkk": 0.0, "status": "matched"})
    return pd.DataFrame(rows)


def test_intercompany_match_is_invariant_under_the_order_and_swapping_the_two_sides_flips_the_sign():
    r = rng(12)
    for _ in range(30):
        m = pairs(r)
        before = {"m": m.copy()}
        out = intercompany_match(m, context=CTX).value.sort_values("ic_ref").reset_index(drop=True)
        untouched(before, {"m": m})
        again = intercompany_match(m.sample(frac=1, random_state=r.randint(0, 99)), context=CTX).value.sort_values("ic_ref").reset_index(drop=True)
        assert out.equals(again)
        swapped = m.assign(amount_le01_dkk=m["amount_le02_dkk"], amount_le02_dkk=m["amount_le01_dkk"])
        flipped = intercompany_match(swapped, context=CTX).value.sort_values("ic_ref").reset_index(drop=True)
        assert np.allclose(flipped["difference_dkk"], -out["difference_dkk"], atol=1e-9) and list(flipped["status"]) == list(out["status"])


def test_a_pair_is_matched_exactly_when_the_difference_is_within_the_tolerance_and_a_wider_tolerance_never_unmatches():
    r = rng(13)
    for _ in range(30):
        m = pairs(r)
        narrow = intercompany_match(m, tolerance_dkk=1.0, context=CTX).value.set_index("ic_ref")
        wide = intercompany_match(m, tolerance_dkk=10.0, context=CTX).value.set_index("ic_ref")
        assert ((narrow["difference_dkk"].abs() <= 1.0) == (narrow["status"] == "matched")).all()
        assert (wide.loc[narrow["status"] == "matched", "status"] == "matched").all() and (wide["status"] == "matched").sum() >= (narrow["status"] == "matched").sum()


def entries(r: random.Random, with_types: bool = True) -> pd.DataFrame:
    rows = []
    for i, kind in enumerate(["investment", "ic_loan", "ic_trade_revenue"] * 3):
        a, b = r.sample(["GL-8000", "GL-8100", "GL-8200", "GL-8300"], 2)
        rows.append([2026, f"2026-0{r.randint(1, 3)}", i + 1, kind, "movement", "LE-01", a, "LE-02", b, round(r.uniform(10, 900), 2), 0.0])
    return pd.DataFrame(rows, columns=CE)


def test_eliminations_find_nothing_in_clean_entries_and_one_bad_amount_is_one_violation():
    r = rng(14)
    for _ in range(30):
        e = entries(r)
        assert eliminations(e, context=CTX).empty
        k = r.randrange(len(e))
        bad = e.copy()
        bad.loc[k, "amount_dkk"] = -abs(bad.loc[k, "amount_dkk"])
        out = eliminations(bad, context=CTX)
        assert list(out["rule"]) == ["non_positive_amount"]
        zero = e.copy()
        zero.loc[k, "amount_dkk"] = 0.0                                          # an amount of zero is not positive either
        assert list(eliminations(zero, context=CTX)["rule"]) == ["non_positive_amount"]
        assert not e.equals(bad)                                                 # the clean frame was not changed by the call on the other


def test_the_group_trial_balance_does_not_depend_on_the_order_and_the_entries_eliminate_to_zero_over_all_accounts():
    r = rng(15)
    for _ in range(25):
        lines = pd.DataFrame({"le_key": [r.choice(["LE-01", "LE-02"]) for _ in range(30)], "period": [f"2026-0{r.randint(1, 3)}" for _ in range(30)],
                              "gl_key": [r.choice(["GL-8000", "GL-8100", "GL-8200"]) for _ in range(30)], "amount_dkk": [round(r.uniform(-500, 500), 2) for _ in range(30)], "source": "manual"})
        adj = pd.DataFrame({"period": ["2026-01", "2026-02"], "gl_key": ["GL-8000", "GL-8100"], "debit_dkk": [10.0, 0.0], "credit_dkk": [0.0, 10.0]})
        e = entries(r)
        before = {"lines": lines.copy(), "adj": adj.copy(), "e": e.copy()}
        out = group_trial_balance(lines, adj, e, context=CTX).value
        untouched(before, {"lines": lines, "adj": adj, "e": e})
        again = group_trial_balance(lines.sample(frac=1, random_state=r.randint(0, 99)), adj, e.sample(frac=1, random_state=r.randint(0, 99)), context=CTX).value
        assert out.equals(again)
        assert abs(out["elimination_dkk"].sum()) < 0.011
        parts = out["le01_movement_dkk"] + out["le02_movement_dkk"] + out["adjustment_dkk"] + out["elimination_dkk"]
        assert np.allclose(out["movement_dkk"], parts, atol=0.011)                  # every row is the sum of its four parts
        assert abs(out["movement_dkk"].sum() - (lines["amount_dkk"].sum() + (adj["debit_dkk"] - adj["credit_dkk"]).sum())) < 0.011
        assert list(zip(out["period"], out["gl_key"])) == sorted(zip(out["period"], out["gl_key"]))


# ---------------------------------------------------------------- payroll
def test_ledger_gross_pay_is_the_sum_of_the_salary_lines_and_invariant_under_their_order():
    r = rng(16)
    for _ in range(30):
        n = 40
        lines = pd.DataFrame({"le_key": [r.choice(["LE-01", "LE-02"]) for _ in range(n)], "cc_key": [r.choice(["CC-1", "CC-2", "CC-3"]) for _ in range(n)],
                              "gl_key": [r.choice(["GL-7000", "GL-7005", "GL-7050", "GL-6000"]) for _ in range(n)], "period": [f"2026-0{r.randint(1, 3)}" for _ in range(n)],
                              "amount": [round(r.uniform(-100, 9000), 2) for _ in range(n)]})
        before = {"lines": lines.copy()}
        out = ledger_gross_pay(lines, context=CTX)
        untouched(before, {"lines": lines})
        salary = lines[lines["gl_key"] != "GL-6000"]
        assert abs(out["ledger_gross_pay"].sum() - salary["amount"].sum()) < 0.011
        assert list(out[["le_key", "cc_key", "period"]].itertuples(index=False)) == sorted(out[["le_key", "cc_key", "period"]].itertuples(index=False))
        assert out.equals(ledger_gross_pay(lines.sample(frac=1, random_state=r.randint(0, 99)), context=CTX))


# ---------------------------------------------------------------- cash
PARTS = ["receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new", "payments_net_wages",
         "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest"]


def forecast(r: random.Random):
    opening = round(r.uniform(1000, 9000), 2)
    first, rows = opening, []
    for week in range(1, 14):
        parts = {p: round(r.uniform(-300, 300), 2) for p in PARTS}
        net = round(sum(parts.values()), 2)
        closing = round(opening + net, 2)
        rows.append({"le_key": "LE-01", "forecast_date": "2026-03-31", "week_no": week, "opening_cash": opening, "net_cash_flow": net, "closing_cash": closing,
                     "closing_cash_p10": closing - 50, "closing_cash_p90": closing + 50, **parts})
        opening = closing
    return pd.DataFrame(rows), pd.DataFrame({"le_key": ["LE-01"], "balance_date": ["2026-03-31"], "closing_balance": [first]})


def test_a_consistent_forecast_keeps_the_identity_chain_and_a_broken_link_is_found_in_the_rule_of_that_link():
    r = rng(17)
    for _ in range(30):
        cf, bank = forecast(r)
        before = {"cf": cf.copy(), "bank": bank.copy()}
        assert cash_forecast_checks(cf, bank, context=CTX).empty
        untouched(before, {"cf": cf, "bank": bank})
        week = r.randint(1, 13)
        broken = cf.copy()
        broken.loc[broken["week_no"] == week, "opening_cash"] += 5.0
        rules = set(cash_forecast_checks(broken, bank, context=CTX)["rule"])
        assert ("opening_differs_from_bank" if week == 1 else "weekly_chain_broken") in rules and "closing_not_opening_plus_net" in rules


# ---------------------------------------------------------------- subledgers
def receivables(r: random.Random, n: int = 20):
    gl = pd.DataFrame({"gl_key": ["GL-1100", "GL-1190", "GL-2100"], "control_type": ["ar", "retention", "ap"]})
    alloc = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "allocation_kind", "document_type", "booked_amount", "inv_key", "sinv_key", "opening_item_ref"])
    pay = pd.DataFrame(columns=["le_key", "bank_account", "payment_no", "payment_date"])
    ob = pd.DataFrame({"le_key": ["LE-01"], "gl_key": ["GL-1100"], "item_ref": ["O1"], "document_date": ["2024-12-01"], "due_date": [None], "amount": [0.0], "currency": ["DKK"], "cus_key": [None],
                       "sup_key": [None]})
    gross = [round(r.uniform(100, 9000), 2) for _ in range(n)]
    ci = pd.DataFrame({"inv_key": [f"I{i}" for i in range(n)], "le_key": "LE-01", "cus_key": [r.choice(["CUS-1", "CUS-2", "CUS-3"]) for _ in range(n)], "invoice_type": "invoice",
                       "invoice_date": "2025-01-10", "due_date": [(dt.date(2025, 1, 10) + dt.timedelta(days=r.randint(5, 150))).isoformat() for _ in range(n)], "gross_amount_le": gross,
                       "retention_amount_le": [round(g * r.choice([0, 0.05, 0.1]), 2) for g in gross], "retention_release_date": None, "written_off_date": None, "counterpart_le_key": None})
    return ci, alloc, pay, ob, gl


def test_the_ageing_buckets_are_the_sum_of_the_open_amounts_and_a_later_date_never_adds_to_the_not_due_bucket():
    r = rng(18)
    for _ in range(15):
        ci, alloc, pay, ob, gl = receivables(r)
        before = {"ci": ci.copy()}
        items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 6, 30), context=CTX)
        untouched(before, {"ci": ci})
        total = ci["gross_amount_le"].sum() - ci["retention_amount_le"].sum()
        not_due = []
        for day in (dt.date(2025, 2, 1), dt.date(2025, 3, 15), dt.date(2025, 5, 1), dt.date(2025, 6, 30)):
            out = ageing(items, day, context=CTX)
            assert abs(out["amount"].sum() - total) < 0.011 and out["n_items"].sum() == len(ci)
            not_due.append(out.loc[out["bucket"] == "not_due", "amount"].sum())
        assert not_due == sorted(not_due, reverse=True) and not_due[0] > 0 and not_due[-1] == 0          # the first date has items not yet due, the last has none


def test_an_item_due_on_the_date_is_not_yet_late_and_one_day_later_it_is_in_the_first_late_bucket():
    ci, alloc, pay, ob, gl = receivables(rng(30), n=1)
    ci = ci.assign(due_date="2025-03-31", retention_amount_le=0.0)
    items = open_items_ar(ci, alloc, pay, ob, gl, dt.date(2025, 4, 30), context=CTX)
    assert list(ageing(items, dt.date(2025, 3, 31), context=CTX)["bucket"]) == ["not_due"]
    assert list(ageing(items, dt.date(2025, 4, 1), context=CTX)["bucket"]) == ["1-30"]
    assert list(ageing(items, dt.date(2025, 4, 30), context=CTX)["bucket"]) == ["1-30"] and list(ageing(items, dt.date(2025, 5, 1), context=CTX)["bucket"]) == ["31-60"]


# ---------------------------------------------------------------- exposure
def test_supplier_spend_over_the_whole_range_is_the_sum_of_the_spend_over_two_adjacent_ranges():
    r = rng(19)
    for _ in range(25):
        n = 60
        si = pd.DataFrame({"sinv_key": [f"SI-{i:05d}" for i in range(n)], "sup_key": [r.choice(["SUP-1", "SUP-2", "SUP-3"]) for _ in range(n)],
                           "invoice_type": [r.choice(["invoice", "invoice", "credit_note"]) for _ in range(n)],
                           "invoice_date": [(dt.date(2026, 1, 1) + dt.timedelta(days=r.randint(0, 89))).isoformat() for _ in range(n)], "net_amount_dkk": [round(r.uniform(10, 9000), 2) for _ in range(n)]})
        sup = pd.DataFrame({"sup_key": ["SUP-1", "SUP-2", "SUP-3"], "category": ["a", "b", "a"]})
        before = {"si": si.copy(), "sup": sup.copy()}
        whole = supplier_spend(si, sup, dt.date(2026, 1, 1), dt.date(2026, 3, 31), context=CTX).set_index("sup_key")
        untouched(before, {"si": si, "sup": sup})
        cut = dt.date(2026, 1, 1) + dt.timedelta(days=r.randint(10, 70))
        left = supplier_spend(si, sup, dt.date(2026, 1, 1), cut, context=CTX).set_index("sup_key")
        right = supplier_spend(si, sup, cut + dt.timedelta(days=1), dt.date(2026, 3, 31), context=CTX).set_index("sup_key")
        both = left[["n_invoices", "spend_dkk"]].add(right[["n_invoices", "spend_dkk"]], fill_value=0)
        assert np.allclose(both.loc[whole.index, "spend_dkk"], whole["spend_dkk"], atol=0.011) and (both.loc[whole.index, "n_invoices"] == whole["n_invoices"]).all()


# ---------------------------------------------------------------- reconcile
def test_the_asset_rollforward_identity_chains_from_month_to_month_ends_at_full_cost_and_the_net_book_value_is_cost_less_depreciation():
    r = rng(20)
    for _ in range(25):
        n = 6
        fa = pd.DataFrame({"le_key": "LE-01", "asset_class": [r.choice(["IT", "Vehicles"]) for _ in range(n)],
                           "acquisition_date": [dt.date(2023, 1, 1) + dt.timedelta(days=r.randint(0, 700)) for _ in range(n)], "cost": [round(r.uniform(1000, 90000), 2) for _ in range(n)],
                           "useful_life_months": [r.choice([12, 36, 60]) for _ in range(n)], "disposal_date": None, "depreciation_method": "straight_line_monthly", "currency": "DKK"})
        before = {"fa": fa.copy()}
        s = fixed_asset_rollforward(fa, context=CTX).value
        untouched(before, {"fa": fa})
        for _, g in s.groupby(["le_key", "asset_class"]):
            g = g.sort_values("period")
            assert np.allclose(g["accumulated_opening"].iloc[1:].to_numpy(), g["accumulated_closing"].iloc[:-1].to_numpy(), atol=0.011)
            assert np.allclose(g["cost_opening"].iloc[1:].to_numpy(), g["cost_closing"].iloc[:-1].to_numpy(), atol=0.011)
            assert (g["accumulated_closing"].diff().dropna() >= -0.011).all()
        assert np.allclose(s["net_book_value"], s["cost_closing"] - s["accumulated_closing"], atol=0.011)
        assert s["accumulated_closing"].max() <= s["cost_closing"].max() + 0.011 and (s["accumulated_closing"] <= s["cost_closing"] + 0.011).all()


# ---------------------------------------------------------------- statements
def test_size_class_is_monotone_in_the_revenue():
    r = rng(21)
    for _ in range(30):
        n = 8
        rep = pd.DataFrame({"rpt_key": [f"RPT-{i}" for i in range(n)], "le_key": "LE-01", "revenue": [r.choice([0, 10 ** 3, 10 ** 8, 10 ** 12]) for _ in range(n)],
                            "total_assets": [r.choice([0, 10 ** 3, 10 ** 8, 10 ** 12]) for _ in range(n)], "average_employees": [r.choice([0, 3, 60, 900]) for _ in range(n)], "size_criteria_met": 0})
        before = {"rep": rep.copy()}
        low = size_class(rep, context=CTX).value.set_index("rpt_key")
        untouched(before, {"rep": rep})
        high = size_class(rep.assign(revenue=10 ** 13), context=CTX).value.set_index("rpt_key")
        assert (high["criteria_exceeded"] >= low["criteria_exceeded"]).all() and high["revenue_over"].all()
        zero = size_class(rep.assign(revenue=0, total_assets=0, average_employees=0), context=CTX).value
        assert (zero["criteria_exceeded"] == 0).all()


def test_a_value_at_a_size_threshold_does_not_exceed_it_and_one_cent_more_does():
    from halvaro.finance import statements
    names = {"revenue": "net_revenue", "total_assets": "balance_sheet_total", "average_employees": "average_full_time_employees"}
    over = {"revenue": "revenue_over", "total_assets": "assets_over", "average_employees": "employees_over"}
    for column, threshold in names.items():
        limit = fact(f"{statements._FREP_DK}.size_thresholds.{threshold}").value
        rep = pd.DataFrame({"rpt_key": ["AT", "ABOVE"], "le_key": "LE-01", "revenue": 0, "total_assets": 0, "average_employees": 0, "size_criteria_met": 0})
        rep[column] = [limit, limit + 0.01]
        out = size_class(rep, context=CTX).value.set_index("rpt_key")
        assert not out.loc["AT", over[column]] and out.loc["ABOVE", over[column]], column


# ---------------------------------------------------------------- project_costs (cost per metre)
def cost_frames(r: random.Random, n: int = 8):
    comp = pd.DataFrame({"prj_key": [f"P{i}" for i in range(1, n + 1)], "legacy": False, "data_depth": "full"})
    project = pd.DataFrame({"prj_key": comp["prj_key"], "route_length_m": [r.choice([500.0, 800.0, 1000.0, 2500.0, np.nan]) for _ in range(n)]})
    rows = []
    for prj in comp["prj_key"]:
        for code in r.sample(["CST-110", "CST-120", "CST-720"], r.randint(0, 3)):
            total = 0.0
            for month in range(1, r.randint(2, 5)):
                step = round(r.uniform(10, 900), 2)
                total = round(total + step, 2)
                rows.append((prj, f"2025-{month:02d}", code, "EUR", total, step, 0.0))
    return comp, pd.DataFrame(rows, columns=["prj_key", "period", "cst_key", "currency", "actual_amount", "incurred_in_period", "estimate_amount"]), project


def test_cost_per_metre_is_homogeneous_in_the_cost_and_in_the_length_and_does_not_depend_on_the_order_of_the_rows():
    r = rng(22)
    for _ in range(20):
        comp, cb, project = cost_frames(r)
        before = {"comp": comp.copy(), "cb": cb.copy(), "project": project.copy()}
        base = cost_per_metre_by_cost_code(comp, cb, project, context=CTX)
        untouched(before, {"comp": comp, "cb": cb, "project": project})
        med = base.by_code.set_index("cst_key")["median_per_metre"]
        twice = cost_per_metre_by_cost_code(comp, cb.assign(actual_amount=cb["actual_amount"] * 2), project, context=CTX).by_code.set_index("cst_key")["median_per_metre"]
        assert np.allclose(twice.reindex(med.index), med * 2, atol=0.011)
        longer = cost_per_metre_by_cost_code(comp, cb, project.assign(route_length_m=project["route_length_m"] * 2), context=CTX).by_code.set_index("cst_key")["median_per_metre"]
        assert np.allclose(longer.reindex(med.index), med / 2, atol=0.011)
        shuffled = cost_per_metre_by_cost_code(comp.sample(frac=1, random_state=r.randint(0, 99)), cb.sample(frac=1, random_state=r.randint(0, 99)), project, context=CTX)
        assert shuffled.by_code.reset_index(drop=True).equals(base.by_code.reset_index(drop=True))


def test_the_median_per_metre_is_between_the_lowest_and_the_highest_value_of_the_projects_and_a_project_without_length_or_rows_is_dropped():
    r = rng(23)
    seen = 0
    for _ in range(25):
        comp, cb, project = cost_frames(r)
        out = cost_per_metre_by_cost_code(comp, cb, project, context=CTX)
        last = cb.sort_values("period").groupby(["prj_key", "cst_key"], as_index=False).last().merge(project, on="prj_key")
        last = last[last["route_length_m"].notna()]
        last["per_metre"] = last["actual_amount"] / last["route_length_m"]
        for _, row in out.by_code.iterrows():
            values = last.loc[last["cst_key"] == row["cst_key"], "per_metre"]
            assert values.min() - 0.011 <= row["median_per_metre"] <= values.max() + 0.011 and row["n_projects"] == len(values)
            m = row["median_per_metre"]                                          # a median has at least half of the values on each side (or on it)
            assert (values <= m + 0.011).sum() * 2 >= len(values) and (values >= m - 0.011).sum() * 2 >= len(values)
            if len(values) % 2 == 1:                                             # with an odd number of projects the median is one of their values, a mean is not
                assert np.isclose(values.to_numpy(), row["median_per_metre"], atol=0.011).any()
            seen += 1
        no_length = set(project.loc[project["route_length_m"].isna(), "prj_key"]) | (set(comp["prj_key"]) - set(cb["prj_key"]))
        assert no_length == set(out.dropped["prj_key"]) if len(out.dropped) else not no_length
    assert seen > 20
