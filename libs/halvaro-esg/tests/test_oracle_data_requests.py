"""Oracle tests of halvaro.esg.data_requests: answer_pack, request_timeliness.

answer_pack is checked on hand frames and on baseline sums carried through; request_timeliness against a python loop over the request rows with datetime dates and Fractions.
"""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
TARGET_COLS = ["target_no", "scope", "baseline_year", "target_year", "reduction_percent", "basis", "status", "baseline_value", "target_value"]


# ---- answer_pack


def _pack_inputs(**totals_over):
    req = pd.DataFrame([("CUS-000007", 12, "annual_questionnaire")], columns=["cus_key", "request_no", "request_type"])
    row = {"le_key": "ALL", "year": 2025, "basis": "current", "months": 12, "scope1": 1000.5, "scope2_location": 300.25, "scope2_market": 80.125, "scope3": 5000.0, **totals_over}
    targets = pd.DataFrame([(3, "2_market", 2023, 2030, 90.0, "absolute", "adopted", 400.0, 40.0), (1, "1", 2023, 2030, 42.0, "absolute", "adopted", 1000.0, 580.0),
                            (2, "2_location", 2023, 2030, 50.0, "absolute", "adopted", 600.0, 300.0)], columns=TARGET_COLS)
    return req, pd.DataFrame([row]), targets


def test_oracle_answer_pack_hand_example_numbers_targets_and_notes():
    """route: hand frames; every key of the pack written out from the numbers in the frames, the two scope 2 values kept apart, the targets as the rows given in target order."""
    req, totals, targets = _pack_inputs()
    kept = [x.copy(deep=True) for x in (req, totals, targets)]
    p = esg.answer_pack(req, totals, targets, context=M12)
    for got, want in zip((req, totals, targets), kept):
        pd.testing.assert_frame_equal(got, want)
    assert set(p) == {"request", "year", "months", "scope1", "scope2_location", "scope2_market", "scope3", "targets", "notes"}, "numbers only, no document text"
    assert p["request"] == ("CUS-000007", 12) and p["year"] == 2025 and p["months"] == 12
    assert (p["scope1"], p["scope2_location"], p["scope2_market"], p["scope3"]) == (1000.5, 300.25, 80.125, 5000.0)
    assert 300.25 + 80.125 not in [p[k] for k in ("scope1", "scope2_location", "scope2_market", "scope3")], "the two scope 2 methods are not added"
    assert p["targets"] == [{"target_no": 1, "scope": "1", "baseline_year": 2023, "target_year": 2030, "reduction_percent": 42.0, "basis": "absolute", "status": "adopted", "baseline_value": 1000.0, "target_value": 580.0},
                            {"target_no": 2, "scope": "2_location", "baseline_year": 2023, "target_year": 2030, "reduction_percent": 50.0, "basis": "absolute", "status": "adopted", "baseline_value": 600.0, "target_value": 300.0},
                            {"target_no": 3, "scope": "2_market", "baseline_year": 2023, "target_year": 2030, "reduction_percent": 90.0, "basis": "absolute", "status": "adopted", "baseline_value": 400.0, "target_value": 40.0}]
    assert p["notes"][0] == "totals are on the current basis: earlier years may have been restated"
    assert any("both methods" in n and "not added" in n for n in p["notes"]) and any("synthetic" in n for n in p["notes"])
    assert not any("months of data" in n for n in p["notes"]), "a full year has no part year note"
    assert all(isinstance(n, str) for n in p["notes"])
    assert isinstance(p["year"], int) and isinstance(p["months"], int) and all(isinstance(p[k], float) for k in ("scope1", "scope2_location", "scope2_market", "scope3"))


def test_oracle_answer_pack_basis_and_part_year_notes():
    """route: hand frames; the basis note per basis text and the part year note on each side of twelve months."""
    first = esg.answer_pack(*_pack_inputs(basis="first_booked"), context=M12)["notes"]
    assert first[0] == "totals are on the first_booked basis"
    req, totals, targets = _pack_inputs()
    nobasis = esg.answer_pack(req, totals.drop(columns="basis"), targets, context=M12)["notes"]
    assert nobasis[0] == "totals are on the unknown basis"
    eleven = esg.answer_pack(*_pack_inputs(months=11), context=M12)
    assert eleven["months"] == 11 and "the year has 11 months of data" in eleven["notes"]
    assert not any("months of data" in n for n in esg.answer_pack(*_pack_inputs(months=12), context=M12)["notes"])
    assert not any("months of data" in n for n in esg.answer_pack(*_pack_inputs(months=13), context=M12)["notes"])
    typed = esg.answer_pack(req, totals.astype({"months": float, "year": float}), targets, context=M12)
    assert typed["months"] == 12 and isinstance(typed["months"], int) and typed["year"] == 2025 and isinstance(typed["year"], int)
    one = esg.answer_pack(req, totals, targets.iloc[:1], context=M12)
    assert [t["target_no"] for t in one["targets"]] == [3]
    none = esg.answer_pack(req, totals, targets.iloc[:0], context=M12)
    assert none["targets"] == []


def test_oracle_answer_pack_refuses_what_is_not_one_request_and_one_company_row():
    """route: hand frames, each input the pack cannot be built from and the error it must raise."""
    req, totals, targets = _pack_inputs()
    with pytest.raises(FrameError, match="one request row and one totals row"):
        esg.answer_pack(pd.concat([req, req]), totals, targets, context=M12)
    with pytest.raises(FrameError, match="one request row and one totals row"):
        esg.answer_pack(req, pd.concat([totals, totals]), targets, context=M12)
    with pytest.raises(FrameError, match="whole company"):
        esg.answer_pack(req, totals.assign(le_key="LE-01"), targets, context=M12)
    for col in ("months", "scope1", "scope2_location", "scope2_market", "scope3"):
        with pytest.raises(FrameError, match="nulls"):
            esg.answer_pack(req, totals.assign(**{col: np.nan}), targets, context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        esg.answer_pack(req, totals.drop(columns="scope2_market"), targets, context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        esg.answer_pack(req, totals, targets.drop(columns="status"), context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        esg.answer_pack(req.drop(columns="request_no"), totals, targets, context=M12)


def test_oracle_answer_pack_every_route():
    """route: the hand frames, notes and refusals above. The release step (the baseline sums and target rows carried through) is a separate test that needs the closed repository."""
    test_oracle_answer_pack_hand_example_numbers_targets_and_notes()
    test_oracle_answer_pack_basis_and_part_year_notes()
    test_oracle_answer_pack_refuses_what_is_not_one_request_and_one_company_row()


# ---- request_timeliness


def _hand_requests():
    rows = [("CUS-1", 1, "2025-01-01", "2025-01-31", "2025-01-31", "type_a"),     # 30 days, on the due day
            ("CUS-1", 2, "2025-02-01", "2025-02-10", "2025-02-12", "type_a"),     # 11 days, two days late
            ("CUS-1", 3, "2025-03-01", "2025-03-31", None, "type_a"),             # not answered
            ("CUS-1", 4, "2025-04-01", "2025-04-30", "2025-04-21", "type_a"),     # 20 days
            ("CUS-2", 1, "2025-01-10", "2025-01-20", "2025-01-14", "type_b"),     # 4 days
            ("CUS-2", 2, "2025-02-10", "2025-02-20", "2025-02-17", "type_b"),     # 7 days
            ("CUS-3", 1, "2025-05-01", "2025-05-31", None, "type_c")]
    return pd.DataFrame(rows, columns=["cus_key", "request_no", "received", "due", "answered_date", "request_type"])


def test_oracle_request_timeliness_hand_example_per_type():
    """route: hand request rows whose days to answer and on-time answers are counted in the test; mean, median and shares worked out per type."""
    R = _hand_requests()
    before = R.copy(deep=True)
    r = esg.request_timeliness(R, context=M12)
    pd.testing.assert_frame_equal(R, before)
    assert list(r.columns) == ["request_type", "n", "n_answered", "mean_days_to_answer", "median_days_to_answer", "n_on_time", "share_on_time"]
    v = r.set_index("request_type")
    assert v.index.tolist() == ["type_a", "type_b", "type_c"]
    assert v.loc["type_a", ["n", "n_answered", "n_on_time"]].tolist() == [4, 3, 2]
    assert v.loc["type_a", "mean_days_to_answer"] == pytest.approx(61 / 3, abs=0.005) and v.loc["type_a", "mean_days_to_answer"] == 20.33
    assert v.loc["type_a", "median_days_to_answer"] == 20.0 and v.loc["type_a", "share_on_time"] == pytest.approx(0.6667, abs=1e-9)
    assert v.loc["type_b", ["n", "n_answered", "n_on_time"]].tolist() == [2, 2, 2]
    assert v.loc["type_b", "mean_days_to_answer"] == 5.5 and v.loc["type_b", "median_days_to_answer"] == 5.5 and v.loc["type_b", "share_on_time"] == 1.0
    assert v.loc["type_c", ["n", "n_answered", "n_on_time"]].tolist() == [1, 0, 0]
    assert v.loc[["type_c"], ["mean_days_to_answer", "median_days_to_answer", "share_on_time"]].isna().all().all(), "no answer, no average and no share"


def test_oracle_request_timeliness_as_of_day_boundaries():
    """route: hand request rows; answers after the day count as not answered, requests received after the day are left out, and both edges are inclusive."""
    R = _hand_requests()
    a = lambda d: esg.request_timeliness(R, as_of=d, context=M12).set_index("request_type")
    v = a("2025-02-05")
    assert v.loc["type_a", ["n", "n_answered", "n_on_time"]].tolist() == [2, 1, 1] and v.loc["type_a", "mean_days_to_answer"] == 30.0 and v.loc["type_a", "share_on_time"] == 1.0
    assert v.loc["type_b", ["n", "n_answered"]].tolist() == [1, 1] and v.loc["type_b", "mean_days_to_answer"] == 4.0 and "type_c" not in v.index, "later requests are left out"
    b = a("2025-02-15").loc["type_b"]
    assert b[["n", "n_answered", "n_on_time"]].tolist() == [2, 1, 1] and b.mean_days_to_answer == 4.0 and b.share_on_time == 1.0, "the answer of 2025-02-17 is not yet given on 2025-02-15"
    assert a("2025-01-31").loc["type_a", ["n", "n_answered"]].tolist() == [1, 1], "an answer on the day counts, a request received after the day does not"
    assert a("2025-01-30").loc["type_a", ["n", "n_answered"]].tolist() == [1, 0], "an answer the day after does not count"
    assert a("2025-02-01").loc["type_a", ["n", "n_answered"]].tolist() == [2, 1], "a request received on the day is in"
    assert a("2025-12-31").equals(esg.request_timeliness(R, context=M12).set_index("request_type"))
    assert esg.request_timeliness(R, as_of="2024-12-31", context=M12).empty


def test_oracle_request_timeliness_refuses_unreadable_rows():
    """route: hand request rows, each input the measure cannot be worked out from and the error it must raise."""
    R = _hand_requests()
    with pytest.raises(FrameError, match="answered before it was received"):
        esg.request_timeliness(R.assign(answered_date=["2024-01-01"] + list(R.answered_date[1:])), context=M12)
    with pytest.raises(FrameError, match="due before it was received"):
        esg.request_timeliness(R.assign(due=["2024-01-01"] + list(R.due[1:])), context=M12)
    with pytest.raises(FrameError, match="without a request_type"):
        esg.request_timeliness(R.assign(request_type=[None] + list(R.request_type[1:])), context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        esg.request_timeliness(pd.concat([R, R.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="numbers, not dates"):
        esg.request_timeliness(R.assign(received=20250101), context=M12)


def test_oracle_request_timeliness_every_route():
    """route: the hand examples, day boundaries and refusals above. The release step (the tampered baseline requests) is a separate test that needs the closed repository."""
    test_oracle_request_timeliness_hand_example_per_type()
    test_oracle_request_timeliness_as_of_day_boundaries()
    test_oracle_request_timeliness_refuses_unreadable_rows()
