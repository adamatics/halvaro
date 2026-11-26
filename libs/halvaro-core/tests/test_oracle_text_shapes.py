"""Oracles of the text shapes of periods, keys and dates in halvaro.core (lane P1): a trailing newline, the year range of a period and a date text that is no date. Expected values are written by
hand or come from numpy and the date module."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core

SHAPES = ["2026-11\n", "2026-11 ", " 2026-11", "2026-11\r", "2026-11\n\n", "0000-05", "0000-01", "10000-01", "2026-1", "2026-13", "2026-00"]


@pytest.mark.parametrize("text", SHAPES)
def test_parse_period_oracle_only_a_year_a_dash_and_a_month_are_a_period(text):
    """halvaro.core.periods.parse_period: a final newline, blanks, the year 0000, five digit years and months out of range raise PeriodError (a final newline passed because `$` matches before it,
    and 0000-05 passed and failed later with ValueError); the period functions that read a text refuse the same texts."""
    with pytest.raises(core.PeriodError):
        core.parse_period(text)
    for call in (lambda: core.month_start(text), lambda: core.month_end(text), lambda: core.add_months(text, 1), lambda: core.compare_periods(text, "2026-11")):
        with pytest.raises(core.PeriodError):
            call()


def test_parse_period_oracle_the_first_and_last_valid_periods_still_work():
    """halvaro.core.periods.parse_period: 0001-01 and 9999-12 are periods and give the dates numpy gives; texts that worked keep their value."""
    assert core.parse_period("0001-01") == (1, 1) and core.parse_period("9999-12") == (9999, 12) and core.parse_period("2026-11") == (2026, 11)
    assert core.month_start("0001-01") == dt.date(1, 1, 1) and core.month_end("9999-12") == dt.date(9999, 12, 31)
    assert core.month_end("2024-02") == np.datetime64("2024-03-01").astype(dt.date) - dt.timedelta(days=1)


def test_add_months_oracle_a_result_outside_the_years_0001_to_9999_is_a_period_error():
    """halvaro.core.periods.add_months: a shift that leaves the years 0001 to 9999 raises PeriodError naming the shift (it returned 10000-01 and -001-12, which are no periods); the edge periods can be
    reached from inside, and a shift of 12000 months (1000 years) stays inside."""
    for start, n in (("9999-12", 1), ("0001-01", -1), ("0001-01", -13), ("9999-01", 12), ("2026-11", 100000), ("2026-11", -25000)):
        with pytest.raises(core.PeriodError, match="outside the years 0001 to 9999"):
            core.add_months(start, n)
    assert core.add_months("9999-12", -1) == "9999-11" and core.add_months("0001-01", 1) == "0001-02" and core.add_months("0001-12", -11) == "0001-01"
    assert core.add_months("9998-12", 12) == "9999-12" and core.add_months("0002-01", -12) == "0001-01" and core.add_months("2026-11", 12000) == "3026-11"


@pytest.mark.parametrize("text", ["WST-01\n", "WST-01 ", "GND-00012\n", "BUD-2025\n", "FC-2026-Q1\n", "GL-1000\n", "GL-1000 ", "EMP-000001\n"])
def test_key_functions_oracle_a_final_newline_is_not_part_of_a_key(text):
    """halvaro.core.keys.parse_label, parse_key, is_valid_key and check_key_column: natural labels, GL accounts and typed keys with a final newline or blank are refused (KeyFormatError, False,
    bad_format); the same texts without it are accepted. The `$` of the patterns matched before a final newline."""
    clean = text.rstrip("\n ")
    if not text.startswith("EMP-"):
        with pytest.raises(core.KeyFormatError):
            core.parse_label(text)
        assert core.parse_label(clean).text == clean
    else:
        with pytest.raises(core.KeyFormatError):
            core.parse_key(text)
        assert core.parse_key(clean).number == 1
    assert core.is_valid_key(text) is False
    import pandas as pd
    found = core.check_key_column(pd.DataFrame({"k": [text, clean]}), "k")
    assert [(r.key, r.rule) for r in found.itertuples()] == [(text, "bad_format")]


def test_caption_oracle_a_date_text_that_is_not_a_date_is_a_frame_error():
    """halvaro.core.theme.caption: a text that is not an ISO date (month 13, a day word, a day that does not exist, a date with a time, an empty text) raises FrameError naming the text (date.fromisoformat raised ValueError);
    a text, a date and a Timestamp of the same day give the same line."""
    for bad in ("2026-13-01", "tomorrow", "2026-11-31", "", "26-11-30", "2026/11/30", "2026-11-30T10:00"):
        with pytest.raises(core.FrameError, match="not an ISO date"):
            core.caption("basis", bad)
    assert core.caption("b", "2026-11-30") == core.caption("b", dt.date(2026, 11, 30)) == core.caption("b", pd.Timestamp("2026-11-30")) == "b, as of 2026-11-30"


def test_asof_join_oracle_a_period_with_a_final_newline_in_the_date_column_does_not_make_the_join_fail():
    """halvaro.core.periods.asof_join: a date given as a period uses its first day (`2026-11` is 2026-11-01); the same text with a final newline is no period for parse_period any more, and the join reads it as
    pandas reads a date (2026-11-01) instead of raising PeriodError, so the answer for it equals the answer for the clean period (by hand: the row valid from 2026-11-01 gives v = 2.0 for all three dates)."""
    left = pd.DataFrame({"k": ["A", "A", "A"], "d": ["2026-11", "2026-11\n", "2026-11-15"]})
    right = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-11-01"], "valid_to": ["2026-10-31", None], "v": [1, 2]})
    got = core.asof_join(left, right, "d", "k")
    assert got["v"].tolist() == [2.0, 2.0, 2.0] and got["d"].tolist() == ["2026-11", "2026-11\n", "2026-11-15"], "the left rows keep their order and their text"
    before = core.asof_join(left.iloc[[0]].assign(d="2026-10"), right, "d", "k")
    assert before["v"].tolist() == [1.0], "a period in the first row's range gets the first row"


@pytest.mark.parametrize("text, valid", [("EMP-000001", True), ("EMP-000001\n", False), ("EMP-000001 ", False), (" EMP-000001", False), ("TEAM-001", True), ("TEAM-001\n", False), ("EMP-1", False), ("emp-000001", False)])
def test_is_valid_key_oracle_a_typed_key_is_valid_only_without_a_newline_or_blank(text, valid):
    """halvaro.core.keys.is_valid_key: a typed key of the design (EMP with six digits, TEAM with three) is valid; the same text with a final newline, a blank before or after, too few digits or lower case is not. By hand."""
    assert core.is_valid_key(text) is valid
    assert core.is_valid_key(text, "EMP") is (valid and text.startswith("EMP"))
