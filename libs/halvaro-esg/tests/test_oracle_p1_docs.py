"""Oracles of lane P1 for halvaro-esg: what the docstrings of request_timeliness, winter_decomposition and target_progress now say, checked on small hand frames. Numbers are written by hand."""
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context

M12 = Context(stage="month12", role="r")


def test_request_timeliness_oracle_requests_received_after_as_of_are_left_out_and_late_answers_do_not_count():
    """halvaro.esg.data_requests.request_timeliness: with as_of, a request received after that day is not in n, an answer after that day counts as not answered, and an answer before it counts with its
    days; without as_of every request counts."""
    R = pd.DataFrame({"cus_key": ["C1", "C1", "C1", "C1"], "request_no": [1, 2, 3, 4], "request_type": ["ghg"] * 4,
                      "received": ["2026-01-05", "2026-01-10", "2026-02-10", "2026-03-20"], "due": ["2026-01-20", "2026-01-25", "2026-02-25", "2026-04-03"],
                      "answered_date": ["2026-01-15", "2026-02-08", "2026-02-12", None]})
    full = esg.request_timeliness(R, context=M12).iloc[0]
    assert (full["n"], full["n_answered"], full["n_on_time"]) == (4, 3, 2)
    cut = esg.request_timeliness(R, as_of="2026-02-01", context=M12).iloc[0]
    assert (cut["n"], cut["n_answered"], cut["n_on_time"], cut["mean_days_to_answer"]) == (2, 1, 1, 10.0), "requests 3 and 4 are after the day; the answer to request 2 came on 8 February"


def test_winter_decomposition_oracle_months_count_the_distinct_periods_of_the_group():
    """halvaro.esg.ghg.winter_decomposition: with by='kind' two meters of one kind whose rows fall in the periods 2025-12, 2026-01 (both meters) and 2026-02 (one meter) give months_now 3, not 5; by meter the first has 2 and the second 3;
    a gap shows only when no meter of the group has a row in the period."""
    M = pd.DataFrame([("M1", "diesel", "a", "l"), ("M2", "diesel", "a", "l")], columns=["mtr_key", "carrier", "kind", "unit"])
    MA = pd.DataFrame({"mtr_key": ["M1"], "asset_type": ["vehicle"]})
    C = pd.DataFrame([("M1", "2025-12", 10.0), ("M1", "2026-01", 20.0), ("M2", "2025-12", 1.0), ("M2", "2026-01", 2.0), ("M2", "2026-02", 4.0)], columns=["mtr_key", "period", "quantity"]).assign(unit="l")
    now, prev = ("2025-12", "2026-02"), ("2024-12", "2025-02")
    by_kind = esg.winter_decomposition(C, M, MA, now, prev, by="kind", context=M12).set_index("kind")
    assert (by_kind.loc["a", "litres_now"], by_kind.loc["a", "months_now"]) == (37.0, 3), "periods 2025-12, 2026-01 and 2026-02: three distinct periods over five rows"
    by_meter = esg.winter_decomposition(C, M, MA, now, prev, by="meter", context=M12).set_index("mtr_key")
    assert (by_meter.loc["M1", "months_now"], by_meter.loc["M2", "months_now"]) == (2, 3), "per meter the periods are its rows"


def _lines(kg_by_year):
    rows = [("LE-01", f"{y}-{m:02d}", 1, "c", 1, None, "1", kg, None, None, False) for y, kg in kg_by_year.items() for m in range(1, 13)]
    return pd.DataFrame(rows, columns=["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded"]).astype({"supersedes_line_no": "Int64"})


@pytest.mark.parametrize("basis, mismatch", [("current", False), ("first_booked", True)])
def test_target_progress_oracle_a_baseline_that_matches_both_line_bases_is_read_as_current(basis, mismatch):
    """halvaro.esg.audit_targets.target_progress: when the stored baseline equals the scope total on both the current and the first booked basis (no restatements), baseline_basis says current, so
    basis_mismatch is false for basis=current and true for basis=first_booked; a baseline that matches neither gives baseline_basis neither and no mismatch."""
    L = _lines({2023: 50.0, 2025: 40.0})
    T = pd.DataFrame([(1, 1, 2023, 2030, 600.0, 300.0)], columns=["target_no", "scope", "baseline_year", "target_year", "baseline_value", "target_value"])
    row = esg.target_progress(T, L, "2026-03-01", basis=basis, context=M12).value.iloc[0]
    assert row["baseline_basis"] == "current" and bool(row["basis_mismatch"]) is mismatch
    other = esg.target_progress(T.assign(baseline_value=999.0), L, "2026-03-01", basis=basis, context=M12).value.iloc[0]
    assert other["baseline_basis"] == "neither" and bool(other["basis_mismatch"]) is False


def test_request_timeliness_oracle_a_request_received_on_the_as_of_day_is_in_and_an_answer_on_that_day_counts():
    """halvaro.esg.data_requests.request_timeliness: with as_of 2026-02-05 both requests are counted (n 2): the one received that day, and the one received on 2026-02-04 and answered on 2026-02-05, which counts as
    answered on time after 1 day (n_answered 1, mean_days_to_answer 1.0); with as_of 2026-02-04 the first request is out and the second is not answered yet. By hand."""
    R = pd.DataFrame({"cus_key": ["C1", "C1"], "request_no": [1, 2], "request_type": ["ghg", "ghg"], "received": ["2026-02-05", "2026-02-04"], "due": ["2026-02-20", "2026-02-20"],
                      "answered_date": [None, "2026-02-05"]})
    on_day = esg.request_timeliness(R, as_of="2026-02-05", context=M12).iloc[0]
    assert (on_day["n"], on_day["n_answered"], on_day["n_on_time"], on_day["mean_days_to_answer"]) == (2, 1, 1, 1.0)
    before = esg.request_timeliness(R, as_of="2026-02-04", context=M12).iloc[0]
    assert (before["n"], before["n_answered"], before["n_on_time"]) == (1, 0, 0)


def test_answer_pack_oracle_a_totals_row_without_a_year_is_refused_with_frame_error_like_any_other_null():
    """halvaro.esg.data_requests.answer_pack: a totals row whose year is null raises FrameError "the scope totals have nulls" (it raised ValueError from int(nan) before); the same row with a year of 2025 is
    answered, with year 2025 and months 12, by hand."""
    from halvaro.core import FrameError
    req = pd.DataFrame({"cus_key": ["C1"], "request_no": [1]})
    totals = pd.DataFrame({"le_key": ["ALL"], "year": [2025], "months": [12], "scope1": [10.0], "scope2_location": [5.0], "scope2_market": [4.0], "scope3": [100.0]})
    targets = pd.DataFrame(columns=["target_no", "scope", "baseline_year", "target_year", "reduction_percent", "basis", "status"])
    got = esg.answer_pack(req, totals, targets, context=M12)
    assert got["year"] == 2025 and got["months"] == 12 and got["scope1"] == 10.0
    with pytest.raises(FrameError, match="nulls"):
        esg.answer_pack(req, totals.assign(year=[float("nan")]), targets, context=M12)
