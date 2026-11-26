"""Procurement exposure part 2 (plan 5.4): hand computed frames, then the baseline release with the delivery frames built from the procurement tables by the plan's definition."""

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _price(rows):
    return pd.DataFrame(rows, columns=["sup_key", "itm_key", "unit_price", "currency", "change_reason"])


def test_price_steps_per_item_with_the_amendment_flag_and_sides():
    before = _price([("S1", "I1", 100.0, "EUR", "list"), ("S1", "I2", 50.0, "EUR", "list"), ("S1", "I3", 10.0, "EUR", "list")])
    after = _price([("S1", "I1", 118.0, "EUR", "framework_amendment"), ("S1", "I2", 50.0, "EUR", "list"), ("S1", "I4", 7.0, "EUR", "list")])
    s = fin.price_steps(before, after, context=M12).set_index("itm_key")
    assert s.loc["I1", ["price_before", "price_after", "step", "step_percent", "amended", "side"]].tolist() == [100.0, 118.0, 18.0, 18.0, True, "both"]
    assert s.loc["I2", ["step", "step_percent", "amended"]].tolist() == [0.0, 0.0, False]
    assert s.loc["I3", "side"] == "before_only" and np.isnan(s.loc["I3", "step"]) and s.loc["I4", "side"] == "after_only" and not s.loc["I4", "amended"] and np.isnan(s.loc["I4", "step_percent"])
    assert fin.price_steps(before, after, reason="list", context=M12).set_index("itm_key").loc["I2", "amended"], "the reason is a keyword"
    with pytest.raises(FrameError, match="changes its currency"):
        fin.price_steps(before, after.assign(currency="DKK"), context=M12)
    with pytest.raises(FrameError, match="more than one price"):
        fin.price_steps(pd.concat([before, before.iloc[:1]]), after, context=M12)
    with pytest.raises(FrameError, match="null prices"):
        fin.price_steps(before.assign(unit_price=np.nan), after, context=M12)
    assert fin.price_steps(before.iloc[:0], after.iloc[:0], context=M12).empty


def _steps():
    return fin.price_steps(_price([("S1", "I1", 100.0, "EUR", "list"), ("S1", "I2", 10.0, "DKK", "list")]), _price([("S1", "I1", 118.0, "EUR", "framework_amendment"), ("S1", "I2", 11.0, "DKK", "framework_amendment")]), context=M12)


def _demand():
    c = ["prj_key", "sup_key", "itm_key", "qty_open", "source", "after_effective_date"]
    return pd.DataFrame([("P1", "S1", "I1", 10.0, "po_line", True), ("P1", "S1", "I1", 5.0, "po_line", False), ("P1", "S1", "I2", 100.0, "reservation", False),
                         ("P2", "S1", "I2", 40.0, "po_line", True)], columns=c)


def test_open_exposure_prices_new_lines_and_reservations_and_leaves_old_lines_out():
    eur = fact("world.fx_eur_dkk_fixed").value
    r = fin.open_exposure(_demand(), _steps(), context=M12).set_index("prj_key")
    assert r.loc["P1", ["n_po_lines", "exposure_po_dkk", "reserved_open_qty", "exposure_reserved_dkk", "exposure_dkk"]].tolist() == [2, round(180 * eur, 2), 100.0, 100.0, round(180 * eur, 2) + 100.0]
    assert r.loc["P2", ["exposure_po_dkk", "exposure_dkk", "step_percent_max"]].tolist() == [40.0, 40.0, 10.0] and r.loc["P1", "step_percent_max"] == 18.0
    assert fin.open_exposure(_demand().iloc[:0], _steps(), context=M12).empty
    zero = fin.open_exposure(_demand().assign(qty_open=0.0), _steps(), context=M12)
    assert zero.exposure_dkk.eq(0).all() and zero.step_percent_max.isna().all(), "no open quantity, no exposure and no step"
    for bad, msg in ((_demand().assign(source="x"), "not po_line or reservation"), (_demand().assign(qty_open=[1.0, 2.0, -3.0, 4.0]), "negative"), (_demand().assign(itm_key="I9"), "no price step row"),
                     (_demand().assign(qty_open=np.nan), "qty_open")):
        with pytest.raises(FrameError, match=msg):
            fin.open_exposure(bad, _steps(), context=M12)
    with pytest.raises(FrameError, match="step is null"):
        fin.open_exposure(_demand(), _steps().assign(step=np.nan), context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        fin.open_exposure(_demand(), pd.concat([_steps(), _steps().iloc[:1]]), context=M12)


def test_review_cases_amendment_only_unpriced_rows_reservations_rounding_and_dtypes():
    before = _price([("S1", "I1", 100.0, "EUR", "list"), ("S1", "I2", 50.0, "EUR", "list"), ("S1", "I3", 10.0, "EUR", "list")])
    after = _price([("S1", "I1", 118.0, "EUR", "framework_amendment"), ("S1", "I2", 55.0, "EUR", "list")])
    steps = fin.price_steps(before, after, context=M12)
    d = pd.DataFrame({"prj_key": ["P1", "P1", "P1"], "sup_key": "S1", "itm_key": ["I1", "I2", "I3"], "qty_open": [10.0, 10.0, 10.0], "source": "po_line", "after_effective_date": [True, True, False]})
    eur = fact("world.fx_eur_dkk_fixed").value
    r = fin.open_exposure(d, steps, context=M12).iloc[0]
    assert r.exposure_dkk == round(180 * eur, 2) and r.n_po_lines == 3, "the ordinary list change of I2 is no exposure; the old line of I3 needs no step"
    both = fin.open_exposure(d, steps, only_amended=False, context=M12).iloc[0]
    assert both.exposure_dkk == round(230 * eur, 2)
    with pytest.raises(FrameError, match="step is null|no price step"):
        fin.open_exposure(d.assign(after_effective_date=True), steps, context=M12)
    tied = d.assign(source=["po_line", "reservation", "po_line"], po_key=[None, "PO-1", None])
    with pytest.raises(FrameError, match="tied to a PO line"):
        fin.open_exposure(tied, steps, context=M12)
    with pytest.raises(FrameError, match="prj_key"):
        fin.open_exposure(d.assign(prj_key=None), steps, context=M12)
    with pytest.raises(FrameError, match="true or false"):
        fin.open_exposure(d.assign(after_effective_date="False"), steps, context=M12)
    assert fin.open_exposure(d.assign(qty_open=pd.array([10, 10, 10], dtype="Int64")), steps, context=M12).exposure_dkk.iloc[0] == r.exposure_dkk
    half = fin.price_steps(_price([("S1", "I1", 1.0, "EUR", "list")]), _price([("S1", "I1", 1.025, "EUR", "framework_amendment")]), context=M12)
    h = fin.open_exposure(pd.DataFrame({"prj_key": ["P1"], "sup_key": "S1", "itm_key": "I1", "qty_open": [1.0], "source": "po_line", "after_effective_date": [True]}), half, context=M12)
    assert h.exposure_dkk.iloc[0] == round(0.03 * eur, 2) or h.exposure_dkk.iloc[0] == round(3 * eur) / 100, "2.5 foreign cents round to 3 (half away from zero), not to 2"
    with pytest.raises(FrameError, match="null amounts"):
        fin.exposure_bridge(fin.open_exposure(d, steps, context=M12), pd.DataFrame({"prj_key": ["P1"], "price_exposure_dkk": [np.nan]}), context=M12)


def test_the_bridge_identity_and_projects_in_one_definition_only():
    o = fin.open_exposure(_demand(), _steps(), context=M12)
    f = pd.DataFrame({"prj_key": ["P1", "P3"], "price_exposure_dkk": [2000.0, 500.0]})
    b = fin.exposure_bridge(o, f, context=M12).set_index("prj_key")
    assert b.index.tolist() == ["P1", "P2", "P3"] and b.loc["P3", ["open_dkk", "finance_dkk", "difference"]].tolist() == [0.0, 500.0, 500.0] and b.loc["P2", "finance_dkk"] == 0.0
    assert ((b.difference - (b.received_or_timing_dkk - b.reserved_dkk)).abs() < 0.011).all(), "the identity holds on every project"
    assert b.loc["P1", "reserved_dkk"] == 100.0 and abs(b.loc["P1", "received_or_timing_dkk"] - (2000.0 - o.set_index("prj_key").loc["P1", "exposure_po_dkk"])) < 0.011
    with pytest.raises(FrameError, match="more than one row"):
        fin.exposure_bridge(o, pd.concat([f, f]), context=M12)


def test_recoverable_follows_the_contract_and_fixed_price_passes_nothing():
    o = fin.open_exposure(_demand(), _steps(), context=M12)
    contracts = pd.DataFrame({"prj_key": ["P1", "P2"], "con_key": ["C1", "C2"], "price_type": ["indexed", "fixed_price"]})
    terms = pd.DataFrame({"con_key": ["C1"], "pass_through_percent": [50.0], "threshold_percent": [20.0]})
    r = fin.recoverable(o, terms, contracts, context=M12).set_index("prj_key")
    p1 = o.set_index("prj_key").loc["P1", "exposure_dkk"]
    assert r.loc["P1", ["recoverable_dkk", "absorbed_dkk", "pass_through_percent"]].tolist() == [round(p1 * 0.5, 2), round(p1 - round(p1 * 0.5, 2), 2), 50.0]
    assert r.loc["P2", ["recoverable_dkk", "absorbed_dkk", "pass_through_percent"]].tolist() == [0.0, 40.0, 0.0] and r.loc["P2", "price_type"] == "fixed_price"
    t = fin.recoverable(o, terms, contracts, apply_threshold=True, context=M12).set_index("prj_key")
    assert t.loc["P1", "recoverable_dkk"] == 0.0, "a step of 18 percent does not exceed the threshold of 20"
    assert fin.recoverable(o, terms.assign(threshold_percent=3.0), contracts, apply_threshold=True, context=M12).set_index("prj_key").loc["P1", "recoverable_dkk"] == round(p1 * 0.5, 2)
    assert fin.recoverable(o, terms.assign(threshold_percent=np.nan), contracts, apply_threshold=True, context=M12).set_index("prj_key").loc["P1", "recoverable_dkk"] == round(p1 * 0.5, 2), "no threshold in the clause"
    for bad, msg in ((dict(terms=terms.iloc[:0]), "no price adjustment terms"), (dict(contracts=contracts.iloc[:1]), "no customer contract"), (dict(terms=terms.assign(pass_through_percent=150.0)), "between 0 and 100"),
                     (dict(contracts=pd.concat([contracts, contracts.iloc[:1]])), "one row per project")):
        args = dict(terms=terms, contracts=contracts)
        args.update(bad)
        with pytest.raises(FrameError, match=msg):
            fin.recoverable(o, args["terms"], args["contracts"], context=M12)


def test_committed_cost_values_open_lines_by_project_and_cost_code():
    eur = fact("world.fx_eur_dkk_fixed").value
    open_ = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-2"], "line_no": [1, 2, 1], "prj_key": ["P1", "P1", "P2"], "qty_open": [10.0, 5.0, 2.0]})
    spot = pd.DataFrame({"po_key": ["PO-1", "PO-3"], "line_no": [2, 1], "prj_key": ["P1", "P1"], "qty_open": [5.0, 4.0]})
    pl = pd.DataFrame({"po_key": ["PO-1", "PO-1", "PO-2", "PO-3"], "line_no": [1, 2, 1, 1], "unit_price": [100.0, 20.0, 50.0, 1000.0], "currency": ["EUR", "EUR", "DKK", "DKK"], "cst_key": ["C-1", "C-1", "C-2", "C-1"]})
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "delivery_type": ["project_site", "project_site", "project_site"]})
    c = fin.committed_cost(open_, pl, po, spot_orders=spot, context=M12)
    e = c[(c.prj_key == "P1") & (c.currency == "EUR") & ~c.spot].iloc[0]
    assert e.committed == 1000.0 and e.n_lines == 1 and e.committed_dkk == round(1000 * eur, 2)
    sp = c[(c.prj_key == "P1") & (c.currency == "EUR") & c.spot].iloc[0]
    assert sp.committed == 100.0 and sp.n_lines == 1, "PO-1 line 2 is in both frames: counted once and flagged spot"
    s = c[(c.currency == "DKK") & c.spot].iloc[0]
    assert (s.prj_key, s.cst_key, s.committed, s.committed_dkk, s.n_lines) == ("P1", "C-1", 4000.0, 4000.0, 1)
    assert c[c.prj_key == "P2"].committed_dkk.tolist() == [100.0] and round(c.committed.sum(), 2) == 5200.0
    other = po.assign(delivery_type=["project_site", "warehouse", "project_site"])
    assert fin.committed_cost(open_, pl, other, context=M12).prj_key.tolist() == ["P1"] and fin.committed_cost(open_, pl, other, delivery_type="warehouse", context=M12).prj_key.tolist() == ["P2"]
    for bad, msg in (({"po": po.iloc[1:]}, "without a delivery_type"), ({"pl": pl.iloc[1:]}, "no order line"), ({"open_": pd.concat([open_, open_.iloc[:1]])}, "more than once"),
                     ({"open_": open_.assign(qty_open=-1.0)}, "qty_open"), ({"pl": pd.concat([pl, pl.iloc[:1]])}, "repeated keys")):
        a = dict(open_=open_, pl=pl, po=po)
        a.update(bad)
        with pytest.raises(FrameError, match=msg):
            fin.committed_cost(a["open_"], a["pl"], a["po"], context=M12)
    assert fin.committed_cost(open_.iloc[:0], pl, po, context=M12).empty
    with pytest.raises(FrameError, match="unit_price and a currency"):
        fin.committed_cost(open_, pl.assign(unit_price=np.nan), po, context=M12)
    with pytest.raises(FrameError, match="prj_key"):
        fin.committed_cost(open_.assign(prj_key=None), pl, po, context=M12)
