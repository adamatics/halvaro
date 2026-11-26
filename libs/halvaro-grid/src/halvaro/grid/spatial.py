"""Spatial functions (plan 5.6): fault density, fault clusters, install age clusters and the share of each soil class along a route.

No geometry library: the release holds WKT in EPSG:25832 metres (routes, ground polygons) and a longitude and latitude per element, which is the element's midpoint. Distances between elements use a
local planar projection of the longitude and latitude (metres, good to a fraction of a percent at the 300 m of the cluster rule). Policy values are keywords marked PROPOSED.
"""
from __future__ import annotations

from typing import Any, NamedTuple, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need, _utc
from ._types import DateLike
from .geometry import _parse
from ._tail import value_text

_M_PER_DEG_LAT = 110574.0
_M_PER_DEG_LON = 111320.0
_ON_SITE = "site_finding"        # the survey_kind value of gis.ground_condition for a polygon recorded on site (the other value is borehole_survey)


def _seq(value: Any, name: str) -> list[Any]:
    """A list of allowed values: a plain string is refused (it would be split into letters)."""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise FrameError(f"{name} must be a tuple or list of values, not {value!r}")
    return list(value)


def _xy(lon: pd.Series, lat: pd.Series) -> np.ndarray[Any, Any]:
    """Planar metres of longitude and latitude around the mean latitude of the points."""
    lo, la = lon.to_numpy(dtype=float), lat.to_numpy(dtype=float)
    if not (np.isfinite(lo).all() and np.isfinite(la).all()):
        raise FrameError("lon and lat must be finite numbers")
    return np.column_stack([lo * _M_PER_DEG_LON * np.cos(np.radians(la.mean() if len(la) else 0.0)), la * _M_PER_DEG_LAT])


def _components(xy: np.ndarray[Any, Any], link_m: float) -> np.ndarray[Any, Any]:
    """Single linkage components at a linking distance: label per point, found with a grid hash and union find."""
    n = len(xy)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cell = np.floor(xy / link_m).astype(np.int64)
    buckets: dict[tuple[Any, ...], list[int]] = {}
    for i, c in enumerate(map(tuple, cell)):
        buckets.setdefault(c, []).append(i)
    for (cx, cy), idx in buckets.items():
        near_l = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in buckets.get((cx + dx, cy + dy), [])]
        near = np.array(near_l)
        for i in idx:
            d = np.hypot(*(xy[near] - xy[i]).T)
            for j in near[(d <= link_m) & (near > i)]:
                a, b = find(i), find(int(j))
                if a != b:
                    parent[max(a, b)] = min(a, b)
    return np.array([find(i) for i in range(n)])


def _hull(pts: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Convex hull (monotone chain), counter clockwise without the closing point; a point or a segment gives one or two points."""
    p = np.unique(pts, axis=0)
    if len(p) <= 2:
        return p
    p = p[np.lexsort((p[:, 1], p[:, 0]))]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower: list[Any] = []
    upper: list[Any] = []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    for q in p[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return np.array(lower[:-1] + upper[:-1])


def _dist_to_hull(points: np.ndarray[Any, Any], hull: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Distance of each point to the convex hull polygon, zero inside it."""
    if len(hull) == 1:
        return cast("np.ndarray[Any, Any]", np.hypot(*(points - hull[0]).T))
    a, b = hull, np.roll(hull, -1, axis=0)
    if len(hull) == 2:
        b = hull[[1, 0]]
    ab = b - a
    denom = np.maximum((ab ** 2).sum(axis=1), 1e-12)
    t = np.clip(((points[:, None, :] - a[None]) * ab[None]).sum(axis=2) / denom[None], 0.0, 1.0)
    proj = a[None] + t[:, :, None] * ab[None]
    d = np.hypot(*(points[:, None, :] - proj).transpose(2, 0, 1)).min(axis=1)
    if len(hull) >= 3:
        side = ab[None, :, 0] * (points[:, None, 1] - a[None, :, 1]) - ab[None, :, 1] * (points[:, None, 0] - a[None, :, 0])
        d = np.where((side >= 0).all(axis=1), 0.0, d)
    return cast("np.ndarray[Any, Any]", d)


class FaultCluster(NamedTuple):
    """A cluster of faulted elements: id, centre (longitude, latitude of the mean of the faulted members), n_faulted (elements with a fault in the window), n_faults, n_members (in service elements of the
    faulted types inside the hull buffered by the buffer distance), members (their net_keys, sorted), hull (longitude and latitude corners), radius_m (largest distance of a faulted element to the centre)."""
    cluster_id: int
    centre_lon: float
    centre_lat: float
    n_faulted: int
    n_faults: int
    n_members: int
    members: tuple[Any, ...]
    hull: tuple[Any, ...]
    radius_m: float


@staged(sources=("service.fault_event.net_key", "service.fault_event.fault_ts", "gis.grid_element.net_key", "gis.grid_element.element_type", "gis.grid_element.zone_key", "gis.grid_element.lon",
                 "gis.grid_element.lat", "gis.grid_element.commissioned_date", "gis.grid_element.status"))
def fault_density(fault_event: pd.DataFrame, grid_element: pd.DataFrame, window_start: DateLike, window_end: DateLike, *, cell_m: float = 500.0, in_service: str | None = "in_service") -> pd.DataFrame:
    """Use this when you need the faults per element and month of each element in a window, with the planar grid cell of each element.

    Faults per element in a window (both days inclusive: PROPOSED policy.grid.winter_window, December to February), for the elements that were commissioned by the end of the window and, when the frame has a
    `status` column, are `in_service` (planned or under construction elements do not exist yet, T18; pass in_service=None to keep every status), with a planar grid cell of `cell_m` metres (PROPOSED 500).
    An element without a commissioning date counts as commissioned. Elements with no fault are listed with zero. A fault of an element that is not in grid_element raises FrameError.

    Args:
        fault_event: The service.fault_event table; it needs the columns net_key and fault_ts.
        grid_element: The gis.grid_element table; it needs the columns net_key, element_type, zone_key, lon, lat and commissioned_date, and status when in_service is used.
        window_start: First day of the window (inclusive), a date or timestamp.
        window_end: Last day of the window (inclusive), a date or timestamp, not before window_start.
        cell_m: Edge of a planar grid cell in metres (PROPOSED 500); a positive number.
        in_service: The status value an element must have (default "in_service"); None keeps every status.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame sorted by net_key with the columns net_key, element_type, zone_key, lon, lat, cell_x, cell_y, n_faults, months (the part of the window the element existed, in months of 30.4375 days),
        faults_per_month (null when months is zero) and cell_faults (faults of all listed elements in the cell).

    Raises:
        FrameError: a table lacks a needed column; cell_m is not a positive number; the window is not a (start, end) pair of dates in order; gis.grid_element has more than one row for a net_key; a faulted
            element is not in gis.grid_element; a timestamp or date cannot be read; lon or lat is not a finite number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import fault_density
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ev = pd.DataFrame({"net_key": ["NET-900001", "NET-900001"], "fault_ts": ["2024-01-05T10:00:00", "2024-01-20T10:00:00"]})
        >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "element_type": ["cable", "cable"], "zone_key": ["ZONE-0001", "ZONE-0001"],
        ...                    "lon": [9.50, 9.51], "lat": [53.50, 53.51], "commissioned_date": ["2000-01-01", "2001-01-01"], "status": ["in_service", "in_service"]})
        >>> out = fault_density(ev, ge, "2024-01-01", "2024-02-29", context=ctx)
        >>> out["n_faults"].tolist()
        [2, 0]
        >>> out["months"].round(1).tolist()
        [2.0, 2.0]
    """
    _need(fault_event, ["net_key", "fault_ts"], "service.fault_event")
    _need(grid_element, ["net_key", "element_type", "zone_key", "lon", "lat", "commissioned_date"], "gis.grid_element")
    if isinstance(cell_m, bool) or not isinstance(cell_m, (int, float)) or cell_m <= 0:
        raise FrameError(f"cell_m must be a positive number of metres (got {value_text(cell_m)})")
    a, b = _utc([window_start], "window_start").iloc[0], _utc([window_end], "window_end").iloc[0]
    if pd.isna(a) or pd.isna(b) or a.normalize() > b.normalize():
        raise FrameError("the window is a (start, end) pair of dates in order")
    a, b = a.normalize(), b.normalize()
    if grid_element["net_key"].duplicated().any():
        raise FrameError("gis.grid_element has more than one row for a net_key")
    unknown = sorted(set(fault_event["net_key"].dropna()) - set(grid_element["net_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} faulted elements are not in gis.grid_element (for example {unknown[0]})")
    ts = _utc(fault_event["fault_ts"], "service.fault_event.fault_ts")
    end = b + pd.Timedelta(days=1)
    n = fault_event[(ts >= a).to_numpy() & (ts < end).to_numpy()].groupby("net_key").size()
    com = _utc(grid_element["commissioned_date"], "gis.grid_element.commissioned_date")
    ge = grid_element.assign(_c=com.to_numpy())
    ge = ge[ge["_c"].isna() | (ge["_c"] < end)]
    if in_service is not None and "status" in ge.columns:
        ge = ge[ge["status"] == in_service]
    xy = _xy(ge["lon"], ge["lat"])
    out = pd.DataFrame({"net_key": ge["net_key"].to_numpy(), "element_type": ge["element_type"].to_numpy(), "zone_key": ge["zone_key"].to_numpy(), "lon": ge["lon"].to_numpy(dtype=float),
                        "lat": ge["lat"].to_numpy(dtype=float), "cell_x": np.floor(xy[:, 0] / cell_m).astype(int), "cell_y": np.floor(xy[:, 1] / cell_m).astype(int)})
    out["n_faults"] = out["net_key"].map(n).fillna(0).astype(int).to_numpy()
    start = ge["_c"].fillna(a).clip(lower=a)
    out["months"] = ((end - start).dt.days.clip(lower=0) / 30.4375).round(4).to_numpy()
    out["faults_per_month"] = np.where(out["months"] > 0, out["n_faults"] / out["months"].where(out["months"] > 0), np.nan).round(4)
    out["cell_faults"] = out.groupby(["cell_x", "cell_y"])["n_faults"].transform("sum")
    return out.sort_values("net_key").reset_index(drop=True)


@staged(sources=("service.fault_event.net_key", "gis.grid_element.net_key", "gis.grid_element.element_type", "gis.grid_element.status", "gis.grid_element.lon", "gis.grid_element.lat"))
def fault_clusters(density: pd.DataFrame, grid_element: pd.DataFrame, *, link_m: float = 300.0, min_faults: int = 8, buffer_m: float = 150.0, min_element_faults: int = 1) -> list[FaultCluster]:
    """Use this when you need the spatial clusters of faulted elements found from the output of fault_density.

    Elements with a fault in the window are linked when their midpoints are at most `link_m` apart (single linkage, PROPOSED 300 m); a component with at least `min_faults` faults (PROPOSED 8) is a cluster. Its
    hull (convex, buffered by `buffer_m`, PROPOSED 150 m) selects the members: in service elements of the faulted types of the cluster that exist in the window (they are in the density frame). Only elements
    with at least `min_element_faults` faults in the window (PROPOSED 1) are linked. The rule is policy.grid.fault_cluster (needed, LOW) and the distances are not calibrated by the data: with dense faults
    single linkage can chain a whole zone into one component that is much larger than a cluster; a smaller link_m with a higher min_element_faults keeps the components small (the measurement is in
    the notes of the closed generator repository). The age route (age_group_clusters) groups elements by install year instead.

    Args:
        density: The output of fault_density; it needs the columns net_key, element_type, lon, lat and n_faults.
        grid_element: The gis.grid_element table; it needs the columns net_key, element_type, status, lon and lat.
        link_m: Linking distance in metres (PROPOSED 300); above zero.
        min_faults: Smallest number of faults of a cluster (PROPOSED 8); a whole number, one or more.
        buffer_m: Distance in metres by which the hull is buffered to select members (PROPOSED 150); zero or more.
        min_element_faults: Smallest number of faults for an element to be linked (PROPOSED 1); a whole number, one or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A list of FaultCluster, sorted by size (faults, then first net_key), with cluster_id (from 1), centre_lon and centre_lat (the mean of the faulted members), n_faulted (elements with a fault in the
        window), n_faults, n_members (in service elements of the faulted types inside the buffered hull), members (their net_keys, sorted), hull (longitude and latitude corners) and radius_m (largest
        distance of a faulted element to the centre). The list is empty when no element reaches min_element_faults.

    Raises:
        FrameError: a table lacks a needed column; link_m or buffer_m is not a number of metres (or link_m is zero); min_faults or min_element_faults is not a whole number of one or more; lon or lat is not
            a finite number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import fault_clusters
        >>> ctx = Context(stage="month12", role="analyst")
        >>> dens = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "element_type": ["cable"] * 3, "lon": [9.5000, 9.5005, 9.6000],
        ...                      "lat": [53.5, 53.5, 53.6], "n_faults": [3, 2, 1]})
        >>> ge = dens.assign(status="in_service")
        >>> cl = fault_clusters(dens, ge, min_faults=4, context=ctx)
        >>> len(cl), cl[0].n_faults, list(cl[0].members)
        (1, 5, ['NET-900001', 'NET-900002'])
    """
    _need(density, ["net_key", "element_type", "lon", "lat", "n_faults"], "fault_density output")
    _need(grid_element, ["net_key", "element_type", "status", "lon", "lat"], "gis.grid_element")
    for name, v in (("link_m", link_m), ("buffer_m", buffer_m)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or (name == "link_m" and v == 0):
            raise FrameError(f"{name} must be a number of metres, link_m above zero (got {value_text(v)})")
    if isinstance(min_faults, bool) or not isinstance(min_faults, int) or min_faults < 1:
        raise FrameError(f"min_faults must be a whole number, one or more (got {value_text(min_faults)})")
    if isinstance(min_element_faults, bool) or not isinstance(min_element_faults, int) or min_element_faults < 1:
        raise FrameError(f"min_element_faults must be a whole number, one or more (got {value_text(min_element_faults)})")
    f = density[density["n_faults"] >= min_element_faults].reset_index(drop=True)
    if f.empty:
        return []
    allxy = _xy(pd.concat([grid_element["lon"], f["lon"]]), pd.concat([grid_element["lat"], f["lat"]]))
    ge_xy, f_xy = allxy[:len(grid_element)], allxy[len(grid_element):]
    lab = _components(f_xy, float(link_m))
    out = []
    for lbl in sorted(set(lab)):
        sel = lab == lbl
        if f.loc[sel, "n_faults"].sum() < min_faults:
            continue
        pts, types = f_xy[sel], set(f.loc[sel, "element_type"])
        hull = _hull(pts)
        ok = (grid_element["status"].to_numpy() == "in_service") & grid_element["element_type"].isin(types).to_numpy() & grid_element["net_key"].isin(set(density["net_key"])).to_numpy()
        near = np.zeros(len(grid_element), dtype=bool)
        near[ok] = _dist_to_hull(ge_xy[ok], hull) <= buffer_m
        members = tuple(sorted(set(grid_element.loc[near, "net_key"]) | set(f.loc[sel, "net_key"][f.loc[sel, "net_key"].isin(grid_element.loc[ok, "net_key"])])))
        ctr = pts.mean(axis=0)
        lon_lat = f.loc[sel, ["lon", "lat"]].to_numpy(dtype=float)
        hull_ll = tuple((float(x), float(y)) for x, y in lon_lat[[int(np.argmin(np.hypot(*(pts - h).T))) for h in hull]])
        out.append(FaultCluster(0, float(f.loc[sel, "lon"].mean()), float(f.loc[sel, "lat"].mean()), int(sel.sum()), int(f.loc[sel, "n_faults"].sum()), len(members), members, hull_ll,
                                round(float(np.hypot(*(pts - ctr).T).max()), 1)))
    out.sort(key=lambda c: (-c.n_faults, c.members[0] if c.members else ""))
    return [c._replace(cluster_id=i + 1) for i, c in enumerate(out)]


@staged(sources=("gis.grid_element.net_key", "gis.grid_element.install_year", "gis.grid_element.element_type", "gis.grid_element.zone_key", "gis.grid_element.lon", "gis.grid_element.lat"))
def age_group_clusters(grid_element: pd.DataFrame, *, decade: int, element_type: str, link_m: float = 300.0, min_size: int = 20, buffer_m: float = 150.0) -> pd.DataFrame:
    """Use this when you need the spatial concentrations of one install decade and element type found without fault data.

    The elements of `element_type` installed in the decade (for example 1960 for 1960 to 1969) are linked at `link_m` metres (PROPOSED 300, policy.grid.fault_cluster); a component of at least `min_size`
    elements (PROPOSED 20) is a candidate. density_ratio is the elements of the same type per square kilometre of the hull buffered by `buffer_m` (150 m PROPOSED), over the same for all other elements of the
    type in the cluster's most common zone, in or out of the decade, over the bounding box of the zone's elements of that type; it is null when the hull has no area.

    Args:
        grid_element: The gis.grid_element table; it needs the columns net_key, install_year (numeric, null for elements not in service), element_type, zone_key, lon and lat.
        decade: First year of the decade, a whole number divisible by ten (for example 1960).
        element_type: The element type to look at.
        link_m: Linking distance in metres (PROPOSED 300); above zero.
        min_size: Smallest number of elements of a candidate (PROPOSED 20); a whole number, two or more.
        buffer_m: Distance in metres by which the hull is buffered (PROPOSED 150); above zero.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns cluster_id, zone_key (most common), n_elements, share_of_group, centre_lon, centre_lat, radius_m (largest distance to the centre) and density_ratio, sorted by n_elements
        (largest first) and cluster_id. It is empty when no element of the type was installed in the decade.

    Raises:
        FrameError: grid_element lacks a needed column; decade is not a whole number divisible by ten; link_m or buffer_m is not a positive number; min_size is not a whole number of two or more; install_year is
            not numeric; lon or lat is not a finite number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import age_group_clusters
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "install_year": [1961, 1965, 1998], "element_type": ["cable"] * 3,
        ...                    "zone_key": ["ZONE-0001"] * 3, "lon": [9.5000, 9.5005, 9.7], "lat": [53.5, 53.5, 53.7]})
        >>> out = age_group_clusters(ge, decade=1960, element_type="cable", min_size=2, context=ctx)
        >>> out["n_elements"].tolist(), out["zone_key"].tolist()
        ([2], ['ZONE-0001'])
    """
    _need(grid_element, ["net_key", "install_year", "element_type", "zone_key", "lon", "lat"], "gis.grid_element")
    if isinstance(decade, bool) or not isinstance(decade, int) or decade % 10:
        raise FrameError(f"decade is the first year of a decade, for example 1960 (got {value_text(decade)})")
    for nm, v in (("link_m", link_m), ("buffer_m", buffer_m)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0:
            raise FrameError(f"{nm} must be a positive number of metres (got {value_text(v)})")
    if isinstance(min_size, bool) or not isinstance(min_size, int) or min_size < 2:
        raise FrameError(f"min_size must be a whole number of two or more (got {value_text(min_size)})")
    if not pd.api.types.is_numeric_dtype(grid_element["install_year"]):
        raise FrameError("gis.grid_element.install_year must be numeric (null for elements not in service)")
    ge = grid_element[grid_element["element_type"] == element_type]
    ge = ge[ge["install_year"].between(decade, decade + 9) & ge["lon"].notna() & ge["lat"].notna()].reset_index(drop=True)
    cols = ["cluster_id", "zone_key", "n_elements", "share_of_group", "centre_lon", "centre_lat", "radius_m", "density_ratio"]
    if ge.empty:
        return pd.DataFrame(columns=cols)
    typ = grid_element[(grid_element["element_type"] == element_type) & grid_element["lon"].notna()]
    xy_all = _xy(pd.concat([typ["lon"], ge["lon"]]), pd.concat([typ["lat"], ge["lat"]]))
    t_xy, g_xy = xy_all[:len(typ)], xy_all[len(typ):]
    lab = _components(g_xy, float(link_m))
    rows: list[Any] = []
    for lbl in sorted(set(lab)):
        sel = lab == lbl
        if sel.sum() < min_size:
            continue
        pts = g_xy[sel]
        ctr = pts.mean(axis=0)
        inside = _dist_to_hull(t_xy, _hull(pts)) <= buffer_m
        area = _polygon_area(_buffered_hull_area(_hull(pts), buffer_m))
        zmode = ge.loc[sel, "zone_key"].mode()
        zone = zmode.iloc[0] if len(zmode) else None
        zmask = (typ["zone_key"] == zone).to_numpy() if zone is not None else np.ones(len(typ), dtype=bool)
        zxy = t_xy[zmask]
        in_group = typ["net_key"].isin(set(ge.loc[sel, "net_key"])).to_numpy()
        others_inside = int((inside & ~in_group).sum())
        rest_area = (np.ptp(zxy[:, 0]) * np.ptp(zxy[:, 1])) / 1e6 - area
        rows.append({"cluster_id": len(rows) + 1, "zone_key": zone, "n_elements": int(sel.sum()), "share_of_group": round(float(sel.mean()), 4),
                     "centre_lon": float(ge.loc[sel, "lon"].mean()), "centre_lat": float(ge.loc[sel, "lat"].mean()), "radius_m": round(float(np.hypot(*(pts - ctr).T).max()), 1),
                     "density_ratio": round((int(inside.sum()) / area) / (max(int(zmask.sum()) - int((inside & zmask).sum()), 1) / max(rest_area, 1e-9)), 3) if area > 0 and rest_area > 0 else np.nan})
        rows[-1]["others_inside"] = others_inside
    out = pd.DataFrame(rows, columns=cols + ["others_inside"]) if rows else pd.DataFrame(columns=cols + ["others_inside"])
    return out.drop(columns="others_inside").sort_values(["n_elements", "cluster_id"], ascending=[False, True]).reset_index(drop=True)


def _buffered_hull_area(hull: np.ndarray[Any, Any], buffer_m: float) -> tuple[float, float]:
    """Area in km2 of the hull buffered by a distance: hull area + perimeter x buffer + pi buffer squared (exact for a convex hull), in square metres."""
    if len(hull) == 1:
        per, area = 0.0, 0.0
    elif len(hull) == 2:
        per, area = 2 * float(np.hypot(*(hull[0] - hull[1]))), 0.0
    else:
        x, y = hull[:, 0], hull[:, 1]
        area = 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
        per = float(np.hypot(*(hull - np.roll(hull, -1, axis=0)).T).sum())
    return float(area + per * buffer_m + np.pi * buffer_m ** 2), 0.0


def _polygon_area(v: tuple[Any, ...]) -> float:
    return float(v[0] / 1e6)


# ---- routes and ground

class _Ring:
    __slots__ = ("pts", "a", "b")

    def __init__(self, pts: np.ndarray[Any, Any]):
        self.pts, self.a, self.b = pts, pts[:-1], pts[1:]


def _inside(point: np.ndarray[Any, Any], rings: list[_Ring]) -> bool:
    """Even-odd test of a point against the rings of a polygon (shell and holes)."""
    x, y = point
    inside = False
    for r in rings:
        (x1, y1), (x2, y2) = r.a.T, r.b.T
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= bool(((x < xi) & cond).sum() % 2)
    return inside


def _length_inside(line: np.ndarray[Any, Any], rings: list[_Ring]) -> float:
    """Planar length of a polyline inside a polygon with holes."""
    total = 0.0
    allp = np.vstack([r.pts for r in rings])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    for p, q in zip(line[:-1], line[1:]):
        if max(p[0], q[0]) < lo[0] or min(p[0], q[0]) > hi[0] or max(p[1], q[1]) < lo[1] or min(p[1], q[1]) > hi[1]:
            continue
        d = q - p
        seg = float(np.hypot(*d))
        if seg == 0:
            continue
        ts = [0.0, 1.0]
        for r in rings:
            e = r.b - r.a
            den = d[0] * e[:, 1] - d[1] * e[:, 0]
            ok = np.abs(den) > 1e-12
            w = r.a - p
            t = np.where(ok, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / np.where(ok, den, 1.0), -1.0)
            u = np.where(ok, (w[:, 0] * d[1] - w[:, 1] * d[0]) / np.where(ok, den, 1.0), -1.0)
            ts += list(t[ok & (t > 0) & (t < 1) & (u >= 0) & (u <= 1)])
        ts = sorted(ts)
        for t0, t1 in zip(ts[:-1], ts[1:]):
            if t1 - t0 > 1e-12 and _inside(p + d * (t0 + t1) / 2, rings):
                total += (t1 - t0) * seg
    return total


@staged(sources=("gis.project_area.prj_key", "gis.project_area.version", "gis.project_area.kind", "gis.project_area.geom", "gis.ground_condition.area_id", "gis.ground_condition.geom",
                 "gis.ground_condition.soil_class", "gis.ground_condition.groundwater", "gis.ground_condition.bearing_capacity", "gis.ground_condition.survey_kind"),
        oracle="py:tests/test_gis.py::test_ground_conditions")
def route_ground_intersection(project_area: pd.DataFrame, ground_condition: pd.DataFrame, *, kind: str = "planned_route", min_metres: float = 0.05) -> pd.DataFrame:
    """Use this when you need the metres of each route that lie inside each ground polygon, with the soil class and the shares of the route.

    One row per route version and polygon that it crosses (RouteSoilShare), planar in the metres of the WKT. `kind` picks planned_route (default) or as_built_route. A crossing shorter than `min_metres`
    (PROPOSED 0.05 m: tiny planar float slivers appear where a route touches a polygon edge) is not a crossing. Polygons add up as the generator does: they overlap by less than 5 square metres.

    Args:
        project_area: The gis.project_area table; it needs the columns prj_key, version, kind and geom (WKT LINESTRING for the routes).
        ground_condition: The gis.ground_condition table; it needs the columns area_id, geom (WKT POLYGON), soil_class, groundwater, bearing_capacity and survey_kind.
        kind: The route kind to use, planned_route (default) or as_built_route.
        min_metres: Smallest crossing length in metres that counts (PROPOSED 0.05); zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame sorted by prj_key, version and area_id with the columns prj_key, version, kind, area_id, soil_class, groundwater, bearing_capacity, survey_kind, metres, route_length_m, covered_m (metres of the
        route inside any polygon), share_of_covered (metres over covered metres, as the generator) and share_of_route (metres over the route length). It is empty when no route crosses a polygon.

    Raises:
        FrameError: a table lacks a needed column; kind is not planned_route or as_built_route; min_metres is not a number of zero or more; gis.ground_condition has more than one row for an area_id;
            gis.project_area has more than one row for a project and version of this kind; a ground polygon is not a closed POLYGON or a route is not a LINESTRING; a geometry is not readable WKT.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import route_ground_intersection
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pa = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [1], "kind": ["planned_route"], "geom": ["LINESTRING (0 5, 100 5)"]})
        >>> gc = pd.DataFrame({"area_id": ["GC-900001"], "geom": ["POLYGON ((0 0, 40 0, 40 10, 0 10, 0 0))"], "soil_class": ["clay"], "groundwater": ["low"],
        ...                    "bearing_capacity": ["good"], "survey_kind": ["survey"]})
        >>> out = route_ground_intersection(pa, gc, context=ctx)
        >>> out[["metres", "route_length_m", "share_of_route"]].to_dict("records")
        [{'metres': 40.0, 'route_length_m': 100.0, 'share_of_route': 0.4}]
    """
    _need(project_area, ["prj_key", "version", "kind", "geom"], "gis.project_area")
    _need(ground_condition, ["area_id", "geom", "soil_class", "groundwater", "bearing_capacity", "survey_kind"], "gis.ground_condition")
    if kind not in ("planned_route", "as_built_route"):
        raise FrameError(f"kind is planned_route or as_built_route (got {value_text(kind)})")
    if isinstance(min_metres, bool) or not isinstance(min_metres, (int, float)) or not min_metres >= 0:
        raise FrameError(f"min_metres must be a number of metres, zero or more (got {value_text(min_metres)})")
    if ground_condition["area_id"].duplicated().any():
        raise FrameError("gis.ground_condition has more than one row for an area_id")
    routes = project_area[project_area["kind"] == kind]
    if routes[["prj_key", "version"]].duplicated().any():
        raise FrameError("gis.project_area has more than one row for a project and version of this kind")
    polys = []
    for r in ground_condition.itertuples():
        k, rings = _parse(r.geom)
        if k != "POLYGON":
            raise FrameError(f"ground condition {r.area_id} is not a POLYGON")
        rr = [_Ring(x) for x in rings]
        allp = np.vstack(rings)
        polys.append((rr, allp.min(axis=0), allp.max(axis=0)))
    rows = []
    for r in routes.itertuples():
        k, parts = _parse(r.geom)
        if k != "LINESTRING":
            raise FrameError(f"route {r.prj_key} is not a LINESTRING")
        line = parts[0]
        length = float(np.hypot(*np.diff(line, axis=0).T).sum())
        lo, hi = line.min(axis=0), line.max(axis=0)
        for i, (rr, plo, phi) in enumerate(polys):
            if hi[0] < plo[0] or lo[0] > phi[0] or hi[1] < plo[1] or lo[1] > phi[1]:
                continue
            m = _length_inside(line, rr)
            if m > min_metres:
                g = ground_condition.iloc[i]
                rows.append({"prj_key": r.prj_key, "version": r.version, "kind": kind, "area_id": g["area_id"], "soil_class": g["soil_class"], "groundwater": g["groundwater"],
                             "bearing_capacity": g["bearing_capacity"], "survey_kind": g["survey_kind"], "metres": m, "route_length_m": length})
    cols = ["prj_key", "version", "kind", "area_id", "soil_class", "groundwater", "bearing_capacity", "survey_kind", "metres", "route_length_m", "covered_m", "share_of_covered", "share_of_route"]
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows)
    out["covered_m"] = out.groupby(["prj_key", "version"])["metres"].transform("sum")
    out["share_of_covered"] = out["metres"] / out["covered_m"]
    out["share_of_route"] = (out["metres"] / out["route_length_m"]).clip(upper=1.0)
    out[["metres", "route_length_m", "covered_m"]] = out[["metres", "route_length_m", "covered_m"]].round(3)
    out[["share_of_covered", "share_of_route"]] = out[["share_of_covered", "share_of_route"]].round(6)
    return out[cols].sort_values(["prj_key", "version", "area_id"]).reset_index(drop=True)


@staged(sources=("gis.project_area.prj_key", "gis.ground_condition.soil_class"), oracle="py:tests/test_gis.py::test_ground_conditions")
def majority_soil(route_shares: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the soil class with the most metres on each route version, from the output of route_ground_intersection.

    The soil class with most metres per route version and its share of the covered metres (the generator's rule: ties go to the class name that sorts first).

    Args:
        route_shares: The output of route_ground_intersection; it needs the columns prj_key, version, soil_class, metres and route_length_m.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with one row per route version and the columns prj_key, version, soil_class, share (of covered metres), share_of_route and covered_share_of_route (covered metres over the route length). It is
        empty when route_shares is empty.

    Raises:
        FrameError: route_shares lacks a needed column.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import majority_soil
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rs = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "version": [1, 1], "soil_class": ["clay", "sand"], "metres": [30.0, 10.0], "route_length_m": [100.0, 100.0]})
        >>> out = majority_soil(rs, context=ctx)
        >>> out[["soil_class", "share", "share_of_route", "covered_share_of_route"]].to_dict("records")
        [{'soil_class': 'clay', 'share': 0.75, 'share_of_route': 0.3, 'covered_share_of_route': 0.4}]
    """
    _need(route_shares, ["prj_key", "version", "soil_class", "metres", "route_length_m"], "route_ground_intersection output")
    if route_shares.empty:
        return pd.DataFrame(columns=["prj_key", "version", "soil_class", "share", "share_of_route", "covered_share_of_route"])
    g = route_shares.groupby(["prj_key", "version", "soil_class"], as_index=False).agg(metres=("metres", "sum"), route_length_m=("route_length_m", "first"))
    tot = g.groupby(["prj_key", "version"])["metres"].transform("sum")
    g = g.assign(covered=tot).sort_values(["prj_key", "version", "metres", "soil_class"], ascending=[True, True, False, True]).drop_duplicates(["prj_key", "version"])
    return pd.DataFrame({"prj_key": g["prj_key"], "version": g["version"], "soil_class": g["soil_class"], "share": (g["metres"] / g["covered"]).round(6), "share_of_route": (g["metres"] / g["route_length_m"]).round(6),
                         "covered_share_of_route": (g["covered"] / g["route_length_m"]).clip(upper=1.0).round(6)}).reset_index(drop=True)


@staged(sources=("gis.ground_condition.bearing_capacity", "gis.ground_condition.groundwater", "gis.ground_condition.survey_kind"))
def route_conditions_summary(route_shares: pd.DataFrame, *, poor_bearing: tuple[str, ...] = ("poor",), high_groundwater: tuple[str, ...] = ("high",)) -> pd.DataFrame:
    """Use this when you need to know how much of each route lies on poor bearing capacity or high groundwater and whether it crosses a polygon recorded on site.

    Share of each route on poor bearing capacity and on high groundwater (of the route length) and whether it crosses either, and a polygon recorded on site. `poor_bearing` and `high_groundwater` are the PROPOSED
    values of the two attributes.

    Args:
        route_shares: The output of route_ground_intersection; it needs the columns prj_key, version, metres, route_length_m, bearing_capacity, groundwater and survey_kind.
        poor_bearing: The bearing_capacity values that count as poor (PROPOSED ("poor",)); a tuple or list, not a plain string.
        high_groundwater: The groundwater values that count as high (PROPOSED ("high",)); a tuple or list, not a plain string.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with one row per route version and the columns prj_key, version, poor_bearing_m, poor_bearing_share, high_groundwater_m, high_groundwater_share (both of the route length),
        crosses_poor_bearing, crosses_high_groundwater and crosses_site_observation (polygons whose survey_kind says they were recorded on site, not by a borehole survey). It is empty when route_shares is empty.

    Raises:
        FrameError: route_shares lacks a needed column; poor_bearing or high_groundwater is not a tuple or list of values.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import route_conditions_summary
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rs = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "version": [1, 1], "metres": [20.0, 30.0], "route_length_m": [100.0, 100.0],
        ...                    "bearing_capacity": ["poor", "good"], "groundwater": ["low", "high"], "survey_kind": ["survey", "survey"]})
        >>> out = route_conditions_summary(rs, context=ctx)
        >>> out[["poor_bearing_share", "high_groundwater_share", "crosses_site_observation"]].to_dict("records")
        [{'poor_bearing_share': 0.2, 'high_groundwater_share': 0.3, 'crosses_site_observation': False}]
    """
    _need(route_shares, ["prj_key", "version", "metres", "route_length_m", "bearing_capacity", "groundwater", "survey_kind"], "route_ground_intersection output")
    cols = ["prj_key", "version", "poor_bearing_m", "poor_bearing_share", "high_groundwater_m", "high_groundwater_share", "crosses_poor_bearing", "crosses_high_groundwater", "crosses_site_observation"]
    if route_shares.empty:
        return pd.DataFrame(columns=cols)
    x = route_shares.assign(pb=route_shares["bearing_capacity"].isin(_seq(poor_bearing, "poor_bearing")), hw=route_shares["groundwater"].isin(_seq(high_groundwater, "high_groundwater")), sf=route_shares["survey_kind"] == _ON_SITE)
    g: pd.DataFrame = x.groupby(["prj_key", "version"], as_index=False).apply(lambda d: pd.Series({  # type: ignore[call-overload]  # pandas-stubs: groupby.apply lacks include_groups
        "poor_bearing_m": d.loc[d["pb"], "metres"].sum(), "high_groundwater_m": d.loc[d["hw"], "metres"].sum(), "route_length_m": d["route_length_m"].iloc[0],
        "crosses_poor_bearing": bool(d["pb"].any()), "crosses_high_groundwater": bool(d["hw"].any()), "crosses_site_observation": bool(d["sf"].any())}), include_groups=False)
    g["poor_bearing_share"] = (g["poor_bearing_m"] / g["route_length_m"]).clip(upper=1.0).round(6)
    g["high_groundwater_share"] = (g["high_groundwater_m"] / g["route_length_m"]).clip(upper=1.0).round(6)
    g[["poor_bearing_m", "high_groundwater_m"]] = g[["poor_bearing_m", "high_groundwater_m"]].round(3)
    return g[cols].reset_index(drop=True)
