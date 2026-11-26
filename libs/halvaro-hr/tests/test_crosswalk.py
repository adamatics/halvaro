"""XW-1: username to person or team on a date, assignments, overlaps. Synthetic boundaries, then the baseline against the generator's own Resolver."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import AmbiguousKey, FrameError, registry

D = dt.date


def _uh():
    return pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000002", "EMP-000003"], "username": ["a.one", "b.old", "b.new", "c.gone"],
                         "valid_from": [D(2020, 1, 1), D(2020, 1, 1), D(2024, 3, 1), D(2021, 1, 1)], "valid_to": [None, D(2024, 2, 29), None, D(2023, 6, 30)]})


def _sa():
    return pd.DataFrame({"account_name": ["pool-1"], "team_key": ["TEAM-005"], "valid_from": [D(2023, 1, 1)], "valid_to": [None]})


def _idx():
    return hr.build_username_index(_uh(), _sa())


def test_index_shape_and_order():
    idx = _idx()
    assert list(idx.columns) == ["username", "kind", "holder", "emp_key", "team_key", "valid_from", "valid_to"] and len(idx) == 5
    assert idx.username.tolist() == sorted(idx.username) and idx.set_index("username").loc["pool-1", ["kind", "holder"]].tolist() == ["pool", "TEAM-005"]
    assert idx.set_index("username").loc["c.gone", "valid_to"] == pd.Timestamp(2023, 6, 30) and pd.isna(idx.set_index("username").loc["a.one", "valid_to"])


def test_index_refuses_missing_columns_nulls_and_reversed_rows():
    with pytest.raises(FrameError, match="lacks column.*valid_to"):
        hr.build_username_index(_uh().drop(columns="valid_to"), _sa())
    with pytest.raises(FrameError, match="no holder"):
        hr.build_username_index(_uh().assign(emp_key=[None, "EMP-000002", "EMP-000002", "EMP-000003"]), _sa())
    with pytest.raises(FrameError, match="no username"):
        hr.build_username_index(_uh().assign(username=[None, "b.old", "b.new", "c.gone"]), _sa())
    with pytest.raises(FrameError, match="end before they start.*c.gone"):
        hr.build_username_index(_uh().assign(valid_to=[None, D(2024, 2, 29), None, D(2020, 12, 31)]), _sa())
    with pytest.raises(FrameError, match="not a date"):
        hr.build_username_index(_uh().assign(valid_from=["x"] * 4), _sa())


def test_resolve_username_at_every_boundary():
    idx = _idx()
    r = hr.resolve_username
    assert r(idx, "b.old", D(2024, 2, 29)) == {"kind": "employee", "emp_key": "EMP-000002", "team_key": None}, "the old name holds to valid_to"
    assert r(idx, "b.old", D(2024, 3, 1)) is None and r(idx, "b.new", D(2024, 2, 29)) is None
    assert r(idx, "b.new", D(2024, 3, 1))["emp_key"] == "EMP-000002" and r(idx, "b.old", D(2019, 12, 31)) is None and r(idx, "b.old", D(2020, 1, 1))["emp_key"] == "EMP-000002"
    assert r(idx, "c.gone", D(2023, 6, 30))["emp_key"] == "EMP-000003" and r(idx, "c.gone", D(2023, 7, 1)) is None, "a leaver keeps the username history"
    assert r(idx, "pool-1", pd.Timestamp("2025-06-01 13:00")) == {"kind": "pool", "emp_key": None, "team_key": "TEAM-005"}
    assert r(idx, "nobody.here", D(2025, 6, 1)) is None and r(idx, "a.one", "2030-01-01")["emp_key"] == "EMP-000001"
    for bad in (None, "junk", 20250601):
        with pytest.raises(FrameError, match="not a date"):
            r(idx, "a.one", bad)


def test_two_holders_on_a_date_raise_and_are_listed_as_overlapping():
    dup = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000009"], "username": ["a.one"], "valid_from": [D(2024, 1, 1)], "valid_to": [None]})])
    idx = hr.build_username_index(dup, _sa())
    with pytest.raises(hr.AmbiguousUsername, match="a.one on 2025-01-01") as e:
        hr.resolve_username(idx, "a.one", D(2025, 1, 1))
    assert isinstance(e.value, AmbiguousKey) and e.value.username == "a.one" and len(e.value.candidates) == 2
    assert hr.resolve_username(idx, "a.one", D(2023, 1, 1))["emp_key"] == "EMP-000001", "before the second holder it is not ambiguous"
    assert hr.overlapping_usernames(idx) == ["a.one"] and hr.overlapping_usernames(_idx()) == []
    touching = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000009"], "username": ["c.gone"], "valid_from": [D(2023, 7, 1)], "valid_to": [None]})])
    assert hr.overlapping_usernames(hr.build_username_index(touching, _sa())) == [], "a day after the old holder ended is not an overlap"
    on_the_day = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000009"], "username": ["c.gone"], "valid_from": [D(2023, 6, 30)], "valid_to": [None]})])
    assert hr.overlapping_usernames(hr.build_username_index(on_the_day, _sa())) == ["c.gone"]
    same_person = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000001"], "username": ["a.one"], "valid_from": [D(2022, 1, 1)], "valid_to": [None]})])
    assert hr.overlapping_usernames(hr.build_username_index(same_person, _sa())) == [], "the same person twice is a duplicate row, not two holders"
    pool_vs_person = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000009"], "username": ["pool-1"], "valid_from": [D(2024, 1, 1)], "valid_to": [None]})])
    assert hr.overlapping_usernames(hr.build_username_index(pool_vs_person, _sa())) == ["pool-1"]


def _emp():
    return pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002", "EMP-000003"], "hire_date": [D(2020, 1, 1), D(2020, 1, 1), D(2021, 1, 1)], "leave_date": [None, None, D(2023, 6, 30)]})


def _assign(rows):
    return pd.DataFrame(rows, columns=["ast_key", "valid_from", "valid_to", "assigned_username", "pool_team_key", "assignment_type"])


def test_assignments_resolve_at_valid_from_and_flag_returns():
    a = _assign([("AST-000001", D(2023, 1, 1), D(2023, 7, 30), "c.gone", None, "named"),          # returned 30 days after leaving: on time
                 ("AST-000002", D(2023, 1, 1), D(2023, 7, 31), "c.gone", None, "named"),          # 31 days: late
                 ("AST-000003", D(2023, 1, 1), None, "c.gone", None, "named"),                    # still open, left long ago: late
                 ("AST-000004", D(2022, 1, 1), D(2023, 6, 30), "b.old", None, "named"),           # old name, valid_from inside its window
                 ("AST-000005", D(2024, 3, 1), None, "b.new", None, "named"),
                 ("AST-000006", D(2024, 3, 1), None, "b.old", None, "named"),                     # old name after the change: unresolved
                 ("AST-000007", D(2024, 1, 1), None, "pool-1", None, "pool_account"),
                 ("AST-000008", D(2024, 1, 1), None, None, "TEAM-005", "team"),
                 ("AST-000009", D(2024, 1, 1), None, "pool-1", None, "named"),                    # kind does not follow the type
                 ("AST-000010", D(2020, 6, 1), None, "c.gone", None, "named")])                   # before c.gone was hired / assigned
    res = hr.resolve_assignments(a, _idx(), _emp(), D(2026, 11, 30))
    f = res.frame.set_index("ast_key")
    assert f.resolution.to_dict() == {"AST-000001": "resolved", "AST-000002": "resolved", "AST-000003": "resolved", "AST-000004": "resolved", "AST-000005": "resolved",
                                      "AST-000006": "unresolved", "AST-000007": "resolved", "AST-000008": "no_username", "AST-000009": "resolved", "AST-000010": "unresolved"}
    assert f.loc["AST-000004", "emp_key"] == "EMP-000002" and f.loc["AST-000007", "team_key"] == "TEAM-005" and pd.isna(f.loc["AST-000007", "emp_key"])
    assert f.kind_ok.to_dict() == {k: (k not in ("AST-000006", "AST-000009", "AST-000010")) for k in f.index}
    assert f.loc["AST-000001", "returned_after_leave_days"] == 30 and not f.loc["AST-000001", "late_return"]
    assert f.loc["AST-000002", "returned_after_leave_days"] == 31 and f.loc["AST-000002", "late_return"]
    assert f.loc["AST-000003", "open_after_leave"] and f.loc["AST-000003", "late_return"] and pd.isna(f.loc["AST-000003", "returned_after_leave_days"])
    assert not f.loc["AST-000005", "late_return"] and not f.loc["AST-000005", "open_after_leave"] and f.loc["AST-000005", "employed_on_start"]
    d = res.diagnostics
    assert (d["rows"], d["with_username"], d["no_username"], d["resolved"], d["unresolved"], d["ambiguous"], d["kind_mismatch"]) == (10, 9, 1, 7, 2, 0, 3)
    assert d["late_return"] == 2 and d["open_after_leave"] == 1 and d["returned_after_leave"] == 2 and d["asset_return_days"] == 30


def test_return_days_parameter_and_open_rows_of_recent_leavers():
    a = _assign([("AST-000001", D(2023, 1, 1), D(2023, 7, 30), "c.gone", None, "named"), ("AST-000002", D(2023, 1, 1), None, "c.gone", None, "named")])
    assert hr.resolve_assignments(a, _idx(), _emp(), D(2023, 7, 15)).frame.late_return.tolist() == [False, False], "left 15 days ago and still open: not late yet"
    assert hr.resolve_assignments(a, _idx(), _emp(), D(2023, 7, 30)).frame.late_return.tolist() == [False, False] and hr.resolve_assignments(a, _idx(), _emp(), D(2023, 7, 31)).frame.late_return.tolist() == [False, True]
    assert hr.resolve_assignments(a, _idx(), _emp(), D(2023, 7, 15), asset_return_days=10).frame.late_return.tolist() == [True, True]


def test_ambiguous_names_are_counted_not_raised_and_input_is_not_changed():
    dup = pd.concat([_uh(), pd.DataFrame({"emp_key": ["EMP-000009"], "username": ["a.one"], "valid_from": [D(2024, 1, 1)], "valid_to": [None]})])
    a = _assign([("AST-000001", D(2025, 1, 1), None, "a.one", None, "named"), ("AST-000002", D(2023, 1, 1), None, "a.one", None, "named")])
    before = a.copy(deep=True)
    res = hr.resolve_assignments(a, hr.build_username_index(dup, _sa()), _emp(), D(2026, 11, 30))
    assert res.frame.resolution.tolist() == ["ambiguous", "resolved"] and res.diagnostics["ambiguous"] == 1
    assert pd.isna(res.frame.emp_key.iloc[0]) and res.frame.emp_key.iloc[1] == "EMP-000001" and not res.frame.kind_ok.iloc[0]
    pd.testing.assert_frame_equal(a, before)


def test_assignment_input_refusals():
    a = _assign([("AST-000001", D(2023, 1, 1), None, "a.one", None, "named")])
    with pytest.raises(FrameError, match="unknown assignment_type.*loan"):
        hr.resolve_assignments(a.assign(assignment_type="loan"), _idx(), _emp(), D(2026, 11, 30))
    with pytest.raises(FrameError, match="already has column.*resolution"):
        hr.resolve_assignments(a.assign(resolution="x"), _idx(), _emp(), D(2026, 11, 30))
    with pytest.raises(FrameError, match="duplicate emp_key"):
        hr.resolve_assignments(a, _idx(), pd.concat([_emp(), _emp()]), D(2026, 11, 30))
    with pytest.raises(FrameError, match="lacks column.*assigned_username"):
        hr.resolve_assignments(a.drop(columns="assigned_username"), _idx(), _emp(), D(2026, 11, 30))
    with pytest.raises(FrameError, match="not a date"):
        hr.resolve_assignments(a, _idx(), _emp(), "junk")
    assert hr.resolve_assignments(a.iloc[:0], _idx(), _emp(), D(2026, 11, 30)).diagnostics["rows"] == 0


def test_registered_with_oracles_and_exported():
    reg = registry.registered()
    for n in ("build_username_index", "resolve_username", "resolve_assignments", "overlapping_usernames"):
        m = reg[f"halvaro.hr.crosswalk.{n}"]
        assert m.sources and m.oracle.startswith("py:halvaro_gen/world/it_assets/xw1.py")
    assert reg["halvaro.hr.crosswalk.resolve_assignments"].parameters == ("assignment", "index", "employee", "as_of", "asset_return_days")
    assert {"build_username_index", "resolve_username", "resolve_assignments", "overlapping_usernames", "AmbiguousUsername"} <= set(hr.__all__) and registry.check() == []


# baseline


# review fixes

def test_the_person_must_hold_the_username_to_the_end_of_the_row():
    a = _assign([("AST-000001", D(2024, 1, 1), D(2024, 6, 1), "b.old", None, "named"),        # b.old ends 2024-02-29, the row runs on: not held
                 ("AST-000002", D(2024, 1, 1), D(2024, 2, 29), "b.old", None, "named"),        # ends with the name: held
                 ("AST-000003", D(2022, 1, 1), None, "c.gone", None, "named"),                 # open, the person left 2023-06-30: checked to the leave date
                 ("AST-000004", D(2024, 3, 1), None, "b.new", None, "named")])
    res = hr.resolve_assignments(a, _idx(), _emp(), D(2026, 11, 30))
    assert res.frame.holds_to_end.tolist() == [False, True, True, True] and res.diagnostics["not_holding_to_end"] == 1


def test_a_team_row_needs_its_team_key_and_the_open_boundary_is_the_last_day_employed():
    a = _assign([("AST-000001", D(2024, 1, 1), None, None, "TEAM-005", "team"), ("AST-000002", D(2024, 1, 1), None, None, None, "team")])
    assert hr.resolve_assignments(a, _idx(), _emp(), D(2026, 11, 30)).frame.kind_ok.tolist() == [True, False]
    open_row = _assign([("AST-000001", D(2023, 1, 1), None, "c.gone", None, "named")])
    on_leave_day = hr.resolve_assignments(open_row, _idx(), _emp(), D(2023, 6, 30))
    assert on_leave_day.frame.open_after_leave.tolist() == [False], "still employed on the leave date"
    assert hr.resolve_assignments(open_row, _idx(), _emp(), D(2023, 7, 1)).frame.open_after_leave.tolist() == [True]


def test_dates_time_zones_reversed_rows_and_hand_built_indexes():
    a = _assign([("AST-000001", D(2024, 3, 1), None, "b.new", None, "named")])
    with pytest.raises(FrameError, match="time zone"):
        hr.resolve_assignments(a, _idx(), _emp(), pd.Timestamp("2026-01-01", tz="UTC"))
    with pytest.raises(FrameError, match="time zone"):
        hr.resolve_username(_idx(), "a.one", pd.Timestamp("2023-01-01 23:00", tz="US/Pacific"))
    with pytest.raises(FrameError, match="tz-aware|time zone"):
        hr.build_username_index(_uh().assign(valid_from=pd.to_datetime(_uh().valid_from).dt.tz_localize("UTC")), _sa())
    with pytest.raises(FrameError, match="end before they start"):
        hr.resolve_assignments(_assign([("AST-000001", D(2023, 1, 1), D(2022, 1, 1), "b.new", None, "named")]), _idx(), _emp(), D(2026, 11, 30))
    raw = _idx().assign(valid_from=_idx().valid_from.dt.date, valid_to=_idx().valid_to.dt.date.astype(object).where(_idx().valid_to.notna(), None))
    assert hr.resolve_username(raw, "b.new", D(2024, 3, 1))["emp_key"] == "EMP-000002" and hr.overlapping_usernames(raw) == []
    assert hr.resolve_assignments(a, raw, _emp(), D(2026, 11, 30)).frame.resolution.tolist() == ["resolved"]
    empty = hr.resolve_assignments(a.iloc[:0], _idx(), _emp(), D(2026, 11, 30)).frame
    assert empty.returned_after_leave_days.dtype == "float64" and empty.empty


def test_no_warnings_from_the_baseline_shaped_frames():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        idx = hr.build_username_index(_uh(), _sa())
        hr.resolve_assignments(_assign([("AST-000001", D(2024, 3, 1), None, "b.new", None, "named")]), idx, _emp(), D(2026, 11, 30))
        hr.overlapping_usernames(idx)
