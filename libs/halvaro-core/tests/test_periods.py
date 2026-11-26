"""C1: periods, effective dating, as-of join, release identity."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core


def test_period_helpers():
    assert core.parse_period("2026-11") == (2026, 11) and core.period_of(dt.date(2026, 2, 28)) == "2026-02"
    assert core.month_start("2024-02") == dt.date(2024, 2, 1) and core.month_end("2024-02") == dt.date(2024, 2, 29)
    assert core.month_end("2026-12") == dt.date(2026, 12, 31)
    assert core.add_months("2026-11", 3) == "2027-02" and core.add_months("2026-01", -1) == "2025-12" and core.add_months("2026-01", 0) == "2026-01"
    assert [core.compare_periods(a, b) for a, b in (("2026-01", "2026-02"), ("2026-02", "2026-02"), ("2027-01", "2026-12"))] == [-1, 0, 1]
    assert core.period_range("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"] and core.period_range("2026-02", "2026-01") == []
    for bad in ("2026-13", "2026-1", "26-01", "", None, "2026-00"):
        with pytest.raises(core.PeriodError):
            core.parse_period(bad)


def test_year_of_for_holiday_and_fiscal_years():
    assert [core.year_of(p, 9) for p in ("2026-08", "2026-09", "2026-12", "2027-01", "2027-08")] == [2025, 2026, 2026, 2026, 2026]
    assert core.year_of("2026-03", 1) == 2026
    with pytest.raises(core.PeriodError):
        core.year_of("2026-03", 13)


def _terms():
    return pd.DataFrame({"emp": ["a", "a", "b"], "valid_from": pd.to_datetime(["2023-01-01", "2024-01-01", "2023-06-01"]),
                         "valid_to": pd.to_datetime(["2023-12-31", None, None]), "grade": [1, 2, 3]})


def test_rows_on_is_inclusive_at_both_ends():
    t = _terms()
    assert sorted(core.rows_on(t, dt.date(2023, 12, 31))["grade"]) == [1, 3]
    assert sorted(core.rows_on(t, dt.date(2024, 1, 1))["grade"]) == [2, 3]
    assert core.rows_on(t, dt.date(2022, 12, 31)).empty
    with pytest.raises(core.AmbiguousKey):
        core.rows_on(pd.concat([t, t.iloc[[1]]]), dt.date(2024, 6, 1), key="emp")


def test_check_contiguity_rules_day_after():
    def rules(rows):
        df = pd.DataFrame(rows, columns=["k", "valid_from", "valid_to"])
        return sorted(core.check_contiguity(df, "k").rule)

    ok = [("a", "2023-01-01", "2023-12-31"), ("a", "2024-01-01", None)]
    assert rules(ok) == []
    assert rules([("a", "2023-01-01", "2023-12-31"), ("a", "2024-01-02", None)]) == ["gap"]
    assert rules([("a", "2023-01-01", "2023-12-31"), ("a", "2023-12-31", None)]) == ["overlap"]
    assert rules([("a", "2023-01-01", "2022-12-31")]) == ["reversed"]
    assert rules([("a", "2023-01-01", None), ("a", "2024-01-01", None)]) == ["open_not_last", "two_open", "two_open"]
    assert rules([("a", "2023-01-01", None), ("a", "2024-01-01", "2024-12-31")]) == ["open_not_last"]
    assert rules([("a", "2023-01-01", "2023-12-31"), ("b", "2023-01-01", None), ("a", "2024-01-01", None)]) == []
    touching = pd.DataFrame([("a", "2023-01-01", "2023-12-31"), ("a", "2023-12-31", None)], columns=["k", "valid_from", "valid_to"])
    assert len(core.check_contiguity(touching, "k", convention="touching")) == 0
    with pytest.raises(core.PeriodError):
        core.check_contiguity(touching, "k", convention="weekly")


def test_asof_join_selects_by_date_and_period():
    left = pd.DataFrame({"emp": ["a", "a", "b", "c"], "when": [dt.date(2023, 12, 31), dt.date(2024, 1, 1), dt.date(2023, 5, 31), dt.date(2024, 1, 1)], "x": [1, 2, 3, 4]})
    out = core.asof_join(left, _terms().rename(columns={"emp": "emp"}), "when", "emp")
    assert out["grade"].tolist()[:2] == [1, 2] and pd.isna(out["grade"][2]) and pd.isna(out["grade"][3])
    assert out["x"].tolist() == [1, 2, 3, 4], "left order and rows are kept"
    per = pd.DataFrame({"emp": ["a", "a"], "when": ["2023-12", "2024-01"]})
    assert core.asof_join(per, _terms(), "when", "emp")["grade"].tolist() == [1, 2], "a period uses the first day of the month"
    clash = pd.DataFrame({"emp": ["a"], "when": [dt.date(2024, 1, 1)], "grade": [9]})
    assert core.asof_join(clash, _terms(), "when", "emp").columns.tolist().count("grade_r") == 1
    overlapping = pd.concat([_terms(), _terms().iloc[[1]].assign(valid_from=pd.Timestamp("2024-06-01"))])
    with pytest.raises(core.PeriodError):
        core.asof_join(left, overlapping, "when", "emp")


def _release(name="baseline", now="2026-11-30", seed=42):
    return pd.DataFrame([{"release": name, "now": now, "generated_at": pd.Timestamp(now), "base_seed": seed, "increment": 0}])


def test_release_now_agrees_or_raises():
    info = core.release_now({"hr": _release(), "finance": _release()})
    assert (info.release, info.now, info.base_seed, info.increment) == ("baseline", dt.date(2026, 11, 30), 42, 0)
    with pytest.raises(core.ReleaseMismatch, match="release"):
        core.release_now({"hr": _release(), "finance": _release("i1")})
    with pytest.raises(core.ReleaseMismatch, match="base_seed"):
        core.release_now({"hr": _release(), "finance": _release(seed=7)})
    with pytest.raises(core.FrameMissing):
        core.release_now({})
    with pytest.raises(core.FrameError):
        core.release_now({"hr": pd.concat([_release(), _release()])})
