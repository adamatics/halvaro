"""Oracles of on_call and requires_authorisation: the expected rota rows and plan counts come from plain python and pandas readings, never from the functions."""

import pandas as pd

import halvaro.grid as grid
from halvaro.core import Context

M12 = Context(stage="month12", role="r")


def _rota(rows):
    return pd.DataFrame(rows, columns=["team_key", "week_start", "primary_emp_key", "secondary_emp_key"])




def _got(frame):
    return [(r.team_key, pd.Timestamp(r.week_start).date(), r.primary_emp_key, r.secondary_emp_key) for r in frame.itertuples(index=False)]


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# on_call
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def test_oracle_on_call_hand_worked_rota_boundaries():
    """route: a hand worked rota of three teams (a stub Sunday week, Mondays, a missing week) and the answer on each day around every change, written down by hand."""
    rota = _rota([("A", "2026-01-04", "a0", "b0"),            # a one day stub week on a Sunday, the next row starts the day after
                  ("A", "2026-01-05", "a1", "b1"), ("A", "2026-01-12", "a2", "b2"),
                  ("B", "2026-01-05", "c1", "d1"), ("B", "2026-01-19", "c3", "d3"),            # B: the week of 12 January is missing
                  ("C", "2026-01-05", "e1", "f1")])
    rota0 = rota.copy()

    def on(day, **kw):
        return [(t, str(w), p, s) for t, w, p, s in _got(grid.on_call(rota, day, context=M12, **kw))]

    assert on("2026-01-03") == [], "before the first row of every team: nobody"
    assert on("2026-01-04") == [("A", "2026-01-04", "a0", "b0")], "the stub week covers its Sunday"
    assert on("2026-01-05") == [("A", "2026-01-05", "a1", "b1"), ("B", "2026-01-05", "c1", "d1"), ("C", "2026-01-05", "e1", "f1")], "the day a row starts belongs to that row, not to the stub"
    assert on("2026-01-11") == [("A", "2026-01-05", "a1", "b1"), ("B", "2026-01-05", "c1", "d1"), ("C", "2026-01-05", "e1", "f1")], "the last day of a seven day week"
    assert on("2026-01-12") == [("A", "2026-01-12", "a2", "b2")], "the eighth day: A has a new row; B and C have none (a missing week is nobody, the earlier person does not cover it)"
    assert on("2026-01-18") == [("A", "2026-01-12", "a2", "b2")], "the last row of A runs seven days"
    assert on("2026-01-19") == [("B", "2026-01-19", "c3", "d3")], "the first day after the last row of A has run out"
    assert on("2026-01-25") == [("B", "2026-01-19", "c3", "d3")] and on("2026-01-26") == [], "the last row of B runs seven days, the eighth day is nobody"
    assert on("2026-01-05", team_key="B") == [("B", "2026-01-05", "c1", "d1")] and on("2026-01-05", team_key=["A", "C"]) == [("A", "2026-01-05", "a1", "b1"), ("C", "2026-01-05", "e1", "f1")]
    assert on("2026-01-05", team_key="Z") == [], "a team that is not in the rota is nobody"
    assert on("2026-01-07", days=3, team_key="C") == [("C", "2026-01-05", "e1", "f1")] and on("2026-01-08", days=3, team_key="C") == [], "days=3: a row without a next row runs three days, the third day is the last"
    assert on("2026-01-08", days=3) == [], "days=3: the rows of A and B end after three days even though the next row is later"
    pd.testing.assert_frame_equal(rota, rota0)
    assert grid.on_call(rota, "2026-01-05", context=M12).columns.tolist() == ["team_key", "week_start", "primary_emp_key", "secondary_emp_key"]



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# requires_authorisation
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _plans(rows):
    return pd.DataFrame(rows, columns=["net_key", "plan_no", "plan_type", "requires_electrical_authorisation", "team_key", "status"])


def test_oracle_requires_authorisation_hand_worked_counts_and_shares():
    """route: a hand worked example with eleven plans, active and not, and the counts and shares of each team and plan type written down."""
    p = _plans([("N1", 1, "inspection", True, "T1", "active"), ("N2", 1, "inspection", False, "T1", "active"), ("N3", 1, "inspection", False, "T1", "active"),        # T1 inspection: 1 of 3
                ("N4", 1, "inspection", True, "T1", "suspended"), ("N5", 1, "inspection", True, "T1", "retired"),                                                    # not active
                ("N1", 2, "service", True, "T1", "active"), ("N2", 2, "service", True, "T1", "active"),                                                             # T1 service: 2 of 2
                ("N6", 1, "inspection", False, "T2", "active"), ("N7", 1, "inspection", True, "T2", "active"), ("N8", 1, "inspection", True, "T2", "active"),         # T2 inspection: 2 of 3
                ("N9", 1, "service", False, "T2", "active")])                                                                                                       # T2 service: 0 of 1
    p0 = p.copy()
    r = grid.requires_authorisation(p, context=M12)
    pd.testing.assert_frame_equal(p, p0)
    assert r.columns.tolist() == ["team_key", "plan_type", "n_plans", "n_requiring", "share_requiring"]
    got = {(x.team_key, x.plan_type): (int(x.n_plans), int(x.n_requiring), float(x.share_requiring)) for x in r.itertuples(index=False)}
    assert got == {("T1", "inspection"): (3, 1, 0.3333), ("T1", "service"): (2, 2, 1.0), ("T2", "inspection"): (3, 2, 0.6667), ("T2", "service"): (1, 0, 0.0)}, "active plans only; share rounded to four decimals"
    assert list(zip(r.team_key, r.plan_type)) == [("T1", "inspection"), ("T1", "service"), ("T2", "inspection"), ("T2", "service")], "sorted by team and plan type"
    s = grid.requires_authorisation(p, active_status=("suspended", "retired"), context=M12)
    assert {(x.team_key, x.plan_type): (int(x.n_plans), int(x.n_requiring)) for x in s.itertuples(index=False)} == {("T1", "inspection"): (2, 2)}, "the status list is a parameter"
    assert grid.requires_authorisation(p, active_status=("none",), context=M12).empty
    assert int(r["n_plans"].sum()) == int((p["status"] == "active").sum()) == 9 and int(r["n_requiring"].sum()) == int(((p["status"] == "active") & p["requires_electrical_authorisation"]).sum()) == 5, "the groups add up to the active plans"
