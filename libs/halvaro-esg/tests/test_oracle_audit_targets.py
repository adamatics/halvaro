"""Oracle tests of halvaro.esg.audit_targets: target_progress.

Expected values come from hand frames with the numbers in the test and from plain pandas sums of the baseline release; the function is never called to compute an expected value.
"""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
LINE_COLS = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]


def _lines(rows):
    return pd.DataFrame(rows, columns=LINE_COLS).astype({"supersedes_line_no": "Int64"})


def _months(year, kg, *, scope=1, method=None, ghg="1", category="c", skip=(), line_no=1):
    return [("LE-01", f"{year}-{m:02d}", scope, category, line_no, method, ghg, kg, None, None, False) for m in range(1, 13) if m not in skip]


def _targets(rows):
    return pd.DataFrame(rows, columns=["target_no", "scope", "baseline_year", "target_year", "baseline_value", "target_value"])


def _flag(x):
    return None if pd.isna(x) else bool(x)


def _hand():
    rows = []
    # scope 1: 2023 booked 12 x 50 = 600, June restated to 80 (the original line 1 is superseded by line 2); 2025: 12 x 40
    rows += _months(2023, 50.0, skip=(6,)) + [("LE-01", "2023-06", 1, "c", 1, None, "1", 50.0, None, None, True), ("LE-01", "2023-06", 1, "c", 2, None, "1", 80.0, "2025-01", 1, False)]
    rows += _months(2025, 40.0)
    # scope 2: location 12 x 10 in 2023 and 11 x 5 in 2025 (no December); market 12 x 30 in 2023 and 12 x 25 in 2025 (the two methods are never added)
    rows += _months(2023, 10.0, scope=2, method="location", ghg="2", category="e") + _months(2025, 5.0, scope=2, method="location", ghg="2", category="e", skip=(12,))
    rows += _months(2023, 30.0, scope=2, method="market", ghg="2", category="e", line_no=2) + _months(2025, 25.0, scope=2, method="market", ghg="2", category="e", line_no=2)
    # scope 3: 12 x 100 in 2023, only 10 months in 2025
    rows += _months(2023, 100.0, scope=3, ghg="3.1") + _months(2025, 100.0, scope=3, ghg="3.1", skip=(11, 12))
    return _lines(rows)


def _hand_targets():
    return _targets([(1, "1", 2023, 2033, 600.0, 100.0), (2, "2_location", 2023, 2033, 120.0, 60.0), (3, "2_market", 2023, 2033, 360.0, 36.0), (4, "3", 2023, 2033, 1200.0, 600.0),
                     (5, "project_intensity", 2025, 2028, 90.0, 60.0)])


def test_oracle_target_progress_hand_example_glide_gap_and_flags():
    """route: hand lines whose yearly sums are written in the test; glide path, gap and flags worked out by hand for the year 2025, a target at a time."""
    L, T = _hand(), _hand_targets()
    L0, T0 = L.copy(deep=True), T.copy(deep=True)
    r = esg.target_progress(T, L, "2026-03-01", context=M12)
    pd.testing.assert_frame_equal(L, L0)
    pd.testing.assert_frame_equal(T, T0)
    assert r.status == "VERIFY+synthetic" and r.synthetic and r.function == "halvaro.esg.audit_targets.target_progress"
    v = r.value.set_index("target_no")
    assert v.index.tolist() == [1, 2, 3, 4, 5]
    assert {"target_no", "scope", "baseline_year", "target_year", "baseline_value", "baseline_current", "baseline_first_booked", "baseline_basis", "year", "actual", "glide_value", "gap", "on_track", "months",
            "actual_basis", "basis_mismatch"} <= set(r.value.columns)
    assert (v.year == 2025).all(), "the default year is the year before the day"
    # glide at 2025: baseline plus (target less baseline) times 2/10
    assert v.loc[1, "glide_value"] == pytest.approx(500.0) and v.loc[2, "glide_value"] == pytest.approx(108.0) and v.loc[3, "glide_value"] == pytest.approx(295.2) and v.loc[4, "glide_value"] == pytest.approx(1080.0)
    assert v.loc[5, "glide_value"] == pytest.approx(90.0), "the glide of a target that starts in 2025 is its baseline in 2025"
    assert v.loc[[1, 2, 3, 4], "actual"].tolist() == pytest.approx([480.0, 55.0, 300.0, 1000.0]), "each scope and method is summed on its own"
    assert v.loc[[1, 2, 3, 4], "gap"].tolist() == pytest.approx([-20.0, -53.0, 4.8, -80.0])
    assert v.loc[[1, 2, 3, 4], "months"].tolist() == [12, 11, 12, 10], "the months are those of the scope and method of the target"
    assert [_flag(v.loc[k, "on_track"]) for k in (1, 2, 3, 4)] == [True, None, False, None], "fewer than twelve months of data in the year give no answer"
    assert v.loc[[1, 2, 3, 4], "baseline_current"].tolist() == pytest.approx([630.0, 120.0, 360.0, 1200.0]), "June 2023 is 80 on the current basis"
    assert v.loc[[1, 2, 3, 4], "baseline_first_booked"].tolist() == pytest.approx([600.0, 120.0, 360.0, 1200.0])
    assert v.loc[[1, 2, 3, 4], "baseline_basis"].tolist() == ["first_booked", "current", "current", "current"]
    assert bool(v.loc[1, "basis_mismatch"]) is True, "the stored baseline of scope 1 is reproduced by the first booked basis only, and the actual is on the current basis"
    assert (v.loc[[1, 2, 3, 4], "actual_basis"] == "current").all()
    assert v.loc[5, "baseline_basis"] == "not a line scope" and pd.isna(v.loc[5, "actual"]) and pd.isna(v.loc[5, "gap"]) and pd.isna(v.loc[5, "on_track"]) and not v.loc[5, "basis_mismatch"]
    fb = esg.target_progress(T, L, "2026-03-01", basis="first_booked", context=M12).value.set_index("target_no")
    assert fb.loc[1, "actual"] == pytest.approx(480.0) and fb.loc[1, "actual_basis"] == "first_booked" and not fb.loc[1, "basis_mismatch"]


def test_oracle_target_progress_year_and_day_boundaries():
    """route: hand lines of one scope; the glide clipped at the two ends of the path, the year-is-over test around the last day of the year, and the actual on the glide value itself."""
    L = _lines(_months(2023, 50.0) + _months(2025, 40.0) + _months(2033, 10.0))
    T = _targets([(1, "1", 2023, 2033, 600.0, 100.0)])
    glide = lambda y: esg.target_progress(T, L, "2040-01-01", year=y, context=M12).value.glide_value.iloc[0]
    assert glide(2020) == pytest.approx(600.0) and glide(2023) == pytest.approx(600.0), "no step before the baseline year"
    assert glide(2028) == pytest.approx(350.0) and glide(2033) == pytest.approx(100.0) and glide(2040) == pytest.approx(100.0), "no step after the target year"
    assert glide(2024) == pytest.approx(550.0) and glide(2032) == pytest.approx(150.0)
    day = lambda d: esg.target_progress(T, L, d, year=2025, context=M12).value.iloc[0]
    assert _flag(day("2025-12-30").on_track) is None, "the year is not over on 2025-12-30"
    last = day("2025-12-31")
    assert _flag(last.on_track) is True and last.actual == pytest.approx(480.0) and last.months == 12
    assert esg.target_progress(T, L, "2026-06-30", context=M12).value.year.iloc[0] == 2025
    assert esg.target_progress(T, L, "2026-01-01", context=M12).value.year.iloc[0] == 2025 and esg.target_progress(T, L, "2025-12-31", context=M12).value.year.iloc[0] == 2024
    on_path = lambda top: _lines(_months(2023, 50.0) + _months(2025, 40.0, skip=(12,)) + [("LE-01", "2025-12", 1, "c", 1, None, "1", top, None, None, False)])      # 2025 total is 440 + top
    at = esg.target_progress(T, on_path(60.0), "2026-03-01", context=M12).value.iloc[0]
    assert at.glide_value == pytest.approx(500.0) and at.actual == pytest.approx(500.0) and at.gap == pytest.approx(0.0) and _flag(at.on_track) is True, "an actual on the glide value is on track"
    over = esg.target_progress(T, on_path(60.001), "2026-03-01", context=M12).value.iloc[0]
    assert over.gap == pytest.approx(0.001, abs=1e-9) and _flag(over.on_track) is False
    short = esg.target_progress(T, on_path(60.0).iloc[:-1], "2026-03-01", context=M12).value.iloc[0]
    assert short.months == 11 and _flag(short.on_track) is None and short.actual == pytest.approx(440.0)
    none = esg.target_progress(T, L[L.period.str[:4] != "2025"], "2026-03-01", context=M12).value.iloc[0]
    assert pd.isna(none.actual) and pd.isna(none.gap) and none.months == 0 and _flag(none.on_track) is None and none.glide_value == pytest.approx(500.0)


def test_oracle_target_progress_first_booked_basis_counts_its_own_months():
    """route: hand lines in which December 2025 exists only as a restated line; the current basis has twelve months and an answer, the first booked basis has eleven months and none."""
    L = _lines(_months(2023, 50.0) + _months(2025, 40.0, skip=(12,)) + [("LE-01", "2025-12", 1, "c", 1, None, "1", 40.0, "2026-01", 99, False)])
    T = _targets([(1, "1", 2023, 2033, 600.0, 100.0)])
    cur = esg.target_progress(T, L, "2026-03-01", context=M12).value.iloc[0]
    first = esg.target_progress(T, L, "2026-03-01", basis="first_booked", context=M12).value.iloc[0]
    assert (cur.months, cur.actual, _flag(cur.on_track)) == (12, pytest.approx(480.0), True)
    assert (first.months, first.actual, _flag(first.on_track)) == (11, pytest.approx(440.0), None)
    assert cur.actual_basis == "current" and first.actual_basis == "first_booked"


def test_oracle_target_progress_tolerance_boundary_of_the_stored_baseline():
    """route: hand lines; the stored baseline 1000 against a 2023 total of 1005 sits exactly on the default tolerance of 0.5 percent of the stored value (5.0), checked on the edge and just beyond it."""
    T = _targets([(1, "1", 2023, 2030, 1000.0, 500.0)])
    exact = _lines([("LE-01", f"2023-{m:02d}", 1, "c", 1, None, "1", 100.0 if m <= 5 else 0.0, None, None, False) for m in range(1, 13)])
    exact.loc[exact.period == "2023-06", "kgco2e"] = 505.0
    beyond = exact.assign(kgco2e=exact.kgco2e.where(exact.period != "2023-06", 505.001))
    assert exact.kgco2e.sum() == 1005.0 and beyond.kgco2e.sum() == pytest.approx(1005.001)
    got = lambda frame, **kw: esg.target_progress(T, frame, "2026-03-01", context=M12, **kw).value.iloc[0]
    assert got(exact).baseline_basis == "current", "a difference equal to the tolerance still reproduces the baseline"
    assert got(beyond).baseline_basis == "neither", "a difference above the tolerance does not"
    assert got(exact, tolerance=0.004).baseline_basis == "neither" and got(exact, tolerance=0.006).baseline_basis == "current"
    assert not got(beyond).basis_mismatch, "'neither' is not a mismatch"
    for bad in (-0.1, np.nan, True):
        with pytest.raises(FrameError, match="tolerance"):
            got(exact, tolerance=bad)


def test_oracle_target_progress_refusals_name_the_input():
    """route: hand frames, each input the function cannot work with and the error it must raise."""
    L, T = _hand(), _hand_targets()
    with pytest.raises(FrameError, match="more than one row"):
        esg.target_progress(pd.concat([T, T.iloc[:1]]), L, "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="no rows"):
        esg.target_progress(T.iloc[:0], L, "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="before its baseline year"):
        esg.target_progress(T.assign(target_year=2023), L, "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="scope"):
        esg.target_progress(T.assign(scope="4"), L, "2026-03-01", context=M12)
    with pytest.raises(FrameError, match="basis"):
        esg.target_progress(T, L, "2026-03-01", basis="all", context=M12)
    with pytest.raises(FrameError, match="whole year"):
        esg.target_progress(T, L, "2026-03-01", year=2025.5, context=M12)


def test_oracle_target_progress_every_route():
    """route: the hand examples, boundaries and refusals above. The release step (the baseline targets against the baseline lines) is a separate test that needs the closed repository."""
    test_oracle_target_progress_hand_example_glide_gap_and_flags()
    test_oracle_target_progress_year_and_day_boundaries()
    test_oracle_target_progress_first_booked_basis_counts_its_own_months()
    test_oracle_target_progress_tolerance_boundary_of_the_stored_baseline()
    test_oracle_target_progress_refusals_name_the_input()
