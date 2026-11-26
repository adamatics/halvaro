"""Oracle tests of the chart ready views: the expected numbers come from hand worked frames or from plain python loops over the input frame (built from the baseline tables), never from the view."""
import math
from collections import defaultdict

import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError
from halvaro.delivery.history import ExperienceNetwork

CTX = Context(stage="month12", role="r")


def _ts(x):
    return None if x is None or pd.isna(x) else pd.Timestamp(x)


# --------------------------------------------------------------------------------------------------------- attendance_view
def _attendance_cells(frame, by):
    """Cells (period, meeting type) -> [rows, present, meetings] by a plain loop over the attendee rows."""
    rows, present, meetings = defaultdict(int), defaultdict(int), defaultdict(set)
    types = frame["meeting_type"] if "meeting_type" in frame.columns else ["all"] * len(frame)
    for mtg, day, p, t in zip(frame["mtg_key"], frame["date"], frame["present"], types):
        iso = str(pd.Timestamp(day).date())
        key = (iso[:7] if by == "month" else iso[:4], "unknown" if t is None or (isinstance(t, float) and math.isnan(t)) else t)
        rows[key] += 1
        present[key] += int(bool(p))
        meetings[key].add(mtg)
    return {k: (rows[k], present[k], len(meetings[k])) for k in rows}


def _check_attendance(frame, by):
    v = delivery.attendance_view(frame, by=by, context=CTX)
    f = v.frame
    want = _attendance_cells(frame, by)
    got = {(r.period, r.meeting_type): (int(r.n_rows), int(r.n_present), int(r.n_meetings)) for r in f.itertuples()}
    assert len(f) == len(want) and got == want, "one cell per (period, meeting type) with its rows, present and meetings"
    tol = 5.1e-5      # the rate is rounded to four decimals
    for r in f.itertuples():
        n_rows, n_present, _ = want[(r.period, r.meeting_type)]
        assert r.absence_rate == pytest.approx(1.0 - n_present / n_rows, abs=tol), (by, r.period, r.meeting_type)
    assert int(f["n_present"].sum()) == int(frame["present"].astype(bool).sum()) and int(f["n_rows"].sum()) == len(frame) == v.n, "the cells sum to the present attendees and to all rows"
    assert (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("heatmap", "period", "meeting_type", None, "absence_rate", ("synthetic data",))
    return v


def test_oracle_attendance_view_cells_sum_to_present():
    """route: hand worked cells (rows, present, meetings, absence rate) of a 15 row attendance frame, plus the sum and grouping properties."""
    at = pd.DataFrame({
        "mtg_key": ["M1"] * 4 + ["M2"] * 3 + ["M3"] * 2 + ["M4"] * 2 + ["M5"] * 2 + ["M6"] * 2,
        "date": ["2025-01-05"] * 4 + ["2025-01-20"] * 3 + ["2025-02-01"] * 2 + ["2025-01-31"] * 2 + ["2025-01-10"] * 2 + ["2026-01-15"] * 2,
        "present": [True, True, False, False, True, True, True, False, False, True, False, True, True, True, False],
        "meeting_type": ["steering"] * 4 + ["steering"] * 3 + ["steering"] * 2 + ["site"] * 2 + [None] * 2 + ["steering"] * 2})
    before = at.copy()
    m = delivery.attendance_view(at, context=CTX)
    got = {(r.period, r.meeting_type): (r.n_rows, r.n_present, r.n_meetings, r.absence_rate) for r in m.frame.itertuples()}
    assert got == {("2025-01", "steering"): (7, 5, 2, 0.2857), ("2025-01", "site"): (2, 1, 1, 0.5), ("2025-01", "unknown"): (2, 2, 1, 0.0),
                   ("2025-02", "steering"): (2, 0, 1, 1.0), ("2026-01", "steering"): (2, 1, 1, 0.5)}, "31 January and 1 February are two months, January of two years are two periods, a null type is shown as unknown"
    assert (m.n, int(m.frame.n_present.sum()), int(m.frame.n_rows.sum())) == (15, 9, 15)
    y = delivery.attendance_view(at, by="year", context=CTX)
    got_y = {(r.period, r.meeting_type): (r.n_rows, r.n_present, r.n_meetings, r.absence_rate) for r in y.frame.itertuples()}
    assert got_y == {("2025", "steering"): (9, 5, 3, 0.4444), ("2025", "site"): (2, 1, 1, 0.5), ("2025", "unknown"): (2, 2, 1, 0.0), ("2026", "steering"): (2, 1, 1, 0.5)}
    assert int(y.frame.n_present.sum()) == int(m.frame.n_present.sum()) == 9 and int(y.frame.n_rows.sum()) == int(m.frame.n_rows.sum()) == 15, "month and year grouping give the same totals"
    _check_attendance(at, "month")
    _check_attendance(at, "year")
    plain = delivery.attendance_view(at.drop(columns="meeting_type"), context=CTX).frame
    assert plain.meeting_type.tolist() == ["all"] * 3 and plain.set_index("period").n_rows.to_dict() == {"2025-01": 11, "2025-02": 2, "2026-01": 2}, "without a meeting type the rows are all 'all'"
    stamped = at.assign(date=pd.to_datetime(at["date"]), present=at["present"].astype(object))
    pd.testing.assert_frame_equal(delivery.attendance_view(stamped, context=CTX).frame, m.frame)
    pd.testing.assert_frame_equal(at, before)
    with pytest.raises(FrameError, match="month or year"):
        delivery.attendance_view(at, by="week", context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        delivery.attendance_view(at.assign(present=[None] + at.present.tolist()[1:]), context=CTX)


@pytest.mark.release
def test_oracle_attendance_view_baseline_cells(load):
    """route: the attendee rows joined to their meetings with pandas merge, the cells recounted with a python loop and compared per cell."""
    ma, mt = load("projects", "meeting_attendance"), load("projects", "meeting")
    at = ma.merge(mt[["mtg_key", "date", "meeting_type"]], on="mtg_key", how="left", validate="many_to_one").assign(present=lambda f: f["status"] == "present")[["mtg_key", "date", "present", "meeting_type"]]
    assert len(at) == len(ma) and at["date"].notna().all()
    for by in ("month", "year"):
        v = _check_attendance(at, by)
        assert int(v.frame["n_present"].sum()) == int((ma["status"] == "present").sum()), "present attendees counted straight from the status column"
    assert delivery.attendance_view(at, by="year", context=CTX).frame.n_meetings.sum() >= mt["mtg_key"].nunique(), "a meeting is in the cell of its own year and type"


# --------------------------------------------------------------------------------------------------------- cause_bars_view
def _cause_bars(frame, view):
    days, events = defaultdict(int), defaultdict(int)
    for v, c, d, e in zip(frame["view"], frame["cause_code"], frame["days"], frame["events"]):
        if v == view:
            key = "(unknown)" if c is None or (isinstance(c, float) and math.isnan(c)) else c
            days[key] += int(d)
            events[key] += int(e)
    total = sum(days.values())
    order = sorted(days, key=lambda c: (-days[c], c))
    return [(c, days[c], events[c], days[c] / total) for c in order], total, sum(events.values())


def _check_cause_bars(frame, view):
    v = delivery.cause_bars_view(frame, view=view, context=CTX)
    want, total, n_events = _cause_bars(frame, view)
    f = v.frame
    assert f.cause_code.tolist() == [w[0] for w in want], "sorted by days (high first), then by cause code"
    assert f.days.tolist() == [w[1] for w in want] and f.events.tolist() == [w[2] for w in want]
    assert f.share.tolist() == pytest.approx([w[3] for w in want], abs=5.1e-5)
    assert int(f.days.sum()) == total and v.n == n_events
    assert float(f.share.sum()) == pytest.approx(1.0, abs=1e-3 + 1e-4 * len(f)), "the shares add to one"
    assert (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("bars", "cause_code", "days", None, None, ("synthetic data",))
    return v


def test_oracle_cause_bars_view_days_per_cause():
    """route: hand worked days, events and shares per cause of a frame with two views, responsible parties summed and a null cause."""
    cs = pd.DataFrame({"view": ["all_events"] * 8 + ["full_linked"] * 2,
                       "cause_code": ["ground_conditions", "ground_conditions", "permit_delay", "weather", "design_error", None, "ground_conditions", "weather", "ground_conditions", "weather"],
                       "responsible_party": ["customer", "contractor", "authority", "force_majeure", "contractor", "shared", "shared", "shared", "customer", "force_majeure"],
                       "days": [40, 20, 25, 8, 5, 5, 0, 0, 7, 3], "events": [4, 2, 3, 1, 2, 1, 0, 0, 1, 1]})
    before = cs.copy()
    v = delivery.cause_bars_view(cs, context=CTX)
    assert v.frame.cause_code.tolist() == ["ground_conditions", "permit_delay", "weather", "(unknown)", "design_error"], "sorted by days; a tie at 5 days goes by cause code and a null cause is the bar '(unknown)'"
    assert v.frame.days.tolist() == [60, 25, 8, 5, 5] and v.frame.events.tolist() == [6, 3, 1, 1, 2]
    assert v.frame.share.tolist() == [0.5825, 0.2427, 0.0777, 0.0485, 0.0485], "60, 25, 8 and 5 of 103 days, four decimals"
    assert v.n == 13 and float(v.frame.share.sum()) == pytest.approx(1.0, abs=1e-3), "events of the view; shares from the summed days"
    f = delivery.cause_bars_view(cs, view="full_linked", context=CTX)
    assert f.frame.cause_code.tolist() == ["ground_conditions", "weather"] and f.frame.days.tolist() == [7, 3] and f.frame.share.tolist() == [0.7, 0.3] and f.n == 2
    _check_cause_bars(cs, "all_events")
    _check_cause_bars(cs, "full_linked")
    cap = delivery.cause_bars_view(cs, as_of="2026-11-30", legacy=4, context=CTX).caption
    assert "view all_events" in cap and "as of 2026-11-30" in cap and "4 legacy projects" in cap and cap.endswith("synthetic data")
    pd.testing.assert_frame_equal(cs, before)
    with pytest.raises(FrameError, match="no rows for the view"):
        delivery.cause_bars_view(cs, view="missing", context=CTX)


@pytest.mark.release
def test_oracle_cause_bars_view_baseline_days_per_cause(load):
    """route: delay days and events per cause counted with a python loop over the baseline delay_event rows and compared per cause for both views."""
    de, pj = load("projects", "delay_event"), load("projects", "project")
    full = set(pj.loc[pj["data_depth"] == "full", "prj_key"])
    linked = de[de["prj_key"].isin(full) & de["mtg_key"].notna()]
    parts = []
    for name, x in (("all_events", de), ("full_linked", linked)):
        parts.append(x.groupby(["cause_code", "responsible_party"], as_index=False).agg(days=("days", "sum"), events=("days", "size")).assign(view=name))
    cs = pd.concat(parts, ignore_index=True)
    a = _check_cause_bars(cs, "all_events")
    assert a.n == len(de) and int(a.frame.days.sum()) == int(de["days"].sum()), "every delay event is in a bar"
    b = _check_cause_bars(cs, "full_linked")
    assert b.n == len(linked)
    by_cause = {}
    for c, d in zip(de["cause_code"], de["days"]):
        by_cause[c] = by_cause.get(c, 0) + int(d)
    assert dict(zip(a.frame.cause_code, a.frame.days)) == by_cause, "days per cause straight from the delay events"


# --------------------------------------------------------------------------------------------------------- experience_network_view
_EDGE_COLS = ["prj_key", "emp_key", "roles", "start", "end", "hours_total", "basis", "legacy"]


def _network(edges, leavers):
    """An ExperienceNetwork built by hand from edge rows: a node per person and per project, `leavers` marks persons."""
    e = pd.DataFrame(edges, columns=_EDGE_COLS)
    persons, projects = sorted(set(e["emp_key"])), sorted(set(e["prj_key"]))
    nodes = pd.DataFrame({"node_key": persons + projects, "kind": ["person"] * len(persons) + ["project"] * len(projects), "leaver": [p in leavers for p in persons] + [False] * len(projects)})
    pairs = pd.DataFrame({"prj_key": ["P1"], "emp_a": ["e1"], "emp_b": ["e2"], "overlap_days": [31]})
    return ExperienceNetwork(nodes, e, pairs)


def test_oracle_experience_network_view_counts_and_pass_through():
    """route: a hand built network of five edges whose legacy edges and leavers are counted by eye, then the pass through of edges, nodes and pairs and the empty network."""
    edges = [("P1", "e1", "foreman", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-03-31"), 100.0, "time_entries", False),
             ("P1", "e2", "engineer; lead", pd.Timestamp("2025-03-01"), pd.Timestamp("2025-07-31"), 75.0, "mixed", False),
             ("P2", "e1", "foreman", pd.Timestamp("2025-02-01"), pd.Timestamp("2025-02-28"), 8.0, "roster", True),
             ("P2", "e3", "fitter", pd.Timestamp("2025-02-15"), pd.Timestamp("2025-03-15"), 9.0, "roster", True),
             ("P3", "e3", "fitter", pd.Timestamp("2025-04-01"), pd.Timestamp("2025-04-30"), 4.0, "time_entries", None)]
    net = _network(edges, leavers={"e2", "e3"})
    v = delivery.experience_network_view(net, as_of="2026-11-30", n_no_route=3, context=CTX)
    pd.testing.assert_frame_equal(v.frame, net.edges)
    assert v.n == 5 and (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("network", "emp_key", "prj_key", None, None, ("synthetic data",))
    assert set(v.extra) == {"nodes", "pairs"}
    pd.testing.assert_frame_equal(v.extra["nodes"], net.nodes)
    pd.testing.assert_frame_equal(v.extra["pairs"], net.pairs)
    assert "2 legacy edges (hours estimated)" in v.caption, "two edges are legacy; a null flag is not legacy"
    assert "2 leavers marked" in v.caption, "e2 and e3 are leavers; project nodes are not people"
    assert "3 projects without a route length" in v.caption and "as of 2026-11-30" in v.caption and v.caption.endswith("synthetic data")
    assert set(v.extra["nodes"].node_key) == set(v.frame.emp_key) | set(v.frame.prj_key), "the nodes are the distinct persons and projects of the edge list"
    assert "without a route length" not in delivery.experience_network_view(net, context=CTX).caption and "as of" not in delivery.experience_network_view(net, context=CTX).caption
    none_legacy = _network([e[:-1] + (False,) for e in edges], leavers=set())
    c = delivery.experience_network_view(none_legacy, n_no_route=0, context=CTX).caption
    assert "0 legacy edges" in c and "0 leavers marked" in c and "0 projects without a route length" in c
    empty = ExperienceNetwork(pd.DataFrame({"node_key": [], "kind": [], "leaver": []}), pd.DataFrame(columns=_EDGE_COLS), pd.DataFrame({"prj_key": [], "emp_a": [], "emp_b": [], "overlap_days": []}))
    ev = delivery.experience_network_view(empty, context=CTX)
    assert ev.n == 0 and "0 legacy edges" in ev.caption and "0 leavers marked" in ev.caption
    with pytest.raises(FrameError, match="result of experience_network"):
        delivery.experience_network_view(net.edges, context=CTX)
    with pytest.raises(FrameError, match="result of experience_network"):
        delivery.experience_network_view(tuple(net), context=CTX)


@pytest.mark.release
def test_oracle_experience_network_view_baseline_counts(load):
    """route: edges, legacy edges, leavers and projects without a route length counted with pandas over the baseline project_role and project rows."""
    pr, pj = load("projects", "project_role"), load("projects", "project")
    keys = pj[(pj["country"] == "DE") & (pj["type"] == "dh_network")]["prj_key"].tolist()
    sub = pr[pr["prj_key"].isin(keys)]
    persons = sorted(set(sub["emp_key"]))
    leavers = set(persons[::3])
    emp = pd.DataFrame({"emp_key": persons, "leave_date": ["2026-06-30" if p in leavers else None for p in persons]})
    net = delivery.experience_network(pr, pj, keys, emp, as_of="2026-11-30", context=CTX)
    pairs = set(zip(sub["prj_key"], sub["emp_key"]))
    leg = set(pj.loc[pj["legacy"], "prj_key"])
    no_route = int(pj[pj["prj_key"].isin(set(sub["prj_key"]))]["route_length_m"].isna().sum())
    v = delivery.experience_network_view(net, as_of="2026-11-30", n_no_route=no_route, context=CTX)
    assert v.n == len(v.frame) == len(pairs) > 0, "one edge per person and project of the role rows"
    assert set(zip(v.frame.prj_key, v.frame.emp_key)) == pairs and not v.frame.duplicated(["prj_key", "emp_key"]).any()
    assert abs(float(v.frame.hours_total.sum()) - float(sub["hours_total"].sum())) < 0.01 * len(pairs), "the hours of the role rows are all on the edges"
    n_leg = sum(1 for p, _ in pairs if p in leg)
    n_leavers = len(leavers)
    assert f"{n_leg} legacy edges (hours estimated), {n_leavers} leavers marked" in v.caption and n_leavers > 0
    assert f"{no_route} projects without a route length" in v.caption
    assert set(v.extra["nodes"].node_key) == {e for _, e in pairs} | {p for p, _ in pairs}, "nodes are the distinct persons and projects of the edges"


# --------------------------------------------------------------------------------------------------------- gantt_view
_GANTT_COLS = ["prj_key", "activity_code", "name", "baseline_start", "baseline_end", "latest_start", "latest_end", "actual_start", "actual_end", "critical"]


def _gantt_expected(frame, as_of):
    """Bars (prj, code, name, series, start, end, in_progress, critical) by a plain loop over the activities, in the order baseline start (none last), key, series."""
    day = None if as_of is None else pd.Timestamp(as_of).normalize()
    bars = []
    for r in frame.to_dict("records"):
        for series, s, e in (("baseline", "baseline_start", "baseline_end"), ("latest", "latest_start", "latest_end"), ("actual", "actual_start", "actual_end")):
            start, end, prog = _ts(r[s]), _ts(r[e]), False
            if start is None:
                continue
            if series == "actual" and day is not None:
                if start > day:
                    continue
                prog = end is None or end > day
                end = day if prog else end
            if end is None:
                continue
            assert end >= start
            bars.append((r["prj_key"], r["activity_code"], r["name"], series, start, end, prog, bool(r["critical"])))
    first = {(r["prj_key"], r["activity_code"], r["name"]): _ts(r["baseline_start"]) for r in frame.to_dict("records")}
    far = pd.Timestamp.max

    def key(b):
        return (first[b[:3]] or far, b[0], b[1], b[2], b[3])
    return sorted(bars, key=key)


def _gantt_rows(spec):
    return [(r.prj_key, r.activity_code, r.name, r.series, r.start, r.end, bool(r.in_progress), bool(r.critical)) for r in spec.frame.itertuples()]


def test_oracle_gantt_view_bars_per_activity():
    """route: a hand worked table of the bars of nine activities (as-of day, no day, boundaries on the day) written out in the test."""
    ap = pd.DataFrame([
        ("P1", "A1", "dig", "2025-01-01", "2025-01-31", "2025-01-10", "2025-02-15", "2025-01-12", "2025-02-20", True),
        ("P1", "A2", "weld", "2025-03-01", "2025-03-31", "2025-03-01", "2025-03-31", "2025-03-05", None, False),
        ("P1", "A3", "test", "2025-02-01", "2025-02-28", "2025-02-01", "2025-04-30", None, None, False),
        ("P2", "A4", "dig", "2025-01-01", "2025-01-20", "2025-01-01", "2025-01-20", "2025-07-01", None, False),
        ("P2", "A5", "weld", None, None, "2025-05-01", "2025-05-31", None, None, True),
        ("P1", "A6", "fill", "2025-04-01", "2025-04-30", "2025-04-01", "2025-04-30", "2025-04-02", "2025-09-01", False),
        ("P1", "A7", "lay", "2025-05-01", "2025-05-31", "2025-05-01", "2025-05-31", "2025-05-02", "2025-06-30", False),
        ("P1", "A8", "seal", "2025-06-01", "2025-06-30", "2025-06-01", "2025-06-30", "2025-06-30", None, False),
        ("P1", "A9", "clean", "2025-07-01", "2025-07-31", "2025-07-01", None, None, None, False)], columns=_GANTT_COLS)
    before = ap.copy()
    T = pd.Timestamp
    g = delivery.gantt_view(ap, as_of="2025-06-30", legacy=4, context=CTX)
    assert _gantt_rows(g) == [
        ("P1", "A1", "dig", "actual", T("2025-01-12"), T("2025-02-20"), False, True), ("P1", "A1", "dig", "baseline", T("2025-01-01"), T("2025-01-31"), False, True), ("P1", "A1", "dig", "latest", T("2025-01-10"), T("2025-02-15"), False, True),
        ("P2", "A4", "dig", "baseline", T("2025-01-01"), T("2025-01-20"), False, False), ("P2", "A4", "dig", "latest", T("2025-01-01"), T("2025-01-20"), False, False),
        ("P1", "A3", "test", "baseline", T("2025-02-01"), T("2025-02-28"), False, False), ("P1", "A3", "test", "latest", T("2025-02-01"), T("2025-04-30"), False, False),
        ("P1", "A2", "weld", "actual", T("2025-03-05"), T("2025-06-30"), True, False), ("P1", "A2", "weld", "baseline", T("2025-03-01"), T("2025-03-31"), False, False), ("P1", "A2", "weld", "latest", T("2025-03-01"), T("2025-03-31"), False, False),
        ("P1", "A6", "fill", "actual", T("2025-04-02"), T("2025-06-30"), True, False), ("P1", "A6", "fill", "baseline", T("2025-04-01"), T("2025-04-30"), False, False), ("P1", "A6", "fill", "latest", T("2025-04-01"), T("2025-04-30"), False, False),
        ("P1", "A7", "lay", "actual", T("2025-05-02"), T("2025-06-30"), False, False), ("P1", "A7", "lay", "baseline", T("2025-05-01"), T("2025-05-31"), False, False), ("P1", "A7", "lay", "latest", T("2025-05-01"), T("2025-05-31"), False, False),
        ("P1", "A8", "seal", "actual", T("2025-06-30"), T("2025-06-30"), True, False), ("P1", "A8", "seal", "baseline", T("2025-06-01"), T("2025-06-30"), False, False), ("P1", "A8", "seal", "latest", T("2025-06-01"), T("2025-06-30"), False, False),
        ("P1", "A9", "clean", "baseline", T("2025-07-01"), T("2025-07-31"), False, False),
        ("P2", "A5", "weld", "latest", T("2025-05-01"), T("2025-05-31"), False, True)], \
        "A4 starts after the day: no actual bar; A6 ends after the day: cut at the day and in progress; A7 ends on the day: not in progress; A8 starts on the day: a bar of one day; A9 has no latest end: no latest bar; A5 has no baseline: sorted last"
    assert (g.kind, g.x, g.y, g.group, g.value, g.n) == ("gantt", "start", "name", "series", None, 9) and "4 legacy projects" in g.caption and "without an as-of day" not in g.caption
    n = delivery.gantt_view(ap, context=CTX)
    assert _gantt_rows(n) == _gantt_expected(ap, None) and "without an as-of day" in n.caption
    assert [b for b in _gantt_rows(n) if b[3] == "actual"] == [("P1", "A1", "dig", "actual", T("2025-01-12"), T("2025-02-20"), False, True), ("P1", "A6", "fill", "actual", T("2025-04-02"), T("2025-09-01"), False, False),
                                                              ("P1", "A7", "lay", "actual", T("2025-05-02"), T("2025-06-30"), False, False)], "without a day only the finished activities have an actual bar (A2, A4 and A8 are unfinished)"
    assert not n.frame.in_progress.any() and len(n.frame) == len(_gantt_expected(ap, None))
    for day in ("2025-01-11", "2025-02-20", "2025-03-05", "2025-12-31"):
        assert _gantt_rows(delivery.gantt_view(ap, as_of=day, context=CTX)) == _gantt_expected(ap, day), day
    on_start = _gantt_rows(delivery.gantt_view(ap.iloc[[0]], as_of="2025-01-12", context=CTX))
    assert [b for b in on_start if b[3] == "actual"] == [("P1", "A1", "dig", "actual", T("2025-01-12"), T("2025-01-12"), True, True)], "an actual that starts on the day is a one day bar in progress"
    before_day = _gantt_rows(delivery.gantt_view(ap.iloc[[0]], as_of="2025-01-11", context=CTX))
    assert [b[3] for b in before_day] == ["baseline", "latest"], "an actual that starts after the day is not drawn"
    pd.testing.assert_frame_equal(ap, before)
    with pytest.raises(FrameError, match="ends before"):
        delivery.gantt_view(ap.assign(actual_end=["2025-01-01"] + ap.actual_end.tolist()[1:]), context=CTX)


@pytest.mark.release
def test_oracle_gantt_view_baseline_bars(load):
    """route: baseline, latest and actual dates read with pandas groupby from the baseline plan_activity and actual_activity rows, the bars rebuilt with a python loop and compared in order."""
    pa, aa = load("projects", "plan_activity"), load("projects", "actual_activity")
    pa = pa.sort_values(["prj_key", "activity_code", "plan_version"])
    first = pa.groupby(["prj_key", "activity_code"], as_index=False).first()
    last = pa.groupby(["prj_key", "activity_code"], as_index=False).last()
    ap = first[["prj_key", "activity_code", "start", "end"]].rename(columns={"start": "baseline_start", "end": "baseline_end"}).merge(
        last[["prj_key", "activity_code", "name", "start", "end", "critical"]].rename(columns={"start": "latest_start", "end": "latest_end"}), on=["prj_key", "activity_code"]).merge(
        aa[["prj_key", "activity_code", "actual_start", "actual_end"]], on=["prj_key", "activity_code"], how="left")
    assert len(ap) == len(first) and ap.actual_start.notna().sum() == len(aa)
    for day in (None, "2025-12-31", "2026-11-30"):
        v = delivery.gantt_view(ap, as_of=day, context=CTX)
        assert _gantt_rows(v) == _gantt_expected(ap, day), day
        assert v.n == len(ap) and set(v.frame.series) == {"baseline", "latest", "actual"}
        bl = v.frame[v.frame.series == "baseline"].merge(ap[["prj_key", "activity_code", "baseline_start", "baseline_end"]], on=["prj_key", "activity_code"])
        assert len(bl) == len(ap) and (bl.start == pd.to_datetime(bl.baseline_start)).all() and (bl.end == pd.to_datetime(bl.baseline_end)).all(), "the bars carry the input dates"
        assert len(v.frame[v.frame.series == "latest"]) == len(ap)
    v = delivery.gantt_view(ap, as_of="2026-11-30", context=CTX).frame
    assert int(v.in_progress.sum()) == int(((aa["actual_end"].isna()) | (pd.to_datetime(aa["actual_end"]) > pd.Timestamp("2026-11-30"))).sum()), "in progress: started and not finished on the day"


# --------------------------------------------------------------------------------------------------------- performance_view
def _performance_expected(frame):
    due, on = defaultdict(int), defaultdict(int)
    for s, d, o in zip(frame["sup_key"], frame["lines_due"], frame["lines_on_time"]):
        due[s] += int(d)
        on[s] += int(o)
    return {s: (due[s], on[s], round(100.0 * on[s] / due[s], 2) if due[s] > 0 else None) for s in sorted(due)}


def _check_performance(frame):
    v = delivery.performance_view(frame, context=CTX)
    want = _performance_expected(frame)
    assert v.frame.sup_key.tolist() == sorted(want), "one row per supplier, sorted by key"
    for r in v.frame.itertuples():
        d, o, pct = want[r.sup_key]
        assert (int(r.lines_due), int(r.lines_on_time)) == (d, o), r.sup_key
        if pct is None:
            assert pd.isna(r.on_time_percent), r.sup_key
        else:
            assert r.on_time_percent == pytest.approx(pct, abs=0.0051), r.sup_key
    assert v.n == int(frame["lines_due"].sum()) and (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("bars", "sup_key", "on_time_percent", None, None, ("synthetic data",))
    return v


def test_oracle_performance_view_summed_lines():
    """route: hand worked on time shares from summed lines (62.5 where the mean of the window percents is 75), a zero due supplier, rounding and the lead time pass through."""
    pf = pd.DataFrame({"sup_key": ["S2", "S1", "S3", "S1", "S0", "S2", "S4"], "period": ["2025-01", "2025-01", "2025-01", "2025-02", "2025-01", "2025-02", "2025-01"],
                       "lines_due": [3, 10, 0, 30, 7, 0, 7], "lines_on_time": [1, 10, 0, 15, 7, 0, 5]})
    before = pf.copy()
    v = delivery.performance_view(pf, as_of="2026-11-30", context=CTX)
    f = v.frame.set_index("sup_key")
    assert v.frame.sup_key.tolist() == ["S0", "S1", "S2", "S3", "S4"]
    assert f.lines_due.to_dict() == {"S0": 7, "S1": 40, "S2": 3, "S3": 0, "S4": 7} and f.lines_on_time.to_dict() == {"S0": 7, "S1": 25, "S2": 1, "S3": 0, "S4": 5}
    assert f.loc["S0", "on_time_percent"] == 100.0 and f.loc["S1", "on_time_percent"] == 62.5, "25 of 40 lines, not the mean of 100 and 50"
    assert f.loc["S2", "on_time_percent"] == 33.33 and f.loc["S4", "on_time_percent"] == 71.43, "two decimals"
    assert pd.isna(f.loc["S3", "on_time_percent"]), "no line due: no share, not zero and not 100"
    assert v.n == 57 and v.extra == {} and "as of 2026-11-30" in v.caption
    _check_performance(pf)
    lead = pd.DataFrame({"sup_key": ["S1", "S0", "S1"], "itm_key": ["I2", "I1", "I3"], "previous_weeks": [4, 6, None], "lead_time_weeks": [8, 6, 3], "change_weeks": [4, 0, None], "note": ["x", "y", "z"]},
                        index=[7, 3, 5])
    lv = delivery.performance_view(pf, lead, context=CTX).extra["lead_times"]
    pd.testing.assert_frame_equal(lv, lead[["sup_key", "itm_key", "previous_weeks", "lead_time_weeks", "change_weeks"]].reset_index(drop=True))
    short = delivery.performance_view(pf, lead[["sup_key", "itm_key", "lead_time_weeks"]], context=CTX).extra["lead_times"]
    assert short.columns.tolist() == ["sup_key", "itm_key", "lead_time_weeks"]
    pd.testing.assert_frame_equal(pf, before)
    with pytest.raises(FrameError, match="more lines on time"):
        delivery.performance_view(pf.assign(lines_on_time=[1, 10, 0, 31, 7, 0, 5]), context=CTX)
    with pytest.raises(FrameError, match="nulls"):
        delivery.performance_view(pf.assign(lines_due=[3, 10, None, 30, 7, 0, 7]), context=CTX)


@pytest.mark.release
def test_oracle_performance_view_baseline_suppliers(load):
    """route: lines due and on time summed per supplier with a python loop over the baseline supplier_performance rows, compared per supplier for all months and for a window, and one month against the table's own percent."""
    sp = load("procurement", "supplier_performance")
    v = _check_performance(sp)
    assert len(v.frame) == sp["sup_key"].nunique() and v.n == int(sp["lines_due"].sum())
    win = sp[(sp["period"] >= "2025-01") & (sp["period"] <= "2025-06")]
    _check_performance(win)
    one = sp[(sp["period"] == "2025-06") & (sp["lines_due"] > 0)]
    o = delivery.performance_view(one, context=CTX).frame.set_index("sup_key")["on_time_percent"]
    assert (o - one.set_index("sup_key")["on_time_percent"]).abs().max() <= 0.051, "for one month the share is the figure the table itself reports (one decimal)"
    lt = load("inventory", "lead_time")
    lead = delivery.performance_view(win, lt, context=CTX).extra["lead_times"]
    pd.testing.assert_frame_equal(lead, lt[["sup_key", "itm_key", "lead_time_weeks"]].reset_index(drop=True))


# --------------------------------------------------------------------------------------------------------- stock_view
_STOCK_COLS = ["as_of", "site_key", "itm_key", "on_hand", "reserved", "available"]
_ORDER = {"available": 0, "on_hand": 1, "reserved": 2}


def _stock_expected(frame):
    """Long rows (itm, site, as_of, series, quantity) from the three measure columns of each row, in the order item, site, date, series."""
    out = []
    for r in frame.to_dict("records"):
        for s in ("on_hand", "reserved", "available"):
            out.append((r["itm_key"], r["site_key"], r["as_of"], s, r[s]))
    return sorted(out, key=lambda t: (t[0], t[1], t[2], t[3]))


def _check_stock(frame):
    v = delivery.stock_view(frame, context=CTX)
    got = [(r.itm_key, r.site_key, r.as_of, r.series, r.quantity) for r in v.frame.itertuples()]
    assert got == _stock_expected(frame), "three rows per input row, with its own quantities, sorted by item, site, date and series"
    assert len(v.frame) == 3 * len(frame) and v.n == len(frame)
    q = {(r.itm_key, r.site_key, r.as_of, r.series): r.quantity for r in v.frame.itertuples()}
    assert len(q) == len(v.frame), "no cell is twice in the long frame"
    for k in {(a, b, c) for a, b, c, _ in q}:
        assert q[k + ("available",)] == pytest.approx(q[k + ("on_hand",)] - q[k + ("reserved",)]), k
    assert (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("lines", "as_of", "quantity", "series", None, ("synthetic data",))
    return v


def test_oracle_stock_view_long_frame_per_key():
    """route: hand written quantities of two items, two sites and two dates, the long frame compared per key, available equal to on hand less reserved, and the open lines carried unchanged."""
    st = pd.DataFrame([("2026-02-01", "S2", "I2", 10.0, 4.0, 6.0), ("2026-01-01", "S1", "I2", 8.0, 0.0, 8.0), ("2026-02-01", "S1", "I1", 5.5, 1.5, 4.0), ("2026-01-01", "S2", "I1", 2.0, 2.0, 0.0),
                       ("2026-02-01", "S1", "I2", 9.0, 3.0, 6.0), ("2026-01-01", "S1", "I1", 7.0, 1.0, 6.0)], columns=_STOCK_COLS)
    before = st.copy()
    v = _check_stock(st)
    assert v.frame.itm_key.tolist() == ["I1"] * 9 + ["I2"] * 9, "items are never added together"
    first = v.frame.iloc[:3]
    assert first.site_key.tolist() == ["S1"] * 3 and first.as_of.tolist() == ["2026-01-01"] * 3 and first.series.tolist() == ["available", "on_hand", "reserved"] and first.quantity.tolist() == [6.0, 7.0, 1.0]
    assert v.frame[(v.frame.itm_key == "I1") & (v.frame.site_key == "S2")].quantity.tolist() == [0.0, 2.0, 2.0] and v.extra == {}
    assert v.frame.dtypes["quantity"] == "float64" and v.frame.index.tolist() == list(range(18))
    ol = pd.DataFrame({"itm_key": ["I2", "I1", "I2"], "po_key": ["PO-2", "PO-1", "PO-3"], "line_no": [1, 2, 1], "promised_date": ["2026-03-01", "2026-02-15", "2026-04-01"], "remaining": [3.0, 0.5, 9.0], "unit": ["pcs"] * 3},
                      index=[4, 9, 2])
    o = delivery.stock_view(st, ol, as_of="2026-02-01", context=CTX)
    pd.testing.assert_frame_equal(o.extra["orders"], ol[["itm_key", "po_key", "line_no", "promised_date", "remaining"]].reset_index(drop=True))
    assert list(o.extra) == ["orders"] and "as of 2026-02-01" in o.caption
    pd.testing.assert_frame_equal(o.frame, v.frame)
    short = delivery.stock_view(st, ol[["itm_key", "remaining"]], context=CTX).extra["orders"]
    assert short.columns.tolist() == ["itm_key", "remaining"] and short.remaining.tolist() == [3.0, 0.5, 9.0]
    pd.testing.assert_frame_equal(st, before)
    with pytest.raises(FrameError, match="lacks column"):
        delivery.stock_view(st, ol.drop(columns="remaining"), context=CTX)
    with pytest.raises(FrameError, match="lacks column"):
        delivery.stock_view(st.drop(columns="reserved"), context=CTX)


@pytest.mark.release
def test_oracle_stock_view_baseline_levels(load):
    """route: the long frame of three baseline stock_level dates compared per (item, site, date, series) with the table columns, and open lines cut from the baseline po_line rows."""
    sl = load("inventory", "stock_level")
    all_dates = sorted(sl["as_of_date"].unique())
    dates = [all_dates[0], all_dates[len(all_dates) // 2], all_dates[-1]]
    st = sl[sl["as_of_date"].isin(dates)].rename(columns={"as_of_date": "as_of"})[_STOCK_COLS].reset_index(drop=True)
    assert st["as_of"].nunique() == 3 and len(st) > 0
    assert ((st["available"] - (st["on_hand"] - st["reserved"])).abs() < 1e-9).all(), "the baseline levels keep available = on hand less reserved"
    v = _check_stock(st)
    assert v.n == len(st) and v.frame.groupby("series").quantity.sum().to_dict() == pytest.approx({"on_hand": st.on_hand.sum(), "reserved": st.reserved.sum(), "available": st.available.sum()}), "the sums of the three series are the sums of the table columns"
    po = load("procurement", "po_line")
    ol = po.assign(remaining=po["qty"] - po["received_qty"])
    ol = ol[ol["remaining"] > 0][["itm_key", "po_key", "line_no", "promised_date", "remaining"]].head(300)
    got = delivery.stock_view(st, ol, context=CTX).extra["orders"]
    pd.testing.assert_frame_equal(got, ol.reset_index(drop=True))


# --------------------------------------------------------------------------------------------------------- timeline_view
def _timeline_expected(tl, att, wd):
    """Rows (date, lane, label, source, source_key, n_invited, n_present) of the spec: the input rows in order, the write down after the last row on or before its date."""
    inv, pres = defaultdict(int), defaultdict(int)
    if att is not None:
        for m, p in zip(att["mtg_key"], att["present"]):
            inv[m] += 1
            pres[m] += int(bool(p))
    rows = []
    for r in tl.to_dict("records"):
        meeting = r["kind"] == "meeting"
        rows.append((r["date"], r["kind"], r["text"], r["source"], r["source_key"], inv[r["source_key"]] if att is not None and meeting else None, pres[r["source_key"]] if att is not None and meeting else None))
    if wd is not None:
        d = pd.Timestamp(wd["date"])
        at = max([i for i, r in enumerate(rows) if pd.Timestamp(r[0]) <= d], default=-1)
        rows.insert(at + 1, (d, "write_down", f"{round(wd['amount'])} {wd['currency']}", "finance", "", None, None))
    return rows


def _timeline_rows(spec, with_att):
    f = spec.frame
    cols = ["date", "lane", "label", "source", "source_key"] + (["n_invited", "n_present"] if with_att else [])
    out = []
    for r in f[cols].itertuples(index=False):
        r = list(r)
        if with_att:
            r[5:] = [None if pd.isna(x) else int(x) for x in r[5:]]
        out.append(tuple(r) if with_att else tuple(r) + (None, None))
    return out


def _same_rows(got, want):
    assert len(got) == len(want), (len(got), len(want))
    for g, w in zip(got, want):
        assert (pd.Timestamp(g[0]), *g[1:]) == (pd.Timestamp(w[0]), *w[1:]), (g, w)


def test_oracle_timeline_view_order_and_attendance():
    """route: a hand written seven row timeline with attendance counted by eye, the write down placed by hand at five dates, and the rows compared with the input in order."""
    T = pd.Timestamp
    tl = pd.DataFrame({"date": [T("2025-01-01")] * 3 + [T("2025-01-02"), T("2025-01-15"), T("2025-02-01"), T("2025-03-01")],
                       "kind": ["meeting", "decision", "decision", "delay_event", "meeting", "risk", "plan_version"],
                       "source": ["projects.meeting", "projects.decision", "projects.decision", "projects.delay_event", "projects.meeting", "projects.risk", "projects.plan_version"],
                       "source_key": ["MTG-1", "MTG-1/2", "MTG-1/1", "1", "MTG-2", "1", "2"],
                       "text": ["kick off", "second", "first", "ground, 52 days", "review", "late permit", "re-plan"]})
    att = pd.DataFrame({"mtg_key": ["MTG-1"] * 3 + ["MTG-2"] * 2 + ["MTG-9"], "present": [True, False, True, False, False, True]})
    before = (tl.copy(), att.copy())
    v = delivery.timeline_view(tl, att, as_of="2026-11-30", context=CTX)
    assert v.frame.lane.tolist() == ["meeting", "decision", "decision", "delay_event", "meeting", "risk", "plan_version"], "the order of the input is kept: a meeting before its decisions on the same date"
    assert v.frame.label.tolist() == tl.text.tolist() and v.frame.source_key.tolist() == ["MTG-1", "MTG-1/2", "MTG-1/1", "1", "MTG-2", "1", "2"], "no event is lost or reordered, decisions keep their order"
    assert v.frame.n_invited.fillna(-1).tolist() == [3, -1, -1, -1, 2, -1, -1] and v.frame.n_present.fillna(-1).tolist() == [2, -1, -1, -1, 0, -1, -1], "attendance only on meeting rows; the meeting of another project is ignored"
    assert (v.kind, v.x, v.y, v.group, v.value, v.n, v.labels) == ("timeline", "date", "lane", "lane", None, 7, ("synthetic data",)) and "as of 2026-11-30" in v.caption
    assert "n_invited" not in delivery.timeline_view(tl, context=CTX).frame.columns
    for wd, lanes in ((("2025-01-20"), ["meeting", "decision", "decision", "delay_event", "meeting", "write_down", "risk", "plan_version"]),
                      ("2025-01-15", ["meeting", "decision", "decision", "delay_event", "meeting", "write_down", "risk", "plan_version"]),
                      ("2025-01-01", ["meeting", "decision", "decision", "write_down", "delay_event", "meeting", "risk", "plan_version"]),
                      ("2024-12-31", ["write_down", "meeting", "decision", "decision", "delay_event", "meeting", "risk", "plan_version"]),
                      ("2026-01-01", ["meeting", "decision", "decision", "delay_event", "meeting", "risk", "plan_version", "write_down"])):
        w = delivery.timeline_view(tl, att, {"date": wd, "amount": 1500000, "currency": "EUR"}, context=CTX)
        assert w.frame.lane.tolist() == lanes, f"the write down of {wd} follows the last row on or before its date"
        row = w.frame[w.frame.lane == "write_down"].iloc[0]
        assert (row.label, row.source, row.source_key, row.date) == ("1500000 EUR", "finance", "", T(wd)) and w.n == 7, "amount without separators, in its currency; the write down is not an event of the input"
        _same_rows(_timeline_rows(w, True), _timeline_expected(tl, att, {"date": wd, "amount": 1500000, "currency": "EUR"}))
    odd = delivery.timeline_view(tl, None, {"date": "2025-01-20", "amount": 2500000.6, "currency": "DKK"}, context=CTX).frame
    assert odd.label.tolist()[5] == "2500001 DKK"
    clash = tl.assign(kind=["decision", "meeting", "meeting", "delay_event", "meeting", "risk", "plan_version"])
    assert delivery.timeline_view(clash, context=CTX).frame.lane.tolist() == clash.kind.tolist(), "no sorting of its own: the lanes are the input order"
    pd.testing.assert_frame_equal(tl, before[0])
    pd.testing.assert_frame_equal(att, before[1])
    with pytest.raises(FrameError, match="nulls"):
        delivery.timeline_view(tl, att.assign(present=[True, None, True, False, False, True]), context=CTX)
    with pytest.raises(FrameError, match="write_down"):
        delivery.timeline_view(tl, None, {"date": "2025-01-20", "amount": 1}, context=CTX)


@pytest.mark.release
def test_oracle_timeline_view_baseline_projects(load):
    """route: for six baseline projects the timeline rows are cut from the meeting, decision, delay_event, risk and plan_version tables with pandas, attendance counted per meeting, and the spec compared row by row with a python placement of the write down."""
    mt, de, dl, rk, pv, ma = (load("projects", t) for t in ("meeting", "decision", "delay_event", "risk", "plan_version", "meeting_attendance"))
    wd_row = de[de["decision_type"] == "write_down"].iloc[0]
    wd_prj = mt.set_index("mtg_key").loc[wd_row["mtg_key"], "prj_key"]
    wd_date = mt.set_index("mtg_key").loc[wd_row["mtg_key"], "date"]
    projects = [wd_prj] + sorted(set(mt["prj_key"]) - {wd_prj})[:5]
    rank = {"meeting": 0, "decision": 1, "delay_event": 2, "risk": 3, "plan_version": 4}
    checked = 0
    for p in projects:
        m = mt[mt["prj_key"] == p]
        d = de.merge(m[["mtg_key", "date"]], on="mtg_key")
        rows = ([(r.date, "meeting", r.title, "projects.meeting", r.mtg_key, i) for i, r in enumerate(m.itertuples())]
                + [(r.date, "decision", f"{r.decision_type}: {r.text}", "projects.decision", f"{r.mtg_key}/{r.seq}", i) for i, r in enumerate(d.itertuples())]
                + [(r.start, "delay_event", f"{r.cause_code}, {r.days} days", "projects.delay_event", str(r.seq), i) for i, r in enumerate(dl[dl["prj_key"] == p].itertuples())]
                + [(r.raised, "risk", r.title, "projects.risk", str(r.risk_no), i) for i, r in enumerate(rk[rk["prj_key"] == p].itertuples())]
                + [(r.created, "plan_version", r.reason, "projects.plan_version", str(r.plan_version), i) for i, r in enumerate(pv[pv["prj_key"] == p].itertuples())])
        rows.sort(key=lambda t: (t[0], rank[t[1]], t[5]))
        tl = pd.DataFrame([t[:5] for t in rows], columns=["date", "kind", "text", "source", "source_key"])
        tl["date"] = pd.to_datetime(tl["date"])
        att = ma[ma["mtg_key"].isin(m["mtg_key"])].assign(present=lambda f: f["status"] == "present")[["mtg_key", "present"]]
        assert len(tl) > 0
        for wd in (None, {"date": wd_date, "amount": float(wd_row["impact_cost"]), "currency": wd_row["currency"]} if p == wd_prj else {"date": tl["date"].iloc[len(tl) // 2], "amount": 123456.0, "currency": "DKK"}):
            v = delivery.timeline_view(tl, att, wd, context=CTX)
            _same_rows(_timeline_rows(v, True), _timeline_expected(tl, att, wd))
            assert v.n == len(tl)
        plain = delivery.timeline_view(tl, None, None, context=CTX).frame
        assert plain.lane.tolist() == tl.kind.tolist() and plain.source_key.tolist() == tl.source_key.tolist()
        mrows = v.frame[v.frame.lane == "meeting"]
        assert int(mrows.n_invited.sum()) == len(att) and int(mrows.n_present.sum()) == int(att["present"].sum()), "every attendee of the project's meetings is counted once"
        checked += len(tl)
    assert checked > 0 and wd_prj in projects


# --------------------------------------------------------------------------------------------------------- waterfall_view
def _waterfall_expected(lines, from_type, to_type):
    """{(currency, category): [from, to]} by a plain loop: a project counts in a currency when it has lines of both types in that currency."""
    have = defaultdict(set)
    for p, t, c in zip(lines["prj_key"], lines["type"], lines["currency"]):
        have[(c, p)].add(t)
    sums, included = defaultdict(lambda: [0.0, 0.0]), set()
    for p, t, cat, a, c in zip(lines["prj_key"], lines["type"], lines["category"], lines["amount"], lines["currency"]):
        if {from_type, to_type} <= have[(c, p)] and t in (from_type, to_type):
            cat = "(none)" if cat is None or (isinstance(cat, float) and math.isnan(cat)) else cat
            sums[(c, cat)][0 if t == from_type else 1] += float(a)
            included.add(p)
    for c in {k[0] for k in sums}:
        sums[(c, "total")] = [sum(v[0] for k, v in list(sums.items()) if k[0] == c and k[1] != "total"), sum(v[1] for k, v in list(sums.items()) if k[0] == c and k[1] != "total")]
    return dict(sums), len(included)


def _check_waterfall(lines, from_type="tender", to_type="final", tol=1e-9):
    v = delivery.waterfall_view(lines, from_type=from_type, to_type=to_type, context=CTX)
    want, n_proj = _waterfall_expected(lines, from_type, to_type)
    got = {(r.currency, r.category): (r.from_amount, r.to_amount, r.delta) for r in v.frame.itertuples()}
    assert set(got) == set(want) and len(v.frame) == len(want), "one row per currency and category, and a total row per currency"
    for k, (a, b) in want.items():
        assert got[k] == pytest.approx((a, b, b - a), abs=tol), k
    for c in {k[0] for k in got}:
        parts = [k for k in got if k[0] == c and k[1] != "total"]
        assert sum(got[k][2] for k in parts) == pytest.approx(got[(c, "total")][2], abs=tol) and got[(c, "total")][1] - got[(c, "total")][0] == pytest.approx(got[(c, "total")][2], abs=tol)
        idx = [i for i, r in enumerate(v.frame.itertuples()) if r.currency == c]
        assert idx == list(range(idx[0], idx[-1] + 1)) and v.frame.iloc[idx[-1]].category == "total", "a currency is one block with its total last"
    assert v.extra["n_projects"] == n_proj and (v.kind, v.x, v.y, v.group, v.value, v.labels) == ("waterfall", "category", "delta", "currency", None, ("synthetic data",))
    return v


def test_oracle_waterfall_view_steps():
    """route: hand worked category steps of three projects in two currencies (sums, deltas, totals, excluded projects, null category) written out in the test."""
    L = lambda *a: a  # noqa: E731
    rows = [L("P1", "tender", "labour", 100.0, "EUR"), L("P1", "tender", "material", 60.0, "EUR"), L("P1", "tender", None, 10.0, "EUR"),
            L("P1", "final", "labour", 130.0, "EUR"), L("P1", "final", "material", 45.0, "EUR"), L("P1", "final", "subcontractor", 20.0, "EUR"), L("P1", "budget", "labour", 120.0, "EUR"), L("P1", "forecast", "labour", 999.0, "EUR"),
            L("P2", "tender", "labour", 40.0, "EUR"), L("P2", "final", "labour", 55.0, "EUR"), L("P2", "final", "material", 5.0, "EUR"),
            L("P3", "tender", "labour", 1000.0, "DKK"), L("P3", "final", "labour", 900.0, "DKK"),
            L("P4", "tender", "labour", 500.0, "EUR"), L("P5", "final", "labour", 70.0, "DKK"),
            L("P6", "tender", "labour", 300.0, "EUR"), L("P6", "final", "labour", 330.0, "DKK")]
    ln = pd.DataFrame(rows, columns=["prj_key", "type", "category", "amount", "currency"])
    before = ln.copy()
    v = delivery.waterfall_view(ln, as_of="2026-11-30", legacy=4, context=CTX)
    got = [(r.currency, r.category, r.from_amount, r.to_amount, r.delta) for r in v.frame.itertuples()]
    assert got == [("DKK", "labour", 1000.0, 900.0, -100.0), ("DKK", "total", 1000.0, 900.0, -100.0),
                   ("EUR", "(none)", 10.0, 0.0, -10.0), ("EUR", "labour", 140.0, 185.0, 45.0), ("EUR", "material", 60.0, 50.0, -10.0), ("EUR", "subcontractor", 0.0, 20.0, 20.0), ("EUR", "total", 210.0, 255.0, 45.0)], \
        "P4 has no final, P5 no tender, P6 has its two types in two currencies: all three are left out; currencies are never added"
    assert v.extra == {"n_projects": 3} and v.n == 11 and "3 projects with both" in v.caption and "4 legacy projects" in v.caption and "as of 2026-11-30" in v.caption
    b = delivery.waterfall_view(ln, to_type="budget", context=CTX)
    assert [(r.currency, r.category, r.from_amount, r.to_amount, r.delta) for r in b.frame.itertuples()] == [
        ("EUR", "(none)", 10.0, 0.0, -10.0), ("EUR", "labour", 100.0, 120.0, 20.0), ("EUR", "material", 60.0, 0.0, -60.0), ("EUR", "total", 170.0, 120.0, -50.0)] and b.extra["n_projects"] == 1, "only P1 has a budget"
    r = delivery.waterfall_view(ln, from_type="final", to_type="tender", context=CTX).frame.set_index(["currency", "category"])
    assert (r.loc[("EUR", "total"), "from_amount"], r.loc[("EUR", "total"), "to_amount"], r.loc[("EUR", "total"), "delta"]) == (255.0, 210.0, -45.0), "the two types swap places"
    for args in (("tender", "final"), ("tender", "budget"), ("tender", "forecast"), ("final", "tender"), ("budget", "forecast")):
        _check_waterfall(ln, *args)
    pd.testing.assert_frame_equal(ln, before)
    with pytest.raises(FrameError, match="must differ"):
        delivery.waterfall_view(ln, from_type="final", to_type="final", context=CTX)
    with pytest.raises(FrameError, match="null currency"):
        delivery.waterfall_view(ln.assign(currency=[None] + ln.currency.tolist()[1:]), context=CTX)
    none = delivery.waterfall_view(ln[ln["prj_key"].isin(["P4", "P5"])], context=CTX)
    assert none.frame.empty and none.extra["n_projects"] == 0 and none.n == 0, "no project with both types: an empty table"


@pytest.mark.release
def test_oracle_waterfall_view_baseline_steps(load):
    """route: the estimate lines of the baseline joined to their version type and cost category with pandas, steps summed per currency and category with a python loop and compared per key; totals against estimate_version.total_cost."""
    ev, el, cc = load("projects", "estimate_version"), load("projects", "estimate_line"), load("projects", "cost_code")
    last = ev.sort_values("estimate_version").groupby(["prj_key", "type"], as_index=False).last()[["prj_key", "type", "estimate_version"]]
    lines = el.merge(last, on=["prj_key", "estimate_version"]).merge(cc[["cst_key", "category"]], on="cst_key", how="left")[["prj_key", "type", "category", "amount", "currency"]]
    assert len(lines) > 0 and lines["currency"].notna().all()
    for from_type, to_type in (("tender", "final"), ("tender", "budget"), ("tender", "forecast"), ("budget", "final")):
        v = _check_waterfall(lines, from_type, to_type)
        assert v.extra["n_projects"] > 0, (from_type, to_type)
    v = delivery.waterfall_view(lines, context=CTX)
    both = {}
    for c in ("DKK", "EUR"):
        t = ev[(ev["type"] == "tender") & (ev["currency"] == c)]
        f = ev[(ev["type"] == "final") & (ev["currency"] == c)]
        both[c] = sorted(set(t["prj_key"]) & set(f["prj_key"]))
        tot = v.frame[(v.frame.currency == c) & (v.frame.category == "total")].iloc[0]
        want_from = float(t[t["prj_key"].isin(both[c])]["total_cost"].sum())
        want_to = float(f[f["prj_key"].isin(both[c])]["total_cost"].sum())
        assert abs(tot.from_amount - want_from) <= 5 * len(both[c]) and abs(tot.to_amount - want_to) <= 5 * len(both[c]), f"{c}: the totals tie to the version totals within the rounding of the lines"
    assert v.extra["n_projects"] == len(set(both["DKK"]) | set(both["EUR"]))
