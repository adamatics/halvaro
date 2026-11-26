"""Release oracle tests of supply_strain_answer and profile_rules: the expected values come from plain readings of the release tables (walks over the column values, a dict lookup, a groupby count, a hand written project filter), from properties that must hold (every output row is an input row, the answer carries exactly the pieces it was given, idempotence) or from small hand worked frames, never from the functions under test or their helpers."""
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, fact
from halvaro.delivery.supply import BlockedProjects

CTX = Context(stage="month12", role="r")
FRAMES = ("stock", "open_lines", "blocked_projects", "alerts", "spot_orders")


def _now():
    return pd.Timestamp(fact("world.now").value)


def _inputs(load, n_items=5):
    """The nine pieces of a supply answer for the release, built with the library's own supply functions on the release tables, and the item and zone lists."""
    now = _now().date()
    mv, rsv, prj = load("inventory", "stock_movement"), load("inventory", "reservation"), load("projects", "project")
    lt, ge, zone = load("inventory", "lead_time"), load("gis", "grid_element"), load("gis", "supply_zone")
    po, pl, gr, plist, perf = (load("procurement", t) for t in ("purchase_order", "po_line", "goods_receipt", "price_list", "supplier_performance"))
    stock = delivery.stock_on(mv, now, context=CTX)
    items = sorted(rsv["itm_key"].dropna().unique())[:n_items]
    site = stock.groupby("site_key").size().idxmax()
    blocked = delivery.blocked_projects(delivery.reserved_demand(rsv, mv, now, context=CTX), stock, now, items=items, active=delivery.active_on(prj, now, context=CTX), context=CTX)
    lead_on = delivery.lead_time_on(lt, now, context=CTX)
    zones = sorted(zone["zone_key"])
    thin = pd.concat([delivery.elements_per_spare_unit(stock, ge, items=items, site=site, zone_keys=zones, context=CTX),
                      delivery.elements_per_spare_unit(stock, ge, items=items, site=site, context=CTX)], ignore_index=True)
    kw = dict(stock=stock, open_lines=delivery.open_po_lines(pl, po, gr, now, context=CTX), blocked=blocked, lead_on=lead_on, alerts=delivery.lead_time_alerts(lead_on, context=CTX),
              performance=perf, spot=delivery.spot_orders(pl, po, plist, context=CTX), thin_cover=thin, supply_zone=zone, customer=load("crm", "customer"))
    return items, zones, kw


def _cut(frame, col, keys):
    """The rows of frame whose col is one of keys, in their order, by a walk over the column values (not an isin mask)."""
    want = set(keys)
    return frame.iloc[[i for i, v in enumerate(frame[col].tolist()) if v in want]].reset_index(drop=True)


def _absent(v):
    return v is None or (isinstance(v, float) and v != v) or v is pd.NA or v is pd.NaT


@pytest.mark.release
def test_oracle_supply_strain_answer_carries_exactly_the_cut_pieces(load):
    """halvaro.delivery.supply.supply_strain_answer: route: every frame of the answer compared with a walk over the column values of the input frame built from the release; nothing dropped, nothing invented, customers by a dict lookup."""
    items, zones, kw = _inputs(load)
    a = delivery.supply_strain_answer(items, zones[:2], context=CTX, **kw)
    pd.testing.assert_frame_equal(a.stock, _cut(kw["stock"], "itm_key", items))
    pd.testing.assert_frame_equal(a.open_lines, _cut(kw["open_lines"], "itm_key", items))
    pd.testing.assert_frame_equal(a.blocked_projects, _cut(kw["blocked"].items, "itm_key", items))
    pd.testing.assert_frame_equal(a.alerts, _cut(kw["alerts"], "itm_key", items))
    pd.testing.assert_frame_equal(a.spot_orders, _cut(kw["spot"], "itm_key", items))
    lead = _cut(kw["lead_on"], "itm_key", items)
    pd.testing.assert_frame_equal(a.lead_times, lead)
    suppliers = set(lead["sup_key"])
    pd.testing.assert_frame_equal(a.performance, _cut(kw["performance"], "sup_key", suppliers))
    assert set(a.performance["sup_key"]) <= suppliers, "performance rows only of the suppliers of the items"
    assert a.items == tuple(sorted(items)) and a.zones == tuple(sorted(zones[:2]))
    # every kept row exists in the input and the cut size equals a groupby count of the input
    for got, src in ((a.stock, kw["stock"]), (a.open_lines, kw["open_lines"]), (a.alerts, kw["alerts"]), (a.spot_orders, kw["spot"])):
        assert len(got) == sum(v in set(items) for v in src["itm_key"].tolist()) and set(got["itm_key"]) <= set(items)
    cus = kw["customer"].set_index("cus_key")["name"].to_dict()
    zn = kw["supply_zone"].set_index("zone_key")["cus_key"].to_dict()
    assert a.customers.columns.tolist() == ["zone_key", "cus_key", "name"]
    assert a.customers["zone_key"].tolist() == sorted(zones[:2]), "one customer row per zone, sorted by zone_key"
    assert a.customers["cus_key"].tolist() == [zn[z] for z in sorted(zones[:2])] and a.customers["name"].tolist() == [cus[zn[z]] for z in sorted(zones[:2])]
    # the thin cover keeps the row for all zones (null zone_key) and the rows of the zones passed, as passed
    tc = kw["thin_cover"]
    keep = [i for i, z in enumerate(tc["zone_key"].tolist()) if _absent(z) or z in set(zones[:2])]
    pd.testing.assert_frame_equal(a.thin_cover, tc.iloc[keep].reset_index(drop=True))
    assert a.thin_cover["zone_key"].isna().sum() == tc["zone_key"].isna().sum() and set(a.thin_cover["zone_key"].dropna()) == set(zones[:2])


@pytest.mark.release
def test_oracle_supply_strain_answer_is_idempotent_and_order_free(load):
    """halvaro.delivery.supply.supply_strain_answer: route: property checks on the release: the order and repeats of the keys do not matter, feeding the answer frames back gives the same answer, an empty cut is not an error."""
    items, zones, kw = _inputs(load)
    a = delivery.supply_strain_answer(items, zones, context=CTX, **kw)
    b = delivery.supply_strain_answer(list(reversed(items)) + list(items), tuple(reversed(zones)), context=CTX, **kw)
    assert a.items == b.items and a.zones == b.zones
    for f in a._fields[:-2]:
        pd.testing.assert_frame_equal(getattr(a, f), getattr(b, f))
    again = delivery.supply_strain_answer(items, zones, context=CTX, **{**kw, "stock": a.stock, "open_lines": a.open_lines, "blocked": BlockedProjects(a.blocked_projects, kw["blocked"].projects.iloc[:0]),
                                                                    "lead_on": a.lead_times, "alerts": a.alerts, "performance": a.performance, "spot": a.spot_orders, "thin_cover": a.thin_cover})
    for f in a._fields[:-2]:
        pd.testing.assert_frame_equal(getattr(a, f), getattr(again, f))
    assert set(a.zones) == set(kw["supply_zone"]["zone_key"]) and a.customers["zone_key"].tolist() == sorted(zones)
    none = delivery.supply_strain_answer(["ITM-NOT-IN-THE-RELEASE"], zones[:1], context=CTX, **kw)
    assert all(len(getattr(none, f)) == 0 for f in ("stock", "open_lines", "blocked_projects", "lead_times", "alerts", "performance", "spot_orders")), "an item in no frame gives empty cuts"
    assert len(none.customers) == 1
    nothing = delivery.supply_strain_answer([], [], context=CTX, **kw)
    assert len(nothing.stock) == len(nothing.customers) == 0 and nothing.items == nothing.zones == ()


@pytest.mark.release
def test_oracle_supply_strain_answer_refuses_a_broken_piece(load):
    """halvaro.delivery.supply.supply_strain_answer: route: the errors the docstring promises fire on release inputs with one piece broken."""
    items, zones, kw = _inputs(load)
    call = lambda **over: delivery.supply_strain_answer(over.pop("items", items), over.pop("zones", zones), context=CTX, **{**kw, **over})   # noqa: E731
    with pytest.raises(FrameError, match="not in gis.supply_zone"):
        call(zones=[*zones[:1], "ZONE-NOT-IN-THE-RELEASE"])
    cus = kw["customer"]
    with pytest.raises(FrameError, match="more than one row"):
        call(customer=pd.concat([cus, cus.iloc[:1]], ignore_index=True))
    for name in ("stock", "open_lines", "alerts"):
        with pytest.raises(FrameError, match="itm_key"):
            call(**{name: kw[name].drop(columns="itm_key")})
    with pytest.raises(FrameError, match="sup_key"):
        call(performance=kw["performance"].drop(columns="sup_key"))
    with pytest.raises(FrameError):
        call(supply_zone=kw["supply_zone"].drop(columns="cus_key"))
    with pytest.raises(FrameError):
        call(items=kw["stock"])
    with pytest.raises(FrameError):
        call(zones=None)
    with pytest.raises(FrameError):
        call(items=[1, 2])
    with pytest.raises(FrameError):
        call(stock=[])


# ------------------------------------------------------------------------------------------------------------ profile_rules
def _kept(project, rule, d):
    """The projects of a rule by a hand written pandas filter: equality on the text fields, the window on the length, the status from the two dates, the start and end from dates."""
    p = project.assign(_s=pd.to_datetime(project["start"]), _e=pd.to_datetime(project["actual_end"]))
    m = pd.Series(True, index=p.index)
    for c in ("country", "type", "soil_class"):
        if pd.notna(rule[c]):
            m &= p[c] == rule[c]
    if pd.notna(rule["status"]):
        completed = p["_s"].notna() & (p["_s"] <= d) & p["_e"].notna() & (p["_e"] < d)
        m &= completed if rule["status"] == "completed" else (p["_s"].notna() & ((p["_s"] > d) if rule["status"] == "planned" else ((p["_s"] <= d) & ~(p["_e"].notna() & (p["_e"] < d)))))
    if pd.notna(rule["route_min_m"]):
        m &= p["route_length_m"] >= rule["route_min_m"]
    if pd.notna(rule["route_max_m"]):
        m &= p["route_length_m"] <= rule["route_max_m"]
    if pd.notna(rule["start_from"]):
        m &= p["_s"] >= pd.Timestamp(rule["start_from"])
    if pd.notna(rule["end_from"]):
        m &= p["_e"] >= pd.Timestamp(rule["end_from"])
    return sorted(p.loc[m, "prj_key"])


@pytest.mark.release
def test_oracle_profile_rules_rows_select_the_projects_of_a_plain_filter(load):
    """halvaro.delivery.comparables.profile_rules: route: each row, handed to comparable_set as a rule, selects the same projects as a pandas filter of projects.project written from the row fields, and as the profile name does."""
    project = load("projects", "project")
    d = _now()
    rules = delivery.profile_rules(context=CTX)
    for row in rules.to_dict("records"):
        want = _kept(project, row, d)
        by_row = delivery.comparable_set(project, row, context=CTX)
        by_name = delivery.comparable_set(project, row["profile"], context=CTX)
        assert by_row.frame["prj_key"].tolist() == want == by_name.frame["prj_key"].tolist(), row["profile"]
        assert by_name.profile == row["profile"]
        assert set(want) <= set(project["prj_key"])
        assert len(want) <= len(project)
