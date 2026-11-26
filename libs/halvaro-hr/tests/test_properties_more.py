"""Property style tests of the hr modules availability, certs, controlled, coverage and org that the standard check found none for (standard 3.2.3, lane W1, issue #504).

Seeded random inputs, no extra package; each rule is written from the documented behaviour, not from the function bodies. The functions are called in the test itself.
"""
import datetime as dt
import random

import pandas as pd

from halvaro.hr import (allocation_hours, availability_hours, cert_intervals, cert_status_on, controlled_work_audit, headcount_on, project_crew, renewal_chains, terms_on, valid_on)

D = dt.date
TEAM = pd.DataFrame({"team_key": ["T-DK", "T-HH"], "site_key": ["SITE-01", "SITE-05"], "dep_key": ["DEP-A", "DEP-B"]})


def rng(seed: int) -> random.Random:
    return random.Random(20261120 + seed)


def people(r: random.Random, n: int = 15):
    emp = pd.DataFrame({"emp_key": [f"E{i:03d}" for i in range(n)], "hire_date": [D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 300)) for _ in range(n)], "leave_date": None,
                        "legal_entity_key": [r.choice(["LE-01", "LE-02"]) for _ in range(n)]})
    term = pd.DataFrame({"emp_key": emp["emp_key"], "valid_from": emp["hire_date"], "valid_to": None, "team_key": [r.choice(["T-DK", "T-HH"]) for _ in range(n)],
                         "role_key": "R", "fte": [r.choice([0.5, 1.0]) for _ in range(n)]})
    return emp, term


# ---------------------------------------------------------------- availability
def test_availability_hours_is_invariant_under_the_order_of_the_periods_and_allocation_hours_before_plus_after_is_the_total():
    r = rng(1)
    for _ in range(20):
        emp, term = people(r)
        leave = pd.DataFrame(columns=["emp_key", "start", "end", "leave_type"])
        periods = [(D(2026, 1, 1), D(2026, 1, 31)), (D(2026, 2, 1), D(2026, 2, 28)), (D(2026, 3, 1), D(2026, 3, 31))]
        shuffled = periods[:]
        r.shuffle(shuffled)
        assert availability_hours(emp, term, leave, TEAM, periods).equals(availability_hours(emp, term, leave, TEAM, shuffled))
        alloc = pd.DataFrame({"emp_key": emp["emp_key"][:6], "prj_key": "P1", "start": D(2026, 1, 5), "end": D(2026, 3, 20), "percent": [r.choice([25, 50, 100]) for _ in range(6)]})
        out = allocation_hours(alloc, emp, term, leave, TEAM, D(2026, 2, 10))
        assert ((out["hours_before"] + out["hours_after"] - out["hours"]).abs() < 1e-6).all()          # sum of parts: before and after the date make the stint


# ---------------------------------------------------------------- certs
def certs(r: random.Random, n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(n):
        issued = D(2022, 1, 1) + dt.timedelta(days=r.randint(0, 900))
        rows.append((f"E{r.randint(0, 9):03d}", r.choice(["Q1", "Q2"]), issued, None if r.random() < 0.2 else issued + dt.timedelta(days=r.randint(30, 900))))
    return pd.DataFrame(rows, columns=["emp_key", "qual_key", "issued", "expires"])


def test_valid_on_returns_only_certificates_in_force_on_the_date_one_per_person_and_qualification_invariant_under_row_order():
    r = rng(2)
    for _ in range(25):
        c = certs(r)
        day = D(2023, 1, 1) + dt.timedelta(days=r.randint(0, 900))
        before = c.copy()
        out = valid_on(c, day)
        assert c.equals(before) and not out.duplicated(["emp_key", "qual_key"]).any()
        assert (pd.to_datetime(out["issued"]) <= pd.Timestamp(day)).all() and (out["expires"].isna() | (pd.to_datetime(out["expires"]) >= pd.Timestamp(day))).all()
        assert out.equals(valid_on(c.sample(frac=1, random_state=r.randint(0, 99)), day))
        assert len(cert_status_on(c.assign(status="valid"), day)) == len(c)                                                    # every row has a status


def test_renewal_chains_and_cert_intervals_keep_every_certificate_sum_of_the_parts_equals_the_rows():
    r = rng(3)
    for _ in range(25):
        c = certs(r)
        assert sum(len(v) for v in cert_intervals(c).values()) == len(c)
        chained = renewal_chains(c.assign(origin="initial", event_no=range(len(c)), renews_issued=None))
        assert len(chained) == len(c) and chained["position"].min() == 1


# ---------------------------------------------------------------- controlled
def test_controlled_work_audit_a_longer_certificate_never_adds_a_violation_property():
    r = rng(4)
    role = pd.DataFrame({"role_key": ["R1"], "name": ["Pipe fitter"]})
    emp = pd.DataFrame({"emp_key": ["EMP-1"], "legal_entity_key": ["LE-01"], "hire_date": [D(2020, 1, 1)]})
    term = pd.DataFrame({"emp_key": ["EMP-1"], "valid_from": [D(2024, 1, 1)], "valid_to": [None], "role_key": ["R1"]})
    prj = pd.DataFrame({"prj_key": ["P1"], "type": ["dh_network"]})
    rules = pd.DataFrame([dict(rule_id="pipework", qual_key="Q4", roles=["crew"], entity=None, project_types=["dh_network"], cst=[430], allocation=False)])
    none = pd.DataFrame({"emp_key": [], "prj_key": [], "start": [], "end": []})
    for _ in range(25):
        te = pd.DataFrame({"emp_key": "EMP-1", "prj_key": "P1", "work_date": [D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 500)) for _ in range(30)], "cst_key": "CST-430"})
        a = D(2024, 1, 1) + dt.timedelta(days=r.randint(0, 200))
        b = a + dt.timedelta(days=r.randint(0, 200))

        def run(issued, expires):
            cert = pd.DataFrame({"emp_key": ["EMP-1"], "qual_key": ["Q4"], "issued": [issued], "expires": [expires]})
            return controlled_work_audit(te, none, prj, term, role, emp, cert, rules, D(2026, 1, 1), role_groups={"crew": ["Pipe fitter"]})
        short, longer = run(a, b), run(a - dt.timedelta(days=20), b + dt.timedelta(days=20))
        assert len(longer.violations) <= len(short.violations)
        outside = sum(1 for d in te["work_date"] if not a <= d <= b)                                    # by the rule: each time entry on a day without a valid certificate is one violation
        assert len(short.violations) == outside
        assert len(run(a, None).violations) <= len(short.violations)


# ---------------------------------------------------------------- coverage
def test_project_crew_has_one_row_per_person_with_the_larger_percent_and_is_invariant_under_the_order_of_the_rows():
    r = rng(5)
    for _ in range(30):
        n = 20
        alloc = pd.DataFrame({"emp_key": [f"E{r.randint(0, 6)}" for _ in range(n)], "prj_key": "P1", "start": [D(2026, 1, 1) + dt.timedelta(days=r.randint(0, 30)) for _ in range(n)],
                              "end": [None if r.random() < 0.3 else D(2026, 3, 1) + dt.timedelta(days=r.randint(0, 60)) for _ in range(n)], "percent": [r.choice([25, 50, 100]) for _ in range(n)]})
        plan = pd.DataFrame(columns=["prj_key", "emp_key", "planned_start", "planned_end", "percent"])
        day = D(2026, 2, 15)
        out = project_crew(alloc, plan, "P1", day)
        assert not out["emp_key"].duplicated().any()
        for _, row in out.iterrows():
            cover = alloc[(alloc["emp_key"] == row["emp_key"]) & (pd.to_datetime(alloc["start"]) <= pd.Timestamp(day)) & (alloc["end"].isna() | (pd.to_datetime(alloc["end"]) >= pd.Timestamp(day)))]
            assert row["percent"] == cover["percent"].max()
        assert out.sort_values("emp_key").reset_index(drop=True).equals(project_crew(alloc.sample(frac=1, random_state=r.randint(0, 99)), plan, "P1", day).sort_values("emp_key").reset_index(drop=True))


# ---------------------------------------------------------------- org
def test_headcount_on_sum_of_the_parts_is_the_same_total_at_every_level_and_terms_on_keeps_one_row_per_person():
    r = rng(6)
    for _ in range(25):
        emp, term = people(r)
        team = pd.DataFrame({"team_key": ["T-DK", "T-HH"], "dep_key": ["DEP-A", "DEP-B"]})
        day = D(2026, 6, 1)
        totals = {level: headcount_on(emp, term, team, day, level=level)["headcount"].sum() for level in ("department", "team", "entity")}
        assert len(set(totals.values())) == 1 and totals["team"] == int(((emp["hire_date"] <= day)).sum())
        once = terms_on(term, day)
        shuffled = terms_on(term.sample(frac=1, random_state=r.randint(0, 99)), day)
        assert not once["emp_key"].duplicated().any()
        assert once.sort_values("emp_key").reset_index(drop=True).equals(shuffled.sort_values("emp_key").reset_index(drop=True))
