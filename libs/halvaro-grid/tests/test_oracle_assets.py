"""Oracles of the asset functions (element_peak_load, strained_elements, zone_strain_summary): each expected value comes from a plain pandas or python reading, never from the function itself."""
import re

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# helpers: the independent reading of the rules (a groupby per sensor, a loop per element)
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------




def _tri(v):
    """True, False or None for a possibly unknown flag."""
    return None if pd.isna(v) else bool(v)




def _strain_rule_from_fact():
    """The thresholds of the proposed strain rule, read from its text: load percent, age years, bad condition classes."""
    text = fact("policy.grid.strained_element").value
    load = re.search(r"at or above (\d+(?:\.\d+)?) percent", text)
    age = re.search(r"(\d+(?:\.\d+)?) years or more", text)
    cls = re.search(r"condition class ([A-E]) or ([A-E])", text)
    assert load and age and cls, f"the text of policy.grid.strained_element is not in the form this oracle reads: {text!r}"
    return float(load.group(1)), float(age.group(1)), (cls.group(1), cls.group(2)), text


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# element_peak_load
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _sn(rows):
    return pd.DataFrame(rows, columns=["sns_key", "net_key", "rated_value", "install_date", "sensor_type"])


def _md(rows):
    return pd.DataFrame(rows, columns=["sns_key", "date", "max", "availability_pct"])


def _hand_peak_inputs():
    days = lambda a, b: [d.strftime("%Y-%m-%d") for d in pd.date_range(a, b)]            # noqa: E731
    sn = _sn([("S1", "A", 100.0, "2025-01-01", "load_percent"), ("S2", "F", 100.0, "2024-12-01", "load_percent"), ("S3", "B", 100.0, "2025-01-05", "load_percent"),
              ("S4", "C", 100.0, "2024-06-01", "load_percent"), ("S5", "D", 100.0, "2025-01-01", "active_power"), ("S6", None, 100.0, "2025-01-01", "load_percent"),
              ("S7", "E", 100.0, "2025-01-01", "load_percent"), ("S8", "E", 100.0, "2025-01-01", "load_percent"), ("S10", "F", 100.0, "2025-01-01", "load_percent"),
              ("S9", "G", 100.0, "2025-02-01", "load_percent")])
    rows = [("S1", d, v, 90.0) for d, v in zip(days("2025-01-01", "2025-01-10"), [50, 60, 70, 80, 95, 60, 50, 40, 30, 20])]
    rows += [("S2", "2025-01-03", 99.0, 100.0)]
    rows += [("S3", d, v, a) for d, v, a in zip(days("2025-01-05", "2025-01-10"), [80, 85, np.nan, 70, 60, 50], [100, 100, 0, 100, 100, 100])]
    rows += [("S4", d, v, 100.0) for d, v in zip(days("2025-01-01", "2025-01-08"), [10, 20, 30, 40, 45, 30, 20, 10])]
    rows += [("S5", "2025-01-01", 10.0, 100.0), ("S6", "2025-01-02", 5.0, 100.0)]
    rows += [("S7", "2025-01-01", 70.0, 100.0), ("S7", "2025-01-02", 60.0, 100.0), ("S8", "2025-01-01", 70.0, 100.0), ("S8", "2025-01-02", 65.0, 100.0)]
    rows += [("S10", d, 60.0, 100.0) for d in days("2025-01-01", "2025-01-10")]
    return sn, _md(rows)


def test_oracle_element_peak_load_hand_worked_days_completeness_and_choice_of_sensor():
    """route: a hand worked example, every peak, day count and completeness written down from the frames below (ten days, 1 to 10 January 2025)."""
    sn, md = _hand_peak_inputs()
    sn0, md0 = sn.copy(), md.copy()
    r = grid.element_peak_load(sn, md, min_completeness=0.9, context=M12).set_index("net_key")
    assert r.index.tolist() == ["A", "B", "C", "E", "F", "G"], "one row per element with a load sensor, sorted; the power sensor (D) and the sensor without element are not listed"
    a = r.loc["A"]
    assert (a.sns_key, a.peak_percent, str(a.peak_date.date()), a.days, a.completeness, bool(a.valid)) == ("S1", 95.0, "2025-01-05", 10, 0.9, True), "ten days at 90 percent availability is exactly 0.9, which is valid at the limit 0.9"
    b = r.loc["B"]
    assert (b.sns_key, b.peak_percent, str(b.peak_date.date()), b.days, b.completeness, bool(b.valid)) == ("S3", 85.0, "2025-01-06", 5, 0.8333, False), "installed 5 January: 6 days to count, 500 of 600 percent days; a null maximum is not a day with data"
    c = r.loc["C"]
    assert (c.sns_key, c.peak_percent, str(c.peak_date.date()), c.days, c.completeness, bool(c.valid)) == ("S4", 45.0, "2025-01-05", 8, 0.8, False), "installed before the window: ten days to count, not the days since installation"
    e = r.loc["E"]
    assert (e.sns_key, e.peak_percent, str(e.peak_date.date()), e.days, e.completeness, bool(e.valid)) == ("S7", 70.0, "2025-01-01", 2, 0.2, False), "equal peaks of two sensors: the lower sensor key"
    f = r.loc["F"]
    assert (f.sns_key, f.peak_percent, str(f.peak_date.date()), f.days, f.completeness, bool(f.valid)) == ("S2", 99.0, "2025-01-03", 1, 0.1, False), "the highest sensor of the element wins, valid or not"
    g = r.loc["G"]
    assert (g.sns_key, g.days, g.completeness, bool(g.valid)) == ("S9", 0, 0.0, False) and np.isnan(g.peak_percent) and pd.isna(g.peak_date), "installed after the last day of the data: no day to count, no data, completeness 0"
    pd.testing.assert_frame_equal(sn, sn0)
    pd.testing.assert_frame_equal(md, md0)
    # the same limit one step to either side
    assert not bool(grid.element_peak_load(sn, md, min_completeness=0.9001, context=M12).set_index("net_key").loc["A", "valid"])
    low = grid.element_peak_load(sn, md, min_completeness=0.83, context=M12).set_index("net_key")
    assert bool(low.loc["B", "valid"]) and not bool(low.loc["C", "valid"]), "0.8333 is valid at 0.83, 0.8 is not"
    assert bool(grid.element_peak_load(sn, md, min_completeness=0.8, context=M12).set_index("net_key").loc["C", "valid"]), "0.8 is valid at the limit 0.8"
    # input that cannot be read as the stored tables is refused
    for bad_sn, bad_md, kw, msg in ((sn, md, dict(min_completeness=1.5), "min_completeness"), (sn.assign(rated_value=0.0), md, {}, "rated_value"), (pd.concat([sn, sn.iloc[:1]]), md, {}, "more than one row"),
                                    (sn, pd.concat([md, md.iloc[:1]]), {}, "more than one row"), (sn, md, dict(window=("2025-02-01", "2025-01-01")), "in order")):
        with pytest.raises(FrameError, match=msg):
            grid.element_peak_load(bad_sn, bad_md, context=M12, **kw)


def test_oracle_element_peak_load_hand_worked_window():
    """route: a hand worked example with a window of four days (3 to 6 January 2025) over the frames of the first example."""
    sn, md = _hand_peak_inputs()
    r = grid.element_peak_load(sn, md, window=("2025-01-03", "2025-01-06"), min_completeness=0.9, context=M12).set_index("net_key")
    row = lambda k: (r.at[k, "sns_key"], r.at[k, "peak_percent"], r.at[k, "days"], r.at[k, "completeness"], bool(r.at[k, "valid"]))      # noqa: E731
    assert row("A") == ("S1", 95.0, 4, 0.9, True), "70, 80, 95, 60 at 90 percent availability over four days"
    assert row("B") == ("S3", 85.0, 2, 1.0, True), "installed 5 January: the days to count are 5 and 6 January only"
    assert row("C") == ("S4", 45.0, 4, 1.0, True)
    assert row("F") == ("S2", 99.0, 1, 0.25, False), "one day of four"
    e = r.loc["E"]
    assert (e.sns_key, e.days, e.completeness, bool(e.valid)) == ("S7", 0, 0.0, False) and np.isnan(e.peak_percent) and pd.isna(e.peak_date), "two sensors without a day in the window: null peak, completeness 0"
    g = r.loc["G"]
    assert (g.sns_key, g.days, g.completeness, bool(g.valid)) == ("S9", 0, 0.0, False), "installed after the end of the window"


def test_oracle_element_peak_load_default_limit_is_the_fact_policy_grid_min_peak_completeness():
    """route: sensors built at the fact value plus and minus 0.02 availability over ten days; the default call must call the first valid and the second not."""
    f = fact("policy.grid.min_peak_completeness")
    limit = float(f.value)
    assert 0.03 < limit < 0.97, f"the construction needs a limit inside (0.03, 0.97); the fact says {f.value!r}"
    sn = _sn([("H", "NH", 100.0, "2025-01-01", "load_percent"), ("L", "NL", 100.0, "2025-01-01", "load_percent")])
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range("2025-01-01", "2025-01-10")]
    md = _md([("H", d, 50.0, 100.0 * (limit + 0.02)) for d in days] + [("L", d, 50.0, 100.0 * (limit - 0.02)) for d in days])
    r = grid.element_peak_load(sn, md, context=M12).set_index("net_key")
    assert bool(r.loc["NH", "valid"]) and not bool(r.loc["NL", "valid"]), f"default limit read from policy.grid.min_peak_completeness = {f.value!r}; completeness {limit + 0.02:.4f} is valid, {limit - 0.02:.4f} is not"



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# strained_elements
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _el(rows):
    return pd.DataFrame(rows, columns=["net_key", "element_type", "status", "install_year", "condition_class", "cus_key", "zone_key", "commissioned_date"])


def test_oracle_strained_elements_hand_worked_boundaries():
    """route: a hand worked example around the three limits (load 90, age 40, classes D and E) with explicit parameters, ages counted in days over 365.25 by hand."""
    # 14610 days = 40 years (10 leap days) from 1 January 1986 to 1 January 2026
    ge = _el([("A", "substation", "in_service", 1986, "B", "C1", "Z1", "1986-01-01"),            # age 40.0 exactly: age strained at the limit
              ("B", "substation", "in_service", 1986, "B", "C1", "Z1", "1986-01-02"),            # 14609 days = 39.997, shown as 40.0 (two decimals): age strained
              ("C", "substation", "in_service", 1986, "B", "C1", "Z1", "1986-01-17"),            # 14594 days = 39.956, shown as 39.96: not age strained
              ("D", "substation", "in_service", 2020, "D", "C2", "Z2", "2020-01-01"),            # class D
              ("E", "substation", "in_service", 2020, "C", "C2", "Z2", "2020-01-01"),            # class C is not bad
              ("F", "substation", "in_service", 2020, "E", "C2", "Z2", "2020-01-01"),            # class E
              ("G", "substation", "out_of_service", 1950, "E", "C2", "Z2", "1950-01-01"),        # not in service: not listed
              ("H", "cable_section", "in_service", 2010, "B", None, "Z1", None),                 # no commissioning date: 1 January 2010
              ("I", "cable_section", "in_service", 2026, "B", "C1", "Z1", "2026-03-01")])        # commissioned after the date: no age
    pk = pd.DataFrame({"net_key": ["A", "B", "C", "D", "E", "F", "H", "I"], "peak_percent": [90.0, 89.99, 90.01, 10.0, 120.0, 10.0, 55.0, 95.0], "valid": [True, True, True, True, False, True, True, True]})
    cu = pd.DataFrame({"cus_key": ["C1", "C2"], "name": ["Net One", "Net Two"]})
    ge, pk = ge.iloc[::-1], pk.sample(frac=1, random_state=2)                                        # the inputs are not in key order
    pk0, ge0 = pk.copy(), ge.copy()
    s = grid.strained_elements(pk, ge, cu, as_of="2026-01-01", load_percent=90.0, bad_classes=("D", "E"), age_years=40.0, context=M12).set_index("net_key")
    assert s.index.tolist() == ["A", "B", "C", "D", "E", "F", "H", "I"], "the element out of service is not listed; sorted by key"
    want = {  # age_years, load_strained, age_strained, strained, reasons
        "A": (40.0, True, True, True, "load,age"),          # 90.0 is at the limit, 40.0 years is at the limit
        "B": (40.0, False, True, True, "age"),              # 89.99 is under 90, 39.997 years shows as 40.0
        "C": (39.96, True, False, True, "load"),            # 90.01, 39.96 years
        "D": (6.0, False, True, True, "class"),
        "E": (6.0, None, False, None, ""),                  # the peak 120 is not valid: load unknown, young, class C: unknown
        "F": (6.0, False, True, True, "class"),
        "H": (16.0, False, False, False, ""),               # 5844 days = 16.0 years, load known and low
        "I": (None, True, False, True, "load"),
    }
    for k, (age, load, agef, strained, reasons) in want.items():
        r = s.loc[k]
        assert (None if pd.isna(r.age_years) else r.age_years) == age, f"age of {k}"
        assert _tri(r.load_strained) == load and bool(r.age_strained) == agef and _tri(r.strained) == strained and r.reasons == reasons, f"flags of {k}: {r.to_dict()}"
    assert s.loc["A", "customer_name"] == "Net One" and s.loc["D", "customer_name"] == "Net Two" and pd.isna(s.loc["H", "customer_name"]), "names by customer key; no customer, no name"
    assert pd.isna(s.loc["E", "peak_percent"]) and s.loc["A", "peak_percent"] == 90.0, "the peak of a sensor that is not valid is not carried"
    pd.testing.assert_frame_equal(pk, pk0)
    pd.testing.assert_frame_equal(ge, ge0)
    # limits moved: the same elements under other parameters
    loose = grid.strained_elements(pk, ge, as_of="2026-01-01", load_percent=95.0, bad_classes=("E",), age_years=50.0, context=M12).set_index("net_key")
    assert [_tri(loose.at[k, "strained"]) for k in ("A", "B", "C", "D", "E", "F", "H", "I")] == [False, False, False, False, None, True, False, True], "limits 95, class E only, age 50"
    only = grid.strained_elements(pk, ge, as_of="2026-01-01", types=("cable_section",), context=M12)
    assert only["net_key"].tolist() == ["H", "I"]


def test_oracle_strained_elements_default_rule_is_the_fact_policy_grid_strained_element():
    """route: elements built on each side of the load, age and class limits read from the text of the fact policy.grid.strained_element, the function called with its defaults."""
    load_lim, age_lim, classes, text = _strain_rule_from_fact()
    now = pd.Timestamp(fact("world.now").value).date()
    days = int(round(age_lim * 365.25))
    assert abs(days / 365.25 - age_lim) < 0.005, "the construction needs a whole number of days at the age limit"
    at = (pd.Timestamp(now) - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    short = (pd.Timestamp(now) - pd.Timedelta(days=days - 20)).strftime("%Y-%m-%d")                     # 20 days younger: under the limit in two decimals
    good = [c for c in "ABCDE" if c not in classes][0]
    ge = _el([("AGE_AT", "substation", "in_service", 2000, good, "C1", "Z1", at), ("AGE_UNDER", "substation", "in_service", 2000, good, "C1", "Z1", short),
              ("CLASS_BAD1", "substation", "in_service", 2020, classes[0], "C1", "Z1", "2020-01-01"), ("CLASS_BAD2", "substation", "in_service", 2020, classes[1], "C1", "Z1", "2020-01-01"),
              ("CLASS_OK", "substation", "in_service", 2020, good, "C1", "Z1", "2020-01-01"), ("LOAD_AT", "substation", "in_service", 2020, good, "C1", "Z1", "2020-01-01"),
              ("LOAD_UNDER", "substation", "in_service", 2020, good, "C1", "Z1", "2020-01-01")])
    pk = pd.DataFrame({"net_key": ["LOAD_AT", "LOAD_UNDER"], "peak_percent": [load_lim, load_lim - 0.01], "valid": [True, True]})
    s = grid.strained_elements(pk, ge, context=M12).set_index("net_key")
    why = f"defaults against the fact text {text!r} (world.now {now})"
    assert _tri(s.at["AGE_AT", "age_strained"]) is True and _tri(s.at["AGE_UNDER", "age_strained"]) is False, why
    assert _tri(s.at["CLASS_BAD1", "age_strained"]) is True and _tri(s.at["CLASS_BAD2", "age_strained"]) is True and _tri(s.at["CLASS_OK", "age_strained"]) is False, why
    assert _tri(s.at["LOAD_AT", "load_strained"]) is True and _tri(s.at["LOAD_UNDER", "load_strained"]) is False, why
    assert s.at["AGE_AT", "age_years"] == round(days / 365.25, 2), f"{why}: the age is counted from world.now when as_of is not given"



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# zone_strain_summary
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def _strained_frame(rows):
    return pd.DataFrame(rows, columns=["net_key", "zone_key", "cus_key", "load_strained", "age_strained", "strained"]).astype({"load_strained": "boolean", "strained": "boolean", "age_strained": bool})


def test_oracle_zone_strain_summary_hand_worked_counts_by_zone_and_customer():
    """route: a hand worked example, ten elements in four zone and customer groups, every count written down; the parts add up to the totals."""
    T, F, U = True, False, pd.NA
    rows = [("e1", "Z1", "C1", T, T, T), ("e2", "Z1", "C1", F, T, T), ("e3", "Z1", "C1", F, F, F), ("e4", "Z1", "C1", U, F, U),            # Z1 C1: 4 elements
            ("e5", "Z1", "C2", T, F, T),                                                                                                       # Z1 C2: 1
            ("e6", "Z2", "C2", F, F, F), ("e7", "Z2", "C2", U, T, T), ("e8", "Z2", "C2", U, F, U),                                              # Z2 C2: 3
            ("e9", "Z3", None, T, T, T), ("e10", "Z3", None, F, F, F)]                                                                          # Z3 without customer: 2
    st = _strained_frame(rows)
    st0 = st.copy()
    zones = pd.DataFrame({"zone_key": ["Z1", "Z2", "Z3", "Z4"], "area_km2": [4.0, 7.0, 0.0, 3.0]})
    z = grid.zone_strain_summary(st, zones, context=M12)
    pd.testing.assert_frame_equal(st, st0)
    assert z.columns.tolist() == ["zone_key", "cus_key", "area_km2", "n_elements", "n_strained", "n_strained_unknown", "n_load_strained", "n_age_strained", "n_load_unknown", "strained_per_km2"]
    z = z.set_index(["zone_key", "cus_key"])
    count_cols = ["n_elements", "n_strained", "n_strained_unknown", "n_load_strained", "n_age_strained", "n_load_unknown"]
    assert z.index.tolist() == [("Z1", "C1"), ("Z1", "C2"), ("Z2", "C2"), ("Z3", "-")], "a zone without element is not listed; a missing customer is shown as '-'"
    assert z.loc[("Z1", "C1"), count_cols].tolist() == [4, 2, 1, 1, 2, 1] and z.loc[("Z1", "C1"), "strained_per_km2"] == 0.5 and z.loc[("Z1", "C1"), "area_km2"] == 4.0
    assert z.loc[("Z1", "C2"), count_cols].tolist() == [1, 1, 0, 1, 0, 0] and z.loc[("Z1", "C2"), "strained_per_km2"] == 0.25
    assert z.loc[("Z2", "C2"), count_cols].tolist() == [3, 1, 1, 0, 1, 2] and z.loc[("Z2", "C2"), "strained_per_km2"] == round(1 / 7.0, 3) == 0.143
    assert z.loc[("Z3", "-"), count_cols].tolist() == [2, 1, 0, 1, 1, 0] and np.isnan(z.loc[("Z3", "-"), "strained_per_km2"]), "area 0: no density"
    # the parts add up to the totals of the input
    assert z["n_elements"].sum() == len(st) == 10
    assert z["n_strained"].sum() == int((st["strained"] == True).sum()) == 5       # noqa: E712
    assert z["n_strained_unknown"].sum() == int(st["strained"].isna().sum()) == 2
    assert z["n_load_unknown"].sum() == int(st["load_strained"].isna().sum()) == 3
    assert z["n_load_strained"].sum() == int((st["load_strained"] == True).sum()) == 3        # noqa: E712
    assert z["n_age_strained"].sum() == int(st["age_strained"].sum()) == 4
    # a missing area gives no density either
    nan_area = grid.zone_strain_summary(st, zones.assign(area_km2=[4.0, np.nan, 2.0, 3.0]), context=M12).set_index(["zone_key", "cus_key"])
    assert np.isnan(nan_area.loc[("Z2", "C2"), "strained_per_km2"]) and nan_area.loc[("Z3", "-"), "strained_per_km2"] == 0.5
    # a strained element of a zone that the supply zone frame does not hold is refused
    with pytest.raises(FrameError, match="Z9"):
        grid.zone_strain_summary(_strained_frame([("x", "Z9", "C1", T, T, T)]), zones, context=M12)
