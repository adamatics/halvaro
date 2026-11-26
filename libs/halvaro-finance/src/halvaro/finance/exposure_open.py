"""Procurement exposure, part 2: the price step of an amendment, the open quantity exposure per project, its bridge to the finance definition, the recoverable part and the committed cost.

The function ids are those of the plan (halvaro.finance.exposure.*). The frames of halvaro-delivery are arguments (finance never imports delivery) and are described by their columns. Money is in the
currency of the price list or the order and converted to DKK in integer cents at the fixed booking rates of core convert.
"""
from __future__ import annotations

import datetime as dt
from typing import Mapping

import numpy as np
import pandas as pd

from halvaro.core import FrameError, convert

from ._guard import staged
from ._util import _need, _round_half_away

_PLAN_MODULE = "halvaro.finance.exposure"
_SOURCES_DEMAND = ("procurement.price_list.unit_price", "procurement.price_list.change_reason", "procurement.price_list.valid_from", "procurement.price_list.currency")


def _dkk(amount: np.ndarray, currency: pd.Series) -> np.ndarray:
    """DKK amounts of float amounts in a currency per row: the foreign cents round half away from zero, core convert converts at the fixed booking rate. A null amount or currency raises."""
    a = np.asarray(amount, dtype=float)
    if np.isnan(a).any() or currency.isna().any():
        raise FrameError("amounts and currencies must not be null")
    cents = _round_half_away(a * 100).astype(np.int64)
    out = np.zeros(len(cents), dtype=np.int64)
    for cur in currency.unique():
        m = (currency == cur).to_numpy()
        out[m] = convert(pd.Series(cents[m]), str(cur), "DKK", basis="booking").to_numpy()
    return out / 100.0


@staged(id=f"{_PLAN_MODULE}.price_steps", sources=_SOURCES_DEMAND)
def price_steps(price_before: pd.DataFrame, price_after: pd.DataFrame, *, reason: str = "framework_amendment") -> pd.DataFrame:
    """Use this when you need the change of the price of each supplier and item between the day before an effective date and the effective date.

    Rule: the two frames are joined on supplier and item. The step is the price after less the price before, and step_percent is the step over the price before in percent (four decimals; null when there is no price before or after, or when the price before is not above zero). A price counts as amended when the price in force after has the given change reason. Side says whether the item has a price on both dates, before only or after only.

    Args:
        price_before: Frame from price_list_on for the day before the effective date, with sup_key, itm_key, unit_price, currency and change_reason.
        price_after: Frame from price_list_on for the effective date, with the same columns.
        reason: The change reason that marks an amendment. Default "framework_amendment".
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with sup_key, itm_key, currency, price_before, price_after, step, step_percent, amended and side (both, before_only or after_only), sorted by supplier and item.

    Raises:
        FrameError: a column is missing, a frame has more than one price for a supplier and item or a null price, or the currency of a price differs between the two dates.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import price_steps
        >>> ctx = Context(stage="month12", role="analyst")
        >>> before = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [10.0], "currency": ["EUR"], "change_reason": ["list"]})
        >>> after = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "currency": ["EUR"], "change_reason": ["framework_amendment"]})
        >>> price_steps(before, after, context=ctx)[["step", "step_percent", "amended", "side"]].values.tolist()
        [[1.0, 10.0, True, 'both']]
    """
    cols = ["sup_key", "itm_key", "unit_price", "currency", "change_reason"]
    _need(price_before, cols, "price_list_on frame (before)")
    _need(price_after, cols, "price_list_on frame (after)")
    for f, name in ((price_before, "before"), (price_after, "after")):
        if f.duplicated(["sup_key", "itm_key"]).any():
            raise FrameError(f"the {name} price frame has more than one price for a supplier and item")
        if f["unit_price"].isna().any():
            raise FrameError(f"the {name} price frame has null prices")
    m = price_before[cols].merge(price_after[cols], on=["sup_key", "itm_key"], how="outer", suffixes=("_before", "_after"), indicator=True)
    both = m["_merge"] == "both"
    if (both & (m["currency_before"] != m["currency_after"])).any():
        raise FrameError("a price changes its currency between the two dates")
    out = pd.DataFrame({"sup_key": m["sup_key"], "itm_key": m["itm_key"], "currency": m["currency_after"].fillna(m["currency_before"]), "price_before": m["unit_price_before"].astype(float),
                        "price_after": m["unit_price_after"].astype(float)})
    out["step"] = (out["price_after"] - out["price_before"]).round(6)
    pos = out["price_before"] > 0
    out["step_percent"] = np.where(pos & both, np.round((out["price_after"] / out["price_before"].where(pos) - 1) * 100, 4), np.nan)
    out["amended"] = (m["change_reason_after"] == reason).to_numpy() & both.to_numpy()
    out["side"] = m["_merge"].map({"both": "both", "left_only": "before_only", "right_only": "after_only"}).astype(str)
    return out.sort_values(["sup_key", "itm_key"]).reset_index(drop=True)


def _open_qty_alias(frame: pd.DataFrame) -> pd.DataFrame:
    """The delivery frames (open_po_lines, ExposedDemand.combined, spot_orders) name the open quantity `remaining`; finance names it `qty_open`.
    Both are accepted, so the delivery frame goes in as it is (library-plans/README.md, dependency table: finance reads the delivery frame).
    A frame with both columns must hold the same numbers."""
    if "qty_open" not in frame.columns and "remaining" in frame.columns:
        return frame.rename(columns={"remaining": "qty_open"})
    if "qty_open" in frame.columns and "remaining" in frame.columns and not np.allclose(frame["qty_open"].to_numpy(dtype=float), frame["remaining"].to_numpy(dtype=float), equal_nan=True):
        raise FrameError("the frame has qty_open and remaining with different numbers")
    return frame


@staged(id=f"{_PLAN_MODULE}.open_exposure", sources=(*_SOURCES_DEMAND, "procurement.po_line.qty", "procurement.po_line.received_qty", "inventory.reservation.qty_open"))
def open_exposure(exposed_demand: pd.DataFrame, steps: pd.DataFrame, *, only_amended: bool = True) -> pd.DataFrame:
    """Use this when you need the added cost of a price step on the demand that is still open, per project, in DKK.

    Rule: the open quantity times the step of the item, converted to DKK at the booking rates and rounded to the cent. A purchase order line placed before the effective date was bought at the old price and carries no exposure. A free reservation is priced now. With only_amended the step of an ordinary price list change is not exposure, only the step of an amendment. The project set is the one of exposed_demand and is never rebuilt here.

    Args:
        exposed_demand: Frame with prj_key, sup_key, itm_key, qty_open (the name remaining is also accepted), source (po_line or reservation) and after_effective_date; a po_key column must be empty on reservation rows.
        steps: The result of price_steps (or a frame with sup_key, itm_key, currency, step and step_percent, and optionally amended), one row per supplier and item.
        only_amended: True counts only the steps of an amendment. Default True.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, n_po_lines, exposure_po_dkk, reserved_open_qty, exposure_reserved_dkk, exposure_dkk and step_percent_max (the largest step among the priced items of the project that have an open quantity, not weighted by exposure).

    Raises:
        FrameError: a column is missing, steps repeats a supplier and item, a demand row has a null project or quantity (or no after_effective_date on a PO line), a source is neither po_line nor reservation, a quantity is negative, a reservation has a po_key, a priced demand row has no step row or a null step, or qty_open and remaining disagree.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import open_exposure
        >>> ctx = Context(stage="month12", role="analyst")
        >>> demand = pd.DataFrame({"prj_key": ["PRJ-1"], "sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "qty_open": [5.0], "source": ["po_line"], "after_effective_date": [True]})
        >>> steps = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "currency": ["DKK"], "step": [2.0], "step_percent": [10.0]})
        >>> open_exposure(demand, steps, context=ctx)[["prj_key", "n_po_lines", "exposure_dkk"]].values.tolist()
        [['PRJ-1', 1, 10.0]]
    """
    exposed_demand = _open_qty_alias(exposed_demand)
    _need(exposed_demand, ["prj_key", "sup_key", "itm_key", "qty_open", "source", "after_effective_date"], "delivery exposed_demand frame")
    _need(steps, ["sup_key", "itm_key", "currency", "step", "step_percent"], "price_steps result")
    if steps.duplicated(["sup_key", "itm_key"]).any():
        raise FrameError("price_steps has more than one row for a supplier and item")
    d = exposed_demand
    # A free reservation is priced now, so its after_effective_date does not matter: the delivery frame leaves it null there and finance reads null as false.
    # A PO line needs the flag (a line placed before the effective date was bought at the old price).
    flag_missing = d["after_effective_date"].isna() & (d["source"] != "reservation")
    if d["qty_open"].isna().any() or flag_missing.any() or d["prj_key"].isna().any():
        raise FrameError("exposed_demand rows need prj_key, qty_open and, on a PO line, after_effective_date")
    d = d.assign(after_effective_date=d["after_effective_date"].where(d["after_effective_date"].notna(), False))
    if not pd.api.types.is_bool_dtype(d["after_effective_date"]) and not set(d["after_effective_date"].unique()) <= {True, False, 0, 1}:
        raise FrameError("exposed_demand.after_effective_date must be true or false")
    if "po_key" in d.columns and ((d["source"] == "reservation") & d["po_key"].notna()).any():
        raise FrameError("a reservation tied to a PO line (po_key set) is not free demand: its value is in the PO line")
    d = d.assign(qty_open=d["qty_open"].astype(float), after_effective_date=d["after_effective_date"].astype(bool))
    bad = sorted(set(d["source"]) - {"po_line", "reservation"})
    if bad:
        raise FrameError(f"exposed_demand source {bad[0]!r} is not po_line or reservation")
    if (d["qty_open"] < 0).any():
        raise FrameError("exposed_demand has a negative qty_open")
    x = d.merge(steps[["sup_key", "itm_key", "currency", "step", "step_percent", "amended"]] if "amended" in steps.columns else steps[["sup_key", "itm_key", "currency", "step", "step_percent"]].assign(amended=True),
                on=["sup_key", "itm_key"], how="left", validate="many_to_one")
    priced = ((x["source"] == "reservation") | x["after_effective_date"]).to_numpy()
    miss = x["currency"].isna().to_numpy() & priced
    if miss.any():
        raise FrameError(f"{int(miss.sum())} demand rows have no price step row (for example {x.loc[miss, 'itm_key'].iloc[0]}); price_steps must cover the items of the demand")
    if (x["step"].isna().to_numpy() & priced).any():
        raise FrameError("a price step is null: the item has no price on both dates")
    counts = priced & (x["amended"].fillna(False).astype(bool).to_numpy() | (not only_amended))
    step = x["step"].where(counts, 0.0).fillna(0.0)
    x["dkk"] = 0.0
    if counts.any():
        x.loc[counts, "dkk"] = _dkk((x.loc[counts, "qty_open"] * step[counts]).to_numpy(), x.loc[counts, "currency"])
    po, rs = x[x["source"] == "po_line"], x[x["source"] == "reservation"]
    g = pd.DataFrame({"prj_key": sorted(set(x["prj_key"]))}).set_index("prj_key")
    x["qty_open"] = x["qty_open"].astype(float)
    g["n_po_lines"] = po.groupby("prj_key").size().reindex(g.index, fill_value=0)
    g["exposure_po_dkk"] = po.groupby("prj_key")["dkk"].sum().reindex(g.index, fill_value=0.0)
    g["reserved_open_qty"] = rs.groupby("prj_key")["qty_open"].sum().reindex(g.index, fill_value=0.0)
    g["exposure_reserved_dkk"] = rs.groupby("prj_key")["dkk"].sum().reindex(g.index, fill_value=0.0)
    g["exposure_dkk"] = g["exposure_po_dkk"] + g["exposure_reserved_dkk"]
    g["step_percent_max"] = x[counts & (x["qty_open"] > 0).to_numpy()].groupby("prj_key")["step_percent"].max().reindex(g.index)
    return g.round({"exposure_po_dkk": 2, "exposure_reserved_dkk": 2, "exposure_dkk": 2, "reserved_open_qty": 3}).reset_index()


@staged(id=f"{_PLAN_MODULE}.exposure_bridge", sources=("finance.project_financials.price_exposure", "procurement.po_line.received_qty", "inventory.reservation.qty_open"), oracle="py:tests/test_oracle_exposure.py::test_oracle_exposure_bridge_identity_and_sums_on_seeded_random_frames")
def exposure_bridge(open_exposure_result: pd.DataFrame, finance_exposure_result: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need to explain the gap between the open quantity and the finance definitions of the price exposure, per project.

    Rule: difference is the finance exposure less the open exposure. received_or_timing_dkk is the finance exposure less the open purchase order part (what finance counts on lines already received or booked in another month) and reserved_dkk is what only the open definition counts. By construction difference equals received_or_timing_dkk less reserved_dkk, to the cent. A project in one result only is listed with 0 on the other side.

    Args:
        open_exposure_result: The result of open_exposure, with prj_key, exposure_po_dkk, exposure_reserved_dkk and exposure_dkk, one row per project.
        finance_exposure_result: The result of finance_exposure, with prj_key and price_exposure_dkk, one row per project.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, open_po_dkk, open_reserved_dkk, open_dkk, finance_dkk, difference, received_or_timing_dkk and reserved_dkk, sorted by project.

    Raises:
        FrameError: a column is missing, a result has more than one row for a project, or an amount is null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import exposure_bridge
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_po_dkk": [10.0], "exposure_reserved_dkk": [4.0], "exposure_dkk": [14.0]})
        >>> finance = pd.DataFrame({"prj_key": ["PRJ-1"], "price_exposure_dkk": [30.0]})
        >>> exposure_bridge(opened, finance, context=ctx)[["difference", "received_or_timing_dkk", "reserved_dkk"]].values.tolist()
        [[16.0, 20.0, 4.0]]
    """
    _need(open_exposure_result, ["prj_key", "exposure_po_dkk", "exposure_reserved_dkk", "exposure_dkk"], "open_exposure result")
    _need(finance_exposure_result, ["prj_key", "price_exposure_dkk"], "finance_exposure result")
    for f, name in ((open_exposure_result, "open_exposure"), (finance_exposure_result, "finance_exposure")):
        if f["prj_key"].duplicated().any():
            raise FrameError(f"{name} result has more than one row for a project")
    if finance_exposure_result["price_exposure_dkk"].isna().any() or open_exposure_result[["exposure_po_dkk", "exposure_reserved_dkk", "exposure_dkk"]].isna().any().any():
        raise FrameError("the exposure results must not hold null amounts")
    parts = open_exposure_result["exposure_po_dkk"] + open_exposure_result["exposure_reserved_dkk"]
    broken = (open_exposure_result["exposure_dkk"] - parts).abs() > 0.005
    if broken.any():
        first = open_exposure_result.loc[broken, "prj_key"].iloc[0]
        raise FrameError(f"the open_exposure result is inconsistent: exposure_dkk differs from exposure_po_dkk + exposure_reserved_dkk in {int(broken.sum())} project(s), for example {first}; the bridge identity needs them to agree")
    m = open_exposure_result[["prj_key", "exposure_po_dkk", "exposure_reserved_dkk", "exposure_dkk"]].merge(finance_exposure_result[["prj_key", "price_exposure_dkk"]], on="prj_key", how="outer").fillna(0.0)
    out = pd.DataFrame({"prj_key": m["prj_key"], "open_po_dkk": m["exposure_po_dkk"], "open_reserved_dkk": m["exposure_reserved_dkk"], "open_dkk": m["exposure_dkk"], "finance_dkk": m["price_exposure_dkk"]})
    out["difference"] = (out["finance_dkk"] - out["open_dkk"]).round(2)
    out["received_or_timing_dkk"] = (out["finance_dkk"] - out["open_po_dkk"]).round(2)
    out["reserved_dkk"] = out["open_reserved_dkk"]
    return out.sort_values("prj_key").reset_index(drop=True)


@staged(id=f"{_PLAN_MODULE}.recoverable", sources=("contracts.contract.price_type", "contracts.clause.param_value", "contracts.clause.param2_value"))
def recoverable(open_exposure_result: pd.DataFrame, terms: pd.DataFrame, contracts: pd.DataFrame, *, apply_threshold: bool = False, on: dt.date | str | pd.Timestamp | None = None) -> pd.DataFrame:
    """Use this when you need the part of the price exposure that the customer contract passes on to the customer, per project.

    Rule: exposure times the pass-through percent of the customer contract of the project, to the cent; a fixed price contract passes nothing on. The rest is absorbed. With apply_threshold (proposed False) nothing is passed on when the largest step of the project does not exceed the threshold percent of the terms; the default passes the percent on whatever the size of the step. Only the contracts of `contracts` are read from `terms`. A contract with more than one clause row needs `on`; then every used contract is read on that date and of the clauses in force the one with the latest start counts (never two).

    Args:
        open_exposure_result: The result of open_exposure, with prj_key, exposure_dkk and step_percent_max.
        terms: Frame from price_adjustment_terms with con_key, pass_through_percent and threshold_percent (null when none), and valid_from and valid_to when a contract has several clauses.
        contracts: Frame from contracts_for_project with prj_key, con_key and price_type, one row per project.
        apply_threshold: True passes nothing on when step_percent_max does not exceed threshold_percent. Default False (proposed).
        on: The date to read the clauses on (no time zone), needed when a contract has more than one clause row. Optional.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, con_key, price_type, exposure_dkk, pass_through_percent, threshold_percent, recoverable_dkk and absorbed_dkk, sorted by project.

    Raises:
        FrameError: a column is missing, contracts has more than one row for a project, a contract has several clause rows and on is missing or terms lacks valid_from and valid_to, on has a time zone, a clause has no valid_from or ends before it starts, no clause or two clauses with the same start are in force on the date, a project has no contract, a contract that is not fixed price has no terms, or a pass-through percent is outside 0 to 100.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import recoverable
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_dkk": [1000.0], "step_percent_max": [10.0]})
        >>> terms = pd.DataFrame({"con_key": ["CON-1"], "pass_through_percent": [50.0], "threshold_percent": [None]})
        >>> contracts = pd.DataFrame({"prj_key": ["PRJ-1"], "con_key": ["CON-1"], "price_type": ["indexed"]})
        >>> recoverable(opened, terms, contracts, context=ctx)[["prj_key", "recoverable_dkk", "absorbed_dkk"]].values.tolist()
        [['PRJ-1', 500.0, 500.0]]
        >>> recoverable(opened, terms, contracts.assign(price_type="fixed_price"), context=ctx)["recoverable_dkk"].tolist()
        [0.0]
    """
    _need(open_exposure_result, ["prj_key", "exposure_dkk", "step_percent_max"], "open_exposure result")
    _need(terms, ["con_key", "pass_through_percent", "threshold_percent"], "price_adjustment_terms frame")
    _need(contracts, ["prj_key", "con_key", "price_type"], "contracts_for_project frame")
    if contracts.duplicated("prj_key").any():
        raise FrameError("contracts_for_project needs one row per project")
    terms = terms[terms["con_key"].isin(set(contracts["con_key"]))]
    dated = {"valid_from", "valid_to"} <= set(terms.columns)
    many = terms.duplicated("con_key", keep=False)
    if many.any() and (on is None or not dated):
        what = "pass on= (the invoice date)" if on is None else "terms needs the columns valid_from and valid_to"
        raise FrameError(f"a contract has more than one price clause row: {what} to take the clause in force")
    if on is not None and dated:
        d = pd.Timestamp(on)
        if d.tzinfo is not None:
            raise FrameError("on must be a date without a time zone")
        d = d.normalize()
        vf, vt = pd.to_datetime(terms["valid_from"]), pd.to_datetime(terms["valid_to"])
        if vf.isna().any():
            raise FrameError("a price clause row has no valid_from")
        if (vt.notna() & (vt < vf)).any():
            raise FrameError("a price clause row has valid_to before valid_from")
        # Every used contract is read on the date, a single clause too: a clause outside its validity is not in force.
        inforce = terms.assign(_from=vf)[(vf <= d) & (vt.isna() | (vt >= d))]
        # A later clause revises the earlier one: of the clauses in force the one with the latest start counts. Two with the same start are ambiguous.
        picked = inforce[inforce["_from"] == inforce.groupby("con_key")["_from"].transform("max")]
        if picked.duplicated("con_key").any():
            raise FrameError(f"two price clauses start on the same date and are both in force on {d.date()} for contract {picked.loc[picked.duplicated('con_key'), 'con_key'].iloc[0]}")
        lacking = set(terms["con_key"]) - set(picked["con_key"])
        if lacking:
            raise FrameError(f"no price clause is in force on {d.date()} for contract {sorted(lacking)[0]}")
        terms = picked.drop(columns="_from")
    elif many.any():
        raise FrameError("a contract has more than one price clause row")
    x = open_exposure_result[["prj_key", "exposure_dkk", "step_percent_max"]].merge(contracts[["prj_key", "con_key", "price_type"]], on="prj_key", how="left", validate="one_to_one")
    if x["con_key"].isna().any():
        raise FrameError(f"{int(x['con_key'].isna().sum())} projects have no customer contract in contracts_for_project (for example {x.loc[x['con_key'].isna(), 'prj_key'].iloc[0]})")
    x = x.merge(terms[["con_key", "pass_through_percent", "threshold_percent"]], on="con_key", how="left", validate="many_to_one")
    fixed = x["price_type"] == "fixed_price"
    if (~fixed & x["pass_through_percent"].isna()).any():
        raise FrameError("a contract that is not fixed price (indexed or by unit price) has no price adjustment terms")
    pt = np.where(fixed, 0.0, x["pass_through_percent"].astype(float))
    if ((pt < 0) | (pt > 100)).any():
        raise FrameError("pass_through_percent must be between 0 and 100")
    if apply_threshold:
        below = x["threshold_percent"].notna() & (x["step_percent_max"] <= x["threshold_percent"].astype(float))
        pt = np.where(below, 0.0, pt)
    x["pass_through_percent"] = np.where(fixed, 0.0, x["pass_through_percent"].astype(float))
    x["recoverable_dkk"] = np.round(x["exposure_dkk"].to_numpy(dtype=float) * pt / 100.0, 2)
    x["absorbed_dkk"] = np.round(x["exposure_dkk"].to_numpy(dtype=float) - x["recoverable_dkk"].to_numpy(), 2)
    return x[["prj_key", "con_key", "price_type", "exposure_dkk", "pass_through_percent", "threshold_percent", "recoverable_dkk", "absorbed_dkk"]].sort_values("prj_key").reset_index(drop=True)


@staged(id=f"{_PLAN_MODULE}.committed_cost", sources=("procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.unit_price", "procurement.po_line.currency", "procurement.po_line.cst_key",
                                                      "procurement.purchase_order.po_key", "procurement.purchase_order.delivery_type"), facts=("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed"))
def committed_cost(open_po_lines: pd.DataFrame, po_line: pd.DataFrame, purchase_order: pd.DataFrame, *, spot_orders: pd.DataFrame | None = None, delivery_type: str = "project_site") -> pd.DataFrame:
    """Use this when you need the value of the purchase orders that are still open, by project and cost code, in the order currency and in DKK.

    Rule: the open quantity of each line (from open_po_lines and spot_orders; a line in both is counted once and flagged spot) times the unit price of its order line. Only orders of the given delivery type count (proposed "project_site"; orders for stock have no project and are dropped). DKK is converted at the booking rates.

    Args:
        open_po_lines: Frame from the delivery open_po_lines with po_key, line_no, prj_key and qty_open (the name remaining is also accepted).
        po_line: Frame procurement.po_line with po_key, line_no, unit_price, currency and cst_key, one row per order line.
        purchase_order: Frame procurement.purchase_order with po_key and delivery_type, one row per order.
        spot_orders: Frame from the delivery spot_orders with the same columns as open_po_lines. Optional.
        delivery_type: The delivery type of the orders that count. Default "project_site" (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with prj_key, cst_key, currency, spot, n_lines, committed and committed_dkk, sorted by project, cost code, currency and spot.

    Raises:
        FrameError: a column is missing, po_line or purchase_order repeats a key, an order line is listed twice, a quantity is null or negative, an open line has no order line or no price or currency, a quantity or a price is infinite, belongs to an order without a delivery type, or (of the counted type) has no project, or qty_open and remaining disagree.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import committed_cost
        >>> ctx = Context(stage="month12", role="analyst")
        >>> open_lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "prj_key": ["PRJ-1"], "qty_open": [4.0]})
        >>> lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "unit_price": [25.0], "currency": ["DKK"], "cst_key": ["CST-1"]})
        >>> orders = pd.DataFrame({"po_key": ["PO-1"], "delivery_type": ["project_site"]})
        >>> committed_cost(open_lines, lines, orders, context=ctx)[["prj_key", "cst_key", "spot", "committed_dkk"]].values.tolist()
        [['PRJ-1', 'CST-1', False, 100.0]]
    """
    key = ["po_key", "line_no"]
    open_po_lines = _open_qty_alias(open_po_lines)
    _need(open_po_lines, [*key, "prj_key", "qty_open"], "delivery open_po_lines frame")
    _need(po_line, [*key, "unit_price", "currency", "cst_key"], "procurement.po_line")
    _need(purchase_order, ["po_key", "delivery_type"], "procurement.purchase_order")
    if spot_orders is not None:
        spot_orders = _open_qty_alias(spot_orders)
        _need(spot_orders, [*key, "prj_key", "qty_open"], "delivery spot_orders frame")
    if po_line.duplicated(key).any() or purchase_order["po_key"].duplicated().any():
        raise FrameError("po_line or purchase_order has repeated keys")
    spot_keys = pd.MultiIndex.from_frame(spot_orders[key]) if spot_orders is not None else pd.MultiIndex.from_arrays([[], []])
    parts = [open_po_lines[[*key, "prj_key", "qty_open"]].assign(spot=pd.MultiIndex.from_frame(open_po_lines[key]).isin(spot_keys))]
    if spot_orders is not None:
        extra = spot_orders[[*key, "prj_key", "qty_open"]]
        extra = extra[~pd.MultiIndex.from_frame(extra[key]).isin(pd.MultiIndex.from_frame(open_po_lines[key]))]
        parts.append(extra.assign(spot=True))
    x = pd.concat(parts, ignore_index=True)
    if x.duplicated(key).any():
        raise FrameError("the same order line is listed more than once")
    if x["qty_open"].isna().any() or (x["qty_open"] < 0).any():
        raise FrameError("open lines need a qty_open of zero or more")
    x = x.merge(po_line[[*key, "unit_price", "currency", "cst_key"]], on=key, how="left", validate="many_to_one", indicator=True)
    if (x["_merge"] != "both").any():
        raise FrameError(f"{int((x['_merge'] != 'both').sum())} open lines have no order line in procurement.po_line")
    if x["unit_price"].isna().any() or x["currency"].isna().any():
        raise FrameError("order lines with open quantity need a unit_price and a currency")
    x = x.drop(columns="_merge").merge(purchase_order[["po_key", "delivery_type"]], on="po_key", how="left", validate="many_to_one")
    if x["delivery_type"].isna().any():
        raise FrameError("an open line belongs to an order without a delivery_type or not in procurement.purchase_order")
    x = x[x["delivery_type"] == delivery_type]
    # Orders for stock (another delivery type) have no project and are not project committed cost: they are dropped above. A project site line needs a project.
    if x["prj_key"].isna().any():
        raise FrameError("open lines of the counted delivery type need a prj_key")
    for c in ("qty_open", "unit_price"):
        if np.isinf(pd.to_numeric(x[c], errors="coerce")).any():
            raise FrameError(f"{c} must be finite, not infinity")
    x = x.assign(value=x["qty_open"] * x["unit_price"])
    x["dkk"] = _dkk(x["value"].to_numpy(), x["currency"]) if len(x) else np.array([])
    out = x.groupby(["prj_key", "cst_key", "currency", "spot"], as_index=False, dropna=False).agg(n_lines=("value", "size"), committed=("value", "sum"), committed_dkk=("dkk", "sum"))
    out[["committed", "committed_dkk"]] = out[["committed", "committed_dkk"]].round(2)
    return out.sort_values(["prj_key", "cst_key", "currency", "spot"]).reset_index(drop=True)
