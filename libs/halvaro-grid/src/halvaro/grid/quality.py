"""Quality of the telemetry samples: which samples count, how complete a sensor is, where the gaps are, what explains a flag, the daily aggregates from raw samples and the weekly quality board.

Rule (KB K04): only samples flagged `ok` count. `estimated` (interpolated dropout), `suspect` (spike, flatline, drift) and `missing` (null value) are kept visible and never filled or zeroed.
Timestamps are UTC without zone, the daily `date` is a UTC date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import FLAGS, _checked_measurement, _need, _positive_interval, _utc
from ._types import DateLike
from ._tail import value_text

_MEASUREMENT = ("telemetry.measurement.sns_key", "telemetry.measurement.ts", "telemetry.measurement.value", "telemetry.measurement.quality_flag")
_EVENT_FOR_FLAG = {"missing": ("dropout",), "estimated": ("dropout",), "suspect": ("spike", "flatline", "drift")}


@staged(sources=_MEASUREMENT, oracle="py:tests/test_telemetry.py::test_daily_aggregates_equal_raw")
def valid_samples(measurement: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need only the samples that count, those flagged ok with a value, sorted by sensor and time.

    Estimated, suspect and missing samples are dropped, never filled or zeroed. An unknown flag, a duplicated slot or a time zone raises FrameError.

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns of the input, only the ok samples with a value, sorted by sns_key and ts, with a fresh index.

    Raises:
        FrameError: a column of measurement is missing, ts holds numbers, unreadable text or a time zone, a row has no sns_key or ts, quality_flag is null or not one of the known flags, or a sensor has two rows for the same ts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import valid_samples
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
        ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
        >>> valid_samples(m, context=ctx)["value"].tolist()
        [1.0, 4.0]
"""
    m = _checked_measurement(measurement)
    return m[(m["quality_flag"] == "ok") & m["value"].notna()].reset_index(drop=True)


@staged(sources=(*_MEASUREMENT, "telemetry.sensor.sns_key", "telemetry.sensor.install_date", "telemetry.sensor.interval_s"), oracle="py:tests/test_telemetry.py::test_data_quality_layer")
def completeness(measurement: pd.DataFrame, sensor: pd.DataFrame, window_start: DateLike, window_end: DateLike) -> pd.DataFrame:
    """Use this when you need the share of expected slots that hold an ok sample per sensor over a window of days.

    The window runs over the days window_start to window_end inclusive (UTC). Expected slots run from the later of the window start and the install date (midnight) to the end of the last day, one per interval_s.
    A sensor without rows is listed with zeros. A sensor whose first sample comes hours after the midnight of its install date has expected slots without rows, which `share` counts as lost and `share_of_present`
    does not. The minimum share for a peak (policy.grid.min_peak_completeness) is not applied here.

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        sensor: The telemetry.sensor frame, columns sns_key, install_date and interval_s, one row per sensor.
        window_start: First day of the window (a date or date text, UTC).
        window_end: Last day of the window, inclusive.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns sns_key, expected, rows, ok, estimated, suspect, missing, share (ok over expected) and share_of_present (ok over the rows that exist), sorted by sns_key.
        share and share_of_present are null where there are no expected slots or no rows.

    Raises:
        FrameError: a column of sensor or measurement is missing, the measurement is invalid (see valid_samples), window_start or window_end is not a date, the window ends before it starts, telemetry.sensor repeats a sns_key,
            has a missing or not positive interval_s or an empty install_date, a measured sensor is not in telemetry.sensor, or a sensor has more rows in the window than slots after its install date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import completeness
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
        ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "install_date": ["2025-03-01"], "interval_s": [900]})
        >>> out = completeness(m, s, "2025-03-01", "2025-03-01", context=ctx)
        >>> out[["sns_key", "expected", "rows", "ok"]].to_dict("records")
        [{'sns_key': 'SNS-900001', 'expected': 96, 'rows': 4, 'ok': 2}]
        >>> out["share"].tolist()
        [0.020833]
        >>> out["share_of_present"].tolist()
        [0.5]
"""
    _need(sensor, ["sns_key", "install_date", "interval_s"], "telemetry.sensor")
    m = _checked_measurement(measurement)
    w0, w1 = (_utc([window_start], "window_start").iloc[0], _utc([window_end], "window_end").iloc[0])
    if pd.isna(w0) or pd.isna(w1):
        raise FrameError(f"window_start and window_end must be dates (got {value_text(window_start)} and {value_text(window_end)})")
    w0, w1 = pd.Timestamp(w0).normalize(), pd.Timestamp(w1).normalize() + pd.Timedelta(days=1)
    if w1 <= w0:
        raise FrameError(f"the window starts {w0.date()} after it ends {(w1 - pd.Timedelta(days=1)).date()}")
    if sensor["sns_key"].duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    _positive_interval(sensor)
    if sensor["install_date"].isna().any():
        raise FrameError("telemetry.sensor has sensors without an install_date")
    unknown = sorted(set(m["sns_key"]) - set(sensor["sns_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} sensors of the measurements are not in telemetry.sensor (for example {unknown[0]})")
    s = sensor.assign(install=_utc(sensor["install_date"], "telemetry.sensor.install_date").dt.normalize().to_numpy())
    start = np.maximum(s["install"].to_numpy(), np.datetime64(w0))
    seconds = (np.datetime64(w1) - start) / np.timedelta64(1, "s")
    expected = np.where(seconds > 0, np.ceil(seconds / s["interval_s"].to_numpy(dtype=float)), 0).astype(np.int64)
    inside = m[(m["ts"] >= w0) & (m["ts"] < w1)]
    counts = pd.crosstab(inside["sns_key"], inside["quality_flag"]).reindex(columns=list(FLAGS), fill_value=0)
    out = pd.DataFrame({"sns_key": s["sns_key"].to_numpy(), "expected": expected}).set_index("sns_key").join(counts).fillna(0)
    out[list(FLAGS)] = out[list(FLAGS)].astype(np.int64)
    out["rows"] = out[list(FLAGS)].sum(axis=1)
    over = out["rows"] > out["expected"]
    if over.any():
        raise FrameError(f"{int(over.sum())} sensors have more rows in the window than slots after their install date (for example {out.index[over][0]}): rows before the install date, or a wrong interval_s")
    out["share"] = np.where(out["expected"] > 0, np.round(out["ok"] / out["expected"].where(out["expected"] > 0), 6), np.nan)
    out["share_of_present"] = np.where(out["rows"] > 0, np.round(out["ok"] / out["rows"].where(out["rows"] > 0), 6), np.nan)
    return out.reset_index()[["sns_key", "expected", "rows", "ok", "estimated", "suspect", "missing", "share", "share_of_present"]].sort_values("sns_key").reset_index(drop=True)


def _events(events: pd.DataFrame) -> pd.DataFrame:
    _need(events, ["sns_key", "from_ts", "to_ts", "type"], "telemetry.data_quality_event")
    if events[["sns_key", "from_ts", "to_ts", "type"]].isna().any().any():
        raise FrameError("telemetry.data_quality_event has null sns_key, from_ts, to_ts or type")
    e = events.assign(from_ts=_utc(events["from_ts"], "telemetry.data_quality_event.from_ts").to_numpy(), to_ts=_utc(events["to_ts"], "telemetry.data_quality_event.to_ts").to_numpy())
    if (e["to_ts"] < e["from_ts"]).any():
        raise FrameError("telemetry.data_quality_event has an event that ends before it starts")
    return e


def _explain(m: pd.DataFrame, e: pd.DataFrame) -> pd.Series:
    """The type of the event that covers each row that is not ok (by the flag: dropout for missing and estimated; spike, flatline or drift for suspect), None otherwise."""
    result = pd.Series(None, index=m.index, dtype=object)
    for flag, types in _EVENT_FOR_FLAG.items():
        rows = m[m["quality_flag"] == flag][["sns_key", "ts"]].sort_values("ts")
        if rows.empty:
            continue
        for t in types:
            ev = e[e["type"] == t].sort_values("from_ts")[["sns_key", "from_ts", "to_ts", "type"]]
            if ev.empty:
                continue
            ev = ev.assign(to_ts=ev.groupby("sns_key")["to_ts"].cummax())                    # an outer event still covers the samples after an inner one that ended earlier
            hit = pd.merge_asof(rows.reset_index(), ev, left_on="ts", right_on="from_ts", by="sns_key", direction="backward").set_index("index")
            covered = hit.index[(hit["to_ts"] >= hit["ts"]).to_numpy()]
            fresh = covered[result.loc[covered].isna().to_numpy()]
            result.loc[fresh] = t
    return result


@staged(sources=(*_MEASUREMENT, "telemetry.sensor.sns_key", "telemetry.sensor.interval_s", "telemetry.data_quality_event.sns_key", "telemetry.data_quality_event.from_ts",
                 "telemetry.data_quality_event.to_ts", "telemetry.data_quality_event.type", "telemetry.data_quality_event.samples"),
        oracle="py:tests/test_telemetry.py::test_telemetry_gap")
def gap_report(measurement: pd.DataFrame, sensor: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the runs of missing or estimated samples per sensor, never filled, with the data quality event that covers each run.

    Consecutive means one interval_s apart; a slot that is not in the frame ends a run. event_type is the type of the event covering the first slot of the run, null when none does, and explained is true when every
    slot of the run lies in a dropout event.

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        sensor: The telemetry.sensor frame, columns sns_key and interval_s, one row per sensor.
        events: The telemetry.data_quality_event frame, columns sns_key, from_ts, to_ts and type.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns sns_key, start, end (the last slot of the run), samples, missing, estimated, event_type and explained, sorted by sns_key and start; empty with these columns when there is no gap.

    Raises:
        FrameError: a column of sensor, events or measurement is missing, the measurement is invalid (see valid_samples), interval_s is not positive for every sensor, telemetry.sensor repeats a sns_key,
            an event has a null sns_key, from_ts, to_ts or type, an unreadable or zoned time, or ends before it starts, or a measured sensor is not in telemetry.sensor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import gap_report
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
        ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "estimated", "ok"]})
        >>> s = pd.DataFrame({"sns_key": ["SNS-900001"], "interval_s": [900]})
        >>> e = pd.DataFrame({"sns_key": ["SNS-900001"], "from_ts": ["2025-03-01 00:10"], "to_ts": ["2025-03-01 00:40"], "type": ["dropout"]})
        >>> out = gap_report(m, s, e, context=ctx)
        >>> out[["samples", "missing", "estimated", "event_type", "explained"]].to_dict("records")
        [{'samples': 2, 'missing': 1, 'estimated': 1, 'event_type': 'dropout', 'explained': True}]
"""
    _need(sensor, ["sns_key", "interval_s"], "telemetry.sensor")
    _positive_interval(sensor)
    m = _checked_measurement(measurement)
    e = _events(events)
    iv = sensor.set_index("sns_key")["interval_s"]
    if iv.index.duplicated().any():
        raise FrameError("telemetry.sensor has more than one row for a sns_key")
    unknown = sorted(set(m["sns_key"]) - set(iv.index))
    if unknown:
        raise FrameError(f"{len(unknown)} sensors of the measurements are not in telemetry.sensor (for example {unknown[0]})")
    m = m.assign(event_type=_explain(m, e))
    g = m[m["quality_flag"].isin(["missing", "estimated"])].copy()
    cols = ["sns_key", "start", "end", "samples", "missing", "estimated", "event_type", "explained"]
    if g.empty:
        return pd.DataFrame(columns=cols)
    step = g["sns_key"].map(iv).astype(float) * 1e9
    gap = g.groupby("sns_key")["ts"].diff().astype("int64").where(g.groupby("sns_key")["ts"].diff().notna())
    new = gap.isna() | (gap != step)
    g["run"] = new.cumsum()
    g["is_missing"], g["is_estimated"], g["is_dropout"] = g["quality_flag"] == "missing", g["quality_flag"] == "estimated", g["event_type"] == "dropout"
    out = g.groupby("run").agg(sns_key=("sns_key", "first"), start=("ts", "min"), end=("ts", "max"), samples=("ts", "size"), missing=("is_missing", "sum"), estimated=("is_estimated", "sum"),
                               event_type=("event_type", lambda s: s.iloc[0]), explained=("is_dropout", "all"))
    return out[cols].astype({"missing": np.int64, "estimated": np.int64}).sort_values(["sns_key", "start"]).reset_index(drop=True)


@staged(sources=(*_MEASUREMENT, "telemetry.data_quality_event.sns_key", "telemetry.data_quality_event.from_ts", "telemetry.data_quality_event.to_ts", "telemetry.data_quality_event.type"),
        oracle="py:tests/test_telemetry.py::test_data_quality_layer")
def classify_flags(measurement: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need to know which data quality event explains each sample that is not ok.

    event_type is dropout for missing and estimated samples and spike, flatline or drift for suspect ones; it is null for ok samples and for a flagged sample that no event covers. Where several events of the family
    cover a sample the type of the earliest listed one wins (spike, flatline, drift order).

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        events: The telemetry.data_quality_event frame, columns sns_key, from_ts, to_ts and type.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The measurements, sorted by sns_key and ts with a fresh index, with the extra column event_type.

    Raises:
        FrameError: a column of measurement or events is missing, the measurement is invalid (see valid_samples), or an event has a null sns_key, from_ts, to_ts or type, an unreadable or zoned time, or ends before it starts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import classify_flags
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30"]),
        ...                   "value": [1.0, 2.0, None], "quality_flag": ["ok", "suspect", "missing"]})
        >>> e = pd.DataFrame({"sns_key": ["SNS-900001"], "from_ts": ["2025-03-01 00:10"], "to_ts": ["2025-03-01 00:20"], "type": ["spike"]})
        >>> classify_flags(m, e, context=ctx)["event_type"].fillna("none").tolist()
        ['none', 'spike', 'none']
"""
    m = _checked_measurement(measurement)
    return m.assign(event_type=_explain(m, _events(events)))


@staged(sources=_MEASUREMENT, oracle="py:tests/test_telemetry.py::test_daily_aggregates_equal_raw")
def daily_from_raw(measurement: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the daily min, max, avg, count and availability per sensor recomputed from the raw samples.

    The result has the shape and dtypes of telemetry.measurement_daily. Only ok samples with a value enter the aggregates. A day exists when at least one slot is present (a row of any flag, so nothing before the install date);
    the aggregates are null when no sample is ok; availability_pct is 100 times ok over the present slots to two decimals. The date is a Python date like the stored column.

    Args:
        measurement: The telemetry.measurement frame, columns sns_key, ts, value and quality_flag.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns sns_key, date (UTC), min, max, avg, count and availability_pct (float32, count int32), sorted by sns_key and date.

    Raises:
        FrameError: a column of measurement is missing, ts holds numbers, unreadable text or a time zone, a row has no sns_key or ts, quality_flag is null or unknown, or a sensor has two rows for the same ts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import daily_from_raw
        >>> ctx = Context(stage="month12", role="analyst")
        >>> m = pd.DataFrame({"sns_key": "SNS-900001", "ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 00:15", "2025-03-01 00:30", "2025-03-01 00:45"]),
        ...                   "value": [1.0, None, 3.0, 4.0], "quality_flag": ["ok", "missing", "suspect", "ok"]})
        >>> out = daily_from_raw(m, context=ctx)
        >>> out[["min", "max", "avg", "count", "availability_pct"]].to_dict("records")
        [{'min': 1.0, 'max': 4.0, 'avg': 2.5, 'count': 2, 'availability_pct': 50.0}]
        >>> str(out["date"].iloc[0])
        '2025-03-01'
"""
    m = _checked_measurement(measurement)
    m = m.assign(date=m["ts"].dt.normalize(), ok=m["quality_flag"] == "ok")
    ok = m[m["ok"] & m["value"].notna()]
    present = m.groupby(["sns_key", "date"]).agg(rows=("ts", "size"), n_ok=("ok", "sum"))
    v = ok.assign(v=ok["value"].astype("float64")).groupby(["sns_key", "date"])["v"].agg(["min", "max", "sum"])
    out = present.join(v)
    cnt = ok.groupby(["sns_key", "date"]).size().reindex(out.index, fill_value=0)
    out["count"] = cnt.to_numpy()
    out["avg"] = out["sum"] / out["count"].where(out["count"] > 0)
    out["availability_pct"] = np.round(100.0 * out["n_ok"] / out["rows"], 2)
    out = out.reset_index()
    out["date"] = out["date"].dt.date
    for c in ("min", "max", "avg", "availability_pct"):
        out[c] = out[c].astype("float32")
    out["count"] = out["count"].astype("int32")
    return out[["sns_key", "date", "min", "max", "avg", "count", "availability_pct"]].sort_values(["sns_key", "date"]).reset_index(drop=True)


@staged(sources=("telemetry.measurement_daily.sns_key", "telemetry.measurement_daily.date", "telemetry.measurement_daily.availability_pct"), oracle="py:tests/test_telemetry.py::test_daily_aggregates_equal_raw")
def sensor_quality_board(daily: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the availability of each sensor by ISO week as a board.

    Sensors are the rows and ISO weeks the columns ('YYYY-Www'). Each cell is the mean of the daily availability_pct over the days of the week that exist, two decimals; it is null for a week without days.
    Weeks follow the ISO calendar of the UTC date, so a week at the turn of the year carries the ISO year (2024-12-30 is in 2025-W01).

    Args:
        daily: The telemetry.measurement_daily frame, columns sns_key, date and availability_pct, one row per sensor and date.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame indexed by sns_key with one column per ISO week from the week of the first date to the last date (weeks without days included), holding the weekly mean availability.

    Raises:
        FrameError: a column of daily is missing, sns_key, date or availability_pct is null, or there is more than one row for the same sensor and date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import sensor_quality_board
        >>> ctx = Context(stage="month12", role="analyst")
        >>> d = pd.DataFrame({"sns_key": "SNS-900001", "date": ["2024-12-30", "2024-12-31", "2025-01-08"], "availability_pct": [100.0, 50.0, 80.0]})
        >>> board = sensor_quality_board(d, context=ctx)
        >>> board.columns.tolist()
        ['2025-W01', '2025-W02']
        >>> board.loc["SNS-900001"].tolist()
        [75.0, 80.0]
"""
    _need(daily, ["sns_key", "date", "availability_pct"], "telemetry.measurement_daily")
    if daily[["sns_key", "date", "availability_pct"]].isna().any().any():
        raise FrameError("telemetry.measurement_daily has null sns_key, date or availability_pct")
    if daily.duplicated(["sns_key", "date"]).any():
        raise FrameError("telemetry.measurement_daily has more than one row for the same sensor and date")
    d = pd.to_datetime(daily["date"])
    iso = d.dt.isocalendar()
    label = lambda s: s.dt.isocalendar().year.astype(str) + "-W" + s.dt.isocalendar().week.astype(str).str.zfill(2)
    weeks = label(pd.Series(pd.date_range(d.min() - pd.Timedelta(days=d.min().dayofweek), d.max(), freq="7D"))).tolist() if len(d) else []
    board = daily.assign(week=(iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)).to_numpy(), availability_pct=daily["availability_pct"].astype("float64")).pivot_table(
        index="sns_key", columns="week", values="availability_pct", aggfunc="mean", dropna=False)
    board = board.reindex(weeks, axis=1).round(2)
    board.columns.name = None
    return board
