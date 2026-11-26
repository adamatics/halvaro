"""Pay module: synthetic frames for the contract, the baseline release for populations."""
import datetime as dt
import warnings

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
import halvaro.hr.pay as paymod
from halvaro.core import Context, FrameError, RestrictedColumnRefusal, fact

D = dt.date
HR = Context.from_profile("mcp_people_hr", stage="day1")
NO = Context.from_profile("mcp_people", stage="day1")
LIMIT = fact("legal.pay_transparency.joint_assessment_gap_threshold").value * 100


def _people(n_w=10, n_m=10, dep="DEP-03", gap=0.05, hired=D(2024, 3, 1), level=4, entity="LE-01"):
    rows = []
    for i in range(n_w + n_m):
        f = i < n_w
        rate = 50000 * (1 - gap) if f else 50000.0
        rows.append({"emp_key": f"{dep}-{'F' if f else 'M'}{i}", "gender": "F" if f else "M", "hire_date": hired, "legal_entity_key": entity, "dep_key": dep,
                     "level": level, "rate_dkk": rate, "rate_local": rate, "tenure_years": 1.0 + (i % 5) * 0.5, "compa": rate / 52000})
    return pd.DataFrame(rows)


def _noisy(seed=7, n=400):
    """Pay depends on grade, entity and tenure; women sit in the low grades and in LE-01, so the raw gap is far from the 4 percent built into the frame."""
    rng = np.random.default_rng(seed)
    female = rng.random(n) < 0.4
    level = np.where(female, rng.choice([1, 2, 3], n, p=[.5, .3, .2]), rng.choice([1, 2, 3], n, p=[.1, .3, .6]))
    entity = np.where(female, rng.choice(["LE-01", "LE-02"], n, p=[.8, .2]), rng.choice(["LE-01", "LE-02"], n, p=[.4, .6]))
    tenure = rng.uniform(0, 20, n)
    lnr = 10 + 0.25 * level + 0.15 * (entity == "LE-02") + 0.01 * tenure - 0.04 * female + rng.normal(0, 0.02, n)
    return pd.DataFrame({"emp_key": [f"E{i}" for i in range(n)], "gender": np.where(female, "F", "M"), "hire_date": D(2020, 1, 1), "legal_entity_key": entity, "dep_key": "DEP-01",
                         "level": level, "rate_dkk": np.exp(lnr), "rate_local": np.exp(lnr), "tenure_years": tenure, "compa": 1.0}), lnr


def _tables():
    emp = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3"], "gender": ["F", "M", "F"], "hire_date": [D(2020, 1, 1), D(2024, 6, 1), D(2023, 2, 1)], "legal_entity_key": ["LE-01", "LE-02", "LE-01"]})
    term = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3", "EMP-1"], "valid_from": [D(2023, 1, 1), D(2023, 1, 1), D(2023, 1, 1), D(2021, 1, 1)],
                         "valid_to": [None, None, None, D(2022, 12, 31)], "team_key": ["T1", "T1", "T2", "T2"], "grade_key": ["G1", "G1", "G2", "G2"], "fte": [1.0, 0.5, 1.0, 1.0],
                         "currency": ["DKK", "EUR", "DKK", "DKK"], "base_salary": [40000, 4000, 30000, 99999]})
    team = pd.DataFrame({"team_key": ["T1", "T2"], "dep_key": ["DEP-03", "DEP-04"]})
    grade = pd.DataFrame({"gra_key": ["G1", "G2"], "level": [4, 2], "band_min_dkk": [30000, 20000], "band_max_dkk": [50000, 40000], "band_min_eur": [3000, 2000], "band_max_eur": [5000, 4000]})
    return emp, term, team, grade


# ---- pay_frame ---------------------------------------------------------------------------------------------------------------------------------------
def test_pay_frame_rate_fx_tenure_band_position_and_the_term_valid_on_the_date():
    emp, term, team, grade = _tables()
    f = hr.pay_frame(emp, term, team, grade, D(2026, 11, 30), context=HR).set_index("emp_key")
    fx = fact("world.fx_eur_dkk_fixed").value
    assert "base_salary" not in f.columns and len(f) == 3
    assert f.loc["EMP-1", "rate_local"] == 40000 and f.loc["EMP-2", "rate_local"] == 8000, "the rate is salary over fte; EMP-1's closed 2021 term (99999) is not used"
    assert f.loc["EMP-2", "rate_dkk"] == pytest.approx(8000 * fx) and f.loc["EMP-1", "rate_dkk"] == 40000
    assert f.loc["EMP-1", "compa"] == pytest.approx(1.0) and f.loc["EMP-2", "compa"] == pytest.approx(2.0), "midpoints 40000 DKK and 4000 EUR"
    assert f.loc["EMP-1", "tenure_years"] == pytest.approx((D(2026, 11, 30) - D(2020, 1, 1)).days / 365.25)
    assert f.loc["EMP-3", ["dep_key", "level"]].tolist() == ["DEP-04", 2]
    old = hr.pay_frame(emp, term, team, grade, D(2021, 6, 1), context=HR).set_index("emp_key")
    assert list(old.index) == ["EMP-1"] and old.loc["EMP-1", "rate_local"] == 99999 and old.loc["EMP-1", "dep_key"] == "DEP-04", "as_of picks the closed earlier term"


def test_pay_frame_needs_a_context_that_may_read_pay():
    emp, term, team, grade = _tables()
    with pytest.raises(TypeError):
        hr.pay_frame(emp, term, team, grade, D(2026, 11, 30))
    with pytest.raises(RestrictedColumnRefusal) as e:
        hr.pay_frame(emp, term, team, grade, D(2026, 11, 30), context=NO)
    assert (e.value.role, e.value.stage, e.value.column) == ("mcp_people", "day1", "hr.employment_term.base_salary")
    with pytest.raises(RestrictedColumnRefusal) as e2:
        hr.pay_frame(emp, term.drop(columns="base_salary"), team, grade, D(2026, 11, 30), context=HR)
    assert e2.value.role == "mcp_people_hr" and e2.value.stage == "day1"


def test_pay_frame_refuses_bad_inputs_and_warns_before_the_band_year():
    emp, term, team, grade = _tables()
    for bad in (term.assign(fte=[0.0, 0.5, 1.0, 1.0]), term.assign(base_salary=[None, 4000, 30000, 1]), term.assign(currency=["DKK", "SEK", "DKK", "DKK"])):
        with pytest.raises(FrameError):
            hr.pay_frame(emp, bad, team, grade, D(2026, 11, 30), context=HR)
    with pytest.raises(FrameError, match="no employee, team or grade"):
        hr.pay_frame(emp, term, team[team.team_key != "T2"], grade, D(2026, 11, 30), context=HR)
    with pytest.warns(UserWarning, match="2026 level") as w:
        f = hr.pay_frame(emp, term, team, grade, D(2025, 6, 1), context=HR)
    assert len(w) == 1 and f.attrs["warnings"] and "2026" in f.attrs["warnings"][0]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        quiet = hr.pay_frame(emp, term, team, grade, D(2025, 6, 1), context=HR, bands_year=2025)
    assert quiet.attrs["warnings"] == []


# ---- raw gap, adjusted gap -----------------------------------------------------------------------------------------------------------------------------
def test_raw_gap_is_the_gap_of_means_with_a_group_size_floor_and_a_guard():
    f = _people(gap=0.05)
    assert hr.raw_gap(f) == pytest.approx(5.0) and hr.raw_gap(_people(gap=-0.10)) == pytest.approx(-10.0), "positive: women are paid less"
    skew = pd.concat([_people(n_w=8, n_m=0, gap=0.0), _people(n_w=0, n_m=8, gap=0.0)], ignore_index=True)
    skew.loc[skew.gender == "F", "rate_dkk"] = [10, 10, 10, 10, 10, 10, 10, 1000]          # mean 133.75, median 10
    skew.loc[skew.gender == "M", "rate_dkk"] = 100.0
    assert hr.raw_gap(skew) == pytest.approx((1 - 133.75 / 100) * 100), "means, not medians: the women mean is 1070 over 8, their median 10"
    eur = _people(gap=0.0).assign(rate_local=1.0)
    assert hr.raw_gap(eur) == pytest.approx(0.0), "the DKK rate is used, not the local one"
    assert np.isnan(hr.raw_gap(_people(n_w=7, n_m=20))) and not np.isnan(hr.raw_gap(_people(n_w=8, n_m=8))) and np.isnan(hr.raw_gap(_people(n_w=20, n_m=7)))
    assert not np.isnan(hr.raw_gap(_people(n_w=7, n_m=20), minimum_group=7))
    other = pd.concat([f, f.iloc[[0]].assign(gender="X", rate_dkk=1.0)], ignore_index=True)
    assert hr.raw_gap(other) == pytest.approx(5.0), "other gender values are left out"
    with pytest.raises(RestrictedColumnRefusal):
        hr.raw_gap(f, context=NO)
    assert hr.raw_gap(f, context=HR) == pytest.approx(5.0)
    with pytest.raises(RestrictedColumnRefusal):
        hr.raw_gap(f.drop(columns="rate_dkk"))


def test_adjusted_gap_controls_grade_entity_and_tenure_and_matches_an_independent_ols():
    f, lnr = _noisy()
    a = hr.adjusted_gap(f)
    X = np.column_stack([np.ones(len(f)), (f.gender == "F").astype(float), f.tenure_years, (f.legal_entity_key == "LE-02").astype(float), (f.level == 2).astype(float), (f.level == 3).astype(float)])
    b, *_ = np.linalg.lstsq(X, np.log(f.rate_dkk), rcond=None)
    res = np.log(f.rate_dkk) - X @ b
    se = np.sqrt((res @ res) / (len(f) - X.shape[1]) * np.linalg.inv(X.T @ X)[1, 1])
    assert a["adjusted_gap_pct"] == pytest.approx((1 - np.exp(b[1])) * 100, abs=1e-9) and a["adjusted_gap_se_pct"] == pytest.approx(se * 100, abs=1e-9)
    assert a["adjusted_gap_pct"] == pytest.approx(4.0, abs=0.6) and abs(hr.raw_gap(f) - 4.0) > 8, "the raw gap is far from the 4 percent built into the frame, the adjusted one is not"
    assert a["adjusted_gap_se_pct"] > 0.05 and not a["suppressed"] and a["legal_status"] == "ok"


def test_adjusted_gap_boundary_of_eight_per_gender_and_failure_modes():
    for n_w, n_m, sup in ((8, 8, False), (7, 8, True), (8, 7, True), (7, 7, True), (30, 7, True), (7, 30, True)):
        a = hr.adjusted_gap(_people(n_w=n_w, n_m=n_m))
        assert a["suppressed"] is sup and (np.isnan(a["adjusted_gap_pct"]) == sup), (n_w, n_m)
    assert not hr.adjusted_gap(_people(n_w=7, n_m=20), minimum_group=7)["suppressed"]
    assert hr.adjusted_gap(_people(n_w=2, n_m=2), minimum_group=2)["suppressed"], "a sample too small for the model is suppressed"
    with pytest.raises(FrameError, match="missing entity"):
        hr.adjusted_gap(_people().assign(legal_entity_key=[None] * 20))
    with pytest.raises(FrameError, match="non-positive or non-finite"):
        hr.adjusted_gap(_people().assign(rate_dkk=[np.inf] + [50000.0] * 19))
    with pytest.raises(RestrictedColumnRefusal):
        hr.adjusted_gap(_people(), context=NO)


# ---- gap table ---------------------------------------------------------------------------------------------------------------------------------------------
def test_gap_table_full_rows_rank_and_suppression():
    f = pd.concat([_people(n_w=12, n_m=9, dep="DEP-01", gap=0.0), _people(n_w=9, n_m=15, dep="DEP-03", gap=0.06), _people(n_w=8, n_m=11, dep="DEP-05", gap=0.035),
                   _people(n_w=4, n_m=20, dep="DEP-09", gap=0.2)], ignore_index=True)
    t = hr.gap_table(f, context=HR).set_index("dep_key")
    assert t.index.tolist() == ["DEP-03", "DEP-05", "DEP-01", "DEP-09"] and t["rank"].tolist()[:3] == [1, 2, 3] and pd.isna(t["rank"].iloc[3]) and str(t["rank"].dtype) == "Int64"
    for dep, (w, m, raw) in {"DEP-01": (12, 9, 0.0), "DEP-03": (9, 15, 6.0), "DEP-05": (8, 11, 3.5)}.items():
        r = t.loc[dep]
        assert (r.n_women, r.n_men) == (w, m) and r.raw_gap_pct == pytest.approx(raw, abs=1e-6) and r.adjusted_gap_pct == pytest.approx(raw, abs=1e-6), dep
    assert (t.loc["DEP-09", ["n_women", "n_men"]].tolist(), t.loc["DEP-09", "flag"]) == ([4, 20], "suppressed") and t.loc["DEP-09", ["raw_gap_pct", "adjusted_gap_pct"]].isna().all()
    assert set(t.legal_status) == {"VERIFY"} and t.loc["DEP-03", "flag"] == "above_threshold" and t.loc["DEP-05", "flag"] == "watch" and t.loc["DEP-01", "flag"] == "ok"


def test_gap_table_minimum_group_and_flag_limits(monkeypatch):
    f = pd.concat([_people(dep="DEP-01"), _people(n_w=4, n_m=20, dep="DEP-09", gap=0.2)], ignore_index=True)
    assert hr.gap_table(f, minimum_group=4).set_index("dep_key").loc["DEP-09", "suppressed"] is np.False_ or not hr.gap_table(f, minimum_group=4).set_index("dep_key").loc["DEP-09", "suppressed"]
    assert hr.gap_table(f).set_index("dep_key").loc["DEP-09", "suppressed"]
    real = paymod.adjusted_gap
    for value, watch, want in ((LIMIT, 0.03, "above_threshold"), (LIMIT - 0.01, 0.03, "watch"), (3.0, 0.03, "watch"), (3.0 - 0.01, 0.03, "ok"), (3.0 - 0.01, 0.0299, "watch"),
                               (LIMIT + 0.01, 0.03, "above_threshold")):
        monkeypatch.setattr(paymod, "adjusted_gap", lambda g, m=8, v=value: {**real(g, m), "adjusted_gap_pct": v})
        assert hr.gap_table(f, watch=watch).set_index("dep_key").loc["DEP-01", "flag"] == want, (value, watch)
    monkeypatch.setattr(paymod, "adjusted_gap", real)
    g = hr.gap_table(pd.concat([_people(level=3, gap=0.02), _people(level=4, gap=0.07)], ignore_index=True), by="grade")
    assert g.level.tolist() == [4, 3] and g["rank"].tolist() == [1, 2]
    empty = hr.gap_table(f.iloc[0:0])
    assert len(empty) == 0 and "adjusted_gap_pct" in empty.columns
    with pytest.raises(FrameError, match="department or grade"):
        hr.gap_table(f, by="team")
    with pytest.raises(RestrictedColumnRefusal):
        hr.gap_table(f, context=NO)


def test_suppress_small_cells_nulls_values_flag_rank_and_se():
    t = pd.DataFrame({"k": ["a", "b", "c", "d"], "n_women": [10, 7, 30, np.nan], "n_men": [9, 50, 8, 20], "gap": [1.0, 2.0, 3.0, 4.0], "adjusted_gap_se_pct": [.1, .2, .3, .4],
                      "flag": ["ok", "watch", "ok", "ok"], "rank": pd.array([1, 2, 3, 4], dtype="Int64"), "suppressed": [False, False, False, False]})
    s = hr.suppress_small_cells(t, "gap")
    assert s.gap.isna().tolist() == [False, True, False, True] and s.suppressed.tolist() == [False, True, False, True], "a missing count suppresses too; a plain column name works"
    assert s.flag.tolist() == ["ok", "suppressed", "ok", "suppressed"] and s["rank"].isna().tolist() == [False, True, False, True] and s.adjusted_gap_se_pct.isna().tolist() == [False, True, False, True]
    assert hr.suppress_small_cells(t, ["gap"], minimum_group=10).gap.isna().tolist() == [True, True, True, True]
    pre = t.assign(suppressed=[True, False, False, False])
    assert hr.suppress_small_cells(pre, ["gap"], minimum_group=1).suppressed.tolist() == [True, False, False, True], "suppressed only turns on"
    assert t.gap.notna().all() and t.flag.tolist()[1] == "watch", "the input is not changed"


# ---- intake by grade----------------------------------------------------------------------------------------------------------------------------------------
# Neutral test data: department DEP-07, intake from 1 April 2021, grades 2 to 4. The caller always names the intake (date, department, grades).
START, DEP = D(2021, 4, 1), "DEP-07"


def _grade_frame():
    rows = []
    def add(n, gender, level, compa, hired=D(2021, 6, 1), dep=DEP):
        for i in range(n):
            rows.append({"emp_key": f"{dep}-{gender}{level}{len(rows)}", "gender": gender, "hire_date": hired, "dep_key": dep, "level": level, "compa": compa, "rate_dkk": 1.0,
                         "tenure_years": 1.0, "legal_entity_key": "LE-01"})
    add(10, "F", 2, 0.90); add(12, "M", 2, 1.00)           # grade 2: -10 percent
    add(8, "F", 3, 1.10); add(9, "M", 3, 1.00)             # grade 3: +10 percent, exactly 8 women
    add(6, "F", 4, 0.50); add(9, "M", 4, 1.00)             # grade 4: 6 women
    add(1, "F", 2, 0.80, hired=START); add(9, "F", 2, 0.90, hired=D(2021, 3, 31)); add(9, "F", 1, 0.90); add(9, "M", 2, 1.0, dep="DEP-08")
    return pd.DataFrame(rows)


def _by_grade(f, **kw):
    args = {"hired_from": START, "dep": DEP, "grades": (2, 3), **kw}
    return hr.intake_compa_by_grade(f, **args)


def test_intake_compa_by_grade_counts_percentages_boundaries_and_the_pooled_value():
    f = _grade_frame()
    c = _by_grade(f, grades=(2, 3, 4), context=HR).set_index("grade_level")
    assert c.loc[2, ["n_women", "n_men"]].tolist() == [11, 12], "the woman hired exactly on hired_from counts, the 9 hired the day before do not"
    assert c.loc[2, "women_vs_men_compa_pct"] == pytest.approx(((10 * 0.90 + 0.80) / 11) / 1.0 * 100 - 100)
    assert c.loc[3, ["n_women", "n_men"]].tolist() == [8, 9] and c.loc[3, "women_vs_men_compa_pct"] == pytest.approx(10.0) and not c.loc[3, "suppressed"], "exactly 8 is enough"
    assert c.loc[4, ["n_women", "n_men"]].tolist() == [6, 9] and np.isnan(c.loc[4, "women_vs_men_compa_pct"]) and c.loc[4, "suppressed"]
    w_mean = (10 * 0.90 + 0.80 + 8 * 1.10 + 6 * 0.50) / 25
    m_mean = 1.0
    assert c.loc["all", ["n_women", "n_men"]].tolist() == [25, 30] and c.loc["all", "women_vs_men_compa_pct"] == pytest.approx((w_mean / m_mean - 1) * 100), "pooled is a pooled mean, not an average of cells"
    assert 1 not in c.index and set(_by_grade(f).legal_status) == {"ok"} and _by_grade(f).grade_level.tolist() == [2, 3, "all"], "only the grades asked for"


def test_intake_compa_by_grade_needs_the_intake_and_its_parameters_are_keyword_only():
    f = _grade_frame()
    with pytest.raises(TypeError):
        hr.intake_compa_by_grade(f, DEP)
    with pytest.raises(TypeError):
        hr.intake_compa_by_grade(f, dep=DEP, grades=(2,)), "the intake date has no default: the caller names it"
    assert _by_grade(f, grades=(2, 3, 4), minimum_group=6).set_index("grade_level").loc[4, "women_vs_men_compa_pct"] == pytest.approx(-50.0)
    assert _by_grade(f, hired_from=D(2021, 4, 2)).set_index("grade_level").loc[2, "n_women"] == 10, "one day later the woman of 1 April drops out"
    assert _by_grade(f, hired_from=D(2021, 3, 31)).set_index("grade_level").loc[2, "n_women"] == 20
    assert _by_grade(f, grades=(1,)).grade_level.tolist() == [1, "all"] and _by_grade(f, dep="DEP-08", grades=(2,)).set_index("grade_level").loc["all", "n_women"] == 0
    with pytest.raises(RestrictedColumnRefusal):
        _by_grade(f, context=NO)


def _intake_frame(n_intake=12, n_other=10, n_men=30, b_intake=-0.05, b_other=-0.02):
    """DEP-07 with an exact log-linear pay: ln(rate) = 11 + b_intake*intake woman + b_other*other woman + 0.01*tenure + 0.05*(entity LE-02) + 0.2*grade."""
    rows, rng = [], np.random.default_rng(5)
    def add(gender, intake, k):
        grade, ent, ten = 1 + k % 3, "LE-02" if k % 2 else "LE-01", 1.0 + (k * 7) % 13
        hired = D(2021, 6, 1) if intake else D(2018, 6, 1)
        ln = 11 + (b_intake if (gender == "F" and intake) else b_other if gender == "F" else 0.0) + 0.01 * ten + 0.05 * (ent == "LE-02") + 0.2 * grade + rng.normal(0, 0.002)
        rows.append({"gender": gender, "dep_key": DEP, "hire_date": hired, "level": grade, "compa": float(np.exp(ln - 11.2)), "rate_dkk": float(np.exp(ln)), "tenure_years": ten, "legal_entity_key": ent})
    for k in range(n_intake): add("F", True, k)
    for k in range(n_other): add("F", False, k)
    for k in range(n_men): add("M", k % 4 == 0, k)
    return pd.DataFrame(rows)


def _difference(f, **kw):
    args = {"hired_from": START, "dep": DEP, "grades": (2, 3), "context": HR, **kw}
    return hr.intake_pay_difference(f, **args)


def test_intake_pay_difference_recovers_the_intake_and_other_women_effects_and_suppresses_small_cells():
    r = _difference(_intake_frame())
    assert (r["n_intake_women"], r["n_other_women"], r["n_men"]) == (12, 10, 30) and not r["suppressed"]
    assert r["intake_women_pct"] == pytest.approx((np.exp(-0.05) - 1) * 100, abs=0.3) and r["other_women_pct"] == pytest.approx((np.exp(-0.02) - 1) * 100, abs=0.3)
    assert r["intake_women_se_pct"] > 0 and r["intake_women_pct"] < r["other_women_pct"] < 0, "negative when women earn less; the women of the intake are further below"
    assert isinstance(r["by_grade"], pd.DataFrame) and r["by_grade"].grade_level.tolist() == [2, 3, "all"] and r["legal_status"] == "ok"
    s = _difference(_intake_frame(n_intake=7))
    assert s["suppressed"] and np.isnan(s["intake_women_pct"]) and s["n_intake_women"] == 7
    assert _difference(_intake_frame(n_intake=7), minimum_group=7)["suppressed"] is False
    few = _difference(_intake_frame(n_other=7))
    assert not few["suppressed"] and np.isnan(few["other_women_pct"]) and not np.isnan(few["intake_women_pct"]), "only the other women estimate is held back"
    assert _difference(_intake_frame(n_men=7))["suppressed"]
    assert _difference(_intake_frame(), hired_from=D(2030, 1, 1))["suppressed"], "nobody hired from a later intake date"
    with pytest.raises(TypeError):
        hr.intake_pay_difference(_intake_frame(), dep=DEP, grades=(2,), context=HR), "the intake date has no default: the caller names it"
    with pytest.raises(Exception):
        _difference(_intake_frame().drop(columns=["rate_dkk", "compa"]))


def test_band_position_midpoint_position_in_band_and_the_restriction():
    emp, term, team, grade = _tables()
    f = hr.pay_frame(emp, term, team, grade, D(2026, 11, 30), context=HR)
    b = hr.band_position(f, grade, context=HR, as_of=D(2026, 11, 30)).set_index("emp_key")
    assert b.loc["EMP-1", ["band_min", "band_mid", "band_max"]].tolist() == [30000, 40000, 50000] and b.loc["EMP-1", "vs_midpoint"] == pytest.approx(1.0) and b.loc["EMP-1", "position_in_band"] == pytest.approx(0.5)
    assert b.loc["EMP-2", ["currency", "band_mid"]].tolist() == ["EUR", 4000.0] and b.loc["EMP-2", "vs_midpoint"] == pytest.approx(2.0) and b.loc["EMP-2", "position_in_band"] == pytest.approx((8000 - 3000) / 2000) and not b.loc["EMP-2", "in_band"], "8000 EUR is far above the EUR band"
    assert b.loc["EMP-3", "in_band"] and b.loc["EMP-3", "position_in_band"] == pytest.approx(0.5)
    assert b.attrs["warnings"] == []
    with pytest.warns(UserWarning, match="understated"):
        early = hr.band_position(f, grade, context=HR, as_of=D(2024, 1, 1))
    assert early.attrs["warnings"]
    with pytest.raises(RestrictedColumnRefusal):
        hr.band_position(f, grade, context=NO)
    with pytest.raises(RestrictedColumnRefusal):
        hr.band_position(f.drop(columns="compa"), grade, context=HR)
    with pytest.raises(FrameError, match="does not hold"):
        hr.band_position(f, grade[grade.gra_key != "G2"], context=HR)
    with pytest.raises(FrameError, match="more than one"):
        hr.band_position(f, pd.concat([grade, grade.iloc[:1]]), context=HR)
    with pytest.raises(FrameError, match="not above"):
        hr.band_position(f, grade.assign(band_max_dkk=[30000, 40000]), context=HR)
