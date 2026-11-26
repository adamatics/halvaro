"""Activity (plan 5.2): hand computed synthetic frames, then the baseline release against the emission lines and the supplier invoices."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError, fact

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _m(rows=None):
    rows = rows or [("M1", "electricity", "kWh", 2, "SITE-01", "building"), ("M2", "electricity", "kWh", 2, "SITE-02", "ev_charging"), ("M3", "diesel", "l", 1, "SITE-01", "vehicle_pool"),
                    ("M4", "district_heat", "MWh", 2, "SITE-02", "building")]
    return pd.DataFrame(rows, columns=["mtr_key", "carrier", "unit", "scope", "site_key", "kind"])


def _c(rows=None):
    rows = rows or [("M1", "2025-01", 1000.0, "kWh", "renewable_certified", 800.0, "DKK", "SINV-1"), ("M1", "2025-02", 500.0, "kWh", "grid_mix", 450.0, "DKK", "SINV-2"),
                    ("M2", "2025-01", 300.0, "kWh", "grid_mix", 270.0, "EUR", "SINV-3"), ("M3", "2025-01", 100.0, "l", None, 200.0, "DKK", None),
                    ("M4", "2025-01", 2.5, "MWh", "supplier", 250.0, "EUR", "SINV-4")]
    return pd.DataFrame(rows, columns=["mtr_key", "period", "quantity", "unit", "contract_type", "cost_amount", "currency", "source_sinv_key"])


def test_check_meters_rules_and_proposed_maps():
    assert esg.check_meters(_m(), context=M12).empty
    bad = _m([("A", "electricity", "MWh", 2, "S", "b"), ("B", "diesel", "l", 2, "S", "b"), ("C", "coal", "t", 1, "S", "b"), ("A", "electricity", "kWh", 2, "S", "b")])
    r = esg.check_meters(bad, context=M12)
    assert sorted(zip(r.key, r.rule)) == [("A", "duplicate_meter"), ("A", "unit"), ("B", "scope"), ("C", "unknown_carrier")]
    assert esg.check_meters(_m().iloc[:0], context=M12).empty
    assert esg.check_meters(bad.iloc[:1], unit_by_carrier={"electricity": "MWh"}, scope_by_carrier={"electricity": 2}, context=M12).empty, "the maps are keywords"
    with pytest.raises(FrameError, match="lacks column"):
        esg.check_meters(_m().drop(columns="scope"), context=M12)


def test_consumption_by_groups_in_native_units_inside_the_window():
    r = esg.consumption_by(_c(), _m(), "carrier", "2025-01", "2025-02", context=M12)
    assert r[["period", "carrier", "unit", "quantity", "n_meters"]].values.tolist() == [["2025-01", "diesel", "l", 100.0, 1], ["2025-01", "district_heat", "MWh", 2.5, 1], ["2025-01", "electricity", "kWh", 1300.0, 2],
                                                                                           ["2025-02", "electricity", "kWh", 500.0, 1]]
    assert esg.consumption_by(_c(), _m(), "carrier", "2025-02", "2025-02", context=M12).quantity.tolist() == [500.0], "both ends inclusive, nothing outside"
    s = esg.consumption_by(_c(), _m(), "site", "2025-01", "2025-01", context=M12).set_index(["site", "unit"]).quantity
    assert s.to_dict() == {("SITE-01", "kWh"): 1000.0, ("SITE-01", "l"): 100.0, ("SITE-02", "MWh"): 2.5, ("SITE-02", "kWh"): 300.0}, "litres and kWh of one site stay apart"
    k = esg.consumption_by(_c(), _m(), "kind", "2025-01", "2025-01", context=M12)
    assert set(k.kind) == {"building", "ev_charging", "vehicle_pool"} and k.columns.tolist() == ["period", "kind", "unit", "quantity", "n_meters"]
    assert esg.consumption_by(_c().iloc[:0], _m(), "carrier", "2025-01", "2025-02", context=M12).empty
    for args, exc, msg in ((("region", "2025-01", "2025-02"), FrameError, "by must be"), (("carrier", "2025-3", "2025-04"), FrameError, "period text"), (("carrier", "2025-13", "2025-14"), FrameError, "period text"),
                           (("carrier", "2025-03", "2025-01"), FrameError, "after")):
        with pytest.raises(exc, match=msg):
            esg.consumption_by(_c(), _m(), *args, context=M12)
    with pytest.raises(FrameError, match="another unit than their meter"):
        esg.consumption_by(_c().assign(unit="MWh"), _m(), "carrier", "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="not in energy-esg.energy_meter"):
        esg.consumption_by(_c(), _m().iloc[1:], "carrier", "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        esg.consumption_by(pd.concat([_c(), _c().iloc[:1]]), _m(), "carrier", "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="null quantity"):
        esg.consumption_by(_c().assign(quantity=np.nan), _m(), "carrier", "2025-01", "2025-02", context=M12)


def test_electricity_contract_share_uses_the_contract_of_each_month():
    r = esg.electricity_contract_share(_c(), _m(), context=M12).set_index(["period", "site_key"])
    assert r.loc[("2025-01", "SITE-01")].tolist() == [1000.0, 1000.0, 1.0] and r.loc[("2025-02", "SITE-01")].tolist() == [500.0, 0.0, 0.0]
    assert r.loc[("2025-01", "SITE-02")].tolist() == [300.0, 0.0, 0.0] and len(r) == 3, "diesel and heat are not electricity"
    with pytest.raises(FrameError, match="in kWh"):
        esg.electricity_contract_share(_c().assign(unit="MWh"), _m().assign(unit="MWh"), context=M12)
    with pytest.raises(FrameError, match="contract_type"):
        esg.electricity_contract_share(_c().assign(contract_type=None), _m(), context=M12)


def test_energy_cost_keeps_the_currency_and_converts_only_on_request():
    r = esg.energy_cost(_c(), _m(), context=M12)
    assert r[["carrier", "unit", "currency", "quantity", "cost", "unit_price"]].values.tolist() == [["diesel", "l", "DKK", 100.0, 200.0, 2.0], ["district_heat", "MWh", "EUR", 2.5, 250.0, 100.0],
                                                                                                     ["electricity", "kWh", "DKK", 1500.0, 1250.0, 0.8333], ["electricity", "kWh", "EUR", 300.0, 270.0, 0.9]]
    assert "cost_dkk" not in r.columns
    eur = fact("world.fx_eur_dkk_fixed").value
    d = esg.energy_cost(_c(), _m(), to_dkk=True, context=M12).set_index(["carrier", "currency"]).cost_dkk
    assert d[("district_heat", "EUR")] == round(250 * eur, 2) and d[("electricity", "DKK")] == 1250.0
    assert esg.energy_cost(_c().assign(quantity=0.0), _m(), context=M12).unit_price.isna().all()
    with pytest.raises(FrameError, match="cost_amount or a currency"):
        esg.energy_cost(_c().assign(cost_amount=np.nan), _m(), context=M12)


def test_invoice_tie_out_status_per_invoice_and_unkeyed_rows_are_not_errors():
    si = pd.DataFrame({"sinv_key": ["SINV-1", "SINV-2", "SINV-3", "SINV-5"], "net_amount": [800.0, 450.03, 270.01, 9.0], "document_kind": ["energy", "energy", "po_goods", "energy"]})
    r = esg.invoice_tie_out(_c(), si, context=M12).set_index("source_sinv_key")
    assert r.status.to_dict() == {"SINV-1": "ok", "SINV-2": "outside_tolerance", "SINV-3": "not_energy", "SINV-4": "invoice_missing"} and "SINV-5" not in r.index and r.index.notna().all()
    assert r.loc["SINV-2", "difference"] == -0.03 and not r.loc["SINV-2", "within"] and not r.loc["SINV-3", "within"]
    assert esg.invoice_tie_out(_c(), si, tolerance=0.03, context=M12).set_index("source_sinv_key").loc["SINV-2", "status"] == "ok", "the tolerance is a keyword"
    two = _c().iloc[:1].assign(cost_amount=400.0)
    assert esg.invoice_tie_out(pd.concat([two, two.assign(period="2025-02")]), si, context=M12).set_index("source_sinv_key").loc["SINV-1", "cost_sum"] == 800.0, "one invoice can carry several rows"
    for bad, msg in ((dict(tolerance=-1.0), "tolerance"), (dict(tolerance=np.nan), "tolerance")):
        with pytest.raises(FrameError, match=msg):
            esg.invoice_tie_out(_c(), si, context=M12, **bad)
    with pytest.raises(FrameError, match="more than one row"):
        esg.invoice_tie_out(_c(), pd.concat([si, si.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="null cost_amount"):
        esg.invoice_tie_out(_c().assign(cost_amount=np.nan), si, context=M12)


def test_energy_use_mwh_needs_the_fuel_content_for_litres():
    c, m = _c(), _m()
    with pytest.raises(FrameError, match="kWh per litre.*fact that is needed"):
        esg.energy_use_mwh(c, m, context=M12)
    r = esg.energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0}, context=M12).set_index("carrier")
    assert r.loc["electricity", "mwh"] == 1.8 and r.loc["district_heat", "mwh"] == 2.5 and r.loc["diesel", "mwh"] == 1.0
    assert esg.energy_use_mwh(c[c.mtr_key != "M3"], m, context=M12).mwh.sum() == 4.3, "without litres no content is needed"
    for bad in (0, -1.0, np.nan, True, "10"):
        with pytest.raises(FrameError, match="positive number"):
            esg.energy_use_mwh(c, m, kwh_per_litre={"diesel": bad}, context=M12)
    with pytest.raises(FrameError, match="not kWh, MWh or l"):
        esg.energy_use_mwh(c.assign(unit="t").iloc[:1], m.assign(unit="t"), context=M12)


def test_review_cases_nulls_dtypes_site_tanks_basis_cents_and_rounding():
    sek = fact("world.fx_sek_dkk_fixed").value
    m, c = _m(), _c().assign(currency=["DKK", "DKK", "SEK", "DKK", "EUR"])
    r = esg.energy_cost(c, m, to_dkk=True, context=M12).set_index(["carrier", "currency"]).cost_dkk
    assert r[("electricity", "SEK")] == round(270 * sek, 2), "SEK converts at the fixed booking rate (group payment rates do not exist for SEK)"
    cents = _c().iloc[:1].assign(cost_amount=0.285, currency="EUR")
    eur = fact("world.fx_eur_dkk_fixed").value
    assert esg.energy_cost(cents, m, to_dkk=True, context=M12).cost_dkk.iloc[0] == round(0.28 * eur, 2) or esg.energy_cost(cents, m, to_dkk=True, context=M12).cost_dkk.iloc[0] == round(0.29 * eur, 2)
    two = pd.concat([_c().iloc[:1].assign(cost_amount=100.01, currency="EUR"), _c().iloc[1:2].assign(cost_amount=100.01, currency="EUR")])
    assert esg.energy_cost(two, m, to_dkk=True, context=M12).cost_dkk.iloc[0] == 2 * round(100.01 * eur, 2), "converted per row, then summed, as finance books each invoice"
    nosite = _m().assign(site_key=[None, "SITE-02", "SITE-01", "SITE-02"])
    with pytest.raises(FrameError, match="without a site_key"):
        esg.electricity_contract_share(_c(), nosite, context=M12)
    tank = _m().assign(kind=["building", "po_site_tank", "po_site_tank", "building"])
    assert set(esg.consumption_by(_c(), tank, "site", "2025-01", "2025-02", exclude_kinds=("po_site_tank",), context=M12).site) == {"SITE-01", "SITE-02"}
    assert esg.consumption_by(_c(), tank, "carrier", "2025-01", "2025-01", exclude_kinds=("po_site_tank",), context=M12).carrier.tolist() == ["district_heat", "electricity"]
    for bad in ("po_site_tank", ["po_site_tank", 3]):
        with pytest.raises(FrameError, match="exclude_kinds"):
            esg.consumption_by(_c(), tank, "carrier", "2025-01", "2025-01", exclude_kinds=bad, context=M12)
    for col, bad in (("quantity", ["1"] * 5), ("cost_amount", ["1"] * 5)):
        with pytest.raises(FrameError, match="must be numeric"):
            esg.energy_cost(_c().assign(**{col: bad}), _m(), context=M12)
    with pytest.raises(FrameError, match="period must be text"):
        esg.consumption_by(_c().assign(period=["2025-13"] + ["2025-01"] * 4), _m(), "carrier", "2025-01", "2025-12", context=M12)
    cat = _c().assign(currency=_c().currency.astype("category"))
    assert esg.energy_cost(cat, _m().assign(carrier=_m().carrier.astype("category")), context=M12).shape[0] == 4, "categorical keys group as text"
    si = pd.DataFrame({"sinv_key": ["SINV-1"], "net_amount": [800.0], "document_kind": ["energy"]})
    blank = esg.invoice_tie_out(_c().assign(source_sinv_key=["SINV-1", "", "", None, ""]), si, context=M12)
    assert blank.source_sinv_key.tolist() == ["SINV-1"], "an empty key is no key"
    near = esg.invoice_tie_out(_c().iloc[:1].assign(cost_amount=800.0249), si, context=M12).iloc[0]
    assert near.difference == 0.0249 and not near.within and esg.invoice_tie_out(_c().iloc[:1].assign(cost_amount=800.0149), si, context=M12).iloc[0].within, "the difference keeps four decimals"
    nullable = si.convert_dtypes()
    assert esg.invoice_tie_out(_c().convert_dtypes(), nullable, context=M12).status.tolist()[0] == "ok"
    assert esg.energy_use_mwh(_c(), _m(), kwh_per_litre=pd.Series({"diesel": 10.0}), context=M12).set_index("carrier").loc["diesel", "mwh"] == 1.0
    with pytest.raises(FrameError, match="more than one row"):
        esg.consumption_by(_c(), pd.concat([_m(), _m().iloc[:1]]), "carrier", "2025-01", "2025-02", context=M12)
    with pytest.raises(FrameError, match="without a carrier"):
        esg.consumption_by(_c(), _m().assign(carrier=[None, "electricity", "diesel", "district_heat"]), "carrier", "2025-01", "2025-02", context=M12)
