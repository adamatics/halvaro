"""Activity data: meter checks, consumption by carrier, site or kind in native units, the contract share of electricity, energy cost, the invoice tie-out and energy use in MWh.

Units are never mixed (litres, kWh and MWh stay apart). The consumption table holds one row per meter and month; scope 2 emission lines come in two methods, consumption does not.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, convert, violations

from ._guard import staged
from ._util import _need

_UNIT_BY_CARRIER = {"diesel": "l", "petrol": "l", "natural_gas": "kWh", "electricity": "kWh", "district_heat": "MWh"}       # PROPOSED: the measured units of the baseline meters (candidate rule, not asserted)
_SCOPE_BY_CARRIER = {"diesel": 1, "petrol": 1, "natural_gas": 1, "electricity": 2, "district_heat": 2}                      # PROPOSED: same
_BY = {"carrier": "carrier", "site": "site_key", "kind": "kind"}
_PERIOD = r"\d{4}-\d{2}"
_C = ("energy-esg.energy_consumption.mtr_key", "energy-esg.energy_consumption.period", "energy-esg.energy_consumption.quantity", "energy-esg.energy_consumption.unit")
_M = ("energy-esg.energy_meter.mtr_key", "energy-esg.energy_meter.carrier", "energy-esg.energy_meter.unit")


def _numeric(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    for c in columns:
        if not pd.api.types.is_numeric_dtype(frame[c]) or pd.api.types.is_bool_dtype(frame[c]):
            raise FrameError(f"{what}.{c} must be numeric, not {frame[c].dtype}")


def _period(value: Any, what: str) -> str:
    if not isinstance(value, str) or not pd.Series([value]).str.fullmatch(_PERIOD).iloc[0] or not 1 <= int(value[5:]) <= 12:
        raise FrameError(f"{what} must be a period text like 2025-03, not {value!r}")
    return value


def _joined(c: pd.DataFrame, m: pd.DataFrame, cols_c: Sequence[str], cols_m: Sequence[str]) -> pd.DataFrame:
    _need(c, ["mtr_key", "period", "quantity", "unit", *cols_c], "energy-esg.energy_consumption")
    _need(m, ["mtr_key", "carrier", "unit", *cols_m], "energy-esg.energy_meter")
    if m["mtr_key"].duplicated().any():
        raise FrameError("energy-esg.energy_meter has more than one row for a mtr_key")
    if c.duplicated(["mtr_key", "period"]).any():
        raise FrameError("energy-esg.energy_consumption has more than one row for the same mtr_key and period")
    if c["period"].isna().any() or not c["period"].astype(str).str.fullmatch(_PERIOD).all() or not c["period"].astype(str).str[5:].astype(int).between(1, 12).all():
        raise FrameError("energy-esg.energy_consumption.period must be text like 2025-03 (month 01 to 12) for every row")
    _numeric(c, ["quantity"], "energy-esg.energy_consumption")
    obj = lambda f, cols: f.assign(**{k: f[k].astype(object) for k in cols if isinstance(f[k].dtype, pd.CategoricalDtype)})          # categorical keys group as text
    c, m = obj(c, ["mtr_key", "unit", *cols_c]), obj(m, ["mtr_key", "carrier", "unit", *cols_m])
    x = c.merge(m[["mtr_key", "carrier", "unit", *cols_m]].rename(columns={"unit": "meter_unit"}), on="mtr_key", how="left", validate="many_to_one", indicator=True)
    unknown = x["_merge"] == "left_only"
    if unknown.any():
        raise FrameError(f"{int(unknown.sum())} consumption rows name a meter that is not in energy-esg.energy_meter (for example {x.loc[unknown, 'mtr_key'].iloc[0]})")
    x = x.drop(columns="_merge")
    if x["carrier"].isna().any():
        raise FrameError(f"{int(x['carrier'].isna().sum())} consumption rows belong to a meter without a carrier")
    bad = x["unit"] != x["meter_unit"]
    if bad.any():
        raise FrameError(f"{int(bad.sum())} consumption rows have another unit than their meter (for example {x.loc[bad, 'mtr_key'].iloc[0]} {x.loc[bad, 'period'].iloc[0]}); units are never converted silently")
    if x["quantity"].isna().any():
        raise FrameError(f"{int(x['quantity'].isna().sum())} consumption rows have a null quantity")
    return x


@staged(sources=("energy-esg.energy_meter.mtr_key", "energy-esg.energy_meter.carrier", "energy-esg.energy_meter.scope", "energy-esg.energy_meter.unit"), oracle="py:tests/test_oracle_activity.py::test_oracle_check_meters_every_route")
def check_meters(m: pd.DataFrame, *, unit_by_carrier: Mapping[str, Any] = _UNIT_BY_CARRIER, scope_by_carrier: Mapping[str, Any] = _SCOPE_BY_CARRIER) -> pd.DataFrame:
    """Use this when you need to check the meter list against the unit and scope that each carrier must have.

    Violations (table, key, rule, detail) of the meter list: unknown_carrier, unit (not the unit of the carrier), scope (not the scope of the carrier), duplicate_meter.

    PROPOSED: the carrier maps are the units and scopes of the baseline meters; no file states the rule (candidate in the plan, ghg-inventory-method is planned).

    Args:
        m: The energy-esg.energy_meter table, with the columns mtr_key, carrier, scope and unit.
        unit_by_carrier: Map from carrier to its metered unit (PROPOSED default: diesel and petrol l, natural_gas and electricity kWh, district_heat MWh).
        scope_by_carrier: Map from carrier to its scope (PROPOSED default: diesel, petrol and natural_gas 1, electricity and district_heat 2).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A violation frame with the columns table, key, rule and detail, in a stable order; empty when the meters follow the rule.

    Raises:
        FrameError: m is not a DataFrame or lacks mtr_key, carrier, scope or unit.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import check_meters
        >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["diesel", "electricity"],
        ...                   "scope": [1, 2], "unit": ["kWh", "kWh"]})
        >>> out = check_meters(m, context=ctx)
        >>> out[["key", "rule"]].values.tolist()
        [['MTR-900001', 'unit']]
    """
    _need(m, ["mtr_key", "carrier", "scope", "unit"], "energy-esg.energy_meter")
    rows = []
    r: Any
    for r in m.itertuples():
        if r.carrier not in unit_by_carrier or r.carrier not in scope_by_carrier:
            rows.append(("energy-esg.energy_meter", r.mtr_key, "unknown_carrier", f"carrier {r.carrier!r} has no unit and scope in the rule"))
            continue
        if r.unit != unit_by_carrier[r.carrier]:
            rows.append(("energy-esg.energy_meter", r.mtr_key, "unit", f"{r.carrier} is metered in {unit_by_carrier[r.carrier]}, the meter says {r.unit}"))
        if r.scope != scope_by_carrier[r.carrier]:
            rows.append(("energy-esg.energy_meter", r.mtr_key, "scope", f"{r.carrier} is scope {scope_by_carrier[r.carrier]}, the meter says {r.scope}"))
    rows += [("energy-esg.energy_meter", k, "duplicate_meter", "mtr_key listed more than once") for k in m.loc[m["mtr_key"].duplicated(keep="first"), "mtr_key"]]
    return violations.frame(rows)


@staged(sources=(*_C, *_M, "energy-esg.energy_meter.site_key", "energy-esg.energy_meter.kind"), oracle="py:tests/test_energy_esg.py::test_lines_follow_consumption")
def consumption_by(c: pd.DataFrame, m: pd.DataFrame, by: str, p0: str, p1: str, *, exclude_kinds: Sequence[str] | None = ()) -> pd.DataFrame:
    """Use this when you need the consumption per period and carrier, site or kind in the native unit of the meters for a window of periods.

    Quantity per period and carrier, site or kind in the native unit of the meters, for the periods p0 to p1 inclusive. A carrier has one unit, so units never mix; a consumption row whose unit differs from its meter raises. `by` is carrier, site or kind.
    Caution (T12): the purchase order tank meters (kind po_site_tank) carry the administrative site, not the site where the fuel was used, so a site total mixes metered and allocated fuel (part of the litres of a site can be allocated, not metered; the share is computed, not stated here);
    exclude_kinds drops kinds from the result, for example ('po_site_tank',). The meters and the window decide the coverage.

    Args:
        c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity and unit.
        m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit, plus site_key when by is site and kind when by is kind or exclude_kinds is used.
        by: What to group by: carrier, site or kind.
        p0: First period of the window, text like 2025-03.
        p1: Last period of the window (inclusive), text like 2025-03.
        exclude_kinds: Meter kinds to drop before grouping (default none); a sequence of text, not one string.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns period, <by>, unit, quantity and n_meters (distinct meters), sorted by period, <by> and unit.

    Raises:
        FrameError: by is not carrier, site or kind; p0 or p1 is not a period text like 2025-03; p0 is after p1; exclude_kinds is a single string or holds non-text.
        FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
        FrameError: a period is not text like 2025-03 (month 01 to 12) or is null; quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier.
        FrameError: a consumption row has another unit than its meter (units are never converted silently).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import consumption_by
        >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"],
        ...                   "quantity": [100.0, 50.0], "unit": ["kWh", "kWh"]})
        >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"], "unit": ["kWh", "kWh"]})
        >>> out = consumption_by(c, m, "carrier", "2025-01", "2025-01", context=ctx)
        >>> out[["period", "carrier", "quantity", "n_meters"]].values.tolist()
        [['2025-01', 'electricity', 150.0, 2]]
    """
    if by not in _BY:
        raise FrameError(f"by must be one of {sorted(_BY)}, not {by!r}")
    a, b = _period(p0, "p0"), _period(p1, "p1")
    if a > b:
        raise FrameError(f"p0 {a} is after p1 {b}")
    if isinstance(exclude_kinds, str) or (exclude_kinds is not None and not all(isinstance(k, str) for k in exclude_kinds)):
        raise FrameError("exclude_kinds is a sequence of meter kinds, not a single string")
    x = _joined(c, m, [], list(dict.fromkeys(["kind"] if exclude_kinds else []) | dict.fromkeys([] if by == "carrier" else [_BY[by]])))
    if exclude_kinds:
        x = x[~x["kind"].isin(list(exclude_kinds))]
    x = x[(x["period"] >= a) & (x["period"] <= b)]
    col = _BY[by]
    out = x.groupby(["period", col, "unit"], as_index=False, dropna=False).agg(quantity=("quantity", "sum"), n_meters=("mtr_key", "nunique"))
    return out.rename(columns={col: by}).sort_values(["period", by, "unit"]).reset_index(drop=True)


@staged(sources=(*_C, *_M, "energy-esg.energy_meter.site_key", "energy-esg.energy_consumption.contract_type"))
def electricity_contract_share(c: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the share of electricity kWh on a renewable_certified contract per period and site.

    The share is taken from the contract of each month in the consumption table (not today's contract of the meter, T9). Only electricity meters count; their unit must be kWh. The share is null when a site has no kWh in a period.

    Args:
        c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity, unit and contract_type.
        m: The energy-esg.energy_meter table, with the columns mtr_key, carrier, unit and site_key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns period, site_key, kwh, renewable_kwh and share (renewable_kwh over kwh), sorted by period and site_key.

    Raises:
        FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
        FrameError: a period is not text like 2025-03 (month 01 to 12); quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
        FrameError: an electricity meter has no site_key; electricity consumption is not in kWh; an electricity row has no contract_type.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import electricity_contract_share
        >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"], "quantity": [300.0, 100.0],
        ...                   "unit": ["kWh", "kWh"], "contract_type": ["renewable_certified", "standard"]})
        >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"],
        ...                   "unit": ["kWh", "kWh"], "site_key": ["SITE-900001", "SITE-900001"]})
        >>> out = electricity_contract_share(c, m, context=ctx)
        >>> out[["site_key", "kwh", "renewable_kwh", "share"]].values.tolist()
        [['SITE-900001', 400.0, 300.0, 0.75]]
    """
    x = _joined(c, m, ["contract_type"], ["site_key"])
    x = x[x["carrier"] == "electricity"]
    if x["site_key"].isna().any():
        raise FrameError("electricity meters without a site_key: a share per site cannot place their consumption")
    if (x["unit"] != "kWh").any():
        raise FrameError("electricity consumption must be in kWh for a share")
    if x["contract_type"].isna().any():
        raise FrameError("electricity consumption rows without a contract_type")
    x["renewable"] = np.where(x["contract_type"] == "renewable_certified", x["quantity"], 0.0)
    out = x.groupby(["period", "site_key"], as_index=False).agg(kwh=("quantity", "sum"), renewable_kwh=("renewable", "sum"))
    out["share"] = np.where(out["kwh"] > 0, out["renewable_kwh"] / out["kwh"].where(out["kwh"] > 0), np.nan)
    return out.sort_values(["period", "site_key"]).reset_index(drop=True)


@staged(sources=(*_C, *_M, "energy-esg.energy_consumption.cost_amount", "energy-esg.energy_consumption.currency"), facts=("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed"), oracle="py:tests/test_oracle_activity.py::test_oracle_energy_cost_every_route")
def energy_cost(c: pd.DataFrame, m: pd.DataFrame, *, to_dkk: bool = False) -> pd.DataFrame:
    """Use this when you need the cost, quantity and unit price of energy per carrier, unit and currency.

    The currency is kept (DKK sites and EUR sites are never added, T20). With to_dkk the cost is also given in DKK at the fixed booking rates of core convert, converted per consumption row and summed. There is no window: all periods of the frame count, so the unit price is an average over them.
    The unit price is cost over quantity, four decimals, null without quantity.

    Args:
        c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity, unit, cost_amount and currency.
        m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit.
        to_dkk: When true, add cost_dkk (default false).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns carrier, unit, currency, quantity (three decimals), cost (two decimals), unit_price and, with to_dkk, cost_dkk, sorted by carrier, unit and currency.

    Raises:
        FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
        FrameError: a period is not text like 2025-03 (month 01 to 12); quantity or cost_amount is not numeric; quantity, cost_amount or currency is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
        BasisError: with to_dkk, a currency has no booking rate to DKK (known: DKK, EUR, SEK).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import energy_cost
        >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900001"], "period": ["2025-01", "2025-02"], "quantity": [100.0, 100.0],
        ...                   "unit": ["kWh", "kWh"], "cost_amount": [20.0, 30.0], "currency": ["DKK", "DKK"]})
        >>> m = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": ["electricity"], "unit": ["kWh"]})
        >>> out = energy_cost(c, m, context=ctx)
        >>> out[["carrier", "currency", "quantity", "cost", "unit_price"]].values.tolist()
        [['electricity', 'DKK', 200.0, 50.0, 0.25]]
    """
    x = _joined(c, m, ["cost_amount", "currency"], [])
    _numeric(x, ["cost_amount"], "energy-esg.energy_consumption")
    if x["cost_amount"].isna().any() or x["currency"].isna().any():
        raise FrameError("energy-esg.energy_consumption rows without a cost_amount or a currency")
    x = x.assign(cents=np.rint(x["cost_amount"].to_numpy(dtype=float) * 100).astype(np.int64))
    if to_dkk:                                                                       # per row (one invoice each), then summed: the cents tie to finance net_amount_dkk
        dkk = np.zeros(len(x), dtype=np.int64)
        for cur in x["currency"].unique():
            sel = (x["currency"] == cur).to_numpy()
            dkk[sel] = convert(pd.Series(x.loc[sel, "cents"].to_numpy()), str(cur), "DKK", basis="booking").to_numpy()
        x["dkk_cents"] = dkk
    agg = dict(quantity=("quantity", "sum"), cost=("cost_amount", "sum"), **({"dkk_cents": ("dkk_cents", "sum")} if to_dkk else {}))
    out = x.groupby(["carrier", "unit", "currency"], as_index=False).agg(**agg)
    out["unit_price"] = np.where(out["quantity"] > 0, np.round(out["cost"] / out["quantity"].where(out["quantity"] > 0), 4), np.nan)
    if to_dkk:
        out["cost_dkk"] = out.pop("dkk_cents") / 100.0
    out["quantity"], out["cost"] = out["quantity"].round(3), out["cost"].round(2)
    return out.sort_values(["carrier", "unit", "currency"]).reset_index(drop=True)


@staged(sources=("energy-esg.energy_consumption.source_sinv_key", "energy-esg.energy_consumption.cost_amount", "finance.supplier_invoice.sinv_key", "finance.supplier_invoice.net_amount",
                 "finance.supplier_invoice.document_kind"), oracle="py:tests/test_finance.py::test_energy_invoice_keys_link_energy_esg_to_supplier_invoices")
def invoice_tie_out(c: pd.DataFrame, si: pd.DataFrame, *, tolerance: float = 0.02) -> pd.DataFrame:
    """Use this when you need to tie the cost of the consumption rows to the net amount of the energy invoice they come from.

    The cost of the consumption rows per source_sinv_key is compared with the net amount of the energy invoice. Rows without a source_sinv_key (null or empty), such as purchase order fuel and the month after the last invoices (T19), are not an error and are not listed.
    PROPOSED: tolerance 0.02 as in the plan.

    Args:
        c: The energy-esg.energy_consumption table, with the columns source_sinv_key and cost_amount.
        si: The finance.supplier_invoice table, with the columns sinv_key, net_amount and document_kind.
        tolerance: The largest absolute difference that still counts as within (PROPOSED default 0.02); a finite number of zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns source_sinv_key, cost_sum, net_amount, difference, within (|difference| <= tolerance) and status (ok, outside_tolerance, invoice_missing, not_energy), sorted by source_sinv_key.

    Raises:
        FrameError: c lacks source_sinv_key or cost_amount; si lacks sinv_key, net_amount or document_kind.
        FrameError: tolerance is not a finite number of zero or more; finance.supplier_invoice has two rows for a sinv_key; cost_amount or net_amount is not numeric; a row with a source_sinv_key has a null cost_amount.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import invoice_tie_out
        >>> c = pd.DataFrame({"source_sinv_key": ["SINV-900001", "SINV-900001", "SINV-900002"], "cost_amount": [60.0, 40.0, 10.0]})
        >>> si = pd.DataFrame({"sinv_key": ["SINV-900001", "SINV-900002"], "net_amount": [100.0, 12.0], "document_kind": ["energy", "energy"]})
        >>> out = invoice_tie_out(c, si, context=ctx)
        >>> out[["source_sinv_key", "difference", "status"]].values.tolist()
        [['SINV-900001', 0.0, 'ok'], ['SINV-900002', -2.0, 'outside_tolerance']]
    """
    _need(c, ["source_sinv_key", "cost_amount"], "energy-esg.energy_consumption")
    _need(si, ["sinv_key", "net_amount", "document_kind"], "finance.supplier_invoice")
    if not isinstance(tolerance, (int, float, np.number)) or isinstance(tolerance, bool) or not np.isfinite(tolerance) or tolerance < 0:
        raise FrameError(f"tolerance must be a finite number, zero or more, not {tolerance!r}")
    if si["sinv_key"].duplicated().any():
        raise FrameError("finance.supplier_invoice has more than one row for a sinv_key")
    _numeric(c, ["cost_amount"], "energy-esg.energy_consumption")
    _numeric(si, ["net_amount"], "finance.supplier_invoice")
    keyed = c[c["source_sinv_key"].notna() & (c["source_sinv_key"].astype(str) != "")]
    if keyed["cost_amount"].isna().any():
        raise FrameError("energy-esg.energy_consumption rows with a source_sinv_key have a null cost_amount")
    g = keyed.assign(source_sinv_key=keyed["source_sinv_key"].astype(object)).groupby("source_sinv_key", as_index=False).agg(cost_sum=("cost_amount", "sum"))
    inv = si[["sinv_key", "net_amount", "document_kind"]].assign(sinv_key=si["sinv_key"].astype(object), net_amount=si["net_amount"].astype(float), document_kind=si["document_kind"].astype(object))
    out = g.assign(cost_sum=g["cost_sum"].astype(float)).merge(inv, left_on="source_sinv_key", right_on="sinv_key", how="left")
    out["difference"] = (out["cost_sum"] - out["net_amount"]).round(4)
    out["within"] = (out["difference"].abs() <= tolerance).fillna(False).astype(bool)
    out["status"] = np.where(out["sinv_key"].isna(), "invoice_missing", np.where(out["document_kind"] != "energy", "not_energy", np.where(out["within"], "ok", "outside_tolerance")))
    out["within"] = out["within"] & (out["status"] == "ok")
    out["cost_sum"] = out["cost_sum"].round(2)
    return out[["source_sinv_key", "cost_sum", "net_amount", "difference", "within", "status"]].sort_values("source_sinv_key").reset_index(drop=True)


_KWH_FACTOR = {"kWh": 1e-3, "MWh": 1.0}


@staged(sources=(*_C, *_M), oracle="py:tests/test_oracle_activity.py::test_oracle_energy_use_mwh_every_route")
def energy_use_mwh(c: pd.DataFrame, m: pd.DataFrame, *, kwh_per_litre: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Use this when you need the energy use per carrier in MWh.

    kWh is divided by 1,000 and MWh is taken as is. Litres need the energy content of the fuel, which no file holds (fact needed, VERIFY): pass kwh_per_litre as {carrier: kWh per litre} for them, or consumption in litres raises and names the missing fact.
    PROPOSED: kwh_per_litre has no default.

    Args:
        c: The energy-esg.energy_consumption table, with the columns mtr_key, period (text like 2025-03), quantity and unit.
        m: The energy-esg.energy_meter table, with the columns mtr_key, carrier and unit.
        kwh_per_litre: Map from carrier to kWh per litre for the carriers metered in litres (default none).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns carrier, unit (the metered unit), quantity (three decimals) and mwh (six decimals), sorted by carrier and unit.

    Raises:
        FrameError: a table lacks a needed column; energy-esg.energy_meter has two rows for a mtr_key; energy-esg.energy_consumption has two rows for the same mtr_key and period.
        FrameError: a period is not text like 2025-03 (month 01 to 12); quantity is not numeric or is null; a consumption row names a meter that is not in the meter table, or a meter without a carrier; a row has another unit than its meter.
        FrameError: a carrier is metered in litres and kwh_per_litre has no value for it, or the value is not a positive finite number; a unit is not kWh, MWh or l.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import energy_use_mwh
        >>> c = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2025-01", "2025-01"], "quantity": [5000.0, 100.0], "unit": ["kWh", "l"]})
        >>> m = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "diesel"], "unit": ["kWh", "l"]})
        >>> out = energy_use_mwh(c, m, kwh_per_litre={"diesel": 10.0}, context=ctx)
        >>> out[["carrier", "unit", "mwh"]].values.tolist()
        [['diesel', 'l', 1.0], ['electricity', 'kWh', 5.0]]
    """
    x = _joined(c, m, [], [])
    out = x.groupby(["carrier", "unit"], as_index=False).agg(quantity=("quantity", "sum"))
    factor = []
    r: Any
    for r in out.itertuples():
        if r.unit in _KWH_FACTOR:
            factor.append(_KWH_FACTOR[r.unit])
        elif r.unit == "l":
            if kwh_per_litre is None or r.carrier not in kwh_per_litre:
                raise FrameError(f"{r.carrier} is metered in litres: the energy content (kWh per litre) is a fact that is needed and VERIFY; pass kwh_per_litre={{'{r.carrier}': ...}}")
            v = kwh_per_litre[r.carrier]
            if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not np.isfinite(v) or v <= 0:
                raise FrameError(f"kwh_per_litre for {r.carrier} must be a positive number, not {v!r}")
            factor.append(float(v) / 1000.0)
        else:
            raise FrameError(f"unit {r.unit!r} of {r.carrier} is not kWh, MWh or l")
    out["mwh"] = (out["quantity"] * np.asarray(factor)).round(6)
    out["quantity"] = out["quantity"].round(3)
    return out.sort_values(["carrier", "unit"]).reset_index(drop=True)
