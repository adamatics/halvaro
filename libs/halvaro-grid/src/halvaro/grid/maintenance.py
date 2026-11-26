"""Maintenance plans and planned work (plan 5.7): overdue and due plans, planned tickets resolved late, the inspection interval of the rule.

The grace period is a keyword marked PROPOSED (config/service.yaml planned.grace_days 14; a fact is needed). The inspection cycle per condition class and the type multipliers are the proposed facts policy.grid.inspection_cycle_months.A to E and policy.grid.inspection_type_multiplier.<type>; the keywords cycle_months and type_multiplier override them.
"""
from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from ._util import _need, _utc
from ._types import DateLike
from ._tail import value_text

_CLASSES = ("A", "B", "C", "D", "E")
_TYPES = ("pipe_segment", "valve", "heat_exchanger_station", "cable_section", "transformer_station", "substation", "pump_station")
_FACTS = tuple(f"policy.grid.inspection_cycle_months.{c}" for c in _CLASSES) + tuple(f"policy.grid.inspection_type_multiplier.{t}" for t in _TYPES)


def _rule_cycle() -> dict[str, int]:
    """Months by condition class from the facts policy.grid.inspection_cycle_months.A to E (PROPOSED)."""
    return {c: int(fact(f"policy.grid.inspection_cycle_months.{c}").value) for c in _CLASSES}


def _rule_multiplier() -> dict[str, float]:
    """Factor by element type from the facts policy.grid.inspection_type_multiplier.<type> (PROPOSED)."""
    return {t: float(fact(f"policy.grid.inspection_type_multiplier.{t}").value) for t in _TYPES}
_PLAN = ("service.maintenance_plan.net_key", "service.maintenance_plan.plan_no", "service.maintenance_plan.plan_type", "service.maintenance_plan.next_due", "service.maintenance_plan.last_done",
         "service.maintenance_plan.team_key", "service.maintenance_plan.status")


def _strs(value: Any, name: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise FrameError(f"{name} must be a tuple or list of values, not {value!r}")
    return list(value)


def _day(value: Any, what: str) -> pd.Timestamp:
    d = _utc([value], what).iloc[0]
    if pd.isna(d):
        raise FrameError(f"{what} must be a date (got {value_text(value)})")
    return cast(pd.Timestamp, d.normalize())


def _plans(plan: pd.DataFrame) -> pd.DataFrame:
    _need(plan, ["net_key", "plan_no", "plan_type", "next_due", "last_done", "team_key", "status"], "service.maintenance_plan")
    if plan.duplicated(["net_key", "plan_no"]).any():
        raise FrameError("service.maintenance_plan has more than one row for an element and plan number")
    return plan.assign(next_due=_utc(plan["next_due"], "service.maintenance_plan.next_due").to_numpy(), last_done=_utc(plan["last_done"], "service.maintenance_plan.last_done").to_numpy())


@staged(sources=_PLAN, oracle="py:tests/test_maintenance.py::test_overdue_plans_grace_status_and_missing_dates")
def overdue_plans(maintenance_plan: pd.DataFrame, as_of: DateLike, *, grace_days: int = 14, active_status: tuple[str, ...] = ("active",)) -> pd.DataFrame:
    """Use this when you need the active maintenance plans that are overdue beyond the grace period, with the days overdue.

    Active plans whose next due date is more than `grace_days` (PROPOSED 14, config planned.grace_days) before the as-of date, with the days overdue beyond the grace. A plan without a next due date is not overdue.

    Args:
        maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, next_due, last_done, team_key and status.
        as_of: The as-of date.
        grace_days: Days after the next due date that are still tolerated (PROPOSED 14); a whole number of zero or more.
        active_status: The statuses that count as active (default only "active"); a tuple or list.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns net_key, plan_no, plan_type, team_key, next_due, last_done and days_overdue (beyond the grace), sorted by days_overdue (largest first), net_key and plan_no.

    Raises:
        FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; next_due or last_done is not a time; as_of is not a date; grace_days is not a whole number of zero or more; active_status is a single text or not iterable.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import overdue_plans
        >>> ctx = Context(stage="month12", role="analyst")
        >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "plan_no": [1, 1], "plan_type": "condition_inspection", "next_due": ["2025-03-01", "2025-05-30"],
        ...                   "last_done": ["2024-03-01", "2024-05-30"], "team_key": "TEAM-900001", "status": "active"})
        >>> out = overdue_plans(p, "2025-04-01", context=ctx)
        >>> out[["net_key", "days_overdue"]].to_dict("records")
        [{'net_key': 'NET-900001', 'days_overdue': 17}]
    """
    p = _plans(maintenance_plan)
    if isinstance(grace_days, bool) or not isinstance(grace_days, int) or grace_days < 0:
        raise FrameError(f"grace_days must be a whole number of days, zero or more (got {value_text(grace_days)})")
    d = _day(as_of, "as_of")
    x = p[p["status"].isin(_strs(active_status, "active_status")) & p["next_due"].notna() & (p["next_due"] + pd.Timedelta(days=grace_days) < d)]
    out = x.assign(days_overdue=(d - x["next_due"]).dt.days - grace_days)
    return out[["net_key", "plan_no", "plan_type", "team_key", "next_due", "last_done", "days_overdue"]].sort_values(["days_overdue", "net_key", "plan_no"], ascending=[False, True, True]).reset_index(drop=True)


@staged(sources=_PLAN, oracle="py:repo_tests/test_oracle_maintenance_release.py::test_oracle_due_within_baseline_per_team_and_plan_type")
def due_within(maintenance_plan: pd.DataFrame, as_of: DateLike, horizon_days: int, *, active_status: tuple[str, ...] = ("active",)) -> pd.DataFrame:
    """Use this when you need how many active maintenance plans fall due within a number of days from a date, per team and plan type.

    Active plans with a next due date from the as-of date to `horizon_days` days later (both inclusive) are counted.

    Args:
        maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, next_due, last_done, team_key and status.
        as_of: The first day of the horizon.
        horizon_days: Days after the as-of date that the horizon reaches (inclusive); a whole number of zero or more.
        active_status: The statuses that count as active (default only "active"); a tuple or list.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns team_key, plan_type, n_plans, first_due and last_due, sorted by team_key and plan_type; an empty frame with these columns when nothing falls due.

    Raises:
        FrameError: a column of maintenance_plan is missing; it has more than one row for an element and plan number; next_due or last_done is not a time; as_of is not a date; horizon_days is not a whole number of zero or more; active_status is a single text or not iterable.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import due_within
        >>> ctx = Context(stage="month12", role="analyst")
        >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "plan_no": [1, 1, 1], "plan_type": "condition_inspection",
        ...                   "next_due": ["2025-04-05", "2025-04-20", "2025-07-01"], "last_done": ["2024-04-05", "2024-04-20", "2024-07-01"], "team_key": "TEAM-900001", "status": "active"})
        >>> out = due_within(p, "2025-04-01", 30, context=ctx)
        >>> out[["team_key", "n_plans"]].to_dict("records")
        [{'team_key': 'TEAM-900001', 'n_plans': 2}]
        >>> out["last_due"].dt.strftime("%Y-%m-%d").tolist()
        ['2025-04-20']
    """
    p = _plans(maintenance_plan)
    if isinstance(horizon_days, bool) or not isinstance(horizon_days, int) or horizon_days < 0:
        raise FrameError(f"horizon_days must be a whole number of days, zero or more (got {value_text(horizon_days)})")
    d = _day(as_of, "as_of")
    x = p[p["status"].isin(_strs(active_status, "active_status")) & p["next_due"].between(d, d + pd.Timedelta(days=horizon_days))]
    if x.empty:
        return pd.DataFrame(columns=["team_key", "plan_type", "n_plans", "first_due", "last_due"])
    g = x.groupby(["team_key", "plan_type"], as_index=False).agg(n_plans=("net_key", "size"), first_due=("next_due", "min"), last_due=("next_due", "max"))
    return g.sort_values(["team_key", "plan_type"]).reset_index(drop=True)


@staged(sources=("service.service_ticket.tkt_key", "service.service_ticket.source", "service.service_ticket.due_date", "service.service_ticket.resolved_ts", "service.service_ticket.team_key"),
        oracle="py:tests/test_service.py::test_winter_deferral_of_planned_work_in_dk_teams")
def planned_backlog(service_ticket: pd.DataFrame, *, sources: tuple[str, ...] = ("planned_maintenance", "inspection"), grace_days: int = 0) -> pd.DataFrame:
    """Use this when you need how late planned tickets were resolved against their due date, by team and month of the due date.

    Planned tickets (source in `sources`, PROPOSED planned_maintenance and inspection) that were resolved after their due date plus `grace_days` (PROPOSED 0) are counted as late.
    mean_lateness_days is taken over all resolved planned tickets and is negative when early: the figure of the generator test; mean_days_late is taken over the late ones (days between the due date and the resolution time, fractions of a day kept at two decimals).
    Tickets without a resolution time or a due date are left out (still open).

    Args:
        service_ticket: The service.service_ticket frame, columns tkt_key, source, due_date, resolved_ts and team_key.
        sources: The ticket sources that count as planned work (PROPOSED planned_maintenance and inspection); a tuple, not a single text.
        grace_days: Days after the due date (counted to its end) that are still on time (PROPOSED 0); a whole number of zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns team_key, period (YYYY-MM of the due date), n_planned (resolved planned tickets), n_late, late_share, mean_lateness_days, mean_days_late and max_days_late (both null when nothing is late), sorted by team_key and period; an empty frame with these columns when no planned ticket is resolved.

    Raises:
        FrameError: a column of service_ticket is missing; it repeats a tkt_key; grace_days is not a whole number of zero or more; sources is a single text; due_date or resolved_ts is not a time; a resolved planned ticket has no team_key.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import planned_backlog
        >>> ctx = Context(stage="month12", role="analyst")
        >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "source": "planned_maintenance", "due_date": ["2025-03-10", "2025-03-20"],
        ...                   "resolved_ts": ["2025-03-12 10:00", "2025-03-19 10:00"], "team_key": "TEAM-900001"})
        >>> out = planned_backlog(t, context=ctx)
        >>> out[["team_key", "period", "n_planned", "n_late", "late_share"]].to_dict("records")
        [{'team_key': 'TEAM-900001', 'period': '2025-03', 'n_planned': 2, 'n_late': 1, 'late_share': 0.5}]
    """
    _need(service_ticket, ["tkt_key", "source", "due_date", "resolved_ts", "team_key"], "service.service_ticket")
    if service_ticket["tkt_key"].duplicated().any():
        raise FrameError("service.service_ticket has more than one row for a tkt_key")
    if isinstance(grace_days, bool) or not isinstance(grace_days, int) or grace_days < 0:
        raise FrameError(f"grace_days must be a whole number of days, zero or more (got {value_text(grace_days)})")
    if isinstance(sources, (str, bytes)):
        raise FrameError(f"sources must be a tuple of ticket sources, not a single text (got {value_text(sources)})")
    x = service_ticket[service_ticket["source"].isin(list(sources))]
    due = _utc(x["due_date"], "service.service_ticket.due_date")
    res = _utc(x["resolved_ts"], "service.service_ticket.resolved_ts")
    ok = due.notna().to_numpy() & res.notna().to_numpy()
    x, due, res = x[ok], due[ok], res[ok]
    late_days = ((res - (due + pd.Timedelta(days=1))).dt.total_seconds() / 86400.0).to_numpy()          # the due date counts to its end
    cols = ["team_key", "period", "n_planned", "n_late", "late_share", "mean_lateness_days", "mean_days_late", "max_days_late"]
    if x.empty:
        return pd.DataFrame(columns=cols)
    if x["team_key"].isna().any():
        raise FrameError("a planned ticket has no team_key")
    d = pd.DataFrame({"team_key": x["team_key"].to_numpy(), "period": due.dt.strftime("%Y-%m").to_numpy(), "late": late_days > grace_days, "days": late_days})
    g: pd.DataFrame = d.groupby(["team_key", "period"], as_index=False).apply(lambda t: pd.Series({"n_planned": len(t), "n_late": int(t["late"].sum()), "late_share": round(float(t["late"].mean()), 4),  # type: ignore[call-overload]  # pandas-stubs: groupby.apply lacks include_groups
                                                                                   "mean_lateness_days": round(float(t["days"].mean()), 2), "mean_days_late": round(float(t.loc[t["late"], "days"].mean()), 2) if t["late"].any() else np.nan,
                                                                                   "max_days_late": round(float(t.loc[t["late"], "days"].max()), 2) if t["late"].any() else np.nan}), include_groups=False)
    g[["n_planned", "n_late"]] = g[["n_planned", "n_late"]].astype(int)
    return g.sort_values(["team_key", "period"]).reset_index(drop=True)


@staged(sources=("service.maintenance_plan.net_key", "service.maintenance_plan.plan_no", "service.maintenance_plan.plan_type", "service.maintenance_plan.interval_months",
                 "service.maintenance_plan.valid_from", "gis.grid_element.net_key", "gis.grid_element.condition_class", "gis.grid_element.element_type"), facts=_FACTS, oracle="py:repo_tests/test_oracle_maintenance_release.py::test_oracle_inspection_interval_check_baseline_per_plan")
def inspection_interval_check(maintenance_plan: pd.DataFrame, grid_element: pd.DataFrame, *, plan_type: str = "condition_inspection", cycle_months: dict[str, Any] | None = None, type_multiplier: dict[str, Any] | None = None) -> pd.DataFrame:
    """Use this when you need the inspection plans whose interval in months deviates from the rule for the condition class and element type.

    Interval = cycle of the condition class (A 120, B 84, C 54, D 32, E 26 months, PROPOSED) times the multiplier of the element type
    (PROPOSED: pipe 1.25, valve 1.2, substation and pump station 0.7, transformer station 0.9, others 1.0), rounded half to even (32.5 months is 32, as Python's round in the generator).
    Elements without a class or with an unknown type are listed with expected_months null. Plans of other types than `plan_type` are ignored.

    Args:
        maintenance_plan: The service.maintenance_plan frame, columns net_key, plan_no, plan_type, interval_months and valid_from.
        grid_element: The gis.grid_element frame, columns net_key, condition_class and element_type.
        plan_type: The plan type that is checked (default "condition_inspection").
        cycle_months: PROPOSED mapping of condition class to cycle in months; None reads the facts policy.grid.inspection_cycle_months.A to E (proposed, today A 120, B 84, C 54, D 32, E 26).
        type_multiplier: PROPOSED mapping of element type to multiplier; None reads the facts policy.grid.inspection_type_multiplier.<type> (proposed).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame of the deviating plans with the columns net_key, plan_no, element_type, condition_class, interval_months, expected_months and valid_from, sorted by net_key and plan_no.

    Raises:
        FrameError: a column of maintenance_plan or grid_element is missing; grid_element has more than one row for a net_key; a fact of the rule cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import inspection_interval_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> p = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "plan_no": [1, 1], "plan_type": "condition_inspection", "interval_months": [54, 60], "valid_from": ["2025-01-01", "2025-01-01"]})
        >>> g = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "condition_class": ["C", "C"], "element_type": ["cable_section", "cable_section"]})
        >>> out = inspection_interval_check(p, g, context=ctx)
        >>> out[["net_key", "interval_months", "expected_months"]].to_dict("records")
        [{'net_key': 'NET-900002', 'interval_months': 60, 'expected_months': 54.0}]
    """
    _need(maintenance_plan, ["net_key", "plan_no", "plan_type", "interval_months", "valid_from"], "service.maintenance_plan")
    _need(grid_element, ["net_key", "condition_class", "element_type"], "gis.grid_element")
    if grid_element["net_key"].duplicated().any():
        raise FrameError("gis.grid_element has more than one row for a net_key")
    cycle_months = _rule_cycle() if cycle_months is None else cycle_months
    type_multiplier = _rule_multiplier() if type_multiplier is None else type_multiplier
    p = maintenance_plan[maintenance_plan["plan_type"] == plan_type]
    m = p.merge(grid_element[["net_key", "condition_class", "element_type"]], on="net_key", how="left")
    exp = [np.nan if (c not in cycle_months or t not in type_multiplier) else float(round(cycle_months[c] * type_multiplier[t])) for c, t in zip(m["condition_class"], m["element_type"])]
    m["expected_months"] = exp
    bad = m[(m["expected_months"].isna()) | (m["interval_months"].astype(float) != m["expected_months"])]
    return bad[["net_key", "plan_no", "element_type", "condition_class", "interval_months", "expected_months", "valid_from"]].sort_values(["net_key", "plan_no"]).reset_index(drop=True)
