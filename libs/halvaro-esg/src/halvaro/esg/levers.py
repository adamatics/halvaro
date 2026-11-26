"""Low carbon levers (plan 5.7): the estimated saving of switching site diesel to HVO100 and of replacing an item by a lower footprint item, and the two best levers against a gap.

These are estimates for a tender discussion, not measurements, and they rest on synthetic factors (status VERIFY+synthetic). The biogenic treatment of HVO is a policy decision that is still needed:
the factor table is used as it stands and every result says so. Nothing here is read from a truth value.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, make_envelope

from ._guard import staged, unwrapped
from ._util import Provenance, _need
from .factors import product_basis_share
from .lines import current_basis

_L = tuple(f"energy-esg.emission_line.{c}" for c in ("prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"))
_F = tuple(f"energy-esg.emission_factor.{c}" for c in ("efac_key", "category", "region", "factor_set", "kgco2e_per_unit", "unit"))
_BIOGENIC = "biogenic carbon of HVO100 is taken as the factor table states it; the policy decision on its treatment is still needed (VERIFY)"
_SYNTH = "emission factors are synthetic with a VERIFY note: not for real reporting"


def _estimate(value: Any, function: str, sources: Sequence[str], *extra: str) -> Provenance:
    env = make_envelope(value, function, sources=sources, warnings=(_SYNTH, *extra), cls=Provenance)
    return cast(Provenance, dataclasses.replace(env, status="VERIFY+synthetic", synthetic=True))


_TARGETS = {"hvo100": ("fuel_hvo", "fuel_wtt_hvo")}                                   # PROPOSED: target fuel -> (combustion family, well to tank family)


@staged(sources=(*_L, *_F, "projects.project.prj_key", "projects.project.route_length_m"), oracle="py:repo_tests/test_oracle_levers_release.py::test_oracle_lever_fuel_switch_equals_a_line_by_line_repricing_of_the_baseline_diesel_lines")
def lever_fuel_switch(L: pd.DataFrame, F: pd.DataFrame, P: pd.DataFrame | None = None, to: str = "hvo100") -> object:
    """Use this when you need the kilograms CO2e that moving the site diesel of each project to HVO100 would save, per project and optionally per route metre.

    Kilograms CO2e saved per project (and per route metre with `P`, projects.project with route_length_m) if the site diesel of the project moved to HVO100, combustion plus well to tank. Diesel combustion lines are current-basis scope 1 lines whose factor family is fuel_diesel, the well to tank lines are the lines of the family fuel_wtt_diesel. Each diesel quantity is priced again with the HVO factor of the same factor set and region and the same unit; a missing HVO factor row raises FrameError. Property: 0 <= saved <= diesel_kgco2e as long as HVO is not worse. Lines without a project are left out. The result is an estimate with the status VERIFY+synthetic and a warning that the biogenic treatment of HVO100 is a policy decision still needed (VERIFY).

    Args:
        L: The energy-esg.emission_line table with the columns prj_key, le_key, period, scope, category, line_no, quantity, efac_key, kgco2e, is_superseded, restated_from_period, supersedes_line_no and unit.
        F: The energy-esg.emission_factor table with the columns efac_key, category, region, factor_set, kgco2e_per_unit and unit.
        P: Optional projects.project table with prj_key and route_length_m; when given, the per metre columns are added.
        to: The target fuel; only "hvo100" is known (PROPOSED: its combustion family fuel_hvo and well to tank family fuel_wtt_hvo).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns prj_key, diesel_litres, diesel_kgco2e (combustion plus well to tank), switched_kgco2e, saved_kgco2e, worse (the target factor is higher) and, with `P`, route_length_m and saved_kgco2e_per_m (null when the route length is not above zero), one row per project sorted by prj_key, kgco2e to three decimals.

    Raises:
        FrameError: `to` is not a known target fuel, or L or F lacks a column, or the line checks of current_basis fail (repeated line key, bad restatement links).
        FrameError: F has more than one row for a factor key, a fuel line has no efac_key, or L names a factor that F does not hold.
        FrameError: a diesel line has no quantity or no kgco2e, or its unit differs from the unit of its factor.
        FrameError: a target factor row has no kgco2e_per_unit, F has two target rows for the same family, set, region and unit, or no HVO factor row exists for the family, set, region and unit of a diesel line.
        FrameError: P lacks prj_key or route_length_m, or has more than one row for a project.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import lever_fuel_switch
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"]
        >>> L = pd.DataFrame([
        ...     ("PRJ-900001", "LE-900001", "2025-03", 1, "mobile_combustion", 1, 100.0, "EF-900001", 270.0, False, None, None, "l"),
        ...     ("PRJ-900001", "LE-900001", "2025-03", 3, "fuel_and_energy_related", 2, 100.0, "EF-900002", 60.0, False, None, None, "l")], columns=cols)
        >>> F = pd.DataFrame([
        ...     ("EF-900001", "fuel_diesel", "DE", "S1", 2.7, "l"), ("EF-900002", "fuel_wtt_diesel", "DE", "S1", 0.6, "l"),
        ...     ("EF-900003", "fuel_hvo", "DE", "S1", 0.2, "l"), ("EF-900004", "fuel_wtt_hvo", "DE", "S1", 0.5, "l")],
        ...     columns=["efac_key", "category", "region", "factor_set", "kgco2e_per_unit", "unit"])
        >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0]})
        >>> r = lever_fuel_switch(L, F, P, context=ctx)
        >>> r.value[["prj_key", "diesel_kgco2e", "switched_kgco2e", "saved_kgco2e", "saved_kgco2e_per_m"]].to_dict("records")
        [{'prj_key': 'PRJ-900001', 'diesel_kgco2e': 330.0, 'switched_kgco2e': 70.0, 'saved_kgco2e': 260.0, 'saved_kgco2e_per_m': 2.6}]
        >>> r.status
        'VERIFY+synthetic'
    """
    if to not in _TARGETS:
        raise FrameError(f"unknown target fuel {to!r}; known: {sorted(_TARGETS)}")
    _need(L, ["prj_key", "le_key", "period", "scope", "category", "line_no", "quantity", "efac_key", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "unit"], "energy-esg.emission_line")
    _need(F, ["efac_key", "category", "region", "factor_set", "kgco2e_per_unit", "unit"], "energy-esg.emission_factor")
    if F["efac_key"].duplicated().any():
        raise FrameError("energy-esg.emission_factor has more than one row for a factor key")
    comb, wtt = _TARGETS[to]
    L = L.assign(prj_key=L["prj_key"].astype(object)) if str(L["prj_key"].dtype) == "category" else L
    cur = unwrapped(current_basis)(L)
    cur = cur[cur["prj_key"].notna()]
    fuel_cats = ("mobile_combustion", "stationary_combustion", "fuel_and_energy_related")
    if cur.loc[cur["category"].isin(fuel_cats), "efac_key"].isna().any():
        raise FrameError("a fuel line has no efac_key: its fuel cannot be told")
    f = F.set_index("efac_key")
    if not set(cur["efac_key"].dropna()).issubset(set(f.index)):
        raise FrameError("energy-esg.emission_line names factors that energy-esg.emission_factor does not hold")
    cat = cur["efac_key"].map(f["category"])
    use = cur[cat.isin(["fuel_diesel", "fuel_wtt_diesel"])].assign(family=cat[cat.isin(["fuel_diesel", "fuel_wtt_diesel"])])
    if use["quantity"].isna().any():
        raise FrameError("diesel lines without a quantity cannot be priced again")
    if use["quantity"].isna().any() or use["kgco2e"].isna().any():
        raise FrameError("diesel lines without a quantity or kgco2e cannot be priced again")
    if (use["unit"].to_numpy() != use["efac_key"].map(f["unit"]).to_numpy()).any():
        raise FrameError("a diesel line has a unit that differs from the unit of its factor")
    target = F[F["category"].isin([comb, wtt])].set_index(["category", "factor_set", "region", "unit"])["kgco2e_per_unit"]
    if target.isna().any():
        raise FrameError(f"a {to} factor row has no kgco2e_per_unit")
    if target.index.duplicated().any():
        raise FrameError("energy-esg.emission_factor has two target rows for the same family, set, region and unit")
    fset, reg, unit = use["efac_key"].map(f["factor_set"]), use["efac_key"].map(f["region"]), use["efac_key"].map(f["unit"])
    want = use["family"].map({"fuel_diesel": comb, "fuel_wtt_diesel": wtt})
    keys = list(zip(want, fset, reg, unit))
    missing = sorted({k for k in keys if k not in target.index})
    if missing:
        raise FrameError(f"no {to} factor row for {missing[0][0]} in set {missing[0][1]}, region {missing[0][2]}, unit {missing[0][3]}")
    use = use.assign(_new=[float(target.loc[k]) for k in keys])
    use = use.assign(_switched=use["quantity"].astype(float) * use["_new"])
    g = use.groupby("prj_key").agg(diesel_kgco2e=("kgco2e", "sum"), switched_kgco2e=("_switched", "sum"))
    g["diesel_litres"] = use[use["family"] == "fuel_diesel"].groupby("prj_key")["quantity"].sum().reindex(g.index).fillna(0.0)
    g["saved_kgco2e"] = g["diesel_kgco2e"] - g["switched_kgco2e"]
    g["worse"] = g["saved_kgco2e"] < 0
    out = g.reset_index()[["prj_key", "diesel_litres", "diesel_kgco2e", "switched_kgco2e", "saved_kgco2e", "worse"]].round(3)
    if P is not None:
        _need(P, ["prj_key", "route_length_m"], "projects.project")
        if P["prj_key"].duplicated().any():
            raise FrameError("projects.project has more than one row for a project")
        ln = P.set_index("prj_key")["route_length_m"]
        out["route_length_m"] = out["prj_key"].map(ln)
        out["saved_kgco2e_per_m"] = (out["saved_kgco2e"] / out["route_length_m"].where(out["route_length_m"] > 0)).round(3)
    return _estimate(out.sort_values("prj_key").reset_index(drop=True), "halvaro.esg.levers.lever_fuel_switch", ("energy-esg.emission_line", "energy-esg.emission_factor"), _BIOGENIC)


@staged(sources=("inventory.item.itm_key", "inventory.item.category", "inventory.item.unit", "inventory.item.footprint_kgco2e_per_unit", "energy-esg.item_epd.itm_key", "energy-esg.item_epd.source",
                 "energy-esg.item_epd.verification", "energy-esg.emission_factor.category", "energy-esg.emission_factor.kgco2e_per_unit"), oracle="py:repo_tests/test_oracle_levers_release.py::test_oracle_lever_material_substitution_equals_the_direct_formula_on_baseline_item_pairs")
def lever_material_substitution(G: pd.DataFrame, item: pd.DataFrame, epd: pd.DataFrame, cand: pd.DataFrame | dict[str, Any], factors: pd.DataFrame) -> object:
    """Use this when you need the kilograms CO2e saved by replacing bought items with candidate items of a lower footprint.

    Kilograms CO2e saved when the bought quantities `G` (itm_key, quantity in the unit of the item) are replaced by the candidate items `cand` (a dict or frame itm_key -> cand_itm_key), times the counted share of the product footprints (the one row of the factor table, product_basis_share). The candidate must be an item of the same category and unit, else FrameError. The same item gives zero. A candidate with a higher footprint gives a negative saving and `worse` true. Quantities of the same item are summed; items of G without a candidate are left out. The estimate has the status VERIFY+synthetic and warns that the counted share is one row of the factor table and that equivalence of the candidate is not verified.

    Args:
        G: The bought quantities with the columns itm_key and quantity (in the unit of the item).
        item: The inventory.item table with the columns itm_key, category, unit and footprint_kgco2e_per_unit.
        epd: The energy-esg.item_epd table with the columns itm_key, source and verification (valid_from, when present, orders the rows of an item).
        cand: The candidate map, a dict itm_key -> cand_itm_key or a frame with the columns itm_key and cand_itm_key.
        factors: The energy-esg.emission_factor table with category and kgco2e_per_unit, from which product_basis_share reads the counted share.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns itm_key, cand_itm_key, quantity, unit, category, footprint_per_unit, cand_footprint_per_unit, counted_share, saved_kgco2e (three decimals), worse, cand_epd_verified (the latest EPD row of the candidate carries a verification text; the text itself is not judged) and equivalence ('unverified': whether the candidate does the same job is not in the data), sorted by itm_key.

    Raises:
        FrameError: G, item, epd or a candidate frame lacks a column, or item has more than one row for an item, or the candidate map names an item twice.
        FrameError: the bought quantities are not finite numbers of zero or more, or a row has no itm_key.
        FrameError: item does not hold an item or a candidate of the map, a candidate differs in category or unit from the item it replaces, or an item or its candidate has no footprint per unit.
        FrameError: the factor table has no usable counted share (see product_basis_share).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import lever_material_substitution
        >>> ctx = Context(stage="month12", role="analyst")
        >>> G = pd.DataFrame({"itm_key": ["ITM-900001"], "quantity": [10.0]})
        >>> item = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "category": ["steel", "steel"], "unit": ["kg", "kg"], "footprint_kgco2e_per_unit": [2.0, 1.0]})
        >>> epd = pd.DataFrame({"itm_key": ["ITM-900002"], "source": ["EPD"], "verification": ["checked"]})
        >>> factors = pd.DataFrame({"category": ["purchased_goods_product_footprint"], "kgco2e_per_unit": [0.5]})
        >>> r = lever_material_substitution(G, item, epd, {"ITM-900001": "ITM-900002"}, factors, context=ctx)
        >>> r.value[["itm_key", "cand_itm_key", "saved_kgco2e", "worse", "cand_epd_verified"]].to_dict("records")
        [{'itm_key': 'ITM-900001', 'cand_itm_key': 'ITM-900002', 'saved_kgco2e': 5.0, 'worse': False, 'cand_epd_verified': True}]
    """
    _need(G, ["itm_key", "quantity"], "the bought quantities")
    _need(item, ["itm_key", "category", "unit", "footprint_kgco2e_per_unit"], "inventory.item")
    _need(epd, ["itm_key", "source", "verification"], "energy-esg.item_epd")
    if item["itm_key"].duplicated().any():
        raise FrameError("inventory.item has more than one row for an item")
    if isinstance(cand, dict):
        cd = pd.DataFrame({"itm_key": list(cand), "cand_itm_key": list(cand.values())})
    else:
        _need(cand, ["itm_key", "cand_itm_key"], "the candidate map")
        cd = cand[["itm_key", "cand_itm_key"]]
    if cd["itm_key"].duplicated().any():
        raise FrameError("the candidate map names an item twice")
    share = unwrapped(product_basis_share)(factors)
    q = pd.to_numeric(G["quantity"], errors="coerce")
    if q.isna().any() or (q < 0).any() or not np.isfinite(q).all():
        raise FrameError("the bought quantities must be finite numbers of zero or more")
    if G["itm_key"].isna().any():
        raise FrameError("the bought quantities have a row without an itm_key")
    x = G.assign(quantity=q).groupby("itm_key", as_index=False)["quantity"].sum().merge(cd, on="itm_key", how="inner")
    it = item.set_index("itm_key")
    bad = sorted((set(x["itm_key"]) | set(x["cand_itm_key"])) - set(it.index))
    if bad:
        raise FrameError(f"inventory.item does not hold {bad[:3]}")
    a, b = it.loc[x["itm_key"]], it.loc[x["cand_itm_key"]]
    if (a["category"].to_numpy() != b["category"].to_numpy()).any() or (a["unit"].to_numpy() != b["unit"].to_numpy()).any():
        raise FrameError("a candidate must be of the same category and unit as the item it replaces")
    fp_a, fp_b = a["footprint_kgco2e_per_unit"].to_numpy(dtype=float), b["footprint_kgco2e_per_unit"].to_numpy(dtype=float)
    if np.isnan(fp_a).any() or np.isnan(fp_b).any():
        raise FrameError("an item or its candidate has no footprint per unit")
    ver = epd.assign(_v=epd["verification"].notna()).sort_values(["itm_key"] + (["valid_from"] if "valid_from" in epd.columns else []), kind="stable").groupby("itm_key")["_v"].last()
    out = pd.DataFrame({"itm_key": x["itm_key"].to_numpy(), "cand_itm_key": x["cand_itm_key"].to_numpy(), "quantity": x["quantity"].to_numpy(), "unit": a["unit"].to_numpy(), "category": a["category"].to_numpy(),
                        "footprint_per_unit": fp_a, "cand_footprint_per_unit": fp_b, "counted_share": share})
    out["saved_kgco2e"] = ((out["footprint_per_unit"] - out["cand_footprint_per_unit"]) * out["quantity"] * share).round(3)
    out["worse"] = out["saved_kgco2e"] < 0
    out["cand_epd_verified"] = out["cand_itm_key"].map(ver).fillna(False).astype(bool)
    out["equivalence"] = "unverified"
    return _estimate(out.sort_values("itm_key").reset_index(drop=True), "halvaro.esg.levers.lever_material_substitution", ("inventory.item", "energy-esg.item_epd", "energy-esg.emission_factor"),
                     "the counted share is one row of the factor table; equivalence of the candidate is not verified")


@staged(sources=("energy-esg.project_footprint.prj_key", "projects.project.route_length_m"), oracle="py:tests/test_oracle_levers.py::test_oracle_lever_report_hand_worked_numbers_and_ordering")
def lever_report(pm: pd.DataFrame, levers: pd.DataFrame, limit: float, *, top: int = 2) -> pd.DataFrame:
    """Use this when you need the best levers of one project, ranked by saving per route metre, against a customer limit per metre.

    The `top` (2) levers with the largest saving per route metre for one project against a customer limit. Only levers with a positive saving are ranked; ranking is on the unrounded saving. Savings of levers are not added up: two levers may act on the same kilograms.

    Args:
        pm: One row of per_metre with prj_key, route_length_m and kgco2e_per_m (or per_m_exact, which is used when present).
        levers: A frame with lever (name) and saved_kgco2e.
        limit: The customer limit in kg CO2e per route metre; a positive finite number.
        top: How many levers to return, a whole number of one or more (default 2).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns rank, lever, saved_kgco2e, saved_per_m, gap_per_m (per metre footprint less limit, zero when under), share_of_gap_closed (null when there is no gap), per_m_after and below_limit_after (at or below the limit; a footprint exactly at the limit is not above it), best lever first, ties in the order of the lever name. Empty when no lever has a positive saving.

    Raises:
        FrameError: pm lacks prj_key, route_length_m or the per metre column, or levers lacks lever or saved_kgco2e.
        FrameError: pm does not have exactly one row, the project has no route length above zero, or it has no finite footprint per metre.
        FrameError: limit is not a positive finite number, or top is not a whole number of one or more.
        FrameError: levers names a lever twice or has a lever without a finite saving.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import lever_report
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pm = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0], "kgco2e_per_m": [10.0]})
        >>> levers = pd.DataFrame({"lever": ["hvo", "steel", "worse"], "saved_kgco2e": [200.0, 100.0, -5.0]})
        >>> r = lever_report(pm, levers, 9.0, context=ctx)
        >>> r["lever"].tolist()
        ['hvo', 'steel']
        >>> r["saved_per_m"].tolist()
        [2.0, 1.0]
        >>> r["below_limit_after"].tolist()
        [True, True]
    """
    _need(pm, ["prj_key", "route_length_m"], "per_metre frame")
    _need(levers, ["lever", "saved_kgco2e"], "levers frame")
    if len(pm) != 1:
        raise FrameError("lever_report takes one project: pm must have exactly one row")
    if isinstance(limit, bool) or not isinstance(limit, (int, float, np.number)) or not np.isfinite(float(limit)) or limit <= 0:
        raise FrameError(f"limit must be a positive number of kg per metre, not {limit!r}")
    if isinstance(top, bool) or not isinstance(top, (int, np.integer)) or top < 1:
        raise FrameError("top must be a whole number, one or more")
    length = float(pm["route_length_m"].iloc[0])
    if not length > 0:
        raise FrameError("the project has no route length; a saving per metre cannot be stated")
    col = "per_m_exact" if "per_m_exact" in pm.columns else "kgco2e_per_m"
    _need(pm, [col], "per_metre frame")
    per_m = float(pm[col].iloc[0])
    if np.isnan(per_m):
        raise FrameError("the project has no footprint per metre")
    if levers["lever"].duplicated().any():
        raise FrameError("levers names a lever twice")
    lv = levers.assign(saved_kgco2e=pd.to_numeric(levers["saved_kgco2e"], errors="coerce"))
    if lv["saved_kgco2e"].isna().any() or not np.isfinite(lv["saved_kgco2e"]).all():
        raise FrameError("levers has a lever without a finite saving")
    if not np.isfinite(per_m):
        raise FrameError("the project has no finite footprint per metre")
    lv["saved_per_m"] = lv["saved_kgco2e"] / length
    gap = max(per_m - float(limit), 0.0)
    best = lv[lv["saved_per_m"] > 0].sort_values(["saved_per_m", "lever"], ascending=[False, True]).head(top).reset_index(drop=True)
    best["saved_per_m"] = best["saved_per_m"].round(3)
    best.insert(0, "rank", range(1, len(best) + 1))
    best["gap_per_m"] = round(gap, 3)
    best["share_of_gap_closed"] = (best["saved_per_m"] / gap).round(4) if gap > 0 else np.nan
    best["per_m_after"] = (per_m - best["saved_per_m"]).round(3)
    best["below_limit_after"] = (per_m - best["saved_per_m"]) <= float(limit) + 1e-9
    return best[["rank", "lever", "saved_kgco2e", "saved_per_m", "gap_per_m", "share_of_gap_closed", "per_m_after", "below_limit_after"]]
