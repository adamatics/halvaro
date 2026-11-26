"""project_frame, project_status_on, active_on: boundaries on synthetic frames, counts and the row level tie on the baseline."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import Context, FrameError, PeriodError, StageRefusal, fact, registry

CTX = Context(stage="month12", role="r")
D = dt.date(2026, 6, 15)


def _p(rows):
    """rows: (prj_key, start, actual_end, status column) with python dates or None, as in the parquet."""
    return pd.DataFrame({"prj_key": [r[0] for r in rows], "start": [r[1] for r in rows], "actual_end": [r[2] for r in rows], "status": [r[3] for r in rows]})


def _status(frame, d=D):
    return dict(zip(*(delivery.project_status_on(frame, d, context=CTX)[c] for c in ("prj_key", "status"))))


def test_boundaries_start_and_actual_end_on_the_date_itself():
    frame = _p([("PRJ-000001", dt.date(2026, 6, 16), None, "active"),           # starts the day after: planned
                ("PRJ-000002", D, None, "planned"),                              # starts on the date: active
                ("PRJ-000003", dt.date(2020, 1, 1), D, "completed"),             # ends on the date: still active on it
                ("PRJ-000004", dt.date(2020, 1, 1), dt.date(2026, 6, 14), "active"),     # ended the day before: completed
                ("PRJ-000005", dt.date(2020, 1, 1), None, "completed"),          # no end: active whatever the column says
                ("PRJ-000006", dt.date(2026, 6, 16), dt.date(2026, 6, 20), "completed")])      # not started wins over an end
    assert _status(frame) == {"PRJ-000001": "planned", "PRJ-000002": "active", "PRJ-000003": "active", "PRJ-000004": "completed", "PRJ-000005": "active",
                              "PRJ-000006": "planned"}


def test_the_status_column_is_never_read():
    frame = _p([("PRJ-000001", dt.date(2020, 1, 1), None, "completed"), ("PRJ-000002", dt.date(2020, 1, 1), dt.date(2021, 1, 1), "planned")])
    assert _status(frame) == {"PRJ-000001": "active", "PRJ-000002": "completed"}
    assert _status(frame.drop(columns="status")) == _status(frame)


def test_dates_as_dates_timestamps_or_text_give_the_same_answer():
    base = _p([("PRJ-000001", dt.date(2026, 6, 16), None, ""), ("PRJ-000002", dt.date(2020, 1, 1), dt.date(2026, 6, 1), ""), ("PRJ-000003", dt.date(2020, 1, 1), None, "")])
    as_text = base.assign(start=base.start.map(str), actual_end=base.actual_end.map(lambda x: None if x is None else str(x)))
    as_ts = base.assign(start=pd.to_datetime(base.start), actual_end=pd.to_datetime(base.actual_end))
    want = {"PRJ-000001": "planned", "PRJ-000002": "completed", "PRJ-000003": "active"}
    for f in (base, as_text, as_ts):
        for d in (D, pd.Timestamp(D), "2026-06-15"):
            assert _status(f, d) == want


def test_output_shape_and_order_follow_the_input_and_the_input_is_not_changed():
    frame = _p([("PRJ-000009", dt.date(2020, 1, 1), None, "x"), ("PRJ-000002", dt.date(2020, 1, 1), dt.date(2021, 1, 1), "y")])
    before = frame.copy(deep=True)
    out = delivery.project_status_on(frame, D, context=CTX)
    assert list(out.columns) == ["prj_key", "as_of", "status"] and out.prj_key.tolist() == ["PRJ-000009", "PRJ-000002"] and (out.as_of == pd.Timestamp(D)).all()
    pd.testing.assert_frame_equal(frame, before)
    assert delivery.project_status_on(frame.iloc[:0], D, context=CTX).empty


def test_active_on_is_the_sorted_active_keys():
    frame = _p([("PRJ-000009", dt.date(2020, 1, 1), None, ""), ("PRJ-000002", dt.date(2020, 1, 1), None, ""), ("PRJ-000005", dt.date(2027, 1, 1), None, ""),
                ("PRJ-000007", dt.date(2020, 1, 1), dt.date(2021, 1, 1), "")])
    assert delivery.active_on(frame, D, context=CTX) == ["PRJ-000002", "PRJ-000009"]
    assert delivery.active_on(frame, dt.date(2028, 1, 1), context=CTX) == ["PRJ-000002", "PRJ-000005", "PRJ-000009"]
    assert delivery.active_on(frame.iloc[:0], D, context=CTX) == []


def test_bad_input_is_refused():
    frame = _p([("PRJ-000001", dt.date(2020, 1, 1), None, "")])
    with pytest.raises(FrameError, match="no start date.*PRJ-000002"):
        delivery.project_status_on(pd.concat([frame, _p([("PRJ-000002", None, None, "")])]), D, context=CTX)
    with pytest.raises(FrameError, match="duplicate prj_key.*PRJ-000001"):
        delivery.project_status_on(pd.concat([frame, frame]), D, context=CTX)
    with pytest.raises(FrameError, match="lacks column.*actual_end"):
        delivery.active_on(frame.drop(columns="actual_end"), D, context=CTX)
    with pytest.raises(PeriodError):
        delivery.project_status_on(frame, None, context=CTX)


def _full(rows):
    return pd.DataFrame(rows, columns=["prj_key", "data_depth", "legacy", "route_length_m", "currency"])


def test_project_frame_flags_and_story_parameter():
    frame = _full([("PRJ-000001", "full", False, 5200.0, "EUR"), ("PRJ-000002", "summary", True, None, "DKK"), ("PRJ-000003", "full", False, None, "DKK")])
    before = frame.copy(deep=True)
    env = delivery.project_frame(frame, context=CTX)
    out = env.value
    assert out.is_full.tolist() == [True, False, True] and out.legacy.tolist() == [False, True, False] and out.has_route_length.tolist() == [True, False, False]
    assert out.is_story.tolist() == [True, False, False] and out.currency.tolist() == ["EUR", "DKK", "DKK"]
    assert delivery.project_frame(frame, story_prj_keys=("PRJ-000003",), context=CTX).value.is_story.tolist() == [False, False, True]
    pd.testing.assert_frame_equal(frame, before)
    assert env.stage == "month12" and env.function == "halvaro.delivery.projects.project_frame" and env.status == "ok"
    assert {f[0]: f[1] for f in env.facts_used} == {"world.projects.full_total": 220, "world.projects.legacy_total": 150}


def test_counts_off_the_facts_and_inconsistent_flags_are_warnings_not_silence():
    frame = _full([("PRJ-000001", "full", True, 1.0, "EUR"), ("PRJ-000002", "summary", False, 1.0, "EUR")])
    warnings = delivery.project_frame(frame, context=CTX).warnings
    assert len(warnings) == 3 and "2 projects are both or neither" in warnings[2] and "1 full projects, world.projects.full_total says 220" in warnings[0]
    assert "1 legacy projects, world.projects.legacy_total says 150" in warnings[1]
    with pytest.raises(FrameError, match="lacks column.*currency"):
        delivery.project_frame(frame.drop(columns="currency"), context=CTX)


@pytest.mark.parametrize("stage", ["day1", "month3"])
def test_below_month12_is_refused_naming_projects(stage):
    frame = _p([("PRJ-000001", dt.date(2020, 1, 1), None, "")])
    ctx = Context(stage=stage, role="r")
    for call in (lambda: delivery.project_status_on(frame, D, context=ctx), lambda: delivery.active_on(frame, D, context=ctx),
                 lambda: delivery.project_frame(_full([("PRJ-000001", "full", False, 1.0, "EUR")]), context=ctx)):
        with pytest.raises(StageRefusal, match="projects"):
            call()


def test_registered_with_sources_facts_oracle_and_stage():
    reg = registry.registered()
    ids = {"project_frame", "project_status_on", "active_on"}
    for name in ids:
        m = reg[f"halvaro.delivery.projects.{name}"]
        assert m.oracle.startswith("py:tests/test_projects.py::") and all(s.startswith("projects.project.") for s in m.sources) and m.parameters[-1] == "context"
    assert reg["halvaro.delivery.projects.project_frame"].facts == ("world.projects.full_total", "world.projects.legacy_total")
    assert reg["halvaro.delivery.projects.project_frame"].parameters == ("project", "story_prj_keys", "context")
    assert registry.check() == [] and all(m.kb == ("DA.REF.212",) for m in reg.values() if m.id.startswith("halvaro.delivery.projects."))
    recs = {r["id"]: r for r in registry.export_index(library="halvaro-delivery") if r["id"].startswith("halvaro.delivery.projects.")}
    assert set(recs) == {f"halvaro.delivery.projects.{n}" for n in ids} and {r["stage"] for r in recs.values()} == {"month12"}


# release tests: the baseline

def _by_date(project, d):
    """Independent of the library: ISO date strings compare as text."""
    iso = d.isoformat()
    start, end = project.start.astype(str), project.actual_end.map(lambda x: None if x is None else str(x))
    return pd.Series(["planned" if s > iso else "completed" if (e is not None and e < iso) else "active" for s, e in zip(start, end)], index=project.index)


@pytest.mark.release
def test_baseline_counts_flags_and_story(load):
    project = load("projects", "project")
    env = delivery.project_frame(project, context=CTX)
    f = env.value
    assert len(f) == 370 and int(f.is_full.sum()) == fact("world.projects.full_total").value == 220 and int(f.legacy.sum()) == fact("world.projects.legacy_total").value == 150
    assert env.warnings == () and not (f.is_full & f.legacy).any() and (f.is_full | f.legacy).all()
    assert f.has_route_length.sum() == project.route_length_m.notna().sum() == 175 and f.is_story.sum() == 1 and f.loc[f.is_story, "prj_key"].tolist() == ["PRJ-000001"]
    assert (f.loc[f.legacy, "data_depth"] == "summary").all() and f.prj_key.is_unique and f.currency.notna().all()


@pytest.mark.release
def test_baseline_status_on_now_ties_to_the_status_column_row_by_row(load):
    project = load("projects", "project")
    now = fact("world.now").value
    s = delivery.project_status_on(project, now, context=CTX)
    assert s.status.tolist() == project.status.tolist(), "the dates reproduce the generator's status at now"
    counts = s.status.value_counts().to_dict()
    assert counts == {"completed": 307, "active": 56, "planned": fact("world.projects.planned_after_now").value} and counts["planned"] == 7
    assert delivery.active_on(project, now, context=CTX) == sorted(project.loc[project.status == "active", "prj_key"])


@pytest.mark.release
def test_baseline_status_matches_an_independent_computation_on_many_dates(load):
    project = load("projects", "project")
    for d in (dt.date(2014, 1, 1), dt.date(2015, 6, 30), dt.date(2019, 1, 1), dt.date(2022, 12, 31), dt.date(2025, 12, 18), dt.date(2026, 10, 30), dt.date(2026, 12, 25), dt.date(2027, 3, 1), dt.date(2030, 1, 1)):
        got = delivery.project_status_on(project, d, context=CTX).status
        assert got.tolist() == _by_date(project, d).tolist(), d
    early = delivery.project_status_on(project, dt.date(2013, 1, 1), context=CTX).status
    late = delivery.project_status_on(project, dt.date(2035, 1, 1), context=CTX).status
    assert set(early) == {"planned"}
    assert (late == "completed").sum() == project.actual_end.notna().sum() == 307 and (late == "active").sum() == 63, "no end date means active whatever the date (rule from the dates only)"


@pytest.mark.release
def test_a_date_before_now_shows_which_projects_were_not_yet_over(load):
    """On 2026-10-30 two projects the column calls completed (end 2026-11-xx) are active: the column is state at now, not a history."""
    project = load("projects", "project")
    d = dt.date(2026, 10, 30)
    s = delivery.project_status_on(project, d, context=CTX)
    diff = project.loc[s.status.to_numpy() != project.status.to_numpy(), ["prj_key", "status", "actual_end"]]
    assert len(diff) == 2 and (diff.status == "completed").all() and diff.actual_end.map(lambda x: x > d).all()


@pytest.mark.release
def test_negative_control_a_changed_date_breaks_the_tie(load):
    project = load("projects", "project").copy()
    now = fact("world.now").value
    i = project.index[project.status == "completed"][0]
    project.loc[i, "actual_end"] = dt.date(2027, 1, 1)
    s = delivery.project_status_on(project, now, context=CTX)
    assert s.status.tolist() != project.status.tolist() and s.loc[i, "status"] == "active"


# review round 1

def test_legacy_is_never_cast_a_null_or_text_is_refused():
    base = _full([("PRJ-000001", "full", False, 1.0, "EUR"), ("PRJ-000002", "summary", True, None, "DKK")])
    for bad in ([False, None], [False, float("nan")], ["False", "True"], [False, "x"]):
        with pytest.raises(FrameError, match="legacy must be True or False"):
            delivery.project_frame(base.assign(legacy=bad), context=CTX)
    ints = delivery.project_frame(base.assign(legacy=[0, 1]), context=CTX).value
    assert ints.legacy.dtype == bool and ints.legacy.tolist() == [False, True]
    objs = delivery.project_frame(base.assign(legacy=pd.Series([False, True], dtype=object)), context=CTX).value
    assert objs.legacy.dtype == bool and objs.legacy.tolist() == [False, True]


def test_story_keys_as_text_none_or_a_list():
    frame = _full([("PRJ-000001", "full", False, 1.0, "EUR"), ("P", "full", False, 1.0, "EUR"), ("PRJ-000003", "summary", True, None, "DKK")])
    assert delivery.project_frame(frame, story_prj_keys="PRJ-000003", context=CTX).value.is_story.tolist() == [False, False, True]
    assert delivery.project_frame(frame, story_prj_keys=None, context=CTX).value.is_story.sum() == 0
    assert delivery.project_frame(frame, story_prj_keys=["PRJ-000001", "P"], context=CTX).value.is_story.tolist() == [True, True, False]


def test_results_keep_the_input_index_so_label_alignment_is_right():
    frame = _p([("PRJ-000001", dt.date(2020, 1, 1), None, "active"), ("PRJ-000002", dt.date(2027, 1, 1), None, "planned"), ("PRJ-000003", dt.date(2020, 1, 1), dt.date(2021, 1, 1), "completed")])
    shuffled = frame.iloc[::-1]
    out = delivery.project_status_on(shuffled, D, context=CTX)
    assert out.index.tolist() == [2, 1, 0] and shuffled.assign(st=out.status).sort_index().st.tolist() == ["active", "planned", "completed"]
    pf = delivery.project_frame(_full([("PRJ-000001", "full", False, 1.0, "EUR"), ("PRJ-000002", "summary", True, None, "DKK")]).iloc[::-1], context=CTX).value
    assert pf.index.tolist() == [1, 0] and list(pf.columns)[-3:] == ["is_full", "has_route_length", "is_story"]


def test_time_of_day_time_zones_and_unreadable_dates():
    frame = _p([("PRJ-000001", pd.Timestamp("2026-06-15 10:00"), pd.Timestamp("2026-06-15 09:00"), ""), ("PRJ-000002", dt.date(2020, 1, 1), None, "")])
    assert _status(frame) == {"PRJ-000001": "active", "PRJ-000002": "active"}, "start and end on the date itself, whatever the time of day"
    out = delivery.project_status_on(frame, pd.Timestamp("2026-06-15 14:30"), context=CTX)
    assert out.status.tolist() == ["active", "active"] and (out.as_of == pd.Timestamp(D)).all()
    with pytest.raises(PeriodError, match="time zone"):
        delivery.project_status_on(frame, pd.Timestamp("2026-06-15", tz="UTC"), context=CTX)
    with pytest.raises(FrameError, match="time zone"):
        delivery.project_status_on(frame.assign(start=pd.to_datetime(frame.start).dt.tz_localize("UTC")), D, context=CTX)
    for bad in ("junk", 20260615, 1.5, True, "not a date"):
        with pytest.raises(PeriodError):
            delivery.project_status_on(frame, bad, context=CTX)
    with pytest.raises(FrameError, match="not a date"):
        delivery.project_status_on(frame.assign(start=["2020-01-01", "x"]), D, context=CTX)
    with pytest.raises(FrameError, match="not a date"):
        delivery.project_status_on(frame.assign(start=[dt.date(1500, 1, 1), dt.date(2020, 1, 1)]), D, context=CTX)


def test_planned_wins_over_an_end_before_the_start_and_keys_must_be_present():
    assert _status(_p([("PRJ-000001", dt.date(2026, 6, 16), dt.date(2026, 6, 1), "")])) == {"PRJ-000001": "planned"}
    frame = _p([("PRJ-000001", dt.date(2020, 1, 1), None, ""), (None, dt.date(2020, 1, 1), None, "")])
    with pytest.raises(FrameError, match="without prj_key"):
        delivery.active_on(frame, D, context=CTX)
    with pytest.raises(FrameError, match="DataFrame"):
        delivery.active_on([1, 2], D, context=CTX)
    with pytest.raises(FrameError, match="duplicate column names.*start"):
        delivery.active_on(pd.concat([frame.iloc[:1], frame.iloc[:1][["start"]].rename(columns={"start": "start"})], axis=1), D, context=CTX)
    with pytest.raises(FrameError, match="has 1 duplicate prj_key"):
        delivery.active_on(pd.concat([frame.iloc[:1]] * 2), D, context=CTX)


def test_status_words_and_dtype():
    out = delivery.project_status_on(_p([("PRJ-000001", dt.date(2020, 1, 1), None, "")]), D, context=CTX)
    assert out.status.dtype == object and set(out.status) <= {"planned", "active", "completed"}


@pytest.mark.parametrize("n_full,n_legacy,expect", [(221, 150, "221 full projects"), (220, 151, "151 legacy projects")])
def test_a_count_above_the_fact_also_warns(n_full, n_legacy, expect):
    rows = [(f"PRJ-{i:06d}", "full", False, 1.0, "EUR") for i in range(n_full)] + [(f"PRJ-{1000 + i:06d}", "summary", True, None, "DKK") for i in range(n_legacy)]
    assert any(expect in w for w in delivery.project_frame(_full(rows), context=CTX).warnings)


def test_both_and_neither_warn_separately_and_odd_depth_is_flagged():
    both = delivery.project_frame(_full([("PRJ-000001", "full", True, 1.0, "EUR")]), context=CTX).warnings
    neither = delivery.project_frame(_full([("PRJ-000001", "summary", False, 1.0, "EUR")]), context=CTX).warnings
    assert any("1 projects are both or neither" in w for w in both) and any("1 projects are both or neither" in w for w in neither)
    odd = delivery.project_frame(_full([("PRJ-000001", None, False, 1.0, "EUR"), ("PRJ-000002", "other", True, 1.0, "EUR")]), context=CTX)
    assert any("2 projects have a data_depth other than" in w for w in odd.warnings) and odd.value.is_full.tolist() == [False, False]


def test_zero_route_length_counts_and_the_derived_columns_are_not_overwritten():
    frame = _full([("PRJ-000001", "full", False, 0.0, "EUR"), ("PRJ-000002", "full", False, None, "EUR")])
    assert delivery.project_frame(frame, context=CTX).value.has_route_length.tolist() == [True, False]
    with pytest.raises(FrameError, match="already has column.*is_story"):
        delivery.project_frame(frame.assign(is_story=True), context=CTX)


@pytest.mark.parametrize("column", ["data_depth", "legacy", "route_length_m", "currency", "prj_key"])
def test_project_frame_names_every_missing_column(column):
    frame = _full([("PRJ-000001", "full", False, 1.0, "EUR")])
    with pytest.raises(FrameError, match=f"lacks column.*{column}"):
        delivery.project_frame(frame.drop(columns=column), context=CTX)


def test_the_envelope_lists_all_sources_and_the_refusal_names_the_function():
    env = delivery.project_frame(_full([("PRJ-000001", "full", False, 1.0, "EUR")]), context=CTX)
    assert len(env.sources) == 5 and env.sources == tuple(registry.registered()["halvaro.delivery.projects.project_frame"].sources)
    with pytest.raises(StageRefusal, match="halvaro.delivery.projects.active_on"):
        delivery.active_on(_p([("PRJ-000001", dt.date(2020, 1, 1), None, "")]), D, context=Context(stage="day1", role="r"))
