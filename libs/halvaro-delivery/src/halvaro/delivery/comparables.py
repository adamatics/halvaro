"""Comparable projects: the named profiles of the comparable rule, the set of a profile on a date, variants of the rule and what data the set has (plan 5.2).

PROPOSED: policy.delivery.comparable_rule is needed and has no fact per value. The profile table below is the plan's recommended default (halvaro-delivery.md 4.4): the route window
literal is hard coded in the generator in five files (3.4), so the library holds it once, here, and the tests tie it to the generator truth.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, NamedTuple, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from .projects import _day, _days, _need, _status

_KB = ("DA.REF.212",)
_FILTERS = ("country", "type", "soil_class", "status", "route_min_m", "route_max_m", "start_from", "end_from")
_NUMERIC = ("route_min_m", "route_max_m")
_TEXT = ("country", "type", "soil_class", "status")
_DATES = ("start_from", "end_from")
_STATUSES = ("planned", "active", "completed")
_REQUIRED = ("prj_key", "country", "type", "soil_class", "route_length_m", "legacy", "data_depth", "start", "actual_end")

PROFILES: dict[str, dict[str, Any]] = {                        # PROPOSED, plan 4.4. status is the status on the as_of date from the dates (project_status_on), not the stored column.
    "de_clay_window": {"country": "DE", "type": "dh_network", "soil_class": "clay", "status": "completed", "route_min_m": 4000, "route_max_m": 7500},
    "cell_de_dh_clay": {"country": "DE", "type": "dh_network", "soil_class": "clay", "status": "completed"},
    "dk_dh_recent": {"country": "DK", "type": "dh_network", "status": "completed", "start_from": "2023-01-01", "end_from": "2024-01-01"},
}
# Profiles whose rule is a route window need the length. The cell profile does not; esg switches require_route_length on.
_NEEDS_LENGTH = ("route_min_m", "route_max_m")


class ComparableSet(NamedTuple):
    """Result of comparable_set: the frame sorted by prj_key, the rule that was applied, the projects dropped per reason (in the order the filters ran) and the profile name when one was used."""

    frame: pd.DataFrame
    rule: dict[str, Any]
    dropped: dict[str, Any]
    profile: str | None = None      # the profile name when a named profile (or a profile_rules() row) was used, else None


def _exclude(exclude: Any) -> list[str]:
    if exclude is None:
        return []
    if isinstance(exclude, str):
        return [exclude]
    if not isinstance(exclude, (list, tuple, set, frozenset, pd.Series, pd.Index, np.ndarray, pd.api.extensions.ExtensionArray)):
        raise FrameError(f"exclude must be a list of prj_key values, not {type(exclude).__name__}")
    return list(exclude)


def _project_in(project: pd.DataFrame) -> pd.DataFrame:
    """Checks the project frame; an empty or all-null route_length_m without a dtype counts as numeric (empty), a text one is refused. Returns the frame (a copy only when the column was recast)."""
    _need(project, list(_REQUIRED))
    _plain(project, "projects.project")
    col = project["route_length_m"]
    if not pd.api.types.is_numeric_dtype(col):
        if len(col) == 0 or col.isna().all():
            return project.assign(route_length_m=col.astype(float))
        raise FrameError("projects.project.route_length_m must be numeric")
    return project


def _plain(frame: pd.DataFrame, name: str) -> None:
    clash = [n for n in frame.index.names if n is not None and n in frame.columns]
    if clash:
        raise FrameError(f"{name} has an index named {clash[0]!r} and a column of the same name; reset the index (drop=True) first")


def _rule(profile: str | Mapping[str, Any], overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(profile, Mapping):
        base = dict(profile)
    else:
        if profile not in PROFILES:
            raise FrameError(f"unknown comparable profile {profile!r}; known: {', '.join(PROFILES)}")
        base = dict(PROFILES[profile])
    if overrides is not None and not isinstance(overrides, Mapping):
        raise FrameError("overrides must be a mapping of filter fields")
    base.update(overrides or {})
    require = bool(base.pop("require_route_length", False))
    base.pop("profile", None), base.pop("rule_status", None)      # the label columns of a profile_rules() row
    base = {k: v for k, v in base.items() if not (v is None or (isinstance(v, float) and np.isnan(v)))}      # an unset field of profile_rules() is no filter
    bad = sorted(set(base) - set(_FILTERS))
    if bad:
        raise FrameError(f"unknown filter field(s) {', '.join(bad)} in a comparable rule; allowed: {', '.join(_FILTERS)}, require_route_length")
    for k in _NUMERIC:
        if k in base and (isinstance(base[k], (bool, np.bool_)) or not isinstance(base[k], (int, float, np.integer, np.floating))):
            raise FrameError(f"{k} must be a number of metres, not {base[k]!r}")
    for k in _TEXT:
        if k in base and not isinstance(base[k], str):
            if k == "status" and isinstance(base[k], (list, tuple, set, frozenset)) and len(base[k]) and all(isinstance(v, str) for v in base[k]):
                base[k] = sorted(set(base[k]))      # several statuses: set membership
            else:
                raise FrameError(f"{k} must be one text value{' or a non-empty list of texts' if k == 'status' else ''}, not {base[k]!r}")
    if "status" in base:
        bad_status = sorted(set([base["status"]] if isinstance(base["status"], str) else base["status"]) - set(_STATUSES))
        if bad_status:
            raise FrameError(f"unknown status {', '.join(map(repr, bad_status))} in a comparable rule; allowed: {', '.join(_STATUSES)}")
    for k in _DATES:
        if k in base:
            if not isinstance(base[k], (str, dt.date, pd.Timestamp)):
                raise FrameError(f"{k} must be a date or an ISO text, not {base[k]!r}")
            try:
                pd.Timestamp(base[k])
            except (ValueError, TypeError) as e:
                raise FrameError(f"{k} {base[k]!r} is not a date: {e}") from None
    if "route_min_m" in base and "route_max_m" in base and base["route_min_m"] > base["route_max_m"]:
        raise FrameError("route_min_m is above route_max_m")
    if require:
        base["require_route_length"] = True
    return base


def _apply(project: pd.DataFrame, rule: dict[str, Any], d: pd.Timestamp, exclude: Sequence[str], require_route_length: bool) -> tuple[Any, ...]:
    p = project.copy()
    start, end = _days(project["start"], "start"), _days(project["actual_end"], "actual_end")
    keep = pd.Series(True, index=p.index)
    dropped: dict[str, Any] = {}

    def step(name: str, ok: pd.Series) -> None:
        nonlocal keep
        gone = int((keep & ~ok).sum())
        if gone:
            dropped[name] = dropped.get(name, 0) + gone
        keep = keep & ok

    for col in ("country", "type", "soil_class"):
        if col in rule:
            step(col, p[col] == rule[col])
    if "status" in rule or "start_from" in rule:      # a status or a start window needs a start date; a project without one is counted, and a null start of a project another filter removed does not matter
        step("no_start_date", start.notna())
    if "status" in rule:
        st = pd.Series("", index=p.index, dtype=object)
        if keep.any():
            st[keep] = _status(project[keep], d)["status"].to_numpy()
        step("status", st.isin([rule["status"]] if isinstance(rule["status"], str) else list(rule["status"])))
    needs_length = require_route_length or rule.get("require_route_length", False) or any(k in rule for k in _NEEDS_LENGTH)
    if needs_length:
        step("no_route_length", p["route_length_m"].notna())
    if "route_min_m" in rule:        # a window implies needs_length, so the nulls are gone
        step("route_window", p["route_length_m"] >= rule["route_min_m"])
    if "route_max_m" in rule:
        step("route_window", p["route_length_m"] <= rule["route_max_m"])
    if "start_from" in rule:
        step("start_before_window", start >= pd.Timestamp(rule["start_from"]))
    if "end_from" in rule:
        step("end_before_window", end >= pd.Timestamp(rule["end_from"]))
    if exclude:
        step("excluded", ~p["prj_key"].isin(list(exclude)))
    return p[keep], dropped


@staged(sources=("projects.project.prj_key",), kb=_KB, oracle="py:tests/test_projects.py::test_six_comparables")
def profile_rules() -> pd.DataFrame:
    """Use this when you need the named profiles of the comparable rule as a table, to see which filters each profile applies.

    One row per profile with the filter fields (null where the profile does not filter), require_route_length (False: only a profile with a route window needs the length) and status proposed (policy.delivery.comparable_rule is needed).

    Args:
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per profile and the columns profile, country, type, soil_class, status, route_min_m, route_max_m, start_from, end_from, require_route_length and rule_status ("proposed").

    Raises:
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import profile_rules
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rules = profile_rules(context=ctx)
        >>> "de_clay_window" in rules["profile"].tolist()
        True
        >>> set(rules["rule_status"])
        {'proposed'}"""
    rows = []
    for name, r in PROFILES.items():
        rows.append({"profile": name, **{k: r.get(k) for k in _FILTERS}, "require_route_length": False, "rule_status": "proposed"})
    return pd.DataFrame(rows, columns=["profile", *_FILTERS, "require_route_length", "rule_status"])


@staged(sources=("projects.project.prj_key", "projects.project.country", "projects.project.type", "projects.project.soil_class", "projects.project.route_length_m",
                 "projects.project.legacy", "projects.project.data_depth", "projects.project.start", "projects.project.actual_end"),
        kb=_KB, oracle="py:tests/test_projects.py::test_six_comparables")
def comparable_set(project: pd.DataFrame, profile: str | Mapping[str, Any] = "de_clay_window", *, exclude: Sequence[str] = (), require_route_length: bool = False,
                   as_of: dt.date | None = None, overrides: Mapping[str, Any] | None = None) -> ComparableSet:
    """Use this when you need the comparable projects of a named profile (or your own rule) on a date, with a count of what each filter removed.

    Returns the projects of a profile on a date (default: the release date world.now), sorted by prj_key. Status is computed from the dates on the date. A null route length stays in the set with route_known false, unless the rule has a route window
    or require_route_length is on (then the project is dropped as no_route_length). `dropped` counts the projects each filter removed, in the order country, type, soil_class, no_start_date, status, no_route_length, route_window, start_before_window,
    end_before_window, excluded; nothing is dropped without a count. A project without a start date has no status and no start window: it is dropped as no_start_date when the rule has a status or start_from (after the country, type and soil filters,
    so a null start of a project outside the cell does not matter), and kept when the rule has neither. The profile table is PROPOSED (policy.delivery.comparable_rule is needed).

    Args:
        project: The projects.project frame, one row per prj_key; it needs prj_key, country, type, soil_class, route_length_m (numeric), legacy, data_depth, start and actual_end.
        profile: A name of PROFILES (see profile_rules) or a mapping of filter fields (country, type, soil_class, status, route_min_m, route_max_m, start_from, end_from, require_route_length). A rule status is one text or a list of texts (planned, active, completed).
        exclude: Project keys to leave out (for example the project under review); one key as text is accepted.
        require_route_length: True drops the projects without a route length as no_route_length.
        as_of: The date on which the status is computed; None means the release date (fact world.now).
        overrides: A mapping of filter fields that replaces single fields of the profile.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ComparableSet: frame (prj_key, route_length_m, legacy, data_depth, route_known; sorted by prj_key), rule (the rule applied, with require_route_length and as_of as an ISO text), dropped (the count each filter removed, in the order they ran) and profile (the profile name used; None for a mapping without one).

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names, lacks a needed column, has an index named like a column or a text route_length_m; a prj_key is null or repeated; a project has no start date where the rule needs one and its status cannot be computed; a date column is unreadable; profile is neither a known name nor a mapping; exclude is not a list of keys; the rule has an unknown field, a non-numeric route bound, a non-text value, an unknown status, a date that is not a date, or route_min_m above route_max_m; overrides is not a mapping.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import comparable_set
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "country": ["DE", "DE", "DK"],
        ...                     "type": ["dh_network"] * 3, "soil_class": ["clay"] * 3, "route_length_m": [5000.0, 9000.0, 5000.0],
        ...                     "legacy": [False, False, True], "data_depth": ["full", "full", "summary"],
        ...                     "start": ["2029-01-01"] * 3, "actual_end": ["2029-06-01"] * 3})
        >>> res = comparable_set(prj, "de_clay_window", as_of="2030-01-01", context=ctx)
        >>> res.frame["prj_key"].tolist()
        ['PRJ-900001']
        >>> res.dropped
        {'country': 1, 'route_window': 1}
        >>> res.profile
        'de_clay_window'"""
    project = _project_in(project)
    exclude = _exclude(exclude)
    if not isinstance(profile, (str, Mapping)):
        raise FrameError(f"profile must be a profile name or a mapping of filter fields, not {type(profile).__name__}")
    d = _day(as_of if as_of is not None else fact("world.now").value)
    rule = _rule(profile, overrides)
    kept, dropped = _apply(project, rule, d, exclude, bool(require_route_length))
    out = kept[["prj_key", "route_length_m", "legacy", "data_depth"]].copy()
    out["route_known"] = out["route_length_m"].notna()
    out = out.sort_values("prj_key").reset_index(drop=True)
    return ComparableSet(out, {**rule, "require_route_length": bool(require_route_length or rule.get("require_route_length", False)), "as_of": d.date().isoformat()}, dropped,
                         profile if isinstance(profile, str) else (profile.get("profile") if isinstance(profile.get("profile"), str) else None))


@staged(sources=("projects.project.prj_key", "projects.project.country", "projects.project.type", "projects.project.soil_class", "projects.project.route_length_m",
                 "projects.project.legacy", "projects.project.data_depth", "projects.project.start", "projects.project.actual_end"),
        kb=_KB, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def variants_table(project: pd.DataFrame, rules: Mapping[str, Mapping[str, Any]] | None = None, *, metric: pd.DataFrame | None = None, as_of: dt.date | None = None,
                   default: str = "de_clay_window", exclude: Sequence[str] = ()) -> pd.DataFrame:
    """Use this when you need to compare how many projects, how many legacy projects and what metric median each comparable rule gives, the default profile first.

    One row per rule, the default profile first: n projects, legacy count and share, and, when a metric frame (prj_key, value) is passed, metric_n (projects with a value), metric_missing (without one) and metric_median.
    `rules` maps a name to a rule (filter fields as in a profile); when it is None every named profile is listed. An override rule of the same name as a profile replaces it. `exclude` removes the project(s) under review from every rule (as in comparable_set).
    A rule may give a project count one above the count of the matching variant in the esg truth; that is not a defect when the extra project is a planned one without a purchase footprint.
    The count 24 of the esg variant dk_all_status_start_2024_on against 23 in the esg truth is such a case (kept because tests/test_comparables.py pins it; review item 8 of #440).

    Args:
        project: The projects.project frame, one row per prj_key; it needs prj_key, country, type, soil_class, route_length_m (numeric), legacy, data_depth, start and actual_end.
        rules: A mapping of rule name to a mapping of filter fields, or None for every named profile.
        metric: A frame with prj_key (one row per project) and a numeric value column, or None for no metric columns.
        as_of: The date on which the status is computed; None means the release date (fact world.now).
        default: The name of the rule listed first; a name of PROFILES or a key of rules.
        exclude: Project keys to leave out of every rule; one key as text is accepted.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per rule, the default first: rule, n, legacy_n, legacy_share (NaN when n is 0) and, with a metric frame, metric_n, metric_missing and metric_median.

    Raises:
        FrameError: project is not a DataFrame, has duplicate column names, lacks a needed column or has a text route_length_m; a prj_key is null or repeated; rules is not a mapping or a rule is not a mapping of valid filter fields (as comparable_set raises); metric is not a DataFrame, lacks prj_key or value, has a non-numeric value or more than one row for a project; default is neither a profile nor a rule; exclude is not a list of keys.
        PeriodError: as_of is a number, is not a date or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import variants_table
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "country": ["DE", "DE", "DK"],
        ...                     "type": ["dh_network"] * 3, "soil_class": ["clay"] * 3, "route_length_m": [5000.0, 6000.0, 5000.0],
        ...                     "legacy": [False, True, False], "data_depth": ["full", "summary", "full"],
        ...                     "start": ["2029-01-01"] * 3, "actual_end": ["2029-06-01"] * 3})
        >>> met = pd.DataFrame({"prj_key": ["PRJ-900001"], "value": [10.0]})
        >>> out = variants_table(prj, {"de_all": {"country": "DE"}}, metric=met, as_of="2030-01-01", default="de_all", context=ctx)
        >>> out[["rule", "n", "legacy_n", "metric_n", "metric_missing"]].to_dict("records")
        [{'rule': 'de_all', 'n': 2, 'legacy_n': 1, 'metric_n': 1, 'metric_missing': 1}]"""
    project = _project_in(project)
    exclude = _exclude(exclude)
    if rules is not None and not isinstance(rules, Mapping):
        raise FrameError("rules is a mapping of rule name to filter fields")
    for k, v in (rules or {}).items():
        if not isinstance(v, Mapping):
            raise FrameError(f"rule {k!r} must be a mapping of filter fields, not {type(v).__name__}")
    if metric is not None and not isinstance(metric, pd.DataFrame):
        raise FrameError("the metric frame must be a DataFrame with prj_key and value")
    if metric is not None:
        miss = [c for c in ("prj_key", "value") if c not in metric.columns]
        if miss:
            raise FrameError(f"the metric frame lacks column(s) {', '.join(miss)}")
        _plain(metric, "the metric frame")
        if not pd.api.types.is_numeric_dtype(metric["value"]):
            raise FrameError("the metric frame's value column must be numeric")
        if metric["prj_key"].duplicated().any():
            raise FrameError("the metric frame has more than one row for a project")
    if default not in PROFILES and default not in (rules or {}):
        raise FrameError(f"unknown default profile {default!r}")
    given: Mapping[str, Mapping[str, Any]] = rules or {}
    allrules = {**{k: dict(v) for k, v in PROFILES.items()}, **{k: dict(v) for k, v in given.items()}} if rules is None else {k: dict(v) for k, v in rules.items()}
    if default not in allrules:
        allrules = {default: dict(PROFILES[default]), **allrules}
    order = [default] + [k for k in allrules if k != default]
    d = _day(as_of if as_of is not None else fact("world.now").value)
    rows = []
    for name in order:
        rule = _rule(allrules[name], None)
        kept, _ = _apply(project, rule, d, exclude, False)
        n = len(kept)
        legacy = int((kept["legacy"] == True).sum())      # noqa: E712  (a null or text value is not legacy)
        row = {"rule": name, "n": n, "legacy_n": legacy, "legacy_share": legacy / n if n else np.nan}
        if metric is not None:
            vals = kept[["prj_key"]].merge(metric[["prj_key", "value"]], on="prj_key", how="left")["value"]
            row.update(metric_n=int(vals.notna().sum()), metric_missing=int(vals.isna().sum()), metric_median=float(vals.median()) if vals.notna().any() else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


@staged(sources=("projects.project.prj_key", "projects.project.final_cost", "projects.project.route_length_m", "projects.estimate_version.prj_key", "projects.estimate_version.type",
                 "projects.project_role.prj_key", "projects.time_entry.prj_key"),
        kb=_KB, oracle="py:tests/test_release.py::test_legacy_projects_are_summary_only")
def comparable_coverage(comparable: pd.DataFrame, project: pd.DataFrame, estimate_version: pd.DataFrame, project_role: pd.DataFrame, time_entry_projects: Sequence[str]) -> pd.DataFrame:
    """Use this when you need to know which data each project of a comparable set has: estimates, final cost, route length, time entries and roster.

    Returns what data each project of a comparable set has: has_estimate (an estimate version exists), has_final_estimate, has_final_cost, has_route_length, has_time_entries (its key is in time_entry_projects: a list of the distinct prj_key of
    projects.time_entry, or the time_entry frame itself, whose prj_key column is used), has_roster (project_role rows) and roster_only (a roster and no time entries).

    Args:
        comparable: The frame of comparable_set (or the ComparableSet itself), with prj_key, one row per project.
        project: The projects.project frame; it needs prj_key, final_cost and route_length_m.
        estimate_version: The projects.estimate_version frame; it needs prj_key and type (the value final marks a final estimate).
        project_role: The projects.project_role frame; it needs prj_key.
        time_entry_projects: A list (or set, array, Index) of the distinct prj_key of projects.time_entry, or the projects.time_entry frame itself; a Series or a groupby is refused.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per project of the set, in its order: prj_key and the booleans has_estimate, has_final_estimate, has_final_cost, has_route_length, has_time_entries, has_roster and roster_only.

    Raises:
        FrameError: comparable is not a DataFrame with prj_key or has a project more than once; time_entry_projects is a frame without prj_key or is not a list of keys or a frame; project lacks a needed column or has a null or repeated prj_key; estimate_version or project_role is not a DataFrame or lacks a needed column; a project of the set is not in the project frame; a frame has an index named like one of its columns.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import comparable_coverage
        >>> ctx = Context(stage="month12", role="analyst")
        >>> comp = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"], "final_cost": [100.0, None], "route_length_m": [5000.0, None]})
        >>> est = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["final"]})
        >>> role = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002"]})
        >>> out = comparable_coverage(comp, prj, est, role, ["PRJ-900001"], context=ctx)
        >>> out["has_final_cost"].tolist(), out["roster_only"].tolist()
        ([True, False], [False, True])"""
    if isinstance(comparable, ComparableSet):
        comparable = comparable.frame
    if not isinstance(comparable, pd.DataFrame) or "prj_key" not in comparable.columns:
        raise FrameError("comparable must be a DataFrame with prj_key (the frame of comparable_set)")
    if comparable["prj_key"].duplicated().any():
        raise FrameError("the comparable frame has a project more than once")
    if isinstance(time_entry_projects, pd.DataFrame):
        if "prj_key" not in time_entry_projects.columns:
            raise FrameError("the time_entry frame lacks column prj_key")
        _plain(time_entry_projects, "projects.time_entry")
        time_entry_projects = time_entry_projects["prj_key"].dropna().unique()
    elif not isinstance(time_entry_projects, (list, tuple, set, frozenset, np.ndarray, pd.Index, pd.api.extensions.ExtensionArray)):
        raise FrameError("time_entry_projects is a list of prj_key values or the projects.time_entry frame (a Series or a groupby is refused; pass .unique() or the frame)")
    _need(project, ["prj_key", "final_cost", "route_length_m"])
    for name, f, cols in (("projects.estimate_version", estimate_version, ["prj_key", "type"]), ("projects.project_role", project_role, ["prj_key"])):
        if not isinstance(f, pd.DataFrame):
            raise FrameError(f"{name} must be a DataFrame")
        miss = [c for c in cols if c not in f.columns]
        if miss:
            raise FrameError(f"{name} frame lacks column(s) {', '.join(miss)}")
    unknown = sorted(set(comparable["prj_key"]) - set(project["prj_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} projects of the set are not in the project frame (for example {unknown[0]})")
    _plain(project, "projects.project")
    _plain(comparable, "the comparable frame")
    p = project.set_index("prj_key")
    keys = comparable["prj_key"]
    est, fin = set(estimate_version["prj_key"]), set(estimate_version.loc[estimate_version["type"] == "final", "prj_key"])
    te, roster = set(time_entry_projects), set(project_role["prj_key"])
    out = pd.DataFrame({"prj_key": keys.to_numpy()})
    out["has_estimate"] = keys.isin(est).to_numpy()
    out["has_final_estimate"] = keys.isin(fin).to_numpy()
    out["has_final_cost"] = keys.map(p["final_cost"]).notna().to_numpy()
    out["has_route_length"] = keys.map(p["route_length_m"]).notna().to_numpy()
    out["has_time_entries"] = keys.isin(te).to_numpy()
    out["has_roster"] = keys.isin(roster).to_numpy()
    out["roster_only"] = out["has_roster"] & ~out["has_time_entries"]
    return out
