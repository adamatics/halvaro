"""Project footprint: the four components per project and period from the emission lines, the scope split, kg per route metre, the check against a customer limit and the component medians.

The comparable set of a footprint comparison is a delivery frame passed in (profile dk_dh_recent of halvaro-delivery); this module never selects projects. Purchases are in the data from 2023-01, so projects
started earlier have partial footprints and active projects are to date (T14); a null route length stays null (never zero).
"""
from __future__ import annotations

import dataclasses
from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact, make_envelope

from ._guard import staged
from ._util import Provenance, _basis, _days, _need, _num

_COMPONENTS = ("materials", "transport", "site", "subcontractor")
_COMPONENT_MAP = {("3.1", "purchased_goods"): "materials", ("3.1", "purchased_services"): "subcontractor", ("3.4", "upstream_transport"): "transport"}       # PROPOSED: scope 1 and 3.3 are the site component
_L = tuple(f"energy-esg.emission_line.{c}" for c in ("prj_key", "le_key", "period", "scope", "category", "line_no", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"))
_PF = tuple(f"energy-esg.project_footprint.{c}" for c in ("prj_key", "period", "materials_kgco2e", "transport_kgco2e", "site_kgco2e", "subcontractor_kgco2e", "total_kgco2e"))
_P = ("projects.project.prj_key", "projects.project.route_length_m", "projects.project.start", "projects.project.status")


def _strict(series: pd.Series, what: str, *, nullable: bool = True) -> pd.Series:
    """The column as float64 (null stays NaN); text, booleans and infinite values raise FrameError."""
    if pd.api.types.is_bool_dtype(series) or any(isinstance(v, (bool, np.bool_, str)) for v in series.dropna()):
        raise FrameError(f"{what} must hold numbers (no text or booleans)")
    try:
        out = _num(series)
    except (ValueError, TypeError):
        raise FrameError(f"{what} must hold numbers") from None
    if np.isinf(out).any() or (not nullable and out.isna().any()):
        raise FrameError(f"{what} must be finite" + ("" if nullable else " and not null"))
    return out


def _project_lines(L: pd.DataFrame, basis: str) -> pd.DataFrame:
    x = _basis(L, basis)
    _need(x, ["prj_key", "ghg_category", "scope", "kgco2e"], "energy-esg.emission_line")
    x = x[x["prj_key"].notna()]                                                   # lines without a project (scope 2, waste) are not project footprint, whatever their kgco2e
    if x["kgco2e"].isna().any():
        raise FrameError("energy-esg.emission_line has project lines with null kgco2e")
    if x["scope"].isna().any():
        raise FrameError("energy-esg.emission_line has project lines without a scope")
    x = x.assign(kgco2e=_strict(x["kgco2e"], "energy-esg.emission_line.kgco2e", nullable=False))
    _strict(x["scope"], "energy-esg.emission_line.scope", nullable=False)
    if "period" in x.columns and x["period"].isna().any():
        raise FrameError("energy-esg.emission_line has project lines without a period")
    return x.assign(scope=_num(x["scope"]))


def _stamp(value: Any, function: str, *, facts: Sequence[Any] = (), sources: Sequence[str] = ()) -> Provenance:
    env = make_envelope(value, function, facts=facts, sources=sources, warnings=("emission factors are synthetic with a VERIFY note: not for real reporting",), cls=Provenance)
    return cast(Provenance, dataclasses.replace(env, status="VERIFY+synthetic", synthetic=True))


@staged(sources=_L, oracle="py:tests/test_energy_esg.py::test_project_footprints_equal_project_lines")
def project_footprint_from_lines(L: pd.DataFrame, basis: str = "current", *, component_map: Mapping[tuple[str, str], str] = _COMPONENT_MAP) -> pd.DataFrame:
    """Use this when you need the four footprint components of each project and period from the emission lines that carry a project.

    The result has the shape of energy-esg.project_footprint (without route_length_m and basis). Scope 1 and scope 3.3 (the fuel of the site and its well to tank) are the site component; purchased goods (3.1) are materials, purchased services (3.1) subcontractors and upstream transport (3.4) transport.
    A project line that fits no component raises, and so does a component_map value that is not one of the four components (the map cannot move scope 1 or 3.3 lines out of the site component). Lines without a project (scope 2, waste) are not project footprint.
    basis is current (restated lines replace the superseded originals) or first_booked. PROPOSED: the map, as in the generator.

    Args:
        L: The energy-esg.emission_line table, with the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period.
        basis: current (superseded originals left out, the default) or first_booked (restated lines left out).
        component_map: Map from (ghg_category, category) to materials, transport, site or subcontractor (PROPOSED default: (3.1, purchased_goods) materials, (3.1, purchased_services) subcontractor, (3.4, upstream_transport) transport).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e, subcontractor_kgco2e and total_kgco2e (three decimals), sorted by prj_key and period.

    Raises:
        FrameError: component_map is not a mapping or has a value that is not materials, transport, site or subcontractor.
        FrameError: L is not a DataFrame or lacks one of the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period; is_superseded has nulls; two lines share le_key, period, scope, category and line_no; basis is not current or first_booked.
        FrameError: a project line has a null kgco2e, scope or period; kgco2e or scope holds text, booleans or infinite values.
        FrameError: a project line fits no component.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import project_footprint_from_lines
        >>> L = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "le_key": ["LE-900001"] * 3, "period": ["2025-01"] * 3, "scope": [1, 3, 3],
        ...                   "category": ["fuel", "purchased_goods", "upstream_transport"], "line_no": [1, 2, 3],
        ...                   "ghg_category": ["1", "3.1", "3.4"], "kgco2e": [10.0, 20.0, 5.0],
        ...                   "is_superseded": [False] * 3, "restated_from_period": [None] * 3})
        >>> out = project_footprint_from_lines(L, context=ctx)
        >>> out[["prj_key", "materials_kgco2e", "transport_kgco2e", "site_kgco2e", "total_kgco2e"]].values.tolist()
        [['PRJ-900001', 20.0, 5.0, 10.0, 35.0]]
    """
    if not isinstance(component_map, Mapping) or set(component_map.values()) - set(_COMPONENTS):
        raise FrameError(f"component_map values must be one of {', '.join(_COMPONENTS)} (scope 1 and 3.3 lines are always the site component)")
    x = _project_lines(L, basis)
    _need(x, ["category", "period"], "energy-esg.emission_line")
    comp_values = np.where((x["scope"] == 1) | (x["ghg_category"] == "3.3"), "site", np.array([component_map.get((g, c)) for g, c in zip(x["ghg_category"], x["category"])], dtype=np.object_))
    comp = pd.Series(comp_values, index=x.index, dtype=object)
    if comp.isna().any():
        bad = x[comp.isna()].iloc[0]
        raise FrameError(f"{int(comp.isna().sum())} project lines fit no component (for example ghg_category {bad['ghg_category']}, category {bad['category']})")
    g = x.assign(c=comp).pivot_table(index=["prj_key", "period"], columns="c", values="kgco2e", aggfunc="sum", fill_value=0.0, observed=True)
    g = g.reindex(columns=list(_COMPONENTS), fill_value=0.0)
    out = g.rename(columns={c: f"{c}_kgco2e" for c in _COMPONENTS}).reset_index()
    out["total_kgco2e"] = out[[f"{c}_kgco2e" for c in _COMPONENTS]].sum(axis=1)
    return out.round({**{f"{c}_kgco2e": 3 for c in _COMPONENTS}, "total_kgco2e": 3}).sort_values(["prj_key", "period"]).reset_index(drop=True)


@staged(sources=_L, oracle="py:tests/test_energy_esg.py::test_project_footprints_equal_project_lines")
def project_scope_split(L: pd.DataFrame, year: int, basis: str = "current") -> pd.DataFrame:
    """Use this when you need the kgco2e of each project in one year split by scope 1, 3.1, 3.3 and 3.4.

    The sum over projects of the total equals the project footprints of that year. Lines without a project are not counted.

    Args:
        L: The energy-esg.emission_line table, with the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period.
        year: The whole year to split, for example 2025.
        basis: current (superseded originals left out, the default) or first_booked (restated lines left out).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns prj_key, scope1, scope3_1, scope3_3, scope3_4 and total_kgco2e (three decimals), sorted by prj_key.

    Raises:
        FrameError: year is not a whole number (a boolean is refused).
        FrameError: L is not a DataFrame or lacks one of the columns prj_key, le_key, period, scope, category, line_no, ghg_category, kgco2e, is_superseded and restated_from_period; is_superseded has nulls; two lines share le_key, period, scope, category and line_no; basis is not current or first_booked.
        FrameError: a project line has a null kgco2e, scope or period; kgco2e or scope holds text, booleans or infinite values.
        FrameError: a period does not start with a year; a project line of the year is not in scope 1, 3.1, 3.3 or 3.4.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import project_scope_split
        >>> L = pd.DataFrame({"prj_key": ["PRJ-900001"] * 3, "le_key": ["LE-900001"] * 3, "period": ["2025-01"] * 3, "scope": [1, 3, 3],
        ...                   "category": ["fuel", "purchased_goods", "upstream_transport"], "line_no": [1, 2, 3],
        ...                   "ghg_category": ["1", "3.1", "3.4"], "kgco2e": [10.0, 20.0, 5.0],
        ...                   "is_superseded": [False] * 3, "restated_from_period": [None] * 3})
        >>> out = project_scope_split(L, 2025, context=ctx)
        >>> out[["prj_key", "scope1", "scope3_1", "scope3_4", "total_kgco2e"]].values.tolist()
        [['PRJ-900001', 10.0, 20.0, 5.0, 35.0]]
    """
    if isinstance(year, bool) or not isinstance(year, (int, np.integer)):
        raise FrameError(f"year must be a whole year, not {year!r}")
    x = _project_lines(L, basis)
    _need(x, ["period"], "energy-esg.emission_line")
    per = x["period"].astype(str)
    if not per.str.match(r"\d{4}").all():
        raise FrameError(f"energy-esg.emission_line.period must start with the year, not {per[~per.str.match(r'\d{4}')].iloc[0]!r}")
    x = x[per.str[:4] == str(int(year))]
    ghg = x["ghg_category"].astype(str)
    key = pd.Series(np.where(x["scope"] == 1, "scope1", ghg.map({"3.1": "scope3_1", "3.3": "scope3_3", "3.4": "scope3_4"})), index=x.index, dtype=object)
    bad = x[key.isna()]
    if len(bad):
        raise FrameError(f"project lines in scope {bad['scope'].iloc[0]:g}, ghg_category {bad['ghg_category'].iloc[0]}: the split covers scope 1, 3.1, 3.3 and 3.4")
    g = x.assign(k=key.to_numpy()).pivot_table(index="prj_key", columns="k", values="kgco2e", aggfunc="sum", fill_value=0.0, observed=True).reindex(columns=["scope1", "scope3_1", "scope3_3", "scope3_4"], fill_value=0.0)
    g["total_kgco2e"] = g.sum(axis=1)
    return g.round(3).reset_index().sort_values("prj_key").reset_index(drop=True)


@staged(sources=(*_PF, *_P), facts=("world.window_start",))
def per_metre(PF: pd.DataFrame, P: pd.DataFrame, RC: pd.DataFrame | None = None) -> Provenance:
    """Use this when you need the kilograms CO2e per planned route metre of each project.

    The footprint over all periods is divided by the planned route length; the value is null when the length is null. The value is a Provenance (synthetic, status VERIFY+synthetic, fact world.window_start).
    PROPOSED: the RC column name is a stand-in until halvaro-grid defines the frame.

    Args:
        PF: The energy-esg.project_footprint table, with the columns prj_key, period and total_kgco2e.
        P: The projects.project table, with the columns prj_key, route_length_m, start and status.
        RC: Optional grid route_change frame with prj_key and as_built_length_m; it only sets length_changed, the planned length stays the default (see the route change of the grid library).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Provenance whose value is a frame sorted by prj_key with the columns prj_key, total_kgco2e, route_length_m, kgco2e_per_m (three decimals), per_m_exact (unrounded, what limit_check compares),
        partial_history (the project started before world.window_start, because purchases are in the data from then; null for a project without a start), active_to_date (status active) and length_changed (the as-built length of RC differs from the planned one by more than half a metre; false without a planned length).

    Raises:
        FrameError: PF, P or RC lacks a needed column; PF has two rows for a project and period or P two rows for a project; PF has a null prj_key or null totals; totals, route_length_m or as_built_length_m are not numbers or are infinite.
        FrameError: a project of PF is not in projects.project; route_length_m is zero or less; start is not a date or has a time zone; RC has two rows for a project or a negative as_built_length_m.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import per_metre
        >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "period": ["2025-01", "2025-02"], "total_kgco2e": [100.0, 50.0]})
        >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [1000.0], "start": ["2024-05-01"], "status": ["active"]})
        >>> out = per_metre(PF, P, context=ctx).value
        >>> out[["prj_key", "kgco2e_per_m", "partial_history", "active_to_date"]].values.tolist()
        [['PRJ-900001', 0.15, False, True]]
    """
    _need(PF, ["prj_key", "period", "total_kgco2e"], "energy-esg.project_footprint")
    _need(P, ["prj_key", "route_length_m", "start", "status"], "projects.project")
    if PF.duplicated(["prj_key", "period"]).any() or P["prj_key"].duplicated().any():
        raise FrameError("project_footprint and projects.project need one row per project (and period)")
    if PF["total_kgco2e"].isna().any():
        raise FrameError("energy-esg.project_footprint has null totals")
    if PF["prj_key"].isna().any():
        raise FrameError("energy-esg.project_footprint has rows without a prj_key")
    PF = PF.assign(total_kgco2e=_strict(PF["total_kgco2e"], "energy-esg.project_footprint.total_kgco2e", nullable=False))
    w0 = pd.Timestamp(fact("world.window_start").value)
    tot = PF.groupby("prj_key")["total_kgco2e"].sum().round(6).rename("_total")     # the periods carry three decimals: the sum is cut at six, so float noise does not decide a tie
    x = P.set_index("prj_key").join(tot, how="inner")
    unknown = sorted(set(PF["prj_key"]) - set(P["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the footprint are not in projects.project (for example {unknown[0]})")
    length = _strict(x["route_length_m"], "projects.project.route_length_m")
    if (length <= 0).any():
        raise FrameError("route_length_m must be positive or null")
    out = pd.DataFrame({"prj_key": x.index, "total_kgco2e": x["_total"].to_numpy(), "route_length_m": length.to_numpy()})
    out["per_m_exact"] = out["total_kgco2e"] / out["route_length_m"]                 # not rounded: limit_check compares this, so a value displayed as the limit is not a tie by rounding
    out["kgco2e_per_m"] = out["per_m_exact"].round(3)
    start = _days(x.reset_index()[["prj_key", "start"]], ["start"], "projects.project")["start"]
    out["partial_history"] = pd.Series(pd.array(np.where(start.isna(), pd.NA, start < w0), dtype="boolean"), index=out.index) if start.isna().any() else (start < w0).to_numpy()
    out["active_to_date"] = (x["status"] == "active").to_numpy()
    changed = pd.Series(False, index=x.index)
    if RC is not None:
        _need(RC, ["prj_key", "as_built_length_m"], "grid route_change frame")
        if RC["prj_key"].duplicated().any():
            raise FrameError("the route_change frame has more than one row for a project")
        ab_all = _strict(RC.set_index("prj_key")["as_built_length_m"], "the route_change frame as_built_length_m")
        if (ab_all < 0).any():
            raise FrameError("the route_change frame has a negative as_built_length_m")
        ab = ab_all.reindex(x.index)
        changed = (ab.notna() & length.notna() & (ab - length).abs().gt(0.5)).astype(bool)     # without a planned length there is nothing to differ from
    out["length_changed"] = changed.to_numpy()
    return _stamp(out.sort_values("prj_key").reset_index(drop=True), "halvaro.esg.footprint.per_metre", facts=[fact("world.window_start")], sources=(*_PF, *_P))


class LimitCheck(NamedTuple):
    """The comparable set against a limit: n (values), n_null (projects without a value), median, limit, gap (median less limit), n_above, n_below, headroom_percent (limit less median over limit; negative when the median is above the limit), n_at (values equal to the limit).
    A count that puts a value at the limit with the values below it is n_below + n_at here."""
    n: int
    n_null: int
    median: float
    limit: float
    gap: float
    n_above: int
    n_below: int
    headroom_percent: float
    n_at: int


@staged(sources=(*_PF, *_P))
def limit_check(pm: pd.DataFrame, cs: pd.DataFrame, limit: float) -> LimitCheck:
    """Use this when you need to compare the kg CO2e per metre of a comparable set of projects with a customer limit.

    The median, the gap, the number of projects above and below and the headroom of the kg per metre of the comparable set `cs` against the limit (kg per metre). Projects of the set without a value are not counted and their number is reported (n_null).
    A project of the set that is not in pm counts as null. A value exactly at the limit (compared unrounded when pm carries per_m_exact) is neither above nor below; it is counted in n_at.

    Args:
        pm: The value of per_metre, with the columns prj_key and kgco2e_per_m (and per_m_exact, used when present).
        cs: A delivery comparable_set frame, with the column prj_key.
        limit: The limit in kg per metre, a positive finite int or float (not a boolean or a float32).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A LimitCheck with n (values), n_null (projects without a value), median, limit, gap (median less limit), n_above, n_below, headroom_percent (limit less median over limit; negative when the median is above the limit) and n_at (values equal to the limit).
        A count that puts a value at the limit with the values below it is n_below + n_at here.

    Raises:
        FrameError: pm lacks prj_key or kgco2e_per_m, or cs lacks prj_key; a prj_key is null or duplicated in either frame.
        FrameError: limit is not an int or float (a boolean or float32 is refused), is too large, is not finite or is zero or less; the per metre values are not numbers; no project of the comparable set has a value per metre.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import limit_check
        >>> pm = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "kgco2e_per_m": [0.5, 1.5, 3.0]})
        >>> cs = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003", "PRJ-900004"]})
        >>> r = limit_check(pm, cs, 2.0, context=ctx)
        >>> (r.n, r.n_null, r.median, r.n_above, r.n_below, r.headroom_percent)
        (3, 1, 1.5, 1, 2, 25.0)
    """
    _need(pm, ["prj_key", "kgco2e_per_m"], "per_metre frame")
    _need(cs, ["prj_key"], "delivery comparable_set frame")
    if not isinstance(limit, (int, float, np.integer)) or isinstance(limit, (bool, np.bool_)):
        raise FrameError(f"limit must be a positive number of kg per metre (int or float, not a float32), not {limit!r}")
    try:
        limit = float(limit)
    except OverflowError:
        raise FrameError("limit is too large") from None
    if not np.isfinite(limit) or limit <= 0:
        raise FrameError(f"limit must be a positive number of kg per metre, not {limit!r}")
    if cs["prj_key"].duplicated().any() or pm["prj_key"].duplicated().any():
        raise FrameError("the comparable set and the per metre frame need one row per project")
    if cs["prj_key"].isna().any() or pm["prj_key"].isna().any():
        raise FrameError("the comparable set and the per metre frame need a prj_key in every row")
    v = _strict(pm.set_index("prj_key")["per_m_exact" if "per_m_exact" in pm.columns else "kgco2e_per_m"], "the per metre frame").reindex(cs["prj_key"])
    ok = v.dropna()
    if ok.empty:
        raise FrameError("no project of the comparable set has a value per metre")
    med = float(ok.median())
    d = np.round(ok.to_numpy() - limit, 9)                                          # float noise at the ninth decimal does not decide a tie (the inputs have three decimals)
    gap = round(med - limit, 3)
    return LimitCheck(int(len(ok)), int(len(v) - len(ok)), round(med, 3), limit, gap, int((d > 0).sum()), int((d < 0).sum()), round((limit - med) / limit * 100, 3) + 0.0, int((d == 0).sum()))


@staged(sources=(*_PF, *_P))
def component_split(PF: pd.DataFrame, P: pd.DataFrame, cs: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the median kg CO2e per route metre of each footprint component over a comparable set of projects.

    Each project's component over all periods is divided by its route length, then the median is taken over the projects with a length. Projects without a route length are left out.

    Args:
        PF: The energy-esg.project_footprint table, with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e and subcontractor_kgco2e.
        P: The projects.project table, with the columns prj_key and route_length_m.
        cs: A delivery comparable_set frame, with the column prj_key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns component (materials, transport, site, subcontractor), median_kgco2e_per_m (three decimals; null when no project has a length) and n (projects used).

    Raises:
        FrameError: PF, P or cs lacks a needed column; a prj_key of cs or PF is null; cs or P has two rows for a project; PF has two rows for a project and period.
        FrameError: a component of PF is null or not a number; a footprint project of the set is not in projects.project; route_length_m is zero or less or not a number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import component_split
        >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "period": ["2025-01", "2025-01"], "materials_kgco2e": [100.0, 300.0],
        ...                    "transport_kgco2e": [10.0, 30.0], "site_kgco2e": [50.0, 150.0], "subcontractor_kgco2e": [0.0, 0.0]})
        >>> P = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "route_length_m": [100.0, 100.0]})
        >>> cs = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
        >>> out = component_split(PF, P, cs, context=ctx)
        >>> out[["component", "median_kgco2e_per_m", "n"]].values.tolist()[:2]
        [['materials', 2.0, 2], ['transport', 0.2, 2]]
    """
    _need(PF, ["prj_key", "period", *[f"{c}_kgco2e" for c in _COMPONENTS]], "energy-esg.project_footprint")
    _need(P, ["prj_key", "route_length_m"], "projects.project")
    _need(cs, ["prj_key"], "delivery comparable_set frame")
    if cs["prj_key"].duplicated().any() or P["prj_key"].duplicated().any():
        raise FrameError("the comparable set and projects.project need one row per project")
    if cs["prj_key"].isna().any() or PF["prj_key"].isna().any():
        raise FrameError("the comparable set and the footprint need a prj_key in every row")
    if PF.duplicated(["prj_key", "period"]).any():
        raise FrameError("energy-esg.project_footprint needs one row per project and period")
    sel = PF[PF["prj_key"].isin(set(cs["prj_key"]))]
    comp = [f"{c}_kgco2e" for c in _COMPONENTS]
    if sel[comp].isna().any().any():
        raise FrameError("energy-esg.project_footprint has null components")
    unknown = sorted(set(sel["prj_key"]) - set(P["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the footprint are not in projects.project (for example {unknown[0]})")
    plen = _strict(P.set_index("prj_key")["route_length_m"], "projects.project.route_length_m")
    if (plen <= 0).any():
        raise FrameError("route_length_m must be positive or null")
    s = sel.assign(**{c: _strict(sel[c], f"energy-esg.project_footprint.{c}", nullable=False) for c in comp}).groupby("prj_key")[comp].sum()
    length = plen.reindex(s.index)
    keep = length > 0
    rows = [(c, round(float((s.loc[keep, f"{c}_kgco2e"] / length[keep]).median()), 3) if keep.any() else np.nan, int(keep.sum())) for c in _COMPONENTS]
    return pd.DataFrame(rows, columns=["component", "median_kgco2e_per_m", "n"])


_CAT_COMPONENT = {"material": "materials", "labour": "site", "equipment": "site", "subcontractor": "subcontractor"}          # PROPOSED: cost category -> footprint component; transport follows materials


class TenderEstimate(NamedTuple):
    """Labelled estimate of the footprint of an open tender: `rows` (component, currency, intensity_kg_per_unit, tender_cost, estimated_kg), `estimated_kg` (null without a cost frame), the cross-check from the
    comparables (`median_kg_per_m`, `metres`, `cross_check_kg`), `ratio` (estimate over cross-check), `n_projects` and `warnings`. An estimate, not a measurement; synthetic data."""
    rows: pd.DataFrame
    estimated_kg: float
    median_kg_per_m: float
    metres: float
    cross_check_kg: float
    ratio: float
    n_projects: int
    label: str
    warnings: tuple[str, ...]


@staged(sources=("projects.estimate_line.cst_key", "projects.estimate_line.amount", "projects.cost_code.category", *_PF, "projects.project.route_length_m"), oracle="py:tests/test_oracle_footprint.py::test_oracle_tender_estimate_every_route")
def tender_estimate(EB: pd.DataFrame, CC: pd.DataFrame, PF: pd.DataFrame, P: pd.DataFrame, TC: pd.DataFrame | None, metres: float, *, estimate_type: str = "tender",
                    component_of_category: Mapping[str, Any] | None = None) -> TenderEstimate:
    """Use this when you need a labelled footprint estimate of an open tender from the intensity of its comparable projects.

    The estimate is kilograms per unit of estimate cost for each footprint component in each currency (the footprint of the comparable projects over the cost of the estimate categories that drive the component,
    PROPOSED map material to materials, labour and equipment to site, subcontractor to subcontractor, 'other' to none; transport is added to materials), times the cost `TC` of the tender by category that the app passes in.
    The cross-check is the median kg per route metre of the comparables times `metres`. Without `TC` only the cross-check is returned and `warnings` says so; a currency of `TC` that no comparable estimate has gives no row and a warning; a component with tender cost in a currency whose comparables carry no cost for that component gives no row and no warning.
    Amounts of different currencies are never added. Legacy summary projects have no estimate lines and are not in EB. An estimate, not a measurement; synthetic data.

    Args:
        EB: The lines frame of estimate_bridge of the comparables, with the columns prj_key, type, cst_key, amount and currency.
        CC: The projects.cost_code table, with the columns cst_key and category (group rows are left out when is_group is present).
        PF: The energy-esg.project_footprint table, with the columns prj_key, period, materials_kgco2e, transport_kgco2e, site_kgco2e, subcontractor_kgco2e and total_kgco2e.
        P: The projects.project table, with the columns prj_key and route_length_m.
        TC: The cost of the tender by category, with the columns category, amount and currency (passed in by the app), or None for the cross-check only.
        metres: The planned route metres of the tender, a positive finite number.
        estimate_type: The type of the estimate lines used from EB (default tender).
        component_of_category: Map from cost category to footprint component (default the PROPOSED map: material materials, labour and equipment site, subcontractor subcontractor).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A TenderEstimate with rows (component, currency, intensity_kg_per_unit, tender_cost, estimated_kg), estimated_kg (null without a cost frame), the cross-check from the comparables (median_kg_per_m, metres, cross_check_kg),
        ratio (estimate over cross-check; null when the cross-check is zero or there is no estimate), n_projects, label and warnings.

    Raises:
        FrameError: EB, CC, PF, P or TC lacks a needed column; metres is not a positive finite number (a boolean is refused); projects.cost_code has two rows for a cst_key or projects.project two rows for a project.
        FrameError: an estimate line has a cost code that projects.cost_code does not hold; no comparable project has both an estimate and a footprint; no comparable project has a route length.
        FrameError: a tender cost is not a number of zero or more; the tender cost frame matches no component and currency of the comparables.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.esg import tender_estimate
        >>> EB = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tender"], "cst_key": ["CST-900001"], "amount": [1000.0], "currency": ["EUR"]})
        >>> CC = pd.DataFrame({"cst_key": ["CST-900001"], "category": ["material"]})
        >>> PF = pd.DataFrame({"prj_key": ["PRJ-900001"], "period": ["2025-01"], "materials_kgco2e": [100.0], "transport_kgco2e": [10.0],
        ...                    "site_kgco2e": [50.0], "subcontractor_kgco2e": [0.0], "total_kgco2e": [160.0]})
        >>> P = pd.DataFrame({"prj_key": ["PRJ-900001"], "route_length_m": [100.0]})
        >>> TC = pd.DataFrame({"category": ["material"], "amount": [2000.0], "currency": ["EUR"]})
        >>> r = tender_estimate(EB, CC, PF, P, TC, 500.0, context=ctx)
        >>> (r.estimated_kg, r.cross_check_kg, r.ratio, r.n_projects)
        (220.0, 800.0, 0.275, 1)
    """
    _need(EB, ["prj_key", "type", "cst_key", "amount", "currency"], "estimate lines")
    _need(CC, ["cst_key", "category"], "projects.cost_code")
    _need(PF, ["prj_key", "period", *[f"{c}_kgco2e" for c in _COMPONENTS], "total_kgco2e"], "energy-esg.project_footprint")
    _need(P, ["prj_key", "route_length_m"], "projects.project")
    if isinstance(metres, bool) or not isinstance(metres, (int, float, np.integer)) or not np.isfinite(float(metres)) or metres <= 0:
        raise FrameError("metres must be a positive number of route metres")
    if CC["cst_key"].duplicated().any() or P["prj_key"].duplicated().any():
        raise FrameError("projects.cost_code and projects.project need one row per key")
    cmap = dict(_CAT_COMPONENT if component_of_category is None else component_of_category)
    warn = ["an estimate from the comparables, not a measurement; emission factors are synthetic"]
    lines = EB[EB["type"] == estimate_type]
    if "is_group" in CC.columns:
        lines = lines[~lines["cst_key"].isin(set(CC.loc[CC["is_group"].astype(bool), "cst_key"]))]
    lines = lines.assign(category=lines["cst_key"].map(CC.set_index("cst_key")["category"]))
    if lines["category"].isna().any():
        raise FrameError("estimate lines with a cost code that projects.cost_code does not hold")
    pf = PF.groupby("prj_key")[[f"{c}_kgco2e" for c in _COMPONENTS] + ["total_kgco2e"]].sum()
    keys = sorted(set(lines["prj_key"]) & set(pf.index))
    n = len(keys)
    if n == 0:
        raise FrameError("no comparable project has both an estimate and a footprint")
    ln = P.set_index("prj_key")["route_length_m"].reindex(keys)
    per_m = (pf.loc[keys, "total_kgco2e"] / ln.where(ln > 0)).dropna()
    if per_m.empty:
        raise FrameError("no comparable project has a route length")
    med = float(per_m.median())
    cross = round(med * float(metres), 1)
    comp_rows = []
    sel = lines[lines["prj_key"].isin(keys)]
    for cur, g in sel.groupby("currency"):
        for comp in _COMPONENTS:
            cats = [c for c, k in cmap.items() if k == comp or (comp == "materials" and False)]
            cost = g[g["category"].isin(cats)].groupby("prj_key")["amount"].sum()
            if comp == "transport" or cost.sum() <= 0:
                continue
            ps = list(cost.index)
            kg = pf.loc[ps, f"{comp}_kgco2e"].sum() + (pf.loc[ps, "transport_kgco2e"].sum() if comp == "materials" else 0.0)
            comp_rows.append({"component": comp, "currency": cur, "intensity_kg_per_unit": kg / float(cost.sum()), "n_projects": len(ps)})
    ints = pd.DataFrame(comp_rows, columns=["component", "currency", "intensity_kg_per_unit", "n_projects"])
    if TC is None:
        warn.append("no tender cost frame was passed: only the cross-check against the median kg per metre is returned")
        return TenderEstimate(pd.DataFrame(columns=["component", "currency", "intensity_kg_per_unit", "tender_cost", "estimated_kg"]), float("nan"), round(med, 3), float(metres), cross, float("nan"), n, "estimate, synthetic data", tuple(warn))
    _need(TC, ["category", "amount", "currency"], "the tender cost frame")
    if (pd.to_numeric(TC["amount"], errors="coerce").isna() | (pd.to_numeric(TC["amount"], errors="coerce") < 0)).any():
        raise FrameError("tender costs must be numbers of zero or more")
    out = []
    r: Any
    for r in ints.itertuples():
        cats = [c for c, k in cmap.items() if k == r.component]
        tender_cost = float(TC[TC["category"].isin(cats) & (TC["currency"] == r.currency)]["amount"].sum())
        if tender_cost > 0:
            out.append({"component": r.component, "currency": r.currency, "intensity_kg_per_unit": round(r.intensity_kg_per_unit, 6), "tender_cost": tender_cost, "estimated_kg": round(tender_cost * r.intensity_kg_per_unit, 1)})
    rows = pd.DataFrame(out, columns=["component", "currency", "intensity_kg_per_unit", "tender_cost", "estimated_kg"])
    missing = sorted(set(TC["currency"]) - set(ints["currency"]))
    if missing:
        warn.append(f"no comparable estimate in {', '.join(missing)}: the tender cost in that currency has no intensity")
    if rows.empty:
        raise FrameError("the tender cost frame matches no component and currency of the comparables")
    est = float(rows["estimated_kg"].sum())
    return TenderEstimate(rows, round(est, 1), round(med, 3), float(metres), cross, round(est / cross, 3) if cross > 0 else float("nan"), n, "estimate, synthetic data", tuple(warn))
