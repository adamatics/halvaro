"""profile_rules, comparable_set, variants_table, comparable_coverage: boundaries on synthetic frames, then the baseline against the generator (plan oracles O1, O6, O7)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")
D = dt.date
NOW = D(2026, 11, 30)
COLS = ["prj_key", "country", "type", "soil_class", "route_length_m", "legacy", "data_depth", "start", "actual_end"]


def _p(rows):
    return pd.DataFrame(rows, columns=COLS)


def _de(key, route=5000.0, end=D(2020, 1, 1), soil="clay", country="DE", type_="dh_network", legacy=False, start=D(2018, 1, 1)):
    return (key, country, type_, soil, route, legacy, "summary" if legacy else "full", start, end)


def _keys(frame, profile="de_clay_window", **kw):
    return list(delivery.comparable_set(frame, profile, as_of=NOW, context=CTX, **kw).frame.prj_key)


def test_de_clay_window_boundaries_are_inclusive_and_status_comes_from_the_dates():
    p = _p([_de("PRJ-000001", 4000.0), _de("PRJ-000002", 7500.0), _de("PRJ-000003", 3999.9), _de("PRJ-000004", 7500.1),
            _de("PRJ-000005", end=None),                                  # active: not completed
            _de("PRJ-000006", end=NOW),                                   # ends on the date: still active
            _de("PRJ-000007", end=D(2026, 11, 29)),                       # ended the day before: completed
            _de("PRJ-000008", soil="rock"), _de("PRJ-000009", country="DK"), _de("PRJ-000010", type_="substation")])
    assert _keys(p) == ["PRJ-000001", "PRJ-000002", "PRJ-000007"]


def test_null_route_length_is_dropped_by_a_window_and_kept_by_the_cell_and_dropped_when_required():
    p = _p([_de("PRJ-000001", None), _de("PRJ-000002", 5000.0)])
    r = delivery.comparable_set(p, "de_clay_window", as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000002"] and r.dropped == {"no_route_length": 1}
    c = delivery.comparable_set(p, "cell_de_dh_clay", as_of=NOW, context=CTX)
    assert list(c.frame.prj_key) == ["PRJ-000001", "PRJ-000002"] and c.frame.route_known.tolist() == [False, True] and c.dropped == {}
    s = delivery.comparable_set(p, "cell_de_dh_clay", require_route_length=True, as_of=NOW, context=CTX)
    assert list(s.frame.prj_key) == ["PRJ-000002"] and s.dropped == {"no_route_length": 1} and s.rule["require_route_length"] is True


def test_cell_excludes_the_project_under_review_and_counts_it():
    p = _p([_de("PRJ-000001"), _de("PRJ-000002"), _de("PRJ-000003")])
    r = delivery.comparable_set(p, "cell_de_dh_clay", exclude=["PRJ-000002"], as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000001", "PRJ-000003"] and r.dropped == {"excluded": 1}
    assert list(delivery.comparable_set(p, "cell_de_dh_clay", exclude="PRJ-000001", as_of=NOW, context=CTX).frame.prj_key) == ["PRJ-000002", "PRJ-000003"]


def test_dk_dh_recent_start_and_end_windows_and_legacy_is_flagged_not_dropped():
    p = _p([_de("PRJ-000001", country="DK", soil="sand", start=D(2023, 1, 1), end=D(2024, 1, 1)),          # both on the boundary: in
            _de("PRJ-000002", country="DK", soil="sand", start=D(2022, 12, 31), end=D(2024, 6, 1)),        # starts a day early: out
            _de("PRJ-000003", country="DK", soil="sand", start=D(2023, 3, 1), end=D(2023, 12, 31)),        # ends a day early: out
            _de("PRJ-000004", country="DK", soil="sand", start=D(2024, 1, 1), end=D(2025, 1, 1), legacy=True)])
    r = delivery.comparable_set(p, "dk_dh_recent", as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000001", "PRJ-000004"] and r.frame.legacy.tolist() == [False, True]
    assert r.dropped == {"start_before_window": 1, "end_before_window": 1}


def test_overrides_a_mapping_as_profile_and_bad_rules():
    p = _p([_de("PRJ-000001", 5000.0), _de("PRJ-000002", 6000.0)])
    assert _keys(p, overrides={"route_max_m": 5500}) == ["PRJ-000001"]
    assert _keys(p, {"country": "DE", "route_min_m": 5500, "route_max_m": 9000}) == ["PRJ-000002"]
    with pytest.raises(FrameError, match="unknown comparable profile"):
        _keys(p, "nope")
    with pytest.raises(FrameError, match="unknown filter field.*colour"):
        _keys(p, overrides={"colour": "red"})
    with pytest.raises(FrameError, match="route_min_m is above route_max_m"):
        _keys(p, {"route_min_m": 9, "route_max_m": 1})
    with pytest.raises(FrameError, match="lacks column.*soil_class"):
        delivery.comparable_set(p.drop(columns="soil_class"), context=CTX)


def test_the_input_is_not_changed_and_the_default_date_is_the_release_date():
    p = _p([_de("PRJ-000001", end=D(2026, 11, 29)), _de("PRJ-000002", end=NOW)])
    before = p.copy(deep=True)
    assert list(delivery.comparable_set(p, context=CTX).frame.prj_key) == ["PRJ-000001"]
    pd.testing.assert_frame_equal(p, before)


def test_profile_rules_table():
    t = delivery.profile_rules(context=CTX).set_index("profile")
    assert list(t.index) == ["de_clay_window", "cell_de_dh_clay", "dk_dh_recent"] and (t.rule_status == "proposed").all()
    assert t.loc["de_clay_window", "route_min_m"] == 4000 and t.loc["de_clay_window", "route_max_m"] == 7500 and pd.isna(t.loc["cell_de_dh_clay", "route_min_m"])
    assert not t.require_route_length.any()


def test_variants_default_first_counts_legacy_share_and_median_with_missing():
    p = _p([_de("PRJ-000001", 5000.0, legacy=True), _de("PRJ-000002", 6000.0), _de("PRJ-000003", 9000.0), _de("PRJ-000004", None)])
    metric = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000002", "PRJ-000003"], "value": [80.0, 100.0, 50.0]})
    t = delivery.variants_table(p, {"widened": {"country": "DE", "route_max_m": 10000}, "de_clay_window": {"country": "DE", "route_min_m": 4000, "route_max_m": 7500}},
                                metric=metric, as_of=NOW, context=CTX).set_index("rule")
    assert list(t.index) == ["de_clay_window", "widened"], "the default profile comes first"
    assert t.loc["de_clay_window", ["n", "legacy_n", "metric_n", "metric_missing"]].tolist() == [2, 1, 2, 0] and t.loc["de_clay_window", "legacy_share"] == 0.5
    assert t.loc["de_clay_window", "metric_median"] == 90.0
    assert t.loc["widened", "n"] == 3 and t.loc["widened", "metric_median"] == 80.0
    assert list(delivery.variants_table(p, as_of=NOW, context=CTX).rule) == ["de_clay_window", "cell_de_dh_clay", "dk_dh_recent"]
    only = delivery.variants_table(p, {"a": {"country": "DE"}}, as_of=NOW, context=CTX)
    assert list(only.rule) == ["de_clay_window", "a"], "the default is added when the caller lists only overrides"
    with pytest.raises(FrameError, match="more than one row"):
        delivery.variants_table(p, metric=pd.concat([metric, metric]), as_of=NOW, context=CTX)


def test_coverage_flags_what_data_each_project_has():
    comp = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000002", "PRJ-000003"]})
    proj = pd.DataFrame({"prj_key": comp.prj_key, "final_cost": [1.0, None, 3.0], "route_length_m": [5000.0, 5000.0, None]})
    est = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000001", "PRJ-000002"], "type": ["tender", "final", "tender"]})
    roles = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000003"], "basis": ["time_entries", "roster"]})
    c = delivery.comparable_coverage(comp, proj, est, roles, ["PRJ-000001"], context=CTX).set_index("prj_key")
    assert c.loc["PRJ-000001"].tolist() == [True, True, True, True, True, True, False]
    assert c.loc["PRJ-000002"].tolist() == [True, False, False, True, False, False, False]
    assert c.loc["PRJ-000003"].tolist() == [False, False, True, False, False, True, True], "roster only: no time entries"
    with pytest.raises(FrameError, match="not in the project frame.*PRJ-000009"):
        delivery.comparable_coverage(pd.DataFrame({"prj_key": ["PRJ-000009"]}), proj, est, roles, [], context=CTX)


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["profile_rules", "comparable_set", "variants_table", "comparable_coverage"]
    for n in names:
        m = reg[f"halvaro.delivery.comparables.{n}"]
        assert m.oracle.startswith("py:") and m.parameters[-1] == "context" and all(s.startswith("projects.") for s in m.sources)
    assert registry.check() == [] and {f"halvaro.delivery.comparables.{n}" for n in names} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    with pytest.raises(StageRefusal, match="projects"):
        delivery.profile_rules(context=Context(stage="month3", role="r"))


# the baseline


@pytest.mark.release
def test_coverage_legacy_projects_have_no_estimates_or_time_entries(load, release_dir):
    p = load("projects", "project")
    comp = delivery.comparable_set(p, "cell_de_dh_clay", as_of=NOW, context=CTX).frame
    te = pd.read_parquet(release_dir / "projects" / "parquet" / "time_entry.parquet", columns=["prj_key"])["prj_key"].unique()
    cov = delivery.comparable_coverage(comp, p, load("projects", "estimate_version"), load("projects", "project_role"), te, context=CTX)
    legacy = cov.merge(comp[["prj_key", "legacy"]], on="prj_key").query("legacy")
    full = cov.merge(comp[["prj_key", "legacy"]], on="prj_key").query("not legacy")
    assert len(legacy) and not legacy[["has_estimate", "has_time_entries"]].any().any(), "test_legacy_projects_are_summary_only"
    assert legacy.has_roster.all() and legacy.roster_only.all() and legacy.has_final_cost.all()
    assert len(full) and full.has_estimate.all() and full.has_time_entries.all() and not full.roster_only.any()


# review fixes

def test_dropped_counts_add_up_when_both_ends_of_the_window_drop_projects():
    p = _p([_de("PRJ-000001", 3000.0), _de("PRJ-000002", 9000.0), _de("PRJ-000003", 5000.0), _de("PRJ-000004", 3900.0), _de("PRJ-000005", None)])
    r = delivery.comparable_set(p, "de_clay_window", as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000003"] and r.dropped == {"no_route_length": 1, "route_window": 3}
    assert sum(r.dropped.values()) == len(p) - len(r.frame), "every removed project is counted once"


def test_a_profile_rules_row_is_a_valid_rule_and_unset_fields_filter_nothing():
    p = _p([_de("PRJ-000001", 5000.0), _de("PRJ-000002", 9000.0, country="DK")])
    for name in ("de_clay_window", "cell_de_dh_clay", "dk_dh_recent"):
        row = delivery.profile_rules(context=CTX).set_index("profile").loc[name].to_dict()
        assert _keys(p, row) == _keys(p, name), name
    assert _keys(p, {"country": None, "route_min_m": float("nan")}) == ["PRJ-000001", "PRJ-000002"]


def test_require_route_length_inside_a_rule_and_bad_rule_values_are_frame_errors():
    p = _p([_de("PRJ-000001", None), _de("PRJ-000002", 5000.0)])
    assert _keys(p, {"country": "DE", "require_route_length": True}) == ["PRJ-000002"]
    t = delivery.variants_table(p, {"a": {"country": "DE"}, "b": {"country": "DE", "require_route_length": True}}, as_of=NOW, default="a", context=CTX).set_index("rule")
    assert t.n.to_dict() == {"a": 2, "b": 1}
    assert _keys(p, "cell_de_dh_clay", exclude=None) == ["PRJ-000001", "PRJ-000002"]
    for bad, match in (({"country": ["DE", "DK"]}, "one text value"), ({"route_min_m": "4000"}, "number of metres"), ({"start_from": "zzz"}, "not a date"), ({"start_from": 2023}, "date or an ISO text")):
        with pytest.raises(FrameError, match=match):
            _keys(p, bad)
    for bad_call in (lambda: _keys(p, exclude=5), lambda: _keys(p, ["a"]), lambda: delivery.variants_table(p, ["a"], context=CTX),
                     lambda: delivery.variants_table(p, metric=[1], context=CTX),
                     lambda: delivery.comparable_coverage(p, p.assign(final_cost=1.0), pd.DataFrame(columns=["prj_key", "type"]), pd.DataFrame(columns=["prj_key"]), None, context=CTX)):
        with pytest.raises(FrameError):
            bad_call()
    with pytest.raises(FrameError, match="route_length_m must be numeric"):
        delivery.comparable_set(p.assign(route_length_m=p.route_length_m.astype(str)), context=CTX)


def test_coverage_accepts_the_comparable_set_itself_and_refuses_duplicates():
    comp = delivery.comparable_set(_p([_de("PRJ-000001")]), "cell_de_dh_clay", as_of=NOW, context=CTX)
    proj = pd.DataFrame({"prj_key": ["PRJ-000001"], "final_cost": [1.0], "route_length_m": [5000.0]})
    empty = (pd.DataFrame(columns=["prj_key", "type"]), pd.DataFrame(columns=["prj_key"]), [])
    assert len(delivery.comparable_coverage(comp, proj, *empty, context=CTX)) == 1
    with pytest.raises(FrameError, match="more than once"):
        delivery.comparable_coverage(pd.concat([comp.frame, comp.frame]), proj, *empty, context=CTX)


# review fixes, second round

EMPTY_FRAMES = (pd.DataFrame(columns=["prj_key", "type"]), pd.DataFrame(columns=["prj_key"]))


def _cov_inputs(keys):
    comp = pd.DataFrame({"prj_key": keys})
    proj = pd.DataFrame({"prj_key": keys, "final_cost": [1.0] * len(keys), "route_length_m": [5000.0] * len(keys)})
    return comp, proj


def test_coverage_accepts_the_time_entry_frame_a_list_an_array_and_refuses_a_series_or_a_groupby():
    comp, proj = _cov_inputs(["PRJ-000001", "PRJ-000002", "PRJ-000003"])
    te = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000001", "PRJ-000003"], "hours": [1.0, 2.0, 3.0], "person": ["a", "b", "c"]})
    want = [True, False, True]
    for given in (te, te["prj_key"].unique(), ["PRJ-000001", "PRJ-000003"], ("PRJ-000001", "PRJ-000003"), {"PRJ-000001", "PRJ-000003"}, pd.Index(["PRJ-000001", "PRJ-000003"])):
        c = delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, given, context=CTX)
        assert c.has_time_entries.tolist() == want, type(given).__name__
    # the frame is read by its column, not by the set of its column names
    c = delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, te, context=CTX)
    assert c.has_time_entries.tolist() == want and not c.roster_only.any()
    with pytest.raises(FrameError, match="lacks column prj_key"):
        delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, te.rename(columns={"prj_key": "project"}), context=CTX)
    with pytest.raises(FrameError, match="Series"):
        delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, te["prj_key"], context=CTX)
    with pytest.raises(FrameError, match="groupby"):
        delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, te.groupby("prj_key"), context=CTX)


@pytest.mark.release
def test_coverage_with_the_time_entry_frame_of_the_baseline(load, release_dir):
    p = load("projects", "project")
    comp = delivery.comparable_set(p, "de_clay_window", as_of=NOW, context=CTX).frame
    te = load("projects", "time_entry")
    cov = delivery.comparable_coverage(comp, p, load("projects", "estimate_version"), load("projects", "project_role"), te, context=CTX).set_index("prj_key")
    assert cov.loc[["PRJ-000161", "PRJ-000198", "PRJ-000220"], "has_time_entries"].all()
    assert cov.has_time_entries.sum() == 3 and cov.roster_only.sum() == 3


def _dated():
    return _p([_de("PRJ-000001", end=D(2026, 6, 1)),                                  # completed from 2026-06-02
               _de("PRJ-000002", start=D(2026, 7, 1), end=D(2027, 1, 1)),             # planned until 2026-06-30
               _de("PRJ-000003", end=None)])                                          # active from 2018


def test_as_of_moves_the_status_in_comparable_set():
    p = _dated()

    def keys(status, as_of):
        r = delivery.comparable_set(p, {"country": "DE", "status": status}, as_of=as_of, context=CTX)
        assert r.rule["as_of"] == as_of.isoformat()
        return list(r.frame.prj_key)
    assert keys("completed", NOW) == ["PRJ-000001"] and list(delivery.comparable_set(p, {"status": "completed"}, context=CTX).frame.prj_key) == ["PRJ-000001"]
    assert keys("completed", D(2026, 6, 1)) == [] and keys("active", D(2026, 6, 1)) == ["PRJ-000001", "PRJ-000003"], "ends on the date: still active"
    assert keys("completed", D(2026, 6, 2)) == ["PRJ-000001"]
    assert keys("completed", D(2026, 5, 31)) == [] and keys("active", D(2026, 5, 31)) == ["PRJ-000001", "PRJ-000003"]
    assert keys("planned", D(2026, 6, 30)) == ["PRJ-000002"] and keys("planned", D(2026, 7, 1)) == [] and keys("active", D(2026, 7, 1)) == ["PRJ-000002", "PRJ-000003"]


def test_as_of_moves_the_status_in_variants_table_and_the_end_from_boundary():
    p = _dated()
    rules = {"done": {"country": "DE", "status": "completed"}, "open": {"country": "DE", "status": "active"}, "plan": {"country": "DE", "status": "planned"}}

    def n(as_of):
        kw = {} if as_of is None else {"as_of": as_of}
        return delivery.variants_table(p, rules, default="done", context=CTX, **kw).set_index("rule").n.to_dict()
    assert n(None) == {"done": 1, "open": 2, "plan": 0} and n(NOW) == n(None)
    assert n(D(2026, 5, 31)) == {"done": 0, "open": 2, "plan": 1}
    assert n(D(2026, 6, 1)) == {"done": 0, "open": 2, "plan": 1}
    assert n(D(2026, 6, 2)) == {"done": 1, "open": 1, "plan": 1}
    # dk_dh_recent: end_from is 2024-01-01 and a project that ends on it is completed only from the day after
    q = _p([_de("PRJ-000001", country="DK", soil="sand", start=D(2023, 6, 1), end=D(2024, 1, 1)), _de("PRJ-000002", country="DK", soil="sand", start=D(2023, 6, 1), end=D(2023, 12, 31))])
    on, after = D(2024, 1, 1), D(2024, 1, 2)
    r_on, r_after = (delivery.comparable_set(q, "dk_dh_recent", as_of=a, context=CTX) for a in (on, after))
    assert list(r_on.frame.prj_key) == [] and r_on.dropped == {"status": 1, "end_before_window": 1}, "PRJ-000001 ends on the date: still active"
    assert r_after.dropped == {"end_before_window": 1} and list(r_after.frame.prj_key) == ["PRJ-000001"] and r_after.dropped == {"end_before_window": 1}
    assert delivery.variants_table(q, as_of=on, context=CTX).set_index("rule").loc["dk_dh_recent", "n"] == 0
    assert delivery.variants_table(q, as_of=after, context=CTX).set_index("rule").loc["dk_dh_recent", "n"] == 1


def test_status_may_be_a_list_and_variants_table_excludes_the_project_under_review():
    p = _dated()
    r = delivery.comparable_set(p, {"country": "DE", "status": ["planned", "active", "active"]}, as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000002", "PRJ-000003"] and r.rule["status"] == ["active", "planned"] and r.dropped == {"status": 1}
    assert _keys(p, {"status": ("completed", "active")}) == ["PRJ-000001", "PRJ-000002", "PRJ-000003"] and _keys(p, {"status": {"completed"}}) == ["PRJ-000001"]
    for bad, match in (([], "one text value or a non-empty list"), ([1], "one text value or a non-empty list"), (["done"], "unknown status 'done'"), ("done", "unknown status")):
        with pytest.raises(FrameError, match=match):
            _keys(p, {"status": bad})
    q = _p([_de("PRJ-000001"), _de("PRJ-000002"), _de("PRJ-000003", legacy=True)])
    metric = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000002", "PRJ-000003"], "value": [10.0, 20.0, 60.0]})
    t = delivery.variants_table(q, metric=metric, as_of=NOW, default="cell_de_dh_clay", exclude=["PRJ-000002"], context=CTX).set_index("rule")
    assert t.loc["cell_de_dh_clay", ["n", "legacy_n", "metric_n"]].tolist() == [2, 1, 2] and t.loc["cell_de_dh_clay", "metric_median"] == 35.0
    assert delivery.variants_table(q, as_of=NOW, default="cell_de_dh_clay", exclude="PRJ-000001", context=CTX).set_index("rule").loc["cell_de_dh_clay", "n"] == 2
    assert delivery.variants_table(q, as_of=NOW, default="cell_de_dh_clay", context=CTX).set_index("rule").loc["cell_de_dh_clay", "n"] == 3
    with pytest.raises(FrameError, match="exclude must be"):
        delivery.variants_table(q, exclude=5, context=CTX)
    assert "24" in delivery.variants_table.__doc__ and "23" in delivery.variants_table.__doc__


def test_variants_table_metric_missing_and_an_empty_rule():
    p = _p([_de("PRJ-000001", legacy=True), _de("PRJ-000002"), _de("PRJ-000003")])
    metric = pd.DataFrame({"prj_key": ["PRJ-000002", "PRJ-000009"], "value": [4.0, 5.0]})        # PRJ-000001 and 3 have no value; PRJ-000009 is not a project
    t = delivery.variants_table(p, {"all": {"country": "DE"}, "none": {"country": "SE"}}, metric=metric, default="all", as_of=NOW, context=CTX).set_index("rule")
    assert t.loc["all", ["n", "legacy_n", "metric_n", "metric_missing"]].tolist() == [3, 1, 1, 2] and t.loc["all", "metric_median"] == 4.0
    assert t.loc["none", ["n", "legacy_n", "metric_n", "metric_missing"]].tolist() == [0, 0, 0, 0]
    assert pd.isna(t.loc["none", "legacy_share"]) and pd.isna(t.loc["none", "metric_median"])
    nan_metric = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000002"], "value": [np.nan, np.nan]})
    t2 = delivery.variants_table(p, {"all": {"country": "DE"}}, metric=nan_metric, default="all", as_of=NOW, context=CTX).set_index("rule")
    assert t2.loc["all", ["metric_n", "metric_missing"]].tolist() == [0, 3] and pd.isna(t2.loc["all", "metric_median"])


def test_the_set_is_sorted_by_prj_key_whatever_the_input_order_and_a_window_may_be_a_single_length():
    rows = [_de("PRJ-000003", 5000.0), _de("PRJ-000001", 5000.0), _de("PRJ-000004", 5000.1), _de("PRJ-000002", 5000.0)]
    p = _p(rows[::-1]).sample(frac=1.0, random_state=3)
    assert list(p.prj_key) != sorted(p.prj_key)
    r = delivery.comparable_set(p, "cell_de_dh_clay", as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000001", "PRJ-000002", "PRJ-000003", "PRJ-000004"] and r.frame.index.tolist() == [0, 1, 2, 3]
    assert _keys(p, {"route_min_m": 5000, "route_max_m": 5000}) == ["PRJ-000001", "PRJ-000002", "PRJ-000003"], "min equal to max is a valid window"
    assert _keys(p, "de_clay_window", overrides={"route_min_m": 5000.0, "route_max_m": 5000.0}) == ["PRJ-000001", "PRJ-000002", "PRJ-000003"]
    with pytest.raises(FrameError, match="above"):
        _keys(p, {"route_min_m": 5000.1, "route_max_m": 5000})


def test_bad_inputs_are_frame_errors_not_value_errors():
    p = _p([_de("PRJ-000001"), _de("PRJ-000002")])
    for bad in ([1, 2], (1, 2), np.array([1, 2]), True, np.True_, "5", dict):
        with pytest.raises(FrameError, match="number of metres"):
            _keys(p, {"route_min_m": bad})
        with pytest.raises(FrameError, match="number of metres"):
            _keys(p, {"route_max_m": bad})
    assert _keys(p, {"route_min_m": np.int64(4000), "route_max_m": np.float32(6000)}) == ["PRJ-000001", "PRJ-000002"]
    for rules in ({"a": "DE"}, {"a": ["DE"]}, {"a": dict}):
        with pytest.raises(FrameError, match="rule 'a' must be a mapping"):
            delivery.variants_table(p, rules, as_of=NOW, context=CTX)
    clash = p.set_index("prj_key", drop=False)
    assert clash.index.name == "prj_key" and "prj_key" in clash.columns
    with pytest.raises(FrameError, match="index named 'prj_key'"):
        delivery.comparable_set(clash, context=CTX)
    with pytest.raises(FrameError, match="index named 'prj_key'"):
        delivery.variants_table(clash, as_of=NOW, context=CTX)
    metric = pd.DataFrame({"prj_key": ["PRJ-000001"], "value": [1.0]})
    with pytest.raises(FrameError, match="index named 'prj_key'"):
        delivery.variants_table(p, metric=metric.set_index("prj_key", drop=False), as_of=NOW, context=CTX)
    comp, proj = _cov_inputs(["PRJ-000001"])
    for args in ((comp.set_index("prj_key", drop=False), proj), (comp, proj.set_index("prj_key", drop=False))):
        with pytest.raises(FrameError, match="index named 'prj_key'"):
            delivery.comparable_coverage(*args, *EMPTY_FRAMES, [], context=CTX)
    with pytest.raises(FrameError, match="index named 'prj_key'"):
        delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, metric.set_index("prj_key", drop=False), context=CTX)


def test_an_empty_or_all_null_object_frame_without_dtypes_is_an_empty_set_and_text_is_still_refused():
    empty = pd.DataFrame(columns=COLS)
    assert empty.route_length_m.dtype == object
    r = delivery.comparable_set(empty, as_of=NOW, context=CTX)
    assert len(r.frame) == 0 and list(r.frame.columns) == ["prj_key", "route_length_m", "legacy", "data_depth", "route_known"] and r.dropped == {}
    assert delivery.variants_table(empty, as_of=NOW, context=CTX).n.tolist() == [0, 0, 0]
    p = _p([_de("PRJ-000001", None), _de("PRJ-000002", None)])
    assert p.route_length_m.dtype == object
    assert list(delivery.comparable_set(p, "cell_de_dh_clay", as_of=NOW, context=CTX).frame.route_known) == [False, False]
    assert delivery.comparable_set(p, "de_clay_window", as_of=NOW, context=CTX).dropped == {"no_route_length": 2}
    with pytest.raises(FrameError, match="route_length_m must be numeric"):
        delivery.comparable_set(_p([_de("PRJ-000001", "5000")]), context=CTX)


def test_a_null_start_date_is_counted_when_the_rule_needs_it_and_does_not_break_other_projects():
    p = _p([_de("PRJ-000001", start=None), _de("PRJ-000002"), _de("PRJ-000003", country="DK", start=None)])
    r = delivery.comparable_set(p, "de_clay_window", as_of=NOW, context=CTX)
    assert list(r.frame.prj_key) == ["PRJ-000002"] and r.dropped == {"country": 1, "no_start_date": 1}, "the DK project with no start is gone by country; the DE one is counted"
    assert sum(r.dropped.values()) == len(p) - len(r.frame)
    c = delivery.comparable_set(p, {"country": "DE", "type": "dh_network"}, as_of=NOW, context=CTX)
    assert list(c.frame.prj_key) == ["PRJ-000001", "PRJ-000002"] and c.dropped == {"country": 1}, "no status or start window: the null start does not matter"
    s = delivery.comparable_set(p, {"country": "DE", "start_from": "2010-01-01"}, as_of=NOW, context=CTX)
    assert list(s.frame.prj_key) == ["PRJ-000002"] and s.dropped == {"country": 1, "no_start_date": 1}
    assert delivery.variants_table(p, as_of=NOW, context=CTX).set_index("rule").n.to_dict() == {"de_clay_window": 1, "cell_de_dh_clay": 1, "dk_dh_recent": 0}


def test_the_set_carries_the_profile_name():
    p = _p([_de("PRJ-000001")])
    assert delivery.comparable_set(p, "cell_de_dh_clay", as_of=NOW, context=CTX).profile == "cell_de_dh_clay"
    assert delivery.comparable_set(p, "de_clay_window", overrides={"route_max_m": 9000}, as_of=NOW, context=CTX).profile == "de_clay_window"
    assert delivery.comparable_set(p, as_of=NOW, context=CTX).profile == "de_clay_window"
    row = delivery.profile_rules(context=CTX).set_index("profile", drop=False).loc["dk_dh_recent"].to_dict()
    assert delivery.comparable_set(p, row, as_of=NOW, context=CTX).profile == "dk_dh_recent"
    assert delivery.comparable_set(p, {"country": "DE"}, as_of=NOW, context=CTX).profile is None
    frame, rule, dropped = delivery.comparable_set(p, as_of=NOW, context=CTX)[:3]
    assert len(frame) == 1 and "profile" not in rule and dropped == {}


# third review: the extension arrays and indexes the error texts advise (.unique() of a string or category column)

def test_coverage_and_exclude_accept_the_unique_of_a_string_or_category_column_and_an_index():
    comp, proj = _cov_inputs(["PRJ-000001", "PRJ-000002", "PRJ-000003"])
    te = pd.DataFrame({"prj_key": ["PRJ-000001", "PRJ-000001", "PRJ-000003"]})
    for dtype in ("string", "category"):
        given = te["prj_key"].astype(dtype).unique()
        assert not isinstance(given, np.ndarray)
        c = delivery.comparable_coverage(comp, proj, *EMPTY_FRAMES, given, context=CTX)
        assert c.has_time_entries.tolist() == [True, False, True], dtype
    p = _p([_de("PRJ-000001"), _de("PRJ-000002"), _de("PRJ-000003")])
    for given in (pd.Index(["PRJ-000002"]), pd.array(["PRJ-000002"], dtype="string"), pd.Series(["PRJ-000002"]).astype("category").unique(), pd.Series(["PRJ-000002"]).astype("category").cat.categories):
        assert _keys(p, "cell_de_dh_clay", exclude=given) == ["PRJ-000001", "PRJ-000003"], type(given).__name__
