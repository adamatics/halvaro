"""Alarms: recomputed from the ok samples and the limit columns of each sensor, the rule table, summaries, incidents and the link to service tickets.

Rule (K03, tie-out O08): a sample violates when it is ok and above limit_high or below limit_low of its sensor; a run of consecutive violating samples counts when it lasts at least
alarm_min_duration_s; counted runs with a gap of at most alarm_merge_gap_s between them are one alarm. raised_ts is the first violating sample, cleared_ts the end of the last violating sample
(its time plus the interval), null when the series ends inside the alarm. Severity is critical when the extreme value reaches the critical limit. The limits are columns of the sensor table,
never the alarm_rule table.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, NamedTuple, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import _checked_measurement, _need, _utc

_ALARM_NAMES = {("load_percent", "high"): "load_high", ("breaker_state", "low"): "breaker_open"}      # PROPOSED: the names of the alarm types that are not "<sensor_type>_<direction>"
_MERGE_GAP_HOURS = {"load_high": 60.0, "default": 8.0}                                                   # PROPOSED: cfg:service.yaml#alarm_tickets.merge_gap_hours has no fact id
_SENSOR_COLS = ["sns_key", "net_key", "zone_key", "sensor_type", "interval_s", "limit_high", "limit_low", "limit_high_crit", "limit_low_crit", "alarm_min_duration_s", "alarm_merge_gap_s"]
_ALARM_COLS = ["sns_key", "raised_ts", "cleared_ts", "severity", "alarm_type", "net_key", "zone_key", "peak_value", "limit_value", "samples"]
_MEAS = ("telemetry.measurement.sns_key", "telemetry.measurement.ts", "telemetry.measurement.value", "telemetry.measurement.quality_flag")
_SENS = tuple(f"telemetry.sensor.{c}" for c in _SENSOR_COLS)


def _period_month(value: Any, what: str) -> str:
    try:
        return pd.Period(value, "M").strftime("%Y-%m")
    except (ValueError, TypeError) as e:
        raise FrameError(f"{what} {value!r} is not a month: {e}") from None


def _name(sensor_type: str, direction: str, names: Mapping[tuple[str, str], str]) -> str:
    return names.get((sensor_type, direction), f"{sensor_type}_{direction}")


def _sensor_alarms(row: Any, ts: np.ndarray[Any, Any], v: np.ndarray[Any, Any], ok: np.ndarray[Any, Any], names: Mapping[tuple[str, str], str]) -> list[tuple[Any, ...]]:
    step = int(row.interval_s)
    slot = ts.astype("datetime64[ns]").astype("int64") // (step * 10 ** 9)
    last_slot = slot.max()
    min_n = max(1, int(math.ceil(int(row.alarm_min_duration_s) / step)))
    gap_n = int(int(row.alarm_merge_gap_s) // step)
    out: list[tuple[Any, ...]] = []
    for direction, lim, crit in (("high", row.limit_high, row.limit_high_crit), ("low", row.limit_low, row.limit_low_crit)):
        if pd.isna(lim):
            continue
        with np.errstate(invalid="ignore"):
            viol = ok & ((v > lim) if direction == "high" else (v < lim))
        vi = np.flatnonzero(viol)
        if len(vi) == 0:
            continue
        sv = slot[vi]
        cut = np.flatnonzero(np.diff(sv) != 1) + 1
        starts = np.concatenate([[0], cut])
        ends = np.concatenate([cut, [len(sv)]])                                  # exclusive, in violating-sample positions
        keep = (ends - starts) >= min_n
        s_slot, e_slot = sv[starts[keep]], sv[ends[keep] - 1] + 1               # slot of the first violating sample, slot after the last
        if len(s_slot) == 0:
            continue
        grp = np.concatenate([[0], np.cumsum((s_slot[1:] - e_slot[:-1]) > gap_n)])
        for g in np.unique(grp):
            sel = grp == g
            a, b = int(s_slot[sel][0]), int(e_slot[sel][-1])
            inside = (slot >= a) & (slot < b)
            vals = v[inside & ok]
            peak = float(vals.max() if direction == "high" else vals.min())
            sev = "warning" if pd.isna(crit) else ("critical" if ((peak >= crit) if direction == "high" else (peak <= crit)) else "warning")
            last = b - 1
            raised = ts[np.flatnonzero(slot == a)[0]]
            cleared = pd.NaT if last >= last_slot else pd.Timestamp(ts[np.flatnonzero(slot == last)[0]]) + pd.Timedelta(seconds=step)
            out.append((row.sns_key, pd.Timestamp(raised), cleared, sev, _name(row.sensor_type, direction, names), row.net_key, row.zone_key, round(peak, 3), round(float(lim), 3), int(viol[inside].sum())))
    return out


@staged(sources=(*_MEAS, *_SENS), oracle="py:tests/test_telemetry.py::test_alarms_recomputed_from_raw")
def recompute_alarms(measurement: pd.DataFrame, sensor: pd.DataFrame, *, alarm_names: Mapping[tuple[str, str], str] = _ALARM_NAMES) -> pd.DataFrame:
    """Use this when you need the alarms recomputed from the ok samples and the limit columns of each sensor, in the shape of telemetry.alarm.

    Only ok samples with a value count. A sensor with a limit needs alarm_min_duration_s and alarm_merge_gap_s; a sensor without rows in the frame has no alarm. Consecutive means one interval_s apart: a slot that is not
    in the frame ends a run. A series that ends inside an alarm has a null cleared_ts. The limits are columns of the sensor table, never the alarm_rule table.
    PROPOSED: alarm_names, the names of the types that are not '<sensor_type>_<direction>'.

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        sensor: The telemetry.sensor frame, columns sns_key, net_key, zone_key, sensor_type, interval_s, limit_high, limit_low, limit_high_crit, limit_low_crit, alarm_min_duration_s and alarm_merge_gap_s.
        alarm_names: PROPOSED mapping (sensor_type, direction) to alarm type name, for the types that are not '<sensor_type>_<direction>'; the default names load_high and breaker_open.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns sns_key, raised_ts (first violating sample), cleared_ts (end of the last violating sample, its time plus the interval; null when the series ends inside the alarm), severity (critical when the extreme value
        reaches the critical limit, else warning), alarm_type, net_key, zone_key, peak_value, limit_value and samples (violating samples), sorted by sns_key, raised_ts and alarm_type.

    Raises:
        FrameError: a column of sensor or measurement is missing, the measurement is invalid (see valid_samples), telemetry.sensor repeats a sns_key, a measured sensor is not in telemetry.sensor,
            a sensor with a limit has an interval_s that is not a whole number of seconds above 0, or has no alarm_min_duration_s or alarm_merge_gap_s.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import recompute_alarms
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45", "2025-03-01 01:00"]),
        ...                   "value": [50.0, 95.0, 96.0, 50.0, 50.0], "quality_flag": "ok"})
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "net_key": ["NET-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "interval_s": [900],
        ...                   "limit_high": [90.0], "limit_low": [None], "limit_high_crit": [100.0], "limit_low_crit": [None], "alarm_min_duration_s": [900], "alarm_merge_gap_s": [900]})
        >>> out = recompute_alarms(m, s, context=ctx)
        >>> out[["alarm_type", "severity", "peak_value", "limit_value", "samples"]].to_dict("records")
        [{'alarm_type': 'load_high', 'severity': 'warning', 'peak_value': 96.0, 'limit_value': 90.0, 'samples': 2}]
        >>> out["cleared_ts"].dt.strftime("%H:%M").tolist()
        ['00:45']
"""
    _need(sensor, _SENSOR_COLS, "telemetry.sensor")
    m = _checked_measurement(measurement)
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    s = sensor.set_index("sns_key", drop=False)
    unknown = sorted(set(m["sns_key"]) - set(s.index))
    if unknown:
        raise FrameError(f"{len(unknown)} sensors of the measurements are not in telemetry.sensor (for example {unknown[0]})")
    rows: list[tuple[Any, ...]] = []
    for key, g in m.groupby("sns_key", sort=True):
        r = s.loc[key]
        if pd.isna(r["limit_high"]) and pd.isna(r["limit_low"]):
            continue
        if pd.isna(r["interval_s"]) or not float(r["interval_s"]) > 0 or float(r["interval_s"]) != int(float(r["interval_s"])):
            raise FrameError(f"{key}: interval_s must be a whole number of seconds above 0")
        if pd.isna(r["alarm_min_duration_s"]) or pd.isna(r["alarm_merge_gap_s"]):
            raise FrameError(f"{key} has a limit but no alarm_min_duration_s or alarm_merge_gap_s")
        rows += _sensor_alarms(r, g["ts"].to_numpy(), g["value"].to_numpy(dtype=float, na_value=np.nan), ((g["quality_flag"] == "ok") & g["value"].notna()).to_numpy(), alarm_names)
    out = pd.DataFrame(rows, columns=_ALARM_COLS)
    out["cleared_ts"] = pd.to_datetime(out["cleared_ts"]).astype("datetime64[ns]")
    out["raised_ts"] = pd.to_datetime(out["raised_ts"]).astype("datetime64[ns]")
    return out.sort_values(["sns_key", "raised_ts", "alarm_type"]).reset_index(drop=True)


@staged(sources=_SENS, oracle="py:halvaro_gen/world/telemetry/build.py::_rule_frame")
def alarm_rules_table(sensor: pd.DataFrame, *, alarm_names: Mapping[tuple[str, str], str] = _ALARM_NAMES) -> pd.DataFrame:
    """Use this when you need one row per alarm type derived from the limit columns of the sensors, in the shape of telemetry.alarm_rule.

    The description text of telemetry.alarm_rule is not produced. min_duration_s is the minimum over the sensors of the type and merge_gap_s the maximum; the limits come from the sensor table, never the alarm_rule table.
    PROPOSED: alarm_names, the names of the types that are not '<sensor_type>_<direction>'.

    Args:
        sensor: The telemetry.sensor frame, columns sns_key, net_key, zone_key, sensor_type, interval_s, limit_high, limit_low, limit_high_crit, limit_low_crit, alarm_min_duration_s and alarm_merge_gap_s.
        alarm_names: PROPOSED mapping (sensor_type, direction) to alarm type name, for the types that are not '<sensor_type>_<direction>'; the default names load_high and breaker_open.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns rule_no (1 upward, by alarm type), alarm_type, sensor_type, direction, n_sensors, limit_min, limit_max, critical_limit_min, critical_limit_max, min_duration_s and merge_gap_s, sorted by alarm_type.

    Raises:
        FrameError: a column of sensor is missing, telemetry.sensor repeats a sns_key, or a sensor with a limit has no alarm_min_duration_s or alarm_merge_gap_s.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import alarm_rules_table
        >>> ctx = Context(stage="month12", role="analyst")
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001", "SNS-900002"], "net_key": ["NET-900001", "NET-900002"], "zone_key": ["ZONE-0001", "ZONE-0002"], "sensor_type": "load_percent",
        ...                   "interval_s": [900, 900], "limit_high": [90.0, 80.0], "limit_low": [None, None], "limit_high_crit": [100.0, 95.0], "limit_low_crit": [None, None],
        ...                   "alarm_min_duration_s": [900, 1800], "alarm_merge_gap_s": [900, 3600]})
        >>> out = alarm_rules_table(s, context=ctx)
        >>> out[["rule_no", "alarm_type", "direction", "n_sensors", "limit_min", "limit_max", "min_duration_s", "merge_gap_s"]].to_dict("records")
        [{'rule_no': 1, 'alarm_type': 'load_high', 'direction': 'high', 'n_sensors': 2, 'limit_min': 80.0, 'limit_max': 90.0, 'min_duration_s': 900, 'merge_gap_s': 3600}]
"""
    _need(sensor, _SENSOR_COLS, "telemetry.sensor")
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    limited = sensor[sensor["limit_high"].notna() | sensor["limit_low"].notna()]
    if limited[["alarm_min_duration_s", "alarm_merge_gap_s"]].isna().any().any():
        raise FrameError("a sensor with a limit has no alarm_min_duration_s or alarm_merge_gap_s")
    rows: list[tuple[Any, ...]] = []
    for direction, lim, crit in (("high", "limit_high", "limit_high_crit"), ("low", "limit_low", "limit_low_crit")):
        x = sensor[sensor[lim].notna()]
        for st, g in x.groupby("sensor_type"):
            rows.append((_name(cast(str, st), direction, alarm_names), st, direction, len(g), g[lim].min(), g[lim].max(), g[crit].min(), g[crit].max(), g["alarm_min_duration_s"].min(), g["alarm_merge_gap_s"].max()))
    out = pd.DataFrame(rows, columns=["alarm_type", "sensor_type", "direction", "n_sensors", "limit_min", "limit_max", "critical_limit_min", "critical_limit_max", "min_duration_s", "merge_gap_s"])
    out = out.sort_values("alarm_type").reset_index(drop=True)
    out.insert(0, "rule_no", np.arange(1, len(out) + 1))
    return out


class AlarmSummary(NamedTuple):
    """counts: zone_key, alarm_type, severity, month, n_alarms; background: zone_key, year, n_alarms, months, per_month (alarms a month over the months with data in the alarm table's range)."""
    counts: pd.DataFrame
    background: pd.DataFrame


@staged(sources=("telemetry.alarm.zone_key", "telemetry.alarm.alarm_type", "telemetry.alarm.severity", "telemetry.alarm.raised_ts", "telemetry.alarm.sns_key"), oracle="py:halvaro_gen/world/telemetry/truth.py::compute")
def alarm_summary(alarm: pd.DataFrame, *, first_month: str | None = None, last_month: str | None = None) -> AlarmSummary:
    """Use this when you need counts of alarms by zone, type, severity and month, and the background alarm rate per zone and year.

    Counts are by UTC month of raised_ts. The background rate is the alarms per month over the months of the year inside first_month..last_month. first_month and last_month default to the first and last month of the
    alarm frame; pass the data window as months ('YYYY-MM') for a rate that counts months without alarms, as a year with few alarms is otherwise rated on the months it happens to have. An empty alarm frame without
    both months gives an empty background.

    Args:
        alarm: The telemetry.alarm frame, columns zone_key, alarm_type, severity, raised_ts and sns_key.
        first_month: First month of the background window ('YYYY-MM'); None takes the first month of the alarm frame.
        last_month: Last month of the background window ('YYYY-MM'); None takes the last month of the alarm frame.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An AlarmSummary named tuple: counts (zone_key, alarm_type, severity, month, n_alarms, sorted by these keys) and background (zone_key, year, n_alarms, months, per_month; per_month is rounded to 4 decimals, sorted by zone_key and year).

    Raises:
        FrameError: a column of alarm is missing, zone_key, alarm_type, severity or raised_ts is null, raised_ts is not a readable timestamp or has a time zone, first_month or last_month is not a month, or first_month is after last_month.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import alarm_summary
        >>> ctx = Context(stage="month12", role="analyst")
        >>> a = pd.DataFrame({"zone_key": "ZONE-0001", "alarm_type": "load_high", "severity": ["warning", "warning", "critical"], "sns_key": "SNS-900001",
        ...                   "raised_ts": ["2025-03-01 10:00", "2025-03-02 10:00", "2025-04-01 10:00"]})
        >>> out = alarm_summary(a, first_month="2025-01", last_month="2025-12", context=ctx)
        >>> out.counts[["severity", "month", "n_alarms"]].to_dict("records")
        [{'severity': 'critical', 'month': '2025-04', 'n_alarms': 1}, {'severity': 'warning', 'month': '2025-03', 'n_alarms': 2}]
        >>> out.background[["year", "n_alarms", "months", "per_month"]].to_dict("records")
        [{'year': 2025, 'n_alarms': 3, 'months': 12, 'per_month': 0.25}]
"""
    _need(alarm, ["zone_key", "alarm_type", "severity", "raised_ts", "sns_key"], "telemetry.alarm")
    if alarm[["zone_key", "alarm_type", "severity"]].isna().any().any():
        raise FrameError("telemetry.alarm has null zone_key, alarm_type or severity")
    t = _utc(alarm["raised_ts"], "telemetry.alarm.raised_ts")
    if t.isna().any():
        raise FrameError("telemetry.alarm has null raised_ts")
    a = alarm.assign(month=t.dt.strftime("%Y-%m").to_numpy())
    if first_month is not None:
        first_month = _period_month(first_month, "first_month")
    if last_month is not None:
        last_month = _period_month(last_month, "last_month")
    counts = a.groupby(["zone_key", "alarm_type", "severity", "month"], as_index=False, observed=True).size().rename(columns={"size": "n_alarms"}).sort_values(["zone_key", "alarm_type", "severity", "month"]).reset_index(drop=True)
    lo = first_month or (a["month"].min() if len(a) else None)
    hi = last_month or (a["month"].max() if len(a) else None)
    if lo is None or hi is None:
        return AlarmSummary(counts, pd.DataFrame(columns=["zone_key", "year", "n_alarms", "months", "per_month"]))
    if lo > hi:
        raise FrameError(f"first_month {lo} is after last_month {hi}")
    months = pd.period_range(lo, hi, freq="M")
    per_year = pd.Series(months.year).value_counts()
    a = a.assign(year=a["month"].str[:4].astype(int))
    bg = a[a["month"].between(lo, hi)].groupby(["zone_key", "year"], as_index=False, observed=True).size().rename(columns={"size": "n_alarms"})
    bg["months"] = bg["year"].map(per_year).astype(int)
    bg["per_month"] = np.round(bg["n_alarms"] / bg["months"], 4)
    return AlarmSummary(counts, bg.sort_values(["zone_key", "year"]).reset_index(drop=True))


@staged(sources=("telemetry.alarm.raised_ts", "telemetry.alarm.cleared_ts", "telemetry.alarm.net_key", "telemetry.alarm.alarm_type"), oracle="py:halvaro_gen/world/service/demand.py::alarm_incidents")
def incident_groups(alarm: pd.DataFrame, *, merge_gap_hours: Mapping[str, float] = _MERGE_GAP_HOURS) -> pd.Series:
    """Use this when you need the incident number of each alarm, grouping alarms of one element and type that follow each other closely.

    Alarms of one element (net_key) and type are one incident while each starts at most the merge gap after the cleared time of the incident so far; the gap is in hours, by type, else the 'default' entry. A null
    cleared_ts counts as the raised time. Numbers run from 1 in order of net_key, alarm_type and time.
    PROPOSED: merge_gap_hours is cfg:service.yaml#alarm_tickets.merge_gap_hours (load_high 60, default 8); no fact id.

    Args:
        alarm: The telemetry.alarm frame, columns raised_ts, cleared_ts, net_key and alarm_type.
        merge_gap_hours: PROPOSED mapping of alarm type to merge gap in hours, with a required 'default' entry used for types not listed.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        An int64 Series named incident with the index of the alarm frame (empty when the frame is empty).

    Raises:
        FrameError: a column of alarm is missing, merge_gap_hours has no 'default' entry, or raised_ts or cleared_ts holds numbers, unreadable text or a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import incident_groups
        >>> ctx = Context(stage="month12", role="analyst")
        >>> a = pd.DataFrame({"net_key": "NET-900001", "alarm_type": "load_high", "raised_ts": ["2025-03-01 00:00", "2025-03-01 12:00", "2025-03-10 00:00"],
        ...                   "cleared_ts": ["2025-03-01 02:00", "2025-03-01 13:00", None]})
        >>> incident_groups(a, context=ctx).tolist()
        [1, 1, 2]
"""
    _need(alarm, ["raised_ts", "cleared_ts", "net_key", "alarm_type"], "telemetry.alarm")
    if "default" not in merge_gap_hours:
        raise FrameError(f"merge_gap_hours needs a 'default' entry (got the keys {sorted(map(str, merge_gap_hours))!r})")
    a = alarm.assign(raised=_utc(alarm["raised_ts"], "raised_ts").to_numpy(), cleared=_utc(alarm["cleared_ts"], "cleared_ts").to_numpy())
    a["cleared"] = a["cleared"].fillna(a["raised"])
    a = a.assign(_pos=np.arange(len(a)))
    order = a.sort_values(["net_key", "alarm_type", "raised"], kind="stable")
    order_pos = order["_pos"].to_numpy()
    number: list[int] = []
    cur_key: Any = None
    cur_clear: Any = None
    n = 0
    r: Any
    if order.empty:
        return pd.Series([], index=alarm.index, name="incident", dtype="int64")
    for r in order.itertuples():
        gap = merge_gap_hours.get(r.alarm_type, merge_gap_hours["default"])
        key = (r.net_key, r.alarm_type)
        if cur_key == key and (r.raised - cur_clear).total_seconds() / 3600.0 <= gap:
            cur_clear = max(cur_clear, r.cleared)
        else:
            n += 1
            cur_key, cur_clear = key, r.cleared
        number.append(n)
    result = np.empty(len(alarm), dtype="int64")
    result[order_pos] = number
    return pd.Series(result, index=alarm.index, name="incident")


@staged(sources=("telemetry.alarm.sns_key", "telemetry.alarm.raised_ts", "service.ticket_alarm.sns_key", "service.ticket_alarm.raised_ts", "service.ticket_alarm.link_type",
                 "service.ticket_alarm.tkt_key", "service.service_ticket.tkt_key"), oracle="py:tests/test_service.py::test_alarm_tickets_are_deduplicated")
def alarm_ticket_link(alarm: pd.DataFrame, ticket_alarm: pd.DataFrame, service_ticket: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need to know which alarms have a service ticket, and how many tickets each incident has.

    The alarm frame gets linked, tkt_key and link_type (trigger or precursor) from service.ticket_alarm, matched on sns_key and raised_ts. The result keeps the rows and index of the alarm frame. Many alarms of an
    incident share one ticket (T12), so most alarms are not linked. A link whose ticket is not in service.service_ticket or whose alarm is not in the frame raises.

    Args:
        alarm: The telemetry.alarm frame, columns sns_key and raised_ts; with net_key, alarm_type and cleared_ts as well it also gets the incident columns.
        ticket_alarm: The service.ticket_alarm frame, columns sns_key, raised_ts, link_type and tkt_key.
        service_ticket: The service.service_ticket frame, column tkt_key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The alarm frame with the extra columns linked (bool), tkt_key and link_type (null when not linked); when net_key, alarm_type and cleared_ts are in the frame also incident (see incident_groups) and incident_tickets
        (distinct tickets of the incident, 0 when none).

    Raises:
        FrameError: a column of alarm, ticket_alarm or service_ticket is missing, a ticket_alarm or alarm key pair (sns_key, raised_ts) is repeated or null, a link names a ticket that is not in service.service_ticket,
            a link names an alarm that is not in the alarm frame, the alarm frame already has a column linked, tkt_key or link_type, or a timestamp is unreadable or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import alarm_ticket_link
        >>> ctx = Context(stage="month12", role="analyst")
        >>> a = pd.DataFrame({"sns_key": "SNS-900001", "raised_ts": ["2025-03-01 00:00", "2025-03-01 12:00"]})
        >>> t = pd.DataFrame({"sns_key": ["SNS-900001"], "raised_ts": ["2025-03-01 00:00"], "link_type": ["trigger"], "tkt_key": ["TKT-900001"]})
        >>> st = pd.DataFrame({"tkt_key": ["TKT-900001"]})
        >>> out = alarm_ticket_link(a, t, st, context=ctx)
        >>> out["linked"].tolist()
        [True, False]
        >>> out["tkt_key"].tolist()
        ['TKT-900001', nan]
"""
    _need(alarm, ["sns_key", "raised_ts"], "telemetry.alarm")
    _need(ticket_alarm, ["sns_key", "raised_ts", "link_type", "tkt_key"], "service.ticket_alarm")
    _need(service_ticket, ["tkt_key"], "service.service_ticket")
    if ticket_alarm.duplicated(["sns_key", "raised_ts"]).any():
        raise FrameError("service.ticket_alarm has more than one link for the same alarm")
    if alarm.duplicated(["sns_key", "raised_ts"]).any():
        raise FrameError("telemetry.alarm has more than one row for the same sensor and raised_ts")
    missing = set(ticket_alarm["tkt_key"]) - set(service_ticket["tkt_key"])
    if missing:
        raise FrameError(f"{len(missing)} links name a ticket that is not in service.service_ticket (for example {sorted(missing)[0]})")
    clash = [c for c in ("linked", "tkt_key", "link_type") if c in alarm.columns]
    if clash:
        raise FrameError(f"the alarm frame already has the column(s) {', '.join(clash)}")
    if alarm[["sns_key", "raised_ts"]].isna().any().any() or ticket_alarm[["sns_key", "raised_ts"]].isna().any().any():
        raise FrameError("alarms and links need a sns_key and a raised_ts")
    ta = _utc(alarm["raised_ts"], "raised_ts").to_numpy()
    tl = _utc(ticket_alarm["raised_ts"], "raised_ts").to_numpy()
    link = ticket_alarm[["sns_key", "link_type", "tkt_key"]].assign(_t=tl)
    a = alarm.assign(_t=ta)
    out = a.merge(link, on=["sns_key", "_t"], how="left", validate="one_to_one", indicator=True)
    lost = link.merge(a[["sns_key", "_t"]], on=["sns_key", "_t"], how="left", indicator=True)
    if (lost["_merge"] == "left_only").any():
        raise FrameError(f"{int((lost['_merge'] == 'left_only').sum())} ticket links name an alarm that is not in the alarm frame")
    out["linked"] = (out["_merge"] == "both").to_numpy()
    out.index = alarm.index
    inc = unwrapped(incident_groups)(alarm) if {"cleared_ts", "net_key", "alarm_type"} <= set(alarm.columns) else None
    out = out.drop(columns=["_t", "_merge"])
    if inc is not None:
        out["incident"] = inc.to_numpy()
        out["incident_tickets"] = out.groupby("incident")["tkt_key"].transform("nunique").to_numpy()
    return out
