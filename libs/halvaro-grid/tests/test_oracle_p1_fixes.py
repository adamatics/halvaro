"""Oracles of lane P1 for halvaro-grid: mixed timestamp forms, what the docstrings of element_peak_load, grid_strain_answer and strained_elements state, and the inspection rule read from the proposed
facts policy.grid.inspection_*. Expected values are written by hand or computed with a plain loop."""
import re
from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
import halvaro.grid.maintenance as maintenance
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")


def test_outdoor_at_oracle_timestamps_in_mixed_forms_are_read_one_by_one():
    """halvaro.grid.series.outdoor_at: a list or Series of timestamp texts with and without seconds and with a T separator is read value by value (pandas fixed the format from the first text and raised
    FrameError); the result equals the one for the same instants as datetimes, and the index of a Series is kept."""
    obs = pd.DataFrame({"station_key": "WST-01", "ts": pd.to_datetime(["2026-01-01 10:00", "2026-01-01 11:00"]), "temp_c": [-3.0, -5.0]})
    mixed = ["2026-01-01 10:00", "2026-01-01 10:30:30", "2026-01-01T11:15:00", "2026-01-01 09:59"]
    same = pd.to_datetime(["2026-01-01 10:00:00", "2026-01-01 10:30:30", "2026-01-01 11:15:00", "2026-01-01 09:59:00"])
    got = grid.outdoor_at(obs, mixed, "WST-01", context=M12)
    want = grid.outdoor_at(obs, list(same), "WST-01", context=M12)
    assert got.tolist()[:3] == [-3.0, -3.0, -5.0] and np.isnan(got.iloc[3]), "before the first observation: null; within 1.5 hours of the last one: its value"
    pd.testing.assert_series_equal(got, want)
    s = pd.Series(mixed, index=list("wxyz"))
    assert grid.outdoor_at(obs, s, "WST-01", context=M12).index.tolist() == list("wxyz")
    with pytest.raises(FrameError, match="not a timestamp"):
        grid.outdoor_at(obs, ["2026-01-01 10:00", "tomorrow"], "WST-01", context=M12)


def _daily(rows):
    return pd.DataFrame(rows, columns=["sns_key", "date", "max", "availability_pct"])


def test_element_peak_load_oracle_without_a_window_the_rows_passed_in_decide_the_completeness():
    """halvaro.grid.assets.element_peak_load: without `window` the window runs from the first to the last day of the daily rows passed in, a day without a row counts as zero availability, so the same
    sensor is complete on rows of two consecutive days (1.0) and at 0.75 when a row for 4 January is added and none for 3 January; with window 1 to 2 January the extra row changes nothing."""
    sensor = pd.DataFrame({"sns_key": ["S1"], "net_key": ["N1"], "rated_value": [100.0], "install_date": ["2025-01-01"], "sensor_type": ["load_percent"]})
    two = _daily([("S1", "2026-01-01", 60.0, 100.0), ("S1", "2026-01-02", 70.0, 100.0)])
    four = pd.concat([two, _daily([("S1", "2026-01-04", 50.0, 100.0)])], ignore_index=True)
    a = grid.element_peak_load(sensor, two, context=M12).iloc[0]
    b = grid.element_peak_load(sensor, four, context=M12).iloc[0]
    assert (a["completeness"], a["peak_percent"], bool(a["valid"])) == (1.0, 70.0, True)
    assert (b["completeness"], bool(b["valid"])) == (0.75, False), "four days from 1 to 4 January, three rows"
    c = grid.element_peak_load(sensor, four, window=("2026-01-01", "2026-01-02"), context=M12).iloc[0]
    assert c["completeness"] == 1.0


@pytest.mark.parametrize("frame, word", [("critical_issued", "stock_units"), ("zone_summary", "order_count"), ("part_use", "unit_cost"), ("strained", "intent"), ("part_use", "po_ref"), ("zone_summary", "orders"), ("critical_issued", "unit_price"),
                                       ("strained", "amount"), ("part_use", "money_value"), ("zone_summary", "credit_note")])
def test_grid_strain_answer_oracle_a_forbidden_word_in_any_of_the_four_frames_is_refused(frame, word):
    """halvaro.grid.recipes.grid_strain_answer: a column that holds one of the words stock, po, order, orders, price, cost, amount, money, credit or intent in its name raises FrameError naming the frame and the column, whichever of the four input frames carries it;
    the same frames without it give the two key lists."""
    frames = {"strained": pd.DataFrame({"net_key": ["N1"], "strained": [True], "load_strained": [True]}), "zone_summary": pd.DataFrame({"zone_key": ["Z1"], "n_elements": [3], "n_strained": [1]}),
              "part_use": pd.DataFrame({"itm_key": ["ITM-1"], "units": [2]}), "critical_issued": pd.DataFrame({"itm_key": ["ITM-1", "ITM-2"], "units": [2, 0]})}
    ok = grid.grid_strain_answer(frames["strained"], frames["zone_summary"], frames["part_use"], frames["critical_issued"], context=M12)
    assert ok.item_keys == ("ITM-1",) and ok.zone_keys == ("Z1",), "an item never issued is not asked about"
    frames[frame] = frames[frame].assign(**{word: 1})
    with pytest.raises(FrameError, match=rf"{frame}\.{word}"):
        grid.grid_strain_answer(frames["strained"], frames["zone_summary"], frames["part_use"], frames["critical_issued"], context=M12)


def test_strained_elements_oracle_an_element_one_day_short_of_the_age_limit_counts_as_age_strained():
    """halvaro.grid.assets.strained_elements: the age is the age of element_age rounded to two decimals, so an element 14609 days old (39.9973 years) is age strained at the limit of 40 years and one
    14600 days old (39.97 years) is not; this follows from the docstring and is written down so that a change to the comparison is a decision."""
    as_of = pd.Timestamp("2026-06-30")
    ge = pd.DataFrame({"net_key": ["N1", "N2"], "element_type": ["valve", "valve"], "status": ["in_service"] * 2, "install_year": [1986, 1986], "condition_class": ["A", "A"], "cus_key": [None, None],
                       "zone_key": ["Z1", "Z1"], "commissioned_date": [(as_of - pd.Timedelta(days=14609)).date().isoformat(), (as_of - pd.Timedelta(days=14600)).date().isoformat()]})
    peaks = pd.DataFrame({"net_key": ["N1", "N2"], "peak_percent": [10.0, 10.0], "valid": [True, True]})
    r = grid.strained_elements(peaks, ge, as_of=as_of, context=M12).set_index("net_key")
    assert r.loc["N1", "age_years"] == 40.0 and bool(r.loc["N1", "age_strained"]) is True
    assert r.loc["N2", "age_years"] == 39.97 and bool(r.loc["N2", "age_strained"]) is False


RULE_CYCLE = {"A": 120, "B": 84, "C": 54, "D": 32, "E": 26}
RULE_MULT = {"pipe_segment": 1.25, "valve": 1.2, "heat_exchanger_station": 1.0, "cable_section": 1.0, "transformer_station": 0.9, "substation": 0.7, "pump_station": 0.7}
Fake = namedtuple("Fake", "value status")


def test_the_inspection_facts_oracle_hold_the_values_the_rule_had_typed():
    """halvaro.grid.maintenance.inspection_interval_check: the twelve proposed facts policy.grid.inspection_cycle_months.A to E and policy.grid.inspection_type_multiplier.<type> are proposed and
    equal the cycle and the multipliers that the function and its first oracle had typed, so reading the facts does not change a result."""
    for c, v in RULE_CYCLE.items():
        f = fact(f"policy.grid.inspection_cycle_months.{c}")
        assert f.status == "proposed" and f.value == v, c
    for t, v in RULE_MULT.items():
        f = fact(f"policy.grid.inspection_type_multiplier.{t}")
        assert f.status == "proposed" and f.value == v, t


def _plans(rows):
    return pd.DataFrame(rows, columns=["net_key", "plan_no", "plan_type", "interval_months", "valid_from"])


def test_inspection_interval_check_oracle_the_rule_is_read_from_the_facts(monkeypatch):
    """halvaro.grid.maintenance.inspection_interval_check: with the facts as they are, each plan is expected at the cycle of its class times the multiplier of its type, rounded half to even (a plain loop
    over the typed rule); with the fact of class A replaced by a stand in of 10 months the expected interval of class A elements follows it, and the keywords still override the facts."""
    ge = pd.DataFrame({"net_key": ["N1", "N2", "N3"], "condition_class": ["A", "D", "E"], "element_type": ["valve", "substation", "pipe_segment"]})
    mp = _plans([("N1", 1, "condition_inspection", 144, "2026-01-01"), ("N2", 1, "condition_inspection", 22, "2026-01-01"), ("N3", 1, "condition_inspection", 33, "2026-01-01")])
    got = grid.inspection_interval_check(mp, ge, context=M12).set_index("net_key")
    want = {k: float(round(RULE_CYCLE[c] * RULE_MULT[t])) for k, c, t in zip(ge.net_key, ge.condition_class, ge.element_type)}
    assert want == {"N1": 144.0, "N2": 22.0, "N3": 32.0}, "120 x 1.2, 32 x 0.7 = 22.4 and 26 x 1.25 = 32.5 (rounded half to even)"
    assert got.index.tolist() == ["N3"] and got.loc["N3", "expected_months"] == 32.0, "only the plan of N3 deviates (33 against 32)"
    monkeypatch.setattr(maintenance, "fact", lambda fid: Fake(10, "decided") if fid == "policy.grid.inspection_cycle_months.A" else fact(fid))
    moved = grid.inspection_interval_check(mp, ge, context=M12).set_index("net_key")
    assert moved.loc["N1", "expected_months"] == 12.0 and moved.loc["N1", "interval_months"] == 144, "10 x 1.2 = 12 now, the plan says 144"
    kw = grid.inspection_interval_check(mp, ge, cycle_months={"A": 100, "D": 32, "E": 26}, context=M12).set_index("net_key")
    assert kw.loc["N1", "expected_months"] == 120.0, "a keyword overrides the fact"


def test_outdoor_at_oracle_timestamps_of_a_string_series_in_mixed_forms_are_read_one_by_one():
    """halvaro.grid.series.outdoor_at: the same mixed texts as a Series of the `string` dtype (not `object`) are read value by value too and give the same answer as the object Series."""
    obs = pd.DataFrame({"station_key": "WST-01", "ts": pd.to_datetime(["2026-01-01 10:00", "2026-01-01 11:00"]), "temp_c": [-3.0, -5.0]})
    texts = ["2026-01-01 10:00", "2026-01-01 10:30:30", "2026-01-01T11:15:00"]
    as_string = pd.Series(texts, dtype="string", index=list("abc"))
    as_object = pd.Series(texts, dtype=object, index=list("abc"))
    got = grid.outdoor_at(obs, as_string, "WST-01", context=M12)
    assert got.tolist() == [-3.0, -3.0, -5.0]
    pd.testing.assert_series_equal(got, grid.outdoor_at(obs, as_object, "WST-01", context=M12))


def test_inspection_interval_check_oracle_the_type_multiplier_keyword_overrides_the_facts_and_the_facts_are_declared():
    """halvaro.grid.maintenance.inspection_interval_check: a type_multiplier keyword replaces the multipliers of the facts (valve 1.0 instead of 1.2: 120 x 1.0 = 120 months, not 144), and the registry lists the twelve
    facts policy.grid.inspection_cycle_months.A to E and policy.grid.inspection_type_multiplier.<type> as the facts the function reads."""
    ge = pd.DataFrame({"net_key": ["N1"], "condition_class": ["A"], "element_type": ["valve"]})
    mp = _plans([("N1", 1, "condition_inspection", 144, "2026-01-01")])
    assert grid.inspection_interval_check(mp, ge, context=M12).empty, "144 = 120 x 1.2 from the facts"
    kw = grid.inspection_interval_check(mp, ge, type_multiplier={"valve": 1.0}, context=M12).set_index("net_key")
    assert kw.loc["N1", "expected_months"] == 120.0 and kw.loc["N1", "interval_months"] == 144
    from halvaro.core import registry
    meta = registry.registered()["halvaro.grid.maintenance.inspection_interval_check"]
    want = {f"policy.grid.inspection_cycle_months.{c}" for c in "ABCDE"} | {f"policy.grid.inspection_type_multiplier.{t}" for t in
            ("pipe_segment", "valve", "heat_exchanger_station", "cable_section", "transformer_station", "substation", "pump_station")}
    assert set(meta.facts) == want and len(want) == 12


def test_outdoor_at_oracle_texts_that_pandas_read_before_give_the_same_instants_and_zones_are_refused():
    """halvaro.grid.series.outdoor_at: a list of day first texts that pandas read before ("13/04/2026" first, so both are day first) gives the instants of 13 and 3 April as before; month first texts after a day first
    text and unreadable words raise FrameError; a text with a time zone, and a text that mixes zoned and unzoned values, raise FrameError."""
    import warnings
    obs = pd.DataFrame({"station_key": "WST-01", "ts": pd.to_datetime(["2026-04-03 00:00", "2026-04-13 00:00"]), "temp_c": [1.0, 2.0]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        got = grid.outdoor_at(obs, ["13/04/2026", "03/04/2026"], "WST-01", context=M12)
    assert got.tolist() == [2.0, 1.0], "13 April and 3 April, as pandas read the list before"
    for bad in (["03/04/2026", "13/04/2026"], ["2026-01-01 10:00", "tomorrow"], ["2026-01-01T10:00:00+01:00"], ["2026-01-01T10:00:00+01:00", "2026-01-01 10:00"]):
        with pytest.raises(FrameError):
            grid.outdoor_at(obs, bad, "WST-01", context=M12)
