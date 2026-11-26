"""Capacity and load: design capacity of the zones, the load in percent of the design, its peak, the hours above bands, the load duration curve, the ranking of zones, winters and cold snaps.

Heat zones are read at their root pump (critical_role root_pump): `load_percent` of the root sensor, or `heat_power` over `rated_value`. The electric zone has stations only, its zone value is null (T9),
and 100 percent is a design value with diversity, not a physical limit (T8). Only ok samples count in peaks and hours.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact

from ._guard import staged
from ._util import _checked_measurement, _need, _positive_interval, _utc
from ._types import TimesLike
from ._tail import value_text

_DIVERSITY = {"heat": 0.6, "electric": 0.45}                    # PROPOSED: cfg:gis.yaml#defaults.*.design_diversity has no fact id
_WINTER_MONTHS = (11, 12, 1, 2, 3)                             # PROPOSED: policy.grid.winter_window is needed
_BANDS = (90.0, 100.0, 105.0)                                  # PROPOSED: policy.grid.load_bands is needed
_MEAS = ("telemetry.measurement.sns_key", "telemetry.measurement.ts", "telemetry.measurement.value", "telemetry.measurement.quality_flag")
_SENSOR = ("telemetry.sensor.sns_key", "telemetry.sensor.zone_key", "telemetry.sensor.sensor_type", "telemetry.sensor.interval_s", "telemetry.sensor.critical_role", "telemetry.sensor.rated_value")
_SERIES_COLS = ["zone_key", "sns_key", "level", "basis", "ts", "quality_flag", "ok", "load_percent"]


@staged(sources=("gis.supply_zone.zone_key", "gis.supply_zone.design_capacity", "gis.supply_zone.design_capacity_unit"), oracle="py:halvaro_gen/world/gis/facts.py::story_facts")
def zone_design_capacity(supply_zone: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the design capacity of each zone with its unit, as stored in the supply zone table.

    One row per zone with the design capacity and its unit as stored (MW_th for heat, MVA for electric).

    Args:
        supply_zone: The gis.supply_zone table, with the columns zone_key, design_capacity and design_capacity_unit.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, design_capacity, design_capacity_unit, sorted by zone_key, one row per zone.

    Raises:
        FrameError: supply_zone is not a DataFrame or lacks zone_key, design_capacity or design_capacity_unit; a zone_key appears in more than one row; a zone has a null design_capacity or unit, or a design_capacity that is not above zero.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import zone_design_capacity
        >>> ctx = Context(stage="month12", role="analyst")
        >>> zones = pd.DataFrame({"zone_key": ["ZONE-0002", "ZONE-0001"], "design_capacity": [40.0, 25.0], "design_capacity_unit": ["MW_th", "MVA"]})
        >>> zone_design_capacity(zones, context=ctx)["zone_key"].tolist()
        ['ZONE-0001', 'ZONE-0002']
        >>> zone_design_capacity(zones, context=ctx)["design_capacity"].tolist()
        [25.0, 40.0]

    """
    _need(supply_zone, ["zone_key", "design_capacity", "design_capacity_unit"], "gis.supply_zone")
    if supply_zone["zone_key"].duplicated().any():
        raise FrameError("gis.supply_zone has more than one row for a zone_key")
    if supply_zone[["design_capacity", "design_capacity_unit"]].isna().any().any() or not (supply_zone["design_capacity"] > 0).all():
        raise FrameError("gis.supply_zone needs a positive design_capacity and a unit for every zone")
    return supply_zone[["zone_key", "design_capacity", "design_capacity_unit"]].sort_values("zone_key").reset_index(drop=True)


@staged(sources=("gis.grid_element.zone_key", "gis.grid_element.element_type", "gis.grid_element.status", "gis.grid_element.rated_capacity", "gis.grid_element.capacity_unit"),
        oracle="py:halvaro_gen/world/gis/facts.py::story_facts")
def recompute_design_capacity(grid_element: pd.DataFrame, *, heat_diversity: float = _DIVERSITY["heat"], electric_diversity: float = _DIVERSITY["electric"]) -> pd.DataFrame:
    """Use this when you need to recompute the design capacity of each zone from the grid elements in service, with the heat and electric diversity applied.

    Heat exchanger stations (kW) times the heat diversity give MW_th, transformer stations (kVA) times the electric diversity give MVA. Elements that are not in service count for nothing. The stored value is rounded to 0.1.
    PROPOSED: the diversities 0.6 and 0.45 (cfg:gis.yaml#defaults, no fact id).

    Args:
        grid_element: The gis.grid_element table, with the columns zone_key, element_type, status, rated_capacity and capacity_unit.
        heat_diversity: Diversity factor of the heat zones, a number in (0, 1]; default 0.6 (PROPOSED).
        electric_diversity: Diversity factor of the electric zones, a number in (0, 1]; default 0.45 (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, network_type, design_capacity (three decimals), design_capacity_unit, n_elements, sorted by zone_key.

    Raises:
        FrameError: grid_element is not a DataFrame or lacks one of its columns; a diversity is not a number in (0, 1]; an element in service has no zone_key; a heat exchanger station is not rated in kW or a transformer station not in kVA; an element in service has a null or negative rated_capacity.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import recompute_design_capacity
        >>> ctx = Context(stage="month12", role="analyst")
        >>> elements = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "element_type": ["heat_exchanger_station"] * 3,
        ...                          "status": ["in_service", "in_service", "planned"], "rated_capacity": [1000.0, 500.0, 9000.0], "capacity_unit": ["kW"] * 3})
        >>> recompute_design_capacity(elements, context=ctx).to_dict("records")
        [{'zone_key': 'ZONE-0001', 'network_type': 'heat', 'design_capacity': 0.9, 'design_capacity_unit': 'MW_th', 'n_elements': 2}]

    """
    _need(grid_element, ["zone_key", "element_type", "status", "rated_capacity", "capacity_unit"], "gis.grid_element")
    for name, v in (("heat_diversity", heat_diversity), ("electric_diversity", electric_diversity)):
        if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not 0 < v <= 1:
            raise FrameError(f"{name} must be a number in (0, 1], not {v!r}")
    if grid_element.loc[grid_element["status"] == "in_service", "zone_key"].isna().any():
        raise FrameError("gis.grid_element has elements in service without a zone_key")
    rows = []
    for etype, unit, kind, div, out_unit in (("heat_exchanger_station", "kW", "heat", heat_diversity, "MW_th"), ("transformer_station", "kVA", "electric", electric_diversity, "MVA")):
        x = grid_element[(grid_element["element_type"] == etype) & (grid_element["status"] == "in_service")]
        if (x["capacity_unit"] != unit).any():
            raise FrameError(f"{etype} elements must be rated in {unit}")
        if x["rated_capacity"].isna().any() or (x["rated_capacity"] < 0).any():
            raise FrameError(f"{etype} elements in service need a rated_capacity of zero or more")
        for z, g in x.groupby("zone_key"):
            exact = Decimal(str(float(g["rated_capacity"].sum()))) * Decimal(str(div)) / Decimal(1000)
            rows.append((z, kind, float(exact.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)), out_unit, len(g)))
    return pd.DataFrame(rows, columns=["zone_key", "network_type", "design_capacity", "design_capacity_unit", "n_elements"]).sort_values("zone_key").reset_index(drop=True)


@staged(sources=(*_MEAS, *_SENSOR))
def zone_load_percent(measurement: pd.DataFrame, sensor: pd.DataFrame, *, basis: str = "load_percent") -> pd.DataFrame:
    """Use this when you need the load in percent of the design per heat zone (its root pump) and per electric station, with the quality flag of every sample.

    basis load_percent takes the root `load_percent` sensor, heat_power takes the root `heat_power` sensor in MW over `rated_value` times 100. Electric stations (zones without a root pump) are listed per sensor with level 'station' and basis 'station':
    they have no zone value (T9). A sensor frame without the root rows would turn the heat sensors of that zone into stations, so pass the full sensor table. The heat_power basis is a weaker oracle than the root load_percent:
    peaks and hours above 100 percent can differ from the root load_percent basis, and the peak time can shift.

    Args:
        measurement: The telemetry.measurement table, with the columns sns_key, ts, value and quality_flag.
        sensor: The full telemetry.sensor table, with the columns sns_key, zone_key, sensor_type, interval_s, critical_role and rated_value.
        basis: load_percent (default) or heat_power, the root sensor type the zone value is read from.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok, load_percent (null unless ok), sorted by zone_key, sns_key and ts.

    Raises:
        FrameError: basis is not load_percent or heat_power; the sensor or measurement frame lacks a column or is not a DataFrame; an interval_s is not a positive number; the measurement has a timestamp that is not readable or has a time zone, a null sns_key or ts, an unknown or null quality_flag, or more than one row for a sensor and timestamp; a heat zone has more than one root sensor of the basis; with heat_power a root sensor has no positive rated_value.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import zone_load_percent
        >>> ctx = Context(stage="month12", role="analyst")
        >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "interval_s": [3600],
        ...                        "critical_role": ["root_pump"], "rated_value": [100.0]})
        >>> m = pd.DataFrame({"sns_key": ["SNS-900001"] * 2, "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "value": [80.0, 95.0], "quality_flag": ["ok", "suspect"]})
        >>> out = zone_load_percent(m, sensor, context=ctx)
        >>> out["level"].tolist()
        ['zone', 'zone']
        >>> out["load_percent"].tolist()
        [80.0, nan]

    """
    if basis not in ("load_percent", "heat_power"):
        raise FrameError(f"basis must be load_percent or heat_power, not {basis!r}")
    _need(sensor, ["sns_key", "zone_key", "sensor_type", "interval_s", "critical_role", "rated_value"], "telemetry.sensor")
    _positive_interval(sensor)
    m = _checked_measurement(measurement)
    root = sensor[(sensor["critical_role"] == "root_pump") & (sensor["sensor_type"] == basis)]
    roots = set(sensor.loc[sensor["critical_role"] == "root_pump", "zone_key"])
    st = sensor[(sensor["sensor_type"] == "load_percent") & ~sensor["zone_key"].isin(roots)]
    if root["zone_key"].duplicated().any():
        raise FrameError(f"a heat zone has more than one root {basis} sensor")
    if basis == "heat_power" and (root["rated_value"].isna() | (root["rated_value"] <= 0)).any():
        raise FrameError("root heat_power sensors need a positive rated_value (MW)")
    parts = []
    by = {k: g for k, g in m.groupby("sns_key", sort=False)}
    empty = m.iloc[:0]
    r: Any
    for r in root.itertuples():
        x = by.get(r.sns_key, empty)
        v = x["value"].to_numpy(dtype=float) * (100.0 / r.rated_value if basis == "heat_power" else 1.0)
        parts.append(pd.DataFrame({"zone_key": r.zone_key, "sns_key": r.sns_key, "level": "zone", "basis": basis, "ts": x["ts"].to_numpy(), "quality_flag": x["quality_flag"].to_numpy(), "load_percent": v}))
    for r in st.itertuples():
        x = by.get(r.sns_key, empty)
        parts.append(pd.DataFrame({"zone_key": r.zone_key, "sns_key": r.sns_key, "level": "station", "basis": "station", "ts": x["ts"].to_numpy(), "quality_flag": x["quality_flag"].to_numpy(),
                                   "load_percent": x["value"].to_numpy(dtype=float)}))
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_SERIES_COLS)
    out["ok"] = (out["quality_flag"] == "ok") & np.isfinite(out["load_percent"].astype(float))
    out["load_percent"] = out["load_percent"].where(out["ok"])
    return out[_SERIES_COLS].sort_values(["zone_key", "sns_key", "ts"]).reset_index(drop=True)


def _check_series(zone_series: pd.DataFrame) -> pd.DataFrame:
    _need(zone_series, _SERIES_COLS, "zone load series")
    if zone_series[["zone_key", "sns_key"]].isna().any().any():
        raise FrameError("the zone load series has null zone_key or sns_key")
    return zone_series.assign(ts=_utc(zone_series["ts"], "zone load series ts").to_numpy())


def _hours(sensor: pd.DataFrame, series: pd.DataFrame) -> pd.Series:
    _need(sensor, ["sns_key", "interval_s"], "telemetry.sensor")
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    _positive_interval(sensor)
    missing = sorted(set(series["sns_key"]) - set(sensor["sns_key"]))
    if missing:
        raise FrameError(f"{len(missing)} sensors of the series are not in telemetry.sensor (for example {missing[0]})")
    return sensor.set_index("sns_key")["interval_s"].astype(float) / 3600.0


def _outdoor(obs: pd.DataFrame, station: str, when: pd.Timestamp, max_age: pd.Timedelta) -> float:
    o = obs[(obs["station_key"] == station) & (obs["ts"] <= when)]
    if o.empty:
        return np.nan
    last = o.loc[o["ts"].idxmax()]
    return float(last["temp_c"]) if when - last["ts"] <= max_age else np.nan


@staged(sources=(*_MEAS, *_SENSOR, "telemetry.sensor.station_key", "telemetry.weather_observation.station_key", "telemetry.weather_observation.ts", "telemetry.weather_observation.temp_c"))
def peak_load(zone_series: pd.DataFrame, sensor: pd.DataFrame, weather_observation: pd.DataFrame, supply: pd.DataFrame | None = None, *, min_completeness: float = 0.9,
              timezone: str = "Europe/Copenhagen", max_age_hours: float = 1.5) -> pd.DataFrame:
    """Use this when you need the peak load of each heat zone (its root) and each electric station, with its time, validity and the outdoor and supply temperature at the peak.

    Per zone and sensor: the peak percent, its time in UTC and local, the completeness of the series, whether the peak is valid, the outdoor temperature at the peak and the supply temperature of the root at the peak. Over the time span of the series it also gives
    the highest ok supply temperature of the root (supply_temp_max_c) and the lowest outdoor temperature of the station (outdoor_min_c): pass a series cut to a winter or a cold snap to read the maximum and minimum of that period.

    Only ok samples count; the first sample at the maximum is the peak. valid is completeness (ok samples over all samples) at least min_completeness. outdoor_c is the last hourly observation of the sensor's weather station at or before the peak
    (null when older than max_age_hours); supply_temp_c is the ok `supply_temp` sample of the root sensor of the zone in `supply` (a measurement frame) at that time, null without it.
    PROPOSED: min_completeness 0.9 (policy.grid.min_peak_completeness is needed), max_age_hours 1.5 (the age limit of the outdoor observation, as halvaro.grid.series.outdoor_at), timezone Europe/Copenhagen (the offsets of Berlin are the same).

    Args:
        zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
        sensor: The telemetry.sensor table, with the columns sns_key, zone_key, sensor_type, critical_role and station_key.
        weather_observation: The telemetry.weather_observation table, with the columns station_key, ts and temp_c.
        supply: Optional measurement frame (sns_key, ts, value, quality_flag) holding the root supply_temp samples; without it supply_temp_c and supply_temp_max_c are null. Default None.
        min_completeness: Least completeness for a valid peak, a number in [0, 1]; default 0.9 (PROPOSED).
        timezone: Time zone name of the local peak time; default Europe/Copenhagen (PROPOSED).
        max_age_hours: Oldest age in hours of the outdoor observation used for the peak, zero or more; default 1.5 (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with one row per zone and sensor, sorted by zone_key and sns_key, with the columns zone_key, sns_key, level, basis, peak_percent, peak_ts_utc, peak_ts_local, ok_samples, rows, completeness, valid, outdoor_c, supply_temp_c, supply_temp_max_c, outdoor_min_c (temperatures and percent rounded to 4 decimals).

    Raises:
        FrameError: max_age_hours is not a number of zero or more; min_completeness is not a number in [0, 1]; zone_series, sensor or weather_observation lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; telemetry.sensor has more than one row for a sns_key; the weather ts is not readable; the supply frame is not a valid measurement frame or has more than one sample for a sensor and time.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import peak_load
        >>> ctx = Context(stage="month12", role="analyst")
        >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 2, "sns_key": ["SNS-900001"] * 2, "level": ["zone"] * 2, "basis": ["load_percent"] * 2,
        ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "quality_flag": ["ok", "ok"], "ok": [True, True], "load_percent": [80.0, 95.0]})
        >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "zone_key": ["ZONE-0001"], "sensor_type": ["load_percent"], "critical_role": ["root_pump"], "station_key": ["WST-900001"]})
        >>> weather = pd.DataFrame({"station_key": ["WST-900001"] * 2, "ts": ["2026-01-10 00:00", "2026-01-10 01:00"], "temp_c": [-3.0, -5.0]})
        >>> out = peak_load(series, sensor, weather, context=ctx)
        >>> out[["peak_percent", "completeness", "valid", "outdoor_c"]].to_dict("records")
        [{'peak_percent': 95.0, 'completeness': 1.0, 'valid': True, 'outdoor_c': -5.0}]

    """
    if isinstance(max_age_hours, bool) or not isinstance(max_age_hours, (int, float, np.number)) or not np.isfinite(max_age_hours) or max_age_hours < 0:
        raise FrameError(f"max_age_hours must be a number of hours, zero or more (got {value_text(max_age_hours)})")
    z = _check_series(zone_series)
    _need(sensor, ["sns_key", "zone_key", "sensor_type", "critical_role", "station_key"], "telemetry.sensor")
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    _need(weather_observation, ["station_key", "ts", "temp_c"], "telemetry.weather_observation")
    if not isinstance(min_completeness, (int, float, np.number)) or isinstance(min_completeness, bool) or not 0 <= min_completeness <= 1:
        raise FrameError(f"min_completeness must be a number in [0, 1], not {min_completeness!r}")
    obs = weather_observation.assign(ts=_utc(weather_observation["ts"], "telemetry.weather_observation.ts").to_numpy())
    sup = None
    if supply is not None:
        sm = _checked_measurement(supply)
        sup = sm[sm["quality_flag"] == "ok"].set_index(["sns_key", "ts"])["value"]
        if sup.index.duplicated().any():
            raise FrameError("the supply frame has more than one sample for a sensor and time")
    srow = sensor.set_index("sns_key")
    rows = []
    key: Any
    ts: Any
    for (zone, key), g in z.groupby(["zone_key", "sns_key"], sort=True):
        g = g.sort_values("ts", kind="stable")
        ok = g[g["ok"]]
        n_ok, n = len(ok), len(g)
        comp = n_ok / n if n else np.nan
        if n_ok:
            i = int(np.argmax(ok["load_percent"].to_numpy(dtype=float)))
            peak, ts = float(ok["load_percent"].iloc[i]), pd.Timestamp(ok["ts"].iloc[i])
            local = ts.tz_localize("UTC").tz_convert(timezone)
        else:
            peak, ts, local = np.nan, pd.NaT, pd.NaT
        station = srow.loc[key, "station_key"]
        out_c = _outdoor(obs, station, ts, pd.Timedelta(hours=max_age_hours)) if n_ok else np.nan
        sup_c, sup_max = np.nan, np.nan
        if sup is not None and n_ok:
            roots = sensor[(sensor["zone_key"] == zone) & (sensor["critical_role"] == "root_pump") & (sensor["sensor_type"] == "supply_temp")]["sns_key"]
            lo, hi = g["ts"].min(), g["ts"].max()
            for k in roots:
                if (k, ts) in sup.index:
                    sup_c = float(sup.loc[(k, ts)])
                v = sup[(sup.index.get_level_values(0) == k) & (sup.index.get_level_values(1) >= lo) & (sup.index.get_level_values(1) <= hi)]
                if len(v):
                    sup_max = float(v.max())
        window = obs[(obs["station_key"] == station) & (obs["ts"] >= g["ts"].min()) & (obs["ts"] <= g["ts"].max())]["temp_c"]
        out_min = float(window.min()) if len(window) else np.nan
        rows.append((zone, key, g["level"].iloc[0], g["basis"].iloc[0], peak, ts, local, n_ok, n, comp, bool(n and comp >= min_completeness), out_c, sup_c, sup_max, out_min))
    out = pd.DataFrame(rows, columns=["zone_key", "sns_key", "level", "basis", "peak_percent", "peak_ts_utc", "peak_ts_local", "ok_samples", "rows", "completeness", "valid", "outdoor_c", "supply_temp_c",
                                      "supply_temp_max_c", "outdoor_min_c"])
    return out.round({"peak_percent": 4, "outdoor_c": 4, "supply_temp_c": 4, "supply_temp_max_c": 4, "outdoor_min_c": 4})


@staged(sources=(*_MEAS, "telemetry.sensor.sns_key", "telemetry.sensor.interval_s"))
def hours_above(zone_series: pd.DataFrame, sensor: pd.DataFrame, bands: Sequence[float] = _BANDS) -> pd.DataFrame:
    """Use this when you need the hours each zone or station spends above load bands such as 90, 100 and 105 percent, with the coverage of the series.

    Hours above each band: ok samples strictly above the band times the interval of the sensor, with the coverage (ok over all samples).
    PROPOSED: the bands 90, 100 and 105 percent (policy.grid.load_bands is needed).

    Args:
        zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
        sensor: The telemetry.sensor table, with the columns sns_key and interval_s; it must hold every sensor of the series.
        bands: The load bands in percent; default (90.0, 100.0, 105.0) (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, sns_key, level, band, hours_above, ok_samples, rows, coverage, one row per zone, sensor, level and band.

    Raises:
        FrameError: zone_series or sensor lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; bands is empty or holds something that is not a finite number; telemetry.sensor has more than one row for a sns_key or an interval_s that is not positive; a sensor of the series is not in telemetry.sensor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import hours_above
        >>> ctx = Context(stage="month12", role="analyst")
        >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "sns_key": ["SNS-900001"] * 3, "level": ["zone"] * 3, "basis": ["load_percent"] * 3,
        ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00", "2026-01-10 02:00"], "quality_flag": ["ok"] * 3, "ok": [True] * 3, "load_percent": [85.0, 95.0, 101.0]})
        >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [3600]})
        >>> out = hours_above(series, sensor, bands=[90.0, 100.0], context=ctx)
        >>> out["hours_above"].tolist()
        [2.0, 1.0]

    """
    z = _check_series(zone_series)
    b = list(bands)
    if not b or not all(isinstance(x, (int, float, np.number)) and not isinstance(x, bool) and np.isfinite(x) for x in b):
        raise FrameError(f"bands must be a list of numbers (got {value_text(bands)})")
    hours = _hours(sensor, z)
    rows = []
    key: Any
    for (zone, key, level), g in z.groupby(["zone_key", "sns_key", "level"], sort=True):
        v = g.loc[g["ok"], "load_percent"].to_numpy(dtype=float)
        for band in b:
            rows.append((zone, key, level, float(band), round(float((v > band).sum()) * float(hours.loc[key]), 4), len(v), len(g), len(v) / len(g) if len(g) else np.nan))
    return pd.DataFrame(rows, columns=["zone_key", "sns_key", "level", "band", "hours_above", "ok_samples", "rows", "coverage"])


def _winter(ts: pd.Series[Any], months: Any) -> tuple[Any, ...]:
    m = ts.dt.month
    y0 = ts.dt.year.astype("Int64").where(m >= 7, ts.dt.year.astype("Int64") - 1)
    label = y0.astype("string") + "/" + (y0 + 1).astype("string").str[2:]
    return m.isin(list(months)).fillna(False), label.astype(object)


@staged(sources=("telemetry.measurement.ts",), oracle="py:halvaro_gen/world/telemetry/truth.py::winter_label")
def winter_label(ts: TimesLike, *, months: Sequence[int] = _WINTER_MONTHS) -> str | None | pd.Series:
    """Use this when you need the winter season of a timestamp or a series of timestamps as a label such as 2025/26.

    The label is like '2025/26' (the season starts in July, so January 2026 is 2025/26) and null outside the winter months. A timestamp gives text or None, a Series gives a Series.
    PROPOSED: the months November to March (policy.grid.winter_window is needed).

    Args:
        ts: A timestamp, or a list, tuple, array, Index or Series of timestamps (UTC without time zone).
        months: The month numbers 1 to 12 that count as winter; default (11, 12, 1, 2, 3) (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The label as text, or None outside the winter months, for one timestamp; a Series of labels (None outside the winter months) for several, with the index of ts when it is a Series.

    Raises:
        FrameError: months is empty or holds something that is not a month number 1 to 12; ts holds numbers, a time zone or a value that is not a timestamp.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> from halvaro.core import Context
        >>> from halvaro.grid import winter_label
        >>> ctx = Context(stage="month12", role="analyst")
        >>> winter_label("2026-01-15 12:00", context=ctx)
        '2025/26'
        >>> winter_label("2026-06-15 12:00", context=ctx) is None
        True
        >>> winter_label(["2025-12-01", "2026-07-01"], context=ctx).tolist()
        ['2025/26', None]

    """
    mo = list(months)
    if not mo or not all(isinstance(x, (int, np.integer)) and 1 <= x <= 12 for x in mo):
        raise FrameError(f"months must be a list of month numbers 1 to 12 (got {value_text(months)})")
    scalar = not isinstance(ts, (pd.Series, pd.Index, list, tuple, np.ndarray))
    s = _utc([ts] if scalar else ts, "ts")
    inside, label = _winter(s, mo)
    if scalar:
        return label.iloc[0] if bool(inside.iloc[0]) else None
    return pd.Series(label.where(inside, None).to_numpy(), index=ts.index if isinstance(ts, pd.Series) else None, dtype=object)


@staged(sources=(*_MEAS, "telemetry.sensor.sns_key", "telemetry.sensor.interval_s"))
def load_duration_curve(zone_series: pd.DataFrame, sensor: pd.DataFrame, *, winter_only: bool = False, by_winter: bool = False, months: Sequence[int] = _WINTER_MONTHS) -> pd.DataFrame:
    """Use this when you need the load duration curve of each zone or station: the ok load, highest first, against the hours it is reached or exceeded.

    Rank k has hours k times the interval of the sensor. With winter_only only the samples of the winter months count. Ties keep their time order. With by_winter one curve per winter (a winter column, the months of the winter only).
    The hours count ok samples, so a gap in the series shortens the curve (the coverage is in hours_above).

    Args:
        zone_series: The output of zone_load_percent, with the columns zone_key, sns_key, level, basis, ts, quality_flag, ok and load_percent.
        sensor: The telemetry.sensor table, with the columns sns_key and interval_s; it must hold every sensor of the series.
        winter_only: Count only the samples of the winter months; default False.
        by_winter: Give one curve per winter with a winter column (this also keeps only the winter months); default False.
        months: The month numbers 1 to 12 that count as winter; default (11, 12, 1, 2, 3) (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, sns_key, [winter,] rank, hours, load_percent, sorted by zone_key and sns_key (and winter) with the highest load first; empty when no sample is ok.

    Raises:
        FrameError: zone_series or sensor lacks a column; zone_series has a null zone_key or sns_key or a ts that is not a timestamp; telemetry.sensor has more than one row for a sns_key or an interval_s that is not positive; a sensor of the series is not in telemetry.sensor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import load_duration_curve
        >>> ctx = Context(stage="month12", role="analyst")
        >>> series = pd.DataFrame({"zone_key": ["ZONE-0001"] * 3, "sns_key": ["SNS-900001"] * 3, "level": ["zone"] * 3, "basis": ["load_percent"] * 3,
        ...                        "ts": ["2026-01-10 00:00", "2026-01-10 01:00", "2026-01-10 02:00"], "quality_flag": ["ok"] * 3, "ok": [True] * 3, "load_percent": [85.0, 95.0, 90.0]})
        >>> sensor = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [3600]})
        >>> out = load_duration_curve(series, sensor, context=ctx)
        >>> out["load_percent"].tolist()
        [95.0, 90.0, 85.0]
        >>> out["hours"].tolist()
        [1.0, 2.0, 3.0]

    """
    z = _check_series(zone_series)
    hours = _hours(sensor, z)
    ok = z[z["ok"]].reset_index(drop=True)
    inside, label = _winter(ok["ts"], months)
    if winter_only or by_winter:
        ok = ok[inside.to_numpy()].assign(winter=label[inside.to_numpy()].to_numpy())
    keys = ["zone_key", "sns_key"] + (["winter"] if by_winter else [])
    parts = []
    k: Any
    for k, g in ok.groupby(keys, sort=True):
        k = k if isinstance(k, tuple) else (k,)
        v = g.sort_values(["load_percent", "ts"], ascending=[False, True], kind="stable")["load_percent"].to_numpy(dtype=float)
        d = {"zone_key": k[0], "sns_key": k[1]}
        if by_winter:
            d["winter"] = k[2]
        parts.append(pd.DataFrame({**d, "rank": np.arange(1, len(v) + 1), "hours": np.arange(1, len(v) + 1) * float(hours.loc[k[1]]), "load_percent": v}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=[*keys, "rank", "hours", "load_percent"])


@staged(sources=("telemetry.sensor.zone_key", "telemetry.sensor.critical_role"))
def rank_zones(summary: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the heat zones ranked on the peak load of their root, with the electric stations listed below without a rank.

    Ranks the heat zones on the peak percent of their root (valid peaks only, highest first) and lists the electric stations below with rank null and their basis, because a station percent is not comparable with a zone percent (T9).
    A zone with an invalid peak is listed with rank null.

    Args:
        summary: The output of peak_load, with the columns zone_key, sns_key, level, basis, peak_percent and valid.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns rank, zone_key, sns_key, level, basis, peak_percent, valid: ranked zones first (rank 1.0, 2.0, ...), then the rest sorted by zone_key and sns_key with rank null.

    Raises:
        FrameError: summary is not a DataFrame or lacks one of the columns zone_key, sns_key, level, basis, peak_percent or valid.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import rank_zones
        >>> ctx = Context(stage="month12", role="analyst")
        >>> summary = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0003", "ZONE-0004"], "sns_key": ["SNS-900001", "SNS-900002", "SNS-900003"],
        ...                         "level": ["zone", "zone", "station"], "basis": ["load_percent", "load_percent", "station"],
        ...                         "peak_percent": [61.0, 84.0, 70.0], "valid": [True, True, True]})
        >>> out = rank_zones(summary, context=ctx)
        >>> out["zone_key"].tolist()
        ['ZONE-0003', 'ZONE-0001', 'ZONE-0004']
        >>> out["rank"].tolist()
        [1.0, 2.0, nan]

    """
    _need(summary, ["zone_key", "sns_key", "level", "basis", "peak_percent", "valid"], "peak_load output")
    summary = summary.reset_index(drop=True)
    heat = summary[summary["level"] == "zone"].copy()
    usable = heat[heat["valid"] & heat["peak_percent"].notna()].sort_values(["peak_percent", "zone_key"], ascending=[False, True])
    usable["rank"] = np.arange(1, len(usable) + 1).astype(float)
    rest = pd.concat([heat.drop(usable.index), summary[summary["level"] != "zone"]]).assign(rank=np.nan).sort_values(["zone_key", "sns_key"])
    out = pd.concat([usable, rest], ignore_index=True)
    return out[["rank", "zone_key", "sns_key", "level", "basis", "peak_percent", "valid"]]


@staged(sources=("telemetry.weather_daily.zone_key", "telemetry.weather_daily.date", "telemetry.weather_daily.t_min"), facts=("policy.grid.cold_snap_min_core_days",),
        oracle="py:tests/test_telemetry.py::test_weather")
def cold_snaps(weather_daily: pd.DataFrame, *, core_c: float = -8.0, edge_c: float = -4.0, min_core_days: int | None = None) -> pd.DataFrame:
    """Use this when you need the cold snaps of each zone found from the daily minimum temperatures.

    A cold snap has a core of at least min_core_days consecutive days with t_min at or below core_c, extended on both sides over days with t_min at or below edge_c.
    PROPOSED: -8, -4 and 2 days (policy.grid.cold_snap; the rule is new, the dates of the configured snap are a test value only and never used to find one). Dates are UTC days of the weather table.
    `min_core_days` None (default) reads the proposed fact policy.grid.cold_snap_min_core_days (2; owner decision of 2026-11-13, D12); pass a number to override.

    Args:
        weather_daily: The telemetry.weather_daily table, with the columns zone_key, date and t_min.
        core_c: Temperature in degrees C at or below which a day belongs to the core; default -8.0 (PROPOSED).
        edge_c: Temperature in degrees C at or below which a day extends the snap around its core, not below core_c; default -4.0 (PROPOSED).
        min_core_days: Least number of consecutive core days, a whole number of at least 1; None (default) reads the fact policy.grid.cold_snap_min_core_days.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns zone_key, start, end (both days inclusive), days, core_days, t_min (lowest), t_min_date, one row per cold snap, ordered by zone_key and start.

    Raises:
        FrameError: weather_daily is not a DataFrame or lacks zone_key, date or t_min; core_c or edge_c is not a finite number; edge_c is below core_c or min_core_days is not a whole number of at least 1; date is not a UTC timestamp; zone_key or date is null; a zone has more than one row for a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import cold_snaps
        >>> ctx = Context(stage="month12", role="analyst")
        >>> days = pd.DataFrame({"zone_key": ["ZONE-0001"] * 5, "date": pd.date_range("2026-01-10", periods=5), "t_min": [-3.0, -9.0, -10.0, -5.0, 0.0]})
        >>> out = cold_snaps(days, min_core_days=2, context=ctx)
        >>> out["start"].dt.strftime("%Y-%m-%d").tolist(), out["end"].dt.strftime("%Y-%m-%d").tolist()
        (['2026-01-11'], ['2026-01-13'])
        >>> out[["days", "core_days", "t_min"]].to_dict("records")
        [{'days': 3, 'core_days': 2, 't_min': -10.0}]

    """
    if min_core_days is None:
        min_core_days = int(fact("policy.grid.cold_snap_min_core_days").value)
    _need(weather_daily, ["zone_key", "date", "t_min"], "telemetry.weather_daily")
    for name, v in (("core_c", core_c), ("edge_c", edge_c)):
        if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not np.isfinite(v):
            raise FrameError(f"{name} must be a number (got {value_text(v)})")
    if edge_c < core_c or not isinstance(min_core_days, (int, np.integer)) or isinstance(min_core_days, bool) or min_core_days < 1:
        raise FrameError(f"edge_c must not be below core_c and min_core_days must be a whole number of at least 1 (got edge_c {edge_c!r}, core_c {core_c!r}, min_core_days {min_core_days!r})")
    w = weather_daily.assign(date=_utc(weather_daily["date"], "telemetry.weather_daily.date").dt.normalize().to_numpy())
    if w[["zone_key", "date"]].isna().any().any():
        raise FrameError("telemetry.weather_daily has null zone_key or date")
    if w.duplicated(["zone_key", "date"]).any():
        raise FrameError("telemetry.weather_daily has more than one row for a zone and date")
    rows = []
    for zone, g in w.sort_values("date").groupby("zone_key", sort=True):
        g = g.reset_index(drop=True)
        days = (g["date"].diff() != pd.Timedelta(days=1)).cumsum()
        t = g["t_min"].to_numpy(dtype=float)
        core = (t <= core_c) & ~np.isnan(t)
        edge = (t <= edge_c) & ~np.isnan(t)
        run = (core != np.roll(core, 1)).cumsum() + days.to_numpy() * 10 ** 6
        used = set()
        for _, idx in pd.Series(np.arange(len(g))).groupby(run):
            i = idx.to_numpy()
            if not core[i[0]] or len(i) < min_core_days:
                continue
            a, b = i[0], i[-1]
            while a > 0 and edge[a - 1] and g["date"].iloc[a] - g["date"].iloc[a - 1] == pd.Timedelta(days=1):
                a -= 1
            while b < len(g) - 1 and edge[b + 1] and g["date"].iloc[b + 1] - g["date"].iloc[b] == pd.Timedelta(days=1):
                b += 1
            if a in used:
                continue
            used.add(a)
            seg = g.iloc[a:b + 1]
            rows.append((zone, seg["date"].iloc[0], seg["date"].iloc[-1], len(seg), int(core[a:b + 1].sum()), float(seg["t_min"].min()), seg.loc[seg["t_min"].idxmin(), "date"]))
    return pd.DataFrame(rows, columns=["zone_key", "start", "end", "days", "core_days", "t_min", "t_min_date"])
