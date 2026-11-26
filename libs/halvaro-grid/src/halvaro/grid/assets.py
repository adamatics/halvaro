"""Asset condition and strain (plan 5.7): score trend of a group, peak load per element with its own sensor, strained elements and a summary by zone and customer.

Strain is a proposal (policy.grid.strained_element, needed, LOW): in service and (load strained or age strained). Thresholds are keywords marked PROPOSED.
"""
from __future__ import annotations

from typing import Any, Iterable, NamedTuple, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import _need, _utc
from ._types import DateLike, Window
from .geometry import element_age
from ._tail import value_text


class ConditionTrend(NamedTuple):
    """Mean score of the last assessment before a date and of the assessments from a later date, for a group, and the check of the last assessment against the gis score of all assessed elements."""
    n_before: int
    mean_before: float
    n_after: int
    mean_after: float
    change: float
    n_assessed: int
    last_vs_gis_mean: float
    last_vs_gis_sd: float


@staged(sources=("service.condition_assessment.net_key", "service.condition_assessment.assessed_on", "service.condition_assessment.score", "gis.grid_element.net_key", "gis.grid_element.condition_score"),
        oracle="py:tests/test_service.py::test_condition_assessments")
def condition_trend(condition_assessment: pd.DataFrame, grid_element: pd.DataFrame, group: Iterable[Any], before: DateLike, after: DateLike) -> ConditionTrend:
    """Use this when you need the change of the condition score of a group of elements between two dates, checked against the gis score.

    Score change of a group over two dates: the mean of each group element's last assessment strictly before `before`, the mean of the group's assessments on or after `after` (one value per
    element: its first assessment from that date), the change (after less before), and for all assessed elements the mean and standard deviation of the last assessment less the gis condition score.
    Elements without an assessment in a period are not in that mean (n_before, n_after count the elements). `before` must not be after `after`. An element twice on one date raises FrameError.

    Args:
        condition_assessment: The service.condition_assessment table; it needs the columns net_key, assessed_on and score.
        grid_element: The gis.grid_element table; it needs the columns net_key and condition_score.
        group: One net_key or an iterable of net_keys, the elements of the group.
        before: The first date; the last assessment strictly before it counts as the earlier state.
        after: The second date; the first assessment on or after it counts as the later state; not before `before`.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ConditionTrend with the fields n_before, mean_before, n_after, mean_after, change (after less before), n_assessed, last_vs_gis_mean and last_vs_gis_sd, all rounded to three decimals. A mean or the change is NaN when its period has no assessed element; the standard deviation is NaN with fewer than two assessed elements.

    Raises:
        FrameError: a needed column is missing; the group has no element; before or after is not a date or before is after after; an element has two assessments on one date; a score is null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import condition_trend
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ca = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900002"], "assessed_on": ["2020-01-01", "2022-01-01", "2020-06-01"], "score": [80.0, 60.0, 70.0]})
        >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "condition_score": [58.0, 72.0]})
        >>> t = condition_trend(ca, ge, ["NET-900001", "NET-900002"], "2021-01-01", "2021-06-01", context=ctx)
        >>> (t.n_before, t.mean_before, t.n_after, t.change)
        (2, 75.0, 1, -15.0)
"""
    _need(condition_assessment, ["net_key", "assessed_on", "score"], "service.condition_assessment")
    _need(grid_element, ["net_key", "condition_score"], "gis.grid_element")
    members = set([group] if isinstance(group, str) else group)
    if not members:
        raise FrameError("the group has no element")
    b, a = _utc([before], "before").iloc[0], _utc([after], "after").iloc[0]
    if pd.isna(a) or pd.isna(b) or b > a:
        raise FrameError(f"before and after are dates with before not after after (got before {before!r}, after {after!r})")
    ca = condition_assessment.assign(_d=_utc(condition_assessment["assessed_on"], "service.condition_assessment.assessed_on").to_numpy())
    if ca.duplicated(["net_key", "_d"]).any():
        raise FrameError("service.condition_assessment has two assessments of one element on one date")
    if ca["score"].isna().any():
        raise FrameError("service.condition_assessment has a null score")
    g = ca[ca["net_key"].isin(members)]
    pre = g[g["_d"] < b].sort_values(["net_key", "_d"]).drop_duplicates("net_key", keep="last")
    post = g[g["_d"] >= a].sort_values(["net_key", "_d"]).drop_duplicates("net_key", keep="first")
    mb = float(pre["score"].mean()) if len(pre) else np.nan
    ma = float(post["score"].mean()) if len(post) else np.nan
    last = ca.sort_values(["net_key", "_d"]).drop_duplicates("net_key", keep="last").merge(grid_element[["net_key", "condition_score"]], on="net_key", how="inner").dropna(subset=["condition_score"])
    diff = last["score"].astype(float) - last["condition_score"].astype(float)
    return ConditionTrend(len(pre), round(mb, 3), len(post), round(ma, 3), round(ma - mb, 3) if len(pre) and len(post) else np.nan, len(last), round(float(diff.mean()), 3) if len(diff) else np.nan,
                          round(float(diff.std(ddof=1)), 3) if len(diff) > 1 else np.nan)


@staged(sources=("telemetry.sensor.sns_key", "telemetry.sensor.net_key", "telemetry.sensor.sensor_type", "telemetry.sensor.install_date", "telemetry.measurement_daily.sns_key",
                 "telemetry.measurement_daily.date", "telemetry.measurement_daily.max", "telemetry.measurement_daily.availability_pct"), oracle="py:repo_tests/test_oracle_assets_release.py::test_oracle_element_peak_load_baseline_per_element")
def element_peak_load(sensor: pd.DataFrame, measurement_daily: pd.DataFrame, *, window: Window | None = None, min_completeness: float = 0.9, sensor_type: str = "load_percent") -> pd.DataFrame:
    """Use this when you need the peak load in percent of each element that has its own load sensor, with the completeness that says whether the peak can be trusted.

    Peak load in percent for each element with its own load sensor (`sensor_type`, default load_percent: sensors whose value is already a percent of their rated value), from the daily
    maxima of the ok samples; elements without such a sensor are not listed (null in a join). Other sensor types (kW, A, kV, m3/h) are in their own units and are not converted.

    Args:
        sensor: The telemetry.sensor table; it needs the columns sns_key, net_key, rated_value, install_date and sensor_type.
        measurement_daily: The telemetry.measurement_daily table; it needs the columns sns_key, date, max and availability_pct.
        window: An optional (first, last) pair of days that limits the daily rows; the first day must not be after the last. Without it the window runs from the first to the last day of the rows passed in, and a day without a row counts as zero availability, so completeness depends on the rows passed: pass the window when the share matters.
        min_completeness: The share from 0 to 1 of the days with data that makes a peak valid, PROPOSED 0.9, policy.grid.min_peak_completeness.
        sensor_type: The sensor type that is used, default load_percent.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per net_key, sorted by net_key, with the columns net_key, sns_key, peak_percent (highest daily maximum of the ok samples as stored: for load_percent sensors that already is a percent of the rated value; with several sensors the highest, valid or not), peak_date, days (days with data
        in the window), completeness (mean of the daily availability_pct over the days from the later of the window start and the sensor install date to the window end, as a share) and valid (completeness at least
        `min_completeness`). A sensor without data has a null peak and completeness 0.

    Raises:
        FrameError: a needed column is missing; min_completeness is not a share from 0 to 1; a rated_value is not above zero; telemetry.sensor has more than one row for a sns_key; telemetry.measurement_daily has more than one row for a sensor and day; a date is not readable; window is not a (first, last) pair of days in order.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import element_peak_load
        >>> ctx = Context(stage="month12", role="analyst")
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "net_key": ["NET-900001"], "rated_value": [100.0], "install_date": ["2019-01-01"], "sensor_type": ["load_percent"]})
        >>> md = pd.DataFrame({"sns_key": ["SNS-900001"] * 2, "date": ["2020-01-01", "2020-01-02"], "max": [55.0, 72.5], "availability_pct": [100.0, 100.0]})
        >>> out = element_peak_load(s, md, context=ctx)
        >>> out[["net_key", "peak_percent", "days", "valid"]].to_dict("records")
        [{'net_key': 'NET-900001', 'peak_percent': 72.5, 'days': 2, 'valid': True}]
"""
    _need(sensor, ["sns_key", "net_key", "rated_value", "install_date", "sensor_type"], "telemetry.sensor")
    _need(measurement_daily, ["sns_key", "date", "max", "availability_pct"], "telemetry.measurement_daily")
    if isinstance(min_completeness, bool) or not isinstance(min_completeness, (int, float)) or not 0 <= min_completeness <= 1:
        raise FrameError(f"min_completeness is a share from 0 to 1 (got {value_text(min_completeness)})")
    s = sensor[sensor["net_key"].notna() & (sensor["sensor_type"] == sensor_type)]
    if (s["rated_value"].dropna() <= 0).any():
        raise FrameError("rated_value must be above zero")
    if s["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    measurement_daily = measurement_daily.reset_index(drop=True)
    md = measurement_daily.assign(_d=_utc(measurement_daily["date"], "telemetry.measurement_daily.date").to_numpy())
    if md.duplicated(["sns_key", "_d"]).any():
        raise FrameError("telemetry.measurement_daily has more than one row for a sensor and day")
    if window is not None:
        w0, w1 = _utc([window[0]], "window start").iloc[0], _utc([window[1]], "window end").iloc[0]
        if pd.isna(w0) or pd.isna(w1) or w0 > w1:
            raise FrameError(f"window is a (first, last) pair of days in order (got {value_text(window)})")
        md = md[(md["_d"] >= w0) & (md["_d"] <= w1)]
    else:
        w0, w1 = md["_d"].min(), md["_d"].max()
    md = md[md["sns_key"].isin(set(s["sns_key"]))]
    rows = []
    last = w1
    for r in s.itertuples():
        g = md[md["sns_key"] == r.sns_key]
        inst = _utc([r.install_date], "install_date").iloc[0]
        start = (max(w0, inst.normalize()) if pd.notna(inst) else w0) if pd.notna(w0) else pd.NaT
        n = (last - start).days + 1 if pd.notna(start) and pd.notna(last) and last >= start else 0
        comp = float(g["availability_pct"].sum() / 100.0 / n) if n > 0 else 0.0
        gv = g.dropna(subset=["max"])
        if gv.empty:
            rows.append({"net_key": r.net_key, "sns_key": r.sns_key, "peak_percent": np.nan, "peak_date": pd.NaT, "days": 0, "completeness": round(comp, 4), "valid": False})
            continue
        i = gv["max"].idxmax()
        rows.append({"net_key": r.net_key, "sns_key": r.sns_key, "peak_percent": round(float(cast(Any, gv.at[i, "max"])), 3), "peak_date": gv.at[i, "_d"], "days": int(len(gv)),
                     "completeness": round(comp, 4), "valid": comp >= min_completeness})
    out = pd.DataFrame(rows, columns=["net_key", "sns_key", "peak_percent", "peak_date", "days", "completeness", "valid"])
    if out.empty:
        return out
    out = out.sort_values(["net_key", "peak_percent", "sns_key"], ascending=[True, False, True], na_position="last").drop_duplicates("net_key", keep="first")
    return out.reset_index(drop=True)


@staged(sources=("gis.grid_element.net_key", "gis.grid_element.element_type", "gis.grid_element.status", "gis.grid_element.install_year", "gis.grid_element.condition_class", "gis.grid_element.cus_key",
                 "gis.grid_element.zone_key", "gis.grid_element.commissioned_date", "crm.customer.cus_key", "crm.customer.name"), facts=("world.now",), oracle="py:repo_tests/test_oracle_assets_release.py::test_oracle_strained_elements_baseline_per_element")
def strained_elements(element_peaks: pd.DataFrame, grid_element: pd.DataFrame, customer: pd.DataFrame | None = None, *, as_of: DateLike | None = None, load_percent: float = 90.0, bad_classes: tuple[str, ...] = ("D", "E"),
                      age_years: float = 40.0, types: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Use this when you need to know which in service elements are strained by load or by age or condition class, with the reasons.

    The age is that of `element_age` (two decimals), so an element one day short of `age_years` counts as age strained.

    Strain per in service element: load strained (own valid peak at or above `load_percent` of the rated value, PROPOSED 90; unknown without a valid peak), age strained (condition class in
    `bad_classes`, PROPOSED D and E, or age at least `age_years`, PROPOSED 40), and strained: true when either is true, false when the load is known to be below and the age is not strained, null (unknown) when the load is unknown and the age is not strained (T19: unknown is not 'not strained'). Reported separately: load_strained (null when unknown), age_strained, reasons.
    The rule is policy.grid.strained_element (needed, LOW). Customer names come from the crm customer frame (cus_key, name) when given.

    Args:
        element_peaks: The output of element_peak_load; it needs the columns net_key, peak_percent and valid.
        grid_element: The gis.grid_element table; it needs the columns net_key, element_type, status, install_year, condition_class, cus_key, zone_key and commissioned_date, one row per net_key.
        customer: The crm.customer table with the columns cus_key and name, or None for no customer names.
        as_of: The date the age is measured on; defaults to world.now.
        load_percent: The peak percent at or above which the load is strained, PROPOSED 90.0.
        bad_classes: The condition classes that count as strained, PROPOSED D and E; a tuple or list, not a string.
        age_years: The age in years at or above which the element is age strained, PROPOSED 40.0.
        types: Limits the element types (for the switchgear link of the supply strain question: substation and transformer_station); None keeps all types; a tuple or list, not a string.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by net_key with the columns net_key, element_type, zone_key, cus_key, customer_name, peak_percent, load_strained, age_years, condition_class, age_strained, strained, reasons.

    Raises:
        FrameError: a needed column is missing; element_peaks or gis.grid_element has more than one row for a net_key; types or bad_classes is a string; a date or an install_year cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import strained_elements
        >>> ctx = Context(stage="month12", role="analyst")
        >>> peaks = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "peak_percent": [95.0, 40.0], "valid": [True, True]})
        >>> ge = pd.DataFrame({"net_key": ["NET-900001", "NET-900002", "NET-900003"], "element_type": ["cable"] * 3, "status": ["in_service"] * 2 + ["planned"],
        ...                    "install_year": [2015, 2015, 2015], "condition_class": ["B", "B", "B"], "cus_key": [None] * 3, "zone_key": ["ZONE-0001"] * 3, "commissioned_date": [None] * 3})
        >>> out = strained_elements(peaks, ge, as_of="2020-01-01", context=ctx)
        >>> out["net_key"].tolist(), out["strained"].tolist()
        (['NET-900001', 'NET-900002'], [True, False])
"""
    _need(element_peaks, ["net_key", "peak_percent", "valid"], "element_peak_load output")
    _need(grid_element, ["net_key", "element_type", "status", "install_year", "condition_class", "cus_key", "zone_key", "commissioned_date"], "gis.grid_element")
    if element_peaks["net_key"].duplicated().any() or grid_element["net_key"].duplicated().any():
        raise FrameError("element peaks and gis.grid_element need one row per net_key")
    for nm, v in (("types", types), ("bad_classes", bad_classes)):
        if isinstance(v, (str, bytes)):
            raise FrameError(f"{nm} must be a tuple or list of values, not {v!r}")
    ge = grid_element[grid_element["status"] == "in_service"]
    if types is not None:
        ge = ge[ge["element_type"].isin(list(types))]
    ages = unwrapped(element_age)(ge, as_of)
    x = ge[["net_key", "element_type", "zone_key", "cus_key", "condition_class"]].copy()
    x["age_years"] = ages.to_numpy()
    pk = element_peaks.set_index("net_key")
    x["peak_percent"] = x["net_key"].map(pk["peak_percent"].where(pk["valid"].fillna(False).astype(bool)))
    x["load_strained"] = pd.array(np.where(x["peak_percent"].notna(), x["peak_percent"] >= load_percent, pd.NA), dtype="boolean")
    x["age_strained"] = (x["condition_class"].isin(list(bad_classes)) | (x["age_years"] >= age_years)).to_numpy()
    ls = x["load_strained"]
    x["strained"] = pd.array(np.where(ls.fillna(False).astype(bool).to_numpy() | x["age_strained"].to_numpy(), True, np.where(ls.isna().to_numpy(), pd.NA, False)), dtype="boolean")
    x["reasons"] = [",".join(r for r, f in (("load", l is True), ("class", c in bad_classes), ("age", (a == a) and a >= age_years)) if f) for l, c, a in zip(x["load_strained"].astype(object), x["condition_class"], x["age_years"])]
    if customer is not None:
        _need(customer, ["cus_key", "name"], "crm.customer")
        x["customer_name"] = x["cus_key"].map(customer.drop_duplicates("cus_key").set_index("cus_key")["name"])
    else:
        x["customer_name"] = None
    return x[["net_key", "element_type", "zone_key", "cus_key", "customer_name", "peak_percent", "load_strained", "age_years", "condition_class", "age_strained", "strained", "reasons"]].sort_values("net_key").reset_index(drop=True)


@staged(sources=("gis.supply_zone.zone_key", "gis.supply_zone.area_km2"), oracle="py:repo_tests/test_oracle_assets_release.py::test_oracle_zone_strain_summary_baseline_per_zone_and_customer")
def zone_strain_summary(strained: pd.DataFrame, supply_zone: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the counts of in service and strained elements by zone and customer, with the zone area.

    Counts of in service elements and of strained elements (load, age, either) by zone and customer, with the zone area. Elements of a zone that is not in gis.supply_zone raise FrameError.
    An element without a customer is counted under the customer key "-". strained_per_km2 is null without an area above zero.

    Args:
        strained: The output of strained_elements; it needs the columns net_key, zone_key, cus_key, load_strained, age_strained and strained.
        supply_zone: The gis.supply_zone table; it needs the columns zone_key and area_km2, one row per zone_key.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with one row per zone and customer and the columns zone_key, cus_key, area_km2, n_elements, n_strained (true only), n_strained_unknown, n_load_strained,
        n_age_strained, n_load_unknown, strained_per_km2 (strained elements per square kilometre, rounded to three decimals).

    Raises:
        FrameError: a needed column is missing; gis.supply_zone has more than one row for a zone_key; a zone of the elements is not in gis.supply_zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import zone_strain_summary
        >>> ctx = Context(stage="month12", role="analyst")
        >>> st = pd.DataFrame({"net_key": ["NET-900001", "NET-900002"], "zone_key": ["ZONE-0001"] * 2, "cus_key": [None, None],
        ...                    "load_strained": [True, False], "age_strained": [False, False], "strained": [True, False]})
        >>> z = pd.DataFrame({"zone_key": ["ZONE-0001"], "area_km2": [4.0]})
        >>> zone_strain_summary(st, z, context=ctx)[["zone_key", "cus_key", "n_elements", "n_strained", "strained_per_km2"]].to_dict("records")
        [{'zone_key': 'ZONE-0001', 'cus_key': '-', 'n_elements': 2, 'n_strained': 1, 'strained_per_km2': 0.25}]
"""
    _need(strained, ["net_key", "zone_key", "cus_key", "load_strained", "age_strained", "strained"], "strained_elements output")
    _need(supply_zone, ["zone_key", "area_km2"], "gis.supply_zone")
    if supply_zone["zone_key"].duplicated().any():
        raise FrameError("gis.supply_zone has more than one row for a zone_key")
    unknown = sorted(set(strained["zone_key"].dropna()) - set(supply_zone["zone_key"]))
    if unknown:
        raise FrameError(f"zone {unknown[0]} is not in gis.supply_zone")
    x = strained.assign(cus_key=strained["cus_key"].astype(object).where(strained["cus_key"].notna(), "-"))
    g = x.groupby(["zone_key", "cus_key"], as_index=False).agg(n_elements=("net_key", "size"), n_strained=("strained", lambda s: int((s == True).sum())), n_strained_unknown=("strained", lambda s: int(s.isna().sum())), n_load_strained=("load_strained", lambda s: int((s == True).sum())),
                                                               n_age_strained=("age_strained", lambda s: int(s.astype(bool).sum())), n_load_unknown=("load_strained", lambda s: int(s.isna().sum())))
    g = g.merge(supply_zone[["zone_key", "area_km2"]], on="zone_key", how="left")
    g["strained_per_km2"] = np.where(g["area_km2"] > 0, (g["n_strained"] / g["area_km2"].where(g["area_km2"] > 0)).round(3), np.nan)
    g[["n_strained", "n_age_strained", "n_load_strained", "n_load_unknown", "n_strained_unknown"]] = g[["n_strained", "n_age_strained", "n_load_strained", "n_load_unknown", "n_strained_unknown"]].astype(int)
    return g[["zone_key", "cus_key", "area_km2", "n_elements", "n_strained", "n_strained_unknown", "n_load_strained", "n_age_strained", "n_load_unknown", "strained_per_km2"]]
