"""Answers assembled from the outputs of the other grid modules (plan 5.8): the winter peak answer (capacity, series, faults, quality), the grid side of the supply strain answer (strained elements, zones, customers, part use) and the route facts of a tender comparison.

A recipe computes nothing new. It checks that the pieces it is given have the columns it needs, keeps the gaps of the data in the answer, carries the label "synthetic data" and refuses anything that looks like
money, stock or intent. The two key lists for the supply answer of halvaro-delivery hold keys only.
"""
from __future__ import annotations

import re
from typing import Any, NamedTuple, Sequence

import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need
from .spatial import FaultCluster

LABEL = "synthetic data"
_FORBIDDEN = ("stock", "po", "order", "orders", "price", "cost", "amount", "money", "credit", "intent")           # words of a column name (split at _) that must not enter the delivery key lists


class WinterPeakAnswer(NamedTuple):
    """The pieces of the answer to the winter peak question: zone ranking, the peak week profile, supply and outdoor temperature at the peak, fault density, the cluster, the list of data gaps and the labels."""
    ranking: pd.DataFrame
    peak_profile: pd.DataFrame
    temperatures: pd.DataFrame
    fault_density: pd.DataFrame
    clusters: tuple[Any, ...]
    gaps: pd.DataFrame
    labels: tuple[Any, ...]


class GridStrainAnswer(NamedTuple):
    """Strained elements and their summaries, part use, and the two key lists for the supply answer of halvaro-delivery: the critical items (`itm_key`) and the zones (`zone_key`)."""
    strained: pd.DataFrame
    zone_summary: pd.DataFrame
    part_use: pd.DataFrame
    item_keys: tuple[Any, ...]
    zone_keys: tuple[Any, ...]
    labels: tuple[Any, ...]


class RouteFacts(NamedTuple):
    """Route length, versions, soil shares and flags per project. `summary_projects` are projects without a route version (marked summary, never given a route)."""
    routes: pd.DataFrame
    soil: pd.DataFrame
    summary_projects: tuple[Any, ...]
    labels: tuple[Any, ...]


def _frame(x: Any, cols: Any, what: Any) -> Any:
    _need(x, cols, what)
    return x


@staged(sources=("telemetry.sensor.sns_key", "gis.supply_zone.zone_key", "service.fault_event.net_key", "telemetry.data_quality_event.sns_key"))
def winter_peak_answer(ranking: pd.DataFrame, peak_profile: pd.DataFrame, temperatures: pd.DataFrame, density: pd.DataFrame, clusters: Sequence[FaultCluster], gaps: pd.DataFrame) -> WinterPeakAnswer:
    """Use this when you need the pieces of the winter peak answer (zone ranking, peak week profile, temperatures, fault density, clusters and data gaps) checked and assembled in one result.

    Assemble the winter peak answer from `rank_zones`, a peak week profile, the peak load frame with `outdoor_c` and `supply_temp_c`, `fault_density`, the clusters of `fault_clusters` or `age_group_clusters` (a list or a frame, may be empty) and `gap_report`.
    Nothing new is computed: the pieces are checked for their columns and kept as they are. Gaps are listed, not dropped: an empty gap frame is returned as it is, never filled. The label 'synthetic data' is always part of the answer.

    Args:
        ranking: The output of rank_zones; it needs the columns zone_key, rank, peak_percent and valid.
        peak_profile: The peak week profile with the columns zone_key, ts, load_percent or similar; at least one row.
        temperatures: The peak load frame with the columns outdoor_c and supply_temp_c.
        density: The output of fault_density; it needs the columns net_key and n_faults.
        clusters: The clusters of fault_clusters or age_group_clusters, a list, a tuple or a frame; may be empty.
        gaps: The output of gap_report; it needs the column sns_key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An WinterPeakAnswer with the fields ranking, peak_profile, temperatures, fault_density, clusters (a tuple), gaps and labels (the tuple holding 'synthetic data'); the frames are given back with a fresh index.

    Raises:
        FrameError: a piece is not a frame or lacks a needed column; the peak week profile has no rows; the ranking has no ranked zone, because the answer would have no first place; clusters is not a list, a tuple or a frame.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import winter_peak_answer
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rk = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0002"], "rank": [1, 2], "peak_percent": [90.0, 80.0], "valid": [True, True]})
        >>> pp = pd.DataFrame({"zone_key": ["ZONE-0001"], "ts": ["2020-01-06 00:00"], "load_percent": [88.0]})
        >>> tp = pd.DataFrame({"outdoor_c": [-3.0], "supply_temp_c": [70.0]})
        >>> dn = pd.DataFrame({"net_key": ["NET-900001"], "n_faults": [2]})
        >>> gp = pd.DataFrame({"sns_key": []})
        >>> a = winter_peak_answer(rk, pp, tp, dn, [], gp, context=ctx)
        >>> a.labels, a.clusters, len(a.gaps)
        (('synthetic data',), (), 0)
"""
    _frame(ranking, ["zone_key", "rank", "peak_percent", "valid"], "the zone ranking")
    _frame(temperatures, ["outdoor_c", "supply_temp_c"], "the peak load frame with temperatures")
    _frame(density, ["net_key", "n_faults"], "the fault density")
    _frame(gaps, ["sns_key"], "the gap report")
    if not isinstance(peak_profile, pd.DataFrame) or len(peak_profile) == 0:
        raise FrameError("the peak week profile has no rows")
    if ranking["rank"].notna().sum() == 0:
        raise FrameError("the ranking has no ranked zone")
    if not isinstance(clusters, (list, tuple, pd.DataFrame)):
        raise FrameError(f"clusters must be a list, a tuple or a frame (got {type(clusters).__name__})")
    return WinterPeakAnswer(ranking.reset_index(drop=True), peak_profile.reset_index(drop=True), temperatures.reset_index(drop=True), density.reset_index(drop=True), tuple(clusters) if not isinstance(clusters, pd.DataFrame) else tuple(clusters.itertuples(index=False)), gaps.reset_index(drop=True), (LABEL,))


@staged(sources=("gis.grid_element.net_key", "gis.supply_zone.zone_key", "service.ticket_item_use.itm_key", "inventory.item.critical"), oracle="py:tests/test_oracle_recipes.py::test_oracle_grid_strain_answer_hand_worked_pieces_and_key_lists")
def grid_strain_answer(strained: pd.DataFrame, zone_summary: pd.DataFrame, part_use: pd.DataFrame, critical_issued: pd.DataFrame) -> GridStrainAnswer:
    """Use this when you need the grid side of the supply strain answer (strained elements, zone summary, part use) with the two key lists for the delivery answer.

    Assemble the grid side of the supply strain answer: the strained elements (`strained_elements`), the zone summary (`zone_strain_summary`), the part use (`part_usage`), and the two key lists for the supply answer of halvaro-delivery: the critical items
    that were issued (`itm_key` of `critical_spares_issued` with units above zero, sorted) and the zones of the summary (`zone_key`, sorted). The lists hold keys only. A critical item that was never issued is
    not asked about. Elements whose strain is unknown stay unknown in `strained`. Nothing new is computed; the label 'synthetic data' is part of the answer.

    Args:
        strained: The output of strained_elements; it needs the columns net_key, strained and load_strained.
        zone_summary: The output of zone_strain_summary; it needs the columns zone_key, n_elements and n_strained.
        part_use: The output of part_usage; it needs the columns itm_key and units.
        critical_issued: The output of critical_spares_issued; it needs the columns itm_key and units.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An GridStrainAnswer with the fields strained, zone_summary, part_use (frames with a fresh index), item_keys (sorted tuple of itm_key of the critical items with units above zero), zone_keys (sorted tuple of the zones of the summary) and labels (the tuple holding 'synthetic data').

    Raises:
        FrameError: a piece is not a frame or lacks a needed column; a column name of the four frames contains the word stock, po, order, orders, price, cost, amount, money, credit or intent (split at underscores), so the delivery side never receives it from here; a null itm_key or zone_key.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import grid_strain_answer
        >>> ctx = Context(stage="month12", role="analyst")
        >>> st = pd.DataFrame({"net_key": ["NET-900001"], "strained": [True], "load_strained": [True]})
        >>> zs = pd.DataFrame({"zone_key": ["ZONE-0002", "ZONE-0001"], "n_elements": [3, 2], "n_strained": [1, 0]})
        >>> pu = pd.DataFrame({"itm_key": ["ITM-900001"], "units": [4]})
        >>> ci = pd.DataFrame({"itm_key": ["ITM-900002", "ITM-900001", "ITM-900003"], "units": [2, 5, 0]})
        >>> a = grid_strain_answer(st, zs, pu, ci, context=ctx)
        >>> a.item_keys, a.zone_keys
        (('ITM-900001', 'ITM-900002'), ('ZONE-0001', 'ZONE-0002'))
"""
    _frame(strained, ["net_key", "strained", "load_strained"], "the strained elements")
    _frame(zone_summary, ["zone_key", "n_elements", "n_strained"], "the zone strain summary")
    _frame(part_use, ["itm_key", "units"], "the part use")
    _frame(critical_issued, ["itm_key", "units"], "the critical spares frame")
    _split = lambda c: set(re.split(r"[_\-\s]+|(?<=[a-z])(?=[A-Z])", str(c)))                                  # noqa: E731
    bad = [f"{n}.{c}" for n, fr in (("critical_issued", critical_issued), ("zone_summary", zone_summary), ("part_use", part_use), ("strained", strained)) for c in fr.columns
           if {w.lower() for w in _split(c)} & set(_FORBIDDEN)]
    if bad:
        raise FrameError(f"column(s) {', '.join(bad)} do not belong in an answer that feeds a list of keys (stock, order, price, cost, intent)")
    if critical_issued["itm_key"].isna().any() or zone_summary["zone_key"].isna().any():
        raise FrameError("a null itm_key or zone_key cannot go in a list of keys")
    items = tuple(sorted(set(critical_issued.loc[critical_issued["units"] > 0, "itm_key"].astype(str))))
    zones = tuple(sorted(set(zone_summary["zone_key"].astype(str))))
    return GridStrainAnswer(strained.reset_index(drop=True), zone_summary.reset_index(drop=True), part_use.reset_index(drop=True), items, zones, (LABEL,))


@staged(sources=("gis.project_area.prj_key", "gis.project_area.length_m", "gis.ground_condition.soil_class", "projects.project.prj_key"), oracle="py:tests/test_gis.py::test_ground_conditions")
def route_facts(route_change: pd.DataFrame, soil: pd.DataFrame, conditions: pd.DataFrame, projects: pd.DataFrame | None = None, *, planned_version: int = 2) -> RouteFacts:
    """Use this when you need the route length, versions, soil and crossing flags of each project, with the projects that have no route version listed as summary.

    Route length, versions, soil and flags per project, from `route_change` (planned and as-built length, changed), `majority_soil` and `route_conditions_summary` (both per project and version).
    Columns of `routes`: the route_change columns plus, for the planned version, soil_class, soil_share, crosses_poor_bearing, crosses_high_groundwater, crosses_site_observation (when the conditions frame has it). With the projects frame
    (`prj_key`) a project without a route version is listed in `summary_projects` (legacy projects marked summary), never given invented values. Only the soil and condition rows of `planned_version` are used; other versions are not.

    Args:
        route_change: The output of route_change; it needs the columns prj_key, planned_length_m, as_built_length_m, delta_m and changed, one row per project.
        soil: The output of majority_soil; it needs the columns prj_key, version, soil_class and share.
        conditions: The output of route_conditions_summary; it needs the columns prj_key, version, crosses_poor_bearing and crosses_high_groundwater.
        projects: The projects.project table with the column prj_key, or None to list no summary projects.
        planned_version: The version of gis.project_area whose soil and condition rows are used, default 2 (the planned route).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An RouteFacts with the fields routes (one row per project, sorted by prj_key), soil (the soil frame as given, fresh index), summary_projects (sorted tuple of prj_key of the projects without a route version) and labels (the tuple holding 'synthetic data').

    Raises:
        FrameError: a piece lacks a needed column; route_change has more than one row for a project; majority_soil or route_conditions_summary has more than one row for a project and version; soil or conditions rows for a project that route_change does not hold.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import route_facts
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rc = pd.DataFrame({"prj_key": ["PRJ-900001"], "planned_length_m": [100.0], "as_built_length_m": [104.0], "delta_m": [4.0], "changed": [True]})
        >>> so = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [2], "soil_class": ["clay"], "share": [0.6]})
        >>> co = pd.DataFrame({"prj_key": ["PRJ-900001"], "version": [2], "crosses_poor_bearing": [False], "crosses_high_groundwater": [True]})
        >>> pr = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
        >>> f = route_facts(rc, so, co, pr, context=ctx)
        >>> f.routes[["prj_key", "soil_class", "soil_share"]].to_dict("records"), f.summary_projects
        ([{'prj_key': 'PRJ-900001', 'soil_class': 'clay', 'soil_share': 0.6}], ('PRJ-900002',))
"""
    _frame(route_change, ["prj_key", "planned_length_m", "as_built_length_m", "delta_m", "changed"], "route_change")
    _frame(soil, ["prj_key", "version", "soil_class", "share"], "majority_soil")
    _frame(conditions, ["prj_key", "version", "crosses_poor_bearing", "crosses_high_groundwater"], "route_conditions_summary")
    if route_change["prj_key"].duplicated().any():
        raise FrameError("route_change has more than one row for a project")
    pl, cond = soil[soil["version"] == planned_version], conditions[conditions["version"] == planned_version]
    if pl.duplicated("prj_key").any() or cond.duplicated("prj_key").any():
        raise FrameError("majority_soil or route_conditions_summary has more than one row for a project and version")
    stray = sorted((set(pl["prj_key"]) | set(cond["prj_key"])) - set(route_change["prj_key"]))
    if stray:
        raise FrameError(f"soil or conditions for projects that route_change does not hold, for example {stray[0]}")
    r = route_change.merge(pl[["prj_key", "soil_class", "share"]].rename(columns={"share": "soil_share"}), on="prj_key", how="left")
    keep = [c for c in ("prj_key", "crosses_poor_bearing", "crosses_high_groundwater", "crosses_site_observation") if c in cond.columns]
    r = r.merge(cond[keep], on="prj_key", how="left")
    summary: tuple[str, ...] = ()
    if projects is not None:
        _frame(projects, ["prj_key"], "projects.project")
        summary = tuple(sorted(set(projects["prj_key"].astype(str)) - set(route_change["prj_key"].astype(str))))
    return RouteFacts(r.sort_values("prj_key").reset_index(drop=True), soil.reset_index(drop=True), summary, (LABEL,))
