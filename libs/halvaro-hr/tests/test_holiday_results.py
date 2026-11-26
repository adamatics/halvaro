"""Typed results of the holiday functions: the functions return the models (issue #233, halvaro-hr 1.0), the models carry description and unit, and to_frame() gives the frame of before (issue #196, F3)."""
import copy
import dataclasses
import datetime as dt
import pickle
from collections.abc import Sequence

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import halvaro.hr as hr
from halvaro.core import FrameError
from halvaro.hr.holiday_results import RESULT_CONTAINERS, RESULT_MODELS, UNITS, ColumnSpec

D = dt.date


def _ent(rows):
    return pd.DataFrame(rows, columns=["emp_key", "holiday_year", "entitlement_days", "carried_in_days", "carry_over_agreement", "opening_balance"])


def _acc(rows):
    return pd.DataFrame(rows, columns=["emp_key", "holiday_year", "period", "accrued_days", "taken_days"])


ENT = _ent([("EMP-1", "2025/26", 25.0, 0.0, False, False), ("EMP-1", "2026/27", 25.0, 4.0, True, False), ("EMP-2", "2026/27", 25.0, 0.0, False, True), ("G1", "2026", 30.0, 2.5, False, False)])
ACC = _acc([("EMP-1", "2025/26", "2026-07", 2.0, 0.0), ("EMP-1", "2025/26", "2026-08", 2.0, 1.0), ("EMP-1", "2026/27", "2026-09", 2.0, 0.0), ("EMP-2", "2026/27", "2026-09", 2.0, 0.0),
            ("G1", "2026", "2026-01", 2.5, 0.0)])
EMP = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "G1"], "hire_date": [D(2020, 1, 1), D(2020, 1, 1), D(2020, 1, 1)], "leave_date": [None, None, None]})
LEAVE = pd.DataFrame({"emp_key": ["EMP-1"], "leave_type": ["holiday"], "days": [1], "end": [D(2026, 8, 20)]})


def _results():
    ledger = hr.holiday_ledger(ENT, ACC)
    return {"holiday_ledger": ledger, "carry_over_position": hr.carry_over_position(ENT), "carry_over_projection": hr.carry_over_projection(ledger, ENT),
            "accrual_expected": hr.accrual_expected(EMP, LEAVE.iloc[0:0].assign(start=pd.Series(dtype=object)), ACC, D(2026, 11, 30)),
            "leave_vs_ledger": hr.leave_vs_ledger(LEAVE, ACC, D(2026, 11, 30)), "high_carry_over": hr.high_carry_over(ENT, threshold=1.0)}


def _frames():
    return {name: result.to_frame() for name, result in _results().items()}


def test_every_model_field_has_a_description_and_a_unit_from_the_vocabulary():
    assert set(RESULT_MODELS) == {"holiday_balance", "holiday_ledger", "carry_over_position", "carry_over_projection", "accrual_expected", "leave_vs_ledger", "high_carry_over"}
    for name, model in RESULT_MODELS.items():
        specs = model.columns()
        assert specs and all(isinstance(c, ColumnSpec) for c in specs), name
        for c in specs:
            assert c.description.strip() and c.description.strip().endswith("."), f"{name}.{c.name}: description"
            assert c.unit in UNITS, f"{name}.{c.name}: unit {c.unit!r}"
        assert len({c.name for c in specs}) == len(specs)


def test_the_columns_of_each_frame_form_are_the_fields_of_its_model_in_order():
    for name, frame in _frames().items():
        assert list(frame.columns) == [c.name for c in RESULT_MODELS[name].columns()], name


def test_from_frame_gives_one_frozen_model_per_row_and_turns_missing_values_into_none():
    frames = _frames()
    rows = hr.LedgerRow.from_frame(frames["holiday_ledger"])
    assert len(rows) == len(frames["holiday_ledger"]) and rows[0].emp_key == "EMP-1" and rows[0].period == "2026-07" and rows[0].balance == 2.0 and rows[0].negative is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        rows[0].balance = 0.0                                                      # type: ignore[misc]
    pos = {r.emp_key: r for r in hr.CarryOverRow.from_frame(frames["carry_over_position"]) if r.holiday_year == "2026/27"}
    assert pos["EMP-2"].cap is None and pos["EMP-2"].headroom is None and pos["EMP-2"].opening_balance and pos["EMP-2"].deadline is None
    de = [r for r in hr.CarryOverRow.from_frame(frames["carry_over_position"]) if r.country == "DE"][0]
    assert isinstance(de.deadline, dt.date)
    proj = {(r.emp_key, r.holiday_year): r for r in hr.CarryOverProjectionRow.from_frame(frames["carry_over_projection"])}
    assert proj[("EMP-1", "2025/26")].stored_carry_in == 4.0 and proj[("EMP-1", "2025/26")].matches is not None and proj[("EMP-1", "2026/27")].stored_carry_in is None
    assert proj[("EMP-1", "2026/27")].matches is None and proj[("EMP-1", "2026/27")].difference is None
    acc = hr.AccrualRow.from_frame(frames["accrual_expected"])
    assert any(r.missing_month and r.accrued_days is None and r.difference is None for r in acc) and any(not r.missing_month and r.accrued_days is not None for r in acc)
    assert [r.emp_key for r in hr.HighCarryOverRow.from_frame(frames["high_carry_over"])] == ["EMP-1"]
    assert hr.LeaveLedgerRow.from_frame(frames["leave_vs_ledger"])[0].leave_days == 1


def test_from_frame_names_the_missing_column():
    with pytest.raises(FrameError, match="lacks column"):
        hr.LedgerRow.from_frame(_frames()["holiday_ledger"].drop(columns="balance"))


def test_holiday_balance_model_round_trips_the_dict_and_refuses_other_keys():
    model = hr.holiday_balance(ENT, ACC, "EMP-1", "2026/27", D(2026, 9, 30))
    assert isinstance(model, hr.HolidayBalance), "the function returns the model"
    result = model.to_dict()
    assert hr.HolidayBalance.from_dict(result) == model and dataclasses.asdict(model) == result and model.balance_days == 6.0
    assert list(result) == [c.name for c in hr.HolidayBalance.columns()], "to_dict has the fields in order"
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.balance_days = 0.0                                                   # type: ignore[misc]
    with pytest.raises(FrameError, match="unknown key"):
        hr.HolidayBalance.from_dict({**result, "extra": 1})
    with pytest.raises(FrameError, match="missing"):
        hr.HolidayBalance.from_dict({k: v for k, v in result.items() if k != "balance_days"})


def test_the_return_types_are_pinned():
    assert isinstance(hr.holiday_year_label("DK", D(2026, 9, 1)), str) and isinstance(hr.holiday_year_bounds("2026/27"), tuple), "these two return what they returned before"
    assert isinstance(hr.holiday_balance(ENT, ACC, "EMP-1", "2026/27", D(2026, 9, 30)), hr.HolidayBalance)
    expected = {"holiday_ledger": hr.LedgerRows, "carry_over_position": hr.CarryOverRows, "carry_over_projection": hr.CarryOverProjectionRows, "accrual_expected": hr.AccrualRows,
                "leave_vs_ledger": hr.LeaveLedgerRows, "high_carry_over": hr.HighCarryOverRows}
    assert RESULT_CONTAINERS == expected and set(RESULT_CONTAINERS) == set(RESULT_MODELS) - {"holiday_balance"}
    for name, result in _results().items():
        assert type(result) is expected[name] and isinstance(result, Sequence) and not isinstance(result, pd.DataFrame), name
        assert all(type(row) is RESULT_MODELS[name] for row in result) and len(result) > 0, name
        assert type(result).model is RESULT_MODELS[name], name


# ---- the containers (issue #233) -----------------------------------------------------------------------------------------------------------------------
def test_a_container_is_an_immutable_sequence_of_frozen_rows():
    ledger = hr.holiday_ledger(ENT, ACC)
    assert isinstance(ledger, Sequence) and len(ledger) == 5 and ledger[0].emp_key == "EMP-1" and ledger[-1].emp_key == "G1" and [r.period for r in ledger][:2] == ["2026-07", "2026-08"]
    assert isinstance(ledger[1:3], tuple) and len(ledger[1:3]) == 2 and ledger[0] in ledger and list(reversed(ledger))[0] is ledger[-1]
    for attempt in (lambda: setattr(ledger, "x", 1), lambda: setattr(ledger, "_rows", ()), lambda: delattr(ledger, "_rows")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            attempt()
    for absent in ("append", "extend", "sort", "__setitem__", "__delitem__"):
        assert not hasattr(ledger, absent), absent
    with pytest.raises(TypeError):
        ledger[0] = ledger[1]                                                      # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ledger[0].balance = 0.0                                                    # type: ignore[misc]
    assert ledger == hr.holiday_ledger(ENT, ACC) and hash(ledger) == hash(hr.holiday_ledger(ENT, ACC)) and ledger != hr.holiday_ledger(ENT, ACC.iloc[:2])
    assert ledger != tuple(ledger), "a container equals only a container of its own type"
    assert pickle.loads(pickle.dumps(ledger)) == ledger and copy.deepcopy(ledger) == ledger and copy.copy(ledger) == ledger


def test_to_frame_gives_the_columns_in_order_with_the_dtypes_of_the_declared_types_and_is_a_copy():
    projection = hr.carry_over_projection(hr.holiday_ledger(ENT, ACC), ENT)
    frame = projection.to_frame()
    assert list(frame.columns) == [c.name for c in hr.CarryOverProjectionRow.columns()]
    assert str(frame.matches.dtype) == "boolean" and frame.cap.dtype == "float64" and frame.emp_key.dtype == object and frame.stored_carry_in.isna().any() and frame.matches.isna().any()
    frame.loc[0, "emp_key"] = "CHANGED"
    assert projection[0].emp_key == "EMP-1" and projection.to_frame().emp_key.iloc[0] == "EMP-1", "changing the frame changes nothing in the container"
    flags = hr.holiday_ledger(ENT, ACC).to_frame()
    assert all(flags[c].dtype == bool for c in ("opening_balance", "missing_entitlement", "negative"))
    position = hr.carry_over_position(ENT).to_frame()
    assert position.deadline.dtype == object and position.deadline.isna().sum() == 3 and position.cap.isna().sum() == 1


def test_to_frame_equals_the_frame_the_function_returned_before():
    """The expected frames are written by hand with the dtypes of the pandas frames of halvaro-hr 0.2."""
    ledger = hr.holiday_ledger(_ent([("EMP-1", "2026/27", 25.0, 1.0, False, False)]), _acc([("EMP-1", "2026/27", "2026-09", 2.0, 0.0), ("EMP-1", "2026/27", "2026-10", 2.0, 6.0)]))
    want = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"], "accrued_days": [2.0, 2.0], "taken_days": [0.0, 6.0],
                         "balance": [3.0, -1.0], "opening_balance": [False, False], "missing_entitlement": [False, False], "negative": [False, True], "legal_status": ["VERIFY", "VERIFY"]})
    assert_frame_equal(ledger.to_frame(), want)
    high = hr.high_carry_over(_ent([("A", "2026/27", 25.0, 10.0, True, False)]))
    want = pd.DataFrame({"emp_key": ["A"], "holiday_year": ["2026/27"], "carried_in_days": [10.0], "carry_over_agreement": [True], "legal_status": ["VERIFY"]})
    assert_frame_equal(high.to_frame(), want)
    from halvaro.core import fact      # lane F3 (issue #543), approved edit: the status of the fact, whichever it is
    status = fact("policy.holiday.high_carry_over_days").status
    assert high.to_frame().attrs == {"policy_status": {"policy.holiday.high_carry_over_days": status}}
    assert dict(high.policy_status) == {"policy.holiday.high_carry_over_days": status}
    given = hr.high_carry_over(_ent([("A", "2026/27", 25.0, 10.0, True, False)]), threshold=3.0)
    assert dict(given.policy_status) == {} and given.to_frame().attrs == {}, "a number of the caller has no policy status"
    with pytest.raises(TypeError):
        high.policy_status["x"] = "y"                                              # type: ignore[index]


def test_every_result_goes_from_the_frame_to_the_model_and_back_unchanged():
    for name, result in _results().items():
        container = type(result)
        frame = result.to_frame()
        assert container.from_frame(frame) == result, name
        assert_frame_equal(container.from_frame(frame).to_frame(), frame)
        assert tuple(result) == tuple(RESULT_MODELS[name].from_frame(frame)), name


def test_a_container_built_from_the_models_gives_the_frame_of_those_models():
    rows = [hr.LedgerRow("EMP-9", "2026/27", "2026-09", 2.0, 1.0, 1.0, False, False, False, "VERIFY"), hr.LedgerRow("EMP-9", "2026/27", "2026-10", 2.0, 5.0, -2.0, False, False, True, "VERIFY")]
    ledger = hr.LedgerRows(rows)
    frame = ledger.to_frame()
    assert list(frame.emp_key) == ["EMP-9", "EMP-9"] and list(frame.balance) == [1.0, -2.0] and list(frame.negative) == [False, True] and tuple(ledger) == tuple(rows)
    assert hr.LedgerRows(iter(rows)) == ledger, "any iterable of rows"
    assert hr.LedgerRows() == hr.LedgerRows([]) and len(hr.LedgerRows()) == 0
    with pytest.raises(FrameError, match="LedgerRow rows only"):
        hr.LedgerRows([hr.HighCarryOverRow("EMP-1", "2026/27", 9.0, True, "VERIFY")])      # type: ignore[list-item]
    with pytest.raises(FrameError, match="lacks column"):
        hr.LedgerRows.from_frame(frame.drop(columns="balance"))


def test_an_empty_container_still_has_the_columns_and_the_dtypes():
    for name, container in RESULT_CONTAINERS.items():
        frame = container().to_frame()
        assert frame.empty and list(frame.columns) == [c.name for c in RESULT_MODELS[name].columns()], name
    assert str(hr.CarryOverProjectionRows().to_frame().matches.dtype) == "boolean" and hr.LedgerRows().to_frame().balance.dtype == "float64"
    assert hr.carry_over_projection(hr.holiday_ledger(ENT.iloc[:0], ACC.iloc[:0]), ENT.iloc[:0]) == hr.CarryOverProjectionRows()


def test_the_projection_reads_the_result_of_the_ledger_or_a_frame_with_the_same_answer():
    ledger = hr.holiday_ledger(ENT, ACC)
    assert hr.carry_over_projection(ledger, ENT) == hr.carry_over_projection(ledger.to_frame(), ENT)
    with pytest.raises(FrameError, match="lacks column"):
        hr.carry_over_projection(ledger.to_frame().drop(columns="balance"), ENT)


def test_integer_days_in_a_frame_come_back_as_floats_in_the_models():
    leave = hr.leave_vs_ledger(LEAVE, ACC, D(2026, 11, 30))
    assert all(isinstance(r.leave_days, float) and isinstance(r.taken_days, float) for r in leave) and leave.to_frame().leave_days.dtype == "float64"
