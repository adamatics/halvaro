"""Oracles of due_within and inspection_interval_check: hand worked plans around the edges of the rule, then a pandas or python reading of the stored maintenance plans; the functions are never used to compute an expected value."""

import pandas as pd

import halvaro.grid as grid
from halvaro.core import Context

M12 = Context(stage="month12", role="r")

# The rule parameters of the inspection interval as the library states them (no fact id carries them): months by condition class and a multiplier by element type.
RULE_CYCLE = {"A": 120, "B": 84, "C": 54, "D": 32, "E": 26}
RULE_MULT = {"pipe_segment": 1.25, "valve": 1.2, "heat_exchanger_station": 1.0, "cable_section": 1.0, "transformer_station": 0.9, "substation": 0.7, "pump_station": 0.7}


def _plans(rows):
    return pd.DataFrame(rows, columns=["net_key", "plan_no", "plan_type", "next_due", "last_done", "team_key", "status"])


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# due_within
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _due_hand():
    return _plans([("N1", 1, "inspection", "2026-11-30", "2025-01-01", "T1", "active"),            # the day before the interval
                   ("N2", 1, "inspection", "2026-12-01", "2025-01-01", "T1", "active"),            # the first day
                   ("N3", 1, "inspection", "2026-12-15", "2025-01-01", "T1", "active"),
                   ("N4", 1, "inspection", "2026-12-31", "2025-01-01", "T1", "active"),            # the last day (1 December plus 30 days)
                   ("N5", 1, "inspection", "2027-01-01", "2025-01-01", "T1", "active"),            # the day after
                   ("N6", 1, "service", "2026-12-10", "2025-01-01", "T1", "active"),
                   ("N7", 1, "inspection", "2026-12-20", "2025-01-01", "T1", "suspended"),         # not active
                   ("N8", 1, "inspection", "2026-12-05", "2025-01-01", "T2", "active"),
                   ("N9", 1, "inspection", None, "2025-01-01", "T2", "active"),                    # no due date
                   ("N10", 1, "inspection", "2026-12-31", "2025-01-01", "T2", "active")])


def _rows(frame):
    return [(r.team_key, r.plan_type, int(r.n_plans), str(pd.Timestamp(r.first_due).date()), str(pd.Timestamp(r.last_due).date())) for r in frame.itertuples(index=False)]


def test_oracle_due_within_hand_worked_closed_interval():
    """route: a hand worked example of ten plans around the interval 1 to 31 December 2026 (a horizon of 30 days), each plan placed by hand inside or outside."""
    p = _due_hand()
    p0 = p.copy()
    r = grid.due_within(p, "2026-12-01", 30, context=M12)
    assert r.columns.tolist() == ["team_key", "plan_type", "n_plans", "first_due", "last_due"]
    assert _rows(r) == [("T1", "inspection", 3, "2026-12-01", "2026-12-31"), ("T1", "service", 1, "2026-12-10", "2026-12-10"), ("T2", "inspection", 2, "2026-12-05", "2026-12-31")], "both ends of the interval are in; the day before, the day after, the suspended plan and the plan without a date are out"
    pd.testing.assert_frame_equal(p, p0)
    assert _rows(grid.due_within(p, "2026-12-01 15:30", 30, context=M12)) == _rows(r), "the as-of date is a day"
    one = grid.due_within(p, "2026-12-31", 0, context=M12)
    assert _rows(one) == [("T1", "inspection", 1, "2026-12-31", "2026-12-31"), ("T2", "inspection", 1, "2026-12-31", "2026-12-31")], "horizon 0 is the as-of day only"
    assert _rows(grid.due_within(p, "2026-12-01", 29, context=M12)) == [("T1", "inspection", 2, "2026-12-01", "2026-12-15"), ("T1", "service", 1, "2026-12-10", "2026-12-10"), ("T2", "inspection", 1, "2026-12-05", "2026-12-05")], "horizon 29 drops 31 December"
    assert _rows(grid.due_within(p, "2026-11-30", 1, context=M12)) == [("T1", "inspection", 2, "2026-11-30", "2026-12-01")], "an interval that starts the day before"
    assert _rows(grid.due_within(p, "2026-12-01", 30, active_status=("suspended",), context=M12)) == [("T1", "inspection", 1, "2026-12-20", "2026-12-20")]
    assert grid.due_within(p, "2030-01-01", 30, context=M12).empty and grid.due_within(p, "2030-01-01", 30, context=M12).columns.tolist() == ["team_key", "plan_type", "n_plans", "first_due", "last_due"]
    assert int(r["n_plans"].sum()) == 6, "the groups add up to the plans inside the interval: 3 + 1 + 2"



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# inspection_interval_check
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _mp(rows):
    return pd.DataFrame(rows, columns=["net_key", "plan_no", "plan_type", "interval_months", "valid_from"])


def _ge(rows):
    return pd.DataFrame(rows, columns=["net_key", "condition_class", "element_type"])



def test_oracle_inspection_interval_check_hand_worked_rounding_and_unknowns():
    """route: a hand worked example, each expected interval written down (84, 105, 54, 38, 32, 68, 108, 59, 144) with the half cases 32.5 and 67.5, and the unknown class, type and element."""
    ge = _ge([("N01", "A", "substation"),             # 120 * 0.7 = 84
              ("N02", "B", "pipe_segment"),           # 84 * 1.25 = 105
              ("N03", "C", "cable_section"),          # 54
              ("N04", "D", "valve"),                  # 32 * 1.2 = 38.4: 38
              ("N05", "E", "pipe_segment"),           # 26 * 1.25 = 32.5: half to even gives 32
              ("N06", "C", "pipe_segment"),           # 54 * 1.25 = 67.5: half to even gives 68
              ("N07", "A", "transformer_station"),    # 120 * 0.9 = 108
              ("N08", "B", "pump_station"),           # 84 * 0.7 = 58.8: 59
              ("N09", None, "pipe_segment"),          # no class
              ("N10", "B", "mystery"),                # unknown type
              ("N12", "B", "cable_section"),
              ("N13", "A", "valve"),                  # 120 * 1.2 = 144
              ("N14", "B", "cable_section")])         # 84
    mp = _mp([("N14", 2, "condition_inspection", 11, "2023-01-01"), ("N14", 1, "condition_inspection", 12, "2023-01-01"),          # two plans off the rule, the higher number first
              ("N01", 1, "condition_inspection", 84, "2023-01-01"), ("N02", 1, "condition_inspection", 105, "2023-01-01"), ("N03", 1, "condition_inspection", 54, "2023-01-01"),
              ("N04", 1, "condition_inspection", 39, "2023-01-01"),           # 39 against 38
              ("N05", 1, "condition_inspection", 33, "2023-01-01"),           # 33 against 32
              ("N05", 2, "condition_inspection", 32, "2023-01-01"),           # 32 is right
              ("N06", 1, "condition_inspection", 67, "2026-03-01"),           # 67 against 68
              ("N06", 2, "condition_inspection", 68, "2023-01-01"),
              ("N07", 1, "condition_inspection", 108, "2023-01-01"), ("N08", 1, "condition_inspection", 59, "2023-01-01"),
              ("N09", 1, "condition_inspection", 12, "2023-01-01"), ("N10", 1, "condition_inspection", 12, "2023-01-01"), ("N11", 1, "condition_inspection", 12, "2023-01-01"),
              ("N12", 1, "cable_route_check", 3, "2023-01-01"),               # another plan type: not checked
              ("N13", 1, "condition_inspection", 144, "2023-01-01")])
    mp0, ge0 = mp.copy(), ge.copy()
    r = grid.inspection_interval_check(mp, ge, context=M12)
    assert r.columns.tolist() == ["net_key", "plan_no", "element_type", "condition_class", "interval_months", "expected_months", "valid_from"]
    pd.testing.assert_frame_equal(mp, mp0)
    pd.testing.assert_frame_equal(ge, ge0)
    rows = [(x.net_key, int(x.plan_no), None if pd.isna(x.element_type) else x.element_type, None if pd.isna(x.condition_class) else x.condition_class, int(x.interval_months),
             None if pd.isna(x.expected_months) else float(x.expected_months), str(pd.Timestamp(x.valid_from).date())) for x in r.itertuples(index=False)]
    assert rows == [("N04", 1, "valve", "D", 39, 38.0, "2023-01-01"), ("N05", 1, "pipe_segment", "E", 33, 32.0, "2023-01-01"), ("N06", 1, "pipe_segment", "C", 67, 68.0, "2026-03-01"),
                    ("N09", 1, "pipe_segment", None, 12, None, "2023-01-01"), ("N10", 1, "mystery", "B", 12, None, "2023-01-01"), ("N11", 1, None, None, 12, None, "2023-01-01"),
                    ("N14", 1, "cable_section", "B", 12, 84.0, "2023-01-01"), ("N14", 2, "cable_section", "B", 11, 84.0, "2023-01-01")], \
        "the plans off the rule by one month, and the plans of an element without class, with an unknown type or not in the element frame (expected months null); sorted by element and plan number"
    # the rule is a function of its parameters
    cyc, mul = {"A": 10, "B": 20}, {"x": 1.5, "y": 1.0}
    ge2 = _ge([("F1", "A", "x"), ("F2", "B", "y"), ("F3", "B", "x"), ("F4", "C", "x"), ("F5", "A", "z")])
    mp2 = _mp([("F1", 1, "condition_inspection", 15, "2023-01-01"), ("F2", 1, "condition_inspection", 20, "2023-01-01"), ("F3", 1, "condition_inspection", 29, "2023-01-01"),
               ("F4", 1, "condition_inspection", 15, "2023-01-01"), ("F5", 1, "condition_inspection", 15, "2023-01-01"), ("F5", 2, "other_plan", 9, "2023-01-01")])
    r2 = grid.inspection_interval_check(mp2, ge2, cycle_months=cyc, type_multiplier=mul, context=M12)
    assert [(x.net_key, x.interval_months, None if pd.isna(x.expected_months) else float(x.expected_months)) for x in r2.itertuples(index=False)] == [("F3", 29, 30.0), ("F4", 15, None), ("F5", 15, None)], "own cycles and multipliers"
    r3 = grid.inspection_interval_check(mp2, ge2, plan_type="other_plan", cycle_months=cyc, type_multiplier=mul, context=M12)
    assert [(x.net_key, x.plan_no) for x in r3.itertuples(index=False)] == [("F5", 2)], "the plan type is a parameter"
    assert grid.inspection_interval_check(mp2.iloc[:0], ge2, context=M12).empty
