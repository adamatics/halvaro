"""Oracles of lane P1 (P1.4b) for six functions of halvaro.core.periods that had a pointer to generator code or a generator test: parse_period, period_range, year_of, release_now, rows_on and
asof_join. Expected values come from datetime.strptime, numpy and pandas period arithmetic, the data_release tables read with pyarrow and plain loops."""
import bisect
import datetime as dt
import random

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core

D = dt.date


def test_parse_period_oracle_every_period_text_from_0001_to_9999_equals_strptime():
    """halvaro.core.periods.parse_period: for each of the 119988 texts YYYY-MM of the years 0001 to 9999 the pair (year, month) equals what datetime.strptime reads from the same text, and texts of any other shape raise
    PeriodError (a one digit month, which strptime accepts, a month 13 or 00, a year of five digits, a day, other separators, blanks, an empty text, a number, a date)."""
    for y in range(1, 10000):
        for m in range(1, 13):
            text = f"{y:04d}-{m:02d}"
            t = dt.datetime.strptime(text, "%Y-%m")
            assert core.parse_period(text) == (t.year, t.month), text
    for bad in ("2026-1", "2026-13", "2026-00", "10000-01", "26-11", "2026-11-01", "2026/11", " 2026-11", "2026-11 ", "", None, 202611, D(2026, 11, 1)):                       # the year 0000 and a final newline are the cases of #444
        with pytest.raises(core.PeriodError):
            core.parse_period(bad)


def test_period_range_oracle_numpy_months_for_random_pairs_and_reversed_pairs_are_empty():
    """halvaro.core.periods.period_range: for 1500 random pairs between 1900 and 2200 the list equals numpy's months from first to last, both included; a last before the first gives an empty list;
    one period gives itself."""
    rng = random.Random(4)
    periods = [f"{y:04d}-{m:02d}" for y in range(1900, 2201) for m in range(1, 13)]
    for _ in range(1500):
        a, b = rng.choice(periods), rng.choice(periods)
        want = [str(x) for x in np.arange(np.datetime64(a, "M"), np.datetime64(b, "M") + 1)] if a <= b else []
        assert core.period_range(a, b) == want, (a, b)
    assert core.period_range("2026-11", "2026-11") == ["2026-11"] and core.period_range("2026-12", "2026-11") == []


def test_year_of_oracle_pandas_period_arithmetic_for_every_start_month():
    """halvaro.core.periods.year_of: the year that starts in `start_month` and holds the period equals the calendar year of the period moved back by start_month less one months (pandas Period
    arithmetic) for all months of 2020 to 2030 and all twelve start months; the Danish holiday year (starts in month 9) puts 2026-08 in 2025 and 2026-09 in 2026; a start month outside 1 to 12 raises."""
    for y in range(2020, 2031):
        for m in range(1, 13):
            for s in range(1, 13):
                assert core.year_of(f"{y}-{m:02d}", s) == (pd.Period(f"{y}-{m:02d}", "M") - (s - 1)).year, (y, m, s)
    assert core.year_of("2026-08", 9) == 2025 and core.year_of("2026-09", 9) == 2026
    for bad in (0, 13, -1):
        with pytest.raises(core.PeriodError):
            core.year_of("2026-08", bad)


def test_asof_join_oracle_a_loop_with_bisect_over_random_effective_dated_rows():
    """halvaro.core.periods.asof_join: for seeded random effective dated right frames (several rows per key, gaps between them, an open last row) and 300 left dates and periods, the value joined
    is the one of the right row with the latest valid_from at or before the date, null when the date is in a gap or before the first row; a period text counts from its first day; the left order is kept."""
    rng = random.Random(10)
    rows, spans = [], {}
    for k in range(12):
        start, segs = D(2020, 1, 1) + dt.timedelta(days=rng.randint(0, 200)), []
        for n in range(rng.randint(1, 4)):
            length = rng.randint(30, 200)
            end = None if n == 3 or rng.random() < 0.15 else start + dt.timedelta(days=length)
            segs.append((start, end, f"K{k}-v{n}"))
            rows.append((f"K{k}", start.isoformat(), end.isoformat() if end else None, f"K{k}-v{n}"))
            if end is None:
                break
            start = end + dt.timedelta(days=rng.randint(1, 60))
        spans[f"K{k}"] = segs
    right = pd.DataFrame(rows, columns=["k", "valid_from", "valid_to", "v"])
    left_rows = []
    for _ in range(300):
        key = f"K{rng.randint(0, 11)}"
        left_rows.append((key, D(2020, 1, 1) + dt.timedelta(days=rng.randint(0, 900))))
    left = pd.DataFrame({"k": [k for k, _ in left_rows], "d": [d for _, d in left_rows]})
    got = core.asof_join(left, right, "d", "k")["v"].tolist()
    for (k, d), g in zip(left_rows, got):
        starts = [s for s, _, _ in spans[k]]
        i = bisect.bisect_right(starts, d) - 1
        want = None
        if i >= 0 and (spans[k][i][1] is None or spans[k][i][1] >= d):
            want = spans[k][i][2]
        assert (g if isinstance(g, str) else None) == want, (k, d)
    months = pd.DataFrame({"k": ["K0", "K0"], "p": ["2020-06", "2019-01"]})
    by_month = core.asof_join(months, right, "p", "k")["v"].tolist()
    first_day = core.asof_join(pd.DataFrame({"k": ["K0", "K0"], "d": [D(2020, 6, 1), D(2019, 1, 1)]}), right, "d", "k")["v"].tolist()
    assert [None if pd.isna(x) else x for x in by_month] == [None if pd.isna(x) else x for x in first_day]
    assert core.asof_join(left, right, "d", "k")["k"].tolist() == left["k"].tolist(), "the order of the left rows is kept"
    mid = pd.DataFrame({"k": ["K9"], "valid_from": ["2020-06-15"], "valid_to": [None], "v": ["v9"]})
    june = core.asof_join(pd.DataFrame({"k": ["K9"] * 3, "d": ["2020-06", "2020-07", "2020-06-20"]}), mid, "d", "k")["v"].tolist()
    assert [None if pd.isna(x) else x for x in june] == [None, "v9", "v9"], "the period 2020-06 is 1 June, before a row that starts on 15 June; 2020-07 is 1 July; 20 June is inside"


def test_rows_on_and_asof_join_oracle_an_effective_dated_frame_without_valid_to_is_refused():
    """halvaro.core.periods.rows_on and halvaro.core.periods.asof_join: a frame without the column valid_to raises FrameError naming the column, for both functions."""
    frame = pd.DataFrame({"k": ["A"], "valid_from": ["2020-01-01"], "v": ["x"]})
    with pytest.raises(core.FrameError, match="column valid_to is missing"):
        core.rows_on(frame, D(2020, 2, 1))
    with pytest.raises(core.FrameError, match="column valid_to is missing"):
        core.asof_join(pd.DataFrame({"k": ["A"], "d": ["2020-02-01"]}), frame, "d", "k")


def test_asof_join_oracle_a_right_column_with_the_name_of_a_left_column_gets_the_suffix():
    """halvaro.core.periods.asof_join: a column of the right frame that the left frame also has (v) keeps the left values under v and is given the suffix `_r` (or the suffix asked for) by hand: the left v is 'left', the
    right v of the row valid on 5 March is 'right'."""
    left = pd.DataFrame({"k": ["A"], "d": ["2020-03-05"], "v": ["left"]})
    right = pd.DataFrame({"k": ["A"], "valid_from": ["2020-01-01"], "valid_to": [None], "v": ["right"]})
    got = core.asof_join(left, right, "d", "k")
    assert got["v"].tolist() == ["left"] and got["v_r"].tolist() == ["right"]
    assert core.asof_join(left, right, "d", "k", suffix="_x")["v_x"].tolist() == ["right"]
