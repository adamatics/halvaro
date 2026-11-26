"""Geometry versions, project areas and route changes, element age and condition class.

Geometries are WKT text in EPSG:25832 (metres), read here without shapely: POINT, LINESTRING and POLYGON are enough (T14). Lengths are planar. `valid_to` of a version is inclusive and null is
open; the next version starts the day after the previous ends (T13). Planned versions can start after now.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from ._util import _need, _utc
from ._types import DateLike
from ._tail import value_text

_CLASS_BANDS = ((80.0, "A"), (60.0, "B"), (40.0, "C"), (20.0, "D"))             # PROPOSED: policy.grid.condition_class_bands is needed; the generator code: A at 80 and above, B 60, C 40, D 20, E below
_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_TUPLE = re.compile(rf"\s*({_NUM})\s+({_NUM})((?:\s+{_NUM}){{0,2}})\s*", re.ASCII)
_GV = tuple(f"gis.geometry_version.{c}" for c in ("net_key", "valid_from", "valid_to", "geom", "source", "is_current"))
_DIM = {None: 2, "Z": 3, "M": 3, "ZM": 4}


def _coords(text: str, dim: int | None) -> np.ndarray:
    """Coordinate tuples of one WKT part. Z and M ordinates are read and dropped; every tuple of a geometry has the same number of ordinates."""
    pts, n = [], dim
    for part in text.split(","):
        m = _TUPLE.fullmatch(part)
        if not m:
            raise FrameError(f"not a coordinate tuple of a WKT geometry: {part.strip()[:40]!r}")
        k = 2 + len(m.group(3).split())
        if n is None:
            n = k
        if k != n or (dim is not None and k != dim):
            raise FrameError(f"WKT coordinates with {k} ordinates where {n} are expected: {part.strip()[:40]!r}")
        pts.append((float(m.group(1)), float(m.group(2))))
    return np.asarray(pts, dtype=float)


def _parse(wkt: Any) -> tuple[str, list[np.ndarray[Any, Any]]]:
    """(kind, rings) of a WKT text (case-insensitive, optional Z, M or ZM): POINT gives one point, LINESTRING one line (two points or more), POLYGON its closed rings (outer first, four points or
    more). A hole must lie inside the bounding box of the shell (full containment is not checked). EMPTY, MULTI* and collections are not read and raise FrameError."""
    if not isinstance(wkt, str):
        raise FrameError(f"geometry must be WKT text, not {type(wkt).__name__}")
    t = wkt.strip()
    m = re.fullmatch(r"(POINT|LINESTRING|POLYGON)\s*(ZM|Z|M)?\s*\((.*)\)", t, flags=re.S | re.I | re.ASCII)
    if not m:
        raise FrameError(f"unsupported or malformed WKT: {t[:50]!r}")
    dim: int | None
    kind, dim, body = m.group(1).upper(), _DIM[m.group(2).upper() if m.group(2) else None], m.group(3).strip()
    dim = dim if m.group(2) else None
    if kind == "POLYGON":
        if not re.fullmatch(r"\([^()]*\)(?:\s*,\s*\([^()]*\))*", body, flags=re.ASCII):
            raise FrameError(f"malformed POLYGON rings: {body[:50]!r}")
        rings = [_coords(r, dim) for r in re.findall(r"\(([^()]*)\)", body)]
        for r in rings:
            if len(r) < 4 or not np.array_equal(r[0], r[-1]):
                raise FrameError("a POLYGON ring needs four points or more and must be closed (first point equal to the last)")
        lo, hi = rings[0].min(axis=0), rings[0].max(axis=0)
        if any((r.min(axis=0) < lo).any() or (r.max(axis=0) > hi).any() for r in rings[1:]):
            raise FrameError("a POLYGON hole lies outside the shell")
        return kind, rings
    if "(" in body or ")" in body:
        raise FrameError(f"malformed {kind}: {body[:50]!r}")
    pts = _coords(body, dim)
    if kind == "POINT" and len(pts) != 1:
        raise FrameError("a POINT has exactly one coordinate tuple")
    if kind == "LINESTRING" and len(pts) < 2:
        raise FrameError("a LINESTRING needs two points or more")
    return kind, [pts]


def _length(rings: list[np.ndarray[Any, Any]], kind: str) -> float:
    if kind != "LINESTRING":
        return float("nan")
    c = rings[0]
    return float(np.hypot(*np.diff(c, axis=0).T).sum()) if len(c) > 1 else 0.0


def _area(rings: list[np.ndarray[Any, Any]], kind: str) -> float:
    if kind != "POLYGON":
        return float("nan")
    o = rings[0][0]                                                           # relative to the first vertex: UTM values of 5e5 and 6e6 lose digits otherwise
    a = [abs(0.5 * np.sum((r[:-1, 0] - o[0]) * (r[1:, 1] - o[1]) - (r[1:, 0] - o[0]) * (r[:-1, 1] - o[1]))) for r in rings]
    return float(a[0] - sum(a[1:]))


@staged(sources=("gis.geometry_version.geom", "gis.project_area.geom"), oracle="py:tests/test_gis.py::test_project_areas")
def parse_geom(geom: pd.Series, *, to_4326: bool = False) -> pd.DataFrame:
    """Use this when you need the kind, size and bounding box of WKT geometries as a table.

    The result has one row per geometry, with the index of the series. The coordinates are EPSG:25832 metres. to_4326 reprojects the bounding box corners to longitude and latitude and needs pyproj (an optional
    dependency, imported only then).

    Args:
        geom: A Series of WKT text (POINT, LINESTRING or POLYGON, for example gis.geometry_version.geom or gis.project_area.geom).
        to_4326: True to add the bounding box corners as lon_min, lat_min, lon_max and lat_max (needs pyproj); default False.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the index of geom and the columns kind, n_points, length_m (planar, lines only), area_m2 (polygons only), x_min, y_min, x_max, y_max (bounding box), and with to_4326 lon_min, lat_min,
        lon_max, lat_max.

    Raises:
        FrameError: geom is not a Series; a text is not WKT of a POINT, LINESTRING or POLYGON (malformed, empty, MULTI*, an unclosed ring or a hole outside the shell); to_4326 is set and pyproj is not installed.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import parse_geom
        >>> ctx = Context(stage="month12", role="analyst")
        >>> g = pd.Series(["LINESTRING (0 0, 30 40)", "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"])
        >>> out = parse_geom(g, context=ctx)
        >>> out["kind"].tolist(), out["n_points"].tolist(), out["length_m"].tolist()[0], out["area_m2"].tolist()[1]
        (['LINESTRING', 'POLYGON'], [2, 5], 50.0, 100.0)
    """
    if not isinstance(geom, pd.Series):
        raise FrameError(f"geom must be a Series of WKT text, not {type(geom).__name__}")
    rows = []
    for w in geom:
        kind, rings = _parse(w)
        allc = np.vstack(rings)
        rows.append((kind, len(allc), _length(rings, kind), _area(rings, kind), *allc.min(axis=0), *allc.max(axis=0)))
    out = pd.DataFrame(rows, columns=["kind", "n_points", "length_m", "area_m2", "x_min", "y_min", "x_max", "y_max"], index=geom.index)
    if to_4326:
        try:
            from pyproj import Transformer
        except ImportError:
            raise FrameError("to_4326 needs pyproj, which is not installed") from None
        t = Transformer.from_crs(25832, 4326, always_xy=True)
        lon0, lat0 = t.transform(out["x_min"].to_numpy(), out["y_min"].to_numpy())
        lon1, lat1 = t.transform(out["x_max"].to_numpy(), out["y_max"].to_numpy())
        out = out.assign(lon_min=lon0, lat_min=lat0, lon_max=lon1, lat_max=lat1)
    return out


def _versions(gv: pd.DataFrame, *, strict: bool = True) -> pd.DataFrame:
    _need(gv, ["net_key", "valid_from", "valid_to"], "gis.geometry_version")
    out = gv.assign(valid_from=_utc(gv["valid_from"], "gis.geometry_version.valid_from").dt.normalize().to_numpy(), valid_to=_utc(gv["valid_to"], "gis.geometry_version.valid_to").dt.normalize().to_numpy())
    if strict:
        if out["net_key"].isna().any():
            raise FrameError("gis.geometry_version has a null net_key")
        if out["valid_from"].isna().any():
            raise FrameError("gis.geometry_version has a version without valid_from (validate_versions reports it)")
    return out


def _flag(values: pd.Series, what: str) -> pd.Series:
    """A True/False column: only booleans are accepted (no text, numbers or nulls)."""
    if not all(isinstance(x, (bool, np.bool_)) for x in values):
        raise FrameError(f"{what} must hold True or False in every row (no nulls, text or numbers)")
    return values.astype(bool)


@staged(sources=_GV, facts=("world.now",), oracle="py:tests/test_gis.py::test_geometry_versions")
def geometry_as_of(geometry_version: pd.DataFrame, on: DateLike | None = None) -> pd.DataFrame:
    """Use this when you need the geometry version of each element that was valid on a date.

    A version is valid when valid_from <= date <= valid_to, an open end (null valid_to) valid. The date defaults to world.now. One row per element; an element with no version valid on the date (not yet built,
    or planned from later) is not listed.

    Args:
        geometry_version: The gis.geometry_version table; it needs the columns net_key, valid_from and valid_to.
        on: The date to look at; defaults to world.now.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The rows of geometry_version that are valid on the date (all its columns), sorted by net_key, with a fresh index.

    Raises:
        FrameError: geometry_version lacks a needed column; a net_key or a valid_from is null; a date cannot be read or on is not a date; two versions of an element are valid on the same date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import geometry_as_of
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gv = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "valid_from": ["2000-01-01", "2010-01-01"], "valid_to": ["2009-12-31", None], "geom": ["POINT (1 1)", "POINT (2 2)"]})
        >>> geometry_as_of(gv, "2005-06-01", context=ctx)["geom"].tolist()
        ['POINT (1 1)']
    """
    gv = _versions(geometry_version)
    d = pd.Timestamp(fact("world.now").value) if on is None else pd.Timestamp(_utc([on], "on").iloc[0])
    if pd.isna(d):
        raise FrameError(f"on must be a date (got {value_text(on)})")
    hit = gv[(gv["valid_from"] <= d) & (gv["valid_to"].isna() | (gv["valid_to"] >= d.normalize()))]
    dup = hit.duplicated("net_key", keep=False)
    if dup.any():
        raise FrameError(f"{int(hit.loc[dup, 'net_key'].nunique())} elements have more than one version valid on {d.date()} (for example {hit.loc[dup, 'net_key'].iloc[0]})")
    return hit.sort_values("net_key").reset_index(drop=True)


@staged(sources=(*_GV, "gis.grid_element.net_key", "gis.grid_element.current_geometry_valid_from"), oracle="py:tests/test_gis.py::test_geometry_versions")
def validate_versions(geometry_version: pd.DataFrame, grid_element: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use this when you need to check the geometry versions of the elements for overlaps, gaps and a wrong current version.

    Violations (table, key, rule, detail) of the geometry versions: null_valid_from, reversed (valid_to before valid_from), overlap, gap (the next version must start the day after the previous ends),
    open_not_last (an open end before a later version), no_current and several_current (is_current), current_not_open, and with grid_element current_start_mismatch (current_geometry_valid_from is the
    start of the current version), element_without_version, version_without_element (a version of an element that is not in grid_element) and duplicate_element. The key is the net_key. A version
    without valid_from is reported and left out of the other checks.

    Args:
        geometry_version: The gis.geometry_version table; it needs the columns net_key, valid_from, valid_to and is_current (True or False in every row).
        grid_element: Optional gis.grid_element table with net_key and current_geometry_valid_from; when given, the checks against the elements are added.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The violations frame of halvaro.core (columns table, key, rule, detail), sorted by key; empty when the versions are consistent.

    Raises:
        FrameError: a table lacks a needed column; a net_key is null; is_current is not True or False in every row; a date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import validate_versions
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gv = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "valid_from": ["2000-01-01", "2010-01-01"], "valid_to": ["2009-12-31", None], "is_current": [False, True]})
        >>> len(validate_versions(gv, context=ctx))
        0
        >>> bad = gv.assign(valid_from=["2000-01-01", "2012-01-01"])
        >>> validate_versions(bad, context=ctx)["rule"].tolist()
        ['gap']
    """
    gv = _versions(geometry_version, strict=False)
    _need(geometry_version, ["is_current"], "gis.geometry_version")
    if gv["net_key"].isna().any():
        raise FrameError("gis.geometry_version has a null net_key")
    gv = gv.assign(is_current=_flag(gv["is_current"], "gis.geometry_version.is_current"))
    rows: list[tuple[Any, ...]] = []                                            # (key, phase, seq, rule, detail)
    add = lambda k, ph, rule, detail: rows.append((k, ph, len(rows), rule, detail))
    nofrom = gv["valid_from"].isna()
    for k in sorted(gv.loc[nofrom, "net_key"].unique()):
        add(k, 0, "null_valid_from", "a version without valid_from")
    g = gv[~nofrom].sort_values(["net_key", "valid_from"], kind="stable")
    for k in sorted(g.loc[g["valid_to"] < g["valid_from"], "net_key"].unique()):
        add(k, 1, "reversed", "a version ends before it starts")
    sent = pd.Timestamp("2200-01-01")                                           # an open end counts as the far future in the running end
    run = g["valid_to"].fillna(sent).groupby(g["net_key"], sort=False).cummax()    # the latest end so far: a version nested in an earlier one must not make the next one look like a gap
    prev_to = g.groupby("net_key", sort=False)["valid_to"].shift()
    prev_run = run.groupby(g["net_key"], sort=False).shift()
    follow = g["net_key"].duplicated()                                          # not the first version of its element
    open_prev = follow & prev_to.isna()
    for k in g.loc[open_prev, "net_key"]:
        add(k, 2, "open_not_last", "a version without end is followed by another one")
    ok_prev = follow & ~open_prev & prev_run.notna() & (prev_run < sent)
    ov = ok_prev & (g["valid_from"] <= prev_run)
    for k, nf, pt in zip(g.loc[ov, "net_key"], g.loc[ov, "valid_from"], prev_run[ov]):
        add(k, 2, "overlap", f"a version starts {nf.date()} before an earlier one ends {pt.date()}")
    gp = ok_prev & ~ov & (g["valid_from"] != prev_run + pd.Timedelta(days=1))
    for k, nf, pt in zip(g.loc[gp, "net_key"], g.loc[gp, "valid_from"], prev_run[gp]):
        add(k, 2, "gap", f"a version starts {nf.date()}, the previous one ended {pt.date()}")
    cur = g[g["is_current"]]
    n_cur = cur.groupby("net_key").size()
    for k in sorted(set(g["net_key"]) - set(n_cur.index)):
        add(k, 3, "no_current", "no version is current")
    for k, n in n_cur[n_cur > 1].items():
        add(k, 3, "several_current", f"{n} versions are current")
    one = cur[cur["net_key"].isin(n_cur[n_cur == 1].index)]
    for k in one.loc[one["valid_to"].notna(), "net_key"]:
        add(k, 3, "current_not_open", "the current version has an end")
    if grid_element is not None:
        _need(grid_element, ["net_key", "current_geometry_valid_from"], "gis.grid_element")
        cs = cur.drop_duplicates("net_key").set_index("net_key")["valid_from"]
        ge = grid_element.assign(cs=_utc(grid_element["current_geometry_valid_from"], "current_geometry_valid_from").dt.normalize().to_numpy())
        has = set(gv["net_key"])
        for k in ge.loc[ge["net_key"].duplicated(keep="first") & ge["net_key"].notna(), "net_key"].unique():
            add(k, 4, "duplicate_element", "the element is listed more than once in grid_element")
        for k in sorted(has - set(ge["net_key"].dropna())):
            add(k, 4, "version_without_element", "the element has geometry versions but is not in grid_element")
        r: Any
        for r in ge.drop_duplicates("net_key").itertuples():
            if pd.isna(r.net_key):
                continue
            if r.net_key not in cs.index:
                add(r.net_key, 4, "element_without_version", "the element has versions but none is current" if r.net_key in has else "the element has no geometry version")
            elif r.cs != cs.loc[r.net_key]:
                add(r.net_key, 4, "current_start_mismatch", f"current_geometry_valid_from {r.cs.date() if pd.notna(r.cs) else None}, the current version starts {cast(pd.Timestamp, cs.loc[r.net_key]).date()}")
    from halvaro.core import violations
    rows.sort(key=lambda x: (str(x[0]), x[1], x[2]))
    return violations.frame([("gis.geometry_version", k, rule, detail) for k, _, _, rule, detail in rows])


@staged(sources=tuple(f"gis.project_area.{c}" for c in ("prj_key", "kind", "version", "valid_from", "valid_to", "length_m", "geom")))
def route_change(project_area: pd.DataFrame, *, tolerance_m: float = 0.5) -> pd.DataFrame:
    """Use this when you need the planned and as-built route length of each project with the version dates and the change, as the frame the app passes to halvaro-delivery.

    Lengths are the stored length_m of the route versions (planned_route, as_built_route). A project with several planned or as-built versions raises (a re-plan needs an as-of date, which is not built).
    A project with only an as-built route has a null planned length and changed False; a planned length of 0 gives a null delta_percent. PROPOSED: tolerance 0.5 m.

    Args:
        project_area: The gis.project_area table; it needs the columns prj_key, kind, version, valid_from, valid_to and length_m.
        tolerance_m: Difference in metres above which the lengths count as changed (PROPOSED 0.5); a number of zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame sorted by prj_key with the columns prj_key, planned_length_m, as_built_length_m (null without an as-built route), delta_m, delta_percent, planned_valid_from, planned_valid_to,
        as_built_valid_from and changed (the lengths differ by more than tolerance_m).

    Raises:
        FrameError: project_area lacks a needed column; tolerance_m is not a number of zero or more; a prj_key is null; length_m is not a number or is negative; a project has more than one planned or more
            than one as-built route version; a planned or as-built route version has no length_m; a date cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import route_change
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pa = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "kind": ["planned_route", "as_built_route"], "version": [1, 1],
        ...                    "valid_from": ["2024-01-01", "2024-06-01"], "valid_to": [None, None], "length_m": [100.0, 110.0]})
        >>> out = route_change(pa, context=ctx)
        >>> out[["planned_length_m", "as_built_length_m", "delta_m", "delta_percent", "changed"]].to_dict("records")
        [{'planned_length_m': 100.0, 'as_built_length_m': 110.0, 'delta_m': 10.0, 'delta_percent': 10.0, 'changed': True}]
    """
    _need(project_area, ["prj_key", "kind", "version", "valid_from", "valid_to", "length_m"], "gis.project_area")
    if not isinstance(tolerance_m, (int, float, np.number)) or isinstance(tolerance_m, bool) or not np.isfinite(tolerance_m) or tolerance_m < 0:
        raise FrameError(f"tolerance_m must be zero or more (got {value_text(tolerance_m)})")
    if project_area["prj_key"].isna().any():
        raise FrameError("gis.project_area has a null prj_key")
    raw = project_area["length_m"]
    if any(isinstance(x, (bool, np.bool_, str)) for x in raw.dropna()) or pd.api.types.is_bool_dtype(raw):
        raise FrameError("gis.project_area.length_m holds a value that is not a number")
    try:
        lens = pd.to_numeric(raw).astype(float)
    except (ValueError, TypeError):
        raise FrameError("gis.project_area.length_m holds a value that is not a number") from None
    if (~np.isfinite(lens) & lens.notna()).any() or (lens < 0).any():
        raise FrameError("gis.project_area.length_m must be zero or more")
    project_area = project_area.assign(length_m=lens)
    pa = project_area.assign(valid_from=_utc(project_area["valid_from"], "gis.project_area.valid_from").to_numpy(), valid_to=_utc(project_area["valid_to"], "gis.project_area.valid_to").to_numpy())
    pl, ab = pa[pa["kind"] == "planned_route"], pa[pa["kind"] == "as_built_route"]
    for f, name in ((pl, "planned"), (ab, "as-built")):
        if f["prj_key"].duplicated().any():
            raise FrameError(f"a project has more than one {name} route version")
        if f["length_m"].isna().any():
            raise FrameError(f"{name} route versions without a length_m")
    m = pl.set_index("prj_key")[["length_m", "valid_from", "valid_to"]].rename(columns={"length_m": "planned_length_m", "valid_from": "planned_valid_from", "valid_to": "planned_valid_to"}).join(
        ab.set_index("prj_key")[["length_m", "valid_from"]].rename(columns={"length_m": "as_built_length_m", "valid_from": "as_built_valid_from"}), how="outer")
    m["delta_m"] = (m["as_built_length_m"] - m["planned_length_m"]).round(3)
    m["delta_percent"] = np.where(m["planned_length_m"] > 0, np.round(m["delta_m"] / m["planned_length_m"].where(m["planned_length_m"] > 0) * 100, 3), np.nan)
    m["changed"] = (m["as_built_length_m"] - m["planned_length_m"]).abs().gt(tolerance_m).fillna(False).astype(bool)     # on the unrounded difference
    return m.reset_index().rename(columns={"index": "prj_key"}).sort_values("prj_key").reset_index(drop=True)


@staged(sources=("gis.grid_element.install_year", "gis.grid_element.status", "gis.grid_element.commissioned_date"), facts=("world.now",), oracle="py:repo_tests/test_oracle_geometry_release.py::test_oracle_element_age_baseline_per_element")
def element_age(grid_element: pd.DataFrame, on: DateLike | None = None) -> pd.Series:
    """Use this when you need the age in years of each grid element on a date.

    The age is in years (days over 365.25) from the commissioning date, else 1 January of the install year; it is null when the element is not in service (status in_service is matched exactly), has no install
    year or is commissioned after the date. The date defaults to world.now. The age has two decimals, so a threshold on the age sees an element one day short of a whole year as that year.

    Args:
        grid_element: The gis.grid_element table; it needs the columns install_year, status and commissioned_date.
        on: The date to measure the age on; defaults to world.now.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series named age_years with the index of grid_element.

    Raises:
        FrameError: grid_element lacks a needed column; on is not a date; a date cannot be read; install_year is not a number or not a whole year from 1800 to 2200.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import element_age
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ge = pd.DataFrame({"install_year": [2000, 2010, None], "status": ["in_service", "planned", "in_service"], "commissioned_date": ["2000-01-01", None, None]})
        >>> element_age(ge, "2020-01-01", context=ctx).round(1).tolist()
        [20.0, nan, nan]
    """
    _need(grid_element, ["install_year", "status", "commissioned_date"], "gis.grid_element")
    d = pd.Timestamp(fact("world.now").value) if on is None else pd.Timestamp(_utc([on], "on").iloc[0])
    if pd.isna(d):
        raise FrameError(f"on must be a date (got {value_text(on)})")
    start = _utc(grid_element["commissioned_date"], "gis.grid_element.commissioned_date")
    try:
        iy = pd.to_numeric(grid_element["install_year"])
    except (ValueError, TypeError):
        raise FrameError("gis.grid_element.install_year holds a value that is not a number") from None
    bad = iy.notna() & ((iy % 1 != 0) | (iy < 1800) | (iy > 2200))
    if bad.any():
        raise FrameError(f"gis.grid_element.install_year must be a whole year from 1800 to 2200 (for example {iy[bad].iloc[0]})")
    fallback = pd.to_datetime(iy.astype("Int64").astype("string") + "-01-01", errors="coerce")
    start = start.fillna(pd.Series(fallback.to_numpy(), index=start.index))
    age = (d - start).dt.days / 365.25
    live = (grid_element["status"] == "in_service").to_numpy() & start.notna().to_numpy() & (start <= d).to_numpy()
    return pd.Series(np.where(live, np.round(age.to_numpy(dtype=float), 2), np.nan), index=grid_element.index, name="age_years")


@staged(sources=("gis.grid_element.condition_score",), oracle="py:halvaro_gen/world/gis/network.py::condition_class")
def condition_class_from_score(score: pd.Series, *, bands: Sequence[Any] = _CLASS_BANDS) -> pd.Series:
    """Use this when you need the condition class A to E of condition scores.

    The class is the first band whose lower bound the score reaches (A at 80 and above, B 60, C 40, D 20), E below; null for a null score.

    PROPOSED: the bands (policy.grid.condition_class_bands is needed; the rule is in the generator code only).

    Args:
        score: A Series of condition scores from 0 to 100 (for example gis.grid_element.condition_score).
        bands: Pairs (lower bound, class) in falling order of the lower bound (PROPOSED: A at 80, B 60, C 40, D 20).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series named condition_class with the index of score, holding the class letters (null for a null score).

    Raises:
        FrameError: score is not a Series or holds a value that is not a number; a score is outside 0 to 100; bands are not (lower bound, class) pairs in falling order.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import condition_class_from_score
        >>> ctx = Context(stage="month12", role="analyst")
        >>> condition_class_from_score(pd.Series([95, 60, 10, None]), context=ctx).tolist()
        ['A', 'B', 'E', None]
    """
    if not isinstance(score, pd.Series):
        raise FrameError(f"score must be a Series, not {type(score).__name__}")
    if not isinstance(bands, (tuple, list)):
        raise FrameError(f"bands are (lower bound, class) pairs in falling order (got {type(bands).__name__})")
    b: list[Any] = list(bands)
    if not b or any(not isinstance(x, (tuple, list)) or len(x) != 2 or isinstance(x[0], bool) or not isinstance(x[0], (int, float, np.number)) or not np.isfinite(x[0]) or not isinstance(x[1], str) for x in b):
        raise FrameError(f"bands are (lower bound, class) pairs in falling order (got {value_text(bands)})")
    b = [tuple(x) for x in b]
    if any(not isinstance(x, tuple) or len(x) != 2 for x in b) or [x[0] for x in b] != sorted((x[0] for x in b), reverse=True):
        raise FrameError(f"bands are (lower bound, class) pairs in falling order (got {value_text(bands)})")
    if pd.api.types.is_bool_dtype(score) or pd.api.types.is_complex_dtype(score) or any(isinstance(x, (bool, np.bool_, str, complex)) for x in score.dropna()):
        raise FrameError("score holds a value that is not a number")
    try:
        v = pd.to_numeric(score).to_numpy(dtype=float, na_value=np.nan)
    except (ValueError, TypeError):
        raise FrameError("score holds a value that is not a number") from None
    if (~np.isfinite(v) & ~np.isnan(v)).any() or ((v < 0) | (v > 100)).any():
        raise FrameError(f"score must be from 0 to 100 (for example {float(v[(~np.isfinite(v) & ~np.isnan(v)) | (v < 0) | (v > 100)][0])!r})")
    out = np.full(len(v), "E", dtype=object)
    for lo, cls in reversed(b):
        out = np.where(v >= lo, cls, out)
    out = np.where(np.isnan(v), None, out)
    return pd.Series(out, index=score.index, name="condition_class", dtype=object)
