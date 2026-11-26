"""Audit schedule and target progress (plan 5.9): hand computed dates and glide paths, then the baseline against the truth of the Hannover audit."""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, registry

M12 = Context(stage="month12", role="r")

A = pd.DataFrame({"site_key": ["S1", "S1", "S2", "S3", "S3"], "year": [2022, 2025, 2022, 2021, 2026], "audit_date": ["2022-03-01", "2025-03-01", "2022-12-07", "2021-06-01", "2026-12-31"],
                  "due_date": ["2022-03-01", "2025-03-01", "2022-12-07", "2021-06-01", "2026-12-31"], "status": ["completed", "completed", "completed", "completed", "planned"]})


def test_audit_schedule_cycle_open_row_and_overdue():
    s = esg.audit_schedule(A, "2026-11-30", context=M12).value.set_index("site_key")
    assert str(s.loc["S1", "last_audit_date"].date()) == "2025-03-01" and str(s.loc["S1", "next_due"].date()) == "2029-03-01" and not s.loc["S1", "overdue"] and not s.loc["S1", "open_audit"]
    assert str(s.loc["S2", "next_due"].date()) == "2026-12-07" and s.loc["S2", "days_to_due"] == 7 and not s.loc["S2", "overdue"], "2022-12-07 plus 4 years"
    assert s.loc["S3", "open_audit"] and str(s.loc["S3", "next_due"].date()) == "2026-12-31" and s.loc["S3", "days_to_due"] == 31, "the open row's due date, not last plus cycle"
    assert str(s.loc["S3", "last_audit_date"].date()) == "2021-06-01"
    late = esg.audit_schedule(A, "2026-12-08", context=M12).value.set_index("site_key")
    assert late.loc["S2", "overdue"] and not late.loc["S3", "overdue"]
    short = esg.audit_schedule(A, "2026-11-30", cycle_years=2, context=M12).value.set_index("site_key")
    assert short.loc["S1", "overdue"] is np.False_ or not short.loc["S1", "overdue"]
    assert bool(short.loc["S2", "overdue"]), "2022-12-07 plus 2 years is past"
    early = esg.audit_schedule(A, "2022-06-01", context=M12).value.set_index("site_key")
    assert str(early.loc["S1", "last_audit_date"].date()) == "2022-03-01", "audits after the day are not seen"
    assert pd.isna(early.loc["S2", "last_audit_date"]) and pd.isna(early.loc["S2", "next_due"])


def test_audit_schedule_ignores_due_date_of_completed_rows_and_refuses():
    odd = A.assign(due_date=["1999-01-01"] * 5, status=["completed", "completed", "completed", "completed", "planned"])
    assert str(esg.audit_schedule(odd.assign(due_date=["1999-01-01"] * 4 + ["2026-12-31"]), "2026-11-30", context=M12).value.set_index("site_key").loc["S1", "next_due"].date()) == "2029-03-01"
    with pytest.raises(FrameError, match="more than one open"):
        esg.audit_schedule(pd.concat([A, A.iloc[[4]]]), "2026-11-30", context=M12)
    with pytest.raises(FrameError, match="cycle_years"):
        esg.audit_schedule(A, "2026-11-30", cycle_years=0, context=M12)
    with pytest.raises(FrameError, match="as_of"):
        esg.audit_schedule(A, 5, context=M12)


def _lines():
    c = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "prj_key", "quantity", "efac_key", "ref_type", "ref_key", "unit", "site_key", "subcategory"]
    rows = [("LE-01", "2023-01", 1, "mobile_combustion", 1, None, "1", 1000.0, True, None, None), ("LE-01", "2023-01", 1, "mobile_combustion", 2, None, "1", 1100.0, False, "2026-01", 1),
            ("LE-01", "2025-01", 1, "mobile_combustion", 1, None, "1", 700.0, False, None, None), ("LE-01", "2023-01", 3, "purchased_goods", 3, None, "3.1", 5000.0, False, None, None),
            ("LE-01", "2025-01", 3, "purchased_goods", 2, None, "3.1", 4000.0, False, None, None)]
    return pd.DataFrame([r + (None, np.nan, None, None, None, None, None, None) for r in rows], columns=c).astype({"supersedes_line_no": "Int64"})


def test_target_progress_glide_path_actual_and_baseline_basis():
    T = pd.DataFrame({"target_no": [1, 2, 3], "scope": ["1", "3", "project_intensity"], "baseline_year": [2023, 2023, 2025], "target_year": [2030, 2030, 2028],
                      "baseline_value": [1000.0, 5000.0, 90.0], "target_value": [500.0, 3000.0, 72.0]})
    r = esg.target_progress(T, _lines(), "2026-11-30", context=M12).value.set_index("target_no")
    assert r.loc[1, "baseline_current"] == 1100.0 and r.loc[1, "baseline_first_booked"] == 1000.0 and r.loc[1, "baseline_basis"] == "first_booked", "the stored baseline 1000 is the first booked value"
    assert r.loc[1, "year"] == 2025 and r.loc[1, "glide_value"] == pytest.approx(1000 - 500 * 2 / 7, abs=0.001) and r.loc[1, "actual"] == 700.0 and r.loc[1, "on_track"] is None and r.loc[1, "gap"] == pytest.approx(700 - (1000 - 500 * 2 / 7), abs=0.001)
    assert r.loc[2, "baseline_basis"] == "current" and r.loc[2, "actual"] == 4000.0 and r.loc[2, "months"] == 1
    assert r.loc[3, "baseline_basis"] == "not a line scope" and np.isnan(r.loc[3, "actual"]) and r.loc[3, "on_track"] is None and r.loc[3, "glide_value"] == 90.0
    assert esg.target_progress(T, _lines(), "2026-11-30", tolerance=0.2, context=M12).value.set_index("target_no").loc[1, "baseline_basis"] == "current", "the tolerance decides which basis matches first"
    n = esg.target_progress(T.assign(baseline_value=[999999.0, 5000.0, 90.0]), _lines(), "2026-11-30", context=M12).value.set_index("target_no")
    assert n.loc[1, "baseline_basis"] == "neither"
    with pytest.raises(FrameError, match="before its baseline"):
        esg.target_progress(T.assign(target_year=[2020, 2030, 2028]), _lines(), "2026-11-30", context=M12)
    with pytest.raises(FrameError, match="more than one"):
        esg.target_progress(pd.concat([T, T.iloc[:1]]), _lines(), "2026-11-30", context=M12)


def test_registration():
    for n in ("audit_schedule", "target_progress"):
        assert f"halvaro.esg.audit_targets.{n}" in registry.registered() and n in esg.__all__


def test_audit_schedule_status_and_null_handling_and_the_verify_status():
    r = esg.audit_schedule(A, "2026-11-30", context=M12)
    assert r.status == "VERIFY+synthetic" and any("cycle" in w for w in r.warnings)
    can = pd.concat([A, pd.DataFrame({"site_key": ["S2"], "year": [2026], "audit_date": [None], "due_date": ["2026-03-01"], "status": ["cancelled"]})])
    assert esg.audit_schedule(can, "2026-11-30", context=M12).value.set_index("site_key").loc["S2", "open_audit"] == False, "a cancelled audit is left out, not open"  # noqa: E712
    with pytest.raises(FrameError, match="no due date"):
        esg.audit_schedule(A.assign(due_date=["2022-03-01", "2025-03-01", "2022-12-07", "2021-06-01", None]), "2026-11-30", context=M12)
    with pytest.raises(FrameError, match="no audit date"):
        esg.audit_schedule(A.assign(audit_date=[None] + A.audit_date.tolist()[1:]), "2026-11-30", context=M12)
    day = esg.audit_schedule(A, "2025-03-01", context=M12).value.set_index("site_key")
    assert str(day.loc["S1", "last_audit_date"].date()) == "2025-03-01", "a completed audit on the day is seen"
    assert esg.audit_schedule(A, "2026-12-07", context=M12).value.set_index("site_key").loc["S2", "overdue"] == False, "due on the day is not overdue"  # noqa: E712
    assert esg.audit_schedule(A, "2026-12-08", context=M12).value.set_index("site_key").loc["S2", "overdue"]


def test_target_progress_basis_partial_year_nulls_and_float_scope():
    T = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2023], "target_year": [2030], "baseline_value": [1000.0], "target_value": [500.0]})
    fb = esg.target_progress(T, _lines(), "2026-11-30", basis="first_booked", year=2023, context=M12)
    assert fb.value.actual.tolist() == [1000.0] and "first_booked" in fb.warnings[0] and fb.status == "VERIFY+synthetic"
    assert esg.target_progress(T, _lines(), "2026-11-30", year=2023, context=M12).value.actual.tolist() == [1100.0]
    part = _lines().assign(period=["2023-01", "2023-01", "2025-01", "2023-01", "2025-01"])
    for kw in (dict(basis="x"),):
        with pytest.raises(FrameError, match="basis"):
            esg.target_progress(T, part, "2026-11-30", context=M12, **kw)
    assert esg.target_progress(T, _lines(), "2026-11-30", context=M12).value.on_track.tolist() == [None], "one month of data in 2025: not judged"
    with pytest.raises(FrameError, match="nulls"):
        esg.target_progress(T.assign(target_value=[np.nan]), _lines(), "2026-11-30", context=M12)
    with pytest.raises(FrameError, match="no rows"):
        esg.target_progress(T.iloc[:0], _lines(), "2026-11-30", context=M12)
    assert esg.target_progress(T.assign(scope=[1.0]), _lines(), "2026-11-30", context=M12).value.baseline_basis.tolist() != ["not a line scope"], "a scope read as the float 1.0 is still scope 1"


def test_second_round_audit_status_numbers_and_target_scope_months_and_basis():
    odd = A.assign(status=["Completed", " completed ", "COMPLETED", "completed", "Planned"])
    assert esg.audit_schedule(odd, "2026-11-30", context=M12).value.set_index("site_key").loc["S1", "last_audit_date"].year == 2025, "status is compared without case and spaces"
    for bad, msg in ((A.assign(status=[None] + A.status.tolist()[1:]), "status"), (A.assign(audit_date=[20200101] + A.audit_date.tolist()[1:]), "numbers"), (A.assign(audit_date=["abc"] + A.audit_date.tolist()[1:]), "not a date"),
                     (A.assign(site_key=[None] + A.site_key.tolist()[1:]), "site_key")):
        with pytest.raises(FrameError, match=msg):
            esg.audit_schedule(bad, "2026-11-30", context=M12)
    assert esg.audit_schedule(A, "2026-11-30", cycle_years=np.int64(4), context=M12).value.cycle_years.iloc[0] == 4
    with pytest.raises(FrameError, match="1 to 100"):
        esg.audit_schedule(A, "2026-11-30", cycle_years=100000, context=M12)
    T = pd.DataFrame({"target_no": [1, 2], "scope": ["1", "3"], "baseline_year": [2023, 2023], "target_year": [2030, 2030], "baseline_value": [1000.0, 5000.0], "target_value": [500.0, 3000.0]})
    def flat(rows):
        c = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no"]
        return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})

    half = flat([("LE-01", "2025-01", 1, "mobile_combustion", 1, None, "1", 60.0, False, None, None), ("LE-01", "2025-01", 2, "purchased_electricity", 2, "location", "2", 10.0, False, None, None),
                 ("LE-01", "2025-02", 2, "purchased_electricity", 3, "location", "2", 10.0, False, None, None)])
    r = esg.target_progress(T, half, "2026-11-30", year=2025, context=M12).value.set_index("target_no")
    assert r.loc[1, "months"] == 1 and r.loc[1, "on_track"] is None, "months of the target's own scope, not of the other scopes"
    assert r.loc[2, "months"] == 0 and np.isnan(r.loc[2, "actual"]) and r.loc[2, "on_track"] is None, "a scope without lines has no actual"
    assert (r.actual_basis == "current").all()
    with pytest.raises(FrameError, match="scope"):
        esg.target_progress(T.assign(scope=["1", "2_locaton"]), half, "2026-11-30", context=M12)
    with pytest.raises(FrameError, match="tolerance"):
        esg.target_progress(T, half, "2026-11-30", tolerance=-1, context=M12)
    year = flat([("LE-01", f"2025-{m:02d}", 1, "mobile_combustion", 100 + m, None, "1", 5.0, False, None, None) for m in range(1, 13)])
    assert esg.target_progress(T.iloc[:1], year, "2026-11-30", year=2025, context=M12).value.on_track.notna().all(), "twelve months of scope 1 lines: judged"
    assert esg.target_progress(T.iloc[:1], year, "2025-06-30", year=2025, context=M12).value.on_track.tolist() == [None], "the year is not over on the day"
    fb = esg.target_progress(T.iloc[:1], _lines(), "2026-11-30", year=2023, basis="current", context=M12).value
    assert fb.baseline_basis.iloc[0] == "first_booked" and bool(fb.basis_mismatch.iloc[0]), "the stored baseline is first booked and the actual is on the current basis: flagged"


def test_lever_report_inputs_and_unrounded_limit():
    pm = pd.DataFrame({"prj_key": ["P1"], "route_length_m": [1000.0], "kgco2e_per_m": [10.0004]})
    r = esg.lever_report(pm, pd.DataFrame({"lever": ["a"], "saved_kgco2e": [0.1]}), np.float32(10.0), top=np.int64(1), context=M12)
    assert not bool(r.below_limit_after.iloc[0]), "10.0004 less 0.0001 is still above 10"
    with pytest.raises(FrameError, match="finite"):
        esg.lever_report(pm, pd.DataFrame({"lever": ["a"], "saved_kgco2e": [float("inf")]}), 10.0, context=M12)
