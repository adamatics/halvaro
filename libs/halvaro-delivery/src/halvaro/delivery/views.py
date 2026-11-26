"""Chart ready frames of the delivery functions (plan 5.9, section 7): no drawing and no theme here, the app draws and core supplies the theme.

Every view returns a ViewSpec: the frame to draw, which column is x, y and the group, a caption with the as-of date and the basis, the labels ('synthetic data'), and the numbers the plan asks every table to show
(n, the number of legacy projects and of projects without a route length when the inputs have them). Contract currency stays per row: nothing here adds DKK and EUR. Percentages are recomputed from summed
lines, never averaged.
"""
from __future__ import annotations

from typing import Any, NamedTuple, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._types import DateLike
from .history import ExperienceNetwork

LABEL = "synthetic data"


class ViewSpec(NamedTuple):
    """A chart ready result: `frame`, `x`, `y`, `group` and `value` (column names, None when not used; `value` is the measure of a heatmap), `kind` (chart family), `caption`, `labels`, `n` (rows of the
    underlying data) and `extra` (named further frames)."""
    kind: str
    frame: pd.DataFrame
    x: str | None
    y: str | None
    group: str | None
    value: str | None
    caption: str
    labels: tuple[Any, ...]
    n: int
    extra: dict[str, Any]


def _need(frame: Any, columns: Sequence[str], what: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}")


def _cap(text: str, as_of: Any = None, basis: str | None = None, n_legacy: int | None = None, n_no_route: int | None = None) -> str:
    parts = ([text] + ([f"as of {pd.Timestamp(as_of).date()}"] if as_of is not None else []) + ([f"basis: {basis}"] if basis else []) + ([f"{int(n_legacy)} legacy projects"] if n_legacy is not None else [])
             + ([f"{int(n_no_route)} projects without a route length"] if n_no_route is not None else []) + [LABEL])
    return "; ".join(parts)


@staged(sources=("projects.meeting.mtg_key", "projects.decision.mtg_key", "projects.delay_event.prj_key", "projects.risk.prj_key"), oracle="py:tests/test_oracle_views.py::test_oracle_timeline_view_order_and_attendance")
def timeline_view(timeline: pd.DataFrame, attendance: pd.DataFrame | None = None, write_down: dict[str, Any] | None = None, *, as_of: DateLike | None = None) -> ViewSpec:
    """Use this when you need the project timeline as chart lanes: meetings, decisions, delays, risks and plan versions in date order, with optional attendance and a write-down marker.

    The result is the project timeline as lanes, in the order of `timeline` (it is sorted: date, then meeting before its decisions). The frame has the columns date, lane (meeting, decision, delay_event, first_diary_delay, risk, plan_version), label, source and source_key. With `attendance` (one row per attendee, columns mtg_key, present) meetings get n_present and n_invited; a null `present` raises. With `write_down` ({'date', 'amount', 'currency'} from finance) one more row on the lane 'write_down' follows the last row on or before its date, the amount kept in its currency and written without separators.

    Args:
        timeline: The project timeline frame (sorted by date); it needs date, kind, source, source_key and text.
        attendance: Optional frame with one row per attendee, with mtg_key and present (no nulls); meetings get n_invited and n_present from it.
        write_down: Optional dict with date, amount and currency from finance; it adds one row on the lane 'write_down'.
        as_of: Optional as-of date, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'timeline': `frame` (date, lane, label, source, source_key and, with attendance, n_invited and n_present), x date, y and group lane, caption with the as-of date, the label 'synthetic data' and n, the number of timeline rows.

    Raises:
        FrameError: timeline or attendance is not a DataFrame or lacks a needed column; attendance.present has nulls; write_down lacks date, amount or currency.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import timeline_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> tl = pd.DataFrame({"date": ["2026-01-05", "2026-01-05", "2026-01-09"], "kind": ["meeting", "decision", "delay_event"],
        ...                    "source": ["meeting", "decision", "delay_event"], "source_key": ["MTG-900001", "DEC-900001", "DLY-900001"], "text": ["Kickoff", "Go", "Late"]})
        >>> att = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001"], "present": [True, False]})
        >>> spec = timeline_view(tl, att, {"date": "2026-01-06", "amount": 1200.0, "currency": "EUR"}, context=ctx)
        >>> spec.frame["lane"].tolist()
        ['meeting', 'decision', 'write_down', 'delay_event']
        >>> int(spec.frame["n_present"].iloc[0]), int(spec.frame["n_invited"].iloc[0])
        (1, 2)
        >>> spec.n
        3"""
    _need(timeline, ["date", "kind", "source", "source_key", "text"], "timeline")
    f = timeline.rename(columns={"kind": "lane", "text": "label"})[["date", "lane", "label", "source", "source_key"]].reset_index(drop=True)
    f["_pos"] = np.arange(len(f), dtype=float)
    if attendance is not None:
        _need(attendance, ["mtg_key", "present"], "attendance")
        if attendance["present"].isna().any():
            raise FrameError("attendance.present has nulls")
        a = attendance.assign(present=attendance["present"].astype(bool)).groupby("mtg_key").agg(n_invited=("present", "size"), n_present=("present", "sum"))
        key = f["source_key"].where(f["lane"] == "meeting")
        f["n_invited"], f["n_present"] = key.map(a["n_invited"]), key.map(a["n_present"])
    if write_down is not None:
        if not {"date", "amount", "currency"} <= set(write_down):
            raise FrameError("write_down needs date, amount and currency")
        d = pd.Timestamp(write_down["date"])
        pos = float(f.loc[pd.to_datetime(f["date"]) <= d, "_pos"].max()) + 0.5 if (pd.to_datetime(f["date"]) <= d).any() else -0.5
        f = pd.concat([f, pd.DataFrame([{"date": d, "lane": "write_down", "label": f"{write_down['amount']:.0f} {write_down['currency']}", "source": "finance", "source_key": "", "_pos": pos}])], ignore_index=True)
    return ViewSpec("timeline", f.sort_values("_pos").drop(columns="_pos").reset_index(drop=True), "date", "lane", "lane", None, _cap("project timeline", as_of), (LABEL,), int(len(timeline)), {})


@staged(sources=("projects.plan_activity.prj_key", "projects.actual_activity.prj_key"), oracle="py:tests/test_oracle_views.py::test_oracle_gantt_view_bars_per_activity")
def gantt_view(plan_vs_actual: pd.DataFrame, *, as_of: DateLike | None = None, legacy: int | None = None) -> ViewSpec:
    """Use this when you need baseline, latest plan and actual bars of project activities for a Gantt chart.

    The bars come from the activities of `activity_plan_vs_actual`: a long frame (activity key columns prj_key, activity_code and name where present), series (baseline, latest, actual), start, end, in_progress and critical. A bar needs both dates, except an activity that has started and not finished: with `as_of` its actual bar runs to that day and in_progress is true; without it the actual bar is left out (the caption says so). Sorted by the baseline start, then the key and series.

    Args:
        plan_vs_actual: The output of activity_plan_vs_actual; it needs baseline_start, baseline_end, latest_start, latest_end, actual_start and actual_end, and at least one activity key column (prj_key, activity_code, act_no or name); a critical column is carried when present.
        as_of: Optional day; an unfinished actual bar runs to it and an actual bar that starts after it is left out.
        legacy: Optional number of legacy projects, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'gantt': `frame` (the key columns, in_progress, critical when present, series, start, end; sorted by baseline start, key, series), x start, y the last key column, group series, n the number of activities.

    Raises:
        FrameError: plan_vs_actual is not a DataFrame or lacks a needed column; it has no activity key column; it has more than one row for an activity key; a bar ends before it starts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import gantt_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> pva = pd.DataFrame({"prj_key": ["PRJ-900001"], "activity_code": ["A10"],
        ...                     "baseline_start": ["2026-01-01"], "baseline_end": ["2026-01-10"], "latest_start": ["2026-01-02"], "latest_end": ["2026-01-12"],
        ...                     "actual_start": ["2026-01-02"], "actual_end": [None]})
        >>> spec = gantt_view(pva, as_of="2026-01-20", context=ctx)
        >>> spec.frame["series"].tolist()
        ['actual', 'baseline', 'latest']
        >>> spec.frame["in_progress"].tolist()
        [True, False, False]
        >>> str(spec.frame["end"].iloc[0].date())
        '2026-01-20'"""
    _need(plan_vs_actual, ["baseline_start", "baseline_end", "latest_start", "latest_end", "actual_start", "actual_end"], "activity_plan_vs_actual")
    idc = [c for c in ("prj_key", "activity_code", "act_no", "name") if c in plan_vs_actual.columns]
    if not idc:
        raise FrameError("activity_plan_vs_actual lacks an activity key (prj_key, activity_code or name)")
    if plan_vs_actual.duplicated(idc).any():
        raise FrameError("activity_plan_vs_actual has more than one row for an activity key")
    day = None if as_of is None else pd.Timestamp(as_of).normalize()
    parts = []
    for series, s0, end0 in (("baseline", "baseline_start", "baseline_end"), ("latest", "latest_start", "latest_end"), ("actual", "actual_start", "actual_end")):
        p = plan_vs_actual[plan_vs_actual[s0].notna()].copy()
        if series == "actual" and day is not None:
            p = p[pd.to_datetime(p[s0]) <= day]                                    # an activity that starts after the day has no actual bar yet
        end = pd.to_datetime(p[end0])
        prog = end.isna()
        if series == "actual" and day is not None:
            prog = prog | (end > day)
            end = end.where(end <= day, day).fillna(day)                           # unfinished or finishing later: the bar runs to the day
        p = p.assign(_end=end, in_progress=(prog & (series == "actual") & (day is not None)))
        p = p[p["_end"].notna()]
        if (p["_end"] < pd.to_datetime(p[s0])).any():
            raise FrameError(f"a {series} bar ends before it starts")
        parts.append(p[idc + (["critical"] if "critical" in p.columns else []) + ["in_progress"]].assign(series=series, start=pd.to_datetime(p[s0]), end=p["_end"]))
    f = pd.concat(parts, ignore_index=True)
    order = plan_vs_actual.assign(_b=pd.to_datetime(plan_vs_actual["baseline_start"]))[idc + ["_b"]]
    f = f.merge(order, on=idc, how="left").sort_values(["_b"] + idc + ["series"], kind="stable").drop(columns="_b").reset_index(drop=True)
    note = "activities: baseline, latest plan and actual" + ("" if day is not None else "; unfinished activities have no actual bar without an as-of day")
    return ViewSpec("gantt", f, "start", idc[-1], "series", None, _cap(note, as_of, n_legacy=legacy), (LABEL,), int(len(plan_vs_actual)), {})


@staged(sources=("projects.estimate_line.prj_key", "projects.estimate_line.amount", "projects.cost_code.category"), oracle="py:tests/test_oracle_views.py::test_oracle_waterfall_view_steps")
def waterfall_view(lines: pd.DataFrame, *, from_type: str = "tender", to_type: str = "final", as_of: DateLike | None = None, legacy: int | None = None) -> ViewSpec:
    """Use this when you need the step from one estimate type to another by cost category, per currency, for a waterfall chart.

    The frame has the columns currency, category, from_amount, to_amount and delta, plus a 'total' row per currency. Only projects that have both types in the same currency are included in that currency; n_projects (in extra) says how many. A null category is shown as '(none)'. `lines` is the lines frame of estimate_bridge (prj_key, type, category, amount, currency). Currencies are never added. from_type and to_type must differ.

    Args:
        lines: The lines frame of estimate_bridge; it needs prj_key, type, category, amount and currency.
        from_type: The estimate type to start from (default 'tender').
        to_type: The estimate type to end at (default 'final'); it must differ from from_type.
        as_of: Optional as-of date, shown in the caption.
        legacy: Optional number of legacy projects, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'waterfall': `frame` (currency, category, from_amount, to_amount, delta; sorted by currency, then category with the total row last), x category, y delta, group currency, n the number of line rows used, extra['n_projects'] the number of projects with both types.

    Raises:
        FrameError: lines is not a DataFrame or lacks a needed column; from_type equals to_type; a line has a null currency.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import waterfall_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001"] * 4, "type": ["tender", "final", "tender", "final"], "category": ["labour", "labour", "plant", "plant"],
        ...                       "amount": [100.0, 130.0, 50.0, 40.0], "currency": ["EUR"] * 4})
        >>> spec = waterfall_view(lines, context=ctx)
        >>> spec.frame["category"].tolist()
        ['labour', 'plant', 'total']
        >>> spec.frame["delta"].tolist()
        [30.0, -10.0, 20.0]
        >>> spec.extra["n_projects"]
        1"""
    _need(lines, ["prj_key", "type", "category", "amount", "currency"], "estimate lines")
    if from_type == to_type:
        raise FrameError("from_type and to_type must differ")
    if lines["currency"].isna().any():
        raise FrameError("estimate lines with a null currency")
    x = lines[lines["type"].isin([from_type, to_type])].assign(category=lambda f: f["category"].fillna("(none)"))
    ok = []
    for cur, g in x.groupby("currency"):
        both = set(g.loc[g["type"] == from_type, "prj_key"]) & set(g.loc[g["type"] == to_type, "prj_key"])
        ok.append(g[g["prj_key"].isin(both)].assign(_n=len(both)))
    x = pd.concat(ok, ignore_index=True) if ok else x.iloc[:0].assign(_n=0)
    n_proj = int(x["prj_key"].nunique()) if len(x) else 0
    g = x.pivot_table(index=["currency", "category"], columns="type", values="amount", aggfunc="sum", fill_value=0.0).reset_index()
    for t in (from_type, to_type):
        if t not in g.columns:
            g[t] = 0.0
    g = g.rename(columns={from_type: "from_amount", to_type: "to_amount"})[["currency", "category", "from_amount", "to_amount"]]
    g["delta"] = g["to_amount"] - g["from_amount"]
    tot = g.groupby("currency", as_index=False)[["from_amount", "to_amount", "delta"]].sum().assign(category="total")
    f = pd.concat([g, tot[g.columns]], ignore_index=True).sort_values(["currency", "category"], key=lambda c: c.where(c != "total", "~")).reset_index(drop=True)
    return ViewSpec("waterfall", f, "category", "delta", "currency", None, _cap(f"estimate {from_type} to {to_type}, {n_proj} projects with both", as_of, "contract currency per row", n_legacy=legacy), (LABEL,), int(len(x)), {"n_projects": n_proj})


@staged(sources=("projects.delay_event.cause_code", "projects.delay_event.days"), oracle="py:tests/test_oracle_views.py::test_oracle_cause_bars_view_days_per_cause")
def cause_bars_view(cause_shares: pd.DataFrame, *, view: str = "all_events", as_of: DateLike | None = None, legacy: int | None = None) -> ViewSpec:
    """Use this when you need delay days by cause code for one view of the cause shares, ready for a bar chart.

    The bars are the delay days by cause code for one view of `cause_shares`: cause_code, days, events and share (days over the days of the view, recomputed from the summed rows) with responsible parties summed. A null cause code is shown as '(unknown)'. Sorted by days, largest first, then cause code.

    Args:
        cause_shares: The cause shares frame; it needs view, cause_code, days and events.
        view: The view of the frame to draw (default 'all_events').
        as_of: Optional as-of date, shown in the caption.
        legacy: Optional number of legacy projects, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'bars': `frame` (cause_code, days, events, share rounded to 4 places; sorted by days descending, then cause_code), x cause_code, y days, n the number of events of the view.

    Raises:
        FrameError: cause_shares is not a DataFrame or lacks a needed column; cause_shares has no rows for the view.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import cause_bars_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cs = pd.DataFrame({"view": ["all_events"] * 3, "cause_code": ["WTR", "WTR", "SUP"], "days": [3.0, 1.0, 4.0], "events": [1, 1, 2]})
        >>> spec = cause_bars_view(cs, context=ctx)
        >>> spec.frame["cause_code"].tolist()
        ['SUP', 'WTR']
        >>> spec.frame["share"].tolist()
        [0.5, 0.5]
        >>> spec.n
        4"""
    _need(cause_shares, ["view", "cause_code", "days", "events"], "cause_shares")
    v = cause_shares[cause_shares["view"] == view]
    if v.empty:
        raise FrameError(f"cause_shares has no rows for the view {view}")
    v = v.assign(cause_code=v["cause_code"].fillna("(unknown)"))
    g = v.groupby("cause_code", as_index=False)[["days", "events"]].sum()
    g["share"] = (g["days"] / g["days"].sum()).round(4)
    return ViewSpec("bars", g.sort_values(["days", "cause_code"], ascending=[False, True]).reset_index(drop=True), "cause_code", "days", None, None, _cap(f"delay days by cause, view {view}", as_of, n_legacy=legacy), (LABEL,), int(v["events"].sum()), {})


@staged(sources=("projects.meeting_attendance.mtg_key", "projects.meeting.date"), oracle="py:tests/test_oracle_views.py::test_oracle_attendance_view_cells_sum_to_present")
def attendance_view(attendance: pd.DataFrame, *, by: str = "month", as_of: DateLike | None = None) -> ViewSpec:
    """Use this when you need meeting attendance as heatmap data: the absence rate by month or year and meeting type.

    The heatmap data comes from `attendance` (one row per attendee: date, present and optionally meeting_type): period (month or year), meeting_type, n_rows, n_present, absence_rate from the summed rows (1 less present over rows), n_meetings. A frame without meeting_type uses 'all', a null meeting_type is shown as 'unknown' (rows are never dropped); a null `present` raises FrameError. x is the period, y the meeting type and `value` the absence rate.

    Args:
        attendance: One row per attendee; it needs mtg_key, date and present (no nulls) and may have meeting_type.
        by: The period, 'month' or 'year' (default 'month').
        as_of: Optional as-of date, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'heatmap': `frame` (period, meeting_type, n_rows, n_present, n_meetings, absence_rate rounded to 4 places), x period, y meeting_type, value absence_rate, n the number of attendance rows.

    Raises:
        FrameError: attendance is not a DataFrame or lacks a needed column; by is not month or year; attendance.present has nulls.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import attendance_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> att = pd.DataFrame({"mtg_key": ["MTG-900001", "MTG-900001", "MTG-900002"], "date": ["2026-01-05", "2026-01-05", "2026-02-02"], "present": [True, False, True]})
        >>> spec = attendance_view(att, context=ctx)
        >>> spec.frame["period"].tolist()
        ['2026-01', '2026-02']
        >>> spec.frame["absence_rate"].tolist()
        [0.5, 0.0]
        >>> spec.frame["meeting_type"].tolist()
        ['all', 'all']"""
    _need(attendance, ["mtg_key", "date", "present"], "attendance")
    if by not in ("month", "year"):
        raise FrameError("by is month or year")
    if attendance["present"].isna().any():
        raise FrameError("attendance.present has nulls")
    d = pd.to_datetime(attendance["date"])
    mt = attendance["meeting_type"].astype(object).fillna("unknown") if "meeting_type" in attendance.columns else "all"
    x = attendance.assign(period=d.dt.strftime("%Y-%m" if by == "month" else "%Y"), meeting_type=mt, _p=attendance["present"].astype(bool))
    g = x.groupby(["period", "meeting_type"], as_index=False, dropna=False).agg(n_rows=("mtg_key", "size"), n_present=("_p", "sum"), n_meetings=("mtg_key", "nunique"))
    g["absence_rate"] = (1.0 - g["n_present"] / g["n_rows"]).round(4)
    return ViewSpec("heatmap", g, "period", "meeting_type", None, "absence_rate", _cap("meeting attendance", as_of), (LABEL,), int(len(attendance)), {})


@staged(sources=("inventory.stock_level.on_hand", "procurement.po_line.itm_key"), oracle="py:tests/test_oracle_views.py::test_oracle_stock_view_long_frame_per_key")
def stock_view(stock: pd.DataFrame, open_lines: pd.DataFrame | None = None, *, as_of: DateLike | None = None) -> ViewSpec:
    """Use this when you need on hand, reserved and available stock over dates as chart lines, with the open purchase order lines on the side.

    `stock` is a stack of `stock_on` outputs (as_of, site_key, itm_key, on_hand, reserved, available). The result is a long frame as_of, site_key, itm_key, series, quantity. With `open_lines` (open_po_lines of one date) the remaining quantity per item and promised date is in extra['orders']. Quantities keep the item unit; items are never added together.

    Args:
        stock: A stack of stock_on outputs; it needs as_of, site_key, itm_key, on_hand, reserved and available.
        open_lines: Optional output of open_po_lines for one date; it needs itm_key and remaining, and itm_key, po_key, line_no and promised_date are carried when present.
        as_of: Optional as-of date, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'lines': `frame` (as_of, site_key, itm_key, series one of on_hand, reserved, available, quantity; sorted by itm_key, site_key, as_of, series), x as_of, y quantity, group series, n the number of stock rows, extra['orders'] the open line frame when open_lines is given.

    Raises:
        FrameError: stock or open_lines is not a DataFrame or lacks a needed column.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import stock_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> st = pd.DataFrame({"as_of": ["2026-01-05"], "site_key": ["SITE-900001"], "itm_key": ["ITM-900001"], "on_hand": [10.0], "reserved": [4.0], "available": [6.0]})
        >>> ol = pd.DataFrame({"itm_key": ["ITM-900001"], "po_key": ["PO-900001"], "remaining": [5.0]})
        >>> spec = stock_view(st, ol, context=ctx)
        >>> spec.frame["series"].tolist()
        ['available', 'on_hand', 'reserved']
        >>> spec.frame["quantity"].tolist()
        [6.0, 10.0, 4.0]
        >>> spec.extra["orders"]["remaining"].tolist()
        [5.0]"""
    _need(stock, ["as_of", "site_key", "itm_key", "on_hand", "reserved", "available"], "stock")
    long = stock.melt(id_vars=["as_of", "site_key", "itm_key"], value_vars=["on_hand", "reserved", "available"], var_name="series", value_name="quantity").sort_values(["itm_key", "site_key", "as_of", "series"]).reset_index(drop=True)
    extra = {}
    if open_lines is not None:
        _need(open_lines, ["itm_key", "remaining"], "open_po_lines")
        extra["orders"] = open_lines[[c for c in ("itm_key", "po_key", "line_no", "promised_date", "remaining") if c in open_lines.columns]].reset_index(drop=True)
    return ViewSpec("lines", long, "as_of", "quantity", "series", None, _cap("stock, reservations and orders", as_of), (LABEL,), int(len(stock)), extra)


@staged(sources=("procurement.supplier_performance.sup_key", "inventory.lead_time.lead_time_weeks"), oracle="py:tests/test_oracle_views.py::test_oracle_performance_view_summed_lines")
def performance_view(performance: pd.DataFrame, lead_on: pd.DataFrame | None = None, *, as_of: DateLike | None = None) -> ViewSpec:
    """Use this when you need the on time share of suppliers as bars, with the lead time steps on the side.

    The on time share comes from `supplier_performance_window` (sup_key, lines_due, lines_on_time, on_time_percent recomputed from the summed lines, never averaged) and, with `lead_on` (lead_time_on), the lead time steps are in extra['lead_times'] (sup_key, itm_key, previous_weeks, lead_time_weeks, change_weeks).

    Args:
        performance: The output of supplier_performance_window; it needs sup_key, lines_due and lines_on_time (no nulls, never more on time than due).
        lead_on: Optional output of lead_time_on; it needs sup_key, itm_key and lead_time_weeks, and previous_weeks and change_weeks are carried when present.
        as_of: Optional as-of date, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'bars': `frame` (sup_key, lines_due, lines_on_time, on_time_percent rounded to 2 places and null when no line is due; sorted by sup_key), x sup_key, y on_time_percent, n the summed lines due, extra['lead_times'] the lead time frame when lead_on is given.

    Raises:
        FrameError: performance or lead_on is not a DataFrame or lacks a needed column; the performance frame has nulls in lines_due or lines_on_time or more lines on time than due.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import performance_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> perf = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001", "SUP-900002"], "lines_due": [4, 4, 5], "lines_on_time": [3, 1, 5]})
        >>> spec = performance_view(perf, context=ctx)
        >>> spec.frame["sup_key"].tolist()
        ['SUP-900001', 'SUP-900002']
        >>> spec.frame["on_time_percent"].tolist()
        [50.0, 100.0]
        >>> spec.n
        13"""
    _need(performance, ["sup_key", "lines_due", "lines_on_time"], "supplier_performance_window")
    if performance[["lines_due", "lines_on_time"]].isna().any().any() or (performance["lines_on_time"] > performance["lines_due"]).any():
        raise FrameError("supplier performance has nulls or more lines on time than due")
    f = performance.groupby("sup_key", as_index=False)[["lines_due", "lines_on_time"]].sum()
    f["on_time_percent"] = (100.0 * f["lines_on_time"] / f["lines_due"].where(f["lines_due"] > 0)).round(2)
    extra = {}
    if lead_on is not None:
        _need(lead_on, ["sup_key", "itm_key", "lead_time_weeks"], "lead_time_on")
        extra["lead_times"] = lead_on[[c for c in ("sup_key", "itm_key", "previous_weeks", "lead_time_weeks", "change_weeks") if c in lead_on.columns]].reset_index(drop=True)
    return ViewSpec("bars", f.sort_values("sup_key").reset_index(drop=True), "sup_key", "on_time_percent", None, None, _cap("supplier on time share from summed lines", as_of), (LABEL,), int(f["lines_due"].sum()), extra)


@staged(sources=("projects.project_role.prj_key", "projects.project_role.emp_key"), oracle="py:tests/test_oracle_views.py::test_oracle_experience_network_view_counts_and_pass_through")
def experience_network_view(network: ExperienceNetwork, *, as_of: DateLike | None = None, n_no_route: int | None = None) -> ViewSpec:
    """Use this when you need the experience network as nodes and edges for a force or bipartite drawing.

    The frame is the edge list (prj_key, emp_key, roles, start, end, hours_total, basis, legacy), extra holds the nodes (leavers marked) and the co-working pairs. No ranking, no pay. The number of legacy edges is in the caption: their hours are estimates.

    Args:
        network: The result of experience_network (an ExperienceNetwork).
        as_of: Optional as-of date, shown in the caption.
        n_no_route: Optional number of projects without a route length, shown in the caption.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A ViewSpec of kind 'network': `frame` the edges of the network, x emp_key, y prj_key, n the number of edges, extra['nodes'] and extra['pairs'] the nodes and the co-working pairs of the network.

    Raises:
        FrameError: network is not the result of experience_network.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import experience_network, experience_network_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> roles = pd.DataFrame({"prj_key": ["PRJ-900001"] * 2, "emp_key": ["EMP-900001", "EMP-900002"], "project_role": ["manager", "engineer"],
        ...                       "start": ["2026-01-01", "2026-01-06"], "end": ["2026-01-10", "2026-01-20"], "hours_total": [80.0, 100.0], "basis": ["time_entries"] * 2})
        >>> proj = pd.DataFrame({"prj_key": ["PRJ-900001"], "type": ["tunnel"], "soil_class": ["clay"], "country": ["NL"], "legacy": [False]})
        >>> net = experience_network(roles, proj, ["PRJ-900001"], as_of="2026-02-01", context=ctx)
        >>> spec = experience_network_view(net, as_of="2026-02-01", context=ctx)
        >>> spec.n
        2
        >>> sorted(spec.extra)
        ['nodes', 'pairs']"""
    if not isinstance(network, ExperienceNetwork):
        raise FrameError("experience_network_view takes the result of experience_network")
    n_leg = int(network.edges["legacy"].fillna(False).astype(bool).sum()) if len(network.edges) else 0
    n_lv = int(network.nodes["leaver"].astype(bool).sum())
    return ViewSpec("network", network.edges, "emp_key", "prj_key", None, None, _cap(f"experience network, {n_leg} legacy edges (hours estimated), {n_lv} leavers marked", as_of, n_no_route=n_no_route), (LABEL,), int(len(network.edges)),
                    {"nodes": network.nodes, "pairs": network.pairs})
