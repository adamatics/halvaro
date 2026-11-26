"""Oracles of halvaro.core.periods (lane L1): effective dating checks and the interval join. The expected values come from plain Python loops over the rows, numpy masks and
hand worked frames; the library functions use sorting, shifts and merges."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core

D = dt.date
RULES = {"reversed", "two_open", "open_not_last", "overlap", "gap"}


def _ref_violations(rows: list, convention: str = "day_after") -> set:
    """(key, rule) of the violations, from a loop over the rows of each key sorted by valid_from; rows are (key, valid_from, valid_to) with None for an open end."""
    step = dt.timedelta(days=1 if convention == "day_after" else 0)
    out = set()
    for key in sorted({r[0] for r in rows}):
        mine = sorted((r for r in rows if r[0] == key), key=lambda r: r[1])
        opens = [r for r in mine if r[2] is None]
        for i, (_, vf, vt) in enumerate(mine):
            if vt is not None and vt < vf:
                out.add((key, "reversed"))
            if vt is None and len(opens) > 1:
                out.add((key, "two_open"))
            if i + 1 < len(mine):
                nxt = mine[i + 1][1]
                if vt is None:
                    out.add((key, "open_not_last"))
                elif nxt < vt + step:
                    out.add((key, "overlap"))
                elif nxt > vt + step:
                    out.add((key, "gap"))
    return out


def _frame(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["k", "valid_from", "valid_to"])


def _rules(v: pd.DataFrame) -> set:
    return {(r.key, r.rule) for r in v.itertuples()}


def test_check_contiguity_oracle_each_rule_once_by_hand():
    """halvaro.core.periods.check_contiguity: a clean chain has no violation and each of the five rules is found exactly where a loop over the rows finds it, for both conventions."""
    clean = [("A", D(2024, 1, 1), D(2024, 6, 30)), ("A", D(2024, 7, 1), D(2024, 12, 31)), ("A", D(2025, 1, 1), None)]
    assert len(core.check_contiguity(_frame(clean), "k")) == 0 and _ref_violations(clean) == set()
    bad = {"reversed": [("R", D(2024, 5, 1), D(2024, 4, 1))],
           "two_open": [("T", D(2024, 1, 1), None), ("T", D(2025, 1, 1), None)],
           "open_not_last": [("O", D(2024, 1, 1), None), ("O", D(2025, 1, 1), D(2025, 12, 31))],
           "overlap": [("V", D(2024, 1, 1), D(2024, 6, 30)), ("V", D(2024, 6, 15), D(2024, 12, 31))],
           "gap": [("G", D(2024, 1, 1), D(2024, 6, 30)), ("G", D(2024, 8, 1), D(2024, 12, 31))]}
    for rule, rows in bad.items():
        got = _rules(core.check_contiguity(_frame(rows), "k"))
        assert rule in {r for _, r in got} and got == _ref_violations(rows), rule
    for rule, rows in bad.items():                              # the rows of a key need not come sorted: the same violations when the rows are given in reverse order
        assert _rules(core.check_contiguity(_frame(rows[::-1]), "k")) == _ref_violations(rows), rule
    every = [r for rows in bad.values() for r in rows]
    assert _rules(core.check_contiguity(_frame(every), "k")) == _ref_violations(every)
    assert {r for _, r in _ref_violations(every)} == RULES
    one_day_gap = [("G", D(2024, 1, 1), D(2024, 6, 30)), ("G", D(2024, 7, 2), D(2024, 12, 31))]
    assert _rules(core.check_contiguity(_frame(one_day_gap), "k")) == _ref_violations(one_day_gap) == {("G", "gap")}, "a gap of one day is a gap"
    one_day_row = [("A", D(2024, 1, 1), D(2024, 1, 1)), ("A", D(2024, 1, 2), None)]
    assert len(core.check_contiguity(_frame(one_day_row), "k")) == 0 and _ref_violations(one_day_row) == set(), "a row that starts and ends on the same day is not reversed"
    touching = [("A", D(2024, 1, 1), D(2024, 6, 30)), ("A", D(2024, 6, 30), D(2024, 12, 31))]
    assert _rules(core.check_contiguity(_frame(touching), "k", convention="touching")) == _ref_violations(touching, "touching") == set()
    assert _rules(core.check_contiguity(_frame(touching), "k")) == _ref_violations(touching) == {("A", "overlap")}
    with pytest.raises(core.PeriodError):
        core.check_contiguity(_frame(clean), "k", convention="weekly")


def test_check_contiguity_oracle_composite_keys_table_name_and_custom_columns():
    """halvaro.core.periods.check_contiguity: a list of key columns is one key (violations are per combination), the table name is carried into the result, and the date columns can be named."""
    rows = [("A", "x", D(2024, 1, 1), D(2024, 6, 30)), ("A", "x", D(2024, 8, 1), None), ("A", "y", D(2024, 1, 1), D(2024, 6, 30)), ("A", "y", D(2024, 7, 1), None)]
    f = pd.DataFrame(rows, columns=["k1", "k2", "from_d", "to_d"])
    v = core.check_contiguity(f, ["k1", "k2"], valid_from="from_d", valid_to="to_d", table="t")
    assert [(r.table, r.key, r.rule) for r in v.itertuples()] == [("t", "A, x", "gap")]
    assert len(core.check_contiguity(f.query("k2 == 'y'"), ["k1", "k2"], valid_from="from_d", valid_to="to_d")) == 0


def test_interval_join_oracle_a_colliding_column_name_gets_the_suffix_and_the_point_columns_come_first():
    """halvaro.core.periods.interval_join: an interval column with the name of a point column gets the suffix _iv, and the columns are the point columns, then the interval columns."""
    pts = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01 10:30"]), "name": ["p"], "from_ts": [1]})
    iv = pd.DataFrame({"from_ts": pd.to_datetime(["2026-01-01 10:00"]), "to_ts": pd.to_datetime(["2026-01-01 11:00"]), "name": ["i"]})
    out = core.interval_join(pts, iv)
    assert list(out.columns) == ["ts", "name", "from_ts", "from_ts_iv", "to_ts", "name_iv"]
    assert out["name"].tolist() == ["p"] and out["name_iv"].tolist() == ["i"] and out["from_ts"].tolist() == [1]


def test_interval_join_oracle_other_column_names_and_a_list_of_keys():
    """halvaro.core.periods.interval_join: the names of the point timestamp, the interval start and end can be given, and a list of key columns must all match."""
    pts = pd.DataFrame({"when": pd.to_datetime(["2026-01-01 10:30", "2026-01-01 10:30", "2026-01-01 12:00"]), "a": ["x", "x", "x"], "b": [1, 2, 1]})
    iv = pd.DataFrame({"s": pd.to_datetime(["2026-01-01 10:00"]), "e": pd.to_datetime(["2026-01-01 11:00"]), "a": ["x"], "b": [1]})
    out = core.interval_join(pts, iv, point_ts="when", start="s", end="e", key=["a", "b"])
    assert out["s"].notna().tolist() == [True, False, False], "only the first point has the key (x, 1) and lies inside"
    assert out["when"].tolist() == pts["when"].tolist() and list(out.columns) == ["when", "a", "b", "s", "e"]


def _random_case(seed: int, n_points=120, n_iv=25):
    rng = np.random.default_rng(seed)
    base = pd.Timestamp("2026-01-01")
    pts = pd.DataFrame({"pid": range(n_points), "k": rng.choice(["a", "b", "c"], n_points), "ts": base + pd.to_timedelta(rng.integers(0, 600, n_points), unit="m")})
    starts = base + pd.to_timedelta(rng.integers(0, 560, n_iv), unit="m")
    ends = starts + pd.to_timedelta(rng.integers(0, 90, n_iv), unit="m")
    iv = pd.DataFrame({"iid": range(n_iv), "k": rng.choice(["a", "b", "c"], n_iv), "from_ts": starts, "to_ts": ends})
    iv.loc[iv.index[::7], "to_ts"] = pd.NaT                       # open intervals
    iv["to_ts"] = pd.to_datetime(iv["to_ts"])
    return pts, iv


def _ref_pairs(pts, iv, key, inclusive, how):
    pairs = []
    for p in pts.itertuples():
        hit = [i.iid for i in iv.itertuples() if (key is None or i.k == p.k) and i.from_ts <= p.ts and (pd.isna(i.to_ts) or (p.ts <= i.to_ts if inclusive else p.ts < i.to_ts))]
        pairs += [(p.pid, h) for h in hit] if hit else ([(p.pid, None)] if how == "left" else [])
    return sorted(pairs, key=lambda x: (x[0], -1 if x[1] is None else x[1]))


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("inclusive", [True, False])
@pytest.mark.parametrize("key", [None, "k"])
@pytest.mark.parametrize("how", ["left", "inner"])
def test_interval_join_oracle_nested_loop(seed, inclusive, key, how):
    """halvaro.core.periods.interval_join: the pairs of points and intervals equal a nested loop over both frames: start <= ts <= end (or < end), an open end contains everything after
    the start, a point in two intervals appears twice, a point without an interval stays for left and goes for inner, `key` must match."""
    pts, iv = _random_case(seed)
    out = core.interval_join(pts.drop(columns="k") if key is None else pts, iv.drop(columns="k") if key is None else iv, key=key, inclusive_end=inclusive, how=how)
    got = sorted(((int(r.pid), None if pd.isna(r.iid) else int(r.iid)) for r in out.itertuples()), key=lambda x: (x[0], -1 if x[1] is None else x[1]))
    pts_ref = pts if key else pts.assign(k="x")
    iv_ref = iv if key else iv.assign(k="x")
    assert got == _ref_pairs(pts_ref, iv_ref, key, inclusive, how)
    assert (out["pid"].diff().dropna() >= 0).all(), "output is ordered by point"
    if how == "left":
        assert set(out["pid"]) == set(pts["pid"]), "a left join keeps every point"


def test_interval_join_oracle_boundary_points_by_hand():
    """halvaro.core.periods.interval_join: a point exactly on the end is in for inclusive_end and out for exclusive; on the start it is always in."""
    iv = pd.DataFrame({"from_ts": [pd.Timestamp("2026-01-01 10:00")], "to_ts": [pd.Timestamp("2026-01-01 11:00")]})
    pts = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01 09:59", "2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 11:01"])})
    inc = core.interval_join(pts, iv)
    exc = core.interval_join(pts, iv, inclusive_end=False)
    assert inc["from_ts"].notna().tolist() == [False, True, True, False]
    assert exc["from_ts"].notna().tolist() == [False, True, False, False]
    with pytest.raises(core.FrameError):
        core.interval_join(pts, iv, how="outer")
    with pytest.raises(core.FrameError):
        core.interval_join(pts.rename(columns={"ts": "t"}), iv)


def test_asof_join_oracle_overlapping_two_open_and_reversed_right_rows_are_refused():
    """halvaro.core.periods.asof_join: a right frame with overlapping rows, two open rows or a reversed row for one key raises PeriodError naming the key, a gap does not, and the clean frame joins
    the row valid on the date (the pointer of the index stays on the generator function; the overlap case was found by a mutation that the older tests did not catch)."""
    left = pd.DataFrame({"k": ["A"], "d": [D(2026, 3, 15)]})
    good = pd.DataFrame({"k": ["A", "A"], "valid_from": [D(2026, 1, 1), D(2026, 4, 1)], "valid_to": [D(2026, 3, 31), None], "v": [1, 2]})
    assert core.asof_join(left, good, "d", "k")["v"].tolist() == [1]
    bad = {"overlap": [("A", D(2026, 1, 1), D(2026, 3, 31)), ("A", D(2026, 3, 1), D(2026, 12, 31))],
           "two_open": [("A", D(2026, 1, 1), None), ("A", D(2026, 4, 1), None)],
           "reversed": [("A", D(2026, 5, 1), D(2026, 4, 1))]}
    for rule, rows in bad.items():
        right = pd.DataFrame(rows, columns=["k", "valid_from", "valid_to"]).assign(v=1)
        with pytest.raises(core.PeriodError, match="A"):
            core.asof_join(left, right, "d", "k")
    gap = pd.DataFrame([("A", D(2026, 1, 1), D(2026, 2, 28), 1), ("A", D(2026, 4, 1), None, 2)], columns=["k", "valid_from", "valid_to", "v"])
    assert pd.isna(core.asof_join(left, gap, "d", "k")["v"].iloc[0]), "a date in a gap finds no row"
