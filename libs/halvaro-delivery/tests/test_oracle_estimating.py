"""Oracle tests of the estimating functions: the expected values come from numbers worked by hand in the test, or from a plain python loop over the baseline tables, never from the function."""
import inspect
import re
import statistics

import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, fact

CTX = Context(stage="month12", role="r")
METHOD_ID = "policy.delivery.contingency_method"


def _method():
    """The PROPOSED method fact and the allowance line code it names (the reading under test)."""
    f = fact(METHOD_ID)
    code = re.search(r"CST-\d+", f.value)
    assert code, f"{METHOD_ID} ({f.status}) names no cost code: {f.value!r}"
    return f, code.group(0)


def _rows(advice):
    return advice.rows.set_index("measure")["value"]


def test_oracle_contingency_advice_net_of_the_allowance_line():
    """route: a hand worked example (ground share, overrun quantile, median of the per project allowance ratios) with the numbers written in the test, and the method text read through core.fact."""
    f, code = _method()
    msg = f"{METHOD_ID} = {f.value!r} (status {f.status})"
    assert "net of" in f.value and "legacy count" in f.value and "no percentage is hard coded" in f.value, msg
    assert inspect.signature(delivery.contingency_advice).parameters["contingency_code"].default == code, "the allowance line of the default is the one the method names; " + msg
    other = "CST-110"
    assert code != other

    od = pd.DataFrame({"measure": ["cost", "schedule"], "n": [9, 12], "n_legacy": [2, 5], "q25": [0.5, 0.04], "median": [0.6, 0.20], "q75": [0.9, 0.25]})
    cs = pd.DataFrame({"view": ["all_events"] * 5 + ["full_linked"] * 2,
                       "cause_code": ["ground_conditions", "ground_conditions", "ground_water", "weather", "supply_delay", "ground_conditions", "weather"],
                       "responsible_party": ["customer", "contractor", "contractor", "force_majeure", "supplier", "customer", "force_majeure"],
                       "days": [30, 20, 10, 25, 15, 30, 10]})
    # tender totals 1000, 1000, 500, 400; allowance line 100, 30, none, 80 -> ratios 10, 3, 0 and 20 percent
    ln = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P1", "P2", "P2", "P3", "P4", "P4"],
                       "type": ["tender", "tender", "budget", "final", "tender", "tender", "tender", "tender", "tender"],
                       "cst_key": ["CST-100", code, code, code, "CST-100", code, "CST-100", code, other],
                       "amount": [900.0, 100.0, 700.0, 5.0, 970.0, 30.0, 500.0, 80.0, 320.0]})
    before = (od.copy(), cs.copy(), ln.copy())

    a = delivery.contingency_advice(od, cs, ln, context=CTX)
    assert a.rows.measure.tolist() == ["ground_share", "schedule_overrun_q75", "gross_percent", "existing_percent", "net_percent"], msg
    # ground days 30 + 20 of 100 days: 0.5; overrun 0.25 -> 25 percent; gross 12.5; median of 0, 3, 10, 20 is 6.5 (the mean 8.25 and the median without the project without the line, 10, are not it); net 6.0
    assert _rows(a).tolist() == pytest.approx([0.5, 25.0, 12.5, 6.5, 6.0], abs=1e-9), msg
    assert (a.n, a.n_legacy) == (12, 5), "the number of projects and of legacy projects behind the overrun are shown; " + msg

    q25 = _rows(delivery.contingency_advice(od, cs, ln, quantile="q25", context=CTX))
    assert q25.index.tolist()[1] == "schedule_overrun_q25" and q25.tolist() == pytest.approx([0.5, 4.0, 2.0, 6.5, 0.0], abs=1e-9), "gross 2.0 is below the allowance 6.5: net is zero, not negative; " + msg
    med = _rows(delivery.contingency_advice(od, cs, ln, quantile="median", context=CTX))
    assert med.index.tolist()[1] == "schedule_overrun_median" and med.tolist() == pytest.approx([0.5, 20.0, 10.0, 6.5, 3.5], abs=1e-9), msg
    assert _rows(delivery.contingency_advice(od.assign(q75=[0.9, 0.065]), cs, ln, context=CTX))["net_percent"] == 0.0, "gross 3.25 against 6.5"
    assert _rows(delivery.contingency_advice(od.assign(q75=[0.9, 0.13]), cs, ln, context=CTX))["net_percent"] == pytest.approx(0.0, abs=1e-9), "gross equal to the allowance: net zero"
    assert _rows(delivery.contingency_advice(od.assign(q75=[0.9, 0.5]), cs, ln, context=CTX)).tolist() == pytest.approx([0.5, 50.0, 25.0, 6.5, 18.5], abs=1e-9), "no percentage is hard coded: it follows the input; " + msg

    two = _rows(delivery.contingency_advice(od, cs, ln, ground_causes=("ground_conditions", "ground_water"), context=CTX))
    assert two.tolist() == pytest.approx([0.6, 25.0, 15.0, 6.5, 8.5], abs=1e-9), "60 of 100 days"
    full = _rows(delivery.contingency_advice(od, cs, ln, view="full_linked", context=CTX))
    assert full.tolist() == pytest.approx([0.75, 25.0, 18.75, 6.5, 12.25], abs=1e-9), "30 of 40 days of the other view"
    sub = _rows(delivery.contingency_advice(od, cs, ln, projects=["P1", "P3"], context=CTX))
    assert sub.tolist() == pytest.approx([0.5, 25.0, 12.5, 5.0, 7.5], abs=1e-9), "median of 10 and 0 percent"
    assert _rows(delivery.contingency_advice(od, cs, ln, projects=["P4"], context=CTX))["existing_percent"] == pytest.approx(20.0, abs=1e-9)
    elsewhere = delivery.contingency_advice(od, cs, ln, contingency_code=other, context=CTX)
    assert _rows(elsewhere).tolist() == pytest.approx([0.5, 25.0, 12.5, 0.0, 12.5], abs=1e-9), "only P4 has CST-110 (80 percent): median of 0, 0, 0 and 80 is 0"
    cost = delivery.contingency_advice(od, cs, ln, schedule_measure="cost", context=CTX)
    assert _rows(cost).tolist() == pytest.approx([0.5, 90.0, 45.0, 6.5, 38.5], abs=1e-9) and (cost.n, cost.n_legacy) == (9, 2), "the row of the chosen measure decides"
    none = delivery.contingency_advice(od, cs, ln[ln.cst_key != code], context=CTX)
    assert _rows(none).tolist() == pytest.approx([0.5, 25.0, 12.5, 0.0, 12.5], abs=1e-9), "no tender carries the line: existing is zero"

    for was, now in zip(before, (od, cs, ln)):
        pd.testing.assert_frame_equal(was, now)


@pytest.mark.release
def test_oracle_contingency_advice_baseline_ratios(load):
    """route: the ground share and the allowance ratios recomputed with python loops over the baseline delay_event, estimate_version and estimate_line rows."""
    f, code = _method()
    msg = f"{METHOD_ID} = {f.value!r} (status {f.status})"
    de, ev, el = load("projects", "delay_event"), load("projects", "estimate_version"), load("projects", "estimate_line")
    pj = load("projects", "project")
    cs = de.groupby(["cause_code", "responsible_party"], as_index=False).agg(days=("days", "sum")).assign(view="all_events")
    tender = ev[ev["type"] == "tender"][["prj_key", "estimate_version"]]
    ln = el.merge(tender, on=["prj_key", "estimate_version"]).assign(type="tender")[["prj_key", "type", "cst_key", "amount"]]
    od = pd.DataFrame({"measure": ["schedule"], "n": [100], "n_legacy": [40], "q25": [0.1], "median": [0.2], "q75": [0.3]})

    days = {}
    for cause, d in zip(de["cause_code"], de["days"]):
        days[cause] = days.get(cause, 0) + int(d)
    ground = days["ground_conditions"] / sum(days.values())

    def existing(keys=None):
        total, line = {}, {}
        for p, c, a in zip(ln["prj_key"], ln["cst_key"], ln["amount"]):
            if keys is not None and p not in keys:
                continue
            total[p] = total.get(p, 0) + int(a)
            line[p] = line.get(p, 0) + (int(a) if c == code else 0)
        return statistics.median(100.0 * line[p] / total[p] for p in total)

    sets = {"all": None, "DE clay": set(pj[(pj["country"] == "DE") & (pj["soil_class"] == "clay")]["prj_key"]), "DK": set(pj[pj["country"] == "DK"]["prj_key"])}
    for name, keys in sets.items():
        got = _rows(delivery.contingency_advice(od, cs, ln, projects=None if keys is None else sorted(keys), context=CTX))
        ex = existing(keys)
        want = [ground, 30.0, ground * 30.0, ex, max(ground * 30.0 - ex, 0.0)]
        assert got.tolist() == pytest.approx(want, abs=6e-4), f"set {name}; {msg}"
        assert ex > 0, f"set {name} has projects with the allowance line"
