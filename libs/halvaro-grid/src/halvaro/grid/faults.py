"""Faults (plan 5.7): fault rate of a group against its baseline and the rest, repeat faults, causes by group and window.

Windows and the repeat gap are keywords marked PROPOSED (policy.grid.winter_window, policy.grid.repeat_fault_window). The group is a set of net keys the caller supplies (a cluster, a type, a zone).
"""
from __future__ import annotations

from typing import Any, Iterable, NamedTuple

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need, _utc
from ._tail import value_text


class FaultRateComparison(NamedTuple):
    """Faults per month of a group and of the rest, in the baseline months and in the window, and the ratios: group_ratio and rest_ratio (window over baseline), spike_vs_rest (group_ratio over rest_ratio).
    per_element_month_* divide by the number of elements of the group and of the rest when grid_element was given (null otherwise)."""
    group_baseline_per_month: float
    group_window_per_month: float
    group_ratio: float
    rest_baseline_per_month: float
    rest_window_per_month: float
    rest_ratio: float
    spike_vs_rest: float
    n_group_elements: int
    n_rest_elements: int
    group_window_per_element_month: float
    rest_window_per_element_month: float


def _months(first: str, last: str, what: str) -> pd.PeriodIndex:
    try:
        a, b = pd.Period(first, "M"), pd.Period(last, "M")
    except (ValueError, TypeError):
        raise FrameError(f"{what} must be a (first, last) pair of months like 2025-12 (got ({first!r}, {last!r}))") from None
    if a > b:
        raise FrameError(f"{what} is out of order (got ({first!r}, {last!r}))")
    return pd.period_range(a, b, freq="M")


@staged(sources=("service.fault_event.net_key", "service.fault_event.fault_ts", "gis.grid_element.net_key"), oracle="py:halvaro_gen/world/service/truth.py::compute")
def fault_rate(fault_event: pd.DataFrame, group: Iterable[Any], *, baseline: tuple[str, str] = ("2023-01", "2025-10"), window: tuple[str, str] = ("2025-12", "2026-02"), grid_element: pd.DataFrame | None = None) -> FaultRateComparison:
    """Use this when you need the faults per month of a group of elements against the rest, in the baseline months and in a window, and the spike ratio.

    The months are calendar months (`baseline` and `window` are first and last months). PROPOSED: the window of policy.grid.winter_window and the baseline of the months the caller passes (the policy
    text would take every month before the window); the defaults of both are placeholders the caller should replace with the months it means. A month without a fault counts as zero. Ratios (window over
    baseline, and spike_vs_rest as group_ratio over rest_ratio) are null when the baseline mean is zero. With grid_element the number of elements of the group and of the rest (in service or not,
    commissioned or not: a count of rows) is added and the window rates per element-month are given; without it the counts are -1 and the per-element rates are null. A baseline and a window that overlap,
    a month pair out of order or not a pair of months, or an empty group raises FrameError.

    Args:
        fault_event: The service.fault_event table; needs net_key and fault_ts.
        group: The net keys of the group (one key as text, or an iterable of keys); must not be empty.
        baseline: The (first, last) calendar months of the baseline, like "2024-01"; replace the default with the months you mean.
        window: The (first, last) calendar months of the comparison window, like "2024-04"; replace the default with the months you mean.
        grid_element: Optional gis.grid_element table with net_key, used to count the elements of the group and of the rest.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A FaultRateComparison with group_baseline_per_month, group_window_per_month, group_ratio, rest_baseline_per_month, rest_window_per_month, rest_ratio, spike_vs_rest, n_group_elements,
        n_rest_elements, group_window_per_element_month and rest_window_per_element_month.

    Raises:
        FrameError: fault_event or grid_element lacks a needed column; the group is empty; a month pair is not a (first, last) pair of months or is out of order; the baseline and the window overlap; a fault has no time.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import fault_rate
        >>> ctx = Context(stage="month12", role="analyst")
        >>> fe = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900001", "NET-900001", "NET-900002", "NET-900002"],
        ...                    "fault_ts": ["2024-01-10", "2024-02-10", "2024-04-05", "2024-04-20", "2024-01-15", "2024-04-10"]})
        >>> r = fault_rate(fe, ["NET-900001"], baseline=("2024-01", "2024-02"), window=("2024-04", "2024-04"), context=ctx)
        >>> (r.group_baseline_per_month, r.group_window_per_month, r.group_ratio, r.spike_vs_rest)
        (1.0, 2.0, 2.0, 1.0)
        >>> r.n_group_elements
        -1
    """
    _need(fault_event, ["net_key", "fault_ts"], "service.fault_event")
    members = set([group] if isinstance(group, str) else group)
    if not members:
        raise FrameError("the group has no element")
    base, win = _months(*baseline, "baseline"), _months(*window, "window")
    if base.max() >= win.min() and win.max() >= base.min():
        raise FrameError("the baseline and the window overlap")
    ts = _utc(fault_event["fault_ts"], "service.fault_event.fault_ts")
    if ts.isna().any():
        raise FrameError("service.fault_event has a fault without a time")
    d = pd.DataFrame({"m": pd.PeriodIndex(ts.to_numpy(), freq="M"), "g": fault_event["net_key"].isin(members).to_numpy()})
    c = d.groupby(["g", "m"]).size()
    mean = lambda flag, months: float(sum(c.get((flag, m), 0) for m in months) / len(months))
    gb, gw, rb, rw = mean(True, base), mean(True, win), mean(False, base), mean(False, win)
    ratio = lambda w, b: round(w / b, 3) if b > 0 else np.nan
    n_g = n_r = -1
    pe_g = pe_r = np.nan
    if grid_element is not None:
        _need(grid_element, ["net_key"], "gis.grid_element")
        n_g = int(grid_element["net_key"].isin(members).sum())
        n_r = int(len(grid_element) - n_g)
        pe_g, pe_r = (round(gw / n_g, 6) if n_g else np.nan), (round(rw / n_r, 6) if n_r else np.nan)
    gr, rr = ratio(gw, gb), ratio(rw, rb)
    return FaultRateComparison(round(gb, 3), round(gw, 3), gr, round(rb, 3), round(rw, 3), rr, round(gr / rr, 3) if gr == gr and rr == rr and rr > 0 else np.nan, n_g, n_r, pe_g, pe_r)


@staged(sources=("service.fault_event.net_key", "service.fault_event.fault_ts", "service.fault_event.tkt_key", "service.fault_event.repeat_of_tkt_key"),
        oracle="py:tests/test_service.py::test_fault_events_consistent")
def repeat_faults(fault_event: pd.DataFrame, *, gap_days: int = 45) -> pd.DataFrame:
    """Use this when you need to find the repeat faults, the faults on an element that follow an earlier fault of the same element within a number of days.

    A fault is a repeat when the same element had a fault at most `gap_days` days before (PROPOSED 45, as the generator's hazard rule), counted from the time of the fault before. The repeat flag is
    recomputed from the times and compared with the stored repeat_of_tkt_key.

    Args:
        fault_event: The service.fault_event table; needs net_key, fault_ts, tkt_key and repeat_of_tkt_key.
        gap_days: The largest number of days between a fault and the fault before it for it to count as a repeat (PROPOSED 45); a whole number, zero or more.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame sorted by element and time with the columns tkt_key, net_key, fault_ts, repeat (recomputed), chain_length (consecutive repeats up to and including this fault, 0 for a first fault),
        previous_tkt_key, gap_days, linked (the stored repeat_of_tkt_key is set) and agrees (the stored link points to the fault before when repeat, and is null otherwise).

    Raises:
        FrameError: fault_event lacks a needed column; gap_days is not a whole number of zero or more; a tkt_key appears in more than one row; a fault time cannot be read.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import repeat_faults
        >>> ctx = Context(stage="month12", role="analyst")
        >>> fe = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002", "TKT-900003"], "net_key": ["NET-900001"] * 3,
        ...                    "fault_ts": ["2024-03-01", "2024-03-10", "2024-06-01"], "repeat_of_tkt_key": [None, "TKT-900001", None]})
        >>> out = repeat_faults(fe, context=ctx)
        >>> out["repeat"].tolist(), out["chain_length"].tolist(), out["agrees"].tolist()
        ([False, True, False], [0, 1, 0], [True, True, True])
    """
    _need(fault_event, ["net_key", "fault_ts", "tkt_key", "repeat_of_tkt_key"], "service.fault_event")
    if isinstance(gap_days, bool) or not isinstance(gap_days, int) or gap_days < 0:
        raise FrameError(f"gap_days must be a whole number of days, zero or more (got {value_text(gap_days)})")
    if fault_event["tkt_key"].duplicated().any():
        raise FrameError("service.fault_event has more than one row for a tkt_key")
    ts = _utc(fault_event["fault_ts"], "service.fault_event.fault_ts")
    x = fault_event.assign(_ts=ts.to_numpy()).sort_values(["net_key", "_ts", "tkt_key"], kind="stable").reset_index(drop=True)
    prev_ts = x.groupby("net_key")["_ts"].shift(1)
    prev_tkt = x.groupby("net_key")["tkt_key"].shift(1)
    gap = (x["_ts"] - prev_ts).dt.total_seconds() / 86400.0
    rep = gap.notna() & (gap <= gap_days)
    chain = np.zeros(len(x), dtype=int)
    for i in range(len(x)):
        if rep[i]:
            chain[i] = chain[i - 1] + 1 if i > 0 and x.at[i - 1, "net_key"] == x.at[i, "net_key"] else 1
    linked = x["repeat_of_tkt_key"].notna()
    agrees = np.where(rep, x["repeat_of_tkt_key"] == prev_tkt, ~linked)
    return pd.DataFrame({"tkt_key": x["tkt_key"], "net_key": x["net_key"], "fault_ts": x["_ts"], "repeat": rep.to_numpy(), "chain_length": chain, "previous_tkt_key": prev_tkt.where(rep),
                         "gap_days": gap.round(3), "linked": linked, "agrees": agrees})


@staged(sources=("service.fault_event.net_key", "service.fault_event.fault_ts", "service.fault_event.cause", "service.fault_event.fault_type", "service.fault_event.detected_by"))
def fault_causes(fault_event: pd.DataFrame, group: Iterable[Any] | None = None, *, window: tuple[Any, ...] | None = None, allowed_causes: Iterable[Any] | None = None,
                 refuse_words: tuple[str, ...] = ("intent", "deliberate", "blame")) -> pd.DataFrame:
    """Use this when you need the share of each recorded cause among the faults of a group in a window of days.

    The group defaults to all faults and the window (first, last, in days) to all time. `allowed_causes` (optional) is the closed list the caller accepts: a cause outside it, or a missing cause, raises
    FrameError, so wording of intent or blame cannot enter a result. Faults without a cause are counted as 'unknown' when allowed_causes is not given. Without allowed_causes a recorded cause that contains
    one of `refuse_words` (PROPOSED: the three words of intent and blame of the default; the plan keeps statements of intent out of results) raises FrameError.

    Args:
        fault_event: The service.fault_event table; needs net_key, fault_ts and cause (the columns fault_type and detected_by are sources of the function but are not read).
        group: Optional net keys (one key as text, or an iterable); default all faults.
        window: Optional (first, last) dates, both days included, in order; default all time.
        allowed_causes: Optional closed list of accepted causes; a cause outside it, or a missing cause, raises FrameError.
        refuse_words: Words (a tuple, PROPOSED: the default of the signature) that may not occur in a recorded cause when allowed_causes is not given.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns cause, n, share (of n_total, rounded to 4 places; null when there are no faults) and n_total, sorted by n descending and then by cause.

    Raises:
        FrameError: fault_event lacks a needed column; the window is not a pair of dates in order; refuse_words is a single text; allowed_causes is a single text; a cause is outside allowed_causes or missing; a cause contains a refused word.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import fault_causes
        >>> ctx = Context(stage="month12", role="analyst")
        >>> fe = pd.DataFrame({"net_key": ["NET-900001", "NET-900001", "NET-900002"], "fault_ts": ["2024-03-01", "2024-03-05", "2024-03-09"],
        ...                    "cause": ["wear", "wear", "load"]})
        >>> out = fault_causes(fe, context=ctx)
        >>> out["cause"].tolist(), out["n"].tolist(), out["share"].tolist()
        (['wear', 'load'], [2, 1], [0.6667, 0.3333])
    """
    _need(fault_event, ["net_key", "fault_ts", "cause"], "service.fault_event")
    x = fault_event
    if group is not None:
        x = x[x["net_key"].isin(set([group] if isinstance(group, str) else group))]
    if window is not None:
        a, b = _utc([window[0]], "window start").iloc[0], _utc([window[1]], "window end").iloc[0]
        if pd.isna(a) or pd.isna(b) or a > b:
            raise FrameError(f"window is a (first, last) pair of dates in order (got {value_text(window)})")
        ts = _utc(x["fault_ts"], "service.fault_event.fault_ts")
        x = x[((ts >= a) & (ts < b + pd.Timedelta(days=1))).to_numpy()]
    cause = x["cause"].astype(object)
    if isinstance(refuse_words, (str, bytes)):
        raise FrameError(f"refuse_words must be a tuple of words (got {value_text(refuse_words)})")
    if allowed_causes is None:
        hit = sorted({str(c) for c in cause.dropna() if any(w.lower() in str(c).lower() for w in refuse_words)})
        if hit:
            raise FrameError(f"causes that state intent or blame are not returned: {hit}")
    if allowed_causes is not None:
        if isinstance(allowed_causes, (str, bytes)):
            raise FrameError(f"allowed_causes must be a list of causes, not a single text (got {value_text(allowed_causes)})")
        ok = set(allowed_causes)
        bad = sorted(set(cause.dropna()) - ok)
        if bad or cause.isna().any():
            raise FrameError(f"causes outside the accepted list: {bad or ['(missing)']}")
    cause = cause.where(cause.notna(), "unknown")
    n = cause.value_counts()
    out = pd.DataFrame({"cause": n.index, "n": n.to_numpy()})
    out["n_total"] = int(len(x))
    out["share"] = (out["n"] / out["n_total"]).round(4) if len(x) else np.nan
    return out.sort_values(["n", "cause"], ascending=[False, True]).reset_index(drop=True)[["cause", "n", "share", "n_total"]]
