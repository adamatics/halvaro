"""Greenhouse gas totals from the emission lines: scope totals on a basis, scope 2 by both methods, scope 3 by category and screening, the effect of the renewable contract and the winter ratio.

Rules: sum only one basis (current or first_booked, never all lines: T1), never add the two scope 2 methods (T4), report the months covered (2026 has 11, T7). Totals are in kgco2e and rest
on synthetic factors: every result has the status VERIFY+synthetic.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact, make_envelope

from ._guard import staged, unwrapped
from ._util import Provenance, _basis, _need, _num, _period_text

_L = tuple(f"energy-esg.emission_line.{c}" for c in ("le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"))
_ALL_CATEGORIES = ("3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15")
_NOTE = "emission factors are synthetic with a VERIFY note: not for real reporting"


def _result(value: Any, function: str, *, facts: Sequence[Any] = (), sources: Sequence[str] = _L, as_of: dt.date | None = None) -> Provenance:
    env = make_envelope(value, function, facts=facts, sources=sources, as_of=as_of, warnings=(_NOTE,), cls=Provenance)
    return cast(Provenance, dataclasses.replace(env, status="VERIFY+synthetic", synthetic=True))


def _year(year: Any) -> int:
    if year is None:
        return int(pd.Timestamp(fact("world.now").value).year) - 1
    if isinstance(year, bool) or not isinstance(year, (int, np.integer)) or not 1900 <= int(year) <= 2100:
        raise FrameError(f"year must be a whole year like 2025, not {year!r}")
    return int(year)


def _stale_check(L: pd.DataFrame) -> None:
    """With supersedes_line_no in the frame: a restated line must name its original, and an original that a restated line replaces must be flagged is_superseded (else the current basis counts the change twice)."""
    if "supersedes_line_no" not in L.columns or "line_no" not in L.columns:
        return
    restated = L["restated_from_period"].notna()
    if (restated & L["supersedes_line_no"].isna()).any():
        raise FrameError(f"{int((restated & L['supersedes_line_no'].isna()).sum())} restated lines have no supersedes_line_no; the original they replace cannot be told")
    new = L[restated]
    replaced = pd.MultiIndex.from_arrays([new["le_key"], new["period"], new["scope"], new["category"], _num(new["supersedes_line_no"])])
    stale = pd.MultiIndex.from_arrays([L["le_key"], L["period"], L["scope"], L["category"], _num(L["line_no"])]).isin(replaced) & ~L["is_superseded"].astype(bool).to_numpy()
    if stale.any():
        raise FrameError(f"{int(stale.sum())} original lines are replaced by a restated line but not flagged is_superseded; a total over the current basis would count them twice")


def _in_year(L: pd.DataFrame, basis: str, year: int, le: str | None) -> pd.DataFrame:
    if basis == "current":
        _stale_check(L)
    x = _basis(L, basis)
    _need(x, ["le_key", "period", "scope", "category", "method", "ghg_category", "kgco2e"], "energy-esg.emission_line")
    if x["kgco2e"].isna().any():
        raise FrameError("energy-esg.emission_line has null kgco2e")
    x = x[x["period"].astype(str).str[:4] == str(year)]
    if (~x["scope"].isin([1, 2, 3])).any():
        raise FrameError(f"lines with scope {sorted(set(x['scope']) - {1, 2, 3})[0]!r}: the scopes are 1, 2 and 3")
    if (x["scope"] == 3).any() and x.loc[x["scope"] == 3, "ghg_category"].isna().any():
        raise FrameError("scope 3 lines without a ghg_category")
    odd = sorted(set(x.loc[x["scope"] == 3, "ghg_category"].dropna().astype(str)) - set(_ALL_CATEGORIES))
    if odd:
        raise FrameError(f"ghg_category {odd[0]!r} is not a scope 3 category (one of the 15)")
    if (x["scope"] == 2).any() and not x.loc[x["scope"] == 2, "method"].isin(["location", "market"]).all():
        raise FrameError("scope 2 lines need the method location or market")
    x = x.assign(**{k: x[k].astype(object) for k in ("le_key", "category", "ghg_category", "method") if isinstance(x[k].dtype, pd.CategoricalDtype)})
    if le is not None and le != "ALL":
        if le not in set(x["le_key"]):
            raise FrameError(f"no lines of the entity {le!r} in {year}")
        return x[x["le_key"] == le]
    return x


@staged(sources=_L, facts=("world.now",), oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def scope_totals(L: pd.DataFrame, year: int | None = None, basis: str = "current", le: str | None = None) -> Provenance:
    """Use this when you need the scope 1, scope 2 and scope 3 totals of one year on one basis, per entity, for one entity or for all.

    Scope 1, scope 2 by location and by market, scope 3 (and each ghg_category) and the two totals of one year on one basis, per entity or for one entity (le) or all (le_key 'ALL'). The value
    columns are le_key, year, basis, months (distinct periods with lines), scope1, scope2_location, scope2_market, scope3, scope3_<category> for each category present, total_location_based
    (scope 1 + scope 2 location + scope 3) and total_market_based. kgco2e to three decimals. The year defaults to the year before the year of world.now; basis is 'current' or 'first_booked'.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        year: The whole year to total, like 2025; the year before the year of world.now when None.
        basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
        le: One le_key to report only that entity, or None or 'ALL' for every entity plus an 'ALL' row.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with the columns above, one row per entity sorted by le_key and then the 'ALL' row, in kgco2e.

    Raises:
        FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, the entity le has no lines in the year, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import scope_totals
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 20.0, False, None),
        ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
        >>> r = scope_totals(L, 2025, context=ctx)
        >>> r.value["le_key"].tolist()
        ['LE-900001', 'ALL']
        >>> r.value.loc[0, ["months", "scope1", "scope2_location", "scope2_market", "scope3"]].astype(float).tolist()
        [2.0, 100.0, 50.0, 20.0, 30.0]
        >>> r.value.loc[0, ["total_location_based", "total_market_based"]].astype(float).tolist()
        [180.0, 150.0]
    """
    y = _year(year)
    x = _in_year(L, basis, y, le)
    cats = set(x.loc[x["scope"] == 3, "ghg_category"])
    rows = []
    groups = [(k, g) for k, g in x.groupby("le_key", sort=True)] + ([("ALL", x)] if (le is None or le == "ALL") and len(x) else [])
    if le is not None:
        groups = [g for g in groups if g[0] == le]
    for key, g in groups:
        s3 = g[g["scope"] == 3].groupby("ghg_category")["kgco2e"].sum()
        row = {"le_key": key, "year": y, "basis": basis, "months": int(g["period"].nunique()), "scope1": g.loc[g["scope"] == 1, "kgco2e"].sum(),
               "scope2_location": g.loc[(g["scope"] == 2) & (g["method"] == "location"), "kgco2e"].sum(), "scope2_market": g.loc[(g["scope"] == 2) & (g["method"] == "market"), "kgco2e"].sum(),
               "scope3": s3.sum(), **{f"scope3_{c}": float(s3.get(c, 0.0)) for c in _ALL_CATEGORIES if c in cats}}
        row["total_location_based"] = row["scope1"] + row["scope2_location"] + row["scope3"]
        row["total_market_based"] = row["scope1"] + row["scope2_market"] + row["scope3"]
        rows.append(row)
    out = pd.DataFrame(rows)
    num = [c for c in out.columns if c not in ("le_key", "year", "basis", "months")]
    out[num] = out[num].round(3)
    return _result(out, "halvaro.esg.ghg.scope_totals", facts=[fact("world.now")], as_of=None)


@staged(sources=_L)
def scope2_dual(L: pd.DataFrame, year: int | None = None, basis: str = "current") -> Provenance:
    """Use this when you need scope 2 by carrier category with the location based and the market based result side by side.

    Scope 2 by carrier category (purchased_electricity, purchased_heat) with both methods side by side and never summed.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        year: The whole year, like 2025; the year before the year of world.now when None.
        basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with le_key, year, category, location_kg, market_kg and market_vs_location_percent (market over location less 100, null without location), sorted by le_key and category.

    Raises:
        FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import scope2_dual
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 20.0, False, None)], columns=cols)
        >>> scope2_dual(L, 2025, context=ctx).value.to_dict("records")
        [{'le_key': 'LE-900001', 'year': 2025, 'category': 'purchased_electricity', 'location_kg': 50.0, 'market_kg': 20.0, 'market_vs_location_percent': -60.0}]
    """
    y = _year(year)
    x = _in_year(L, basis, y, None)
    x = x[x["scope"] == 2]
    p = x.pivot_table(index=["le_key", "category"], columns="method", values="kgco2e", aggfunc="sum", observed=True).reindex(columns=["location", "market"]).reset_index()
    out = p.rename(columns={"location": "location_kg", "market": "market_kg"}).assign(year=y)
    out["market_vs_location_percent"] = np.where(out["location_kg"] > 0, np.round((out["market_kg"] / out["location_kg"].where(out["location_kg"] > 0) - 1) * 100, 2), np.nan)
    out[["location_kg", "market_kg"]] = out[["location_kg", "market_kg"]].round(3)
    return _result(out[["le_key", "year", "category", "location_kg", "market_kg", "market_vs_location_percent"]].sort_values(["le_key", "category"]).reset_index(drop=True), "halvaro.esg.ghg.scope2_dual")


@staged(sources=_L, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def scope3_by_category(L: pd.DataFrame, year: int | None = None, basis: str = "current") -> Provenance:
    """Use this when you need scope 3 by ghg_category and line category for one year and basis.

    The sum is the scope3 of scope_totals.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        year: The whole year, like 2025; the year before the year of world.now when None.
        basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with ghg_category, category, n_lines and kgco2e (three decimals), sorted by the order of the 15 categories and then by category.

    Raises:
        FrameError: L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import scope3_by_category
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None),
        ...     ("LE-900001", "2025-02", 3, "purchased_goods", 2, None, "3.1", 10.0, False, None),
        ...     ("LE-900001", "2025-02", 3, "business_travel", 1, None, "3.6", 5.0, False, None)], columns=cols)
        >>> r = scope3_by_category(L, 2025, context=ctx)
        >>> r.value[["ghg_category", "category", "n_lines", "kgco2e"]].values.tolist()
        [['3.1', 'purchased_goods', 2, 40.0], ['3.6', 'business_travel', 1, 5.0]]
    """
    y = _year(year)
    x = _in_year(L, basis, y, None)
    x = x[x["scope"] == 3]
    out = x.groupby(["ghg_category", "category"], as_index=False, observed=True).agg(n_lines=("kgco2e", "size"), kgco2e=("kgco2e", "sum"))
    out["kgco2e"] = out["kgco2e"].round(3)
    key = out["ghg_category"].map({c: i for i, c in enumerate(_ALL_CATEGORIES)})
    return _result(out.assign(_k=key).sort_values(["_k", "category"]).drop(columns="_k").reset_index(drop=True), "halvaro.esg.ghg.scope3_by_category")


@staged(sources=_L, oracle="py:tests/test_oracle_ghg.py::test_oracle_scope3_coverage_every_route")
def scope3_coverage(L: pd.DataFrame, screening: Mapping[str, Any] | None = None, year: int | None = None, basis: str = "current") -> Provenance:
    """Use this when you need to see which of the 15 scope 3 categories have lines and the reason for each absent one.

    The 15 scope 3 categories against the lines: present or not, kgco2e, and the reason for an absent one from the screening decision. `screening` maps a category to the reason it is out (for example
    {'3.2': 'screened out: capital goods are in 3.1'}); an absent category without an entry has the reason 'not screened: decision needed'. PROPOSED: no default screening
    (policy.esg.scope3_screening is needed). A reason given for a category that has lines is ignored with a warning.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        screening: Mapping from a scope 3 category (such as '3.2') to the reason it is out, or None for no screening.
        year: The whole year, like 2025; the year before the year of world.now when None.
        basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with ghg_category, present, n_lines, kgco2e and reason (null for a present category), one row for each of the 15 categories in order.

    Raises:
        FrameError: screening is not a mapping or names something that is not a scope 3 category, L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import scope3_coverage
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
        >>> r = scope3_coverage(L, {"3.2": "screened out: capital goods are in 3.1"}, 2025, context=ctx)
        >>> int(r.value["present"].sum()), len(r.value)
        (1, 15)
        >>> r.value.set_index("ghg_category").loc[["3.2", "3.3"], "reason"].tolist()
        ['screened out: capital goods are in 3.1', 'not screened: decision needed']
    """
    if screening is not None and not isinstance(screening, Mapping):
        raise FrameError(f"screening is a mapping from a category to a reason (the year is the next argument), not {type(screening).__name__}")
    y = _year(year)
    x = _in_year(L, basis, y, None)
    x = x[x["scope"] == 3]
    unknown = sorted(set(x["ghg_category"]) - set(_ALL_CATEGORIES))
    if unknown:
        raise FrameError(f"lines with ghg_category {unknown[0]!r}, which is not a scope 3 category")
    if screening is not None:
        bad = sorted(set(screening) - set(_ALL_CATEGORIES))
        if bad:
            raise FrameError(f"screening names {bad[0]!r}, which is not a scope 3 category")
    g = x.groupby("ghg_category").agg(n_lines=("kgco2e", "size"), kgco2e=("kgco2e", "sum"))
    out = pd.DataFrame({"ghg_category": list(_ALL_CATEGORIES)}).join(g, on="ghg_category")
    out["present"] = out["n_lines"].notna()
    out[["n_lines", "kgco2e"]] = out[["n_lines", "kgco2e"]].fillna(0)
    out["n_lines"] = out["n_lines"].astype(int)
    out["kgco2e"] = out["kgco2e"].round(3)
    reasons = dict(screening or {})
    out["reason"] = [None if p else reasons.get(c, "not screened: decision needed") for c, p in zip(out["ghg_category"], out["present"])]
    kept = sorted(c for c in reasons if c in set(x["ghg_category"]))
    warn = (f"screening gives a reason for {kept[0]}, which has lines: the reason is ignored",) if kept else ()
    res = _result(out[["ghg_category", "present", "n_lines", "kgco2e", "reason"]], "halvaro.esg.ghg.scope3_coverage")
    return dataclasses.replace(res, warnings=res.warnings + warn)


def _months(lo: str, hi: str) -> int:
    return (int(hi[:4]) - int(lo[:4])) * 12 + int(hi[5:]) - int(lo[5:]) + 1


@staged(sources=(*_L, "energy-esg.energy_consumption.period", "energy-esg.energy_consumption.contract_type"))
def renewable_effect(L: pd.DataFrame, C: pd.DataFrame, before: Sequence[str] | None = None, after: Sequence[str] | None = None) -> Provenance:
    """Use this when you need the monthly average of scope 2 before and after the renewable contract, market against location, with the percent change.

    Monthly average of scope 2 on the current basis before and after the renewable contract, market against location, for electricity and for all scope 2, with the percent change. The windows come
    from the data when not given: `after` runs from the first period with a renewable_certified contract in the consumption table to the last period of the lines, `before` is the 12 months ending the
    month before. The market method falls with the contract, the location method does not (T10, T11).

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        C: Frame energy-esg.energy_consumption with period and contract_type (used to find the first renewable_certified period when after is None).
        before: The (first, last) periods like ('2024-01', '2024-12') of the window before the contract; the 12 months ending the month before after when None.
        after: The (first, last) periods of the window after the contract starts; from the first renewable_certified period to the last period of the lines when None.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with measure (location_all, location_electricity, market_all, market_electricity), avg_before_kg, avg_after_kg, change_percent (null without a positive before average), months_before and months_after, one row per measure in that order.

    Raises:
        FrameError: L or C is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, a restated line has no supersedes_line_no or its original is not flagged is_superseded, no consumption is on a renewable_certified contract and the windows are not passed, a window is not a (first, last) pair of periods in order, the windows overlap or are in the wrong order, or a window lacks scope 2 lines (location or market, all or purchased_electricity) for some of its months.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import renewable_effect
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
        ...     ("LE-900001", "2025-01", 2, "purchased_electricity", 2, "market", None, 40.0, False, None),
        ...     ("LE-900001", "2025-02", 2, "purchased_electricity", 1, "location", None, 50.0, False, None),
        ...     ("LE-900001", "2025-02", 2, "purchased_electricity", 2, "market", None, 10.0, False, None)], columns=cols)
        >>> C = pd.DataFrame({"period": ["2025-01", "2025-02"], "contract_type": ["standard", "renewable_certified"]})
        >>> r = renewable_effect(L, C, before=("2025-01", "2025-01"), after=("2025-02", "2025-02"), context=ctx)
        >>> r.value.set_index("measure")["change_percent"].to_dict()
        {'location_all': 0.0, 'location_electricity': 0.0, 'market_all': -75.0, 'market_electricity': -75.0}
    """
    _stale_check(L)
    L = _basis(L, "current")
    _need(L, ["period", "scope", "method", "category", "kgco2e"], "energy-esg.emission_line")
    _need(C, ["period", "contract_type"], "energy-esg.energy_consumption")
    if L["kgco2e"].isna().any():
        raise FrameError("energy-esg.emission_line has null kgco2e")
    last = L["period"].max()
    a: tuple[Any, ...]
    b: tuple[Any, ...]
    if after is None:
        ren = C.loc[C["contract_type"] == "renewable_certified", "period"]
        if ren.empty:
            raise FrameError("no consumption on a renewable_certified contract: pass the windows")
        a0 = ren.min()
        a = (a0, last)
    else:
        a = tuple(after)
    if before is None:
        if len(a) != 2:
            raise FrameError("after must be a (first, last) pair of periods in order")
        b = ((pd.Period(a[0], "M") - 12).strftime("%Y-%m"), (pd.Period(a[0], "M") - 1).strftime("%Y-%m"))
    else:
        b = tuple(before)
    for w, name in ((a, "after"), (b, "before")):
        if len(w) != 2 or _period_text(w[0], name) > _period_text(w[1], name):
            raise FrameError(f"{name} must be a (first, last) pair of periods in order")
    if not b[1] < a[0]:
        raise FrameError("the windows overlap or are in the wrong order")
    s2all = L[L["scope"] == 2]
    for label, sub in (("location", s2all[s2all["method"] == "location"]), ("market", s2all[s2all["method"] == "market"]),
                       ("location purchased_electricity", s2all[(s2all["method"] == "location") & (s2all["category"] == "purchased_electricity")]),
                       ("market purchased_electricity", s2all[(s2all["method"] == "market") & (s2all["category"] == "purchased_electricity")])):
        have = set(sub["period"])
        for w, name in ((b, "before"), (a, "after")):
            want = {p.strftime("%Y-%m") for p in pd.period_range(w[0], w[1], freq="M")}
            if want - have:
                raise FrameError(f"the {name} window {w[0]} to {w[1]} has scope 2 {label} lines for {len(want & have)} of {len(want)} months; the monthly average needs all of them")
    s2 = L[L["scope"] == 2]
    rows = []
    for name, method, elec in (("location_all", "location", False), ("location_electricity", "location", True), ("market_all", "market", False), ("market_electricity", "market", True)):
        x = s2[s2["method"] == method]
        if elec:
            x = x[x["category"] == "purchased_electricity"]
        mb, ma = _months(*b), _months(*a)
        ab = x[(x["period"] >= b[0]) & (x["period"] <= b[1])]["kgco2e"].sum() / mb
        aa = x[(x["period"] >= a[0]) & (x["period"] <= a[1])]["kgco2e"].sum() / ma
        rows.append((name, round(ab, 3), round(aa, 3), round((aa / ab - 1) * 100, 3) if ab > 0 else np.nan, mb, ma))
    return _result(pd.DataFrame(rows, columns=["measure", "avg_before_kg", "avg_after_kg", "change_percent", "months_before", "months_after"]), "halvaro.esg.ghg.renewable_effect")


@staged(sources=_L, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def winter_ratio(L: pd.DataFrame, prev: Sequence[str] = ("2024-12", "2025-02"), now: Sequence[str] = ("2025-12", "2026-02")) -> Provenance:
    """Use this when you need Scope 1 of a winter window against the same window a year earlier, on the current and the first booked basis.

    Scope 1 of a winter window over the same window a year earlier, on both bases. Windows are (first, last) periods, inclusive; the defaults are December to February. The two bases differ because
    a restatement changes the earlier window only, so the ratio on the current basis can differ from the ratio as first booked. A longer window (November to March) gives another ratio.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        prev: The (first, last) periods of the earlier window, inclusive (default ('2024-12', '2025-02')).
        now: The (first, last) periods of the later window, inclusive, with as many months as prev (default ('2025-12', '2026-02')).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with basis, scope1_prev_kg, scope1_now_kg and ratio (three decimals; null without scope 1 in the earlier window), one row for current and one for first_booked.

    Raises:
        FrameError: a window is not a (first, last) pair of period text in order, the two windows have a different number of months, L lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, a restated line has no supersedes_line_no or its original is not flagged is_superseded, or a window has scope 1 lines for fewer months than it spans.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import winter_ratio
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2024-12", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
        ...     ("LE-900001", "2025-12", 1, "stationary_combustion", 1, None, None, 120.0, False, None)], columns=cols)
        >>> r = winter_ratio(L, prev=("2024-12", "2024-12"), now=("2025-12", "2025-12"), context=ctx)
        >>> r.value[["basis", "scope1_prev_kg", "scope1_now_kg", "ratio"]].values.tolist()
        [['current', 100.0, 120.0, 1.2], ['first_booked', 100.0, 120.0, 1.2]]
    """
    for w, name in ((prev, "prev"), (now, "now")):
        if len(tuple(w)) != 2 or _period_text(tuple(w)[0], name) > _period_text(tuple(w)[1], name):
            raise FrameError(f"{name} must be a (first, last) pair of periods in order")
    if _months(*prev) != _months(*now):
        raise FrameError("the two windows must have the same number of months")
    rows = []
    _stale_check(L)
    for basis in ("current", "first_booked"):
        s1 = _basis(L, basis)
        if s1["kgco2e"].isna().any():
            raise FrameError("energy-esg.emission_line has null kgco2e")
        s1 = s1[s1["scope"] == 1]
        have = set(s1["period"])
        for w, name in ((prev, "prev"), (now, "now")):
            want = {p.strftime("%Y-%m") for p in pd.period_range(w[0], w[1], freq="M")}
            if want - have:
                raise FrameError(f"the {name} window {w[0]} to {w[1]} has scope 1 lines for {len(want & have)} of {len(want)} months")
        p = s1[(s1["period"] >= prev[0]) & (s1["period"] <= prev[1])]["kgco2e"].sum()
        n = s1[(s1["period"] >= now[0]) & (s1["period"] <= now[1])]["kgco2e"].sum()
        rows.append((basis, round(p, 3), round(n, 3), round(n / p, 3) if p > 0 else np.nan))
    return _result(pd.DataFrame(rows, columns=["basis", "scope1_prev_kg", "scope1_now_kg", "ratio"]), "halvaro.esg.ghg.winter_ratio")


_CONS = tuple(f"energy-esg.energy_consumption.{c}" for c in ("mtr_key", "period", "quantity", "unit"))


@staged(sources=(*_CONS, "energy-esg.energy_meter.mtr_key", "energy-esg.energy_meter.kind", "energy-esg.energy_meter.carrier", "energy-esg.energy_meter_asset.mtr_key", "energy-esg.energy_meter_asset.asset_type"),
        oracle="py:tests/test_oracle_ghg.py::test_oracle_winter_decomposition_every_route")
def winter_decomposition(C: pd.DataFrame, M: pd.DataFrame, MA: pd.DataFrame, now: Sequence[str] = ("2025-12", "2026-02"), prev: Sequence[str] = ("2024-12", "2025-02"), *, carrier: str = "diesel",
                         by: str = "meter") -> pd.DataFrame:
    """Use this when you need the litres of a fuel in a winter window against the same months a year earlier, per meter, meter kind or asset type.

    Litres of a fuel in a winter window against the same months a year earlier, per meter (by='meter'), meter kind or asset type. Columns: [mtr_key,] [kind,] asset_type (the most common asset type of the
    meter in `MA`, null without an asset), litres_now, litres_prev, extra_litres (now less prev; null when a window has no consumption row), months_now, months_prev (distinct periods with a consumption row of the group in the window, so a
    gap shows only when no meter of the group has a row), pct_change. Meters of another carrier are left out. The generator's own 'extra litres' is build state and is not reproduced (plan: candidate); this is the difference of the metered litres.

    Args:
        C: Frame energy-esg.energy_consumption with mtr_key, period, quantity and unit, one row per meter and period.
        M: Frame energy-esg.energy_meter with mtr_key, carrier, kind and unit, one row per meter.
        MA: Frame energy-esg.energy_meter_asset with mtr_key and asset_type.
        now: The (first, last) periods of the later window, inclusive (default ('2025-12', '2026-02')).
        prev: The (first, last) periods of the window a year earlier, with as many months as now (default ('2024-12', '2025-02')).
        carrier: The carrier of the meters to count (default 'diesel').
        by: 'meter' (mtr_key, kind and asset_type), 'kind' or 'asset_type'; the grouping of the rows.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        DataFrame with the columns above (mtr_key, kind and asset_type for by='meter', else the one group column), sorted by the group columns with nulls last; litres to three decimals, pct_change to two.

    Raises:
        FrameError: a window is not a (first, last) pair of period text in order, the two windows have a different number of months, by is not meter, kind or asset_type, C, M or MA lacks a column, a meter or a meter and period is repeated, the meters of the carrier have more than one unit, or the consumption has null quantities.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import winter_decomposition
        >>> ctx = Context(stage="month12", role="analyst")
        >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"] * 4, "period": ["2024-12", "2025-01", "2025-12", "2026-01"], "quantity": [100.0, 100.0, 150.0, 150.0], "unit": "l"})
        >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": "diesel", "kind": "generator", "unit": "l"})
        >>> MA = pd.DataFrame({"mtr_key": ["MTR-900001"], "asset_type": ["generator_set"]})
        >>> r = winter_decomposition(C, M, MA, now=("2025-12", "2026-01"), prev=("2024-12", "2025-01"), context=ctx)
        >>> r.to_dict("records")
        [{'mtr_key': 'MTR-900001', 'kind': 'generator', 'asset_type': 'generator_set', 'litres_now': 300.0, 'litres_prev': 200.0, 'extra_litres': 100.0, 'months_now': 2, 'months_prev': 2, 'pct_change': 50.0}]
    """
    for w, name in ((now, "now"), (prev, "prev")):
        if len(tuple(w)) != 2 or _period_text(tuple(w)[0], name) > _period_text(tuple(w)[1], name):
            raise FrameError(f"{name} must be a (first, last) pair of periods in order")
    if _months(*prev) != _months(*now):
        raise FrameError("the two windows must have the same number of months")
    if by not in ("meter", "kind", "asset_type"):
        raise FrameError("by is meter, kind or asset_type")
    _need(C, ["mtr_key", "period", "quantity", "unit"], "energy-esg.energy_consumption")
    _need(M, ["mtr_key", "carrier", "kind", "unit"], "energy-esg.energy_meter")
    _need(MA, ["mtr_key", "asset_type"], "energy-esg.energy_meter_asset")
    if M["mtr_key"].duplicated().any() or C.duplicated(["mtr_key", "period"]).any():
        raise FrameError("energy-esg.energy_meter and energy_consumption need one row per meter (and period)")
    m = M[M["carrier"] == carrier]
    if m["unit"].nunique() > 1:
        raise FrameError("the meters of the carrier have more than one unit; litres cannot be added to kWh")
    def _mode(s: "pd.Series[Any]") -> Any:
        return s.mode().sort_values().iloc[0] if len(s.dropna()) else None

    asset = MA.groupby("mtr_key")["asset_type"].agg(_mode)
    x = C[C["mtr_key"].isin(set(m["mtr_key"]))].merge(m[["mtr_key", "kind"]], on="mtr_key", how="left")
    x = x.assign(asset_type=x["mtr_key"].map(asset))
    if x["quantity"].isna().any():
        raise FrameError("energy-esg.energy_consumption has null quantities")
    keys = {"meter": ["mtr_key", "kind", "asset_type"], "kind": ["kind"], "asset_type": ["asset_type"]}[by]
    acc: pd.DataFrame | None = None
    for name, w in (("now", now), ("prev", prev)):
        sel = x[(x["period"] >= w[0]) & (x["period"] <= w[1])]
        g = sel.groupby(keys, dropna=False, as_index=False).agg(**{f"litres_{name}": ("quantity", "sum"), f"months_{name}": ("period", "nunique")})
        acc = g if acc is None else acc.merge(g, on=keys, how="outer")
    out = cast(pd.DataFrame, acc)
    for c in ("months_now", "months_prev"):
        out[c] = out[c].fillna(0).astype(int)
    out["extra_litres"] = np.where((out["months_now"] > 0) & (out["months_prev"] > 0), (out["litres_now"].fillna(0) - out["litres_prev"].fillna(0)).round(3), np.nan)
    out["pct_change"] = np.where(out["litres_prev"] > 0, ((out["litres_now"] / out["litres_prev"] - 1) * 100).round(2), np.nan)
    out[["litres_now", "litres_prev"]] = out[["litres_now", "litres_prev"]].round(3)
    return out[keys + ["litres_now", "litres_prev", "extra_litres", "months_now", "months_prev", "pct_change"]].sort_values(keys, na_position="last").reset_index(drop=True)


@staged(sources=(*_L, "finance-reporting.statutory_report.le_key", "finance-reporting.statutory_report.fiscal_year", "finance-reporting.statutory_report.revenue", "finance-reporting.statutory_report.average_employees",
                 "finance-reporting.statutory_report.currency", "finance-reporting.statutory_report.scope"), facts=("world.now", "world.fx_eur_dkk_fixed"), oracle="py:tests/test_oracle_ghg.py::test_oracle_intensity_every_route")
def intensity(L: pd.DataFrame, SR: pd.DataFrame, year: int | None = None, basis: str = "current") -> Provenance:
    """Use this when you need the emissions in tonnes CO2e per employee and per DKK million of revenue, per legal entity and for the company.

    Tonnes CO2e per employee and per DKK million of revenue, per legal entity and for the company ('ALL', from the consolidated group row of the statutory report: its revenue is already in DKK without
    the intercompany sales). Emissions are the scope totals of the year on `basis`; location based and market based totals are both given, never added. Revenue of an EUR entity is converted at the
    fixed rate world.fx_eur_dkk_fixed. A year without a statutory report row gives null denominators. Property: all ratios are above zero for a year with lines.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        SR: Frame finance-reporting.statutory_report with le_key, scope ('entity' or 'group'), fiscal_year, revenue, average_employees and currency.
        year: The whole year, like 2025; the year before the year of world.now when None.
        basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a DataFrame with le_key, year, months (months of lines; under 12 flags a part year), employees, revenue_dkk_m, total_location_t, total_market_t, t_per_employee_location, t_per_employee_market, t_per_dkk_m_location and t_per_dkk_m_market (three decimals), one row per entity and the 'ALL' row last.

    Raises:
        FrameError: SR lacks a column, there are no emission lines for the year, the statutory report has more than one row for an entity (or the group) and the year, a revenue currency is not DKK or EUR, or the emission lines fail as in scope_totals (missing column, null kgco2e, bad year, basis or scope, restated lines not flagged).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import intensity
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100000.0, False, None),
        ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 50000.0, False, None)], columns=cols)
        >>> SR = pd.DataFrame({"le_key": ["LE-900001", "GROUP-900001"], "scope": ["entity", "group"], "fiscal_year": [2025, 2025],
        ...                    "revenue": [50000000.0, 50000000.0], "average_employees": [100, 100], "currency": ["DKK", "DKK"]})
        >>> r = intensity(L, SR, 2025, context=ctx)
        >>> r.value[["le_key", "employees", "revenue_dkk_m", "total_location_t", "t_per_employee_location", "t_per_dkk_m_location"]].values.tolist()
        [['LE-900001', 100.0, 50.0, 150.0, 1.5, 3.0], ['ALL', 100.0, 50.0, 150.0, 1.5, 3.0]]
    """
    _need(SR, ["le_key", "scope", "fiscal_year", "revenue", "average_employees", "currency"], "finance-reporting.statutory_report")
    y = _year(year)
    tot = unwrapped(scope_totals)(L, y, basis, None).value
    if tot.empty:
        raise FrameError(f"no emission lines for {y}")
    fx = fact("world.fx_eur_dkk_fixed")
    rep = SR[SR["fiscal_year"] == y]
    rows = []
    r: Any
    for r in tot.itertuples():
        if r.le_key == "ALL":
            q = rep[rep["scope"] == "group"]
        else:
            q = rep[(rep["scope"] == "entity") & (rep["le_key"] == r.le_key)]
        if len(q) > 1:
            raise FrameError(f"finance-reporting.statutory_report has more than one row for {r.le_key} and {y}")
        emp = float(q["average_employees"].iloc[0]) if len(q) else np.nan
        rev = np.nan
        if len(q):
            cur = q["currency"].iloc[0]
            if cur not in ("DKK", "EUR"):
                raise FrameError(f"revenue in {cur}: only DKK and EUR are converted")
            rev = float(q["revenue"].iloc[0]) * (float(fx.value) if cur == "EUR" else 1.0) / 1e6
        tl, tm = r.total_location_based / 1000.0, r.total_market_based / 1000.0
        rows.append({"le_key": r.le_key, "year": y, "months": int(r.months), "employees": emp, "revenue_dkk_m": round(rev, 3) if not np.isnan(rev) else np.nan, "total_location_t": round(tl, 3), "total_market_t": round(tm, 3),
                     "t_per_employee_location": round(tl / emp, 3) if emp > 0 else np.nan, "t_per_employee_market": round(tm / emp, 3) if emp > 0 else np.nan,
                     "t_per_dkk_m_location": round(tl / rev, 3) if rev > 0 else np.nan, "t_per_dkk_m_market": round(tm / rev, 3) if rev > 0 else np.nan})
    return _result(pd.DataFrame(rows), "halvaro.esg.ghg.intensity", facts=[fx], sources=(*_L, "finance-reporting.statutory_report"))


class StatementInputs(NamedTuple):
    """The numbers for a statutory statement or a questionnaire: `totals` (scope totals of the year on the basis), `comparatives` (the previous year on the current and on the first booked basis, so a
    restatement is visible), `energy_use` (MWh per carrier), `targets` (as stored) and `notes`."""
    totals: pd.DataFrame
    comparatives: pd.DataFrame
    energy_use: pd.DataFrame
    targets: pd.DataFrame
    notes: tuple[str, ...]


@staged(sources=(*_L, *_CONS, "energy-esg.energy_meter.mtr_key", "energy-esg.energy_meter.carrier", "energy-esg.energy_meter.le_key", "energy-esg.target.target_no"), facts=("world.now",), oracle="py:tests/test_energy_esg.py::test_emission_totals_for_finance")
def statement_inputs(L: pd.DataFrame, C: pd.DataFrame, M: pd.DataFrame, T: pd.DataFrame, year: int | None = None, le: str = "ALL", *, basis: str = "current", kwh_per_litre: Mapping[str, Any] | None = None) -> StatementInputs:
    """Use this when you need the numbers for a statutory statement or a questionnaire of one entity or of the company: totals, comparatives, energy use and targets.

    The scope totals of `year` on `basis` (default current; the basis decision is open, so the first booked totals are given too in the comparatives), the previous year on both bases, the energy use of the
    year in MWh by carrier (litres need `kwh_per_litre`, as in energy_use_mwh; no default), and the targets. Notes say which basis was used, the months covered, that scope 2 is given by both methods and
    never added, and that factors are synthetic. No text of a statement is written here.

    Args:
        L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
        C: Frame energy-esg.energy_consumption with mtr_key, period, quantity and unit.
        M: Frame energy-esg.energy_meter with mtr_key, carrier and unit (and le_key when le is one entity).
        T: Frame energy-esg.target with target_no, returned as stored sorted by target_no.
        year: The whole year, like 2025; the year before the year of world.now when None.
        le: One le_key, or 'ALL' (default) for the company.
        basis: 'current' (default) or 'first_booked'; the basis of the totals.
        kwh_per_litre: Mapping from a carrier metered in litres to its kWh per litre (VERIFY, no default); needed when the year has litres.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        StatementInputs, a named tuple of totals (the scope totals frame of the year), comparatives (the scope totals of the previous year on the current and on the first_booked basis, with a basis column), energy_use (carrier, unit, quantity, mwh), targets (frame T sorted by target_no) and notes (a tuple of text).

    Raises:
        FrameError: there are no emission lines for the year and entity, C, M or T lacks a column, the lines fail as in scope_totals (missing column, null kgco2e, bad year, basis or scope, restated lines not flagged), or the consumption fails as in energy_use_mwh (a repeated meter or period, an unknown meter, a unit that differs from the meter, a carrier in litres without a positive kwh_per_litre, a unit that is not kWh, MWh or l).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import statement_inputs
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([
        ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100.0, False, None),
        ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
        >>> C = pd.DataFrame({"mtr_key": ["MTR-900001"] * 2, "period": ["2025-12", "2025-11"], "quantity": [100.0, 200.0], "unit": "l"})
        >>> M = pd.DataFrame({"mtr_key": ["MTR-900001"], "carrier": "diesel", "unit": "l", "le_key": "LE-900001"})
        >>> T = pd.DataFrame({"target_no": ["TGT-900001"]})
        >>> s = statement_inputs(L, C, M, T, 2025, kwh_per_litre={"diesel": 10.0}, context=ctx)
        >>> s.totals.loc[0, ["scope1", "scope3", "total_location_based"]].astype(float).tolist()
        [100.0, 30.0, 130.0]
        >>> s.energy_use.to_dict("records")
        [{'carrier': 'diesel', 'unit': 'l', 'quantity': 300.0, 'mwh': 3.0}]
        >>> s.notes[0]
        'totals are on the current basis'
    """
    y = _year(year)
    t = unwrapped(scope_totals)(L, y, basis, le).value
    if t.empty:
        raise FrameError(f"no emission lines for {y} and {le}")
    comp = pd.concat([unwrapped(scope_totals)(L, y - 1, b, le).value.assign(basis=b) for b in ("current", "first_booked")], ignore_index=True)
    _need(C, ["mtr_key", "period", "quantity", "unit"], "energy-esg.energy_consumption")
    _need(M, ["mtr_key", "carrier", "unit"], "energy-esg.energy_meter")
    cy = C[C["period"].astype(str).str[:4] == str(y)]
    if le != "ALL":
        _need(M, ["le_key"], "energy-esg.energy_meter")
        cy = cy[cy["mtr_key"].isin(set(M.loc[M["le_key"] == le, "mtr_key"]))]
    from .activity import energy_use_mwh
    eu = unwrapped(energy_use_mwh)(cy, M, kwh_per_litre=kwh_per_litre) if len(cy) else pd.DataFrame(columns=["carrier", "unit", "quantity", "mwh"])
    _need(T, ["target_no"], "energy-esg.target")
    months = int(t["months"].iloc[0])
    notes = (f"totals are on the {basis} basis", f"{months} months of data in {y}" + ("" if months == 12 else " (a part year)"), "scope 2 is given by both methods and the two are not added",
             "comparatives are shown on the current and the first booked basis", "emission factors are synthetic: not for real reporting")
    return StatementInputs(t.reset_index(drop=True), comp, eu.reset_index(drop=True), T.sort_values("target_no").reset_index(drop=True), notes)
