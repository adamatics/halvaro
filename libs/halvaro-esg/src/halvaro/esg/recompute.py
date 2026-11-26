"""Recomputation of emission lines from the activity data and the factors, the oracle that checks the lines of the estate.

Scope 1 (fuels), scope 2 (electricity and district heat, both methods) and scope 3.3 (well to tank of the fuels) are rebuilt per meter and month from the consumption; waste lines per site, month
and fraction from the waste records. The factor is the one valid on the first day of the line period (T22). Purchase order fuel (kind po_site_tank) can be HVO, which the meter does not say: those
meters are left out unless `include_tanks` is set. Family choices that no file states are keywords marked proposed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import _day, _days, _need
from .factors import family_key

_FUEL_CATEGORY = {"diesel": "fuel_diesel", "petrol": "fuel_petrol", "natural_gas": "fuel_natural_gas"}
_WTT_CATEGORY = {"diesel": "fuel_wtt_diesel", "petrol": "fuel_wtt_petrol", "natural_gas": "fuel_wtt_natural_gas"}
_KEYS = ["ref_key", "period", "scope", "ghg_category", "method", "category", "subcategory"]
_EXPECTED_COLS = [*_KEYS, "quantity", "unit", "efac_key", "factor", "expected_kg"]
_C = tuple(f"energy-esg.energy_consumption.{c}" for c in ("mtr_key", "period", "quantity", "unit", "contract_type"))
_M = tuple(f"energy-esg.energy_meter.{c}" for c in ("mtr_key", "carrier", "kind", "country", "site_key", "le_key"))
_F = tuple(f"energy-esg.emission_factor.{c}" for c in ("efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"))


def _pick(f: pd.DataFrame, want: pd.DataFrame) -> pd.DataFrame:
    """For each row of `want` (category, carrier, region, method, date) the one factor row of that family valid on the date: efac_key, factor and factor_set; no or two rows raise."""
    fx = _days(f, ["valid_from", "valid_to"], "energy-esg.emission_factor")
    fx = fx.assign(_fam=unwrapped(family_key)(f).to_numpy())
    w = want.reset_index(drop=True)
    w = w.assign(_fam=unwrapped(family_key)(w.assign(carrier=w["carrier"], method=w["method"], category=w["category"], region=w["region"])).to_numpy(), _row=np.arange(len(w)))
    m = w.merge(fx[["_fam", "efac_key", "kgco2e_per_unit", "factor_set", "valid_from", "valid_to", *(["unit"] if "unit" in fx.columns else [])]], on="_fam", how="left")
    ok = m["valid_from"].notna() & (m["valid_from"] <= m["date"]) & (m["valid_to"].isna() | (m["valid_to"] >= m["date"]))
    hit = m[ok]
    got = hit.groupby("_row").size().reindex(w.index, fill_value=0)
    if (got == 0).any():
        i = int(got[got == 0].index[0])
        raise FrameError(f"{int((got == 0).sum())} lines have no valid factor (for example {w.loc[i, '_fam']} on {cast(Any, w.loc[i, 'date']).date()})")
    if (got > 1).any():
        i = int(got[got > 1].index[0])
        raise FrameError(f"{int((got > 1).sum())} lines have more than one valid factor (for example {w.loc[i, '_fam']} on {cast(Any, w.loc[i, 'date']).date()})")
    h = hit.set_index("_row").loc[np.arange(len(w))]
    return pd.DataFrame({"efac_key": h["efac_key"].to_numpy(), "factor": h["kgco2e_per_unit"].to_numpy(dtype=float), "factor_set": h["factor_set"].to_numpy(), "unit": h["unit"].to_numpy() if "unit" in h else None})


def _restate_spec(restate: Mapping[str, Any] | None) -> tuple[int, pd.Timestamp] | None:
    """(year, factor_date) of a restate mapping or None; anything else than {'year': 2025, 'factor_date': '2026-01-01'} raises."""
    if restate is None:
        return None
    if not isinstance(restate, Mapping) or set(restate) != {"year", "factor_date"}:
        raise FrameError("restate is {'year': 2025, 'factor_date': '2026-01-01'}")
    y = restate["year"]
    if isinstance(y, bool) or not isinstance(y, (int, np.integer)) or not 1900 <= int(y) <= 2200:
        raise FrameError("restate year must be a whole year from 1900 to 2200")
    return int(y), _day(restate["factor_date"], "restate factor_date")


def _restate_dates(period: pd.Series, restate: Mapping[str, Any] | None) -> pd.Series:
    p = period.astype(str)
    if not p.str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise FrameError(f"period must be text YYYY-MM, not {p[~p.str.fullmatch(r'\d{4}-(0[1-9]|1[0-2])')].iloc[0]!r}")
    spec = _restate_spec(restate)
    if spec and len(p) and not (p.str[:4] == str(spec[0])).any():
        raise FrameError(f"restate year {spec[0]} has no period in the data")
    try:
        d = pd.to_datetime(p + "-01", format="%Y-%m-%d")
    except (ValueError, TypeError) as e:
        raise FrameError(f"period must be text YYYY-MM: {e}") from None
    if spec:
        d = d.where(p.str[:4] != str(spec[0]), spec[1])
    return d


@staged(sources=(*_C, *_M, *_F, "energy-esg.energy_meter.valid_from"), oracle="py:tests/test_energy_esg.py::test_lines_follow_consumption")
def expected_lines_s123(c: pd.DataFrame, m: pd.DataFrame, f: pd.DataFrame, *, heat_region_by_site: Mapping[str, Any] | None = None, restate: Mapping[str, Any] | None = None, include_tanks: bool = False, contract_types: Sequence[str] = ("grid_mix", "renewable_certified")) -> pd.DataFrame:
    """Use this when you need the scope 1, scope 2 and scope 3.3 emission lines that the consumption of each meter and month should produce.

    The scope 1, scope 2 (location and market) and scope 3.3 lines expected from the consumption of each meter and month, one row per meter, month and line kind. Scope 1 category is stationary_combustion for gas and generator
    meters, else mobile_combustion; scope 3.3 is the well to tank factor of the same fuel (region EU). Electricity location uses the grid average of the country; market uses certified renewable
    in a month whose contract is renewable_certified, else the residual mix. District heat uses the network of the site (`heat_region_by_site`, required when heat meters are present; the networks
    are not in any table). `restate={'year': 2025, 'factor_date': '2026-01-01'}` takes the factors valid on that date for the periods of that year (the restated basis); without it the factor of
    the first day of each period (as first booked). Scope 1 lines of the estate are split over projects: compare with recompute_diff, which sums per meter. Meters of kind po_site_tank are left out
    unless include_tanks (their fuel can be HVO, which the meter does not say; with include_tanks a tank filled with HVO does not tie, because the meter does not say which fuel the purchase order delivered).
    Electricity contract types other than `contract_types` (PROPOSED: grid_mix and renewable_certified; null is the residual mix) raise, as do negative or null quantities and a factor unit that differs from the line unit.

    Args:
        c: The energy-esg.energy_consumption table with the columns mtr_key, period (text YYYY-MM), quantity, unit and contract_type; one row per meter and period.
        m: The energy-esg.energy_meter table with the columns mtr_key (one row per meter), carrier, kind, country, site_key, unit and le_key.
        f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set (and unit, which must then equal the consumption unit).
        heat_region_by_site: Mapping (or Series) from site_key to the heat network region; required when district heat meters are present, else None.
        restate: None for the factors of the first day of each period (as first booked), or a mapping with exactly the keys year and factor_date for the restated basis of that year.
        include_tanks: True to keep the meters of kind po_site_tank, which are left out otherwise.
        contract_types: The electricity contract types that are accepted (PROPOSED: grid_mix and renewable_certified); another non null type raises.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns ref_key (the meter), period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor and expected_kg (quantity times factor, rounded to 3 decimals), sorted by ref_key, period, scope, ghg_category and method; empty with these columns when no line is expected.

    Raises:
        FrameError: c, m or f is not a frame or lacks a needed column; a meter is twice in m or a meter and period twice in c; a consumption row names a meter that is not in m or has another unit than its meter.
        FrameError: a quantity is text or boolean, null, negative or infinite; an electricity contract_type is not in contract_types (or null); a carrier has no factor family in the rule.
        FrameError: heat_region_by_site is not a mapping, has a site twice, maps a site to no region, or lacks a site of a district heat meter.
        FrameError: restate is not a mapping with exactly the keys year (a whole year from 1900 to 2200) and factor_date (a date), the restate year has no period in the data, or a period is not text YYYY-MM.
        FrameError: a line has no valid factor or more than one valid factor on its date, or the factor unit differs from the consumption unit.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import expected_lines_s123
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set", "unit"]
        >>> F = pd.DataFrame([
        ...     ("EF-900001", "fuel_natural_gas", "natural_gas", "DE", None, 2.0, "2031-01-01", None, "FS-A", "m3"),
        ...     ("EF-900002", "fuel_wtt_natural_gas", "natural_gas", "EU", None, 0.5, "2031-01-01", None, "FS-A", "m3")], columns=cols)
        >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"], "period": ["2031-03"], "quantity": [100.0], "unit": ["m3"], "contract_type": [None]})
        >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": ["natural_gas"], "kind": ["gas"], "country": ["DE"],
        ...                   "site_key": ["SITE-900001"], "unit": ["m3"], "le_key": ["LE-900001"]})
        >>> out = expected_lines_s123(C, M, F, context=ctx)
        >>> out[["scope", "ghg_category", "expected_kg"]].values.tolist()
        [[1, '1', 200.0], [3, '3.3', 50.0]]
    """
    _need(c, ["mtr_key", "period", "quantity", "unit", "contract_type"], "energy-esg.energy_consumption")
    _need(m, ["mtr_key", "carrier", "kind", "country", "site_key", "unit", "le_key"], "energy-esg.energy_meter")
    _need(f, ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"], "energy-esg.emission_factor")
    if isinstance(heat_region_by_site, pd.Series):
        if heat_region_by_site.index.duplicated().any():
            raise FrameError("heat_region_by_site has a site twice")
        heat_region_by_site = heat_region_by_site.to_dict()
    if heat_region_by_site is not None and not isinstance(heat_region_by_site, Mapping):
        raise FrameError("heat_region_by_site is a mapping from site_key to heat network region")
    if m["mtr_key"].duplicated().any() or c.duplicated(["mtr_key", "period"]).any():
        raise FrameError("meters and consumption need one row per mtr_key and per meter and period")
    x = c.merge(m[["mtr_key", "carrier", "kind", "country", "site_key", "le_key", "unit"]].rename(columns={"unit": "meter_unit"}), on="mtr_key", how="left", validate="many_to_one")
    if x["carrier"].isna().any():
        raise FrameError("consumption rows name a meter that is not in energy-esg.energy_meter")
    if (x["unit"] != x["meter_unit"]).any():
        raise FrameError("consumption rows have another unit than their meter")
    x = x.assign(kind=x["kind"].astype(object).where(x["kind"].notna(), ""))
    if not include_tanks:
        x = x[x["kind"] != "po_site_tank"]
    if any(isinstance(v, (bool, np.bool_, str)) for v in x["quantity"].dropna()):
        raise FrameError("energy-esg.energy_consumption.quantity must hold numbers")
    q = pd.to_numeric(x["quantity"]).to_numpy(dtype=float, na_value=np.nan)
    if np.isnan(q).any() or (q < 0).any() or np.isinf(q).any():
        raise FrameError("energy-esg.energy_consumption.quantity must be zero or more and not null (a credit is not a line)")
    x = x.assign(quantity=q)[q > 0]
    el_bad = sorted(set(x.loc[x["carrier"] == "electricity", "contract_type"].dropna()) - set(contract_types))
    if el_bad:
        raise FrameError(f"electricity contract_type {el_bad[0]!r} is not one of {', '.join(contract_types)} (or null)")
    unknown = sorted(set(x["carrier"]) - set(_FUEL_CATEGORY) - {"electricity", "district_heat"})
    if unknown:
        raise FrameError(f"carrier {unknown[0]!r} has no factor family in the rule")
    if (x["carrier"] == "district_heat").any():
        sites = set(x.loc[x["carrier"] == "district_heat", "site_key"])
        if not heat_region_by_site or sites - set(heat_region_by_site):
            raise FrameError(f"district heat meters need heat_region_by_site for the sites {sorted(sites - set(heat_region_by_site or {}))}")
    date = _restate_dates(x["period"], restate)
    parts = []

    def add(sel: Any, scope: int, ghg: str, method: str | None, category_of: Any, carrier_of: Any, region_of: Any, line_category: Any, fam_method: Any) -> None:
        s = x[sel]
        if s.empty:
            return
        want = pd.DataFrame({"category": category_of(s), "carrier": carrier_of(s), "region": region_of(s), "method": fam_method(s), "date": date[sel].to_numpy()}, index=s.index)
        got = _pick(f, want)
        if got["unit"].notna().any() and (got["unit"].astype(object) != s["unit"].astype(object).to_numpy()).any():
            k = int(np.argmax((got["unit"].astype(object) != s["unit"].astype(object).to_numpy()).to_numpy()))
            raise FrameError(f"the factor {got['efac_key'].iloc[k]} is per {got['unit'].iloc[k]}, the consumption is in {s['unit'].iloc[k]}")
        parts.append(pd.DataFrame({"ref_key": s["mtr_key"].to_numpy(), "period": s["period"].to_numpy(), "scope": scope, "ghg_category": ghg, "method": method(s) if callable(method) else method,
                                   "category": line_category(s) if callable(line_category) else line_category, "subcategory": None, "quantity": s["quantity"].to_numpy(dtype=float), "unit": s["unit"].to_numpy(),
                                   "efac_key": got["efac_key"].to_numpy(), "factor": got["factor"].to_numpy(), "expected_kg": (s["quantity"].to_numpy(dtype=float) * got["factor"].to_numpy())}))

    fuel = x["carrier"].isin(_FUEL_CATEGORY)
    none = lambda s: pd.Series([None] * len(s), index=s.index, dtype=object)
    stationary = lambda s: np.where((s["carrier"] == "natural_gas") | s["kind"].str.startswith("generator"), "stationary_combustion", "mobile_combustion")
    add(fuel, 1, "1", None, lambda s: s["carrier"].map(_FUEL_CATEGORY), lambda s: s["carrier"], lambda s: s["country"], stationary, none)
    add(fuel, 3, "3.3", None, lambda s: s["carrier"].map(_WTT_CATEGORY), lambda s: s["carrier"], lambda s: pd.Series(["EU"] * len(s), index=s.index), "fuel_and_energy_related", none)
    el = x["carrier"] == "electricity"
    add(el, 2, "2", "location", lambda s: pd.Series(["electricity_grid_average"] * len(s), index=s.index), lambda s: s["carrier"], lambda s: s["country"], "purchased_electricity", lambda s: pd.Series(["location"] * len(s), index=s.index))
    ren = lambda s: np.where(s["contract_type"] == "renewable_certified", "electricity_certified_renewable", "electricity_residual_mix")
    add(el, 2, "2", "market", lambda s: pd.Series(ren(s), index=s.index), lambda s: s["carrier"], lambda s: s["country"], "purchased_electricity", lambda s: pd.Series(["market"] * len(s), index=s.index))
    dh = x["carrier"] == "district_heat"
    if heat_region_by_site and any(v is None or (isinstance(v, float) and np.isnan(v)) for v in heat_region_by_site.values()):
        raise FrameError("heat_region_by_site maps a site to no region")
    region = lambda s: s["site_key"].map(dict(heat_region_by_site or {}))
    add(dh, 2, "2", "location", lambda s: pd.Series(["district_heat_network_average"] * len(s), index=s.index), lambda s: s["carrier"], region, "purchased_heat", lambda s: pd.Series(["location"] * len(s), index=s.index))
    add(dh, 2, "2", "market", lambda s: pd.Series(["district_heat_supplier_specific"] * len(s), index=s.index), lambda s: s["carrier"], region, "purchased_heat", lambda s: pd.Series(["market"] * len(s), index=s.index))
    if not parts:
        return pd.DataFrame(columns=_EXPECTED_COLS)
    out = pd.concat(parts, ignore_index=True)
    out["expected_kg"] = out["expected_kg"].round(3)
    return out[_EXPECTED_COLS].sort_values(["ref_key", "period", "scope", "ghg_category", "method"], na_position="first").reset_index(drop=True)


@staged(sources=("energy-esg.waste_record.site_key", "energy-esg.waste_record.period", "energy-esg.waste_record.fraction", "energy-esg.waste_record.tonnes", *_F), oracle="py:tests/test_energy_esg.py::test_waste_and_travel")
def expected_waste_lines(w: pd.DataFrame, f: pd.DataFrame, *, restate: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Use this when you need the scope 3.5 waste emission lines that the waste records of each site, month and fraction should produce.

    Waste lines (scope 3.5) from the waste records: tonnes times the factor of the fraction (category waste_<fraction>, region EU) valid on the first of the month. Same columns as expected_lines_s123 (ref_key is the site, subcategory the fraction, category waste_generated, unit t). The plan's oracle is one sided (a lower or missing line passes), recompute_diff checks both ways.

    Args:
        w: The energy-esg.waste_record table with the columns site_key, period (text YYYY-MM), fraction and tonnes; one row per site, period and fraction.
        f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
        restate: None for the factors of the first day of each month, or a mapping with exactly the keys year and factor_date for the restated basis of that year, as in expected_lines_s123.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), sorted by ref_key, period and subcategory; rows with zero tonnes give no line, and the frame is empty when there is none.

    Raises:
        FrameError: w or f is not a frame or lacks a needed column; w has more than one row for a site, period and fraction; tonnes is null or negative.
        FrameError: restate is not a mapping with exactly the keys year and factor_date, the restate year has no period in the data, or a period is not text YYYY-MM.
        FrameError: a line has no valid factor or more than one valid factor on the first of its month.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import expected_waste_lines
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
        >>> F = pd.DataFrame([("EF-900003", "waste_scrap", None, "EU", None, 12.5, "2031-01-01", None, "FS-A")], columns=cols)
        >>> W = pd.DataFrame({"site_key": ["SITE-900001"], "period": ["2031-03"], "fraction": ["scrap"], "tonnes": [3.0]})
        >>> out = expected_waste_lines(W, F, context=ctx)
        >>> out[["ref_key", "subcategory", "unit", "expected_kg"]].to_dict("records")
        [{'ref_key': 'SITE-900001', 'subcategory': 'scrap', 'unit': 't', 'expected_kg': 37.5}]
    """
    _need(w, ["site_key", "period", "fraction", "tonnes"], "energy-esg.waste_record")
    _need(f, ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"], "energy-esg.emission_factor")
    if w.duplicated(["site_key", "period", "fraction"]).any():
        raise FrameError("energy-esg.waste_record has more than one row for a site, period and fraction")
    if w["tonnes"].isna().any() or (w["tonnes"] < 0).any():
        raise FrameError("energy-esg.waste_record needs tonnes of zero or more")
    x = w[w["tonnes"] > 0]
    if x.empty:
        return pd.DataFrame(columns=_EXPECTED_COLS)
    want = pd.DataFrame({"category": "waste_" + x["fraction"].str.replace("_waste$", "", regex=True), "carrier": None, "region": "EU", "method": None, "date": _restate_dates(x["period"], restate).to_numpy()}, index=x.index)
    got = _pick(f, want)
    out = pd.DataFrame({"ref_key": x["site_key"].to_numpy(), "period": x["period"].to_numpy(), "scope": 3, "ghg_category": "3.5", "method": None, "category": "waste_generated", "subcategory": x["fraction"].to_numpy(),
                        "quantity": x["tonnes"].to_numpy(dtype=float), "unit": "t", "efac_key": got["efac_key"].to_numpy(), "factor": got["factor"].to_numpy(), "expected_kg": (x["tonnes"].to_numpy(dtype=float) * got["factor"].to_numpy()).round(3)})
    return out[_EXPECTED_COLS].sort_values(["ref_key", "period", "subcategory"]).reset_index(drop=True)


_GOODS_UNIT = "kgCO2e gross product footprint"
_SERVICE_FACTOR = {"service_civil": "spend_subcontractor_civil", "service_electrical": "spend_subcontractor_electrical", "service_plant": "spend_subcontractor_other", "service_site": "spend_subcontractor_other",
                   "service_other": "spend_subcontractor_other", "service_transport": "spend_subcontractor_other", "service_freight": "spend_express_freight"}          # PROPOSED: item category -> factor category (fact needed)
_LE_COUNTRY = {"LE-01": "DK", "LE-02": "DE"}                                                                                                                                  # PROPOSED: country of the legal entity
_GR = tuple(f"procurement.goods_receipt.{c}" for c in ("po_key", "line_no", "receipt_type", "qty_accepted", "receipt_date"))
_PO = tuple(f"procurement.purchase_order.{c}" for c in ("po_key", "prj_key", "sup_key", "legal_entity_key"))
_IT = tuple(f"inventory.item.{c}" for c in ("itm_key", "category", "footprint_kgco2e_per_unit", "item_type"))


def _by_key(out: pd.DataFrame) -> pd.DataFrame:
    """Expected lines summed per recompute_diff key, so that a key with several factors is compared as one."""
    g = out.groupby(_KEYS, dropna=False, as_index=False).agg(quantity=("quantity", "sum"), unit=("unit", "first"), efac_key=("efac_key", lambda s: s.iloc[0] if s.nunique() == 1 else "mixed"), expected_kg=("expected_kg", "sum"))
    g["quantity"], g["expected_kg"] = g["quantity"].round(3), g["expected_kg"].round(3)
    g["factor"] = (g["expected_kg"] / g["quantity"].where(g["quantity"] > 0)).round(6)
    return g[_EXPECTED_COLS].sort_values(["ref_key", "period", "subcategory"], na_position="first").reset_index(drop=True)


@staged(sources=(*_GR, *_PO, *_IT, "procurement.po_line.po_key", "procurement.po_line.line_no", "procurement.po_line.itm_key", *_F), oracle="py:tests/test_energy_esg.py::test_project_footprints_equal_project_lines")
def expected_goods_lines(goods_receipt: pd.DataFrame, po_line: pd.DataFrame, purchase_order: pd.DataFrame, item: pd.DataFrame, f: pd.DataFrame, *, exclude_categories: tuple[str, ...] = ("fuel_fleet",),
                         periods: Iterable[str] | None = None) -> pd.DataFrame:
    """Use this when you need the scope 3.1 goods emission lines that the goods accepted at receipt per supplier, month and item category should produce.

    Scope 3.1 goods lines: the gross product footprint accepted at goods receipt (accepted quantity times `item.footprint_kgco2e_per_unit`, items with a footprint outside `exclude_categories`,
    PROPOSED fuel_fleet) per supplier, month of the receipt and item category, times the counted share (the product footprint factor row, category purchased_goods_product_footprint, region ALL, valid on the
    first of the month). Same columns as expected_lines_s123: ref_key is the supplier, subcategory the item category, quantity the gross footprint in `kgCO2e gross product footprint`, expected_kg quantity times factor.
    Projects are not in the key (recompute_diff sums the project lines of a key). The spend based lines of excluded fuel supplies (unit DKK) are not rebuilt here. `periods` limits the months (a set of YYYY-MM).

    Args:
        goods_receipt: The procurement.goods_receipt table with the columns po_key, line_no, receipt_type (only 'goods' counts), qty_accepted and receipt_date.
        po_line: The procurement.po_line table with the columns po_key, line_no and itm_key; one row per order line.
        purchase_order: The procurement.purchase_order table with the columns po_key (one row per order) and sup_key.
        item: The inventory.item table with the columns itm_key (one row per item), category and footprint_kgco2e_per_unit.
        f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
        exclude_categories: Tuple of item categories left out (PROPOSED: fuel_fleet); a plain text raises.
        periods: A collection of YYYY-MM months to keep, or None for every month.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), one row per supplier, month and item category, sorted by ref_key, period and subcategory; empty with these columns when no receipt counts.

    Raises:
        FrameError: a table is not a frame or lacks a needed column; exclude_categories is a text and not a tuple; po_line, purchase_order or item has two rows for a key.
        FrameError: qty_accepted has nulls; a receipt names an order line that po_line does not hold, or an item or order that item or purchase_order does not hold.
        FrameError: a month has no valid factor or more than one valid factor on its first day.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import expected_goods_lines
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
        >>> F = pd.DataFrame([("EF-900004", "purchased_goods_product_footprint", None, "ALL", None, 0.8, "2031-01-01", None, "FS-A")], columns=cols)
        >>> GR = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "receipt_type": ["goods"], "qty_accepted": [10.0], "receipt_date": ["2031-03-15"]})
        >>> PL = pd.DataFrame({"po_key": ["PO-900001"], "line_no": [1], "itm_key": ["ITM-900001"]})
        >>> PO = pd.DataFrame({"po_key": ["PO-900001"], "sup_key": ["SUP-900001"]})
        >>> IT = pd.DataFrame({"itm_key": ["ITM-900001"], "category": ["steel"], "footprint_kgco2e_per_unit": [5.0]})
        >>> out = expected_goods_lines(GR, PL, PO, IT, F, context=ctx)
        >>> out[["ref_key", "period", "subcategory", "quantity", "expected_kg"]].to_dict("records")
        [{'ref_key': 'SUP-900001', 'period': '2031-03', 'subcategory': 'steel', 'quantity': 50.0, 'expected_kg': 40.0}]
    """
    _need(goods_receipt, ["po_key", "line_no", "receipt_type", "qty_accepted", "receipt_date"], "procurement.goods_receipt")
    _need(po_line, ["po_key", "line_no", "itm_key"], "procurement.po_line")
    _need(purchase_order, ["po_key", "sup_key"], "procurement.purchase_order")
    _need(item, ["itm_key", "category", "footprint_kgco2e_per_unit"], "inventory.item")
    _need(f, ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"], "energy-esg.emission_factor")
    if isinstance(exclude_categories, (str, bytes)):
        raise FrameError("exclude_categories must be a tuple of item categories")
    if po_line.duplicated(["po_key", "line_no"]).any() or purchase_order["po_key"].duplicated().any() or item["itm_key"].duplicated().any():
        raise FrameError("procurement.po_line, procurement.purchase_order and inventory.item need one row per key")
    g = goods_receipt[(goods_receipt["receipt_type"] == "goods") & (goods_receipt["qty_accepted"] > 0)]
    if g["qty_accepted"].isna().any() or goods_receipt["qty_accepted"].isna().any():
        raise FrameError("procurement.goods_receipt.qty_accepted has nulls")
    g = g.merge(po_line[["po_key", "line_no", "itm_key"]], on=["po_key", "line_no"], how="left", validate="many_to_one")
    if g["itm_key"].isna().any():
        raise FrameError("goods receipts of order lines that procurement.po_line does not hold")
    it = item.set_index("itm_key")
    po = purchase_order.set_index("po_key")["sup_key"]
    g = g.assign(period=pd.to_datetime(g["receipt_date"]).dt.strftime("%Y-%m"), cat=g["itm_key"].map(it["category"]), fp=g["itm_key"].map(it["footprint_kgco2e_per_unit"]), sup=g["po_key"].map(po))
    if g["cat"].isna().any() or g["sup"].isna().any():
        raise FrameError("goods receipts of items or orders that inventory.item or procurement.purchase_order does not hold")
    if periods is not None:
        g = g[g["period"].isin(set(periods))]
    g = g[~g["cat"].isin(list(exclude_categories)) & g["fp"].notna()]
    if g.empty:
        return pd.DataFrame(columns=_EXPECTED_COLS)
    gm = g.assign(gross=g["qty_accepted"] * g["fp"]).groupby(["sup", "period", "cat"], as_index=False)["gross"].sum()
    want = pd.DataFrame({"category": "purchased_goods_product_footprint", "carrier": None, "region": "ALL", "method": None, "date": pd.to_datetime(gm["period"] + "-01")}, index=gm.index)
    got = _pick(f, want)
    out = pd.DataFrame({"ref_key": gm["sup"].to_numpy(), "period": gm["period"].to_numpy(), "scope": 3, "ghg_category": "3.1", "method": None, "category": "purchased_goods", "subcategory": gm["cat"].to_numpy(),
                        "quantity": gm["gross"].round(3).to_numpy(), "unit": _GOODS_UNIT, "efac_key": got["efac_key"].to_numpy(), "factor": got["factor"].to_numpy(), "expected_kg": (gm["gross"].to_numpy() * got["factor"].to_numpy()).round(3)})
    return _by_key(out[_EXPECTED_COLS])


@staged(sources=("procurement.po_line.po_key", "procurement.po_line.itm_key", "procurement.po_line.qty", "procurement.po_line.line_value_dkk", "procurement.po_line.received_qty", "procurement.po_line.last_receipt_date",
                 "procurement.po_line.line_status", *_PO, *_IT, *_F), oracle="py:tests/test_energy_esg.py::test_project_footprints_equal_project_lines")
def expected_service_lines(po_line: pd.DataFrame, item: pd.DataFrame, purchase_order: pd.DataFrame, f: pd.DataFrame, *, category_factor: Mapping[str, Any] | None = None, country_of_le: Mapping[str, Any] | None = None,
                           received_status: tuple[str, ...] = ("received", "partially_received"), periods: Iterable[str] | None = None, restate: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Use this when you need the scope 3.1 spend based emission lines that the received share of service orders should produce per project and month.

    Scope 3.1 spend based service lines: the value of the received share of each service order line (`line_value_dkk` times the received share, at most 1, lines with a received quantity and a last receipt
    date) in DKK, per project (or legal entity without a project) and month of the last receipt, times the spend factor of the item category in the country of the legal entity, valid on the first of the month.
    `category_factor` (item category -> factor category) and `country_of_le` are PROPOSED keywords (the plan says fact needed): defaults map the civil and electrical services to their own spend families and the
    rest to spend_subcontractor_other. Same columns as expected_lines_s123: ref_key is the project or the entity, subcategory is null, unit DKK. An item category without a mapping, or a legal entity without a
    country, raises FrameError. `restate` ({'year': 2025, 'factor_date': '2026-01-01'}) takes the factor of that date for the months of the year, as expected_lines_s123 does for the restated lines.

    Args:
        po_line: The procurement.po_line table with the columns po_key, line_no, itm_key, qty, line_value_dkk, received_qty, last_receipt_date and line_status.
        item: The inventory.item table with the columns itm_key (one row per item), category and item_type (only 'service' items count).
        purchase_order: The procurement.purchase_order table with the columns po_key (one row per order), prj_key and legal_entity_key.
        f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
        category_factor: PROPOSED mapping from item category to factor category; None for the built in defaults.
        country_of_le: PROPOSED mapping from legal entity key to country; None for the built in defaults.
        received_status: The line_status values that count as received (default received and partially_received).
        periods: A collection of YYYY-MM months to keep, or None for every month.
        restate: None for the factors of the first day of each month, or a mapping with exactly the keys year and factor_date for the restated basis of that year.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), one row per project or entity, month and factor family, sorted by ref_key, period and subcategory; quantity is the value in DKK; empty with these columns when no line counts.

    Raises:
        FrameError: a table is not a frame or lacks a needed column; po_line, purchase_order or item has two rows for a key.
        FrameError: a counted service line has a quantity of zero or less or a null quantity, value or received quantity; an order is not in purchase_order.
        FrameError: an item category has no factor category (or is null) in category_factor; a legal entity has no country in country_of_le.
        FrameError: restate is not a mapping with exactly the keys year and factor_date, the restate year has no period in the data, or a period is not text YYYY-MM.
        FrameError: a month has no valid factor or more than one valid factor on its date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import expected_service_lines
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
        >>> F = pd.DataFrame([("EF-900005", "spend_subcontractor_civil", None, "DK", None, 0.1, "2031-01-01", None, "FS-A")], columns=cols)
        >>> PL = pd.DataFrame({"po_key": ["PO-900002"], "line_no": [1], "itm_key": ["ITM-900002"], "qty": [4.0], "line_value_dkk": [1000.0],
        ...                    "received_qty": [2.0], "last_receipt_date": ["2031-03-20"], "line_status": ["partially_received"]})
        >>> PO = pd.DataFrame({"po_key": ["PO-900002"], "prj_key": ["PRJ-900001"], "legal_entity_key": ["LE-900001"]})
        >>> IT = pd.DataFrame({"itm_key": ["ITM-900002"], "category": ["service_civil"], "item_type": ["service"]})
        >>> out = expected_service_lines(PL, IT, PO, F, country_of_le={"LE-900001": "DK"}, context=ctx)
        >>> out[["ref_key", "period", "quantity", "unit", "expected_kg"]].to_dict("records")
        [{'ref_key': 'PRJ-900001', 'period': '2031-03', 'quantity': 500.0, 'unit': 'DKK', 'expected_kg': 50.0}]
    """
    cf = dict(_SERVICE_FACTOR if category_factor is None else category_factor)
    ctry = dict(_LE_COUNTRY if country_of_le is None else country_of_le)
    _need(po_line, ["po_key", "line_no", "itm_key", "qty", "line_value_dkk", "received_qty", "last_receipt_date", "line_status"], "procurement.po_line")
    _need(item, ["itm_key", "category", "item_type"], "inventory.item")
    _need(purchase_order, ["po_key", "prj_key", "legal_entity_key"], "procurement.purchase_order")
    _need(f, ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"], "energy-esg.emission_factor")
    if po_line.duplicated(["po_key", "line_no"]).any() or purchase_order["po_key"].duplicated().any() or item["itm_key"].duplicated().any():
        raise FrameError("procurement.po_line, procurement.purchase_order and inventory.item need one row per key")
    it = item.set_index("itm_key")
    sv = po_line[po_line["itm_key"].map(it["item_type"]) == "service"]
    sv = sv[sv["line_status"].isin(list(received_status)) & (sv["received_qty"] > 0) & sv["last_receipt_date"].notna()]
    if sv.empty:
        return pd.DataFrame(columns=_EXPECTED_COLS)
    if (sv["qty"] <= 0).any() or sv[["qty", "line_value_dkk", "received_qty"]].isna().any().any():
        raise FrameError("service order lines need a positive quantity and a value")
    po = purchase_order.set_index("po_key")
    sv = sv.assign(period=pd.to_datetime(sv["last_receipt_date"]).dt.strftime("%Y-%m"), dkk=sv["line_value_dkk"] * (sv["received_qty"] / sv["qty"]).clip(upper=1.0),
                   cat=sv["itm_key"].map(it["category"]), prj=sv["po_key"].map(po["prj_key"]), le=sv["po_key"].map(po["legal_entity_key"]))
    if periods is not None:
        sv = sv[sv["period"].isin(set(periods))]
    if sv["le"].isna().any():
        raise FrameError("service order lines of orders that procurement.purchase_order does not hold")
    miss = sorted(set(sv["cat"].dropna()) - set(cf))
    if miss or sv["cat"].isna().any():
        raise FrameError(f"no factor category for the item category {miss[:1] or ['(null)']}; pass category_factor")
    badle = sorted(set(sv["le"]) - set(ctry))
    if badle:
        raise FrameError(f"no country for the legal entity {badle[0]}; pass country_of_le")
    sv = sv.assign(fcat=sv["cat"].map(cf), region=sv["le"].map(ctry), ref=sv["prj"].where(sv["prj"].notna(), sv["le"]))
    gs = sv.groupby(["ref", "period", "fcat", "region"], as_index=False)["dkk"].sum()
    want = pd.DataFrame({"category": gs["fcat"].to_numpy(), "carrier": None, "region": gs["region"].to_numpy(), "method": None, "date": _restate_dates(gs["period"], restate).to_numpy()}, index=gs.index)
    got = _pick(f, want)
    out = pd.DataFrame({"ref_key": gs["ref"].to_numpy(), "period": gs["period"].to_numpy(), "scope": 3, "ghg_category": "3.1", "method": None, "category": "purchased_services", "subcategory": None,
                        "quantity": gs["dkk"].round(2).to_numpy(), "unit": "DKK", "efac_key": got["efac_key"].to_numpy(), "factor": got["factor"].to_numpy(), "expected_kg": (gs["dkk"].round(2).to_numpy() * got["factor"].to_numpy()).round(3)})
    return _by_key(out[_EXPECTED_COLS])


@staged(sources=tuple(f"energy-esg.emission_line.{c}" for c in ("ref_key", "period", "scope", "ghg_category", "method", "category", "subcategory", "quantity", "kgco2e")), oracle="py:tests/test_energy_esg.py::test_scope_totals_equal_sum_of_lines")
def recompute_diff(lines: pd.DataFrame, expected: pd.DataFrame, *, quantity_tolerance: float = 0.01, kg_tolerance_per_line: float = 0.002) -> pd.DataFrame:
    """Use this when you need to compare stored emission lines with the expected lines and list every key that does not tie.

    Joins stored lines to expected lines by (ref_key, period, scope, ghg_category, method, category, subcategory), summing the lines of a key (scope 1 is split over projects), and reports the mismatches. Null key parts match each other (as text '-');
    a null ref_key, period or scope raises. The kg tolerance is kg_tolerance_per_line times the number of lines of the key (each line is rounded to 0.001); the quantity tolerance is 0.01 (the
    waste tonnes and the energy quantities are stored with two decimals at most). When both frames carry `unit` a key with another unit is reported as unit. The factor row (efac_key) is not compared: a restated
    line of an unchanged factor keeps the old row, so only the kg decides. PROPOSED: the tolerances. Only mismatches are returned; the frame is empty when all keys tie.

    Args:
        lines: The energy-esg.emission_line table (or any frame of stored lines) with the columns ref_key, period, scope, ghg_category, method, category, subcategory, quantity and kgco2e (and unit, when it is to be compared).
        expected: The output of one of the expected_* functions (or their concatenation) with the columns ref_key, period, scope, ghg_category, method, category, subcategory, quantity and expected_kg (and unit, when it is to be compared).
        quantity_tolerance: The largest difference in quantity of a key that still ties (PROPOSED, default 0.01); a number of zero or more.
        kg_tolerance_per_line: The difference in kg that each stored line of a key may add before the key no longer ties (PROPOSED, default 0.002); a number of zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns ref_key, period, scope, ghg_category, method, category, subcategory (the key), n_lines, quantity_lines, quantity_expected, kg_lines, kg_expected and status (missing_line, missing_expected, quantity, kg or unit; ok keys are not listed), sorted by the key; empty when all keys tie.

    Raises:
        FrameError: lines or expected is not a frame or lacks a needed column (kgco2e in lines, expected_kg in expected).
        FrameError: a tolerance is not a number of zero or more (a boolean, infinite or negative value raises).
        FrameError: a ref_key, period or scope is null in either frame; scope is not a whole number.
        FrameError: quantity, kgco2e or expected_kg holds text, booleans or nulls.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import recompute_diff
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["ref_key", "period", "scope", "ghg_category", "method", "category", "subcategory", "quantity"]
        >>> L = pd.DataFrame([("PRJ-900001", "2031-03", 3, "3.1", None, "purchased_services", None, 500.0, 50.0)], columns=[*cols, "kgco2e"])
        >>> E = pd.DataFrame([("PRJ-900001", "2031-03", 3, "3.1", None, "purchased_services", None, 500.0, 55.0)], columns=[*cols, "expected_kg"])
        >>> bad = recompute_diff(L, E, context=ctx)
        >>> bad[["status", "n_lines", "kg_lines", "kg_expected"]].values.tolist()
        [['kg', 1, 50.0, 55.0]]
    """
    for df, name in ((lines, "lines"), (expected, "expected")):
        _need(df, ["ref_key", "period", "scope", "ghg_category", "method", "category", "subcategory", "quantity"], name)
    _need(lines, ["kgco2e"], "lines")
    _need(expected, ["expected_kg"], "expected")
    for name, v in (("quantity_tolerance", quantity_tolerance), ("kg_tolerance_per_line", kg_tolerance_per_line)):
        if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not np.isfinite(v) or v < 0:
            raise FrameError(f"{name} must be a number of zero or more")
    for df, name in ((lines, "lines"), (expected, "expected")):
        if df[["ref_key", "period", "scope"]].isna().any().any():
            raise FrameError(f"{name} has a null ref_key, period or scope")
    for df, name, cols in ((lines, "lines", ["quantity", "kgco2e"]), (expected, "expected", ["quantity", "expected_kg"])):
        for c in cols:
            if pd.api.types.is_bool_dtype(df[c]) or any(isinstance(v, (bool, np.bool_, str)) for v in df[c].dropna()):
                raise FrameError(f"{name}.{c} must hold numbers")
            if df[c].isna().any():
                raise FrameError(f"{name}.{c} has nulls: a line without an amount cannot be compared")
    both = lambda col: col in lines.columns and col in expected.columns

    def text(v: Any) -> str:
        """A key part as text: whole floats lose the '.0' (1.0 is 1), spaces at the ends go, null is a marker that no real text equals."""
        if v is None or v is pd.NA or (isinstance(v, (float, np.floating)) and np.isnan(v)):
            return "\x00null"
        if isinstance(v, (float, np.floating)) and float(v).is_integer():
            return str(int(v))
        return str(v).strip()

    def keyed(df: pd.DataFrame, what: str) -> pd.DataFrame:
        out = df.copy()
        try:
            sc = pd.to_numeric(out["scope"])
        except (ValueError, TypeError):
            raise FrameError(f"{what}.scope must be a whole number") from None
        if pd.api.types.is_bool_dtype(out["scope"]) or any(isinstance(v, (bool, np.bool_)) for v in out["scope"]) or (sc % 1 != 0).any() or np.isinf(sc).any():
            raise FrameError(f"{what}.scope must be a whole number")
        out["scope"] = sc.astype("Int64").astype(str)
        for k in _KEYS:
            if k != "scope":
                out[k] = out[k].astype(object).map(text)
        return out

    extra_a, extra_b = {}, {}
    if both("unit"):
        extra_a["unit_lines"], extra_b["unit_expected"] = ("unit", lambda x: "|".join(sorted(set(map(str, x.dropna()))))), ("unit", lambda x: "|".join(sorted(set(map(str, x.dropna())))))
    a = keyed(lines, "lines").groupby(_KEYS, as_index=False, observed=True).agg(n_lines=("kgco2e", "size"), quantity_lines=("quantity", "sum"), kg_lines=("kgco2e", "sum"), **extra_a)
    b = keyed(expected, "expected").groupby(_KEYS, as_index=False, observed=True).agg(quantity_expected=("quantity", "sum"), kg_expected=("expected_kg", "sum"), **extra_b)
    m = a.merge(b, on=_KEYS, how="outer", indicator=True)
    m["n_lines"] = m["n_lines"].fillna(0).astype(int)
    q_bad = (m["quantity_lines"] - m["quantity_expected"]).abs() > quantity_tolerance + 1e-9
    k_bad = (m["kg_lines"] - m["kg_expected"]).abs() > kg_tolerance_per_line * m["n_lines"].clip(lower=1) + 1e-9
    u_bad = (m["unit_lines"] != m["unit_expected"]) if "unit_lines" in m else pd.Series(False, index=m.index)
    m["status"] = np.select([m["_merge"] == "right_only", m["_merge"] == "left_only", q_bad, k_bad, u_bad], ["missing_line", "missing_expected", "quantity", "kg", "unit"], "ok")
    bad = m[m["status"] != "ok"].drop(columns=["_merge", *[c for c in ("unit_lines", "unit_expected") if c in m]])
    return bad.sort_values(_KEYS).reset_index(drop=True)
