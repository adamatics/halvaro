"""estimate_bridge, estimate_amount_per_metre, overrun_distribution, cause_shares, risk_lessons_summary: synthetic frames, then the baseline against the generator tests (plan oracles O3, O8, O9)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")


def _ev(rows):
    return pd.DataFrame(rows, columns=["prj_key", "estimate_version", "type", "date", "currency", "total_cost"])


def _el(rows):
    return pd.DataFrame(rows, columns=["prj_key", "estimate_version", "cst_key", "amount", "currency"])


CC = pd.DataFrame({"cst_key": ["CST-110", "CST-200", "CST-830"], "category": ["labour", "material", "contingency"]})


def test_bridge_takes_the_latest_version_of_each_type_and_ties_lines_to_the_total():
    ev = _ev([("P1", 1, "tender", "2024-01-01", "EUR", 150), ("P1", 2, "forecast", "2025-01-01", "EUR", 90), ("P1", 3, "forecast", "2025-06-01", "EUR", 300), ("P1", 4, "budget", "2024-02-01", "EUR", 100)])
    el = _el([("P1", 1, "CST-110", 100, "EUR"), ("P1", 1, "CST-200", 50, "EUR"), ("P1", 2, "CST-110", 90, "EUR"), ("P1", 3, "CST-110", 100, "EUR"), ("P1", 3, "CST-200", 200, "EUR"),
              ("P1", 4, "CST-110", 99, "EUR")])
    b = delivery.estimate_bridge(ev, el, CC, full_projects=["P1", "P2"], context=CTX)
    t = b.totals.set_index("type")
    assert t.estimate_version.to_dict() == {"budget": 4, "forecast": 3, "tender": 1}, "version 3 is the latest forecast"
    assert t.line_sum.to_dict() == {"budget": 99.0, "forecast": 300.0, "tender": 150.0} and t.difference.to_dict() == {"budget": -1.0, "forecast": 0.0, "tender": 0.0}
    assert b.lines[b.lines.type == "forecast"].amount.tolist() == [100, 200] and set(b.lines.category) == {"labour", "material"}
    assert sorted(map(tuple, b.missing.values.tolist())) == [("P1", "final"), ("P2", "budget"), ("P2", "final"), ("P2", "forecast"), ("P2", "tender")]
    assert delivery.estimate_bridge(ev, el, CC, context=CTX).missing.empty, "without a list of full projects nothing is flagged missing"


def test_bridge_refuses_unknown_types_cost_codes_and_duplicate_versions():
    ev = _ev([("P1", 1, "tender", "2024-01-01", "EUR", 10)])
    with pytest.raises(FrameError, match="unknown value.*offer"):
        delivery.estimate_bridge(ev.assign(type="offer"), _el([]), CC, context=CTX)
    with pytest.raises(FrameError, match="not in projects.cost_code.*CST-999"):
        delivery.estimate_bridge(ev, _el([("P1", 1, "CST-999", 10, "EUR")]), CC, context=CTX)
    with pytest.raises(FrameError, match="sharing prj_key, estimate_version"):
        delivery.estimate_bridge(pd.concat([ev, ev]), _el([]), CC, context=CTX)
    with pytest.raises(FrameError, match="lacks column"):
        delivery.estimate_bridge(ev.drop(columns="date"), _el([]), CC, context=CTX)


def test_per_metre_null_without_length_replacement_length_and_no_currency_mixing():
    lines = pd.DataFrame({"prj_key": ["P1", "P1", "P2", "P3"], "type": "tender", "cst_key": ["CST-110", "CST-200", "CST-110", "CST-110"], "category": "labour",
                          "currency": ["EUR", "EUR", "DKK", "EUR"], "amount": [1000, 500, 900, 700]})
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "route_length_m": [5000.0, None, 0.0]})
    m = delivery.estimate_amount_per_metre(lines, proj, context=CTX)
    assert m.per_metre.tolist()[:2] == [0.2, 0.1] and m.per_metre.isna().tolist() == [False, False, True, True], "null length and zero length: kept, null per metre"
    assert m.currency.tolist() == ["EUR", "EUR", "DKK", "EUR"], "each row keeps its currency"
    as_built = pd.DataFrame({"prj_key": ["P1"], "route_length_m": [6100.0]})
    assert delivery.estimate_amount_per_metre(lines, proj, route_length=as_built, context=CTX).per_metre.iloc[0] == pytest.approx(1000 / 6100)
    with pytest.raises(FrameError, match="sharing prj_key"):
        delivery.estimate_amount_per_metre(lines, pd.concat([proj, proj]), context=CTX)


def test_overrun_distribution_quartiles_legacy_count_cost_overrun_and_currency_clash():
    ov = pd.DataFrame({"prj_key": [f"P{i}" for i in range(1, 7)], "overrun": [0.0, 0.1, 0.2, 0.3, 0.4, 9.9], "basis": ["actual"] * 5 + ["forecast"]})
    proj = pd.DataFrame({"prj_key": [f"P{i}" for i in range(1, 7)], "final_cost": [110.0, 120.0, None, 90.0, 100.0, None], "legacy": [True, False, False, False, True, False], "currency": "EUR"})
    totals = pd.DataFrame({"prj_key": [f"P{i}" for i in range(1, 7)], "type": "tender", "total_cost": [100.0, 100.0, 100.0, 100.0, 0.0, 100.0], "currency": "EUR"})
    d = delivery.overrun_distribution(ov, proj, totals, context=CTX).set_index("measure")
    s = d.loc["schedule"]
    assert (s.n, s.n_legacy, s["min"], s.q25, s["median"], s.q75, s["max"]) == (5, 2, 0.0, 0.1, 0.2, 0.3, 0.4) and s["mean"] == pytest.approx(0.2), "the forecast row is not an overrun of a finished project"
    c = d.loc["cost"]
    assert c.n == 3 and c["min"] == pytest.approx(-0.1) and c["max"] == pytest.approx(0.2) and c.n_legacy == 1, "no final cost and a zero tender are left out of the cost overrun"
    lim = delivery.overrun_distribution(ov, proj, totals, projects=["P1", "P2"], context=CTX).set_index("measure")
    assert lim.loc["schedule", "n"] == 2 and lim.loc["cost", "n"] == 2
    assert list(delivery.overrun_distribution(ov, proj, context=CTX).measure) == ["schedule"]
    with pytest.raises(FrameError, match="another currency"):
        delivery.overrun_distribution(ov, proj, totals.assign(currency="DKK"), context=CTX)
    assert delivery.overrun_distribution(ov.iloc[:0], proj, context=CTX).n.tolist() == [0]


def _de(rows):
    return pd.DataFrame(rows, columns=["prj_key", "cause_code", "responsible_party", "days", "mtg_key"])


def test_cause_shares_two_views_full_projects_with_a_meeting_and_the_set():
    de = _de([("P1", "ground", "customer", 30, "MTG-1"), ("P1", "weather", "force_majeure", 10, None), ("P2", "ground", "customer", 20, "MTG-2"), ("P3", "supplier", "supplier", 40, "MTG-3")])
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "data_depth": ["full", "full", "summary"]})
    s = delivery.cause_shares(de, proj, context=CTX)
    a, f = s[s.view == "all_events"], s[s.view == "full_linked"]
    assert a.days.sum() == 100 and a.iloc[0].cause_code == "ground" and a.iloc[0].days == 50 and a.iloc[0].share == 0.5 and a.iloc[0].events == 2
    assert f.days.sum() == 50 and f.cause_code.tolist() == ["ground"] and f.share.tolist() == [1.0], "legacy and unlinked events are not in the second view"
    only = delivery.cause_shares(de, proj, projects=["P1"], context=CTX)
    assert only[only.view == "all_events"].days.sum() == 40
    with pytest.raises(FrameError, match="not in the project frame"):
        delivery.cause_shares(de.assign(prj_key="P9"), proj, context=CTX)
    with pytest.raises(FrameError, match="numeric without nulls"):
        delivery.cause_shares(de.assign(days=None), proj, context=CTX)


def test_risk_and_lesson_counts_and_the_match_of_occurred_risks_to_events():
    rk = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P2"], "risk_no": [1, 2, 3, 1], "cause_code": ["ground", "ground", "weather", "ground"], "status": ["occurred", "occurred", "closed", "occurred"],
                       "delay_seq": [1, 2, None, 1]})
    ls = pd.DataFrame({"prj_key": ["P1", "P1", "P2"], "category": ["ground", "weather", "ground"], "delay_seq": [1, None, 1]})
    de = pd.DataFrame({"prj_key": ["P1", "P1", "P2"], "seq": [1, 2, 1], "cause_code": ["ground", "weather", "ground"]})
    r = delivery.risk_lessons_summary(rk, ls, de, context=CTX)
    assert r.risk_causes.values.tolist() == [["ground", 3], ["weather", 1]] and r.lesson_categories.values.tolist() == [["ground", 2]], "a lesson without a delay_seq does not count"
    assert r.occurred[["prj_key", "risk_no", "event_cause", "matches"]].values.tolist() == [["P1", 1, "ground", True], ["P1", 2, "weather", False], ["P2", 1, "ground", True]]
    miss = delivery.risk_lessons_summary(rk, ls, de.iloc[:1], context=CTX).occurred
    assert miss.matches.tolist() == [True, False, False] and miss.event_cause.isna().tolist() == [False, True, True], "an event that is not there is a mismatch, not a drop"
    assert delivery.risk_lessons_summary(rk, ls, de, projects=["P2"], context=CTX).risk_causes.values.tolist() == [["ground", 1]]


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["estimate_bridge", "estimate_amount_per_metre", "overrun_distribution", "cause_shares", "risk_lessons_summary"]
    for n in names:
        m = reg[f"halvaro.delivery.estimating.{n}"]
        assert m.oracle.startswith("py:tests/") and m.parameters[-1] == "context" and all(s.startswith("projects.") for s in m.sources)
    assert registry.check() == [] and {f"halvaro.delivery.estimating.{n}" for n in names} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    with pytest.raises(StageRefusal, match="projects"):
        delivery.cause_shares(_de([]), pd.DataFrame({"prj_key": [], "data_depth": []}), context=Context(stage="month3", role="r"))


# the baseline

@pytest.mark.release
def test_bridge_ties_to_the_generator_estimates_and_the_story_margins(load):
    p, ev, el, cc = load("projects", "project"), load("projects", "estimate_version"), load("projects", "estimate_line"), load("projects", "cost_code")
    full = p[p.data_depth == "full"]
    b = delivery.estimate_bridge(ev, el, cc, full_projects=full.prj_key, context=CTX)
    assert b.totals.difference.abs().max() <= 40, "test_estimates: line amounts sum to total_cost within 40"
    miss = b.missing
    assert not set(miss.type) & {"tender", "budget"}, "tender and budget exist for every full project"
    completed = set(full[pd.to_datetime(full.actual_end) < pd.Timestamp("2026-11-30")].prj_key)
    assert set(miss[miss.type == "final"].prj_key).isdisjoint(completed), "final exists for completed full projects"
    fin = b.totals[b.totals.type == "final"].merge(p[["prj_key", "final_cost"]], on="prj_key")
    assert ((fin.total_cost - fin.final_cost).abs() / fin.final_cost).max() < 1e-3
    t = b.totals[b.totals.prj_key == "PRJ-000001"].set_index("type")
    value = float(p.set_index("prj_key").loc["PRJ-000001", "contract_value"])
    assert 1 - t.loc["tender", "total_cost"] / value == pytest.approx(0.11, abs=0.005) and 1 - t.loc["forecast", "total_cost"] / value == pytest.approx(-0.03, abs=0.002)
    pm = delivery.estimate_amount_per_metre(b.lines, p, context=CTX)
    story = pm[(pm.prj_key == "PRJ-000001") & (pm.type == "tender")]
    assert story.route_length_m.eq(5200.0).all() and story.per_metre.notna().all()
    legacy_keys = set(p[p.legacy].prj_key)
    assert not set(b.lines.prj_key) & legacy_keys, "legacy summary projects have no estimate lines"


@pytest.mark.release
def test_cell_distribution_and_ground_shares_equal_the_calibration(load):
    p, ev, el, cc, de = (load("projects", t) for t in ("project", "estimate_version", "estimate_line", "cost_code", "delay_event"))
    cell = p[(p.country == "DE") & (p.type == "dh_network") & (p.soil_class == "clay") & (pd.to_datetime(p.actual_end) < pd.Timestamp("2026-11-30")) & (p.prj_key != "PRJ-000001")]
    pl, st, ae = (pd.to_datetime(cell[c]) for c in ("planned_end", "start", "actual_end"))
    ov = pd.DataFrame({"prj_key": cell.prj_key, "overrun": ((ae - pl).dt.days / ((pl - st).dt.days + 1)).to_numpy(), "basis": "actual"})
    b = delivery.estimate_bridge(ev, el, cc, context=CTX)
    d = delivery.overrun_distribution(ov, p, b.totals, projects=cell.prj_key, context=CTX).set_index("measure")
    assert d.loc["schedule", "n"] >= 15 and abs(d.loc["schedule", "mean"] - 0.22) < 0.01 and d.loc["schedule", "n_legacy"] > 0
    assert d.loc["cost", "n"] == len(cell[(cell.data_depth == "full") & cell.final_cost.notna()]) and d.loc["cost", "n_legacy"] == 0, "cost overrun exists for full projects only"
    s = delivery.cause_shares(de, p, projects=cell.prj_key, context=CTX)
    a = s[s.view == "all_events"]
    assert abs(a[a.cause_code == "ground_conditions"].days.sum() / a.days.sum() - 0.40) < 0.015, "test_cell_calibration: ground share of all event days"
    f = s[s.view == "full_linked"]
    by = f.groupby("cause_code").days.sum()
    assert by.idxmax() == "ground_conditions" and 0.28 <= by["ground_conditions"] / by.sum() <= 0.55, "O9"


@pytest.mark.release
def test_risks_and_lessons_of_the_cell_are_about_ground_and_every_occurred_risk_matches(load):
    p, de = load("projects", "project"), load("projects", "delay_event")
    cell = p[(p.country == "DE") & (p.type == "dh_network") & (p.soil_class == "clay") & (pd.to_datetime(p.actual_end) < pd.Timestamp("2026-11-30")) & (p.data_depth == "full") & (p.prj_key != "PRJ-000001")]
    r = delivery.risk_lessons_summary(load("projects", "risk"), load("projects", "lesson_learned"), de, projects=cell.prj_key, context=CTX)
    assert r.risk_causes.iloc[0].cause_code == "ground_conditions" and r.lesson_categories.iloc[0].category == "ground_conditions"
    everything = delivery.risk_lessons_summary(load("projects", "risk"), load("projects", "lesson_learned"), de, context=CTX)
    assert len(everything.occurred) > 100 and everything.occurred.matches.all()
    assert len(everything.lessons) > 100 and everything.lessons.matches.all(), "every lesson with a delay_seq has the cause of its event"


# review fixes

def test_bridge_as_of_orphan_lines_line_currency_and_only_lines_of_the_chosen_version():
    ev = _ev([("P1", 1, "tender", "2024-01-01", "EUR", 150), ("P1", 2, "forecast", "2025-11-05", "EUR", 90), ("P1", 3, "forecast", "2025-12-18", "EUR", 300), ("P1", 4, "forecast", "2026-11-30", "EUR", 500)])
    el = _el([("P1", 1, "CST-110", 150, "EUR"), ("P1", 2, "CST-110", 90, "EUR"), ("P1", 3, "CST-110", 300, "EUR"), ("P1", 4, "CST-110", 500, "EUR")])
    now = delivery.estimate_bridge(ev, el, CC, context=CTX)
    assert now.totals.set_index("type").estimate_version.to_dict() == {"forecast": 4, "tender": 1} and len(now.lines) == 2, "lines of superseded versions are not in the bridge"
    then = delivery.estimate_bridge(ev, el, CC, as_of="2025-12-18", context=CTX)
    assert then.totals.set_index("type").loc["forecast", ["estimate_version", "total_cost"]].tolist() == [3, 300], "the forecast valid on the date, dated on the date counts"
    assert delivery.estimate_bridge(ev, el, CC, as_of="2025-12-17", context=CTX).totals.set_index("type").loc["forecast", "estimate_version"] == 2
    assert "forecast" not in set(delivery.estimate_bridge(ev, el, CC, as_of="2025-01-01", context=CTX).totals.type)
    with pytest.raises(FrameError, match="version that is not in projects.estimate_version"):
        delivery.estimate_bridge(ev, pd.concat([el, _el([("P1", 9, "CST-110", 1, "EUR")])]), CC, context=CTX)
    with pytest.raises(FrameError, match="in DKK, its version in EUR"):
        delivery.estimate_bridge(ev, el.assign(currency="DKK"), CC, context=CTX)
    with pytest.raises(FrameError, match="amount must be numeric"):
        delivery.estimate_bridge(ev, el.assign(amount="1"), CC, context=CTX)
    with pytest.raises(FrameError, match="type must be text"):
        delivery.estimate_bridge(ev.assign(type=None), el, CC, context=CTX)
    assert delivery.estimate_bridge(ev, el, CC, full_projects="P1", context=CTX).missing.prj_key.unique().tolist() == ["P1"], "a single project key is one project, not its characters"


def test_per_metre_refuses_lines_of_unknown_projects_and_infinite_lengths():
    lines = pd.DataFrame({"prj_key": ["P1", "P9"], "type": "tender", "cst_key": "CST-110", "category": "labour", "currency": "EUR", "amount": [10.0, 5.0]})
    with pytest.raises(FrameError, match="not in the project frame.*P9"):
        delivery.estimate_amount_per_metre(lines, pd.DataFrame({"prj_key": ["P1"], "route_length_m": [100.0]}), context=CTX)
    m = delivery.estimate_amount_per_metre(lines.iloc[:1], pd.DataFrame({"prj_key": ["P1"], "route_length_m": [np.inf]}), context=CTX)
    assert m.per_metre.isna().all()


def test_overrun_counts_legacy_among_values_filters_before_the_currency_check_and_refuses_duplicates():
    ov = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5"], "overrun": [0.1, 0.2, 0.3, np.nan, np.nan], "basis": "actual"})
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4", "P5"], "final_cost": [110.0, 120.0, 130.0, 140.0, 150.0], "legacy": [True, False, False, True, True], "currency": ["EUR", "EUR", "EUR", "DKK", "EUR"]})
    totals = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4"], "type": "tender", "total_cost": 100.0, "currency": ["EUR", "EUR", "EUR", "EUR"]})
    d = delivery.overrun_distribution(ov, proj, totals, projects=["P1", "P2", "P3"], context=CTX).set_index("measure")
    assert (d.loc["schedule", "n"], d.loc["schedule", "n_legacy"]) == (3, 1), "legacy projects without a value are not counted"
    with pytest.raises(FrameError, match="another currency"):
        delivery.overrun_distribution(ov, proj, totals, context=CTX)
    with pytest.raises(FrameError, match="more than one actual row"):
        delivery.overrun_distribution(pd.concat([ov, ov.iloc[:1]]), proj, context=CTX)
    with pytest.raises(FrameError, match="more than one tender row"):
        delivery.overrun_distribution(ov, proj, pd.concat([totals, totals.iloc[:1]]), context=CTX)
    with pytest.raises(FrameError, match="overrun column must be numeric"):
        delivery.overrun_distribution(ov.assign(overrun="x"), proj, context=CTX)
    assert delivery.overrun_distribution(ov, proj, projects="P1", context=CTX).set_index("measure").loc["schedule", "n"] == 1, "one key given as text is one project"


def test_cause_shares_refuse_null_groups_and_give_the_share_of_the_whole_cause():
    de = _de([("P1", "ground", "customer", 30, "M1"), ("P1", "ground", "shared", 10, "M1"), ("P1", "weather", "force_majeure", 60, "M1")])
    proj = pd.DataFrame({"prj_key": ["P1"], "data_depth": ["full"]})
    s = delivery.cause_shares(de, proj, context=CTX)
    a = s[s.view == "all_events"].set_index(["cause_code", "responsible_party"])
    assert a.loc[("ground", "customer"), "share"] == 0.3 and a.loc[("ground", "customer"), "cause_share"] == 0.4 and a.loc[("ground", "shared"), "cause_share"] == 0.4
    with pytest.raises(FrameError, match="null cause_code"):
        delivery.cause_shares(pd.concat([de, _de([("P1", None, "x", 5, "M")])]), proj, context=CTX)
    with pytest.raises(FrameError, match="null responsible_party"):
        delivery.cause_shares(pd.concat([de, _de([("P1", "ground", None, 5, "M")])]), proj, context=CTX)


def test_lessons_are_matched_to_the_cause_of_their_event_and_bad_delay_seq_is_refused():
    rk = pd.DataFrame({"prj_key": ["P1"], "risk_no": [1], "cause_code": ["ground"], "status": ["occurred"], "delay_seq": [1]})
    ls = pd.DataFrame({"prj_key": ["P1", "P1", "P1"], "category": ["ground", "weather", "ground"], "delay_seq": [1, 1, 99]})
    de = pd.DataFrame({"prj_key": ["P1"], "seq": [1], "cause_code": ["ground"]})
    r = delivery.risk_lessons_summary(rk, ls, de, context=CTX)
    got = r.lessons.sort_values(["delay_seq", "category"])[["delay_seq", "category", "matches"]].values.tolist()
    assert got == [[1, "ground", True], [1, "weather", False], [99, "ground", False]], "a delay_seq without an event does not match"
    with pytest.raises(FrameError, match="whole numbers"):
        delivery.risk_lessons_summary(rk.assign(delay_seq=1.5), ls, de, context=CTX)
    with pytest.raises(FrameError, match="cause_code has nulls"):
        delivery.risk_lessons_summary(rk.assign(cause_code=None), ls, de, context=CTX)


# second review

def test_bridge_as_of_is_validated_like_the_sibling_functions_and_is_inclusive_of_the_day():
    ev = _ev([("P1", 1, "tender", "2024-01-01", "EUR", 10), ("P1", 2, "forecast", "2025-12-18T14:00", "EUR", 20), ("P1", 3, "forecast", "2026-01-01", "EUR", 30)])
    el = _el([])
    for bad in (20251218, 2025.5, True, np.int64(5)):
        with pytest.raises(FrameError, match="is a number, not a date"):
            delivery.estimate_bridge(ev, el, CC, as_of=bad, context=CTX)
    with pytest.raises(FrameError, match="time zone"):
        delivery.estimate_bridge(ev, el, CC, as_of=pd.Timestamp("2025-12-18", tz="UTC"), context=CTX)
    with pytest.raises(FrameError, match="not a date"):
        delivery.estimate_bridge(ev, el, CC, as_of="soon", context=CTX)
    with pytest.raises(FrameError, match="not a date"):
        delivery.estimate_bridge(ev, el, CC, as_of=pd.NaT, context=CTX)
    with pytest.raises(FrameError, match="date has a time zone"):
        delivery.estimate_bridge(ev.assign(date=pd.to_datetime(["2024-01-01", "2025-12-18", "2026-01-01"]).tz_localize("UTC")), el, CC, as_of="2025-12-18", context=CTX)
    with pytest.raises(FrameError, match="not a date"):
        delivery.estimate_bridge(ev.assign(date=["2024-01-01", "x", "2026-01-01"]), el, CC, as_of="2025-12-18", context=CTX)
    with pytest.raises(FrameError, match="date has nulls"):
        delivery.estimate_bridge(ev.assign(date=[None, "2025-12-18", "2026-01-01"]), el, CC, as_of="2025-12-18", context=CTX)
    for day in ("2025-12-18", pd.Timestamp("2025-12-18"), pd.Timestamp("2025-12-18 23:59"), pd.Timestamp("2025-12-18").date()):
        t = delivery.estimate_bridge(ev, el, CC, as_of=day, context=CTX).totals.set_index("type")
        assert t.loc["forecast", "estimate_version"] == 2, "a version dated 2025-12-18 14:00 exists on the day 2025-12-18"
    assert "forecast" not in set(delivery.estimate_bridge(ev, el, CC, as_of="2025-12-17", context=CTX).totals.type)


def test_bridge_version_without_lines_has_a_zero_line_sum_and_the_difference_is_minus_its_total():
    t = delivery.estimate_bridge(_ev([("P1", 1, "tender", "2024-01-01", "EUR", 150)]), _el([]), CC, context=CTX).totals
    assert t.line_sum.tolist() == [0.0] and t.difference.tolist() == [-150.0]


def test_overrun_n_legacy_ignores_legacy_projects_without_a_value_in_the_project_frame_itself():
    ov = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "overrun": [0.1, np.nan, np.nan], "basis": "actual"})
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3"], "final_cost": [1.0, 1.0, 1.0], "legacy": [True, True, False], "currency": "EUR"})
    s = delivery.overrun_distribution(ov, proj, context=CTX).set_index("measure").loc["schedule"]
    assert (s.n, s.n_legacy) == (1, 1), "P2 is legacy but has no overrun: not counted"


def test_overrun_distribution_refuses_projects_that_are_not_in_the_project_frame_like_cause_shares():
    ov = pd.DataFrame({"prj_key": ["P1", "P9", "P8"], "overrun": [0.1, 0.2, 0.3], "basis": "actual"})
    proj = pd.DataFrame({"prj_key": ["P1"], "final_cost": [1.0], "legacy": [False], "currency": "EUR"})
    with pytest.raises(FrameError, match=r"2 projects.*not in the project frame.*P8"):
        delivery.overrun_distribution(ov, proj, context=CTX)
    d = delivery.overrun_distribution(ov, proj, projects=["P1"], context=CTX)
    assert d.set_index("measure").loc["schedule", "n"] == 1, "unknown projects outside the chosen set do not matter"
    ok = delivery.overrun_distribution(ov.assign(basis=["actual", "forecast", "forecast"]), proj, context=CTX)
    assert ok.set_index("measure").loc["schedule", "n"] == 1, "nor do rows of another basis"


def test_per_metre_says_where_the_length_came_from():
    lines = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4"], "type": "tender", "cst_key": "CST-110", "category": "labour", "currency": "EUR", "amount": 100.0})
    proj = pd.DataFrame({"prj_key": ["P1", "P2", "P3", "P4"], "route_length_m": [1000.0, 2000.0, 4000.0, np.nan]})
    assert delivery.estimate_amount_per_metre(lines, proj, context=CTX).length_source.tolist() == ["planned"] * 4
    built = pd.DataFrame({"prj_key": ["P1", "P2", "P4"], "route_length_m": [1100.0, np.nan, 500.0]})
    m = delivery.estimate_amount_per_metre(lines, proj, route_length=built, context=CTX)
    assert m.length_source.tolist() == ["as_built", "planned", "planned", "as_built"], "a null as-built length falls back to the planned one and says so"
    assert m.route_length_m.tolist() == [1100.0, 2000.0, 4000.0, 500.0]
    assert list(m.columns) == ["prj_key", "type", "cst_key", "category", "currency", "amount", "route_length_m", "length_source", "per_metre"]
    assert delivery.estimate_amount_per_metre(lines.iloc[:0], proj, context=CTX).length_source.empty


def test_bridge_missing_says_which_absences_are_expected_by_status():
    ev = _ev([("PL", 1, "tender", "2024-01-01", "EUR", 1), ("PL", 2, "budget", "2024-01-01", "EUR", 1)])
    st = pd.Series({"PL": "planned", "AC": "active", "CO": "completed", "XX": "unknown_to_us"}).drop("XX")
    b = delivery.estimate_bridge(ev, _el([]), CC, full_projects=["PL", "AC", "CO", "XX"], status=st, context=CTX)
    got = {(r.prj_key, r.type): r.expected for r in b.missing.itertuples()}
    assert got == {("PL", "forecast"): True, ("PL", "final"): True,
                   ("AC", "tender"): False, ("AC", "budget"): False, ("AC", "forecast"): True, ("AC", "final"): True,
                   ("CO", "tender"): False, ("CO", "budget"): False, ("CO", "forecast"): True, ("CO", "final"): False,
                   ("XX", "tender"): False, ("XX", "budget"): False, ("XX", "forecast"): True, ("XX", "final"): False}
    assert b.missing.expected.dtype == bool
    assert list(delivery.estimate_bridge(ev, _el([]), CC, full_projects=["PL"], context=CTX).missing.columns) == ["prj_key", "type"], "without a status nothing is judged"
    assert list(delivery.estimate_bridge(ev, _el([]), CC, status=st, context=CTX).missing.columns) == ["prj_key", "type", "expected"]
    with pytest.raises(FrameError, match="unknown value.*done"):
        delivery.estimate_bridge(ev, _el([]), CC, full_projects=["PL"], status=pd.Series({"PL": "done"}), context=CTX)
    with pytest.raises(FrameError, match="must be a Series"):
        delivery.estimate_bridge(ev, _el([]), CC, full_projects=["PL"], status={"PL": "planned"}, context=CTX)
    with pytest.raises(FrameError, match="more than one value"):
        delivery.estimate_bridge(ev, _el([]), CC, full_projects=["PL"], status=pd.Series(["planned", "active"], index=["PL", "PL"]), context=CTX)


@pytest.mark.release
def test_baseline_absences_follow_the_status_and_forecast_is_not_tied_to_it(load):
    p, ev, el, cc = load("projects", "project"), load("projects", "estimate_version"), load("projects", "estimate_line"), load("projects", "cost_code")
    full = p[p.data_depth == "full"]
    b = delivery.estimate_bridge(ev, el, cc, full_projects=full.prj_key, status=full.set_index("prj_key").status, context=CTX)
    assert b.missing.expected.all(), "in the baseline every missing version is expected by status"
    f = b.missing[b.missing.type == "forecast"].merge(full[["prj_key", "status"]], on="prj_key")
    assert set(f.status) == {"completed", "planned"} and (f.status == "completed").any(), "completed projects without a forecast exist"


# third review: the guards that earlier tests did not pin down

def test_overrun_cost_with_a_project_without_currency_is_not_a_currency_clash():
    ov = pd.DataFrame({"prj_key": ["P1", "P2"], "overrun": [0.1, 0.2], "basis": "actual"})
    proj = pd.DataFrame({"prj_key": ["P1", "P2"], "final_cost": [110.0, 120.0], "legacy": False, "currency": ["EUR", None]})
    totals = pd.DataFrame({"prj_key": ["P1", "P2"], "type": "tender", "total_cost": 100.0, "currency": "EUR"})
    d = delivery.overrun_distribution(ov, proj, totals, context=CTX).set_index("measure")
    assert d.loc["cost", "n"] == 2 and d.loc["cost", "max"] == pytest.approx(0.2), "a project with no currency is taken as in the tender currency"
    with pytest.raises(FrameError, match="another currency"):
        delivery.overrun_distribution(ov, proj.assign(currency=["EUR", "DKK"]), totals, context=CTX)


def test_bridge_refuses_a_cost_code_without_category_even_when_no_line_uses_it():
    ev = _ev([("P1", 1, "tender", "2024-01-01", "EUR", 10)])
    el = _el([("P1", 1, "CST-110", 10, "EUR")])
    cc = pd.concat([CC, pd.DataFrame({"cst_key": ["CST-999"], "category": [None]})], ignore_index=True)
    assert len(delivery.estimate_bridge(ev, el, CC, context=CTX).lines) == 1
    with pytest.raises(FrameError, match="category has nulls"):
        delivery.estimate_bridge(ev, el, cc, context=CTX)
