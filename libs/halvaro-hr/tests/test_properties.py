"""Property style tests of the hr modules availability, crosswalk, pay, payroll and controlled that had none (standard 3.2.3, lane P2, issue #469).

Each test states a rule that must hold for many inputs drawn from a seeded generator (no extra package): the hours of a period are the sum of the hours of its two halves, the person found by a username is the
holder in the history, suppressing twice is suppressing once, and the inputs are left as they were. The rules are written from the documented behaviour, not from the function bodies. The payroll tests use
obviously invented round amounts (the restricted column is read by the function, so the frame needs it), never a value of the data.
"""
import datetime as dt
import random

import numpy as np
import pandas as pd
import pytest

from halvaro.core import Context
from halvaro.hr import AmbiguousUsername, availability_hours, build_username_index, overlapping_usernames, payroll_aggregate, resolve_username, suppress_small_cells
from halvaro.hr.availability import HOURS_PER_DAY
from halvaro.hr.controlled import controlled_work_audit

D = dt.date
TEAM = pd.DataFrame({"team_key": ["T-DK", "T-HH", "T-NI"], "site_key": ["SITE-01", "SITE-05", "SITE-06"], "dep_key": ["DEP-A", "DEP-A", "DEP-B"]})


def rng(seed: int) -> random.Random:
    return random.Random(20261119 + seed)


def untouched(before: dict, after: dict) -> None:
    for name, frame in before.items():
        assert frame.equals(after[name]), f"{name} was changed by the call"


# ---------------------------------------------------------------- availability
def staff(r: random.Random, n: int = 12):
    emp, term, leave = [], [], []
    for i in range(n):
        key = f"EMP-{i + 1:06d}"
        hire = D(2025, 6, 1) + dt.timedelta(days=r.randint(0, 400))
        emp.append((key, hire, None if r.random() < 0.8 else hire + dt.timedelta(days=r.randint(30, 300))))
        term.append((key, hire, None, r.choice(["T-DK", "T-HH", "T-NI"]), "R", r.choice([0.5, 0.8, 1.0])))
        for _ in range(r.randint(0, 2)):
            s = D(2026, 1, 1) + dt.timedelta(days=r.randint(0, 120))
            leave.append((key, s, s + dt.timedelta(days=r.randint(0, 9)), r.choice(["holiday", "sick"])))
    return (pd.DataFrame(emp, columns=["emp_key", "hire_date", "leave_date"]), pd.DataFrame(term, columns=["emp_key", "valid_from", "valid_to", "team_key", "role_key", "fte"]),
            pd.DataFrame(leave, columns=["emp_key", "start", "end", "leave_type"]))


def hours(emp, term, leave, periods):
    return availability_hours(emp, term, leave, TEAM, periods)


def test_the_hours_of_a_period_are_the_sum_of_the_hours_of_its_two_halves():
    r = rng(1)
    for _ in range(25):
        emp, term, leave = staff(r)
        a = D(2026, 1, 1) + dt.timedelta(days=r.randint(0, 20))
        c = a + dt.timedelta(days=r.randint(40, 120))
        b = a + dt.timedelta(days=r.randint(5, 30))
        whole = hours(emp, term, leave, [(a, c)]).set_index("emp_key")
        halves = hours(emp, term, leave, [(a, b), (b + dt.timedelta(days=1), c)]).groupby("emp_key")[["working_days", "leave_days", "net_days", "hours"]].sum()
        both = whole.index.union(halves.index)
        for col in ("working_days", "leave_days", "net_days", "hours"):
            assert np.allclose(whole[col].reindex(both).fillna(0), halves[col].reindex(both).fillna(0), atol=1e-6), col


def test_net_days_are_working_days_less_leave_days_and_the_hours_are_net_days_times_fte_times_the_hours_of_a_day():
    r = rng(2)
    for _ in range(25):
        emp, term, leave = staff(r)
        out = hours(emp, term, leave, [(D(2026, 1, 1), D(2026, 4, 30))])
        fte = out["emp_key"].map(term.set_index("emp_key")["fte"])
        assert (out["net_days"] == out["working_days"] - out["leave_days"]).all() and (out["leave_days"] >= 0).all()
        assert np.allclose(out["hours"], out["net_days"] * fte * HOURS_PER_DAY, atol=1e-6)


def test_availability_leaves_the_inputs_alone_is_sorted_and_does_not_depend_on_the_order_of_the_rows():
    r = rng(3)
    for _ in range(20):
        emp, term, leave = staff(r)
        periods = [(D(2026, 1, 1), D(2026, 1, 31)), (D(2026, 2, 1), D(2026, 2, 28))]
        before = {"emp": emp.copy(), "term": term.copy(), "leave": leave.copy()}
        out = hours(emp, term, leave, periods)
        untouched(before, {"emp": emp, "term": term, "leave": leave})
        keys = list(zip(out["emp_key"], out["period_start"], out["period_end"]))
        assert keys == sorted(keys) and len(out) > 0
        shuffled = hours(emp.sample(frac=1, random_state=r.randint(0, 99)), term.sample(frac=1, random_state=r.randint(0, 99)), leave.sample(frac=1, random_state=r.randint(0, 99)), periods)
        assert out.equals(shuffled)


def test_more_leave_never_gives_more_hours():
    r = rng(4)
    for _ in range(25):
        emp, term, leave = staff(r)
        extra = pd.concat([leave, pd.DataFrame([(emp["emp_key"].iloc[0], D(2026, 2, 2), D(2026, 2, 13), "holiday")], columns=leave.columns)], ignore_index=True)
        p = [(D(2026, 1, 1), D(2026, 3, 31))]
        low = hours(emp, term, extra, p).set_index("emp_key")["hours"]
        high = hours(emp, term, leave, p).set_index("emp_key")["hours"]
        assert (low <= high.reindex(low.index) + 1e-9).all()


# ---------------------------------------------------------------- crosswalk
def history(r: random.Random, n: int = 30):
    """One holder per username at a time: each username has two consecutive stints held by two persons."""
    rows = []
    for i in range(n):
        start = D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 200))
        mid = start + dt.timedelta(days=r.randint(10, 200))
        rows.append((f"user{i:03d}", f"EMP-{2 * i + 1:06d}", start, mid))
        rows.append((f"user{i:03d}", f"EMP-{2 * i + 2:06d}", mid + dt.timedelta(days=1), None))
    pool = pd.DataFrame({"account_name": ["pool-a"], "team_key": ["T-DK"], "valid_from": [D(2024, 1, 1)], "valid_to": [None]})
    return pd.DataFrame(rows, columns=["username", "emp_key", "valid_from", "valid_to"]), pool


def test_the_username_index_round_trip_resolves_every_stint_to_its_holder_and_nobody_before_the_first():
    r = rng(5)
    for _ in range(10):
        hist, pool = history(r)
        before = {"hist": hist.copy(), "pool": pool.copy()}
        index = build_username_index(hist, pool)
        untouched(before, {"hist": hist, "pool": pool})
        assert list(index["username"]) == sorted(index["username"]) and overlapping_usernames(index) == []
        for row in hist.itertuples():
            last = row.valid_to if row.valid_to is not None else row.valid_from + dt.timedelta(days=90)
            for day in (row.valid_from, last, row.valid_from + (last - row.valid_from) / 2):
                got = resolve_username(index, row.username, day)
                assert got is not None and got["emp_key"] == row.emp_key and got["kind"] == "employee"
            assert resolve_username(index, row.username, hist[hist["username"] == row.username]["valid_from"].min() - dt.timedelta(days=1)) is None
        assert resolve_username(index, "pool-a", D(2025, 1, 1))["kind"] == "pool"


def test_two_holders_on_the_same_day_are_listed_as_overlapping_and_refused_when_resolved():
    r = rng(6)
    for _ in range(10):
        hist, pool = history(r)
        i = r.randrange(0, len(hist), 2)
        clash = pd.concat([hist, pd.DataFrame([(hist.loc[i, "username"], "EMP-999999", hist.loc[i, "valid_from"], None)], columns=hist.columns)], ignore_index=True)
        index = build_username_index(clash, pool)
        assert overlapping_usernames(index) == [hist.loc[i, "username"]]
        with pytest.raises(AmbiguousUsername):
            resolve_username(index, hist.loc[i, "username"], hist.loc[i, "valid_from"])


# ---------------------------------------------------------------- pay (cells of a gap table, no pay column)
def gap_table(r: random.Random, n: int = 20) -> pd.DataFrame:
    return pd.DataFrame({"group": [f"G{i}" for i in range(n)], "n_women": [r.randint(0, 20) for _ in range(n)], "n_men": [r.randint(0, 20) for _ in range(n)],
                         "raw_gap_pct": [round(r.uniform(-9, 9), 2) for _ in range(n)], "adjusted_gap_se_pct": [round(r.uniform(0, 3), 2) for _ in range(n)],
                         "flag": ["ok"] * n, "rank": list(range(1, n + 1))})


def test_suppressing_small_cells_is_idempotent_and_leaves_the_input_alone():
    r = rng(7)
    for _ in range(30):
        t = gap_table(r)
        before = {"t": t.copy()}
        once = suppress_small_cells(t, ["raw_gap_pct"])
        untouched(before, {"t": t})
        twice = suppress_small_cells(once, ["raw_gap_pct"])
        assert once.equals(twice) and list(once["group"]) == list(t["group"])


def test_a_value_is_suppressed_exactly_when_a_count_is_under_the_minimum_and_a_higher_minimum_never_shows_a_cell_again():
    r = rng(8)
    for _ in range(30):
        t = gap_table(r)
        low = suppress_small_cells(t, ["raw_gap_pct"], minimum_group=5)
        high = suppress_small_cells(t, ["raw_gap_pct"], minimum_group=12)
        small = (t[["n_women", "n_men"]] < 5).any(axis=1)
        assert (low["raw_gap_pct"].isna() == small).all() and (low["suppressed"] == small).all()
        assert (high["suppressed"] | ~low["suppressed"]).all()                                   # suppressed at 5 means suppressed at 12
        assert (low.loc[small, "flag"] == "suppressed").all() and (low.loc[~small, "flag"] == "ok").all()
        assert low.loc[~small, "raw_gap_pct"].equals(t.loc[~small, "raw_gap_pct"])


# ---------------------------------------------------------------- payroll (invented round amounts)
PAY_CONTEXT = Context.from_profile("mcp_people_hr", stage="day1")


def pay_terms(r: random.Random, n: int = 60):
    team = pd.DataFrame({"team_key": ["T1", "T2", "T3"], "cost_centre_key": ["CC-1", "CC-1", "CC-2"], "legal_entity_key": ["LE-01", "LE-01", "LE-01"]})
    grade = pd.DataFrame({"gra_key": ["G1"], "band_min_dkk": [10000.0], "band_max_dkk": [20000.0], "band_min_eur": [1000.0], "band_max_eur": [2000.0]})
    terms = pd.DataFrame({"emp_key": [f"E{i:03d}" for i in range(n)], "valid_from": D(2024, 1, 1), "valid_to": None, "team_key": [r.choice(["T1", "T2", "T3"]) for _ in range(n)], "grade_key": "G1",
                          "fte": [r.choice([0.5, 0.8, 1.0]) for _ in range(n)], "currency": "DKK", "base_salary": [10000.0 + 100 * r.randint(0, 50) for _ in range(n)]})
    return terms, team, grade


def test_payroll_aggregate_is_the_sum_of_the_terms_when_nothing_is_suppressed_and_leaves_the_inputs_alone():
    r = rng(8)
    for _ in range(15):
        terms, team, grade = pay_terms(r)
        before = {"terms": terms.copy(), "team": team.copy(), "grade": grade.copy()}
        out = payroll_aggregate(terms, team, grade, "2025-01", "2025-01", minimum_group=1, context=PAY_CONTEXT)
        untouched(before, {"terms": terms, "team": team, "grade": grade})
        assert abs(out["hr_gross_pay"].sum() - (terms["base_salary"] * terms["fte"]).sum()) < 0.01     # a term in force the whole month pays salary times fte
        assert out["n_people"].sum() == len(terms) and not {"emp_key", "base_salary"} & set(out.columns)
        assert out.equals(payroll_aggregate(terms.sample(frac=1, random_state=r.randint(0, 99)), team, grade, "2025-01", "2025-01", minimum_group=1, context=PAY_CONTEXT))


def test_pooling_small_groups_keeps_the_head_count_and_a_larger_minimum_never_shows_a_group_again():
    r = rng(9)
    for _ in range(15):
        terms, team, grade = pay_terms(r, n=30)
        low = payroll_aggregate(terms, team, grade, "2025-01", "2025-01", minimum_group=5, on_small="suppress", context=PAY_CONTEXT)
        high = payroll_aggregate(terms, team, grade, "2025-01", "2025-01", minimum_group=20, on_small="suppress", context=PAY_CONTEXT)
        assert low["n_people"].sum() == high["n_people"].sum() == len(terms)
        assert (high["suppressed"] | ~low["suppressed"]).all() and (low.loc[low["suppressed"], "hr_gross_pay"].isna()).all()
        pooled = payroll_aggregate(terms, team, grade, "2025-01", "2025-01", minimum_group=20, on_small="pool", context=PAY_CONTEXT)
        assert pooled["n_people"].sum() == len(terms)


# ---------------------------------------------------------------- controlled work (the audit of certificates)
ROLE = pd.DataFrame({"role_key": ["R1"], "name": ["Pipe fitter"]})
EMP = pd.DataFrame({"emp_key": ["EMP-1"], "legal_entity_key": ["LE-01"], "hire_date": [D(2020, 1, 1)]})
TERM = pd.DataFrame({"emp_key": ["EMP-1"], "valid_from": [D(2024, 1, 1)], "valid_to": [None], "role_key": ["R1"]})
PRJ = pd.DataFrame({"prj_key": ["P1"], "type": ["dh_network"]})
RULES = pd.DataFrame([dict(rule_id="pipework", qual_key="Q4", roles=["pipe_crew"], entity=None, project_types=["dh_network"], cst=[430], allocation=False)])
NO_ALLOCATION = pd.DataFrame({"emp_key": [], "prj_key": [], "start": [], "end": []})


def audit(entries: pd.DataFrame, issued: dt.date, expires: dt.date | None):
    cert = pd.DataFrame({"emp_key": ["EMP-1"], "qual_key": ["Q4"], "issued": [issued], "expires": [expires]})
    return controlled_work_audit(entries, NO_ALLOCATION, PRJ, TERM, ROLE, EMP, cert, RULES, D(2026, 1, 1), role_groups={"pipe_crew": ["Pipe fitter"]})


def entries(r: random.Random, n: int = 40) -> pd.DataFrame:
    return pd.DataFrame({"emp_key": "EMP-1", "prj_key": "P1", "work_date": [D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 600)) for _ in range(n)], "cst_key": "CST-430"})


def test_an_entry_is_a_violation_exactly_when_its_day_is_outside_the_certificate_and_a_longer_certificate_never_adds_one():
    r = rng(10)
    for _ in range(25):
        e = entries(r)
        issued = D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 200))
        expires = issued + dt.timedelta(days=r.randint(0, 300))
        before = {"e": e.copy()}
        a = audit(e, issued, expires)
        untouched(before, {"e": e})
        outside = ~e["work_date"].between(issued, expires)
        assert sorted(a.violations["work_date"].dt.date) == sorted(e.loc[outside, "work_date"])
        longer = audit(e, issued - dt.timedelta(days=30), expires + dt.timedelta(days=30))
        assert len(longer.violations) <= len(a.violations) and len(audit(e, issued, None).violations) <= len(a.violations)
        assert len(audit(e.sample(frac=1, random_state=r.randint(0, 99)), issued, expires).violations) == len(a.violations)
